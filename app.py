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
# Używamy bezpośredniego klucza i stabilnego modelu gemini-pro
GEMINI_API_KEY = "AIzaSyB1U0Vhm1wLD6RbNovPhAHDJPB_2Yg6Rq4"
genai.configure(api_key=GEMINI_API_KEY)

# gemini-pro to najbezpieczniejszy wybór, dostępny wszędzie
model = genai.GenerativeModel('gemini-pro')

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Metal News Engine v6.3</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0d0d0d; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
        .article-card { background: #1a1a1a; border-radius: 12px; padding: 20px; margin-bottom: 25px; border: 1px solid #333; }
        .ai-box { display: none; background: #222; border: 1px solid #444; padding: 15px; border-radius: 8px; margin-top: 15px; border-left: 4px solid #ff3d00; }
        textarea { background: #000 !important; color: #0f0 !important; font-family: monospace; border: 1px solid #555 !important; }
        .btn-gemini { background-color: #ff3d00; border: none; color: white; font-weight: bold; }
        .badge-source { font-size: 0.7rem; background: #333; color: #ff3d00; padding: 5px 10px; border-radius: 5px; text-transform: uppercase; }
    </style>
</head>
<body class="container py-5">
    <header class="text-center mb-5">
        <h1 class="display-5 fw-bold">🤘 METAL NEWS <span style="color: #ff3d00;">PRO</span></h1>
        <p class="text-muted">Wersja 6.3 (Stabilny Model Pro)</p>
        <button onclick="location.reload()" class="btn btn-outline-light btn-sm">Odśwież newsy</button>
    </header>
    
    <div id="news-feed">
        {% for art in articles %}
        <div class="article-card">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="badge-source">{{ art.source }}</span>
                <a href="{{ art.url }}" target="_blank" class="text-muted small">Źródło ↗</a>
            </div>
            <h3 id="title-{{ loop.index }}">{{ art.title }}</h3>
            <div style="display:none" id="raw-{{ loop.index }}">{{ art.raw_content }}</div>
            
            <button class="btn btn-gemini btn-sm mt-2" onclick="processWithAI({{ loop.index }})">✨ GENERUJ TEKST AI</button>
            
            <div class="ai-box" id="ai-box-{{ loop.index }}">
                <div class="mb-2">
                    <label class="small text-muted">Tytuł AI:</label>
                    <input type="text" id="ai-title-{{ loop.index }}" class="form-control bg-dark text-white border-secondary">
                </div>
                <div class="mb-2">
                    <label class="small text-muted">Treść (HTML):</label>
                    <textarea id="ai-content-{{ loop.index }}" class="form-control" rows="10"></textarea>
                </div>
                <button class="btn btn-success btn-sm" onclick="publishToWP({{ loop.index }})">🚀 WYŚLIJ DO WP</button>
                <span id="status-{{ loop.index }}" class="ms-3 small"></span>
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
            btn.innerHTML = '⏳ Trwa generowanie (Model Pro)...';

            try {
                const response = await fetch('/run_ai_server', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ title: title, text: text })
                });

                const data = await response.json();
                if (!response.ok) throw new Error(data.error || "Błąd AI");

                document.getElementById(`ai-box-${id}`).style.display = "block";
                document.getElementById(`ai-title-${id}`).value = data.title;
                document.getElementById(`ai-content-${id}`).value = data.content;
                btn.innerHTML = "✅ Wygenerowano";
            } catch (e) {
                alert("Błąd: " + e.message);
                btn.disabled = false;
                btn.innerHTML = "❌ Spróbuj ponownie";
            }
        }

        async function publishToWP(id) {
            const status = document.getElementById(`status-${id}`);
            status.innerText = "Wysyłanie...";
            try {
                const res = await fetch('/publish', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        ai_title: document.getElementById(`ai-title-${id}`).value,
                        ai_content: document.getElementById(`ai-content-${id}`).value
                    })
                });
                status.innerText = res.ok ? "✅ Opublikowano!" : "❌ Błąd WordPressa";
            } catch (e) { status.innerText = "❌ Błąd sieci"; }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    all_news = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    sources = [{"url": "https://kvlt.pl/newsy/", "domain": "kvlt.pl"}, {"url": "https://chaosvault.com/category/newsy/", "domain": "chaosvault.com"}]
    
    for s in sources:
        try:
            r = requests.get(s["url"], headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            links = []
            for a in soup.find_all('a', href=True):
                if s["domain"] in a['href'] and len(a['href']) > 45:
                    links.append(urljoin(s["url"], a['href']))
            
            for l in list(dict.fromkeys(links))[:4]:
                try:
                    res = requests.get(l, headers=headers, timeout=7)
                    asoup = BeautifulSoup(res.text, 'html.parser')
                    title = asoup.find('h1').get_text(strip=True) if asoup.find('h1') else None
                    if not title: continue
                    ctag = asoup.find('article') or asoup.find('div', class_='entry-content')
                    content = ctag.get_text(separator=' ', strip=True)[:1200] if ctag else "Brak tekstu"
                    all_news.append({"title": title, "raw_content": content, "url": l, "source": s["domain"]})
                except: continue
        except: continue
    return render_template_string(HTML_TEMPLATE, articles=all_news)

@app.route('/run_ai_server', methods=['POST'])
def run_ai_server():
    data = request.json
    prompt = (
        f"Jesteś redaktorem portalu metalowego. Napisz unikalny news na podstawie tytułu: '{data['title']}' "
        f"i treści: '{data['text']}'. Styl mroczny i energiczny. "
        f"Zwróć wynik jako JSON: {{\"title\": \"...\", \"content\": \"... (w HTML)\"}}"
    )
    
    try:
        response = model.generate_content(prompt)
        # Gemini-pro czasem zwraca czysty tekst bez markdowna, obsłużmy to:
        raw_text = response.text.strip()
        
        # Ekstrakcja JSON jeśli AI dodało komentarze
        if "{" in raw_text:
            raw_text = raw_text[raw_text.find("{"):raw_text.rfind("}")+1]
            
        return jsonify(json.loads(raw_text))
    except Exception as e:
        return jsonify({"error": f"Model Pro mówi: {str(e)}"}), 500

@app.route('/publish', methods=['POST'])
def publish():
    data = request.json
    auth = (os.environ.get("WP_USER"), os.environ.get("WP_APP_PASSWORD"))
    payload = {"title": data['ai_title'], "content": data['ai_content'], "status": "draft"}
    r = requests.post(os.environ.get("WP_URL"), auth=auth, json=payload, timeout=10)
    return jsonify({"ok": True}) if r.status_code == 201 else (jsonify({"error": "WP error"}), 400)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
