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
app.secret_key = "premium_pro_shortener_final_version_2025"

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
            "site_name": "Pro Link Shortener",
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

# --- ডিজাইন লেআউট (HTML Strings) ---
# এটি আপনার হোম পেজ, রিডাইরেক্ট পেজ এবং এডমিন প্যানেলকে হ্যান্ডেল করবে।

@app.route('/')
def home():
    conf = get_settings()
    html = f"""
    <!DOCTYPE html><html lang="en"><head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.tailwindcss.com"></script>
    <title>{conf['site_name']}</title></head>
    <body class="bg-slate-900 text-white min-h-screen flex flex-col items-center justify-center p-6 text-center">
        <h1 class="text-5xl font-black mb-4 italic tracking-tighter uppercase">{conf['site_name']}</h1>
        <p class="text-slate-400 mb-10 text-lg uppercase tracking-widest font-bold">Fast & Secure Link Management</p>
        <div class="bg-white/5 p-2 rounded-[35px] border border-white/10 w-full max-w-lg flex shadow-2xl">
            <form action="/shorten" method="POST" class="flex w-full">
                <input name="url" type="url" placeholder="Paste your link here..." class="bg-transparent flex-1 p-5 outline-none font-bold" required>
                <button class="bg-blue-600 text-white px-8 rounded-[28px] font-black uppercase text-sm hover:scale-105 transition">Shorten</button>
            </form>
        </div>
        <div class="mt-12 flex gap-4">
            <a href="/login" class="text-slate-500 font-bold hover:text-white uppercase text-xs">Admin Login</a>
        </div>
    </body></html>
    """
    return render_template_string(html)

@app.route('/shorten', methods=['POST'])
def shorten_web():
    long_url = request.form.get('url')
    sc = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    urls_col.insert_one({"long_url": long_url, "short_code": sc, "clicks": 0, "created_at": datetime.now()})
    html = f"""
    <html><head><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-900 text-white flex flex-col items-center justify-center min-h-screen">
        <div class="bg-slate-800 p-10 rounded-[40px] border border-white/10 text-center shadow-2xl">
            <h2 class="text-2xl font-black mb-6 uppercase text-emerald-400">Success!</h2>
            <input readonly value="{request.host_url}{sc}" class="bg-slate-900 p-4 rounded-xl border border-slate-700 text-center w-full mb-6 font-mono font-bold text-emerald-400">
            <a href="/" class="bg-blue-600 px-10 py-4 rounded-full font-bold uppercase text-sm">Create New Link</a>
        </div>
    </body></html>
    """
    return render_template_string(html)

