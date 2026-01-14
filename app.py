import os
import json
import requests
from flask import Flask, render_template_string, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from google import genai  # Używamy nowej biblioteki SDK

app = Flask(__name__)
PORT = int(os.environ.get("PORT", 10000))

# --- KONFIGURACJA KLIENTA ---
# Klucz API wklejony na sztywno dla pewności działania
GEMINI_API_KEY = "AIzaSyB1U0Vhm1wLD6RbNovPhAHDJPB_2Yg6Rq4"
client = genai.Client(api_key=GEMINI_API_KEY)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Metal Growl AI v7.1</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0a0a0a; color: #f0f0f0; font-family: 'Inter', sans-serif; }
        .container { max-width: 900px; }
        .article-card { background: #161616; border: 1px solid #333; border-radius: 12px; padding: 20px; margin-bottom: 25px; }
        .ai-box { display: none; background: #0d200d; border: 1px solid #28a745; padding: 15px; border-radius: 8px; margin-top: 15px; }
        textarea { background: #000 !important; color: #00ff00 !important; border: 1px solid #444 !important; font-family: monospace; }
        .btn-metal { background: #e62117; border: none; color: white; font-weight: bold; }
        .btn-metal:hover { background: #ff3c30; }
        .source-tag { color: #e62117; font-weight: bold; font-size: 0.8rem; text-transform: uppercase; }
    </style>
</head>
<body class="container py-5">
    <div class="text-center mb-5">
        <h1 class="display-4 fw-bold">🤘 METAL <span style="color: #e62117;">AI</span></h1>
        <p class="text-muted text-uppercase">System Redakcyjny v7.1 (Stable Flash)</p>
    </div>
    
    <div id="news-feed">
        {% for art in articles %}
        <div class="article-card">
            <div class="source-tag mb-1">{{ art.source }}</div>
            <h3>{{ art.title }}</h3>
            <div id="raw-{{ loop.index }}" style="display:none">{{ art.raw_content }}</div>
            
            <button class="btn btn-metal btn-sm mt-3" onclick="generateNews({{ loop.index }})">✨ PRZERÓB PRZEZ AI</button>
            
            <div class="ai-box" id="ai-box-{{ loop.index }}">
                <label class="small text-muted mb-1">Nowy Tytuł:</label>
                <input type="text" id="ai-title-{{ loop.index }}" class="form-control mb-3 bg-dark text-white border-0">
                
                <label class="small text-muted mb-1">Nowa Treść (HTML):</label>
                <textarea id="ai-content-{{ loop.index }}" class="form-control" rows="10"></textarea>
                
                <div class="d-flex align-items-center mt-3">
                    <button class="btn btn-success btn-sm" onclick="sendToWP({{ loop.index }})">🚀 WYŚLIJ DO WORDPRESS</button>
                    <span id="status-{{ loop.index }}" class="ms-3 small text-success"></span>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>

    <script>
        async function generateNews(id) {
            const btn = event.target;
            const title = document.querySelector(`#raw-${id}`).previousElementSibling.innerText;
            const content = document.getElementById(`raw-${id}`).innerText;
            
            btn.disabled = true;
            btn.innerText = "⏳ Gemini przetwarza...";

            try {
                const response = await fetch('/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ title: title, content: content })
                });
                
                const data = await response.json();
                if (data.error) throw new Error(data.error);

                document.getElementById(`ai-box-${id}`).style.display = "block";
                document.getElementById(`ai-title-${id}`).value = data.title;
                document.getElementById(`ai-content-${id}`).value = data.content;
                btn.innerText = "✅ Gotowe";
            } catch (e) {
                alert("Błąd: " + e.message);
                btn.disabled = false;
                btn.innerText = "❌ Spróbuj ponownie";
            }
        }

        async function sendToWP(id) {
            const status = document.getElementById(`status-${id}`);
            status.innerText = "Publikowanie...";
            
            try {
                const res = await fetch('/publish', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        title: document.getElementById(`ai-title-${id}`).value,
                        content: document.getElementById(`ai-content-${id}`).value
                    })
                });
                if(res.ok) status.innerText = "✅ Wysłano do szkiców!";
                else status.innerText = "❌ Błąd WP";
            } catch (e) {
                status.innerText = "❌ Błąd sieci";
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
    sources = [{"url": "https://kvlt.pl/newsy/", "domain": "kvlt.pl"}, {"url": "https://chaosvault.com/category/newsy/", "domain": "chaosvault.com"}]
    
    for s in sources:
        try:
            r = requests.get(s["url"], headers=headers, timeout=5)
            soup = BeautifulSoup(r.text, 'html.parser')
            links = [urljoin(s["url"], a['href']) for a in soup.find_all('a', href=True) if s["domain"] in a['href'] and len(a['href']) > 45][:3]
            for l in links:
                ar = requests.get(l, headers=headers, timeout=5)
                asoup = BeautifulSoup(ar.text, 'html.parser')
                t = asoup.find('h1').get_text(strip=True) if asoup.find('h1') else "Metal News"
                c_tag = asoup.find('article') or asoup.find('div', class_='entry-content')
                c = c_tag.get_text(separator=' ', strip=True)[:1500] if c_tag else "Brak treści."
                all_news.append({"title": t, "raw_content": c, "source": s["domain"]})
        except: continue
    return render_template_string(HTML_TEMPLATE, articles=all_news)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    # Prompt wymuszający format JSON
    prompt = (
        f"Jesteś redaktorem portalu metalowego. Na podstawie tytułu: '{data['title']}' i treści: '{data['content']}', "
        "napisz zupełnie nowy news w stylu branżowym. "
        "Zwróć wynik jako CZYSTY JSON (bez markdowna): "
        "{\"title\": \"nowy mroczny tytuł\", \"content\": \"treść w HTML (używaj <p>, <strong>)\"}"
    )
    
    try:
        # KLUCZOWA ZMIANA: Stabilny model 1.5-flash zamiast 2.0
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=prompt
        )
        text = response.text
        
        # Oczyszczanie tekstu z ewentualnych znaczników markdown
        if "{" in text:
            text = text[text.find("{"):text.rfind("}")+1]
            
        return jsonify(json.loads(text))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/publish', methods=['POST'])
def publish():
    data = request.json
    auth = (os.environ.get("WP_USER"), os.environ.get("WP_APP_PASSWORD"))
    payload = {"title": data['title'], "content": data['content'], "status": "draft"}
    r = requests.post(os.environ.get("WP_URL"), auth=auth, json=payload, timeout=10)
    return jsonify({"ok": True}) if r.status_code == 201 else (jsonify({"error": "WP error"}), 400)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
