import os
import random
import string
import requests
import json
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from bson.objectid import ObjectId

app = Flask(__name__)
# এটি সেশন সিকিউরিটির জন্য ব্যবহৃত হয়
app.secret_key = os.environ.get("SECRET_KEY", "premium-super-secret-key-2025")

# --- সেশন দীর্ঘস্থায়ী করার সেটিংস ---
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30) # ৩০ দিনের জন্য লগইন সেভ থাকবে
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

# --- ডাটাবেস কানেকশন ---
# MongoDB এর সাথে কানেক্ট করার জন্য URI ব্যবহার করা হয়েছে
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://user:pass@cluster.mongodb.net/test")
client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=5000)
db = client['premium_url_bot']

# কালেকশনগুলো ডিফাইন করা হয়েছে
urls_col = db['urls']           # শর্ট লিংকের ডাটা রাখার জন্য
settings_col = db['settings']   # সাইটের সেটিংস সেভ করার জন্য
channels_col = db['channels']   # পার্টনার চ্যানেলের লিস্ট রাখার জন্য
otp_col = db['otps']           # পাসওয়ার্ড রিসেট OTP এর জন্য
ad_links_col = db['ad_links']   # ডাইরেক্ট অ্যাড লিংকের জন্য
stats_col = db['stats']         # ভিজিটর স্ট্যাটাস বা অ্যানালিটিক্স এর জন্য

# --- টেলিগ্রাম সেটিংস ---
# পাসওয়ার্ড ভুলে গেলে এই বটের মাধ্যমে OTP যাবে
TELEGRAM_BOT_TOKEN = "8229806805:AAEmi3zJcbUrGuCm_Ro2v6KmCACbCBfvRrM"

# কালার থিম ম্যাপ (সাইটের কালার পরিবর্তনের জন্য)
COLOR_MAP = {
    "red": {"text": "text-red-500", "bg": "bg-red-600", "border": "border-red-500", "hover": "hover:bg-red-700", "light_bg": "bg-red-50"},
    "orange": {"text": "text-orange-500", "bg": "bg-orange-600", "border": "border-orange-500", "hover": "hover:bg-orange-700", "light_bg": "bg-orange-50"},
    "yellow": {"text": "text-yellow-500", "bg": "bg-yellow-500", "border": "border-yellow-500", "hover": "hover:bg-yellow-600", "light_bg": "bg-yellow-50"},
    "green": {"text": "text-green-500", "bg": "bg-green-600", "border": "border-green-500", "hover": "hover:bg-green-700", "light_bg": "bg-green-50"},
    "blue": {"text": "text-blue-500", "bg": "bg-blue-600", "border": "border-blue-500", "hover": "hover:bg-blue-700", "light_bg": "bg-blue-50"},
    "sky": {"text": "text-sky-400", "bg": "bg-sky-500", "border": "border-sky-400", "hover": "hover:bg-sky-600", "light_bg": "bg-sky-50"},
    "purple": {"text": "text-purple-500", "bg": "bg-purple-600", "border": "border-purple-500", "hover": "hover:bg-purple-700", "light_bg": "bg-purple-50"},
    "pink": {"text": "text-pink-500", "bg": "bg-pink-600", "border": "border-pink-500", "hover": "hover:bg-pink-700", "light_bg": "bg-pink-50"},
    "slate": {"text": "text-slate-400", "bg": "bg-slate-700", "border": "border-slate-500", "hover": "hover:bg-slate-800", "light_bg": "bg-slate-50"}
}

# ডিফল্ট সেটিংস লোড করা
def get_settings():
    settings = settings_col.find_one()
    if not settings:
        default_settings = {
            "site_name": "Premium URL Shortener",
            "admin_telegram_id": "", 
            "steps": 2,
            "timer_seconds": 10,
            "admin_password": generate_password_hash("admin123"),
            "api_key": ''.join(random.choices(string.ascii_lowercase + string.digits, k=40)),
            "popunder": "", "banner": "", "social_bar": "", "native": "", "cpa_script": "",
            "direct_click_limit": 1,
            "main_theme": "sky", "step_theme": "blue"
        }
        settings_col.insert_one(default_settings)
        return default_settings
    return settings

# লগইন চেক করার ফাংশন
def is_logged_in(): return session.get('logged_in')

# ভিজিটর ট্র্যাকিং ফাংশন (IP, Country, Device ট্র্যাক করে)
def track_click(short_code, ad_link=None):
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip: ip = ip.split(',')[0]
    country = "Unknown"
    try:
        res = requests.get(f"http://ip-api.com/json/{ip}", timeout=2).json()
        if res.get('status') == 'success': country = res.get('country', 'Unknown')
    except: pass
    ua = request.user_agent.string.lower()
    device = "Mobile" if any(m in ua for m in ['android', 'iphone', 'ipad', 'mobile']) else "Desktop/Laptop"
    stats_col.insert_one({
        "short_code": short_code, "ad_link": ad_link, "country": country,
        "device": device, "timestamp": datetime.now(), "date": datetime.now().strftime("%Y-%m-%d")
    })

