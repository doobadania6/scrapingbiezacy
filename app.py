import os
import json
import requests
from flask import Flask, render_template_string, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import google.generativeai as genai

# --- 1. KONFIGURACJA ---
app = Flask(__name__)
PORT = int(os.environ.get("PORT", 10000))

# Konfiguracja AI (pobierana z Environment Variables na Render)
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

# Dane WordPress (pobierane z Environment Variables na Render)
WP_USER = os.environ.get("WP_USER")
WP_APP_PASS = os.environ.get("WP_APP_PASSWORD")
WP_URL = os.environ.get("WP_URL")

# --- 2. SZABLON HTML (Interfejs redaktora) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KVLT & Chaos AI Engine</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0f0f0f; color: #f0f0f0; font-family: 'Inter', sans-serif; }
        .card { background-color: #1a1a1a; border: 1px solid #333; border-radius: 12px; margin-bottom: 25px; overflow: hidden; }
        .card-header { background-color: #252525; border-bottom: 1px solid #333; font-weight: bold; color: #ff4d4d; }
        .editable-area { background-color: #121212; color: #e0e0e0; border: 1px solid #444; width: 100%; min-height: 250px; padding: 15px; border-radius: 8px; font-size: 0.95rem; }
        .btn-primary { background-color: #ff4d4d; border: none; font-weight: bold; padding: 10px 25px; }
        .btn-primary:hover { background-color: #cc0000; }
        .source-tag { font-size: 0.7rem; background: #333; padding: 3px 8px; border-radius: 4px; text-transform: uppercase; color: #aaa; }
    </style>
</head>
<body class="container py-5">
    <header class="text-center mb-5">
        <h1 class="display-5 fw-bold text-white">🤘 METAL NEWS <span style="color: #ff4d4d;">AI</span></h1>
        <p class="text-muted">Źródła: KVLT.pl | ChaosVault.com</p>
        <button onclick="location.reload()" class="btn btn-outline-light btn-sm">Odśwież i pobierz nowe</button>
    </header>

    <div id="articles">
        {% if not articles %}
            <div class="text-center py-5">
                <div class="spinner-border text-danger" role="status"></div>
                <p class="mt-3 text-muted">Scrapowanie i magia AI w toku... (może to zająć do 30 sek.)</p>
            </div>
        {% endif %}

        {% for art in articles %}
        <div class="card shadow-lg" id="card-{{ loop.index }}">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span>PROPOZYCJA REDAKCYJNA</span>
                <span class="source-tag">{{ art.source_domain }}</span>
            </div>
            <div class="card-body">
                <div class="mb-3">
                    <label class="form-label small text-muted">Tytuł (edytuj):</label>
                    <input type="text" id="title-{{ loop.index }}" class="form-control bg-dark text-white border-secondary" value="{{ art.ai_title }}">
                </div>
                <div class="mb-3">
                    <label class="form-label small text-muted">Treść HTML (edytuj):</label>
                    <textarea id="content-{{ loop.index }}" class="editable-area">{{ art.ai_content }}</textarea>
                </div>
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <button onclick='publishPost({{ loop.index }})' class="btn btn-primary" id="btn-{{ loop.index }}">Wyślij do WordPress</button>
                        <span id="status-{{ loop.index }}" class="ms-3 small fw-bold"></span>
                    </div>
                    <a href="{{ art.url }}" target="_blank" class="text-muted small text-decoration-none text-info">Oryginał ↗</a>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>

    <script>
        async function publishPost(id) {
            const btn = document.getElementById(`btn-${id}`);
            const status = document.getElementById(`status-${id}`);
            const title = document.getElementById(`title-${id}`).value;
            const content = document.getElementById(`content-${id}`).value;

            btn.disabled = true;
            status.innerHTML = "Wysyłanie...";
            status.style.color = "#aaa";

            try {
                const response = await fetch('/publish', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ ai_title: title, ai_content: content })
                });
                
                if (response.ok) {
                    status.innerHTML = "Wysłano pomyślnie!";
                    status.style.color = "#00ff00";
                    btn.className = "btn btn-secondary disabled";
                    btn.innerHTML = "Wysłano";
                } else { throw new Error(); }
            } catch (e) {
                status.innerHTML = "Błąd wysyłki!";
                status.style.color = "#ff4d4d";
                btn.disabled = false;
            }
        }
    </script>
</body>
</html>
"""

# --- 3. LOGIKA SCRAPOWANIA ---
def get_all_news():
    all_articles = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    sources = [
        {"url": "https://kvlt.pl/newsy/", "domain": "kvlt.pl", "selector": ".entry-content"},
        {"url": "https://chaosvault.com/category/newsy/", "domain": "chaosvault.com", "selector": ".td-post-content, article"}
    ]
    
    for source in sources:
        try:
            r = requests.get(source["url"], headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                # Odfiltrowujemy śmieciowe linki
                if source["domain"] in href and "/page/" not in href and len(href) > (len(source["url"]) + 5):
                    links.append(urljoin(source["url"], href))
            
            # Pobieramy 2 najnowsze z każdego źródła (razem 4) dla balansu szybkości
            for link in list(dict.fromkeys(links))[:2]:
                try:
                    res = requests.get(link, headers=headers, timeout=10)
                    art_soup = BeautifulSoup(res.text, 'html.parser')
                    
                    title = art_soup.find('h1').get_text(strip=True) if art_soup.find('h1') else "Nowy news"
                    content_div = art_soup.select_one(source["selector"])
                    
                    if content_div:
                        for tag in content_div(['script', 'style', 'nav', 'aside']): tag.decompose()
                        raw_text = content_div.get_text(separator=' ', strip=True)[:3000]
                        
                        # Przetwarzanie przez AI Gemini
                        prompt = f"Działaj jako redaktor. Przeredaguj ten news muzyczny: {title}. Treść: {raw_text}. Zwróć TYLKO czysty JSON: {{\"title\": \"...\", \"content\": \"...\"}} (content ma być w HTML, używaj <p>)."
                        
                        response = model.generate_content(prompt)
                        clean_json = response.text.strip().replace('```json', '').replace('```', '')
                        ai_data = json.loads(clean_json)

                        all_articles.append({
                            "original_title": title,
                            "ai_title": ai_data.get('title', title),
                            "ai_content": ai_data.get('content', 'Błąd generowania treści'),
                            "url": link,
                            "source_domain": source["domain"]
                        })
                except Exception as e:
                    print(f"Błąd przy artykule {link}: {e}")
                    continue
        except Exception as e:
            print(f"Błąd przy źródle {source['domain']}: {e}")
            
    return all_articles

# --- 4. TRASY (ENDPOINTS) ---
@app.route('/', methods=['GET', 'HEAD'])
def index():
    if request.method == 'HEAD':
        return '', 200
    
    # Wywołanie głównej funkcji i renderowanie
    articles_data = get_all_news()
    return render_template_string(HTML_TEMPLATE, articles=articles_data)

@app.route('/publish', methods=['POST'])
def publish():
    data = request.json
    auth = (WP_USER, WP_APP_PASS)
    payload = {
        "title": data['ai_title'],
        "content": data['ai_content'],
        "status": "draft"
    }
    try:
        r = requests.post(WP_URL, auth=auth, json=payload, timeout=10)
        if r.status_code == 201:
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "code": r.status_code}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- 5. URUCHOMIENIE ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
