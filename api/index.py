import os
import random
import string
import json
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = "link_shortener_pro_2025"

# --- ডাটাবেস কানেকশন (সরাসরি কোডে) ---
MONGO_URI = "mongodb+srv://MoviaXBot4:MoviaXBot4@cluster0.oochesb.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True)
db = client['pro_shortener_db']

# কালেকশনস
urls_col = db['urls']
settings_col = db['settings']

def get_settings():
    conf = settings_col.find_one()
    if not conf:
        default = {
            "site_name": "Premium Link Shortener",
            "admin_password": generate_password_hash("admin123"),
            "api_key": "sk_" + ''.join(random.choices(string.ascii_letters + string.digits, k=15)),
            "timer": 10,
            "popunder": "", 
            "social_bar": "", 
            "banner": "", 
            "direct_link": ""
        }
        settings_col.insert_one(default)
        return default
    return conf

# --- মোবাইল অপ্টিমাইজড অ্যাডমিন প্যানেল (HTML) ---
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <title>Admin Panel</title>
    <style>
        body { background: #f3f4f6; padding-bottom: 80px; font-family: sans-serif; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .active-nav { color: #2563eb !important; border-top: 4px solid #2563eb; }
    </style>
</head>
<body>
    <div class="bg-white p-4 sticky top-0 z-50 border-b flex justify-between items-center shadow-sm">
        <h1 class="text-xl font-black text-slate-800">PRO<span class="text-blue-600">SHORT</span></h1>
        <a href="/logout" class="bg-red-50 text-red-600 px-4 py-1 rounded-lg text-xs font-bold">LOGOUT</a>
    </div>

    <div class="p-4 max-w-md mx-auto">
        <!-- STATS TAB -->
        <div id="stats" class="tab-content active">
            <div class="grid grid-cols-2 gap-4 mb-6">
                <div class="bg-white p-6 rounded-3xl border shadow-sm text-center">
                    <p class="text-[10px] font-bold text-slate-400 uppercase">Total Links</p>
                    <h3 class="text-3xl font-black">{{ links|length }}</h3>
                </div>
                <div class="bg-blue-600 p-6 rounded-3xl shadow-lg text-white text-center">
                    <p class="text-[10px] font-bold text-blue-200 uppercase">Total Clicks</p>
                    <h3 class="text-3xl font-black">{{ total_clicks }}</h3>
                </div>
            </div>
            <h4 class="text-xs font-bold text-slate-400 uppercase mb-3 ml-1">Recent Clicks</h4>
            <div class="space-y-3">
                {% for link in links[:15] %}
                <div class="bg-white p-4 rounded-2xl border flex justify-between items-center shadow-sm">
                    <div class="overflow-hidden">
                        <p class="text-sm font-bold text-blue-600">/{{ link.short_code }}</p>
                        <p class="text-[10px] text-slate-400 truncate w-40">{{ link.long_url }}</p>
                    </div>
                    <div class="bg-slate-100 px-3 py-1 rounded-full text-xs font-black">{{ link.clicks }}</div>
                </div>
                {% endfor %}
            </div>
        </div>

        <!-- ADS TAB -->
        <div id="ads" class="tab-content">
            <form action="/admin/update" method="POST" class="space-y-4">
                <div class="bg-white p-6 rounded-[30px] border shadow-sm space-y-4">
                    <h3 class="font-bold text-lg border-b pb-2">Site Settings</h3>
                    <input name="site_name" value="{{ conf.site_name }}" class="w-full p-3 bg-slate-50 border rounded-xl text-sm" placeholder="Site Name">
                    <input type="number" name="timer" value="{{ conf.timer }}" class="w-full p-3 bg-slate-50 border rounded-xl text-sm" placeholder="Timer (Seconds)">
                </div>

                <div class="bg-white p-6 rounded-[30px] border shadow-sm space-y-4">
                    <h3 class="font-bold text-lg text-emerald-600 border-b pb-2">Ad Management</h3>
                    <div>
                        <label class="text-[10px] font-bold text-slate-400 uppercase">Popunder Script</label>
                        <textarea name="popunder" class="w-full h-24 p-3 bg-slate-50 border rounded-xl mt-1 text-[10px] font-mono">{{ conf.popunder }}</textarea>
                    </div>
                    <div>
                        <label class="text-[10px] font-bold text-slate-400 uppercase">Social Bar Script</label>
                        <textarea name="social_bar" class="w-full h-24 p-3 bg-slate-50 border rounded-xl mt-1 text-[10px] font-mono">{{ conf.social_bar }}</textarea>
                    </div>
                    <div>
                        <label class="text-[10px] font-bold text-slate-400 uppercase">Banner Ad (HTML)</label>
                        <textarea name="banner" class="w-full h-24 p-3 bg-slate-50 border rounded-xl mt-1 text-[10px] font-mono">{{ conf.banner }}</textarea>
                    </div>
                    <div>
                        <label class="text-[10px] font-bold text-slate-400 uppercase">Direct Link Ad URL</label>
                        <input name="direct_link" value="{{ conf.direct_link }}" class="w-full p-3 bg-blue-50 border border-blue-200 rounded-xl mt-1 text-sm font-bold text-blue-600" placeholder="https://ad-link.com">
                    </div>
                    <button class="w-full bg-slate-900 text-white p-4 rounded-2xl font-black uppercase tracking-widest shadow-xl">Save Settings</button>
                </div>
            </form>
        </div>

        <!-- API TAB -->
        <div id="api" class="tab-content">
            <div class="bg-white p-8 rounded-[40px] border shadow-sm text-center">
                <h3 class="font-bold text-xl mb-4">Developer API</h3>
                <p class="text-[10px] font-bold text-slate-400 uppercase mb-2">Your Secret API Key</p>
                <div class="bg-slate-100 p-4 rounded-2xl font-mono text-xs break-all border-dashed border-2 border-slate-300 mb-6">
                    {{ conf.api_key }}
                </div>
                <div class="text-left bg-blue-50 p-4 rounded-2xl border border-blue-100">
                    <p class="text-[10px] font-bold text-blue-600 uppercase mb-2">Endpoint URL:</p>
                    <code class="text-[9px] block text-slate-700">/api/shorten?api_key={{ conf.api_key }}&url=YOUR_URL</code>
                </div>
            </div>
        </div>
    </div>

    <!-- Bottom Navigation -->
    <div class="fixed bottom-0 left-0 right-0 bg-white border-t flex justify-around p-3 pb-6 shadow-lg z-50">
        <button onclick="showTab('stats')" id="nav-stats" class="flex flex-col items-center gap-1 active-nav text-slate-400">
            <span class="text-xl">📊</span><span class="text-[10px] font-black uppercase">Stats</span>
        </button>
        <button onclick="showTab('ads')" id="nav-ads" class="flex flex-col items-center gap-1 text-slate-400">
            <span class="text-xl">💰</span><span class="text-[10px] font-black uppercase">Ads</span>
        </button>
        <button onclick="showTab('api')" id="nav-api" class="flex flex-col items-center gap-1 text-slate-400">
            <span class="text-xl">🔑</span><span class="text-[10px] font-black uppercase">API</span>
        </button>
    </div>

    <script>
        function showTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.fixed button').forEach(b => b.classList.remove('active-nav'));
            document.getElementById(tabId).classList.add('active');
            document.getElementById('nav-' + tabId).classList.add('active-nav');
        }
    </script>
