import os
import json
import requests
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from dotenv import load_dotenv

# Załaduj zmienne z pliku .env
load_dotenv()

app = Flask(__name__)
PORT = int(os.environ.get("PORT", 10000))

# --- KONFIGURACJA GEMINI API ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY nie znaleziony w .env lub zmiennych środowiskowych!")

# Model Gemini (taki sam jak w Lege Memo)
GEMINI_MODEL = "models/gemini-2.0-flash-exp"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/{GEMINI_MODEL}:generateContent"

# Pliki danych
SOURCES_FILE = "sources.json"
ARTICLES_FILE = "articles.json"

def load_sources():
    """Załaduj źródła z pliku JSON"""
    if os.path.exists(SOURCES_FILE):
        try:
            with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return [
        {"url": "https://kvlt.pl/newsy/", "domain": "kvlt.pl"},
        {"url": "https://chaosvault.com/category/newsy/", "domain": "chaosvault.com"}
    ]

def save_sources(sources):
    """Zapisz źródła do pliku JSON"""
    with open(SOURCES_FILE, 'w', encoding='utf-8') as f:
        json.dump(sources, f, ensure_ascii=False, indent=2)

def load_articles():
    """Załaduj zapisane artykuły"""
    if os.path.exists(ARTICLES_FILE):
        try:
            with open(ARTICLES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return []

def save_articles(articles):
    """Zapisz artykuły do pliku"""
    with open(ARTICLES_FILE, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

def call_gemini_api(prompt):
    """Wywołaj Gemini API (zgodnie z metodą z Lege Memo)"""
    try:
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        response = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            error_data = response.json()
            raise Exception(error_data.get('error', {}).get('message', f"API Error: {response.status_code}"))
        
        data = response.json()
        text = data['candidates'][0]['content']['parts'][0]['text']
        
        # Usuń potencjalne markdown formatting
        text = text.replace('```json', '').replace('```', '').strip()
        
        return text
        
    except Exception as e:
        raise Exception(f"Gemini API Error: {str(e)}")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Metal Growl AI | Premium Edition</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Inter:wght@300;400;500;600;700&display=swap');
        
        :root {
            --primary: #0a0e1a;
            --secondary: #1a1a2e;
            --accent: #16213e;
            --gold: #d4af37;
            --gold-light: #f4e4c1;
            --gold-dark: #b8941e;
            --surface: rgba(255,255,255,0.03);
            --border: rgba(212, 175, 55, 0.2);
            --text-primary: #f5f5f5;
            --text-secondary: #b8b8b8;
            --shadow: rgba(0, 0, 0, 0.5);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 50%, var(--accent) 100%);
            color: var(--text-primary);
            font-family: 'Inter', sans-serif;
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* Header */
        .header {
            text-align: center;
            padding: 50px 20px 30px;
            background: linear-gradient(180deg, var(--surface) 0%, transparent 100%);
            border-bottom: 2px solid var(--border);
            margin-bottom: 40px;
            position: relative;
        }

        .header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 200px;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--gold), transparent);
        }

        .header h1 {
            font-family: 'Playfair Display', serif;
            font-size: 3.5rem;
            font-weight: 700;
            letter-spacing: 8px;
            background: linear-gradient(135deg, var(--gold) 0%, var(--gold-light) 50%, var(--gold) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 30px rgba(212, 175, 55, 0.3);
            margin-bottom: 10px;
        }

        .header p {
            color: var(--text-secondary);
            font-size: 0.85rem;
            letter-spacing: 3px;
            text-transform: uppercase;
        }

        /* Main Container */
        .main-container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 0 30px 80px;
            display: grid;
            grid-template-columns: 320px 1fr 320px;
            gap: 30px;
        }

        /* Panels */
        .side-panel {
            background: rgba(10, 14, 39, 0.8);
            backdrop-filter: blur(20px);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 25px;
            height: fit-content;
            position: sticky;
            top: 20px;
            box-shadow: 0 8px 32px var(--shadow);
        }

        .panel-header {
            font-family: 'Playfair Display', serif;
            color: var(--gold);
            font-size: 1.4rem;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        /* Control Panel */
        .control-group {
            margin-bottom: 20px;
        }

        .control-label {
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .date-input {
            width: 100%;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border);
            color: var(--text-primary);
            padding: 12px 15px;
            border-radius: 8px;
            font-size: 0.95rem;
            outline: none;
            transition: all 0.3s ease;
        }

        .date-input:focus {
            border-color: var(--gold);
            box-shadow: 0 0 20px rgba(212, 175, 55, 0.2);
        }

        .btn-primary {
            width: 100%;
            background: linear-gradient(135deg, var(--gold) 0%, var(--gold-dark) 100%);
            border: none;
            color: var(--primary);
            padding: 14px 20px;
            font-weight: 700;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 2px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 20px rgba(212, 175, 55, 0.3);
            margin-bottom: 12px;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 30px rgba(212, 175, 55, 0.5);
        }

        .btn-secondary {
            width: 100%;
            background: transparent;
            border: 2px solid var(--gold);
            color: var(--gold);
            padding: 12px 20px;
            font-weight: 600;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-bottom: 12px;
        }

        .btn-secondary:hover {
            background: rgba(212, 175, 55, 0.1);
            border-color: var(--gold-light);
        }

        .btn-danger {
            background: rgba(239, 68, 68, 0.1);
            border: 2px solid #ef4444;
            color: #ef4444;
        }

        .btn-danger:hover {
            background: rgba(239, 68, 68, 0.2);
        }

        /* Stats */
        .stat-item {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid rgba(212, 175, 55, 0.1);
            font-size: 0.9rem;
        }

        .stat-item:last-child {
            border-bottom: none;
        }

        .stat-value {
            color: var(--gold);
            font-weight: 700;
            font-size: 1.1rem;
        }

        /* Sources Management */
        .source-list {
            max-height: 300px;
            overflow-y: auto;
            margin-bottom: 15px;
        }

        .source-item {
            background: rgba(255, 255, 255, 0.03);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 10px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            transition: all 0.3s ease;
        }

        .source-item:hover {
            background: rgba(255, 255, 255, 0.05);
            border-color: var(--gold);
        }

        .source-domain {
            color: var(--gold);
            font-weight: 600;
            margin-bottom: 4px;
            font-size: 0.9rem;
        }

        .source-url {
            color: var(--text-secondary);
            font-size: 0.75rem;
            word-break: break-all;
        }

        .source-delete {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid #ef4444;
            color: #ef4444;
            padding: 4px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.75rem;
            margin-top: 8px;
            transition: all 0.3s ease;
        }

        .source-delete:hover {
            background: rgba(239, 68, 68, 0.2);
        }

        .add-source-form {
            background: rgba(212, 175, 55, 0.05);
            padding: 15px;
            border-radius: 10px;
            border: 1px solid var(--border);
        }

        .form-input {
            width: 100%;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: var(--text-primary);
            padding: 10px 12px;
            border-radius: 6px;
            margin-bottom: 10px;
            font-size: 0.85rem;
            outline: none;
            transition: all 0.3s ease;
        }

        .form-input:focus {
            border-color: var(--gold);
        }

        /* Articles Container */
        .articles-container {
            display: flex;
            flex-direction: column;
            gap: 25px;
        }

        .article-card {
            background: rgba(10, 14, 39, 0.7);
            backdrop-filter: blur(20px);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 30px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 20px var(--shadow);
        }

        .article-card:hover {
            border-color: var(--gold);
            box-shadow: 0 8px 30px rgba(212, 175, 55, 0.2);
            transform: translateY(-2px);
        }

        .article-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid var(--border);
        }

        .source-tag {
            display: inline-block;
            background: linear-gradient(135deg, rgba(212, 175, 55, 0.2) 0%, rgba(212, 175, 55, 0.1) 100%);
            color: var(--gold);
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            border: 1px solid var(--border);
        }

        .article-title {
            font-size: 1.6rem;
            font-weight: 600;
            color: var(--text-primary);
            margin: 12px 0;
            line-height: 1.4;
        }

        .accordion {
            margin-top: 20px;
        }

        .accordion-item {
            background: transparent;
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            margin-bottom: 12px;
            overflow: hidden;
        }

        .accordion-button {
            background: rgba(0, 0, 0, 0.3);
            color: var(--text-primary);
            padding: 15px 20px;
            font-weight: 600;
            border: none;
            font-size: 0.9rem;
            transition: all 0.3s ease;
        }

        .accordion-button:not(.collapsed) {
            background: linear-gradient(135deg, rgba(212, 175, 55, 0.15) 0%, rgba(212, 175, 55, 0.05) 100%);
            color: var(--gold);
        }

        .accordion-body {
            background: rgba(0, 0, 0, 0.4);
            color: var(--text-secondary);
            padding: 20px;
            line-height: 1.8;
            font-size: 0.9rem;
        }

        .action-buttons {
            display: flex;
            gap: 10px;
            margin-top: 20px;
            flex-wrap: wrap;
        }

        .btn-action {
            background: rgba(212, 175, 55, 0.1);
            border: 1px solid var(--gold);
            color: var(--gold);
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .btn-action:hover {
            background: var(--gold);
            color: var(--primary);
        }

        .btn-action.generate {
            background: linear-gradient(135deg, var(--gold) 0%, var(--gold-dark) 100%);
            color: var(--primary);
            border: none;
        }

        .btn-action.generate:hover {
            box-shadow: 0 4px 20px rgba(212, 175, 55, 0.4);
        }

        .publish-section {
            display: none;
            margin-top: 25px;
            padding-top: 25px;
            border-top: 1px solid var(--border);
        }

        .publish-section.show {
            display: block;
        }

        .form-label {
            color: var(--gold);
            font-weight: 600;
            font-size: 0.85rem;
            margin-bottom: 8px;
            display: block;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        textarea, input[type="text"] {
            width: 100%;
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid var(--border);
            color: var(--text-primary);
            padding: 12px 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
            outline: none;
            transition: all 0.3s ease;
        }

        textarea:focus, input[type="text"]:focus {
            border-color: var(--gold);
            box-shadow: 0 0 20px rgba(212, 175, 55, 0.2);
        }

        .status-message {
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            margin-top: 15px;
            text-align: center;
        }

        .status-success {
            background: rgba(74, 222, 128, 0.2);
            color: #4ade80;
            border: 1px solid #4ade80;
        }

        .status-error {
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
            border: 1px solid #ef4444;
        }

        .status-info {
            background: rgba(100, 200, 255, 0.2);
            color: #64c8ff;
            border: 1px solid #64c8ff;
        }

        .loading {
            opacity: 0.6;
            pointer-events: none;
        }

        .empty-state {
            text-align: center;
            padding: 80px 20px;
            color: var(--text-secondary);
        }

        .empty-state-icon {
            font-size: 4rem;
            margin-bottom: 20px;
            opacity: 0.3;
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: var(--primary); }
        ::-webkit-scrollbar-thumb { 
            background: var(--gold); 
            border-radius: 4px; 
        }
        ::-webkit-scrollbar-thumb:hover { background: var(--gold-light); }

        /* Responsive */
        @media (max-width: 1200px) {
            .main-container {
                grid-template-columns: 1fr;
            }
            .side-panel {
                position: relative;
                top: 0;
            }
        }

        @media (max-width: 768px) {
            .header h1 {
                font-size: 2.5rem;
                letter-spacing: 4px;
            }
            .main-container {
                padding: 0 15px 40px;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>METAL GROWL AI</h1>
        <p>Premium Content Generator</p>
    </div>

    <div class="main-container">
        <!-- Left Panel: Control -->
        <aside class="side-panel">
            <h2 class="panel-header">⚙️ Centrum Kontroli</h2>
            
            <div class="control-group">
                <div class="control-label">Data scrapowania</div>
                <input type="date" class="date-input" id="scrapeDate" value="{{ today }}">
            </div>

            <button class="btn-primary" onclick="startScraping()">
                🤖 URUCHOM ROBOTA
            </button>

            <button class="btn-secondary" onclick="refreshSources()">
                🔄 Odśwież źródła
            </button>

            <button class="btn-secondary" onclick="exportAllArticles()">
                💾 Eksportuj artykuły (TXT)
            </button>

            <button class="btn-secondary btn-danger" onclick="resetAll()">
                🗑️ Reset wszystkiego
            </button>

            <div style="margin-top: 30px;">
                <h3 class="panel-header" style="font-size: 1.1rem;">📊 Statystyki</h3>
                <div class="stat-item">
                    <span>Artykuły:</span>
                    <span class="stat-value" id="articleCount">0</span>
                </div>
                <div class="stat-item">
                    <span>Źródła:</span>
                    <span class="stat-value" id="sourceCount">0</span>
                </div>
                <div class="stat-item">
                    <span>Wygenerowane AI:</span>
                    <span class="stat-value" id="generatedCount">0</span>
                </div>
            </div>
        </aside>

        <!-- Center: Articles -->
        <main class="articles-container" id="articlesContainer">
            {% if articles %}
                {% for art in articles %}
                <div class="article-card" data-index="{{ loop.index }}">
                    <div class="article-header">
                        <div>
                            <span class="source-tag">{{ art.source }}</span>
                            <h3 class="article-title">{{ art.title }}</h3>
                        </div>
                    </div>
                    
                    <div class="accordion" id="accordion-{{ loop.index }}">
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#original-{{ loop.index }}">
                                    📄 Treść oryginalna
                                </button>
                            </h2>
                            <div id="original-{{ loop.index }}" class="accordion-collapse collapse" data-bs-parent="#accordion-{{ loop.index }}">
                                <div class="accordion-body">{{ art.raw_content }}</div>
                            </div>
                        </div>
                        
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#generated-{{ loop.index }}">
                                    ✨ Treść wygenerowana AI
                                </button>
                            </h2>
                            <div id="generated-{{ loop.index }}" class="accordion-collapse collapse" data-bs-parent="#accordion-{{ loop.index }}">
                                <div class="accordion-body" id="gen-content-{{ loop.index }}">
                                    <p style="color: #888;">Kliknij "Generuj AI" poniżej...</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="action-buttons">
                        <button class="btn-action generate" onclick="generateAI({{ loop.index }})">
                            ✨ Generuj AI
                        </button>
                        <button class="btn-action" onclick="copyOriginal({{ loop.index }})">
                            📋 Kopiuj oryginał
                        </button>
                        <button class="btn-action" onclick="copyGenerated({{ loop.index }})">
                            📋 Kopiuj AI
                        </button>
                    </div>
                    
                    <div class="publish-section" id="publish-{{ loop.index }}">
                        <label class="form-label">Tytuł:</label>
                        <input type="text" id="ai-title-{{ loop.index }}" placeholder="Wygenerowany tytuł...">
                        
                        <label class="form-label">Treść (HTML):</label>
                        <textarea id="ai-content-{{ loop.index }}" rows="8"></textarea>
                        
                        <button class="btn-action generate" onclick="sendToWP({{ loop.index }})">
                            🚀 Wyślij do WordPress
                        </button>
                        <div id="status-{{ loop.index }}" class="status-message" style="display: none;"></div>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="empty-state">
                    <div class="empty-state-icon">📰</div>
                    <h3>Brak artykułów</h3>
                    <p>Uruchom robota, aby pobrać najnowsze treści</p>
                </div>
            {% endif %}
        </main>

        <!-- Right Panel: Sources -->
        <aside class="side-panel">
            <h2 class="panel-header">🌐 Źródła</h2>
            
            <div class="source-list" id="sourcesList"></div>
            
            <div class="add-source-form">
                <h3 style="color: var(--gold); font-size: 0.9rem; margin-bottom: 12px;">Dodaj źródło:</h3>
                <input type="text" class="form-input" id="newUrl" placeholder="https://example.com/news/">
                <input type="text" class="form-input" id="newDomain" placeholder="example.com">
                <button class="btn-primary" onclick="addSource()">
                    ➕ Dodaj
                </button>
            </div>
        </aside>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // === INICJALIZACJA ===
        document.addEventListener('DOMContentLoaded', () => {
            loadSources();
            updateStats();
        });

        // === ZARZĄDZANIE ŹRÓDŁAMI ===
        async function loadSources() {
            try {
                const res = await fetch('/sources');
                const data = await res.json();
                const list = document.getElementById('sourcesList');
                list.innerHTML = '';
                
                data.sources.forEach(source => {
                    const item = document.createElement('div');
                    item.className = 'source-item';
                    item.innerHTML = `
                        <div class="source-domain">${source.domain}</div>
                        <div class="source-url">${source.url}</div>
                        <button class="source-delete" onclick="deleteSource('${source.domain}')">
                            🗑️ Usuń
                        </button>
                    `;
                    list.appendChild(item);
                });
                
                updateStats();
            } catch (e) {
                console.error('Błąd ładowania źródeł:', e);
            }
        }

        async function addSource() {
            const url = document.getElementById('newUrl').value.trim();
            const domain = document.getElementById('newDomain').value.trim();
            
            if (!url || !domain) {
                alert('❌ Wypełnij oba pola!');
                return;
            }
            
            try {
                const res = await fetch('/sources', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ url, domain })
                });
                
                const data = await res.json();
                if (data.error) {
                    alert('❌ ' + data.error);
                } else {
                    document.getElementById('newUrl').value = '';
                    document.getElementById('newDomain').value = '';
                    loadSources();
                    showStatus('✅ Źródło dodane!', 'success');
                }
            } catch (e) {
                alert('❌ Błąd: ' + e.message);
            }
        }

        async function deleteSource(domain) {
            if (!confirm(`Czy na pewno usunąć źródło: ${domain}?`)) return;
            
            try {
                const res = await fetch('/sources', {
                    method: 'DELETE',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ domain })
                });
                
                const data = await res.json();
                if (data.success) {
                    loadSources();
                    showStatus('✅ Źródło usunięte!', 'success');
                }
            } catch (e) {
                alert('❌ Błąd: ' + e.message);
            }
        }

        async function refreshSources() {
            await loadSources();
            showStatus('🔄 Źródła odświeżone!', 'info');
        }

        // === SCRAPOWANIE ===
        async function startScraping() {
            const date = document.getElementById('scrapeDate').value;
            
            if (!confirm(`Uruchomić robota dla daty: ${date}?`)) return;
            
            const btn = event.target;
            btn.disabled = true;
            btn.innerHTML = '⏳ Scrapowanie...';
            
            try {
                const res = await fetch('/scrape', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ date })
                });
                
                const data = await res.json();
                
                if (data.error) {
                    throw new Error(data.error);
                }
                
                showStatus(`✅ Pobrano ${data.count} artykułów!`, 'success');
                setTimeout(() => location.reload(), 1500);
                
            } catch (e) {
                alert('❌ Błąd: ' + e.message);
            } finally {
                btn.disabled = false;
                btn.innerHTML = '🤖 URUCHOM ROBOTA';
            }
        }

        async function resetAll() {
            if (!confirm('⚠️ To usunie WSZYSTKIE artykuły i dane! Kontynuować?')) return;
            
            try {
                const res = await fetch('/reset', { method: 'POST' });
                const data = await res.json();
                
                if (data.success) {
                    showStatus('🗑️ Wszystko wyczyszczone!', 'info');
                    setTimeout(() => location.reload(), 1500);
                }
            } catch (e) {
                alert('❌ Błąd: ' + e.message);
            }
        }

        // === GENEROWANIE AI ===
        async function generateAI(id) {
            const btn = event.target;
            const card = btn.closest('.article-card');
            const originalText = card.querySelector(`#original-${id} .accordion-body`).innerText;
            const title = card.querySelector('.article-title').innerText;
            
            btn.disabled = true;
            btn.classList.add('loading');
            btn.innerHTML = '⏳ Przetwarzanie...';
            
            try {
                const res = await fetch('/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ title, content: originalText })
                });
                
                const data = await res.json();
                if (data.error) throw new Error(data.error);
                
                document.getElementById(`gen-content-${id}`).innerHTML = `<p>${data.content}</p>`;
                document.getElementById(`ai-title-${id}`).value = data.title;
                document.getElementById(`ai-content-${id}`).value = data.content;
                document.getElementById(`publish-${id}`).classList.add('show');
                
                btn.innerHTML = '✅ Gotowe';
                updateStats();
                
            } catch (e) {
                alert('❌ Błąd AI: ' + e.message);
                btn.innerHTML = '❌ Spróbuj ponownie';
            } finally {
                btn.disabled = false;
                btn.classList.remove('loading');
            }
        }

        // === KOPIOWANIE ===
        function copyOriginal(id) {
            const text = document.querySelector(`#original-${id} .accordion-body`).innerText;
            copyToClipboard(text, 'Oryginał skopiowany!');
        }

        function copyGenerated(id) {
            const text = document.getElementById(`ai-content-${id}`).value;
            if (!text || text === '') {
                alert('❌ Najpierw wygeneruj treść AI!');
                return;
            }
            copyToClipboard(text, 'Treść AI skopiowana!');
        }

        function copyToClipboard(text, message) {
            navigator.clipboard.writeText(text).then(() => {
                showStatus(`✅ ${message}`, 'success');
            }).catch(() => {
                alert('❌ Nie udało się skopiować');
            });
        }

        // === EKSPORT ===
        async function exportAllArticles() {
            try {
                const res = await fetch('/export');
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `metal_ai_export_${new Date().toISOString().slice(0,10)}.txt`;
                a.click();
                window.URL.revokeObjectURL(url);
                showStatus('💾 Eksport zapisany!', 'success');
            } catch (e) {
                alert('❌ Błąd eksportu: ' + e.message);
            }
        }

        // === WORDPRESS ===
        async function sendToWP(id) {
            const statusEl = document.getElementById(`status-${id}`);
            statusEl.style.display = 'block';
            statusEl.className = 'status-message status-info';
            statusEl.innerText = '⏳ Wysyłanie do WordPress...';
            
            try {
                const res = await fetch('/publish', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        title: document.getElementById(`ai-title-${id}`).value,
                        content: document.getElementById(`ai-content-${id}`).value
                    })
                });
                
                if (res.ok) {
                    statusEl.className = 'status-message status-success';
                    statusEl.innerText = '✅ Wysłano do WordPressa!';
                } else {
                    statusEl.className = 'status-message status-error';
                    statusEl.innerText = '❌ Błąd WordPress';
                }
            } catch (e) {
                statusEl.className = 'status-message status-error';
                statusEl.innerText = '❌ Błąd połączenia';
            }
        }

        // === POMOCNICZE ===
        function updateStats() {
            const articles = document.querySelectorAll('.article-card').length;
            const sources = document.querySelectorAll('.source-item').length;
            const generated = document.querySelectorAll('.publish-section.show').length;
            
            document.getElementById('articleCount').textContent = articles;
            document.getElementById('sourceCount').textContent = sources;
            document.getElementById('generatedCount').textContent = generated;
        }

        function showStatus(message, type) {
            const container = document.querySelector('.main-container');
            const status = document.createElement('div');
            status.className = `status-message status-${type}`;
            status.style.position = 'fixed';
            status.style.top = '20px';
            status.style.right = '20px';
            status.style.zIndex = '9999';
            status.innerText = message;
            document.body.appendChild(status);
            
            setTimeout(() => status.remove(), 3000);
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Główna strona - wyświetl zapisane artykuły"""
    articles = load_articles()
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template_string(HTML_TEMPLATE, articles=articles, today=today)

@app.route('/sources', methods=['GET', 'POST', 'DELETE'])
def manage_sources():
    """Zarządzanie źródłami"""
    try:
        if request.method == 'GET':
            sources = load_sources()
            return jsonify({"sources": sources})
        
        elif request.method == 'POST':
            data = request.json
            url = data.get('url', '').strip()
            domain = data.get('domain', '').strip()
            
            if not url or not domain:
                return jsonify({"error": "URL i domena są wymagane"}), 400
            
            sources = load_sources()
            if any(s['domain'] == domain for s in sources):
                return jsonify({"error": "Źródło już istnieje"}), 400
            
            sources.append({"url": url, "domain": domain})
            save_sources(sources)
            return jsonify({"success": True, "sources": sources})
        
        elif request.method == 'DELETE':
            data = request.json
            domain = data.get('domain', '').strip()
            
            sources = load_sources()
            sources = [s for s in sources if s['domain'] != domain]
            save_sources(sources)
            return jsonify({"success": True, "sources": sources})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/scrape', methods=['POST'])
def scrape_articles():
    """Scrapuj artykuły z podanej daty"""
    try:
        data = request.json
        target_date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        all_news = []
        headers = {'User-Agent': 'Mozilla/5.0'}
        sources = load_sources()
        
        for s in sources:
            try:
                r = requests.get(s["url"], headers=headers, timeout=10)
                soup = BeautifulSoup(r.text, 'html.parser')
                links = [urljoin(s["url"], a['href']) for a in soup.find_all('a', href=True) 
                         if s["domain"] in a['href'] and len(a['href']) > 45 and "page" not in a['href']]
                links = list(dict.fromkeys(links))[:15]
                
                for l in links:
                    try:
                        ar = requests.get(l, headers=headers, timeout=10)
                        asoup = BeautifulSoup(ar.text, 'html.parser')
                        t = asoup.find('h1').get_text(strip=True) if asoup.find('h1') else "Metal News"
                        c_tag = asoup.find('article') or asoup.find('div', class_='entry-content') or asoup.find('div', class_='td-post-content')
                        c = c_tag.get_text(separator=' ', strip=True)[:2500] if c_tag else "Brak treści."
                        
                        all_news.append({
                            "title": t,
                            "raw_content": c,
                            "source": s["domain"],
                            "scraped_date": target_date
                        })
                    except:
                        continue
            except:
                continue
        
        save_articles(all_news)
        return jsonify({"success": True, "count": len(all_news)})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/generate', methods=['POST'])
def generate():
    """Generuj treść AI używając Gemini"""
    try:
        data = request.json
        prompt = (
            f"Jesteś profesjonalnym redaktorem prasowym. Przetwórz poniższy artykuł, zachowując wszystkie istotne informacje, "
            f"ale przedstawiając go w bardziej formalny, klarowny i rzeczowy sposób. Tekst powinien być informacyjny, "
            f"ustrukturyzowany i łatwy do przeczytania. Unikaj emocjonalnych sformułowań i pompatyczności. "
            f"Tytuł: '{data['title']}' \n\nTreść: '{data['content']}'. "
            f"Zwróć wynik TYLKO jako czysty JSON: {{\"title\": \"Nowy tytuł (krótki, trafny)\", \"content\": \"Przerobiona treść (plain text, bez HTML)\"}}"
        )
        
        response_text = call_gemini_api(prompt)
        
        # Parsuj JSON
        result = json.loads(response_text)
        return jsonify(result)
        
    except json.JSONDecodeError:
        return jsonify({"error": "Błąd parsowania odpowiedzi AI"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/publish', methods=['POST'])
def publish():
    """Publikuj do WordPress"""
    try:
        data = request.json
        auth = (os.environ.get("WP_USER"), os.environ.get("WP_APP_PASSWORD"))
        wp_url = os.environ.get("WP_URL")
        
        if not wp_url:
            return jsonify({"error": "WP_URL nie skonfigurowany"}), 500
        
        payload = {
            "title": data['title'],
            "content": data['content'],
            "status": "draft"
        }
        
        r = requests.post(wp_url, auth=auth, json=payload, timeout=15)
        
        if r.status_code == 201:
            return jsonify({"ok": True})
        else:
            return jsonify({"error": f"WordPress: {r.status_code}"}), 400
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/export', methods=['GET'])
def export_articles():
    """Eksportuj wszystkie artykuły do TXT"""
    try:
        articles = load_articles()
        
        output = "═══════════════════════════════════════\n"
        output += "     METAL GROWL AI - EKSPORT\n"
        output += f"     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        output += "═══════════════════════════════════════\n\n"
        
        for i, art in enumerate(articles, 1):
            output += f"\n{'='*60}\n"
            output += f"ARTYKUŁ #{i}\n"
            output += f"Źródło: {art['source']}\n"
            output += f"Tytuł: {art['title']}\n"
            output += f"{'='*60}\n\n"
            output += f"{art['raw_content']}\n\n"
        
        return output, 200, {
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Disposition': f'attachment; filename=export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        }
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/reset', methods=['POST'])
def reset():
    """Resetuj wszystkie dane"""
    try:
        if os.path.exists(ARTICLES_FILE):
            os.remove(ARTICLES_FILE)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
