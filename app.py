import os
import json
import requests
from flask import Flask, render_template_string, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import google.generativeai as genai

app = Flask(__name__)

# --- KONFIGURACJA ZMIENNYCH (Ustaw na Render) ---
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
WP_USER = os.environ.get("WP_USER")
WP_APP_PASS = os.environ.get("WP_APP_PASSWORD")
WP_URL = os.environ.get("WP_URL") 

model = genai.GenerativeModel('gemini-1.5-flash')

# --- SZABLON HTML ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Redaktor AI - KVLT & ChaosVault</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .card { background-color: #1e1e1e; border: 1px solid #333; color: #fff; margin-bottom: 2.5rem; border-radius: 12px; }
        .editable-area { background-color: #2a2a2a; color: #ddd; border: 1px solid #444; width: 100%; min-height: 250px; padding: 15px; border-radius: 8px; font-size: 0.95rem; line-height: 1.6; }
        .btn-primary { background-color: #d32f2f; border: none; font-weight: bold; }
        .btn-primary:hover { background-color: #b71c1c; }
        .badge-source { background-color: #444; color: #fff; margin-bottom: 10px; display: inline-block; padding: 5px 10px; border-radius: 4px; font-size: 0.75rem; }
        .original-link { font-size: 0.85rem; color: #888; text-decoration: none; }
        .original-link:hover { color: #d32f2f; }
        header { border-bottom: 1px solid #333; padding-bottom: 20px; }
    </style>
</head>
<body class="container py-5">
    <header class="mb-5 text-center">
        <h1 class="display-5 text-uppercase fw-bold" style="letter-spacing: 2px;">Metal News <span style="color: #d32f2f;">AI</span> Engine</h1>
        <p class="text-muted">Źródła: KVLT.pl & ChaosVault.com</p>
        <button onclick="location.reload()" class="btn btn-outline-danger">Skanuj obie strony</button>
    </header>

    <div id="articles">
        {% if articles %}
            {% for art in articles %}
            <div class="card shadow-lg" id="card-{{ loop.index }}">
                <div class="card-body p-4">
                    <span class="badge-source">DOMENA: {{ art.source_domain }}</span>
                    
                    <div class="mb-3">
                        <label class="form-label text-danger small fw-bold">PROPOZYCJA TYTUŁU:</label>
                        <input type="text" id="title-{{ loop.index }}" class="form-control bg-dark text-white border-secondary" value="{{ art.ai_title }}">
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label text-danger small fw-bold">TREŚĆ ARTYKUŁU (HTML):</label>
                        <textarea id="content-{{ loop.index }}" class="editable-area">{{ art.ai_content }}</textarea>
                    </div>

                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <button onclick='publishPost({{ loop.index }})' class="btn btn-primary px-4" id="btn-{{ loop.index }}">Wyślij do WordPress</button>
                            <span id="status-{{ loop.index }}" class="ms-3 fw-bold"></span>
                        </div>
                        <a href="{{ art.url }}" target="_blank" class="original-link">Link do oryginału ↗</a>
                    </div>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <div class="text-center py-5">
                <div class="spinner-border text-danger" role="status"></div>
                <p class="mt-3">Scrapowanie i praca AI... to może potrwać do 30 sekund.</p>
            </div>
        {% endif %}
    </div>

    <script>
        async function publishPost(id) {
            const btn = document.getElementById(`btn-${id}`);
            const status = document.getElementById(`status-${id}`);
            const title = document.getElementById(`title-${id}`).value;
            const content = document.getElementById(`content-${id}`).value;

            btn.disabled = true;
            status.innerHTML = "WYSYŁANIE...";
            status.style.color = "#aaa";

            try {
                const response = await fetch('/publish', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ ai_title: title, ai_content: content })
                });
                
                if (response.ok) {
                    status.innerHTML = "DOSTARCZONO!";
                    status.style.color = "#4caf50";
                    btn.className = "btn btn-outline-secondary disabled";
                    btn.innerHTML = "Wysłano pomyślnie";
                } else { throw new Error(); }
            } catch (e) {
                status.innerHTML = "BŁĄD!";
                status.style.color = "#f44336";
                btn.disabled = false;
            }
        }
    </script>
</body>
</html>
"""

# --- LOGIKA SCRAPOWANIA ---
def get_all_news():
    all_articles = []
    
    # Definicja źródeł i ich specyfiki
    sources = [
        {"url": "https://kvlt.pl/newsy/", "domain": "kvlt.pl", "selector": ".entry-content"},
        {"url": "https://chaosvault.com/category/newsy/", "domain": "chaosvault.com", "selector": ".entry-content, .post-content, .td-post-content"}
    ]
    
    for source in sources:
        try:
            r = requests.get(source["url"], timeout=15)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                # Filtr dla Chaos Vault i KVLT
                if source["domain"] in href and "/page/" not in href and len(href) > len(source["url"]) + 3:
                    links.append(urljoin(source["url"], href))
            
            # Pobieramy 3 unikalne, najnowsze linki na każde źródło
            for link in list(dict.fromkeys(links))[:3]:
                try:
                    res = requests.get(link, timeout=10)
                    art_soup = BeautifulSoup(res.text, 'html.parser')
                    
                    title = art_soup.find('h1').get_text(strip=True)
                    # Szukamy treści według selektorów specyficznych dla WP
                    content_div = art_soup.select_one(source["selector"])
                    
                    if content_div:
                        for tag in content_div(['script', 'style', 'nav', 'aside', 'form']):
                            tag.decompose()
                        
                        raw_text = content_div.get_text(separator='\n', strip=True)[:4000]
                        
                        # AI REWRITE
                        prompt = f"""Działaj jako redaktor serwisu muzycznego. Przeredaguj poniższy news, aby brzmiał świeżo i profesjonalnie. 
                        Tytuł: {title}
                        Źródło: {raw_text}
                        Zwróć TYLKO czysty format JSON bez markdown: {{"title": "nowy tytuł", "content": "tekst w HTML"}}"""
                        
                        response = model.generate_content(prompt)
                        clean_json = response.text.strip().replace('```json', '').replace('```', '')
                        ai_data = json.loads(clean_json)

                        all_articles.append({
                            "original_title": title,
                            "ai_title": ai_data.get('title', 'Nowy News'),
                            "ai_content": ai_data.get('content', ''),
                            "url": link,
                            "source_domain": source["domain"]
                        })
                except Exception as e:
                    print(f"Błąd wewnątrz {link}: {e}")
        except Exception as e:
            print(f"Błąd źródła {source['url']}: {e}")
            
    return all_articles

# --- FLASK ROUTES ---
@app.route('/')
def index():
    data = get_all_news()
    return render_template_string(HTML_TEMPLATE, articles=data)

@app.route('/publish', methods=['POST'])
def publish():
    data = request.json
    auth = (WP_USER, WP_APP_PASS)
    payload = {
        "title": data['ai_title'],
        "content": data['ai_content'],
        "status": "draft"
    }
    r = requests.post(WP_URL, auth=auth, json=payload)
    return jsonify({"status": "success"}) if r.status_code == 201 else (jsonify({"status": "error"}), 400)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
