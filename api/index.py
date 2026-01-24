import os
import random
import string
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = "premium_pro_key_2025"

# MongoDB Connection (ভার্সেল Environment Variable এ MONGO_URI সেট করবেন)
MONGO_URI = os.environ.get("MONGO_URI", "your_mongodb_uri_here")
client = MongoClient(MONGO_URI)
db = client['pro_shortener_db']

# Collections
users = db['users']
links = db['links']
settings = db['settings']

# --- Helpers ---
def get_site_settings():
    conf = settings.find_one()
    if not conf:
        default = {
            "site_name": "Premium Shortener",
            "timer": 10,
            "popunder_ad": "",
            "social_bar_ad": "",
            "banner_ad": "",
            "direct_link_ad": "",
            "admin_password": generate_password_hash("admin123")
        }
        settings.insert_one(default)
        return default
    return conf

def gen_code(l=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=l))

# --- HTML Templates (CSS সহ এক ফাইলের ভেতরে) ---

HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.tailwindcss.com"></script>
    <title>{{ title }}</title>
</head>
<body class="bg-slate-50 text-slate-800 font-sans">
    <nav class="bg-white shadow-sm py-4 px-6 flex justify-between items-center border-b">
        <a href="/" class="text-2xl font-black text-blue-600">PRO-SHORT</a>
        <div class="space-x-4">
            {% if session.get('user_id') %}
                <a href="/dashboard" class="font-bold">Dashboard</a>
                <a href="/logout" class="text-red-500 font-bold">Logout</a>
            {% else %}
                <a href="/login" class="font-bold">Login</a>
                <a href="/register" class="bg-blue-600 text-white px-4 py-2 rounded-lg font-bold">Join</a>
            {% endif %}
        </div>
    </nav>
    <main class="p-6 max-w-6xl mx-auto">{{ content | safe }}</main>
