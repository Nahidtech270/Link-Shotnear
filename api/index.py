import os
import random
import string
import json
import requests
from urllib.parse import urlparse
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from collections import Counter

app = Flask(__name__)

# --- কনফিগারেশন ---
app.secret_key = os.environ.get("SECRET_KEY", "pro-secret-key-2025")
MONGO_URI = os.environ.get("MONGO_URI") # Vercel-এ সেট করবেন

# --- ডাটাবেস কানেকশন ---
client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True)
db = client['premium_url_db']
urls_col = db['urls']
settings_col = db['settings']
direct_links_col = db['direct_links']

def get_settings():
    settings = settings_col.find_one()
    if not settings:
        default_settings = {
            "site_name": "Pro Link Shortener",
            "admin_password": generate_password_hash("admin123"),
            "api_key": ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)),
            "steps": 2,
            "timer_seconds": 10,
            "popunder": "", "banner": "", "social_bar": "", "native": "",
            "direct_click_limit": 1,
            "main_theme": "blue"
        }
        settings_col.insert_one(default_settings)
        return default_settings
    return settings

# --- প্রফেশনাল মোবাইল-অপ্টিমাইজড অ্যাডমিন প্যানেল ---
ADMIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <title>Admin Dashboard</title>
    <style>
        body { background: #f8fafc; font-family: sans-serif; padding-bottom: 80px; }
        .glass { background: rgba(255, 255, 255, 0.9); backdrop-filter: blur(10px); }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .active-nav { color: #2563eb !important; }
    </style>
</head>
<body>

    <!-- Header -->
    <div class="sticky top-0 z-40 bg-white border-b p-4 flex justify-between items-center shadow-sm">
        <h1 class="text-xl font-black italic">PRO<span class="text-blue-600">PANEL</span></h1>
        <a href="/logout" class="text-xs font-bold text-red-500 bg-red-50 px-3 py-1 rounded-full">LOGOUT</a>
    </div>

    <div class="p-4 max-w-lg mx-auto">
        
        <!-- Tab 1: OVERVIEW -->
        <div id="overview" class="tab-content active space-y-4">
            <div class="grid grid-cols-2 gap-3">
                <div class="bg-white p-5 rounded-3xl border shadow-sm">
                    <p class="text-[10px] font-bold text-slate-400 uppercase">Total Links</p>
                    <h3 class="text-2xl font-black">{{ total_links }}</h3>
                </div>
                <div class="bg-blue-600 p-5 rounded-3xl shadow-lg text-white">
                    <p class="text-[10px] font-bold text-blue-200 uppercase">Total Clicks</p>
                    <h3 class="text-2xl font-black">{{ total_clicks }}</h3>
                </div>
            </div>
            
            <div class="bg-white p-4 rounded-3xl border shadow-sm">
                <h4 class="text-xs font-bold mb-4 text-slate-500 uppercase">Link Growth</h4>
                <canvas id="linkChart"></canvas>
            </div>

            <div class="space-y-2">
                <h4 class="text-xs font-bold text-slate-400 uppercase ml-2">Recent Activities</h4>
                {% for link in recent_links %}
                <div class="bg-white p-4 rounded-2xl border shadow-sm flex justify-between items-center">
                    <div class="overflow-hidden">
                        <p class="text-sm font-bold truncate w-40 text-blue-600">/{{ link.short_code }}</p>
                        <p class="text-[10px] text-slate-400">{{ link.created_at }}</p>
                    </div>
                    <span class="bg-slate-100 text-[10px] font-black px-2 py-1 rounded-full">{{ link.clicks }} CLICKS</span>
                </div>
                {% endfor %}
            </div>
        </div>

        <!-- Tab 2: SETTINGS (Ads Management) -->
        <div id="settings" class="tab-content space-y-4">
            <form action="/admin/update" method="POST" class="space-y-4">
                <div class="bg-white p-6 rounded-[30px] border shadow-sm space-y-4">
                    <h4 class="font-bold text-lg">General Settings</h4>
                    <input type="text" name="site_name" value="{{ settings.site_name }}" class="w-full p-3 bg-slate-50 rounded-xl border text-sm" placeholder="Site Name">
                    <div class="grid grid-cols-2 gap-2">
                        <input type="number" name="steps" value="{{ settings.steps }}" class="p-3 bg-slate-50 rounded-xl border text-sm" placeholder="Steps">
                        <input type="number" name="timer_seconds" value="{{ settings.timer_seconds }}" class="p-3 bg-slate-50 rounded-xl border text-sm" placeholder="Timer">
                    </div>
                </div>

                <div class="bg-white p-6 rounded-[30px] border shadow-sm space-y-4">
                    <h4 class="font-bold text-lg text-emerald-600">Ad Management</h4>
                    <textarea name="popunder" placeholder="Popunder Ad Script" class="w-full h-24 p-3 bg-slate-50 rounded-xl border text-xs font-mono">{{ settings.popunder }}</textarea>
                    <textarea name="social_bar" placeholder="Social Bar Script" class="w-full h-24 p-3 bg-slate-50 rounded-xl border text-xs font-mono">{{ settings.social_bar }}</textarea>
                    <textarea name="banner" placeholder="Banner Ad Script" class="w-full h-24 p-3 bg-slate-50 rounded-xl border text-xs font-mono">{{ settings.banner }}</textarea>
                    <input type="text" name="direct_link_ad" value="{{ settings.direct_link_ad }}" placeholder="Direct Link URL" class="w-full p-3 bg-blue-50 rounded-xl border border-blue-100 text-sm">
                    <button class="w-full bg-slate-900 text-white p-4 rounded-2xl font-black uppercase tracking-widest shadow-xl">Save All</button>
                </div>
            </form>
        </div>

        <!-- Tab 3: API KEY -->
        <div id="api" class="tab-content space-y-4">
            <div class="bg-white p-6 rounded-[30px] border shadow-sm">
                <h4 class="font-bold text-lg mb-4">Developer API</h4>
                <p class="text-[10px] text-slate-400 font-bold uppercase mb-2">Your API Key</p>
                <div class="bg-slate-100 p-4 rounded-xl break-all font-mono text-xs mb-4 border border-dashed border-slate-300">
                    {{ settings.api_key }}
                </div>
                <p class="text-[10px] text-blue-500 font-bold uppercase">Endpoint:</p>
                <code class="text-[10px] block bg-slate-50 p-2 rounded">/api/shorten?api_key=YOUR_KEY&url=URL</code>
            </div>
        </div>

    </div>

    <!-- Mobile Bottom Navigation -->
    <div class="fixed bottom-0 left-0 right-0 bg-white border-t flex justify-around p-3 pb-6 shadow-lg z-50">
        <button onclick="showTab('overview')" id="nav-overview" class="flex flex-col items-center gap-1 active-nav text-slate-400">
            <span class="text-xl">📊</span><span class="text-[10px] font-bold">Stats</span>
        </button>
        <button onclick="showTab('settings')" id="nav-settings" class="flex flex-col items-center gap-1 text-slate-400">
            <span class="text-xl">⚙️</span><span class="text-[10px] font-bold">Ads</span>
        </button>
        <button onclick="showTab('api')" id="nav-api" class="flex flex-col items-center gap-1 text-slate-400">
            <span class="text-xl">🔑</span><span class="text-[10px] font-bold">API</span>
        </button>
    </div>

    <script>
        function showTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.fixed button').forEach(b => b.classList.remove('active-nav'));
            document.getElementById(tabId).classList.add('active');
            document.getElementById('nav-' + tabId).classList.add('active-nav');
        }

        const ctx = document.getElementById('linkChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: {{ chart_labels | safe }},
                datasets: [{
                    label: 'Links Created',
                    data: {{ chart_data | safe }},
                    borderColor: '#2563eb',
                    tension: 0.4,
                    fill: true,
                    backgroundColor: 'rgba(37, 99, 235, 0.05)'
                }]
            },
            options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
        });
    </script>
