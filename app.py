import os
import json
import requests
from flask import Flask, render_template_string, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import google.generativeai as genai

app = Flask(__name__)
PORT = int(os.environ.get("PORT", 10000))

# --- KONFIGURACJA AI ---
GEMINI_API_KEY = "AIzaSyB1U0Vhm1wLD6RbNovPhAHDJPB_2Yg6Rq4"
genai.configure(api_key=GEMINI_API_KEY)
# Ustawienie modelu z niskim progiem blokowania (ważne przy newsach o metalu)
model = genai.GenerativeModel('gemini-1.5-flash')

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Metal News Engine v6</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0d0d0d; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
        .article-card { background: #1a1a1a; border-radius: 12px; padding: 20px; margin-bottom: 25px; border: 1px solid #333; transition: 0.3s; }
        .article-card:hover { border-color: #ff3d00; }
        .ai-box { display: none; background: #222; border: 1px solid #444; padding: 15px; border-radius: 8px; margin-top: 15px; border-left: 4px solid #6200ea; }
        textarea { background: #000 !important; color: #0f0 !important; font-family: monospace; border: 1px solid #555 !important; font-size: 0.85rem; }
        .btn-gemini { background-color: #6200ea; border: none; color: white; font-weight: bold; }
        .btn-gemini:disabled { background-color: #444; }
        .badge-source { font-size: 0.7rem; background: #333; color: #ff3d00; padding: 5px 10px; border-radius: 5px; text-transform: uppercase; }
    </style>
</head>
<body class="container py-5">
    <header class="text-center mb-5">
        <h1 class="display-5 fw-bold">🤘 METAL NEWS <span style="color: #ff3d00;">AI</span></h1>
        <p class="text-muted">System redakcyjny v6 (Server-Side processing)</p>
        <button onclick="location.reload()" class="btn btn-outline-light btn-sm">Skanuj portale</button>
    </header>
    
    <div id="news-feed">
        {% if not articles %}
            <div class="alert alert-dark text-center">Brak nowych newsów. Spróbuj odświeżyć.</div>
        {% endif %}
        
        {% for art in articles %}
        <div class="article-card">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="badge-source">{{ art.source }}</span>
                <a href="{{ art.url }}" target="_blank" class="text-muted small">Oryginał ↗</a>
            </div>
            <h3 id="title-{{ loop.index }}">{{ art.title }}</h3>
            <div style="display:none" id="raw-{{ loop.index }}">{{ art.raw_content }}</div>
            
            <button class="btn btn-gemini btn-sm mt-2" onclick="processWithAI({{ loop.index }})">✨ PRZERÓB PRZEZ AI</button>
            
            <div class="ai-box" id="ai-box-{{ loop.index }}">
                <div class="mb-2">
                    <label class="small text-muted">Tytuł AI:</label>
                    <input type="text" id="ai-title-{{ loop.index }}" class="form-control bg-dark text-white border-secondary">
                </div>
                <div class="mb-2">
                    <label class="small text-muted">Treść (HTML):</label>
                    <textarea id="ai-content-{{ loop.index }}" class="form-control" rows="10"></textarea>
                </div>
                <div class="d-flex align-items-center">
                    <button class="btn btn-success btn-sm" onclick="publishToWP({{ loop.index }})">🚀 WYŚLIJ DO WORDPRESS</button>
                    <div id="status-{{ loop.index }}" class="ms-3 small"></div>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>

    <script>
        async function processWithAI(id) {
            const btn = event.target;
            const title = document.getElementById(`title-${id}`).innerText;
            const text = document.getElementById(`raw-${id}`).innerText;
            
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Gemini pracuje...';

            try {
                const response = await fetch('/run_ai_server', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ title: title, text: text })
                });

                const data = await response.json();
                
                if (!response.ok) throw new Error(data.error || "Błąd serwera");

                document.getElementById(`ai-box-${id}`).style.display = "block";
                document.getElementById(`ai-title-${id}`).value = data.title;
                document.getElementById(`ai-content-${id}`).value = data.content;
                btn.innerHTML = "✅ Gotowe";
                btn.className = "btn btn-outline-secondary btn-sm mt-2";
            } catch (e) {
                alert("Błąd: " + e.message);
                btn.disabled = false;
                btn.innerHTML = "❌ Spróbuj ponownie";
            }
        }

        async function publishToWP(id) {
            const status = document.getElementById(`status-${id}`);
            status.innerHTML = "Wysyłanie...";
            status.className = "ms-3 small text-info";

            try {
                const res = await fetch('/publish', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        ai_title: document.getElementById(`ai-title-${id}`).value,
                        ai_content: document.getElementById(`ai-content-${id}`).value
                    })
                });

                if (res.ok) {
                    status.innerHTML = "✅ Wysłano jako szkic!";
                    status.className = "ms-3 small text-success";
                } else {
                    throw new Error();
                }
            } catch (e) {
                status.innerHTML = "❌ Błąd WordPressa";
                status.className = "ms-3 small text-danger";
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    all_news = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    sources = [
        {"url": "https://kvlt.pl/newsy/", "domain": "kvlt.pl"},
        {"url": "https://chaosvault.com/category/newsy/", "domain": "chaosvault.com"}
    ]
    
    for s in sources:
        try:
            r = requests.get(s["url"], headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            # Szukamy linków do artykułów (długie linki z domeny)
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if s["domain"] in href and len(href) > 40 and "/page/" not in href:
                    links.append(urljoin(s["url"], href))
            
            for l in list(dict.fromkeys(links))[:4]: # Max 4 z każdego źródła
                try:
                    res = requests.get(l, headers=headers, timeout=7)
                    asoup = BeautifulSoup(res.text, 'html.parser')
                    title = asoup.find('h1').get_text(strip=True) if asoup.find('h1') else None
                    if not title: continue
                    
                    ctag = asoup.find('article') or asoup.find('div', class_='entry-content') or asoup.find('div', class_='td-post-content')
                    content = ctag.get_text(separator=' ', strip=True) if ctag else "Brak treści źródłowej."
                    
                    all_news.append({"title": title, "raw_content": content[:1500], "url": l, "source": s["domain"]})
                except: continue
        except: continue
            
    return render_template_string(HTML_TEMPLATE, articles=all_news)

@app.route('/run_ai_server', methods=['POST'])
def run_ai_server():
    data = request.json
    # Prompt wymuszający unikalny styl i format JSON
    prompt = (
        f"Jesteś redaktorem metalowym. Na podstawie newsa: '{data['title']}' "
        f"i treści: '{data['text']}', przygotuj nowy, unikalny artykuł. "
        f"Używaj luźnego, branżowego języka. "
        f"Zwróć wynik WYŁĄCZNIE jako czysty JSON w formacie: "
        f"{{\"title\": \"nowy tytuł\", \"content\": \"treść w HTML\"}}"
    )
    
    try:
        response = model.generate_content(prompt)
        # Sprzątanie odpowiedzi Gemini (usuwanie markdowna)
        raw_text = response.text.strip()
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].strip()
            
        return jsonify(json.loads(raw_text))
    except Exception as e:
        print(f"BŁĄD AI: {str(e)}")
        return jsonify({"error": f"Błąd Gemini: {str(e)}"}), 500

@app.route('/publish', methods=['POST'])
def publish():
    data = request.json
    auth = (os.environ.get("WP_USER"), os.environ.get("WP_APP_PASSWORD"))
    payload = {
        "title": data['ai_title'],
        "content": data['ai_content'],
        "status": "draft"
    }
    try:
        r = requests.post(os.environ.get("WP_URL"), auth=auth, json=payload, timeout=10)
        return jsonify({"ok": True}) if r.status_code == 201 else (jsonify({"error": "WP error"}), 400)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
