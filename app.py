import os
import json
import requests
from flask import Flask, render_template_string, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import google.generativeai as genai

app = Flask(__name__)
PORT = int(os.environ.get("PORT", 10000))

# KONFIGURACJA AI NA SERWERZE
GEMINI_API_KEY = "AIzaSyB1U0Vhm1wLD6RbNovPhAHDJPB_2Yg6Rq4"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Metal News Engine v6</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0d0d0d; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
        .article-card { background: #1a1a1a; border-radius: 12px; padding: 20px; margin-bottom: 25px; border: 1px solid #333; }
        .ai-box { display: none; background: #222; border: 1px solid #444; padding: 15px; border-radius: 8px; margin-top: 15px; }
        textarea { background: #000 !important; color: #0f0 !important; font-family: monospace; border: 1px solid #555 !important; }
        .btn-gemini { background-color: #6200ea; border: none; color: white; }
    </style>
</head>
<body class="container py-5">
    <h1 class="text-center mb-5">🤘 METAL ENGINE <span style="color: #ff3d00;">V6</span></h1>
    
    <div id="news-feed">
        {% for art in articles %}
        <div class="article-card">
            <span class="badge bg-dark text-danger mb-2">{{ art.source }}</span>
            <h3 id="title-{{ loop.index }}">{{ art.title }}</h3>
            <div style="display:none" id="raw-{{ loop.index }}">{{ art.raw_content }}</div>
            
            <button class="btn btn-gemini btn-sm mt-2" onclick="askGeminiServer({{ loop.index }})">✨ PRZERÓB PRZEZ AI</button>
            
            <div class="ai-box" id="ai-box-{{ loop.index }}">
                <input type="text" id="ai-title-{{ loop.index }}" class="form-control mb-2 bg-dark text-white border-secondary">
                <textarea id="ai-content-{{ loop.index }}" class="form-control" rows="8"></textarea>
                <button class="btn btn-success btn-sm mt-3" onclick="publishToWP({{ loop.index }})">🚀 WYŚLIJ DO WP</button>
                <span id="status-{{ loop.index }}" class="ms-2 small text-warning"></span>
            </div>
        </div>
        {% endfor %}
    </div>

    <script>
        async function askGeminiServer(id) {
            const btn = event.target;
            const title = document.getElementById(`title-${id}`).innerText;
            const text = document.getElementById(`raw-${id}`).innerText;
            
            btn.disabled = true;
            btn.innerHTML = "⏳ Serwer przetwarza...";

            try {
                const response = await fetch('/run_ai_server', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ title: title, text: text })
                });

                const data = await response.json();
                if (data.error) throw new Error(data.error);

                document.getElementById(`ai-box-${id}`).style.display = "block";
                document.getElementById(`ai-title-${id}`).value = data.title;
                document.getElementById(`ai-content-${id}`).value = data.content;
                btn.innerHTML = "✅ Gotowe";
            } catch (e) {
                alert("Błąd: " + e.message);
                btn.disabled = false;
                btn.innerHTML = "❌ Błąd (Ponów)";
            }
        }

        async function publishToWP(id) {
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
            status.innerText = res.ok ? "✅ Wysłano!" : "❌ Błąd WP";
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
            links = [urljoin(s["url"], a['href']) for a in soup.find_all('a', href=True) if s["domain"] in a['href'] and len(a['href']) > 40][:3]
            for l in list(dict.fromkeys(links)):
                try:
                    res = requests.get(l, headers=headers, timeout=5)
                    asoup = BeautifulSoup(res.text, 'html.parser')
                    title = asoup.find('h1').text.strip() if asoup.find('h1') else None
                    ctag = asoup.find('article') or asoup.find('div', class_='entry-content')
                    content = ctag.get_text(strip=True)[:1000] if ctag else "Brak treści"
                    if title: all_news.append({"title": title, "raw_content": content, "source": s["domain"]})
                except: continue
        except: continue
    return render_template_string(HTML_TEMPLATE, articles=all_news)

@app.route('/run_ai_server', methods=['POST'])
def run_ai_server():
    data = request.json
    prompt = f"Jesteś redaktorem metalowym. Przeredaguj news: {data['title']}. Treść: {data['text']}. Zwróć TYLKO JSON: {{\"title\": \"...\", \"content\": \"...\"}}"
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return jsonify(json.loads(clean_text))
    except Exception as e:
        print(f"BŁĄD GEMINI: {str(e)}") # To zobaczysz w logach Rendera
        return jsonify({"error": str(e)}), 500

@app.route('/publish', methods=['POST'])
def publish():
    data = request.json
    auth = (os.environ.get("WP_USER"), os.environ.get("WP_APP_PASSWORD"))
    p = {"title": data['ai_title'], "content": data['ai_content'], "status": "draft"}
    r = requests.post(os.environ.get("WP_URL"), auth=auth, json=p)
    return jsonify({"ok": True}) if r.status_code == 201 else (jsonify({"err": True}), 400)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