# পার্টনার চ্যানেলের লিস্ট তৈরি করার HTML
def get_channels_html(theme_color="sky"):
    channels = list(channels_col.find())
    if not channels: return ""
    c = COLOR_MAP.get(theme_color, COLOR_MAP['sky'])
    html = f'<div class="w-full max-w-5xl mx-auto mt-12 mb-8 p-8 rounded-[40px] border-2 border-white/10 glass shadow-2xl text-center"><h3 class="{c["text"]} font-black mb-10 uppercase tracking-widest text-lg">Partner Channels</h3><div class="flex flex-col items-center gap-10">'
    for ch in channels:
        html += f'<a href="{ch["link"]}" target="_blank" class="flex flex-col items-center gap-3 group transition hover:scale-105"><div><p class="text-lg font-black text-gray-100 uppercase italic tracking-wider">{ch.get("name", "Join Channel")}</p></div><img src="{ch["logo"]}" class="w-full max-w-[320px] h-[180px] object-cover border-2 border-white/10 rounded-lg shadow-2xl"></a>'
    return html + '</div></div>'

# --- API সিস্টেম ---
@app.route('/api')
def api_system():
    settings = get_settings()
    api_token = (request.args.get('api') or request.args.get('api_key') or request.args.get('key','')).strip()
    long_url = request.args.get('url')
    alias = request.args.get('alias')
    res_format = request.args.get('format', 'json').lower()
    if api_token != settings['api_key'].strip():
        return jsonify({"status": "error", "message": "Invalid API Token"}) if res_format != 'text' else "Error: Invalid Token"
    if not long_url:
        return jsonify({"status": "error", "message": "Missing URL"}) if res_format != 'text' else "Error: Missing URL"
    sc = alias if alias else ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    # API দিয়ে তৈরি লিংক ডিফল্টভাবে নরমাল (CPA ছাড়া) হবে
    urls_col.insert_one({"long_url": long_url, "short_code": sc, "clicks": 0, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "is_locked": False})
    return request.host_url + sc if res_format == 'text' else jsonify({"status": "success", "shortenedUrl": request.host_url + sc})

