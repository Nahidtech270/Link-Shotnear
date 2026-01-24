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
app.secret_key = "premium_key_2025_safe"

# --- ডাটাবেস কানেকশন (সরাসরি কোডে বসানো) ---
MONGO_URI = "mongodb+srv://MoviaXBot4:MoviaXBot4@cluster0.oochesb.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True)
db = client['pro_link_shortener']

# --- কালেকশনস ---
urls_col = db['urls']
settings_col = db['settings']

def get_settings():
    conf = settings_col.find_one()
    if not conf:
        default = {
            "site_name": "Premium Shortener",
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

# --- মোবাইল অপ্টিমাইজড অ্যাডমিন প্যানেল ডিজাইন ---
ADMIN_UI = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <title>Admin - {{ conf.site_name }}</title>
    <style>
        body { background: #f1f5f9; padding-bottom: 80px; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .active-tab { color: #2563eb !important; border-top: 3px solid #2563eb; }
    </style>
</head>
<body>
    <!-- Header -->
    <div class="bg-white p-5 sticky top-0 z-50 border-b flex justify-between items-center shadow-sm">
        <h1 class="text-xl font-black text-slate-800">ADMIN <span class="text-blue-600">PRO</span></h1>
        <a href="/logout" class="bg-red-50 text-red-600 px-3 py-1 rounded-lg text-xs font-bold">LOGOUT</a>
    </div>

    <div class="p-4 max-w-lg mx-auto">
        <!-- Tab 1: STATS -->
        <div id="stats" class="tab-content active space-y-4">
            <div class="grid grid-cols-2 gap-4">
                <div class="bg-white p-6 rounded-3xl shadow-sm border text-center">
                    <p class="text-[10px] font-bold text-slate-400 uppercase">Total Links</p>
                    <h3 class="text-3xl font-black">{{ links|length }}</h3>
                </div>
                <div class="bg-blue-600 p-6 rounded-3xl shadow-lg text-white text-center">
                    <p class="text-[10px] font-bold text-blue-200 uppercase">Total Clicks</p>
                    <h3 class="text-3xl font-black">{{ total_clicks }}</h3>
                </div>
            </div>
            
            <h4 class="text-xs font-bold text-slate-400 uppercase mt-6 mb-2 ml-2">Recent Activities</h4>
            <div class="space-y-3">
                {% for link in links[:10] %}
                <div class="bg-white p-4 rounded-2xl border shadow-sm flex justify-between items-center">
                    <div class="overflow-hidden">
                        <p class="text-sm font-bold text-blue-600">/{{ link.short_code }}</p>
                        <p class="text-[10px] text-slate-400 truncate w-32">{{ link.long_url }}</p>
                    </div>
                    <span class="bg-slate-100 text-[10px] font-black px-3 py-1 rounded-full">{{ link.clicks }}</span>
                </div>
                {% endfor %}
            </div>
        </div>

        <!-- Tab 2: ADS SETTINGS -->
        <div id="ads" class="tab-content space-y-4">
            <form action="/admin/update" method="POST" class="space-y-4">
                <div class="bg-white p-6 rounded-[30px] shadow-sm border space-y-5">
                    <h4 class="font-bold text-lg border-b pb-2">Website Settings</h4>
                    <div><label class="text-[10px] font-bold text-slate-400 uppercase">Site Name</label>
                    <input name="site_name" value="{{ conf.site_name }}" class="w-full p-3 bg-slate-50 rounded-xl mt-1 border"></div>
                    <div><label class="text-[10px] font-bold text-slate-400 uppercase">Timer (Seconds)</label>
                    <input type="number" name="timer" value="{{ conf.timer }}" class="w-full p-3 bg-slate-50 rounded-xl mt-1 border"></div>
                </div>

                <div class="bg-white p-6 rounded-[30px] shadow-sm border space-y-5">
                    <h4 class="font-bold text-lg text-emerald-600 border-b pb-2">Monetization (Ads)</h4>
                    <div><label class="text-[10px] font-bold text-slate-400 uppercase">Popunder Script</label>
                    <textarea name="popunder" class="w-full h-24 p-3 bg-slate-50 rounded-xl mt-1 border font-mono text-[10px]">{{ conf.popunder }}</textarea></div>
                    
                    <div><label class="text-[10px] font-bold text-slate-400 uppercase">Social Bar Script</label>
                    <textarea name="social_bar" class="w-full h-24 p-3 bg-slate-50 rounded-xl mt-1 border font-mono text-[10px]">{{ conf.social_bar }}</textarea></div>

                    <div><label class="text-[10px] font-bold text-slate-400 uppercase">Banner Ad (HTML)</label>
                    <textarea name="banner" class="w-full h-24 p-3 bg-slate-50 rounded-xl mt-1 border font-mono text-[10px]">{{ conf.banner }}</textarea></div>

                    <div><label class="text-[10px] font-bold text-slate-400 uppercase">Direct Link URL</label>
                    <input name="direct_link" value="{{ conf.direct_link }}" class="w-full p-3 bg-blue-50 border border-blue-100 rounded-xl mt-1 text-blue-600 font-bold" placeholder="Adsterra Direct Link"></div>
                    
                    <button class="w-full bg-slate-900 text-white p-5 rounded-2xl font-black uppercase tracking-widest shadow-xl">Update Settings</button>
                </div>
            </form>
        </div>

        <!-- Tab 3: DEVELOPER API -->
        <div id="api" class="tab-content space-y-4">
            <div class="bg-white p-6 rounded-[30px] shadow-sm border text-center">
                <h4 class="font-bold text-lg mb-4">Developer API Access</h4>
                <p class="text-[10px] font-bold text-slate-400 uppercase mb-2">Your Professional API Key</p>
                <div class="bg-slate-100 p-4 rounded-2xl font-mono text-xs break-all border-dashed border-2 border-slate-300 mb-6">
                    {{ conf.api_key }}
                </div>
                <div class="text-left bg-blue-50 p-4 rounded-2xl border border-blue-100">
                    <p class="text-[10px] font-bold text-blue-600 uppercase mb-2">Endpoint Example:</p>
                    <code class="text-[9px] block text-slate-700">/api/shorten?api_key={{ conf.api_key }}&url=GOOGLE.COM</code>
                </div>
            </div>
        </div>
    </div>

    <!-- Mobile Bottom Navigation -->
    <div class="fixed bottom-0 left-0 right-0 bg-white border-t flex justify-around p-3 pb-6 shadow-[0_-5px_15px_rgba(0,0,0,0.05)] z-50">
        <button onclick="showTab('stats')" id="nav-stats" class="flex flex-col items-center gap-1 active-tab text-slate-400 transition-all">
            <span class="text-xl">📊</span><span class="text-[10px] font-black uppercase">Stats</span>
        </button>
        <button onclick="showTab('ads')" id="nav-ads" class="flex flex-col items-center gap-1 text-slate-400 transition-all">
            <span class="text-xl">💰</span><span class="text-[10px] font-black uppercase">Ads</span>
        </button>
        <button onclick="showTab('api')" id="nav-api" class="flex flex-col items-center gap-1 text-slate-400 transition-all">
            <span class="text-xl">🔑</span><span class="text-[10px] font-black uppercase">API</span>
        </button>
    </div>

    <script>
        function showTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.fixed button').forEach(b => b.classList.remove('active-tab'));
            document.getElementById(tabId).classList.add('active');
            document.getElementById('nav-' + tabId).classList.add('active-tab');
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
        <h1 class="text-4xl font-black mb-8 italic">{{ site_name }}</h1>
        <form action="/shorten" method="POST" class="w-full max-w-md bg-white/10 p-2 rounded-full border border-white/20 flex shadow-2xl">
            <input name="url" type="url" placeholder="Paste link here..." class="bg-transparent flex-1 p-4 outline-none font-bold text-sm" required>
            <button class="bg-blue-600 px-8 rounded-full font-black uppercase text-xs">Shorten</button>
        </form>
    </body></html>""", site_name=conf['site_name'])

@app.route('/shorten', methods=['POST'])
def web_shorten():
    long_url = request.form.get('url')
    sc = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    urls_col.insert_one({"long_url": long_url, "short_code": sc, "clicks": 0, "created_at": datetime.now()})
    return f"<h3>Short URL: {request.host_url}{sc}</h3><a href='/'>Back</a>"

@app.route('/admin')
def admin():
    if not session.get('logged_in'): return redirect('/login')
    conf = get_settings()
    links = list(urls_col.find().sort("_id", -1))
    total_clicks = sum(l.get('clicks', 0) for l in links)
    return render_template_string(ADMIN_UI, conf=conf, links=links, total_clicks=total_clicks)

@app.post('/admin/update')
def admin_update():
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
            <h2 class="text-xl font-black mb-4">Link is Loading...</h2>
            <div id="timer" class="text-7xl font-black text-blue-600 mb-8">{{ conf.timer }}</div>
            <button id="btn" class="hidden w-full bg-blue-600 text-white py-5 rounded-3xl font-black text-xl shadow-xl hover:scale-105 transition">GET LINK</button>
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

# Developer API
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
