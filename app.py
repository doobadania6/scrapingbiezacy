@app.route('/sources', methods=['GET', 'POST', 'DELETE'])
def manage_sources():
    """Zarządzaj źródłami scrapowania"""
    try:
        if request.method == 'GET':
            sources = load_sources()
            return jsonify({"sources": sources})
        
        elif request.method == 'POST':
            data = request.json
            url = data.get('url', '').strip()
            domain = data.get('domain', '').strip()
            
            if not url or not domain:
                return jsonify({"error": "URL i domain są wymagane"}), 400
            
            sources = load_sources()
            # Sprawdź duplikaty
            if any(s['domain'] == domain for s in sources):
                return jsonify({"error": "Źródło z taką domeną już istnieje"}), 400
            
            sources.append({"url": url, "domain": domain})
            save_sources(sources)
            return jsonify({"success": True, "sources": sources})
        
        elif request.method == 'DELETE':
            data = request.json
            domain = data.get('domain', '').strip()
            
            sources = load_sources()
            sources = [s for s in sources if s['domain'] != domain]
            save_sources(sources)
            return jsonify({"success": True, "sources": sources})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/publish', methods=['POST'])import os
import json
import requests
from flask import Flask, render_template_string, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from google import genai as google_genai
from dotenv import load_dotenv

# Załaduj zmienne z pliku .env
load_dotenv()

app = Flask(__name__)
PORT = int(os.environ.get("PORT", 10000))

# Przechowuj źródła w pamięci (lub w pliku)
SOURCES_FILE = "sources.json"

def load_sources():
    """Załaduj źródła z pliku JSON"""
    if os.path.exists(SOURCES_FILE):
        try:
            with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return [
                {"url": "https://kvlt.pl/newsy/", "domain": "kvlt.pl"},
                {"url": "https://chaosvault.com/category/newsy/", "domain": "chaosvault.com"}
            ]
    return [
        {"url": "https://kvlt.pl/newsy/", "domain": "kvlt.pl"},
        {"url": "https://chaosvault.com/category/newsy/", "domain": "chaosvault.com"}
    ]

def save_sources(sources):
    """Zapisz źródła do pliku JSON"""
    with open(SOURCES_FILE, 'w', encoding='utf-8') as f:
        json.dump(sources, f, ensure_ascii=False, indent=2)

# --- KONFIGURACJA KLIENTA GEMINI ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY nie znaleziony w .env lub zmiennych środowiskowych!")

