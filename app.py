import os
import json
import requests
from flask import Flask, render_template_string, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import google.generativeai as genai

app = Flask(__name__)

# --- KONFIGURACJA ---
PORT = int(os.environ.get("PORT", 10000))
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

WP_USER = os.environ.get("WP_USER")
WP_APP_PASS = os.environ.get("WP_APP_PASSWORD")
WP_URL = os.environ.get("WP_URL")

# --- SZABLON HTML (Zdefiniowany bezpośrednio tutaj, by uniknąć błędu importu) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Metal AI Editor</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: sans-serif; }
        .card { background-color: #1e1e1e; border: 1px solid #333; margin-bottom: 2rem; border-radius: 10px; }
        .editable-area { background-color: #2a2a2a; color: #fff; border: 1px solid #444; width: 100%; min-height: 200px; padding: 10px; }
        .btn-primary { background-color: #d32f2f; border: none; }
        .text-warning { color: #ff9800 !important; }
    </style>
</head>
<body class="container py-5">
    <header class="mb-5 text-center">
        <h1 class="fw-bold">🤘 METAL AI ENGINE</h1>
        <p class="text-muted small">KVLT.PL & CHAOSVAULT.COM</p>
        <button onclick="location.reload()" class="btn btn-outline-light btn-sm">Skanuj Newsy</button>
    </header>

    <div id="articles">
        {% for art in articles %}
        <div class="card shadow" id="card-{{ loop.index }}">
            <div class="card-body">
                <p class="badge bg-dark text-secondary mb-2">{{ art.source_domain }}</p>
                <div class="mb-3">
                    <label class="form-label text-warning small">Tytuł:</label>
                    <input type="text" id="title-{{ loop.index }}" class="form-control bg-dark text-white border-secondary" value="{{ art.ai_title }}">
                </div>
                <div class="mb-3">
                    <label class="form-label text-warning small">Treść (HTML):</label>
                    <textarea id="content-{{ loop.index }}" class="editable-area">{{ art.ai_content }}</textarea>
                </div>
                <div class="d-flex justify-content-between align-items-center">
                    <button onclick='publishPost({{ loop.index }})' class="btn btn-primary" id="btn-{{ loop.index }}">Wyślij do WP</button>
                    <a href="{{ art.url }}" target="_blank" class="text-secondary small">Oryginał ↗</a>
                </div>
                <div id="status-{{ loop.index }}" class="mt-2 small"></div>
            </div>
        </div>
        {% endfor %}
    </div>

    <script>
        async function publishPost(id) {
            const btn = document.getElementById(`btn-${id}`);
            const st = document.getElementById(`status-${id}`);
            const title = document.getElementById(`title-${id}`).value;
            const content = document.getElementById(`content-${id}`).value;

            btn.disabled = true;
            st.innerHTML = "Wysyłanie...";

            try {
                const res = await fetch('/publish', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ ai_title: title, ai_content: content })
                });
                if (res.ok) {
                    st.innerHTML = "✅ Sukces!";
                    btn.className = "btn btn-secondary disabled";
                } else { throw new Error(); }
            } catch (e) {
                st.innerHTML = "❌ Błąd!";
                btn.disabled = false;
            }
        }
    </script>
</body>
</html>
"""

def get_all_news():
    all_articles = []
    sources = [
        {"url": "https://kvlt.pl/newsy/", "domain": "kvlt.pl", "selector": ".entry-content"},
        {"url": "https://chaosvault.com/category/newsy/", "domain": "chaosvault.com", "selector": ".td-post-content, .entry-content"}
    ]
    
    for source in sources:
        try:
            r = requests.get(source["url"], timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if source["domain"] in href and "/page/" not in href and len(href) > len(source["url"]) + 5:
                    links.append(urljoin(source["url"], href))
            
            for link in list(dict.fromkeys(links))[:2]: # Limit 2 dla szybkości na Render
                try:
                    res = requests.get(link, timeout=10)
                    art_soup = BeautifulSoup(res.text, 'html.parser')
                    title = art_soup.find('h1').get_text(strip=True)
                    content_div = art_soup.select_one(source["selector"])
                    if content_div:
                        for tag in content_div(['script', 'style', 'nav', 'aside']): tag.decompose()
                        raw_text = content_div.get_text(separator=' ', strip=True)[:3000]
                        
                        prompt = f"Przeredaguj ten news: {title}. Treść: {raw_text}. Zwróć tylko JSON: {{\"title\": \"...\", \"content\": \"...\"}}"
                        response = model.generate_content(prompt)
                        clean_json = response.text.strip().replace('```json', '').replace('```', '')
                        ai_data = json.loads(clean_json)

                        all_articles.append({
                            "original_title": title,
                            "ai_title": ai_data.get('title', ''),
                            "ai_content": ai_data.get('content', ''),
                            "url": link,
                            "source_domain": source["domain"]
                        })
                except: continue
        except: continue
    return all_articles

@app.route('/')
def index():
    # Optymalizacja dla zapytań HEAD od Rendera
    if request.method == 'HEAD':
        return '', 200
    
    articles = get_all_news()
    return render_template_string(HTML_TEMPLATE, articles=articles)

@app.route('/publish', methods=['POST'])
def publish():
    data = request.json
    auth = (WP_USER, WP_APP_PASS)
    payload = {"title": data['ai_title'], "content": data['ai_content'], "status": "draft"}
    r = requests.post(WP_URL, auth=auth, json=payload)
    return jsonify({"status": "success"}) if r.status_code == 201 else (jsonify({"status": "error"}), 400)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
