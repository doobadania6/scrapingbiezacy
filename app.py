import os
import json
import requests
from flask import Flask, render_template_string, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from google import genai  # Nowa biblioteka zgodnie z Twoim przewodnikiem

app = Flask(__name__)
PORT = int(os.environ.get("PORT", 10000))

# --- KONFIGURACJA NOWEGO KLIENTA GENAI ---
# Klucz pobierany ze zmiennej środowiskowej lub wpisany na sztywno
GEMINI_API_KEY = "AIzaSyB1U0Vhm1wLD6RbNovPhAHDJPB_2Yg6Rq4"
client = genai.Client(api_key=GEMINI_API_KEY)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Metal News AI v7.0</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #050505; color: #eee; font-family: 'Inter', sans-serif; }
        .article-card { background: #111; border: 1px solid #333; border-radius: 15px; padding: 25px; margin-bottom: 30px; }
        .ai-result { display: none; background: #001a00; border: 1px solid #00ff00; padding: 15px; border-radius: 10px; margin-top: 15px; }
        textarea { background: #000 !important; color: #00ff00 !important; border: 1px solid #222 !important; font-family: 'Courier New', monospace; }
        .btn-main { background: linear-gradient(45deg, #ff0000, #8b0000); border: none; color: white; font-weight: bold; }
    </style>
</head>
<body class="container py-5">
    <h1 class="text-center mb-5 font-monospace">METALGROWL <span class="text-danger">AI v7</span></h1>
    
    <div id="feed">
        {% for art in articles %}
        <div class="article-card">
            <h4 class="text-danger">{{ art.source }}</h4>
            <h3>{{ art.title }}</h3>
            <div id="raw-{{ loop.index }}" style="display:none">{{ art.raw_content }}</div>
            
            <button class="btn btn-main btn-sm mt-3" onclick="callGemini({{ loop.index }})">⚡ GENERUJ NOWY NEWS</button>
            
            <div class="ai-result" id="ai-box-{{ loop.index }}">
                <input type="text" id="ai-title-{{ loop.index }}" class="form-control mb-2 bg-dark text-white border-0">
                <textarea id="ai-content-{{ loop.index }}" class="form-control" rows="10"></textarea>
                <button class="btn btn-success mt-3 w-100" onclick="publish({{ loop.index }})">🚀 WYŚLIJ DO WORDPRESS</button>
                <p id="msg-{{ loop.index }}" class="mt-2 small"></p>
            </div>
        </div>
        {% endfor %}
    </div>

    <script>
        async function callGemini(id) {
            const btn = event.target;
            const title = document.querySelector(`#raw-${id}`).previousElementSibling.innerText;
            const content = document.getElementById(`raw-${id}`).innerText;
            
            btn.disabled = true;
            btn.innerText = "⏳ Generowanie przez Gemini 2.0...";

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

        async function publish(id) {
            const msg = document.getElementById(`msg-${id}`);
            msg.innerText = "Publikowanie...";
            const res = await fetch('/publish', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    title: document.getElementById(`ai-title-${id}`).value,
                    content: document.getElementById(`ai-content-${id}`).value
                })
            });
            msg.innerText = res.ok ? "✅ Dodano do szkiców!" : "❌ Błąd publikacji";
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
                t = asoup.find('h1').text.strip() if asoup.find('h1') else "News"
                c_tag = asoup.find('article') or asoup.find('div', class_='entry-content')
                c = c_tag.get_text(strip=True)[:1500] if c_tag else ""
                all_news.append({"title": t, "raw_content": c, "source": s["domain"]})
        except: continue
    return render_template_string(HTML_TEMPLATE, articles=all_news)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    # Model gemini-2.0-flash-exp (wersja z Twojego przewodnika)
    prompt = (
        f"Jesteś redaktorem metalowym. Na podstawie newsa: '{data['title']}' i treści: '{data['content']}', "
        "napisz unikalny news w mrocznym stylu. "
        "Zwróć wynik jako JSON: {\"title\": \"...\", \"content\": \"... (HTML)\"}"
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp", 
            contents=prompt
        )
        text = response.text
        # Naprawa JSONa
        if "{" in text:
            text = text[text.find("{"):text.rfind("}")+1]
        return jsonify(json.loads(text))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/publish', methods=['POST'])
def publish_wp():
    data = request.json
    auth = (os.environ.get("WP_USER"), os.environ.get("WP_APP_PASSWORD"))
    p = {"title": data['title'], "content": data['content'], "status": "draft"}
    r = requests.post(os.environ.get("WP_URL"), auth=auth, json=p)
    return jsonify({"ok": True}) if r.status_code == 201 else (jsonify({"err": True}), 400)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
