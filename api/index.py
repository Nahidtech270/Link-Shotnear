import os
import random
import string
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from bson.objectid import ObjectId

app = Flask(__name__, template_folder='../templates')
app.secret_key = "premium_secret_key_99"

# MongoDB Connection
MONGO_URI = os.environ.get("MONGO_URI") # ভার্সেল এনভায়রনমেন্ট থেকে নিবে
client = MongoClient(MONGO_URI)
db = client['pro_shortener']

# Tables
users = db['users']
links = db['links']
settings = db['settings']

# --- Helpers ---
def get_site_settings():
    conf = settings.find_one()
    if not conf:
        default = {
            "site_name": "ProShort",
            "timer": 10,
            "popunder_ad": "",
            "social_bar_ad": "",
            "banner_ad": "",
            "direct_link_ad": "",
            "api_doc_url": "#"
        }
        settings.insert_one(default)
        return default
    return conf

def gen_code(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# --- Routes ---

@app.route('/')
def home():
    return render_template('home.html', config=get_site_settings())

# --- User & Admin Auth ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = generate_password_hash(request.form.get('password'))
        api_key = "sk_" + gen_code(20)
        if users.find_one({"email": email}): return "Email already exists!"
        users.insert_one({"email": email, "password": password, "api_key": api_key, "role": "user"})
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = users.find_one({"email": request.form.get('email')})
        if user and check_password_hash(user['password'], request.form.get('password')):
            session['user_id'] = str(user['_id'])
            session['role'] = user.get('role', 'user')
            return redirect('/dashboard')
    return render_template('login.html')

# --- User Dashboard ---
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect('/login')
    user = users.find_one({"_id": ObjectId(session['user_id'])})
    user_links = list(links.find({"user_id": session['user_id']}).sort("_id", -1))
    return render_template('dashboard.html', user=user, links=user_links)

# --- Developer API ---
@app.route('/api/v1/shorten')
def api_shorten():
    key = request.args.get('api_key')
    long_url = request.args.get('url')
    user = users.find_one({"api_key": key})
    if not user: return jsonify({"error": "Invalid API Key"}), 401
    
    code = gen_code()
    links.insert_one({
        "user_id": str(user['_id']),
        "long_url": long_url,
        "short_code": code,
        "clicks": 0,
        "created_at": datetime.now()
    })
    return jsonify({"short_url": request.host_url + code})

# --- Admin Panel (Ad Management) ---
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('role') != 'admin': return "Access Denied"
    conf = get_site_settings()
    
    if request.method == 'POST':
        new_data = {
            "site_name": request.form.get('site_name'),
            "timer": int(request.form.get('timer')),
            "popunder_ad": request.form.get('popunder_ad'),
            "social_bar_ad": request.form.get('social_bar_ad'),
            "banner_ad": request.form.get('banner_ad'),
            "direct_link_ad": request.form.get('direct_link_ad')
        }
        settings.update_one({}, {"$set": new_data})
        return redirect('/admin')
    
    all_links = list(links.find().sort("clicks", -1).limit(20))
    return render_template('admin.html', config=conf, links=all_links)

# --- Redirection & Ad Page ---
@app.route('/<code>')
def redirect_link(code):
    link_data = links.find_one({"short_code": code})
    if not link_data: return "Invalid Link", 404
    
    conf = get_site_settings()
    links.update_one({"short_code": code}, {"$inc": {"clicks": 1}})
    
    return render_template('redirect_page.html', link=link_data, config=conf)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
