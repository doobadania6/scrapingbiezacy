import os
import json
import requests
from flask import Flask, render_template_string, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import google.generativeai as genai

app = Flask(__name__)

# Render wymaga bindowania do 0.0.0.0
PORT = int(os.environ.get("PORT", 10000))

# --- KONFIGURACJA AI ---
GEMINI_API_KEY = "AIzaSyB1U0Vhm1wLD6RbNovPhAHDJPB_2Yg6Rq4"
genai.configure(api_key=GEMINI_API_KEY)

# Próbujemy użyć najbardziej zaawansowanego modelu, który ma najlepszą dostępność
model = genai.GenerativeModel('gemini-1.5-pro')

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Metal News Pro v6.4</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0d0d0d; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
        .article-card { background: #1a1a1a; border-radius: 12px; padding: 20px; margin-bottom: 25px; border: 1px solid #333; }
        .ai-box { display: none; background: #222; padding: 15px; border-radius: 8px; margin-top: 15px; border-left: 4px solid #00ff00; }
        textarea { background: #000 !important; color: #00ff00 !important; font-family: monospace; border: 1px solid #555 !important; }
        .btn-gemini { background-color: #6200ea; border: none; color: white; font-weight: bold; }
    </style>
</head>
<body class="container py-5">
    <header class="text-center mb-5">
        <h1>🤘 METAL <span style="color: #00ff00;">AI</span> ULTIMATE</h1>
        <p class="text-muted small">Wersja 6.4 (Auto-Port & Pro Model)</p>
        <button onclick="location.reload()" class="btn btn-outline-success btn-sm">Odśwież źródła</button>
    </header>
    
    <div id="news-feed">
        {% for art in articles %}
        <div class="article-card">
            <span class="badge bg-dark text-success mb-2">{{ art.source }}</span>
            <h3>{{ art.title }}</h3>
            <div style="display:none" id="raw-{{ loop.index }}">{{ art.raw_content }}</div>
            
            <button class="btn btn-gemini btn-sm mt-2" onclick="processAI({{ loop.index }})">✨ GENERUJ TREŚĆ AI</button>
            
            <div class="ai-box" id="ai-box-{{ loop.index }}">
                <input type="text" id="ai-title-{{ loop.index }}" class="form-control mb-2 bg-dark text-white">
                <textarea id="ai-content-{{ loop.index }}" class="form-control" rows="8"></textarea>
                <button class="btn btn-success btn-sm mt-3" onclick="sendToWP({{ loop.index }})">🚀 WYŚLIJ DO WP</button>
                <span id="status-{{ loop.index }}" class="ms-3"></span>
            </div>
        </div>
        {% endfor %}
    </div>

    <script>
        async function processAI(id) {
            const btn = event.target;
            const title = document.querySelector(`#raw-${id}`).previousElementSibling.innerText;
            const text = document.getElementById(`raw-${id}`).innerText;
            
            btn.disabled = true;
            btn.innerText = '⏳ AI generuje...';

            try {
                const res = await fetch('/run_ai_server', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ title: title, text: text })
                });
                const data = await res.json();
                if (data.error) throw new Error(data.error);

                document.getElementById(`ai-box-${id}`).style.display = "block";
                document.getElementById(`ai-title-${id}`).value = data.title;
                document.getElementById(`ai-content-${id}`).value = data.content;
                btn.innerText = "✅ Gotowe";
            } catch (e) {
                alert(e.message);
                btn.disabled = false;
                btn.innerText = "❌ Błąd (Ponów)";
            }
        }

        async function sendToWP(id) {
            const status = document.getElementById(`status-${id}`);
            status.innerText = "Wysyłanie...";
            const res = await fetch('/publish', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    ai_title: document.getElementById(`ai-title-${id}`).value,
                    ai_content: document.getElementById(`ai-content-${id}`).value
                })
            });
            status.innerText = res.ok ? "✅ OK!" : "❌ Błąd!";
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    all_news = []
    try:
        sources = [{"url": "https://kvlt.pl/newsy/", "domain": "kvlt.pl"}, {"url": "https://chaosvault.com/category/newsy/", "domain": "chaosvault.com"}]
        for s in sources:
            r = requests.get(s["url"], headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            soup = BeautifulSoup(r.text, 'html.parser')
            links = [urljoin(s["url"], a['href']) for a in soup.find_all('a', href=True) if s["domain"] in a['href'] and len(a['href']) > 45][:3]
            for l in links:
                ar = requests.get(l, timeout=5)
                asoup = BeautifulSoup(ar.text, 'html.parser')
                t = asoup.find('h1').text.strip() if asoup.find('h1') else "News"
                c = asoup.find('article').get_text(strip=True)[:1000] if asoup.find('article') else ""
                all_news.append({"title": t, "raw_content": c, "source": s["domain"], "url": l})
    except: pass
    return render_template_string(HTML_TEMPLATE, articles=all_news)

@app.route('/run_ai_server', methods=['POST'])
def run_ai_server():
    data = request.json
    try:
        prompt = f"Jesteś redaktorem metalowym. Przeredaguj news: {data['title']}. Treść: {data['text']}. Zwróć JSON: {{\"title\": \"...\", \"content\": \"... (HTML)\"}}"
        response = model.generate_content(prompt)
        text = response.text
        if "{" in text:
            text = text[text.find("{"):text.rfind("}")+1]
        return jsonify(json.loads(text))
    except Exception as e:
        return jsonify({"error": f"Lokalizacja serwera może być nieobsługiwana lub klucz wygasł: {str(e)}"}), 500

@app.route('/publish', methods=['POST'])
def publish():
    data = request.json
    auth = (os.environ.get("WP_USER"), os.environ.get("WP_APP_PASSWORD"))
    p = {"title": data['ai_title'], "content": data['ai_content'], "status": "draft"}
    r = requests.post(os.environ.get("WP_URL"), auth=auth, json=p)
    return jsonify({"ok": True}) if r.status_code == 201 else (jsonify({"err": True}), 400)

if __name__ == '__main__':
    # KLUCZOWE DLA RENDERA: host='0.0.0.0'
    app.run(host='0.0.0.0', port=PORT)
