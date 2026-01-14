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
    <title>Metal News Engine v4</title>
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
    <h1 class="text-center mb-5">🤘 METAL <span style="color: #ff4d4d;">AGRESSIVE</span> ENGINE</h1>
    
    <div class="text-center mb-4">
        <button onclick="location.reload()" class="btn btn-outline-danger">PONÓW SKANOWANIE</button>
    </div>

    <div id="news-feed">
        {% if not articles %}
            <div class="alert alert-dark text-center">Brak nowych artykułów. Spróbuj odświeżyć za chwilę.</div>
        {% endif %}
        
        {% for art in articles %}
        <div class="article-card">
            <div class="d-flex justify-content-between align-items-center">
                <span class="source-label">{{ art.source }}</span>
                <a href="{{ art.url }}" target="_blank" class="text-muted small">Oryginał ↗</a>
            </div>
            <h3 class="mt-2" id="title-{{ loop.index }}">{{ art.title }}</h3>
            <div style="display:none" id="raw-{{ loop.index }}">{{ art.raw_content }}</div>
            
            <button class="btn btn-gemini btn-sm" onclick="askGemini({{ loop.index }})">✨ Generuj przez Gemini</button>
            
            <div class="ai-output-box" id="ai-box-{{ loop.index }}">
                <label class="small text-info">Tytuł:</label>
                <input type="text" id="ai-title-{{ loop.index }}" class="form-control mb-2 bg-dark text-white">
                <label class="small text-info">Treść (HTML):</label>
                <textarea id="ai-content-{{ loop.index }}" class="form-control" rows="6"></textarea>
                <button class="btn btn-success btn-sm mt-3" onclick="publishToWP({{ loop.index }})">🚀 Wyślij do WP</button>
                <span id="status-{{ loop.index }}" class="ms-2"></span>
            </div>
        </div>
        {% endfor %}
    </div>

    <script>
        const GEMINI_KEY = "{{ gemini_key }}";

        async function askGemini(id) {
            const btn = document.querySelector(`#ai-box-${id}`).previousElementSibling;
            const title = document.getElementById(`title-${id}`).innerText;
            const text = document.getElementById(`raw-${id}`).innerText;
            
            btn.disabled = true;
            btn.innerText = "⏳ Pracuję...";

            const prompt = `Jesteś redaktorem portalu o metalu. Przeredaguj ten news: "${title}". Treść: "${text}". Wynik oddaj jako JSON: {"title": "tytuł", "content": "html"}`;

            try {
                const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${GEMINI_KEY}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] })
                });

                const data = await response.json();
                const rawResult = data.candidates[0].content.parts[0].text;
                const cleanJson = rawResult.replace(/```json|```/g, "").trim();
                const final = JSON.parse(cleanJson);

                document.getElementById(`ai-box-${id}`).style.display = "block";
                document.getElementById(`ai-title-${id}`).value = final.title;
                document.getElementById(`ai-content-${id}`).value = final.content;
                btn.innerText = "✅ Gotowe";
            } catch (e) {
                alert("Błąd Gemini. Spróbuj jeszcze raz.");
                btn.disabled = false;
                btn.innerText = "❌ Ponów";
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
            status.innerText = res.ok ? "✅ Sukces!" : "❌ Błąd!";
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
            print(f"Próba scrapowania: {s['domain']}")
            r = requests.get(s["url"], headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Pobieramy wszystkie linki, które wyglądają jak artykuły
            # Filtrujemy te, które są za krótkie lub są stronami kategorii
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if s["domain"] in href and len(href) > 35 and "/page/" not in href and "category" not in href:
                    links.append(urljoin(s["url"], href))
            
            # Unikalne linki, bierzemy pierwsze 3
            for l in list(dict.fromkeys(links))[:3]:
                try:
                    res = requests.get(l, headers=headers, timeout=7)
                    asoup = BeautifulSoup(res.text, 'html.parser')
                    
                    # Szukamy tytułu w H1
                    title = asoup.find('h1').get_text(strip=True) if asoup.find('h1') else None
                    if not title: continue
                    
                    # Agresywne szukanie treści - bierzemy po prostu największy blok tekstu
                    # lub standardowy tag <article>
                    content_tag = asoup.find('article') or asoup.find('main') or asoup.find('div', class_='entry-content')
                    content = ""
                    if content_tag:
                        # Usuwamy zbędne elementy
                        for tag in content_tag(['script', 'style', 'nav', 'aside', 'footer']): tag.decompose()
                        content = content_tag.get_text(separator=' ', strip=True)[:1000]
                    
                    if title and len(content) > 100:
                        all_news.append({"title": title, "raw_content": content, "url": l, "source": s["domain"]})
                except Exception as e:
                    print(f"Błąd artykułu {l}: {e}")
                    continue
        except Exception as e:
            print(f"Błąd źródła {s['domain']}: {e}")
            
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