# --- হোম পেজ (Premium UI with CPA Checkbox) ---
@app.route('/')
def index():
    settings = get_settings()
    c = COLOR_MAP.get(settings.get('main_theme', 'sky'), COLOR_MAP['sky'])
    return render_template_string(f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <title>{settings['site_name']} - Premium URL Shortener</title>
        <style>
            body {{ background: #0f172a; color: white; background-image: radial-gradient(circle at top right, #1e293b, #0f172a); }}
            .glass, .glass-panel {{ background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(24px); border: 1px solid rgba(255, 255, 255, 0.1); box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); }}
            .glow-btn:hover {{ box-shadow: 0 0 25px var(--theme-color); transform: translateY(-2px); }}
        </style>
    </head>
    <body class="min-h-screen flex flex-col items-center justify-center p-4 text-center">
        
        <div class="max-w-5xl mx-auto w-full mb-12 mt-10">
            <div class="inline-block px-4 py-2 rounded-full glass-panel text-sm font-bold {c['text']} mb-6 tracking-widest uppercase">
                <i class="fas fa-rocket mr-2"></i> Fast & Secure Link Shortening
            </div>
            <h1 class="text-5xl md:text-8xl font-black mb-4 text-transparent bg-clip-text bg-gradient-to-r from-white to-gray-400 italic uppercase">
                {settings['site_name']}
            </h1>
            <p class="text-gray-400 text-lg md:text-2xl font-medium tracking-wide">Monetize your traffic with the highest paying shortener.</p>
        </div>

        <div class="glass-panel p-6 md:p-8 rounded-[40px] w-full max-w-4xl relative z-10 transition-all hover:border-white/20">
            <form action="/shorten" method="POST" class="flex flex-col gap-4">
                <div class="flex flex-col md:flex-row gap-3">
                    <div class="flex-1 flex items-center bg-black/20 rounded-[30px] px-6 py-2">
                        <i class="fas fa-link text-gray-400 text-xl"></i>
                        <input type="url" name="long_url" placeholder="Paste your long link here..." required 
                               class="w-full bg-transparent p-4 outline-none text-white text-lg md:text-xl font-bold placeholder-gray-500">
                    </div>
                    <button type="submit" class="{c['bg']} text-white px-12 py-4 rounded-[30px] font-black text-xl md:text-2xl transition-all glow-btn uppercase tracking-wider" style="--theme-color: #38bdf8;">
                        Shorten <i class="fas fa-arrow-right ml-2"></i>
                    </button>
                </div>
                <!-- OPTIONAL CPA LOCKER CHECKBOX -->
                <div class="flex items-center justify-center gap-3 mt-2">
                    <input type="checkbox" name="is_locked" id="is_locked" class="w-6 h-6 cursor-pointer accent-sky-500 rounded-md">
                    <label for="is_locked" class="text-gray-300 font-bold text-lg cursor-pointer select-none flex items-center gap-2">
                        Enable Premium CPA Locker <i class="fas fa-lock text-yellow-500"></i>
                    </label>
                </div>
            </form>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mt-16 max-w-5xl w-full">
            <div class="glass-panel p-6 rounded-3xl text-center">
                <i class="fas fa-shield-alt text-4xl {c['text']} mb-4"></i>
                <h3 class="text-xl font-bold mb-2">Safe & Secure</h3>
                <p class="text-gray-400 text-sm">Advanced anti-bot protection ensures your links are safe.</p>
            </div>
            <div class="glass-panel p-6 rounded-3xl text-center">
                <i class="fas fa-chart-line text-4xl {c['text']} mb-4"></i>
                <h3 class="text-xl font-bold mb-2">Real-time Stats</h3>
                <p class="text-gray-400 text-sm">Track your audience with our detailed analytics system.</p>
            </div>
            <div class="glass-panel p-6 rounded-3xl text-center">
                <i class="fas fa-coins text-4xl {c['text']} mb-4"></i>
                <h3 class="text-xl font-bold mb-2">Highest Rates</h3>
                <p class="text-gray-400 text-sm">Earn more money with our premium direct ad network.</p>
            </div>
        </div>

        <div class="mt-12 w-full">{get_channels_html(settings.get('main_theme', 'sky'))}</div>
    </body>
    </html>
    ''')

# --- শর্টেন সাকসেস পেজ ---
@app.route('/shorten', methods=['POST'])
def web_shorten():
    settings = get_settings()
    c = COLOR_MAP.get(settings.get('main_theme', 'sky'), COLOR_MAP['sky'])
    long_url = request.form.get('long_url')
    # চেক করা হচ্ছে ইউজার চেকবক্সে টিক দিয়েছে কিনা
    is_locked = True if request.form.get('is_locked') else False
    sc = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    
    urls_col.insert_one({
        "long_url": long_url, 
        "short_code": sc, 
        "clicks": 0, 
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "is_locked": is_locked  # ডাটাবেসে সেভ করা হলো এটি লকড নাকি নরমাল
    })
    
    return render_template_string(f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            body {{ background: #0f172a; color: white; background-image: radial-gradient(circle at top right, #1e293b, #0f172a); }}
            .glass-panel {{ background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(24px); border: 1px solid rgba(255, 255, 255, 0.1); box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); }}
        </style>
    </head>
    <body class="min-h-screen flex flex-col items-center justify-center p-4 text-center">
        <div class="glass-panel p-12 md:p-16 rounded-[50px] w-full max-w-2xl relative z-10">
            <div class="inline-block p-4 rounded-full bg-emerald-500/20 text-emerald-400 mb-6">
                <i class="fas fa-check-circle text-5xl"></i>
            </div>
            <h2 class="text-4xl md:text-5xl font-black mb-6 text-white uppercase italic">Link Created!</h2>
            
            {"<p class='text-yellow-400 font-bold mb-6 tracking-widest text-sm uppercase'><i class='fas fa-lock'></i> CPA Premium Lock Enabled</p>" if is_locked else ""}
            
            <div class="flex items-center bg-black/30 rounded-2xl p-2 mb-8 border border-white/10">
                <input id="shortUrl" value="{request.host_url + sc}" readonly class="w-full bg-transparent p-4 outline-none {c['text']} font-black text-center text-xl md:text-2xl">
            </div>
            
            <button onclick="copyLink()" id="copyBtn" class="w-full {c['bg']} text-white py-6 rounded-[30px] font-black text-2xl uppercase tracking-wider shadow-lg hover:scale-105 transition-all">
                <i class="fas fa-copy mr-2"></i> COPY LINK
            </button>
            
            <a href="/" class="inline-block mt-8 text-gray-400 hover:text-white font-bold uppercase text-sm tracking-widest transition-colors">
                <i class="fas fa-redo-alt mr-2"></i> Shorten Another Link
            </a>
        </div>
        <script>
            function copyLink() {{ 
                var copyText = document.getElementById("shortUrl"); 
                copyText.select(); 
                navigator.clipboard.writeText(copyText.value); 
                var btn = document.getElementById("copyBtn");
                btn.innerHTML = '<i class="fas fa-check-double mr-2"></i> COPIED!';
                btn.classList.add('bg-emerald-600');
                setTimeout(() => {{ btn.innerHTML = '<i class="fas fa-copy mr-2"></i> COPY LINK'; btn.classList.remove('bg-emerald-600'); }}, 3000);
            }}
        </script>
    </body>
    </html>
    ''')

# --- এডমিন প্যানেল ---
@app.route('/admin')
def admin_panel():
    if not is_logged_in(): return redirect(url_for('login'))
    settings = get_settings()
    all_urls = list(urls_col.find().sort("_id", -1).limit(50))
    channels = list(channels_col.find())
    ad_links = list(ad_links_col.find())
    
    today = datetime.now().strftime("%Y-%m-%d")
    total_views = stats_col.count_documents({})
    today_views = stats_col.count_documents({"date": today})
    chart_labels, chart_values = [], []
    for i in range(6, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        chart_labels.append(d); chart_values.append(stats_col.count_documents({"date": d}))
    countries = list(stats_col.aggregate([{"$group": {"_id": "$country", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 5}]))
    devices = list(stats_col.aggregate([{"$group": {"_id": "$device", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]))
    ad_stats = [{"url": al['url'], "count": stats_col.count_documents({"ad_link": al['url']})} for al in ad_links]

    return render_template_string('''
    <!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Premium Admin</title>
    <script src="https://cdn.tailwindcss.com"></script><script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style> .tab-content { display: none; } .tab-content.active { display: block; } .active-btn { background: #1e293b !important; color: white !important; } 
    ::-webkit-scrollbar { height: 5px; } ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; } </style>
    </head><body class="bg-slate-50 flex flex-col lg:flex-row min-h-screen font-sans">
        
        <div class="w-full lg:w-72 bg-white border-b lg:border-r p-6 flex lg:flex-col overflow-x-auto lg:overflow-visible sticky top-0 z-50">
            <h2 class="hidden lg:block text-2xl font-black mb-10 text-blue-600 italic tracking-tighter">PREMIUM ADMIN</h2>
            <nav class="flex lg:flex-col gap-2 w-full">
                <button onclick="tab('dash')" id="btn-dash" class="flex-1 lg:w-full text-center lg:text-left p-4 rounded-xl font-bold active-btn">📊 Dashboard</button>
                <button onclick="tab('links')" id="btn-links" class="flex-1 lg:w-full text-center lg:text-left p-4 rounded-xl font-bold text-slate-500">🔗 Links</button>
                <button onclick="tab('ads')" id="btn-ads" class="flex-1 lg:w-full text-center lg:text-left p-4 rounded-xl font-bold text-slate-500">💰 Ads</button>
                <button onclick="tab('partners')" id="btn-partners" class="flex-1 lg:w-full text-center lg:text-left p-4 rounded-xl font-bold text-slate-500">📢 Partners</button>
                <button onclick="tab('config')" id="btn-config" class="flex-1 lg:w-full text-center lg:text-left p-4 rounded-xl font-bold text-slate-500">⚙️ Settings</button>
                <a href="/logout" class="flex-1 lg:w-full text-center lg:text-left p-4 rounded-xl font-bold text-red-500 hover:bg-red-50 mt-4 lg:mt-10 border border-red-100 lg:border-none">🚪 Logout</a>
            </nav>
        </div>

        <div class="flex-1 p-6 lg:p-12 overflow-y-auto">
            <!-- TAB: DASHBOARD -->
            <div id="dash" class="tab-content active space-y-8">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div class="bg-blue-600 p-8 rounded-[40px] text-white shadow-xl"><p class="text-xs font-bold opacity-70">TOTAL VIEWS</p><h3 class="text-5xl font-black">{{total_views}}</h3></div>
                    <div class="bg-emerald-500 p-8 rounded-[40px] text-white shadow-xl"><p class="text-xs font-bold opacity-70">TODAY'S VIEWS</p><h3 class="text-5xl font-black">{{today_views}}</h3></div>
                    <div class="bg-white p-8 rounded-[40px] border shadow-sm"><p class="text-xs font-bold text-slate-400">TOTAL LINKS</p><h3 class="text-5xl font-black text-slate-800">{{all_urls|length}}</h3></div>
                </div>
                <div class="grid grid-cols-1 xl:grid-cols-2 gap-8">
                    <div class="bg-white p-8 rounded-[40px] border shadow-sm"><h4 class="font-black mb-6 uppercase text-slate-400 text-sm">Traffic Trend</h4><canvas id="trafficChart"></canvas></div>
                    <div class="bg-white p-8 rounded-[40px] border shadow-sm">
                        <h4 class="font-black mb-6 uppercase text-slate-400 text-sm">Devices & Countries</h4>
                        <div class="grid grid-cols-2 gap-4">
                            <div><p class="text-xs font-bold text-blue-600 mb-2">DEVICES</p>{% for d in devices %}<div class="bg-slate-50 p-2 rounded-lg text-xs mb-1 flex justify-between"><span>{{d._id}}</span><b>{{d.count}}</b></div>{% endfor %}</div>
                            <div><p class="text-xs font-bold text-orange-600 mb-2">COUNTRIES</p>{% for c in countries %}<div class="bg-slate-50 p-2 rounded-lg text-xs mb-1 flex justify-between"><span>{{c._id}}</span><b>{{c.count}}</b></div>{% endfor %}</div>
                        </div>
                    </div>
                </div>
                <div class="bg-white p-8 rounded-[40px] border shadow-sm"><h4 class="font-black mb-4 uppercase text-slate-400 text-sm">Direct Ad Link Performance</h4>
                    <div class="space-y-2">{% for as in ad_stats %}<div class="flex justify-between p-4 bg-slate-50 rounded-2xl text-sm"><span class="truncate pr-4">{{as.url}}</span><b class="text-emerald-600">{{as.count}} Clicks</b></div>{% endfor %}</div>
                </div>
            </div>

            <!-- TAB: LINKS (CPA 🔒 Icon added) -->
            <div id="links" class="tab-content">
                <div class="bg-white rounded-[40px] border shadow-sm overflow-x-auto">
                    <table class="w-full text-left text-sm"><thead class="bg-slate-50 font-bold uppercase text-slate-400"><tr><th class="p-6">Link</th><th class="p-6">Original URL</th><th class="p-6">Clicks</th></tr></thead>
                    <tbody class="divide-y font-bold">{% for u in all_urls %}<tr>
                        <td class="p-6 text-blue-600">/{{u.short_code}} {% if u.is_locked %}<span title="CPA Locked" class="ml-2">🔒</span>{% endif %}</td>
                        <td class="p-6 truncate max-w-xs text-slate-500">{{u.long_url}}</td><td class="p-6">{{u.clicks}}</td>
                    </tr>{% endfor %}</tbody></table>
                </div>
            </div>

            <!-- TAB: ADS -->
            <div id="ads" class="tab-content space-y-8">
                <div class="bg-white p-10 rounded-[50px] border shadow-sm">
                    <h4 class="font-black mb-6">Manage Direct Ad Links</h4>
                    <form action="/admin/add_ad_link" method="POST" class="flex flex-col md:flex-row gap-4 mb-8">
                        <input type="url" name="ad_url" placeholder="Paste Direct Link URL..." required class="flex-1 p-4 bg-slate-50 rounded-2xl">
                        <button class="bg-blue-600 text-white px-10 py-4 rounded-2xl font-black">ADD LINK</button>
                    </form>
                    <div class="space-y-3">{% for l in ad_links %}<div class="bg-slate-50 p-5 rounded-3xl flex justify-between items-center"><span>{{l.url}}</span><a href="/admin/delete_ad_link/{{l._id}}" class="text-red-500 font-bold">DELETE</a></div>{% endfor %}</div>
                </div>
            </div>

            <!-- TAB: PARTNERS -->
            <div id="partners" class="tab-content">
                <div class="bg-white p-10 rounded-[50px] border shadow-sm">
                    <h4 class="font-black mb-6">Official Channels</h4>
                    <form action="/admin/add_channel" method="POST" class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-10">
                        <input type="text" name="name" placeholder="Name" required class="p-4 bg-slate-50 rounded-xl">
                        <input type="url" name="logo" placeholder="Logo URL" required class="p-4 bg-slate-50 rounded-xl">
                        <input type="url" name="link" placeholder="Invite Link" required class="p-4 bg-slate-50 rounded-xl">
                        <button class="bg-emerald-600 text-white rounded-xl font-bold">ADD CHANNEL</button>
                    </form>
                    <div class="grid gap-6">{% for ch in channels %}<div class="flex items-center gap-6 p-4 border-b"><img src="{{ch.logo}}" class="w-20 h-12 object-cover rounded shadow"><b>{{ch.name}}</b><a href="/admin/delete_channel/{{ch._id}}" class="ml-auto text-red-500 font-bold">DEL</a></div>{% endfor %}</div>
                </div>
            </div>

            <!-- TAB: SETTINGS -->
            <div id="config" class="tab-content space-y-8">
                <form action="/admin/update" method="POST" class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    <div class="bg-white p-10 rounded-[50px] shadow-sm border space-y-6">
                        <h4 class="font-black text-xl">General Settings</h4>
                        <input type="text" name="site_name" value="{{s.site_name}}" placeholder="Site Name" class="w-full p-4 bg-slate-50 rounded-2xl font-bold">
                        <div class="grid grid-cols-2 gap-4">
                            <input type="number" name="steps" value="{{s.steps}}" placeholder="Steps" class="p-4 bg-slate-50 rounded-2xl">
                            <input type="number" name="timer_seconds" value="{{s.timer_seconds}}" placeholder="Seconds" class="p-4 bg-slate-50 rounded-2xl">
                            <select name="main_theme" class="p-4 bg-slate-50 rounded-2xl">{% for k in colors %}<option value="{{k}}" {% if s.main_theme == k %}selected{% endif %}>HOME: {{k|upper}}</option>{% endfor %}</select>
                            <select name="step_theme" class="p-4 bg-slate-50 rounded-2xl">{% for k in colors %}<option value="{{k}}" {% if s.step_theme == k %}selected{% endif %}>STEP: {{k|upper}}</option>{% endfor %}</select>
                        </div>
                        <div class="bg-orange-50 p-6 rounded-3xl space-y-4">
                            <p class="text-xs font-bold text-orange-600 uppercase">API Management</p>
                            <input type="text" id="apiKey" name="api_key" value="{{s.api_key}}" class="w-full p-4 bg-white rounded-xl text-xs font-mono border outline-none">
                            <div class="flex gap-2">
                                <button type="button" onclick="copyApi()" class="flex-1 bg-white text-orange-600 py-3 rounded-lg text-xs font-bold border">COPY KEY</button>
                                <button type="button" onclick="genApi()" class="flex-1 bg-orange-600 text-white py-3 rounded-lg text-xs font-bold">REGENERATE</button>
                            </div>
                        </div>
                        <input type="text" name="admin_telegram_id" value="{{s.admin_telegram_id}}" placeholder="Telegram Chat ID" class="w-full p-4 bg-slate-50 rounded-2xl font-bold">
                        <input type="password" name="new_password" placeholder="Change Admin Password" class="w-full p-4 bg-red-50 rounded-2xl font-bold">
                    </div>
                    
                    <div class="bg-white p-10 rounded-[50px] shadow-sm border space-y-4">
                        <h4 class="font-black text-xl text-emerald-600">Monetization Scripts</h4>
                        <input type="number" name="direct_click_limit" value="{{s.direct_click_limit}}" class="w-full p-4 bg-blue-50 rounded-2xl font-bold" placeholder="Clicks per direct ad">
                        
                        <!-- NEW CPA SCRIPT TEXTAREA -->
                        <textarea name="cpa_script" placeholder="CPA Content Locker Script (e.g. CPAGrip)" class="w-full h-24 p-4 bg-yellow-50 border border-yellow-200 rounded-xl text-xs font-mono">{{s.get('cpa_script', '')}}</textarea>
                        
                        <textarea name="popunder" placeholder="Popunder Script" class="w-full h-24 p-4 bg-slate-50 rounded-xl text-xs font-mono">{{s.popunder}}</textarea>
                        <textarea name="banner" placeholder="Banner Script" class="w-full h-24 p-4 bg-slate-50 rounded-xl text-xs font-mono">{{s.banner}}</textarea>
                        <textarea name="social_bar" placeholder="Social Bar Script" class="w-full h-24 p-4 bg-slate-50 rounded-xl text-xs font-mono">{{s.social_bar}}</textarea>
                        <textarea name="native" placeholder="Native Script" class="w-full h-24 p-4 bg-slate-50 rounded-xl text-xs font-mono">{{s.native}}</textarea>
                        <button class="w-full bg-slate-900 text-white py-6 rounded-3xl font-black text-xl shadow-xl">SAVE ALL CHANGES</button>
                    </div>
                </form>
            </div>
        </div>
        <script>
            function tab(id) {
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                document.querySelectorAll('nav button').forEach(b => b.classList.remove('active-btn'));
                document.getElementById(id).classList.add('active');
                document.getElementById('btn-'+id).classList.add('active-btn');
            }
            function genApi() {
                const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
                let res = ""; for(let i=0; i<40; i++) res += chars[Math.floor(Math.random()*chars.length)];
                document.getElementById('apiKey').value = res;
            }
            function copyApi() {
                let key = document.getElementById('apiKey'); key.select();
                navigator.clipboard.writeText(key.value); alert("API Key Copied!");
            }
            new Chart(document.getElementById('trafficChart'), {
                type: 'line',
                data: { labels: {{chart_labels|tojson}}, datasets: [{ label: 'Views', data: {{chart_values|tojson}}, borderColor: '#2563eb', backgroundColor: 'rgba(37, 99, 235, 0.1)', fill: true, tension: 0.4, borderWidth: 4 }] },
                options: { responsive: true, plugins: { legend: { display: false } } }
            });
        </script>
    </body></html>
    ''', total_views=total_views, today_views=today_views, all_urls=all_urls, countries=countries, 
        devices=devices, ad_stats=ad_stats, ad_links=ad_links, channels=channels, s=settings, 
        colors=COLOR_MAP.keys(), chart_labels=chart_labels, chart_values=chart_values)

# --- এডমিন অ্যাকশনস ---
@app.route('/admin/add_ad_link', methods=['POST'])
def add_ad_link():
    if not is_logged_in(): return redirect(url_for('login'))
    url = request.form.get('ad_url')
    if url: ad_links_col.insert_one({"url": url})
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_ad_link/<id>')
def delete_ad_link(id):
    if not is_logged_in(): return redirect(url_for('login'))
    ad_links_col.delete_one({"_id": ObjectId(id)})
    return redirect(url_for('admin_panel'))

@app.route('/admin/add_channel', methods=['POST'])
def add_channel():
    if not is_logged_in(): return redirect(url_for('login'))
    name, logo, link = request.form.get('name'), request.form.get('logo'), request.form.get('link')
    if logo and link: channels_col.insert_one({"name": name, "logo": logo, "link": link})
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_channel/<id>')
def delete_channel(id):
    if not is_logged_in(): return redirect(url_for('login'))
    channels_col.delete_one({"_id": ObjectId(id)})
    return redirect(url_for('admin_panel'))

@app.post('/admin/update')
def update_settings():
    if not is_logged_in(): return redirect(url_for('login'))
    d = {
        "site_name": request.form.get('site_name'),
        "admin_telegram_id": request.form.get('admin_telegram_id'),
        "steps": int(request.form.get('steps', 2)),
        "timer_seconds": int(request.form.get('timer_seconds', 10)),
        "api_key": request.form.get('api_key').strip(),
        "cpa_script": request.form.get('cpa_script'), # NEW CPA SCRIPT
        "popunder": request.form.get('popunder'),
        "banner": request.form.get('banner'),
        "social_bar": request.form.get('social_bar'),
        "native": request.form.get('native'),
        "direct_click_limit": int(request.form.get('direct_click_limit', 1)),
        "main_theme": request.form.get('main_theme'),
        "step_theme": request.form.get('step_theme')
    }
    np = request.form.get('new_password')
    if np and len(np) > 2: d["admin_password"] = generate_password_hash(np)
    settings_col.update_one({}, {"$set": d})
    return redirect(url_for('admin_panel'))

# --- রিডাইরেক্ট লজিক (CPA + Standard Auto Scroll) ---
@app.route('/<short_code>')
def handle_ad_steps(short_code):
    settings = get_settings()
    url_data = urls_col.find_one({"short_code": short_code})
    if not url_data: return "404 Not Found", 404
    
    # -----------------------------------------------------
    # OPTION 1: CPA LOCKER LOGIC (যদি লিংকে টিক দেওয়া থাকে)
    # -----------------------------------------------------
    if url_data.get('is_locked'):
        urls_col.update_one({"short_code": short_code}, {"$inc": {"clicks": 1}})
        track_click(short_code)
        
        return render_template_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
            <!-- CPA SCRIPT INJECTED HERE -->
            {{ s.get('cpa_script', '')|safe }}
            <title>Content Locked</title>
        </head>
        <body class="bg-slate-900 min-h-screen flex items-center justify-center p-4">
            <div class="bg-slate-800 p-10 md:p-16 rounded-[40px] shadow-2xl text-center max-w-lg w-full border border-slate-700">
                <div class="w-24 h-24 bg-yellow-500/20 text-yellow-500 rounded-full flex items-center justify-center mx-auto mb-6">
                    <i class="fas fa-lock text-5xl"></i>
                </div>
                <h2 class="text-3xl font-black text-white mb-4 uppercase tracking-wider">Premium Content</h2>
                <p class="text-slate-400 font-medium mb-8">This file/link is securely locked. Please complete a quick human verification offer to unlock it automatically.</p>
                
                <!-- এই বাটনে ক্লিক করলে CPA পপ-আপ আসবে (CPAGrip এর ডিফল্ট ক্লাস onClick কাজ করে) -->
                <button onclick="window.location.href='{{url_data['long_url']}}'" class="w-full bg-yellow-500 hover:bg-yellow-600 text-slate-900 py-5 rounded-2xl font-black text-xl uppercase tracking-widest transition-all">
                    Unlock & Continue <i class="fas fa-unlock ml-2"></i>
                </button>
                <p class="text-xs text-slate-500 mt-6"><i class="fas fa-shield-alt mr-1"></i> 100% Safe & Secure Encryption</p>
            </div>
        </body>
        </html>
        ''', s=settings, url_data=url_data)

    # -----------------------------------------------------
    # OPTION 2: STANDARD LOGIC (আগের মতো টাইমার ও অটো স্ক্রল)
    # -----------------------------------------------------
    step = int(request.args.get('step', 1))
    
    if step > settings['steps']:
        urls_col.update_one({"short_code": short_code}, {"$inc": {"clicks": 1}})
        track_click(short_code)
        return redirect(url_data['long_url'])
    
    ads = [l['url'] for l in ad_links_col.find()]
    tc = COLOR_MAP.get(settings.get('step_theme', 'blue'), COLOR_MAP['blue'])
    
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        {{ s.popunder|safe }} {{ s.social_bar|safe }}
        <style>
            .pulse-bg { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
            @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .5; } }
            html { scroll-behavior: smooth; }
        </style>
    </head>
    <body class="bg-gray-100 min-h-screen font-sans text-gray-800 pb-10">
        
        <header class="bg-white shadow-sm p-4 text-center border-b-4 {{tc.border}} sticky top-0 z-50">
            <h1 class="text-xl md:text-2xl font-black text-gray-800 tracking-tighter uppercase">
                <i class="fas fa-shield-check {{tc.text}} mr-2"></i> Safe Link Portal
            </h1>
        </header>

        <div class="max-w-4xl mx-auto flex flex-col items-center p-4 mt-6">
            
            <div class="bg-white p-8 md:p-12 rounded-3xl shadow-xl text-center w-full relative overflow-hidden border border-gray-200 mb-8">
                <div class="absolute top-0 left-0 w-full h-2 bg-gray-100">
                    <div class="h-full {{tc.bg}}" style="width: {{ (step / total_steps) * 100 }}%"></div>
                </div>

                <div class="mb-2 inline-block px-4 py-1 bg-gray-100 rounded-full text-sm font-bold text-gray-500 uppercase tracking-widest">
                    Step {{step}} / {{total_steps}}
                </div>
                
                <h2 id="status_text" class="text-2xl md:text-4xl font-black text-gray-800 mb-6">Checking IP Address...</h2>

                <div id="progress_container" class="w-full max-w-md mx-auto">
                    <div class="flex justify-between text-sm font-bold text-gray-500 mb-2">
                        <span>Please wait</span>
                        <span id="timer_text" class="{{tc.text}} text-lg">{{timer}} seconds</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-4 shadow-inner overflow-hidden">
                        <div id="progress_bar" class="{{tc.bg}} h-4 rounded-full transition-all duration-1000 ease-linear relative" style="width: 0%">
                            <div class="absolute top-0 left-0 w-full h-full bg-white opacity-20 pulse-bg"></div>
                        </div>
                    </div>
                </div>

                <div id="scroll_msg" class="hidden mt-6 bg-emerald-50 text-emerald-600 p-4 rounded-xl border border-emerald-200">
                    <p class="text-lg font-black animate-bounce">
                        <i class="fas fa-arrow-down mr-2"></i> Scroll Down To Continue
                    </p>
                </div>
            </div>

            <div class="w-full bg-white p-2 shadow-md rounded-xl mb-8 text-center min-h-[100px] flex flex-col items-center justify-center border-l-4 border-gray-300">
                <span class="text-xs text-gray-400 mb-2 tracking-widest uppercase">Advertisement</span>
                <div class="w-full overflow-hidden flex justify-center">{{ s.banner|safe }}</div>
            </div>

            <div class="w-full bg-white p-4 shadow-md rounded-xl mb-8 border-l-4 border-gray-300">
                <span class="text-xs text-gray-400 block text-center mb-2 tracking-widest uppercase">Sponsored Content</span>
                <div class="w-full overflow-hidden flex justify-center">{{ s.native|safe }}</div>
            </div>

            <div id="final_action_section" class="w-full bg-white p-8 md:p-12 rounded-3xl shadow-2xl text-center border-t-8 {{tc.border}} mt-4 mb-8 transform transition-all">
                <h3 class="text-xl md:text-2xl font-black text-gray-700 mb-6">Your Link is Almost Ready</h3>
                
                <button id="main_btn" onclick="handleClick()" disabled 
                        class="hidden w-full max-w-md mx-auto {{tc.bg}} text-white py-6 rounded-2xl font-black text-2xl md:text-3xl uppercase tracking-wider shadow-[0_10px_20px_-10px_rgba(0,0,0,0.5)] transition-all hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed">
                    <i class="fas fa-check-circle mr-2"></i> Continue
                </button>
                <p id="wait_msg" class="text-gray-400 font-bold text-sm mt-4">Please complete the progress above...</p>
            </div>

            <div class="w-full bg-slate-900 rounded-[40px] shadow-2xl overflow-hidden p-4">
                {{ partners_html|safe }}
            </div>
        </div>

        <script>
            let sec = {{timer}};
            const totalSec = sec;
            let ads = {{ads|tojson}};
            let clicks = 0;
            let limit = {{limit}};
            
            const timerText = document.getElementById('timer_text');
            const progressBar = document.getElementById('progress_bar');
            const mainBtn = document.getElementById('main_btn');
            const statusText = document.getElementById('status_text');
            const scrollMsg = document.getElementById('scroll_msg');
            const waitMsg = document.getElementById('wait_msg');
            const finalSection = document.getElementById('final_action_section');

            const iv = setInterval(() => { 
                sec--; 
                timerText.innerText = sec + " seconds"; 
                let percent = ((totalSec - sec) / totalSec) * 100;
                progressBar.style.width = percent + "%";

                if (sec === Math.floor(totalSec / 2)) {
                    statusText.innerText = "Scanning for malware...";
                }

                if(sec <= 0) { 
                    clearInterval(iv); 
                    statusText.innerText = "Verification Complete!";
                    statusText.classList.add('text-emerald-600');
                    document.getElementById('progress_container').classList.add('hidden');
                    scrollMsg.classList.remove('hidden');
                    
                    waitMsg.classList.add('hidden');
                    mainBtn.classList.remove('hidden'); 
                    mainBtn.removeAttribute('disabled');
                    updateBtn(); 

                    setTimeout(() => {
                        finalSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        finalSection.classList.add('scale-105');
                        setTimeout(() => finalSection.classList.remove('scale-105'), 500);
                    }, 500);
                } 
            }, 1000);

            function updateBtn() { 
                if(clicks < limit && ads.length > 0) {
                    mainBtn.innerHTML = `<i class="fas fa-external-link-alt mr-2"></i> VERIFY AD (${clicks+1}/${limit})`;
                    mainBtn.classList.add('animate-pulse');
                } else { 
                    mainBtn.innerHTML = `<i class="fas fa-arrow-right mr-2"></i> NEXT STEP`; 
                    mainBtn.classList.remove('animate-pulse');
                }
            }

            function handleClick() {
                if(clicks < limit && ads.length > 0) {
                    let r = ads[Math.floor(Math.random()*ads.length)];
                    fetch('/track_ajax?sc={{sc}}&ad='+encodeURIComponent(r)); 
                    window.open(r, '_blank'); 
                    clicks++; 
                    
                    mainBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Checking Ad...';
                    mainBtn.setAttribute('disabled', 'true');
                    
                    setTimeout(() => {
                        mainBtn.removeAttribute('disabled');
                        updateBtn();
                    }, 3000);

                } else { 
                    mainBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Loading...';
                    window.location.href = "/{{sc}}?step="+({{step}}+1); 
                }
            }
        </script>
    </body>
    </html>
    ''', s=settings, step=step, total_steps=settings['steps'], timer=settings['timer_seconds'], tc=tc, ads=ads, limit=settings['direct_click_limit'], sc=short_code, partners_html=get_channels_html(settings.get('step_theme', 'blue')))

@app.route('/track_ajax')
def track_ajax():
    track_click(request.args.get('sc'), request.args.get('ad'))
    return "ok"

# --- লগইন ও পাসওয়ার্ড রিকভারি ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in(): return redirect(url_for('admin_panel'))
    if request.method == 'POST':
        if check_password_hash(get_settings()['admin_password'], request.form.get('password')):
            session.permanent = True
            session['logged_in'] = True; return redirect(url_for('admin_panel'))
    return render_template_string('<body style="background:#0f172a;display:flex;justify-content:center;align-items:center;height:100vh;padding:20px;"><form method="POST" style="background:white;padding:40px;border-radius:30px;text-align:center;width:100%;max-width:350px;"><h2 style="font-weight:900;margin-bottom:30px;">ADMIN LOGIN</h2><input type="password" name="password" placeholder="Key" style="width:100%;padding:15px;margin-bottom:15px;border:1px solid #ddd;border-radius:10px;text-align:center;"><button style="width:100%;padding:15px;background:#1e293b;color:white;border:none;border-radius:10px;font-weight:900;">LOGIN</button><a href="/forgot-password" style="display:block;margin-top:20px;font-size:12px;color:#3b82f6;text-decoration:none;">Forgot Passkey?</a></form></body>')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        tg_id = request.form.get('telegram_id')
        settings = get_settings()
        if tg_id == settings.get('admin_telegram_id'):
            otp = str(random.randint(100000, 999999))
            otp_col.update_one({"id": "admin_reset"}, {"$set": {"otp": otp, "expire_at": datetime.now() + timedelta(minutes=5)}}, upsert=True)
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data={"chat_id": tg_id, "text": f"🛡️ OTP: {otp}"})
            session['reset_id'] = tg_id; return redirect(url_for('verify_otp'))
    return render_template_string('<body style="background:#0f172a;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="POST" style="background:white;padding:40px;border-radius:30px;width:320px;text-align:center;"><h2>Recovery</h2><input type="text" name="telegram_id" placeholder="Telegram Chat ID" required style="width:100%;padding:15px;margin:20px 0;text-align:center;"><button style="width:100%;padding:15px;background:#3b82f6;color:white;border:none;border-radius:15px;">GET OTP</button></form></body>')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if not session.get('reset_id'): return redirect('/forgot-password')
    if request.method == 'POST':
        otp = request.form.get('otp'); data = otp_col.find_one({"id": "admin_reset"})
        if data and data['otp'] == otp and data['expire_at'] > datetime.now():
            session['otp_verified'] = True; return redirect(url_for('reset_password'))
    return render_template_string('<body style="background:#0f172a;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="POST" style="background:white;padding:40px;border-radius:30px;width:320px;text-align:center;"><h2>Verify OTP</h2><input type="text" name="otp" placeholder="ENTER OTP" required style="width:100%;padding:15px;margin:20px 0;text-align:center;font-size:24px;"><button style="width:100%;padding:15px;background:#10b981;color:white;border:none;border-radius:15px;">VERIFY</button></form></body>')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('otp_verified'): return redirect('/forgot-password')
    if request.method == 'POST':
        pw = request.form.get('password')
        settings_col.update_one({}, {"$set": {"admin_password": generate_password_hash(pw)}})
        session.clear(); return 'SUCCESS! <a href="/login">LOGIN NOW</a>'
    return render_template_string('<body style="background:#0f172a;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="POST" style="background:white;padding:40px;border-radius:30px;width:320px;"><h2 style="text-align:center;">NEW PASSWORD</h2><input type="password" name="password" required placeholder="New Password" style="width:100%;padding:15px;margin:20px 0;"><button style="width:100%;padding:15px;background:#1e293b;color:white;border:none;border-radius:15px;">UPDATE</button></form></body>')

if __name__ == '__main__':
    app.run(debug=True)
