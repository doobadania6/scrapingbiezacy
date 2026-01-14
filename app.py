import os
import json
import requests
from flask import Flask, render_template_string, request, jsonify, send_from_directory
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import google.generativeai as genai

app = Flask(__name__)

# --- KONFIGURACJA ZMIENNYCH ---
# Render automatycznie przypisuje PORT, musimy go pobrać
PORT = int(os.environ.get("PORT", 10000))

# Konfiguracja AI
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

# Dane WordPress
WP_USER = os.environ.get("WP_USER")
WP_APP_PASS = os.environ.get("WP_APP_PASSWORD")
WP_URL = os.environ.get("WP_URL")

# --- SZABLON HTML (Ten sam co wcześniej) ---
# ... (pozostaje bez zmian, by nie zaciemniać kodu) ...

@app.route('/favicon.ico')
def favicon():
    # To uciszy błędy 404 w logach Rendera
    return '', 204

# --- LOGIKA SCRAPOWANIA ---
def get_all_news():
    all_articles = []
    sources = [
        {"url": "https://kvlt.pl/newsy/", "domain": "kvlt.pl", "selector": ".entry-content"},
        {"url": "https://chaosvault.com/category/newsy/", "domain": "chaosvault.com", "selector": ".td-post-content, .entry-content"}
    ]
    
    for source in sources:
        try:
            print(f"📡 Scrapowanie: {source['domain']}")
            r = requests.get(source["url"], timeout=15)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if source["domain"] in href and "/page/" not in href and len(href) > len(source["url"]) + 5:
                    links.append(urljoin(source["url"], href))
            
            for link in list(dict.fromkeys(links))[:3]:
                try:
                    res = requests.get(link, timeout=10)
                    art_soup = BeautifulSoup(res.text, 'html.parser')
                    title_tag = art_soup.find('h1')
                    if not title_tag: continue
                    title = title_tag.get_text(strip=True)
                    
                    content_div = art_soup.select_one(source["selector"])
                    if content_div:
                        for tag in content_div(['script', 'style', 'nav', 'aside']):
                            tag.decompose()
                        
                        raw_text = content_div.get_text(separator='\n', strip=True)[:4000]
                        
                        # AI Prompt
                        prompt = f"Przeredaguj ten news muzyczny: {title}. Tekst: {raw_text}. Zwróć JSON: {{\"title\": \"...\", \"content\": \"...\"}}"
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
                    print(f"Błąd przy linku {link}: {e}")
        except Exception as e:
            print(f"Błąd źródła {source['domain']}: {e}")
    return all_articles

@app.route('/')
def index():
    data = get_all_news()
    # Tu używamy Twojego HTML_TEMPLATE z poprzedniej wiadomości
    from __main__ import HTML_TEMPLATE 
    return render_template_string(HTML_TEMPLATE, articles=data)

@app.route('/publish', methods=['POST'])
def publish():
    data = request.json
    auth = (WP_USER, WP_APP_PASS)
    payload = {"title": data['ai_title'], "content": data['ai_content'], "status": "draft"}
    r = requests.post(WP_URL, auth=auth, json=payload)
    return jsonify({"status": "success"}) if r.status_code == 201 else (jsonify({"status": "error"}), 400)

if __name__ == '__main__':
    # KLUCZOWE DLA RENDERA: host='0.0.0.0' i port z os.environ
    app.run(host='0.0.0.0', port=PORT)