@app.route('/admin')
def admin_panel():
    if not session.get('logged_in'): return redirect('/login')
    conf = get_settings()
    links = list(urls_col.find().sort("_id", -1))
    total_clicks = sum(l.get('clicks', 0) for l in links)
    
    html = """
    <!DOCTYPE html><html lang="en"><head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #f1f5f9; padding-bottom: 80px; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .active-tab { color: #2563eb !important; border-top: 3px solid #2563eb; }
    </style></head>
    <body>
        <div class="bg-white p-5 sticky top-0 z-50 border-b flex justify-between items-center shadow-sm">
            <h1 class="text-xl font-black text-slate-800 uppercase">Admin <span class="text-blue-600">Pro</span></h1>
            <a href="/logout" class="bg-red-50 text-red-600 px-4 py-1 rounded-lg text-xs font-bold uppercase">Logout</a>
        </div>

        <div class="p-4 max-w-lg mx-auto">
            <!-- TAB: STATS -->
            <div id="stats" class="tab-content active space-y-4">
                <div class="grid grid-cols-2 gap-4">
                    <div class="bg-white p-6 rounded-3xl border shadow-sm text-center">
                        <p class="text-[10px] font-bold text-slate-400 uppercase">Links</p>
                        <h3 class="text-3xl font-black text-slate-800">{{ links|length }}</h3>
                    </div>
                    <div class="bg-blue-600 p-6 rounded-3xl shadow-lg text-white text-center">
                        <p class="text-[10px] font-bold text-blue-200 uppercase">Clicks</p>
                        <h3 class="text-3xl font-black">{{ total_clicks }}</h3>
                    </div>
                </div>
                <h4 class="text-xs font-bold text-slate-400 uppercase mt-6 mb-2 ml-2">Recent Activities</h4>
                <div class="space-y-3">
                    {% for link in links[:20] %}
                    <div class="bg-white p-4 rounded-2xl border shadow-sm flex justify-between items-center">
                        <div class="overflow-hidden">
                            <p class="text-sm font-bold text-blue-600">/{{ link.short_code }}</p>
                            <p class="text-[10px] text-slate-400 truncate w-40">{{ link.long_url }}</p>
                        </div>
                        <span class="bg-slate-100 text-[10px] font-black px-3 py-1 rounded-full">{{ link.clicks }}</span>
                    </div>
                    {% endfor %}
                </div>
            </div>

            <!-- TAB: ADS -->
            <div id="ads" class="tab-content space-y-4">
                <form action="/admin/update" method="POST" class="space-y-4">
                    <div class="bg-white p-6 rounded-[30px] shadow-sm border space-y-4">
                        <h3 class="font-bold border-b pb-2 uppercase text-xs">Site Settings</h3>
                        <input name="site_name" value="{{ conf.site_name }}" class="w-full p-3 bg-slate-50 border rounded-xl text-sm" placeholder="Site Name">
                        <input type="number" name="timer" value="{{ conf.timer }}" class="w-full p-3 bg-slate-50 border rounded-xl text-sm" placeholder="Timer (Seconds)">
                    </div>
                    <div class="bg-white p-6 rounded-[30px] shadow-sm border space-y-4">
                        <h3 class="font-bold text-emerald-600 border-b pb-2 uppercase text-xs">Ad Scripts</h3>
                        <div><label class="text-[10px] font-bold text-slate-400 uppercase">Popunder Script</label>
                        <textarea name="popunder" class="w-full h-24 p-3 bg-slate-50 border rounded-xl mt-1 text-[10px] font-mono">{{ conf.popunder }}</textarea></div>
                        <div><label class="text-[10px] font-bold text-slate-400 uppercase">Social Bar Script</label>
                        <textarea name="social_bar" class="w-full h-24 p-3 bg-slate-50 border rounded-xl mt-1 text-[10px] font-mono">{{ conf.social_bar }}</textarea></div>
                        <div><label class="text-[10px] font-bold text-slate-400 uppercase">Banner Ad (HTML)</label>
                        <textarea name="banner" class="w-full h-24 p-3 bg-slate-50 border rounded-xl mt-1 text-[10px] font-mono">{{ conf.banner }}</textarea></div>
                        <div><label class="text-[10px] font-bold text-slate-400 uppercase">Direct Link URL</label>
                        <input name="direct_link" value="{{ conf.direct_link }}" class="w-full p-3 bg-blue-50 border border-blue-200 rounded-xl mt-1 text-sm font-bold text-blue-600" placeholder="https://"></div>
                        <button class="w-full bg-slate-900 text-white p-5 rounded-2xl font-black uppercase shadow-xl">Update All Settings</button>
                    </div>
                </form>
            </div>

            <!-- TAB: API -->
            <div id="api" class="tab-content space-y-4">
                <div class="bg-white p-8 rounded-[40px] border shadow-sm text-center">
                    <h3 class="font-bold text-xl mb-4">Developer API</h3>
                    <p class="text-[10px] font-bold text-slate-400 uppercase mb-2">Your API Key</p>
                    <div class="bg-slate-100 p-4 rounded-2xl font-mono text-xs break-all border-dashed border-2 border-slate-300 mb-6 text-blue-600 uppercase font-black">
                        {{ conf.api_key }}
                    </div>
                    <div class="text-left bg-blue-50 p-4 rounded-2xl border border-blue-100">
                        <p class="text-[10px] font-bold text-blue-600 uppercase mb-2">Endpoint URL:</p>
                        <code class="text-[9px] block text-slate-700 font-bold">/api/shorten?api_key={{ conf.api_key }}&url=YOUR_LINK</code>
                    </div>
                </div>
            </div>
        </div>

        <!-- Mobile Nav -->
        <div class="fixed bottom-0 left-0 right-0 bg-white border-t flex justify-around p-3 pb-6 shadow-2xl z-50">
            <button onclick="showTab('stats')" id="nav-stats" class="flex flex-col items-center gap-1 active-tab text-slate-400">
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
                document.querySelectorAll('.fixed button').forEach(b => b.classList.remove('active-tab'));
                document.getElementById(tabId).classList.add('active');
                document.getElementById('nav-' + tabId).classList.add('active-tab');
            }
        </script>
    </body></html>
    """
    return render_template_string(html, conf=conf, links=links, total_clicks=total_clicks)

@app.post('/admin/update')
def update_settings():
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
    
    html = """
    <html><head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        {{ conf.popunder | safe }} {{ conf.social_bar | safe }}
    </head>
    <body class="bg-slate-50 flex flex-col items-center justify-center min-h-screen p-6">
        <div class="mb-6 w-full flex justify-center">{{ conf.banner | safe }}</div>
        <div class="bg-white p-12 rounded-[50px] shadow-2xl text-center max-w-sm w-full border-t-8 border-blue-600">
            <h2 class="text-xl font-black mb-4 uppercase tracking-tighter">Your Link is Processing...</h2>
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
    </body></html>
    """
    return render_template_string(html, conf=conf, link=link)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if check_password_hash(get_settings()['admin_password'], request.form.get('password')):
            session['logged_in'] = True
            return redirect('/admin')
    html = """
    <body style="background:#0f172a; display:flex; align-items:center; justify-content:center; height:100vh; font-family:sans-serif;">
        <form method="POST" style="background:white; padding:40px; border-radius:30px; text-align:center; width:300px;">
            <h2 style="font-weight:900; margin-bottom:20px;">ADMIN ACCESS</h2>
            <input type="password" name="password" placeholder="Passkey" style="width:100%; padding:15px; border:1px solid #ddd; border-radius:10px; margin-bottom:15px; box-sizing:border-box;">
            <button style="width:100%; padding:15px; background:#2563eb; color:white; border:none; border-radius:10px; font-weight:900; cursor:pointer;">LOGIN</button>
        </form>
    </body>
    """
    return render_template_string(html)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# Developer API
@app.route('/api/shorten')
def api_shorten_developer():
    key = request.args.get('api_key')
    url = request.args.get('url')
    conf = get_settings()
    if key != conf['api_key']: return jsonify({"error": "Invalid API Key"}), 401
    sc = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    urls_col.insert_one({"long_url": url, "short_code": sc, "clicks": 0, "created_at": datetime.now()})
    return jsonify({"status": "success", "short_url": request.host_url + sc})

def handler(event, context):
    return app(event, context)