client = google_genai.Client(api_key=GEMINI_API_KEY)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Metal Growl AI</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            background: linear-gradient(135deg, #0f0f0f 0%, #1a1a2e 100%);
            color: #e8e8e8;
            font-family: 'Inter', 'Segoe UI', sans-serif;
            min-height: 100vh;
        }
        .header {
            text-align: center;
            padding: 60px 20px 40px;
            background: linear-gradient(180deg, rgba(255,255,255,0.05) 0%, transparent 100%);
            border-bottom: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 50px;
        }
        .header h1 {
            font-size: 3.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #fff 0%, #b0b0b0 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
            letter-spacing: -2px;
        }
        .header p { color: #888; font-size: 0.95rem; letter-spacing: 2px; }
        .container-articles { max-width: 1400px; margin: 0 auto; padding: 0 20px 80px; }
        .article-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 32px;
            margin-bottom: 32px;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
        }
        .article-card:hover {
            border-color: rgba(255,255,255,0.15);
            background: rgba(255,255,255,0.06);
        }
        .article-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 24px;
        }
        .source-tag {
            display: inline-block;
            background: rgba(100,200,255,0.15);
            color: #64c8ff;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
            letter-spacing: 1px;
        }
        .article-card h3 {
            font-size: 1.8rem;
            font-weight: 600;
            margin-bottom: 8px;
            line-height: 1.4;
        }
        .accordion-button {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            color: #e8e8e8;
            font-weight: 500;
            padding: 16px 20px;
            border-radius: 12px;
        }
        .accordion-button:not(.collapsed) {
            background: rgba(100,200,255,0.1);
            border-color: rgba(100,200,255,0.3);
            color: #64c8ff;
        }
        .accordion-body {
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.05);
            border-top: none;
            padding: 20px;
            color: #d0d0d0;
            line-height: 1.8;
            font-size: 0.95rem;
        }
        .btn-generate {
            background: linear-gradient(135deg, #64c8ff 0%, #3a9fcc 100%);
            border: none;
            color: #fff;
            font-weight: 600;
            padding: 12px 28px;
            border-radius: 10px;
            transition: all 0.3s ease;
            margin-top: 24px;
        }
        .btn-generate:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(100,200,255,0.3);
            color: #fff;
        }
        .btn-publish {
            background: linear-gradient(135deg, #4ade80 0%, #22c55e 100%);
            border: none;
            color: #fff;
            font-weight: 600;
            padding: 10px 24px;
            border-radius: 10px;
            transition: all 0.3s ease;
        }
        .btn-publish:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(74,222,128,0.3);
            color: #fff;
        }
        .status-message {
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 500;
            margin-left: 16px;
        }
        .status-success { background: rgba(74,222,128,0.2); color: #4ade80; }
        .status-error { background: rgba(239,68,68,0.2); color: #ef4444; }
        .accordion { gap: 16px; }
        .accordion-item {
            background: transparent;
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
            overflow: hidden;
        }
        .publish-section {
            display: none;
            margin-top: 24px;
            padding-top: 24px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }
        .publish-section.show {
            display: block;
        }
        textarea {
            background: rgba(0,0,0,0.4) !important;
            color: #64c8ff !important;
            border: 1px solid rgba(100,200,255,0.2) !important;
            border-radius: 10px !important;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
        }
        input[type="text"] {
            background: rgba(0,0,0,0.4) !important;
            color: #e8e8e8 !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            border-radius: 10px !important;
        }
        .loading { opacity: 0.6; pointer-events: none; }
        .settings-panel {
            position: fixed;
            top: 0;
            right: -400px;
            width: 400px;
            height: 100vh;
            background: linear-gradient(135deg, #0f0f0f 0%, #1a1a2e 100%);
            border-left: 1px solid rgba(255,255,255,0.1);
            padding: 30px;
            overflow-y: auto;
            transition: right 0.3s ease;
            z-index: 1000;
        }
        .settings-panel.open { right: 0; }
        .settings-panel h2 {
            font-size: 1.5rem;
            margin-bottom: 24px;
            color: #64c8ff;
        }
        .settings-close {
            position: absolute;
            top: 20px;
            right: 20px;
            background: none;
            border: none;
            color: #888;
            font-size: 1.5rem;
            cursor: pointer;
        }
        .source-item {
            background: rgba(255,255,255,0.05);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.9rem;
        }
        .source-item button {
            background: rgba(239,68,68,0.2);
            border: none;
            color: #ef4444;
            padding: 4px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85rem;
        }
        .source-form {
            background: rgba(100,200,255,0.1);
            padding: 16px;
            border-radius: 10px;
            border: 1px solid rgba(100,200,255,0.2);
        }
        .source-form input {
            width: 100%;
            padding: 8px 12px;
            margin-bottom: 10px;
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 6px;
            color: #e8e8e8;
        }
        .source-form button {
            width: 100%;
            padding: 10px;
            background: linear-gradient(135deg, #64c8ff 0%, #3a9fcc 100%);
            border: none;
            color: #fff;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
        }
        .settings-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 60px;
            height: 60px;
            background: linear-gradient(135deg, #64c8ff 0%, #3a9fcc 100%);
            border: none;
            border-radius: 50%;
            color: #fff;
            font-size: 1.5rem;
            cursor: pointer;
            box-shadow: 0 10px 30px rgba(100,200,255,0.3);
            transition: all 0.3s ease;
        }
        .settings-btn:hover {
            transform: scale(1.1);
            box-shadow: 0 15px 40px rgba(100,200,255,0.4);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>METAL AI</h1>
        <p>ADVANCED CONTENT GENERATOR</p>
    </div>
    
    <div class="container-articles">
        {% if articles %}
        {% for art in articles %}
        <div class="article-card">
            <div class="article-header">
                <div>
                    <span class="source-tag">{{ art.source }}</span>
                    <h3>{{ art.title }}</h3>
                </div>
            </div>
            
            <div class="accordion" id="accordion-{{ loop.index }}">
                <div class="accordion-item">
                    <h2 class="accordion-header">
                        <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#original-{{ loop.index }}">
                            📄 Treść Oryginalna
                        </button>
                    </h2>
                    <div id="original-{{ loop.index }}" class="accordion-collapse collapse" data-bs-parent="#accordion-{{ loop.index }}">
                        <div class="accordion-body">{{ art.raw_content }}</div>
                    </div>
                </div>
                
                <div class="accordion-item">
                    <h2 class="accordion-header">
                        <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#generated-{{ loop.index }}">
                            ✨ Treść Wygenerowana
                        </button>
                    </h2>
                    <div id="generated-{{ loop.index }}" class="accordion-collapse collapse" data-bs-parent="#accordion-{{ loop.index }}">
                        <div class="accordion-body" id="gen-content-{{ loop.index }}">
                            <p style="color: #888;">Kliknij przycisk poniżej, aby wygenerować treść...</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <button class="btn btn-generate" onclick="generateNews({{ loop.index }})">✨ GENERUJ WERSJĘ AI</button>
            
            <div class="publish-section" id="publish-{{ loop.index }}">
                <label class="d-block mb-3" style="font-weight: 600; color: #64c8ff;">Edytuj przed wysłaniem:</label>
                
                <label class="d-block mb-2" style="font-size: 0.9rem; color: #aaa;">Tytuł:</label>
                <input type="text" id="ai-title-{{ loop.index }}" class="form-control mb-3" placeholder="Wygenerowany tytuł...">
                
                <label class="d-block mb-2" style="font-size: 0.9rem; color: #aaa;">Treść (HTML):</label>
                <textarea id="ai-content-{{ loop.index }}" class="form-control mb-3" rows="8"></textarea>
                
                <div class="d-flex align-items-center">
                    <button class="btn btn-publish" onclick="sendToWP({{ loop.index }})">🚀 WYŚLIJ DO WORDPRESS</button>
                    <span id="status-{{ loop.index }}" class="status-message"></span>
                </div>
            </div>
        </div>
        {% endfor %}
        {% else %}
        <div style="text-align: center; padding: 60px 20px;">
            <p style="color: #888; font-size: 1.1rem;">⏳ Ładowanie artykułów...</p>
        </div>
        {% endif %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function toggleSettings() {
            document.getElementById('settings-panel').classList.toggle('open');
        }

        async function loadSources() {
            try {
                const res = await fetch('/sources');
                const data = await res.json();
                const list = document.getElementById('sources-list');
                list.innerHTML = '';
                
                data.sources.forEach(source => {
                    const item = document.createElement('div');
                    item.className = 'source-item';
                    item.innerHTML = `
                        <div>
                            <strong>${source.domain}</strong><br>
                            <small style="color: #888;">${source.url}</small>
                        </div>
                        <button onclick="deleteSource('${source.domain}')">Usuń</button>
                    `;
                    list.appendChild(item);
                });
            } catch (e) {
                console.error('Błąd ładowania źródeł:', e);
            }
        }

        async function addSource() {
            const url = document.getElementById('new-url').value.trim();
            const domain = document.getElementById('new-domain').value.trim();
            
            if (!url || !domain) {
                alert('Wypełnij oba pola!');
                return;
            }
            
            try {
                const res = await fetch('/sources', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ url, domain })
                });
                
                const data = await res.json();
                if (data.error) {
                    alert('Błąd: ' + data.error);
                } else {
                    document.getElementById('new-url').value = '';
                    document.getElementById('new-domain').value = '';
                    loadSources();
                    alert('✅ Źródło dodane! Odśwież stronę, aby pobrać artykuły.');
                }
            } catch (e) {
                alert('Błąd połączenia: ' + e.message);
            }
        }

        async function deleteSource(domain) {
            if (!confirm('Czy na pewno usunąć to źródło?')) return;
            
            try {
                const res = await fetch('/sources', {
                    method: 'DELETE',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ domain })
                });
                
                const data = await res.json();
                if (data.success) {
                    loadSources();
                    alert('✅ Źródło usunięte!');
                }
            } catch (e) {
                alert('Błąd: ' + e.message);
            }
        }

        // Załaduj źródła na starcie
        loadSources();
        async function generateNews(id) {
            const btn = event.target;
            const originalContent = document.getElementById(`original-${id}`).innerText;
            const title = document.querySelector(`.article-card:has(#accordion-${id}) h3`).innerText;
            
            btn.disabled = true;
            btn.classList.add('loading');
            btn.innerText = "⏳ Przetwarzanie...";

            try {
                const response = await fetch('/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ title: title, content: originalContent })
                });
                
                const data = await response.json();
                if (data.error) throw new Error(data.error);

                document.getElementById(`gen-content-${id}`).innerHTML = `<p>${data.content}</p>`;
                document.getElementById(`ai-title-${id}`).value = data.title;
                document.getElementById(`ai-content-${id}`).value = data.content;
                document.getElementById(`publish-${id}`).classList.add('show');
                
                btn.innerText = "✅ Gotowe";
            } catch (e) {
                alert('Błąd: ' + e.message);
                btn.disabled = false;
                btn.classList.remove('loading');
                btn.innerText = "❌ Spróbuj ponownie";
            }
        }

        async function sendToWP(id) {
            const status = document.getElementById(`status-${id}`);
            status.innerText = "⏳ Wysyłanie...";
            status.className = "status-message";
            
            try {
                const res = await fetch('/publish', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        title: document.getElementById(`ai-title-${id}`).value,
                        content: document.getElementById(`ai-content-${id}`).value
                    })
                });
                if(res.ok) {
                    status.innerText = "✅ Wysłano do WordPressa!";
                    status.classList.add('status-success');
                } else {
                    status.innerText = "❌ Błąd WordPressa";
                    status.classList.add('status-error');
                }
            } catch (e) {
                status.innerText = "❌ Błąd połączenia";
                status.classList.add('status-error');
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    all_news = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    sources = load_sources()
    
    for s in sources:
        try:
            r = requests.get(s["url"], headers=headers, timeout=8)
            soup = BeautifulSoup(r.text, 'html.parser')
            # Szuka wszystkich linkówów do artykułów (nie ograniczaj do 3)
            links = [urljoin(s["url"], a['href']) for a in soup.find_all('a', href=True) 
                     if s["domain"] in a['href'] and len(a['href']) > 45 and "page" not in a['href']]
            # Usuń duplikaty i ogranicz do 10
            links = list(dict.fromkeys(links))[:10]
            for l in links:
                try:
                    ar = requests.get(l, headers=headers, timeout=8)
                    asoup = BeautifulSoup(ar.text, 'html.parser')
                    t = asoup.find('h1').get_text(strip=True) if asoup.find('h1') else "Metal News"
                    c_tag = asoup.find('article') or asoup.find('div', class_='entry-content') or asoup.find('div', class_='td-post-content')
                    c = c_tag.get_text(separator=' ', strip=True)[:2000] if c_tag else "Brak treści."
                    all_news.append({"title": t, "raw_content": c, "source": s["domain"]})
                except: 
                    continue
        except: 
            continue
    return render_template_string(HTML_TEMPLATE, articles=all_news)

@app.route('/debug-models', methods=['GET'])
def debug_models():
    """Endpoint do debugowania dostępnych modeli"""
    try:
        response = client.models.list()
        models = [m.name for m in response.models]
        return jsonify({"available_models": models})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
def generate():
    data = request.json
    prompt = (
        f"Jesteś profesjonalnym redaktorem prasowym. Przetwórz poniższy artykuł, zachowując wszystkie istotne informacje, "
        f"ale przedstawiając go w bardziej formalny, klarowny i rzeczowy sposób. Tekst powinien być informacyjny, "
        f"ustrukturyzowany i łatwy do przeczytania. Unikaj emocjonalnych sformułowań i pompatyczności. "
        f"Tytuł: '{data['title']}' \n\nTreść: '{data['content']}'. "
        f"Zwróć wynik TYLKO jako czysty JSON: {{\"title\": \"Nowy tytuł (krótki, trafny)\", \"content\": \"Przerobiona treść (plain text, bez HTML)\"}}"
    )
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        text = response.text
        
        # Bezpieczne ekstraktowanie JSON z odpowiedzi
        if "{" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]
        
        result = json.loads(text)
        return jsonify(result)
        
    except json.JSONDecodeError:
        return jsonify({"error": "Błąd parsowania JSON z odpowiedzi AI"}), 500
    except Exception as e:
        return jsonify({"error": f"Błąd AI: {str(e)}"}), 500

@app.route('/publish', methods=['POST'])
def publish():
    data = request.json
    auth = (os.environ.get("WP_USER"), os.environ.get("WP_APP_PASSWORD"))
    wp_url = os.environ.get("WP_URL")
    
    if not wp_url:
        return jsonify({"error": "WP_URL nie skonfigurowany"}), 500
    
    payload = {"title": data['title'], "content": data['content'], "status": "draft"}
    
    try:
        r = requests.post(wp_url, auth=auth, json=payload, timeout=10)
        if r.status_code == 201:
            return jsonify({"ok": True})
        else:
            return jsonify({"error": f"WP error: {r.status_code}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    app.run(host='0.0.0.0', port=PORT, debug=False)
