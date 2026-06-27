# ================================================================
# app.py - Adventure Digital Library - Complete Python Version
# ONE FILE - Everything included!
# ================================================================

import os
import json
import asyncio
import re
import base64
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string, send_file
from flask_cors import CORS
import edge_tts

# ================================================================
# CONFIG
# ================================================================

app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).parent
BOOKS_DIR = BASE_DIR / 'Books'
OUTPUT_DIR = BASE_DIR / 'output'
AUDIO_DIR = OUTPUT_DIR / 'audio'
SRT_DIR = OUTPUT_DIR / 'srt'

# Create directories
OUTPUT_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)
SRT_DIR.mkdir(exist_ok=True)

# Edge TTS Voice - Malayalam Midhun
VOICE = 'ml-MidhunNeural'

# ================================================================
# HELPERS
# ================================================================

def clean_text(text):
    """Remove HTML tags"""
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def load_books():
    """Load books.json"""
    try:
        with open('books.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def load_book_parts(book_id):
    """Load all parts of a book"""
    parts = []
    part_num = 1
    
    books = load_books()
    book = next((b for b in books if b['id'] == book_id), None)
    if not book:
        return []
    
    folder = book.get('folder', book_id)
    
    while True:
        file_path = BOOKS_DIR / folder / f"{folder}_part_{part_num}.json"
        if not file_path.exists():
            break
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                parts.append({
                    'id': len(parts) + 1,
                    'part': item.get('part', str(part_num)),
                    'page': item.get('page', str(len(parts) + 1)),
                    'ar': item.get('ar', ''),
                    'ml': item.get('ml', ''),
                    'en': item.get('en', ''),
                    'ar_pure': clean_text(item.get('ar', '')),
                    'ml_pure': clean_text(item.get('ml', '')),
                    'en_pure': clean_text(item.get('en', '')),
                    'is_head': bool(re.search(r'<h[1-6]', item.get('ar', ''))),
                    'heading': clean_text(re.sub(r'<[^>]+>', '', item.get('ar', ''))).strip()[:50]
                })
        part_num += 1
    
    return parts

async def generate_tts(text):
    """Generate MP3 using Edge TTS - Malayalam Midhun"""
    if not text:
        return None
    communicate = edge_tts.Communicate(text, VOICE)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data

def format_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

async def generate_srt(text):
    """Generate SRT with word timings"""
    if not text:
        return None
    communicate = edge_tts.Communicate(text, VOICE)
    words = []
    async for chunk in communicate.stream():
        if chunk["type"] == "WordBoundary":
            words.append({
                'text': chunk.get('text', ''),
                'offset': chunk.get('offset', 0) / 10000000,
                'duration': chunk.get('duration', 0) / 10000000
            })
    if not words:
        return None
    srt_lines = []
    for i, word in enumerate(words, 1):
        start = word['offset']
        end = start + word.get('duration', 0.5)
        srt_lines.append(str(i))
        srt_lines.append(f"{format_time(start)} --> {format_time(end)}")
        srt_lines.append(word['text'])
        srt_lines.append("")
    return "\n".join(srt_lines)

# ================================================================
# HTML (Replaces index.html - Everything in one file!)
# ================================================================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ml">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Adventure Digital Library Pro</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Manjari:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-green: #1b4d3e;
            --bg: #f4f7f6;
            --card-bg: #ffffff;
            --text-dark: #2c3e50;
            --border: #cbd5e1;
            --radius: 12px;
            --font-ar: 'Amiri', serif;
            --font-ml: 'Manjari', sans-serif;
            --bottom-nav: 70px;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background: var(--bg);
            color: var(--text-dark);
            font-family: var(--font-ml);
            height: 100vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        
        /* ===== HEADER ===== */
        .header {
            background: var(--primary-green);
            color: white;
            padding: 15px;
            position: sticky;
            top: 0;
            z-index: 1000;
        }
        .top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .top-bar .title { font-size: 18px; font-weight: bold; }
        .top-bar .actions i { cursor: pointer; padding: 5px; font-size: 18px; margin-left: 10px; }
        
        .tabs {
            display: flex;
            justify-content: space-around;
            padding-bottom: 5px;
        }
        .tab-item {
            color: #bdc3c7;
            padding: 10px;
            cursor: pointer;
            font-weight: bold;
            font-size: 14px;
            border-bottom: 3px solid transparent;
            transition: 0.3s;
        }
        .tab-item.active {
            color: white;
            border-bottom-color: white;
        }
        
        .search-bar { padding: 10px 0; display: none; }
        .search-bar.show { display: block; }
        .search-bar input {
            width: 100%;
            padding: 10px 16px;
            border-radius: 25px;
            border: none;
            font-size: 14px;
            background: rgba(255,255,255,0.2);
            color: white;
        }
        .search-bar input::placeholder { color: #cbd5e1; }
        
        /* ===== BOOK GRID ===== */
        .container { padding: 15px; max-width: 1000px; margin: auto; width: 100%; overflow-y: auto; flex: 1; padding-bottom: 90px; }
        .book-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
            gap: 15px;
        }
        .book-card {
            background: var(--card-bg);
            border-radius: var(--radius);
            border: 1px solid var(--border);
            box-shadow: 0 4px 15px rgba(0,0,0,0.06);
            overflow: hidden;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .book-card:active { transform: scale(0.98); }
        .book-cover {
            height: 200px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 60px;
            background: linear-gradient(135deg, var(--primary-green), #2c3e50);
            color: white;
        }
        .book-details { padding: 12px; text-align: center; }
        .book-details h3 { font-size: 15px; color: var(--primary-green); height: 42px; overflow: hidden; }
        .book-details .author { font-size: 12px; color: #7f8c8d; margin-top: 5px; }
        .book-parts-badge {
            position: absolute; top: 8px; right: 8px;
            background: rgba(0,0,0,0.7); color: white;
            font-size: 10px; padding: 2px 8px; border-radius: 10px;
        }
        .book-card { position: relative; }
        
        /* ===== CONTINUE READING ===== */
        .continue-card {
            background: #f5ece3;
            border: 2px solid var(--primary-green);
            border-radius: var(--radius);
            padding: 15px 20px;
            margin-bottom: 20px;
            display: none;
            align-items: center;
            justify-content: space-between;
            cursor: pointer;
            grid-column: 1/-1;
        }
        .continue-card .btn {
            background: var(--primary-green);
            color: white;
            padding: 8px 20px;
            border-radius: 30px;
            font-size: 13px;
        }
        
        /* ===== BOTTOM NAV ===== */
        .bottom-nav {
            position: fixed;
            bottom: 0;
            width: 100%;
            background: white;
            display: flex;
            justify-content: space-around;
            padding: 10px 0;
            border-top: 1px solid var(--border);
            z-index: 1000;
        }
        .nav-link {
            text-align: center;
            color: #7f8c8d;
            font-size: 12px;
            flex: 1;
            background: none;
            border: none;
        }
        .nav-link i { font-size: 22px; display: block; margin-bottom: 2px; }
        .nav-link.active { color: var(--primary-green); font-weight: bold; }
        
        /* ===== READER ===== */
        #readerView {
            display: none;
            flex-direction: column;
            height: 100%;
            position: fixed;
            inset: 0;
            background: var(--bg);
            z-index: 2000;
        }
        #readerView.show { display: flex; }
        
        .reader-header {
            background: white;
            padding: 12px 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            min-height: 55px;
        }
        .reader-header .back-btn {
            background: none;
            border: none;
            font-size: 20px;
            cursor: pointer;
        }
        .reader-header .title { font-size: 16px; font-weight: bold; flex: 1; text-align: center; }
        .reader-header .actions i { cursor: pointer; padding: 0 8px; }
        
        .reader-content {
            flex: 1;
            overflow-y: auto;
            padding: 15px;
            padding-bottom: 90px;
        }
        
        .reader-page-card {
            background: white;
            padding: 25px 20px;
            border-radius: var(--radius);
            border: 1px solid var(--border);
            min-height: 50vh;
        }
        .head-badge {
            display: inline-block;
            background: #f5ece3;
            padding: 6px 20px;
            border-radius: 50px;
            font-size: 13px;
            margin-bottom: 15px;
        }
        .ar-content {
            font-family: var(--font-ar);
            font-size: 24px;
            direction: rtl;
            line-height: 2.2;
            text-align: right;
            color: #1a5f7a;
        }
        .ml-content { font-size: 18px; line-height: 2.1; margin-top: 15px; }
        .en-content {
            font-size: 16px;
            font-style: italic;
            color: #7f8c8d;
            border-top: 1px dashed var(--border);
            padding-top: 15px;
            margin-top: 15px;
        }
        
        .word-token {
            cursor: pointer;
            transition: 0.15s;
            padding: 0 2px;
            border-radius: 4px;
            display: inline-block;
        }
        .word-hl {
            background: #facc15 !important;
            color: #000 !important;
            font-weight: bold;
            border-radius: 4px;
        }
        
        .reader-pagination {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            margin-top: 15px;
            background: white;
            border-radius: 50px;
            border: 1px solid var(--border);
        }
        .reader-pagination button {
            padding: 8px 18px;
            border-radius: 30px;
            background: var(--bg);
            border: 1px solid var(--border);
            font-weight: bold;
        }
        .page-num { font-weight: bold; color: var(--primary-green); font-size: 15px; }
        
        /* ===== AUDIO ===== */
        .audio-player {
            background: white;
            padding: 25px;
            border-radius: var(--radius);
            border: 1px solid var(--border);
            text-align: center;
            margin-top: 20px;
        }
        .audio-btn {
            background: var(--primary-green);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 50px;
            font-size: 16px;
            cursor: pointer;
        }
        .audio-controls {
            display: flex;
            justify-content: center;
            gap: 20px;
            align-items: center;
            margin: 15px 0;
        }
        .audio-progress {
            width: 100%;
            height: 5px;
            background: var(--border);
            border-radius: 3px;
        }
        .audio-progress .bar {
            height: 100%;
            background: var(--primary-green);
            border-radius: 3px;
            width: 0%;
            transition: width 0.1s;
        }
        
        /* ===== LOADING ===== */
        .loading { text-align: center; padding: 40px; color: #7f8c8d; }
        .loading .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid var(--primary-green);
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        /* ===== SWIPE ===== */
        .swipe-area {
            position: absolute;
            top: 0;
            bottom: 0;
            width: 30%;
            z-index: 5;
            cursor: pointer;
        }
        .swipe-left { left: 0; }
        .swipe-right { right: 0; }
        .reader-page-card { position: relative; }
        
        @media (max-width: 600px) {
            .book-grid { grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); }
        }
    </style>
</head>
<body>

<!-- ===== HOME VIEW ===== -->
<div id="homeView">
    <header class="header">
        <div class="top-bar">
            <div class="title"><i class="fas fa-layer-group"></i> Adventure Library</div>
            <div class="actions">
                <i class="fas fa-search" onclick="toggleSearch()"></i>
                <i class="fas fa-sync-alt" onclick="loadBooks()"></i>
            </div>
        </div>
        <div class="search-bar" id="searchBar">
            <input type="text" id="searchInput" placeholder="🔍 പുസ്തകങ്ങൾ തിരയുക..." oninput="searchBooks(this.value)">
        </div>
        <div class="tabs">
            <div class="tab-item active" onclick="filterBooks('all')">All</div>
            <div class="tab-item" onclick="filterBooks('categories')">Categories</div>
            <div class="tab-item" onclick="filterBooks('authors')">Authors</div>
        </div>
    </header>
    
    <div class="container">
        <div class="continue-card" id="continueCard" onclick="continueReading()">
            <div>
                <h4 style="color:var(--primary-green)"><i class="fas fa-book-open"></i> Continue Reading</h4>
                <p id="continueInfo" style="font-size:12px;color:#7f8c8d;">Loading...</p>
            </div>
            <div class="btn"><i class="fas fa-play"></i> Resume</div>
        </div>
        <div id="loadingIndicator" class="loading"><div class="spinner"></div><p>📚 ലൈബ്രറി ലോഡ് ചെയ്യുന്നു...</p></div>
        <div class="book-grid" id="bookGrid"></div>
    </div>
    
    <nav class="bottom-nav">
        <button class="nav-link active" onclick="goHome()"><i class="fas fa-home"></i>Home</button>
        <button class="nav-link" onclick="processAllBooks()"><i class="fas fa-music"></i>Generate Audio</button>
        <button class="nav-link" onclick="alert('Settings coming soon!')"><i class="fas fa-sliders-h"></i>Settings</button>
    </nav>
</div>

<!-- ===== READER VIEW ===== -->
<div id="readerView">
    <header class="reader-header">
        <button class="back-btn" onclick="closeReader()"><i class="fas fa-arrow-left"></i></button>
        <span class="title" id="readerTitle">Loading...</span>
        <div class="actions">
            <i class="fas fa-bookmark" id="readerBookmark" onclick="toggleBookmark()"></i>
            <i class="fas fa-list-ol" onclick="openTOC()"></i>
            <i class="fas fa-music" onclick="generateAudioForPage()" title="Generate Audio"></i>
        </div>
    </header>
    
    <div class="reader-content" id="readerContent">
        <div class="reader-page-card" id="readerPageCard">
            <div class="swipe-area swipe-left" onclick="changePage(-1)"></div>
            <div class="swipe-area swipe-right" onclick="changePage(1)"></div>
            <div id="pageContent"></div>
        </div>
        <div class="reader-pagination">
            <button onclick="changePage(-1)"><i class="fas fa-chevron-left"></i> Prev</button>
            <span class="page-num" id="pageNum">0 / 0</span>
            <button onclick="changePage(1)">Next <i class="fas fa-chevron-right"></i></button>
        </div>
        
        <!-- Audio Player -->
        <div class="audio-player" id="audioPlayer" style="display:none;">
            <div><i class="fas fa-headphones" style="font-size:30px;color:var(--primary-green);"></i></div>
            <div id="audioStatus" style="margin:10px 0;">Ready</div>
            <div class="audio-controls">
                <button class="audio-btn" onclick="playAudio()"><i class="fas fa-play"></i> Play</button>
                <button class="audio-btn" onclick="stopAudio()"><i class="fas fa-stop"></i> Stop</button>
            </div>
            <div class="audio-progress"><div class="bar" id="audioProgressBar"></div></div>
            <div style="margin-top:10px;font-size:12px;color:#7f8c8d;" id="wordHighlight">Click Play to start</div>
        </div>
    </div>
</div>

<script>
// ================================================================
// STATE
// ================================================================
const STATE = {
    books: [],
    currentBook: null,
    currentPage: 0,
    bookData: [],
    totalPages: 0,
    bookmarks: [],
    isReaderOpen: false,
    currentAudio: null,
    srtData: [],
    currentWordIndex: 0,
    audioInterval: null
};

// ================================================================
// LOAD BOOKS
// ================================================================
async function loadBooks() {
    const indicator = document.getElementById('loadingIndicator');
    indicator.style.display = 'block';
    
    try {
        const response = await fetch('/api/books');
        const books = await response.json();
        STATE.books = books;
        renderBooks(books);
        updateContinueReading();
    } catch (error) {
        console.error('Error:', error);
    }
    
    indicator.style.display = 'none';
}

function renderBooks(books) {
    const grid = document.getElementById('bookGrid');
    if (!books || books.length === 0) {
        grid.innerHTML = '<p style="grid-column:1/-1;text-align:center;padding:40px;color:#7f8c8d;">📚 No books found</p>';
        return;
    }
    
    grid.innerHTML = books.map(book => `
        <div class="book-card" onclick="openBook('${book.id}')">
            <span class="book-parts-badge">${book.parts || 0} Parts</span>
            <div class="book-cover">${book.cover || '📖'}</div>
            <div class="book-details">
                <h3>${book.titleMl || book.title}</h3>
                <div class="author">${book.author || 'Unknown'}</div>
            </div>
        </div>
    `).join('');
}

// ================================================================
// FILTER & SEARCH
// ================================================================
function filterBooks(type) {
    document.querySelectorAll('.tab-item').forEach(el => el.classList.remove('active'));
    event.target.classList.add('active');
    
    if (type === 'all') {
        renderBooks(STATE.books);
    } else if (type === 'categories') {
        const groups = {};
        STATE.books.forEach(b => {
            const cat = b.lang || 'General';
            if (!groups[cat]) groups[cat] = [];
            groups[cat].push(b);
        });
        renderGroupedBooks(groups);
    } else if (type === 'authors') {
        const groups = {};
        STATE.books.forEach(b => {
            const auth = b.author || 'Unknown';
            if (!groups[auth]) groups[auth] = [];
            groups[auth].push(b);
        });
        renderGroupedBooks(groups);
    }
}

function renderGroupedBooks(groups) {
    const grid = document.getElementById('bookGrid');
    let html = '';
    for (const [key, books] of Object.entries(groups)) {
        html += `<div style="grid-column:1/-1;padding:10px;background:#1b4d3e;color:white;border-radius:8px;margin:5px 0;">
            <i class="fas fa-folder-open"></i> ${key} (${books.length})
        </div>`;
        books.forEach(book => {
            html += `
                <div class="book-card" onclick="openBook('${book.id}')">
                    <div class="book-cover">${book.cover || '📖'}</div>
                    <div class="book-details">
                        <h3>${book.titleMl || book.title}</h3>
                        <div class="author">${book.author}</div>
                    </div>
                </div>
            `;
        });
    }
    grid.innerHTML = html;
}

function searchBooks(query) {
    if (!query.trim()) {
        renderBooks(STATE.books);
        return;
    }
    const filtered = STATE.books.filter(b => 
        (b.title || '').toLowerCase().includes(query.toLowerCase()) ||
        (b.titleMl || '').includes(query)
    );
    renderBooks(filtered);
}

function toggleSearch() {
    document.getElementById('searchBar').classList.toggle('show');
}

// ================================================================
// CONTINUE READING
// ================================================================
function updateContinueReading() {
    const card = document.getElementById('continueCard');
    const info = document.getElementById('continueInfo');
    
    const lastBookId = localStorage.getItem('last_book_id');
    const lastPage = localStorage.getItem('last_page');
    const lastTitle = localStorage.getItem('last_book_title');
    
    if (lastBookId && lastPage) {
        card.style.display = 'flex';
        info.textContent = `${lastTitle || 'Book'} - Page ${lastPage}`;
    } else {
        card.style.display = 'none';
    }
}

function continueReading() {
    const bookId = localStorage.getItem('last_book_id');
    if (bookId) openBook(bookId);
}

// ================================================================
// OPEN BOOK
// ================================================================
async function openBook(bookId) {
    const book = STATE.books.find(b => b.id === bookId);
    if (!book) return;
    
    STATE.currentBook = book;
    document.getElementById('readerTitle').textContent = book.titleMl || book.title;
    document.getElementById('readerView').classList.add('show');
    document.getElementById('homeView').style.display = 'none';
    STATE.isReaderOpen = true;
    
    try {
        const response = await fetch(`/api/parts/${bookId}`);
        const parts = await response.json();
        STATE.bookData = parts;
        STATE.totalPages = parts.length;
        STATE.currentPage = parseInt(localStorage.getItem(`page_${bookId}`)) || 0;
        if (STATE.currentPage >= STATE.totalPages) STATE.currentPage = 0;
        renderPage();
    } catch (error) {
        alert('Error loading book parts');
    }
}

function renderPage() {
    const data = STATE.bookData;
    if (!data || data.length === 0) return;
    
    const row = data[STATE.currentPage];
    if (!row) return;
    
    let html = `<div class="head-badge">ഭാഗം ${row.part || '?'} - പേജ് ${row.page || '?'}</div>`;
    if (row.ar) html += `<div class="ar-content">${row.ar}</div>`;
    if (row.ml) html += `<div class="ml-content">${highlightWords(row.ml, 'ml')}</div>`;
    if (row.en) html += `<div class="en-content">${row.en}</div>`;
    
    document.getElementById('pageContent').innerHTML = html;
    document.getElementById('pageNum').textContent = `${STATE.currentPage + 1} / ${STATE.totalPages}`;
    
    // Save position
    localStorage.setItem('last_book_id', STATE.currentBook.id);
    localStorage.setItem('last_page', STATE.currentPage + 1);
    localStorage.setItem('last_book_title', STATE.currentBook.titleMl || STATE.currentBook.title);
    
    // Update audio player
    document.getElementById('audioPlayer').style.display = 'block';
    document.getElementById('audioStatus').textContent = '📄 Page loaded. Click Play for audio.';
    document.getElementById('audioProgressBar').style.width = '0%';
    
    // Load SRT if available
    loadSRT(STATE.currentBook.id, STATE.currentPage);
}

function highlightWords(text, lang) {
    if (!text) return '';
    const words = text.split(/(\s+)/);
    return words.map((word, i) => {
        if (word.trim() === '') return word;
        return `<span class="word-token" data-word-index="${i}" data-lang="${lang}">${word}</span>`;
    }).join('');
}

// ================================================================
// PAGE NAVIGATION
// ================================================================
function changePage(delta) {
    const newPage = STATE.currentPage + delta;
    if (newPage < 0 || newPage >= STATE.totalPages) return;
    STATE.currentPage = newPage;
    localStorage.setItem(`page_${STATE.currentBook.id}`, newPage);
    renderPage();
    document.getElementById('readerContent').scrollTop = 0;
}

function closeReader() {
    STATE.isReaderOpen = false;
    document.getElementById('readerView').classList.remove('show');
    document.getElementById('homeView').style.display = 'flex';
    if (STATE.audioInterval) clearInterval(STATE.audioInterval);
    if (STATE.currentAudio) {
        STATE.currentAudio.pause();
        STATE.currentAudio = null;
    }
}

function goHome() {
    if (STATE.isReaderOpen) {
        closeReader();
    }
}

// ================================================================
// BOOKMARKS
// ================================================================
function toggleBookmark() {
    const key = `${STATE.currentBook.id}_bookmarks`;
    let bookmarks = JSON.parse(localStorage.getItem(key) || '[]');
    const idx = bookmarks.indexOf(STATE.currentPage);
    if (idx > -1) bookmarks.splice(idx, 1);
    else bookmarks.push(STATE.currentPage);
    localStorage.setItem(key, JSON.stringify(bookmarks));
    document.getElementById('readerBookmark').style.color = bookmarks.includes(STATE.currentPage) ? '#f59e0b' : '';
}

// ================================================================
// AUDIO - TTS Generation & Playback
// ================================================================
async function generateAudioForPage() {
    const row = STATE.bookData[STATE.currentPage];
    const text = row.ml_pure || row.ml || '';
    
    if (!text) {
        alert('No text to convert to audio');
        return;
    }
    
    document.getElementById('audioStatus').textContent = '🎵 Generating audio...';
    
    try {
        const response = await fetch('/api/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                book_id: STATE.currentBook.id,
                page_num: STATE.currentPage,
                text: text
            })
        });
        
        const result = await response.json();
        if (result.success) {
            document.getElementById('audioStatus').textContent = '✅ Audio ready! Click Play.';
            // Load SRT
            loadSRT(STATE.currentBook.id, STATE.currentPage);
        } else {
            alert('Error generating audio');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function loadSRT(bookId, pageNum) {
    try {
        const response = await fetch(`/api/srt/${bookId}_page_${pageNum}.srt`);
        if (response.ok) {
            const srtText = await response.text();
            STATE.srtData = parseSRT(srtText);
            document.getElementById('audioStatus').textContent = '✅ Audio + Subtitles ready!';
        }
    } catch (e) {
        // No SRT yet
    }
}

function parseSRT(srtText) {
    const lines = srtText.split('\n');
    const words = [];
    let current = {};
    
    for (const line of lines) {
        if (line.includes('-->')) {
            const [start, end] = line.split(' --> ');
            current.start = parseTime(start);
            current.end = parseTime(end);
        } else if (line.trim() && !line.match(/^\d+$/)) {
            current.text = line.trim();
            if (current.start !== undefined) {
                words.push({...current});
                current = {};
            }
        }
    }
    return words;
}

function parseTime(timeStr) {
    const parts = timeStr.split(':');
    const seconds = parts[2].split(',');
    return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseInt(seconds[0]) + parseInt(seconds[1]) / 1000;
}

function playAudio() {
    const audioUrl = `/api/audio/${STATE.currentBook.id}_page_${STATE.currentPage}.mp3`;
    
    if (STATE.currentAudio) {
        STATE.currentAudio.pause();
        STATE.currentAudio = null;
    }
    
    STATE.currentAudio = new Audio(audioUrl);
    STATE.currentAudio.play();
    document.getElementById('audioStatus').textContent = '▶️ Playing...';
    
    if (STATE.audioInterval) clearInterval(STATE.audioInterval);
    
    STATE.audioInterval = setInterval(() => {
        if (STATE.currentAudio && !STATE.currentAudio.paused) {
            const progress = (STATE.currentAudio.currentTime / STATE.currentAudio.duration) * 100;
            document.getElementById('audioProgressBar').style.width = progress + '%';
            highlightWordByTime(STATE.currentAudio.currentTime);
        }
    }, 100);
    
    STATE.currentAudio.onended = () => {
        document.getElementById('audioStatus').textContent = '✅ Audio finished';
        document.getElementById('audioProgressBar').style.width = '100%';
        if (STATE.audioInterval) clearInterval(STATE.audioInterval);
    };
}

function stopAudio() {
    if (STATE.currentAudio) {
        STATE.currentAudio.pause();
        STATE.currentAudio.currentTime = 0;
        STATE.currentAudio = null;
    }
    if (STATE.audioInterval) clearInterval(STATE.audioInterval);
    document.getElementById('audioStatus').textContent = '⏹️ Stopped';
    document.getElementById('audioProgressBar').style.width = '0%';
    clearHighlights();
}

function highlightWordByTime(time) {
    const words = document.querySelectorAll('.word-token');
    clearHighlights();
    
    for (let i = STATE.srtData.length - 1; i >= 0; i--) {
        if (time >= STATE.srtData[i].start && time <= STATE.srtData[i].end) {
            if (words[i]) {
                words[i].classList.add('word-hl');
                document.getElementById('wordHighlight').textContent = '🔊 ' + STATE.srtData[i].text;
            }
            break;
        }
    }
}

function clearHighlights() {
    document.querySelectorAll('.word-token').forEach(el => el.classList.remove('word-hl'));
}

// ================================================================
// PROCESS ALL BOOKS - Generate Audio for Everything
// ================================================================
async function processAllBooks() {
    if (!confirm('Generate audio for ALL pages of ALL books? This may take time.')) return;
    
    for (const book of STATE.books) {
        document.getElementById('audioStatus').textContent = `Processing ${book.titleMl}...`;
        try {
            const response = await fetch(`/api/process_book/${book.id}`, {
                method: 'POST'
            });
            const result = await response.json();
            console.log(result);
        } catch (e) {
            console.error('Error processing:', e);
        }
    }
    document.getElementById('audioStatus').textContent = '✅ All books processed!';
}

// ================================================================
// TOC
// ================================================================
function openTOC() {
    const data = STATE.bookData;
    if (!data) return;
    
    let html = '<div style="padding:15px;"><h3>📑 Contents</h3><hr>';
    data.forEach((row, i) => {
        const isHead = row.is_head || false;
        const prefix = isHead ? '📌 ' : '  ';
        const style = isHead ? 'font-weight:bold;color:#1b4d3e;' : '';
        html += `<div onclick="jumpToPage(${i})" style="padding:8px 0;border-bottom:1px solid #eee;cursor:pointer;${style}">
            ${prefix} ${row.heading || row.ml_pure?.substring(0, 30) || 'Page ' + (i+1)}
        </div>`;
    });
    html += '</div>';
    
    const modal = document.createElement('div');
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:flex-end;';
    modal.innerHTML = `
        <div style="background:white;width:100%;max-height:80vh;border-radius:20px 20px 0 0;overflow-y:auto;padding:20px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                <h3>📑 Index</h3>
                <button onclick="this.closest('div[style]').remove()" style="background:none;border:none;font-size:24px;">✕</button>
            </div>
            ${html}
        </div>
    `;
    document.body.appendChild(modal);
    modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
}

function jumpToPage(index) {
    STATE.currentPage = index;
    renderPage();
    document.querySelector('[style*="position:fixed;inset:0;background:rgba(0,0,0,0.5)"]')?.remove();
}

// ================================================================
// KEYBOARD SHORTCUTS
// ================================================================
document.addEventListener('keydown', (e) => {
    if (STATE.isReaderOpen) {
        if (e.key === 'ArrowLeft') changePage(-1);
        if (e.key === 'ArrowRight') changePage(1);
        if (e.key === 'Escape') closeReader();
        if (e.key === ' ') { e.preventDefault(); playAudio(); }
    }
});

// ================================================================
// INIT
// ================================================================
document.addEventListener('DOMContentLoaded', loadBooks);
</script>
</body>
</html>
'''

# ================================================================
# FLASK ROUTES
# ================================================================

@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/books')
def get_books():
    """Get all books"""
    books = load_books()
    return jsonify(books)

@app.route('/api/parts/<book_id>')
def get_parts(book_id):
    """Get all parts of a book"""
    parts = load_book_parts(book_id)
    return jsonify(parts)

@app.route('/api/tts', methods=['POST'])
def generate_audio():
    """Generate MP3 + SRT for a page"""
    try:
        data = request.json
        book_id = data.get('book_id')
        page_num = data.get('page_num')
        text = data.get('text', '')
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        # Generate MP3
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio_data = loop.run_until_complete(generate_tts(text))
        loop.close()
        
        if not audio_data:
            return jsonify({'error': 'TTS generation failed'}), 500
        
        # Save MP3
        audio_path = AUDIO_DIR / f"{book_id}_page_{page_num}.mp3"
        with open(audio_path, 'wb') as f:
            f.write(audio_data)
        
        # Generate SRT
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        srt_content = loop.run_until_complete(generate_srt(text))
        loop.close()
        
        if srt_content:
            srt_path = SRT_DIR / f"{book_id}_page_{page_num}.srt"
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
        
        return jsonify({
            'success': True,
            'audio_url': f'/api/audio/{book_id}_page_{page_num}.mp3',
            'srt_url': f'/api/srt/{book_id}_page_{page_num}.srt' if srt_content else None
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/audio/<filename>')
def serve_audio(filename):
    """Serve generated MP3"""
    try:
        return send_file(AUDIO_DIR / filename, mimetype='audio/mpeg')
    except:
        return jsonify({'error': 'File not found'}), 404

@app.route('/api/srt/<filename>')
def serve_srt(filename):
    """Serve generated SRT"""
    try:
        return send_file(SRT_DIR / filename, mimetype='text/plain')
    except:
        return jsonify({'error': 'File not found'}), 404

@app.route('/api/process_book/<book_id>', methods=['POST'])
def process_book(book_id):
    """Generate audio for ALL pages of a book"""
    try:
        parts = load_book_parts(book_id)
        if not parts:
            return jsonify({'error': 'Book not found'}), 404
        
        processed = 0
        for i, page in enumerate(parts):
            text = page.get('ml_pure', '')
            if text and len(text) > 10:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                audio_data = loop.run_until_complete(generate_tts(text))
                loop.close()
                
                if audio_data:
                    audio_path = AUDIO_DIR / f"{book_id}_page_{i}.mp3"
                    with open(audio_path, 'wb') as f:
                        f.write(audio_data)
                    
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    srt_content = loop.run_until_complete(generate_srt(text))
                    loop.close()
                    
                    if srt_content:
                        srt_path = SRT_DIR / f"{book_id}_page_{i}.srt"
                        with open(srt_path, 'w', encoding='utf-8') as f:
                            f.write(srt_content)
                    
                    processed += 1
        
        return jsonify({
            'success': True,
            'book_id': book_id,
            'total_pages': len(parts),
            'processed': processed
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ================================================================
# MAIN
# ================================================================

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════╗
    ║   📚 Adventure Digital Library Pro           ║
    ║   🚀 Server running at: http://localhost:5000 ║
    ║   🎙️ Voice: Malayalam - Midhun (Edge TTS)   ║
    ╚══════════════════════════════════════════════╝
    """)
    app.run(debug=True, host='0.0.0.0', port=5000)