</body>
</html>
"""

# --- ROUTES ---

@app.route('/')
def index():
    settings = get_settings()
    return render_template_string("""
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-900 text-white flex flex-col items-center justify-center min-h-screen p-6">
        <h1 class="text-4xl font-black mb-8 italic">{{ site_name }}</h1>
        <form action="/shorten" method="POST" class="w-full max-w-md bg-white/5 p-2 rounded-[30px] border border-white/10 flex">
            <input name="url" type="url" placeholder="Paste link..." class="bg-transparent flex-1 p-4 outline-none font-bold">
            <button class="bg-blue-600 px-6 rounded-[25px] font-black uppercase">Go</button>
        </form>
    </body></html>""", site_name=settings['site_name'])

@app.route('/shorten', methods=['POST'])
def shorten():
    long_url = request.form.get('url')
    sc = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    urls_col.insert_one({"long_url": long_url, "short_code": sc, "clicks": 0, "created_at": datetime.now().strftime("%Y-%m-%d")})
    return f"Link: {request.host_url}{sc} <br><a href='/'>Back</a>"

@app.route('/admin')
def admin():
    if not session.get('logged_in'): return redirect('/login')
    settings = get_settings()
    all_links = list(urls_col.find().sort("_id", -1))
    total_clicks = sum(l.get('clicks', 0) for l in all_links)
    
    # Chart Data
    date_counts = Counter([l['created_at'] for l in all_links])
    sorted_dates = sorted(date_counts.keys())[-7:]
    chart_data = [date_counts[d] for d in sorted_dates]

    return render_template_string(ADMIN_HTML, 
        settings=settings, 
        total_links=len(all_links), 
        total_clicks=total_clicks, 
        recent_links=all_links[:10],
        chart_labels=json.dumps(sorted_dates),
        chart_data=json.dumps(chart_data)
    )

@app.post('/admin/update')
def update_settings():
    if not session.get('logged_in'): return redirect('/login')
    d = {
        "site_name": request.form.get('site_name'),
        "steps": int(request.form.get('steps')),
        "timer_seconds": int(request.form.get('timer_seconds')),
        "popunder": request.form.get('popunder'),
        "social_bar": request.form.get('social_bar'),
        "banner": request.form.get('banner'),
        "direct_link_ad": request.form.get('direct_link_ad')
    }
    settings_col.update_one({}, {"$set": d})
    return redirect('/admin')

@app.route('/<short_code>')
def handle_redirect(short_code):
    link = urls_col.find_one({"short_code": short_code})
    if not link: return "404", 404
    settings = get_settings()
    urls_col.update_one({"short_code": short_code}, {"$inc": {"clicks": 1}})
    
    return render_template_string("""
    <html><head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        {{ settings.popunder | safe }} {{ settings.social_bar | safe }}
    </head>
    <body class="bg-slate-50 flex flex-col items-center justify-center min-h-screen p-6">
        <div class="mb-4">{{ settings.banner | safe }}</div>
        <div class="bg-white p-10 rounded-[40px] shadow-2xl text-center w-full max-w-sm border">
            <h2 class="text-xl font-bold mb-4">Link Processing...</h2>
            <div id="timer" class="text-6xl font-black text-blue-600 mb-6">{{ settings.timer_seconds }}</div>
            <button id="btn" class="hidden w-full bg-blue-600 text-white py-4 rounded-2xl font-black shadow-lg">GET LINK</button>
        </div>
        <script>
            let t = {{ settings.timer_seconds }};
            const countdown = setInterval(() => {
                t--; document.getElementById('timer').innerText = t;
                if(t <= 0) { 
                    clearInterval(countdown); 
                    document.getElementById('timer').style.display = 'none';
                    document.getElementById('btn').classList.remove('hidden');
                }
            }, 1000);
            document.getElementById('btn').onclick = () => {
                if("{{ settings.direct_link_ad }}") window.open("{{ settings.direct_link_ad }}", "_blank");
                window.location.href = "{{ link.long_url }}";
            };
        </script>
    </body></html>""", settings=settings, link=link)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if check_password_hash(get_settings()['admin_password'], request.form.get('password')):
            session['logged_in'] = True
            return redirect('/admin')
    return 'Login: <form method="POST"><input type="password" name="password"><button>Go</button></form>'

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# Developer API
@app.route('/api/shorten')
def api_shorten():
    key = request.args.get('api_key')
    url = request.args.get('url')
    settings = get_settings()
    if key != settings['api_key']: return jsonify({"error": "Invalid API Key"}), 401
    sc = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    urls_col.insert_one({"long_url": url, "short_code": sc, "clicks": 0, "created_at": datetime.now().strftime("%Y-%m-%d")})
    return jsonify({"short_url": request.host_url + sc})
