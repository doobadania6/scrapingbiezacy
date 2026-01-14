import os
import requests
from flask import Flask, render_template_string, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urljoin

app = Flask(__name__)
PORT = int(os.environ.get("PORT", 10000))

# --- TWÓJ KLUCZ GEMINI (OSADZONY ZEWNĘTRZNIE) ---
GEMINI_API_KEY = "AIzaSyB1U0Vhm1wLD6RbNovPhAHDJPB_2Yg6Rq4"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Metal News Engine v3</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0b0b0b; color: #dcdcdc; font-family: 'Segoe UI', sans-serif; }
        .article-card { background: #161616; border: 1px solid #2a2a2a; border-radius: 12px; padding: 20px; margin-bottom: 25px; }
        .source-label { font-size: 0.7rem; color: #ff4d4d; font-weight: bold; text-transform: uppercase; }
        .ai-output-box { display: none; background: #1d1d1d; border: 1px solid #333; padding: 15px; border-radius: 8px; margin-top: 15px; }
        textarea { background: #000 !important; color: #00ff00 !important; font-family: monospace; border: 1px solid #444 !important; }
        .btn-gemini { background-color: #4b0082; border: none; color: white; }
    </style>
</head>
<body class="container py-5">
    <h1 class="text-center mb-5">🤘 METAL <span style="color: #ff4d4d;">AI</span> ENGINE</h1>
    
    <div id="news-feed">
        {% for art in articles %}
        <div class="article-card" id="card-{{ loop.index }}">
            <div class="d-flex justify-content-between align-items-center">
                <span class="source-label">{{ art.source }}</span>
                <a href="{{ art.url }}" target="_blank" class="text-muted small">Link ↗</a>
            </div>
            <h3 class="mt-2" id="title-{{ loop.index }}">{{ art.title }}</h3>
            <p class="small text-muted" id="raw-{{ loop.index }}">{{ art.raw_content }}</p>
            
            <button class="btn btn-gemini btn-sm" onclick="askGemini({{ loop.index }})">✨ Generuj przez Gemini (Client-Side)</button>
            
            <div class="ai-output-box" id="ai-box-{{ loop.index }}">
                <input type="text" id="ai-title-{{ loop.index }}" class="form-control mb-2 bg-dark text-white">
                <textarea id="ai-content-{{ loop.index }}" class="form-control" rows="6"></textarea>
                <button class="btn btn-success btn-sm mt-3" onclick="publishToWP({{ loop.index }})">🚀 Wyślij Szkic do WP</button>
                <span id="status-{{ loop.index }}" class="ms-2"></span>
            </div>
        </div>
        {% endfor %}
    </div>

    <script>
        const GEMINI_KEY = \"{{ gemini_key }}\";

        async function askGemini(id) {
            const btn = document.querySelector(`#card-${id} .btn-gemini`);
            const title = document.getElementById(`title-${id}`).innerText;
            const text = document.getElementById(`raw-${id}`).innerText;
            
            btn.disabled = true;
            btn.innerText = "⏳ Gemini myśli...";

            const prompt = `Działaj jako metalowy redaktor. Przeredaguj ten news: "${title}". Treść: "${text}". Zwróć wynik w formacie JSON: {"title": "nowy tytuł", "content": "treść w HTML"}`;

            try {
                const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${GEMINI_KEY}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        contents: [{ parts: [{ text: prompt }] }]
                    })
                });

                const data = await response.json();
                const rawResult = data.candidates[0].content.parts[0].text;
                
                // Parsowanie wyniku (usuwanie ewentualnego markdownu ```json)
                const cleanJson = rawResult.replace(/```json|```/g, "").trim();
                const final = JSON.parse(cleanJson);

                document.getElementById(`ai-box-${id}`).style.display = "block";
                document.getElementById(`ai-title-${id}`).value = final.title;
                document.getElementById(`ai-content-${id}`).value = final.content;
                btn.innerText = "✅ Przetworzono";
            } catch (e) {
                console.error(e);
                alert("Błąd połączenia z Gemini. Sprawdź klucz API.");
                btn.disabled = false;
                btn.innerText = "❌ Spróbuj ponownie";
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

            if(res.ok) status.innerText = "✅ Sukces!";
            else status.innerText = "❌ Błąd WordPressa";
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    # Proste scrapowanie bez AI na serwerze
    all_news = []
    sources = [
        {"url": "[https://kvlt.pl/newsy/](https://kvlt.pl/newsy/)", "domain": "kvlt.pl", "sel": ".entry-content"},
        {"url": "[https://chaosvault.com/category/newsy/](https://chaosvault.com/category/newsy/)", "domain": "chaosvault.com", "sel": "article"}
    ]
    for s in sources:
        try:
            r = requests.get(s["url"], headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
            soup = BeautifulSoup(r.text, 'html.parser')
            links = [urljoin(s["url"], a['href']) for a in soup.find_all('a', href=True) if s["domain"] in a['href'] and len(a['href']) > 35][:3]
            for l in links:
                try:
                    res = requests.get(l, timeout=5)
                    asoup = BeautifulSoup(res.text, 'html.parser')
                    t = asoup.find('h1').text.strip() if asoup.find('h1') else "News"
                    c = asoup.select_one(s["sel"]).get_text(strip=True)[:800] if asoup.select_one(s["sel"]) else ""
                    all_news.append({"title": t, "raw_content": c, "url": l, "source": s["domain"]})
                except: continue
        except: continue
    
    return render_template_string(HTML_TEMPLATE, articles=all_news, gemini_key=GEMINI_API_KEY)

@app.route('/publish', methods=['POST'])
def publish():
    data = request.json
    auth = (os.environ.get("WP_USER"), os.environ.get("WP_APP_PASSWORD"))
    payload = {"title": data['ai_title'], "content": data['ai_content'], "status": "draft"}
    r = requests.post(os.environ.get("WP_URL"), auth=auth, json=payload)
    return jsonify({"ok": True}) if r.status_code == 201 else (jsonify({"err": True}), 400)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