</body>
</html>
"""

# --- Routes ---

@app.route('/')
def home():
    conf = get_site_settings()
    content = f'''
    <div class="text-center py-20">
        <h1 class="text-5xl font-black mb-4">{conf['site_name']}</h1>
        <p class="text-xl text-gray-500 mb-8">Professional URL Shortener with Developer API</p>
        <a href="/register" class="bg-blue-600 text-white px-10 py-4 rounded-2xl font-black text-xl shadow-xl">Get Started Now</a>
    </div>
    '''
    return render_template_string(HTML_LAYOUT, title="Home", content=content)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email, password = request.form.get('email'), request.form.get('password')
        if users.find_one({"email": email}): return "User Exists!"
        users.insert_one({"email": email, "password": generate_password_hash(password), "api_key": "sk_"+gen_code(15), "role": "user"})
        return redirect('/login')
    content = '''<div class="max-w-md mx-auto bg-white p-8 rounded-3xl shadow-lg mt-10"><h2 class="text-2xl font-bold mb-6">Create Account</h2><form method="POST"><input type="email" name="email" placeholder="Email" class="w-full p-4 mb-4 border rounded-xl" required><input type="password" name="password" placeholder="Password" class="w-full p-4 mb-6 border rounded-xl" required><button class="w-full bg-blue-600 text-white py-4 rounded-xl font-bold">Register</button></form></div>'''
    return render_template_string(HTML_LAYOUT, title="Register", content=content)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = users.find_one({"email": request.form.get('email')})
        if user and check_password_hash(user['password'], request.form.get('password')):
            session['user_id'] = str(user['_id'])
            session['role'] = user.get('role', 'user')
            return redirect('/dashboard')
    content = '''<div class="max-w-md mx-auto bg-white p-8 rounded-3xl shadow-lg mt-10"><h2 class="text-2xl font-bold mb-6">Login</h2><form method="POST"><input type="email" name="email" placeholder="Email" class="w-full p-4 mb-4 border rounded-xl" required><input type="password" name="password" placeholder="Password" class="w-full p-4 mb-6 border rounded-xl" required><button class="w-full bg-blue-600 text-white py-4 rounded-xl font-bold">Login</button></form></div>'''
    return render_template_string(HTML_LAYOUT, title="Login", content=content)

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session: return redirect('/login')
    user = users.find_one({"_id": ObjectId(session['user_id'])})
    
    if request.method == 'POST':
        long_url = request.form.get('long_url')
        code = gen_code()
        links.insert_one({"user_id": session['user_id'], "long_url": long_url, "short_code": code, "clicks": 0, "created_at": datetime.now()})
        return redirect('/dashboard')

    user_links = list(links.find({"user_id": session['user_id']}).sort("_id", -1))
    
    links_html = "".join([f'<div class="flex justify-between p-4 bg-gray-50 mb-2 rounded-xl"><span>/{l["short_code"]}</span><span class="font-bold">{l["clicks"]} Clicks</span></div>' for l in user_links])
    
    content = f'''
    <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div class="col-span-1 bg-white p-6 rounded-3xl shadow-sm border">
            <h3 class="font-bold mb-4">API Key</h3>
            <code class="bg-gray-100 p-2 block rounded mb-6 text-sm">{user['api_key']}</code>
            <h3 class="font-bold mb-4">Shorten Link</h3>
            <form method="POST"><input name="long_url" placeholder="Paste URL" class="w-full p-3 border rounded-xl mb-4"><button class="w-full bg-blue-600 text-white py-3 rounded-xl font-bold">Shorten</button></form>
        </div>
        <div class="col-span-2 bg-white p-6 rounded-3xl shadow-sm border">
            <h3 class="font-bold mb-4">My Links</h3>
            {links_html}
        </div>
    </div>
    '''
    return render_template_string(HTML_LAYOUT, title="Dashboard", content=content)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('role') != 'admin': return "Admin Access Required"
    conf = get_site_settings()
    
    if request.method == 'POST':
        update = {
            "site_name": request.form.get('site_name'),
            "timer": int(request.form.get('timer')),
            "popunder_ad": request.form.get('popunder_ad'),
            "social_bar_ad": request.form.get('social_bar_ad'),
            "banner_ad": request.form.get('banner_ad'),
            "direct_link_ad": request.form.get('direct_link_ad')
        }
        settings.update_one({}, {"$set": update})
        return redirect('/admin')

    content = f'''
    <h2 class="text-3xl font-black mb-8 text-blue-600">Admin - Ad Management</h2>
    <form method="POST" class="space-y-6 bg-white p-8 rounded-3xl border shadow-sm">
        <div class="grid grid-cols-2 gap-4">
            <div><label class="font-bold">Site Name</label><input name="site_name" value="{conf['site_name']}" class="w-full p-3 border rounded-xl mt-2"></div>
            <div><label class="font-bold">Timer (Seconds)</label><input type="number" name="timer" value="{conf['timer']}" class="w-full p-3 border rounded-xl mt-2"></div>
        </div>
        <div><label class="font-bold">Social Bar Script</label><textarea name="social_bar_ad" class="w-full p-3 border rounded-xl mt-2 h-24">{conf['social_bar_ad']}</textarea></div>
        <div><label class="font-bold">Popunder Script</label><textarea name="popunder_ad" class="w-full p-3 border rounded-xl mt-2 h-24">{conf['popunder_ad']}</textarea></div>
        <div><label class="font-bold">Banner Ad (HTML)</label><textarea name="banner_ad" class="w-full p-3 border rounded-xl mt-2 h-24">{conf['banner_ad']}</textarea></div>
        <div><label class="font-bold">Direct Link URL</label><input name="direct_link_ad" value="{conf['direct_link_ad']}" class="w-full p-3 border rounded-xl mt-2"></div>
        <button class="w-full bg-slate-900 text-white py-4 rounded-xl font-bold">Update All Settings</button>
    </form>
    '''
    return render_template_string(HTML_LAYOUT, title="Admin Panel", content=content)

@app.route('/<code>')
def redirect_handler(code):
    link = links.find_one({"short_code": code})
    if not link: return "Invalid Link", 404
    conf = get_site_settings()
    links.update_one({"short_code": code}, {"$inc": {"clicks": 1}})

    return render_template_string('''
    <!DOCTYPE html><html><head>
    <script src="https://cdn.tailwindcss.com"></script>
    {{ conf.social_bar_ad | safe }} {{ conf.popunder_ad | safe }}
    </head>
    <body class="bg-slate-100 flex flex-col items-center justify-center min-h-screen p-6">
        <div class="mb-6">{{ conf.banner_ad | safe }}</div>
        <div class="bg-white p-10 rounded-[40px] shadow-2xl text-center max-w-md w-full border-t-8 border-blue-600">
            <h1 class="text-2xl font-black mb-4">Link is Ready</h1>
            <div id="timer" class="text-6xl font-black text-blue-600 mb-8">{{ conf.timer }}</div>
            <button id="btn" class="hidden w-full bg-blue-600 text-white py-5 rounded-2xl font-black text-xl shadow-lg">GET LINK</button>
        </div>
        <script>
            let t = {{ conf.timer }};
            const countdown = setInterval(() => {
                t--; document.getElementById('timer').innerText = t;
                if(t <= 0) { clearInterval(countdown); document.getElementById('timer').classList.add('hidden'); document.getElementById('btn').classList.remove('hidden'); }
            }, 1000);
            document.getElementById('btn').onclick = () => {
                if("{{ conf.direct_link_ad }}") window.open("{{ conf.direct_link_ad }}", "_blank");
                window.location.href = "{{ link.long_url }}";
            };
        </script>
    </body></html>''', conf=conf, link=link)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# Developer API
@app.route('/api/shorten')
def api_shorten():
    key = request.args.get('api_key')
    url = request.args.get('url')
    user = users.find_one({"api_key": key})
    if not user: return jsonify({"error": "Invalid API Key"}), 401
    code = gen_code()
    links.insert_one({"user_id": str(user['_id']), "long_url": url, "short_code": code, "clicks": 0, "created_at": datetime.now()})
    return jsonify({"short_url": request.host_url + code})

def handler(event, context):
    return app(event, context)