</body>
</html>
"""

# --- ROUTES ---

@app.route('/')
def home():
    conf = get_settings()
    return render_template_string("""
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-900 text-white flex flex-col items-center justify-center min-h-screen p-6">
        <h1 class="text-4xl font-black mb-8 italic uppercase tracking-tighter">{{ conf.site_name }}</h1>
        <form action="/shorten" method="POST" class="w-full max-w-md bg-white/10 p-2 rounded-full border border-white/20 flex shadow-2xl">
            <input name="url" type="url" placeholder="Paste link here..." class="bg-transparent flex-1 p-4 outline-none font-bold text-sm" required>
            <button class="bg-blue-600 px-8 rounded-full font-black uppercase text-xs">Shorten</button>
        </form>
    </body></html>""", conf=conf)

@app.route('/shorten', methods=['POST'])
def shorten_web():
    long_url = request.form.get('url')
    sc = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    urls_col.insert_one({"long_url": long_url, "short_code": sc, "clicks": 0, "created_at": datetime.now()})
    return f"<h3>Short URL: {request.host_url}{sc}</h3><br><a href='/'>Back</a>"

@app.route('/admin')
def admin():
    if not session.get('logged_in'): return redirect('/login')
    conf = get_settings()
    links = list(urls_col.find().sort("_id", -1))
    total_clicks = sum(l.get('clicks', 0) for l in links)
    return render_template_string(ADMIN_TEMPLATE, conf=conf, links=links, total_clicks=total_clicks)

@app.post('/admin/update')
def update_admin():
    if not session.get('logged_in'): return redirect('/login')
    new_data = {
        "site_name": request.form.get('site_name'),
        "timer": int(request.form.get('timer')),
        "popunder": request.form.get('popunder'),
        "social_bar": request.form.get('social_bar'),
        "banner": request.form.get('banner'),
        "direct_link": request.form.get('direct_link')
    }
    settings_col.update_one({}, {"$set": new_data})
    return redirect('/admin')

@app.route('/<short_code>')
def redirect_handler(short_code):
    link = urls_col.find_one({"short_code": short_code})
    if not link: return "404 - Link Not Found", 404
    conf = get_settings()
    urls_col.update_one({"short_code": short_code}, {"$inc": {"clicks": 1}})
    
    return render_template_string("""
    <html><head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        {{ conf.popunder | safe }} {{ conf.social_bar | safe }}
    </head>
    <body class="bg-slate-50 flex flex-col items-center justify-center min-h-screen p-6">
        <div class="mb-6">{{ conf.banner | safe }}</div>
        <div class="bg-white p-12 rounded-[50px] shadow-2xl text-center max-w-sm w-full border-t-8 border-blue-600">
            <h2 class="text-xl font-black mb-4">Link is Ready!</h2>
            <div id="timer" class="text-7xl font-black text-blue-600 mb-8">{{ conf.timer }}</div>
            <button id="btn" class="hidden w-full bg-blue-600 text-white py-5 rounded-3xl font-black text-xl shadow-xl">GET LINK</button>
        </div>
        <script>
            let t = {{ conf.timer }};
            const countdown = setInterval(() => {
                t--; document.getElementById('timer').innerText = t;
                if(t <= 0) { 
                    clearInterval(countdown); 
                    document.getElementById('timer').style.display = 'none';
                    document.getElementById('btn').classList.remove('hidden');
                }
            }, 1000);
            document.getElementById('btn').onclick = () => {
                if("{{ conf.direct_link }}") window.open("{{ conf.direct_link }}", "_blank");
                window.location.href = "{{ link.long_url }}";
            };
        </script>
    </body></html>""", conf=conf, link=link)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if check_password_hash(get_settings()['admin_password'], request.form.get('password')):
            session['logged_in'] = True
            return redirect('/admin')
    return 'Admin Password: <form method="POST"><input type="password" name="password"><button>Login</button></form>'

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- Developer API ---
@app.route('/api/shorten')
def developer_api():
    key = request.args.get('api_key')
    url = request.args.get('url')
    conf = get_settings()
    if key != conf['api_key']: return jsonify({"error": "Invalid API Key"}), 401
    sc = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    urls_col.insert_one({"long_url": url, "short_code": sc, "clicks": 0, "created_at": datetime.now()})
    return jsonify({"status": "success", "short_url": request.host_url + sc})

def handler(event, context):
    return app(event, context)
