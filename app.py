import os
import json
import requests
from flask import Flask, render_template_string, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import google.generativeai as genai

app = Flask(__name__)

# --- KONFIGURACJA ZMIENNYCH (Ustaw w Render w Environment Variables) ---
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
WP_USER = os.environ.get("WP_USER")
WP_APP_PASS = os.environ.get("WP_APP_PASSWORD")
WP_URL = os.environ.get("WP_URL") # np. https://twoja-strona.pl/wp-json/wp/v2/posts

model = genai.GenerativeModel('gemini-1.5-flash')

# --- SZABLON HTML (Interfejs użytkownika) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Content Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; }
        .article-card { transition: transform 0.2s; border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .article-card:hover { transform: translateY(-5px); }
        .status-badge { font-size: 0.8rem; }
    </style>
</head>
<body class="container py-5">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h1>🚀 AI Content Editor</h1>
        <button onclick="location.reload()" class="btn btn-primary">Odśwież newsy</button>
    </div>

    <div id="articles-container">
        {% for art in articles %}
        <div class="card article-card mb-4" id="card-{{ loop.index }}">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <h5 class="card-title text-primary">{{ art.ai_title }}</h5>
                    <span class="badge bg-secondary status-badge">Źródło: {{ art.source_domain }}</span>
                </div>
                <h6 class="text-muted mb-3">Oryginał: {{ art.original_title }}</h6>
                <div class="card-text mb-4" style="max-height: 200px; overflow-y: auto; border: 1px solid #eee; padding: 10px; border-radius: 5px;">
                    {{ art.ai_content | safe }}
                </div>
                <div class="d-flex gap-2">
                    <button onclick='sendToWP({{ art | tojson }}, "card-{{ loop.index }}")' class="btn btn-success btn-sm">Zatwierdź i wyślij do WP</button>
                    <a href="{{ art.url }}" target="_blank" class="btn btn-outline-secondary btn-sm">Zobacz oryginał</a>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>

    <script>
        async function sendToWP(data, cardId) {
            const btn = document.querySelector(`#${cardId} .btn-success`);
            btn.disabled = true;
            btn.innerHTML = "Wysyłanie...";

            try {
                const response = await fetch('/publish', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                
                if (response.ok) {
                    document.getElementById(cardId).style.opacity = '0.5';
                    btn.className = "btn btn-secondary btn-sm";
                    btn.innerHTML = "Wysłano pomyślnie!";
                } else {
                    alert("Błąd wysyłki!");
                    btn.disabled = false;
                    btn.innerHTML = "Spróbuj ponownie";
                }
            } catch (e) {
                alert("Błąd sieci!");
            }
        }
    </script>
</body>
</html>
"""

# --- LOGIKA SCRAPOWANIA I AI ---
def scrape_and_rewrite():
    articles = []
    sources = ["https://kvlt.pl/newsy/", "https://kvlt.pl/underground/"]
    
    for url in sources:
        try:
            r = requests.get(url, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            # Pobieramy 3 najnowsze linki z każdej sekcji
            links = [urljoin(url, a['href']) for a in soup.find_all('a', href=True) if '/newsy/' in a['href'] or '/underground/' in a['href']][:3]
            
            for link in set(links):
                art_r = requests.get(link, timeout=10)
                art_soup = BeautifulSoup(art_r.text, 'html.parser')
                
                title = art_soup.find('h1').get_text(strip=True)
                content_div = art_soup.find('div', class_='entry-content')
                if not content_div: continue
                
                raw_text = content_div.get_text(separator=' ', strip=True)[:4000]
                
                # Prompt do AI
                prompt = f"Zrób rewrite newsa: {title}. Treść: {raw_text}. Zwróć JSON: {{\"title\": \"...\", \"content\": \"...\"}} (użyj HTML <p>)."
                response = model.generate_content(prompt)
                ai_data = json.loads(response.text.replace('```json', '').replace('```', '').strip())
                
                articles.append({
                    "original_title": title,
                    "ai_title": ai_data['title'],
                    "ai_content": ai_data['content'],
                    "url": link,
                    "source_domain": "kvlt.pl"
                })
        except: continue
    return articles

# --- ENDPOINTY ---
@app.route('/')
def index():
    # Uwaga: Na Renderze darmowym scrapowanie może trwać długo. 
    # W produkcji lepiej byłoby to robić asynchronicznie, ale tu dla prostoty:
    data = scrape_and_rewrite()
    return render_template_string(HTML_TEMPLATE, articles=data)

@app.route('/publish', list=['POST'])
def publish():
    data = request.json
    auth = (WP_USER, WP_APP_PASS)
    payload = {
        "title": data['ai_title'],
        "content": data['ai_content'],
        "status": "draft"
    }
    r = requests.post(WP_URL, auth=auth, json=payload)
    return jsonify({"status": "ok"}) if r.status_code == 201 else (jsonify({"error": "wp_error"}), 400)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
