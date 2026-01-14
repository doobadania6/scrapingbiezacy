import os
import requests
from flask import Flask, render_template_string, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urljoin

app = Flask(__name__)
PORT = int(os.environ.get("PORT", 10000))

# TWÓJ KLUCZ GEMINI
GEMINI_API_KEY = "AIzaSyB1U0Vhm1wLD6RbNovPhAHDJPB_2Yg6Rq4"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Metal News Engine v5</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0d0d0d; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
        .article-card { background: #1a1a1a; border-radius: 12px; padding: 20px; margin-bottom: 25px; border: 1px solid #333; }
        .ai-box { display: none; background: #222; border: 1px solid #444; padding: 15px; border-radius: 8px; margin-top: 15px; }
        textarea { background: #000 !important; color: #0f0 !important; font-family: monospace; border: 1px solid #555 !important; }
        .btn-gemini { background-color: #6200ea; border: none; color: white; padding: 8px 20px; }
        .btn-gemini:hover { background-color: #3700b3; }
    </style>
</head>
<body class="container py-5">
    <h1 class="text-center mb-5">🤘 METAL <span style="color: #ff3d00;">ENGINE</span> V5</h1>
    
    <div id="news-feed">
        {% for art in articles %}
        <div class="article-card">
            <span class="badge bg-dark text-danger mb-2">{{ art.source }}</span>
            <h3 id="title-{{ loop.index }}">{{ art.title }}</h3>
            
            <div style="display:none" id="raw-{{ loop.index }}">{{ art.raw_content }}</div>
            
            <button class="btn btn-gemini btn-sm mt-2" onclick="askGemini({{ loop.index }})">✨ PRZERÓB PRZEZ AI</button>
            
            <div class="ai-box" id="ai-box-{{ loop.index }}">
                <label class="small text-muted">Nowy Tytuł:</label>
                <input type="text" id="ai-title-{{ loop.index }}" class="form-control mb-2 bg-dark text-white border-secondary">
                <label class="small text-muted">Treść (HTML):</label>
                <textarea id="ai-content-{{ loop.index }}" class="form-control" rows="8"></textarea>
                <button class="btn btn-success btn-sm mt-3" onclick="publishToWP({{ loop.index }})">🚀 WYŚLIJ DO WP</button>
                <span id="status-{{ loop.index }}" class="ms-2 small"></span>
            </div>
        </div>
        {% endfor %}
    </div>

    <script>
        const GEMINI_KEY = "{{ gemini_key }}";

        async function askGemini(id) {
            const btn = document.querySelector(`#art-card-${id} .btn-gemini`) || event.target;
            const title = document.getElementById(`title-${id}`).innerText;
            const text = document.getElementById(`raw-${id}`).innerText || title; // Fallback do tytułu
            
            btn.disabled = true;
            btn.innerHTML = "⏳ Gemini przetwarza...";

            const prompt = `Jesteś redaktorem portalu metalowego. Na podstawie newsa: "${title}" i treści: "${text.substring(0,1000)}", przygotuj unikalny news. Zwróć wynik WYŁĄCZNIE jako czysty JSON: {"title": "fajny tytuł", "content": "tresc w html"}`;

            try {
                const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${GEMINI_KEY}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] })
                });

                const data = await response.json();
                let resultText = data.candidates[0].content.parts[0].text;
                
                // Super-czyszczenie JSONa
                resultText = resultText.replace(/```json/g, "").replace(/```/g, "").trim();
                const final = JSON.parse(resultText);

                document.getElementById(`ai-box-${id}`).style.display = "block";
                document.getElementById(`ai-title-${id}`).value = final.title;
                document.getElementById(`ai-content-${id}`).value = final.content;
                btn.innerHTML = "✅ Gotowe";
            } catch (e) {
                console.error("Błąd Gemini:", e);
                alert("Wystąpił błąd AI. Sprawdź konsolę (F12) lub spróbuj ponownie.");
                btn.disabled = false;
                btn.innerHTML = "❌ Błąd (Ponów)";
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
                status.innerText = res.ok ? "✅ Wysłano!" : "❌ Błąd WP";
            } catch (e) { status.innerText = "❌ Błąd sieci"; }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    all_news = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
    sources = [
        {"url": "https://kvlt.pl/newsy/", "domain": "kvlt.pl"},
        {"url": "https://chaosvault.com/category/newsy/", "domain": "chaosvault.com"}
    ]
    
    for s in sources:
        try:
            r = requests.get(s["url"], headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if s["domain"] in href and len(href) > 40 and "/page/" not in href:
                    links.append(urljoin(s["url"], href))
            
            for l in list(dict.fromkeys(links))[:4]:
                try:
                    res = requests.get(l, headers=headers, timeout=7)
                    asoup = BeautifulSoup(res.text, 'html.parser')
                    title = asoup.find('h1').get_text(strip=True) if asoup.find('h1') else None
                    if not title: continue
                    
                    # Szukanie treści - różne selektory
                    content_tag = asoup.find('article') or asoup.find('div', class_='entry-content') or asoup.find('div', class_='td-post-content')
                    content = content_tag.get_text(separator=' ', strip=True) if content_tag else "Brak treści źródłowej (użyj tytułu do generowania)"
                    
                    all_news.append({"title": title, "raw_content": content[:1500], "url": l, "source": s["domain"]})
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
