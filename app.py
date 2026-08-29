from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import secrets
import string
import requests
import time
import random
import json
import bcrypt
from urllib.parse import quote_plus

app = Flask(__name__)
app.config['SECRET_KEY'] = 'JubayerXtools-Secret-Key-2026'

# ============================================
# MONGODB CONFIG
# ============================================
MONGO_URI = "mongodb+srv://hemalmd817_db_user:U1NdZChsjvM2V9N6@cluster0.xkdghcq.mongodb.net/?appName=Cluster0"
DB_NAME = "jubayerxtools"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    client.admin.command('ping')
    print("✅ MongoDB Connected Successfully!")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")
    db = None

# ============================================
# COLLECTIONS
# ============================================
if db is not None:
    users_collection = db['users']
    categories_collection = db['categories']
    products_collection = db['products']
    variants_collection = db['variants']
    orders_collection = db['orders']
    transactions_collection = db['transactions']
    coupons_collection = db['coupons']
    notifications_collection = db['notifications']
    banners_collection = db['banners']
    popup_collection = db['popup']
    maintenance_collection = db['maintenance']
    airdrop_codes_collection = db['airdrop_codes']
else:
    users_collection = None
    categories_collection = None
    products_collection = None
    variants_collection = None
    orders_collection = None
    transactions_collection = None
    coupons_collection = None
    notifications_collection = None
    banners_collection = None
    popup_collection = None
    maintenance_collection = None
    airdrop_codes_collection = None

# ============================================
# CREATE INDEXES (FIXED - Google ID Issue)
# ============================================
if db is not None:
    try:
        # Drop old google_id index if exists
        try:
            users_collection.drop_index("google_id_1")
            print("✅ Dropped old google_id index")
        except:
            pass
        
        users_collection.create_index("username", unique=True)
        users_collection.create_index("email", unique=True)
        # 🔧 FIX: sparse=True so null values don't cause duplicate error
        users_collection.create_index("google_id", unique=True, sparse=True)
        categories_collection.create_index("name", unique=True)
        coupons_collection.create_index("code", unique=True)
        airdrop_codes_collection.create_index("code", unique=True)
        orders_collection.create_index("order_id", unique=True)
        print("✅ Indexes created successfully!")
    except Exception as e:
        print(f"⚠️ Index creation warning: {e}")

# ============================================
# GOOGLE OAUTH CONFIG
# ============================================
GOOGLE_CLIENT_ID = '1000333354528-f49uv8p3f6avkl9ou1iptmdh9ntoa7or.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET = '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'
GOOGLE_REDIRECT_URI = 'https://jubayer-x-tools-pi.vercel.app/google-callback'

# ============================================
# BOHUDUR PAYMENT CONFIG
# ============================================
BOHUDUR_API_KEY = "t3Q7lrUau2E8dHg0oyjc4pvKWsRAOqmD"
BOHUDUR_API_URL = "https://request.bohudur.one/create/v2/"
WEBHOOK_URL = "https://jubayerxtools-webhook.vercel.app"

# ============================================
# FLASK-LOGIN CONFIG
# ============================================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.user_id = user_data.get('user_id')
        self.username = user_data.get('username')
        self.email = user_data.get('email')
        self.password_hash = user_data.get('password_hash')
        self.balance = user_data.get('balance', 0.0)
        self.phone = user_data.get('phone', '')
        self.google_id = user_data.get('google_id')
        self.is_admin = user_data.get('is_admin', False)
        self.created_at = user_data.get('created_at')
        self._data = user_data

    def get_id(self):
        return self.id

@login_manager.user_loader
def load_user(user_id):
    if users_collection is None:
        return None
    try:
        user_data = users_collection.find_one({'_id': ObjectId(user_id)})
        if user_data:
            return User(user_data)
    except Exception as e:
        print(f"⚠️ Load user error: {e}")
    return None

# ============================================
# HELPER FUNCTIONS
# ============================================

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    if hashed is None:
        return False
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_order_id(user_id):
    return f"JX{int(time.time())}{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"

def add_codes_to_product(product_id, codes_text):
    if not codes_text or airdrop_codes_collection is None:
        return 0
    codes = [c.strip() for c in codes_text.split('\n') if c.strip()]
    added = 0
    for code in codes:
        if code:
            existing = airdrop_codes_collection.find_one({'code': code})
            if not existing:
                airdrop_codes_collection.insert_one({
                    'code': code,
                    'product_id': product_id,
                    'is_used': False,
                    'used_by': None,
                    'used_at': None,
                    'created_at': datetime.utcnow()
                })
                added += 1
    return added

def validate_coupon(coupon_code, user_id):
    if coupons_collection is None:
        return None, "Database not connected"
    coupon = coupons_collection.find_one({'code': coupon_code.upper(), 'is_active': True})
    if not coupon:
        return None, "Invalid coupon code!"
    if coupon.get('used_by') is not None:
        return None, "This coupon has already been used!"
    return coupon, None

def calculate_discount(price, coupon):
    discount_amount = price * (coupon['discount_percent'] / 100)
    if coupon.get('max_discount') and discount_amount > coupon['max_discount']:
        discount_amount = coupon['max_discount']
    return discount_amount

def is_maintenance_on():
    if maintenance_collection is None:
        return False
    setting = maintenance_collection.find_one({'key': 'maintenance'})
    return setting.get('value', False) if setting else False

def create_bohudur_payment(amount, user_id, username=None):
    try:
        order_id = generate_order_id(user_id)
        my_reference = f"JX_{amount}TAKA_{order_id}_{user_id}"
        
        base_url = WEBHOOK_URL
        redirect_url = f"{base_url}/payment/success?paymentkey={my_reference}&user_id={user_id}&amount={amount}"
        cancel_url = f"{base_url}/payment/cancel"
        
        payload = {
            "full_name": f"User_{user_id}",
            "email": f"user{user_id}@jubayerxtools.com",
            "amount": amount,
            "return_type": "GET",
            "redirect_url": redirect_url,
            "cancel_url": cancel_url,
            "metadata": {
                "my_reference": my_reference,
                "user_id": user_id,
                "amount": amount,
                "order_id": order_id
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "AH-BOHUDUR-API-KEY": BOHUDUR_API_KEY
        }
        
        response = requests.post(BOHUDUR_API_URL, json=payload, headers=headers, timeout=30)
        result = response.json()
        
        print(f"Bohudur Response: {result}")
        
        if result.get("responseCode") == 200:
            bohudur_payment_key = result.get("paymentkey")
            return {
                "success": True,
                "payment_url": result.get("payment_url"),
                "paymentkey": bohudur_payment_key,
                "my_reference": my_reference,
                "order_id": order_id
            }
        else:
            return {
                "success": False, 
                "error": result.get("message", "Payment creation failed"),
                "response": result
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================
# CREATE DEFAULT DATA (FIXED - No google_id: None)
# ============================================

def init_db():
    if users_collection is None:
        return
    
    # Admin User (google_id excluded to avoid duplicate key error)
    if not users_collection.find_one({'username': 'admin'}):
        users_collection.insert_one({
            'user_id': 1,
            'username': 'admin',
            'email': 'admin@jubayerxtools.com',
            'password_hash': hash_password('admin123'),
            'balance': 999999,
            'phone': '',
            'is_admin': True,
            'created_at': datetime.utcnow()
        })
        print("Admin created: admin / admin123")
    
    # Default Categories
    default_categories = ['Others Item', 'Non Root Panel', 'Root Panel', 'iPhone Panel', 'PC Panel']
    for cat_name in default_categories:
        if not categories_collection.find_one({'name': cat_name}):
            categories_collection.insert_one({
                'name': cat_name,
                'icon': 'fa-tag',
                'created_at': datetime.utcnow()
            })
    
    # Default Products
    default_logo = 'https://i.ibb.co.com/KxSnyTjy/635d5463-6cd3-485e-bd05-907c07468d3a.png'
    default_products = [
        ('FF Guild Glory', 130.00, 'Others Item', 'Free Fire Guild Level Up Bot. Guild Glory'),
        ('BalaMod Android', 80.00, 'Non Root Panel', 'Premium Android mod panel'),
        ('HG CHEAT', 120.00, 'Root Panel', 'Root panel cheat tool'),
        ('Fluorite IOS', 110.00, 'iPhone Panel', 'iOS fluorite panel'),
        ('PC Panel Pro', 200.00, 'PC Panel', 'Pro PC gaming panel'),
    ]
    
    for name, price, cat_name, desc in default_products:
        if not products_collection.find_one({'name': name}):
            category = categories_collection.find_one({'name': cat_name})
            if category:
                products_collection.insert_one({
                    'name': name,
                    'price': price,
                    'logo': default_logo,
                    'description': desc,
                    'product_type': 'file',
                    'file_link': '',
                    'category_id': str(category['_id']),
                    'is_active': True,
                    'has_variants': False,
                    'created_at': datetime.utcnow()
                })
    
    # Default Banners
    if not banners_collection.find_one():
        banners = [
            {
                'image': 'https://i.ibb.co.com/KxSnyTjy/635d5463-6cd3-485e-bd05-907c07468d3a.png',
                'title': 'Welcome to JubayerXtools',
                'order': 0,
                'is_active': True,
                'created_at': datetime.utcnow()
            },
            {
                'image': 'https://i.ibb.co.com/KxSnyTjy/635d5463-6cd3-485e-bd05-907c07468d3a.png',
                'title': 'Premium Products Available',
                'order': 1,
                'is_active': True,
                'created_at': datetime.utcnow()
            }
        ]
        for banner in banners:
            banners_collection.insert_one(banner)
    
    # Popup Setting
    if not popup_collection.find_one():
        popup_collection.insert_one({
            'is_enabled': False,
            'photo': '',
            'message': 'Join our Telegram channel for updates!',
            'button_text': 'Join Now',
            'button_link': 'https://t.me/jubayerxtools',
            'created_at': datetime.utcnow()
        })
    
    # Maintenance Setting
    if not maintenance_collection.find_one({'key': 'maintenance'}):
        maintenance_collection.insert_one({
            'key': 'maintenance',
            'value': False,
            'message': 'Site is under maintenance. Please check back later.',
            'photo': '',
            'created_at': datetime.utcnow()
        })

# Run init
with app.app_context():
    init_db()

# ============================================
# GOOGLE OAUTH ROUTES
# ============================================

@app.route('/google-login')
def google_login():
    from urllib.parse import urlencode
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'email profile',
        'access_type': 'online'
    }
    auth_url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"
    return redirect(auth_url)

@app.route('/google-callback')
def google_callback():
    if users_collection is None:
        flash('Database not connected!', 'error')
        return redirect(url_for('login_page'))
    
    code = request.args.get('code')
    if not code:
        flash('Google login failed!', 'error')
        return redirect(url_for('login_page'))
    
    token_url = 'https://oauth2.googleapis.com/token'
    data = {
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    
    response = requests.post(token_url, data=data)
    if response.status_code != 200:
        flash('Google login failed!', 'error')
        return redirect(url_for('login_page'))
    
    token_data = response.json()
    access_token = token_data.get('access_token')
    
    user_info_url = 'https://www.googleapis.com/oauth2/v2/userinfo'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(user_info_url, headers=headers)
    
    if response.status_code != 200:
        flash('Google login failed!', 'error')
        return redirect(url_for('login_page'))
    
    user_data = response.json()
    google_id = user_data.get('id')
    email = user_data.get('email')
    username = user_data.get('name', email.split('@')[0])
    
    user = users_collection.find_one({'google_id': google_id})
    if not user:
        user = users_collection.find_one({'email': email})
        if user:
            users_collection.update_one({'_id': user['_id']}, {'$set': {'google_id': google_id}})
        else:
            max_user = users_collection.find_one(sort=[('user_id', -1)])
            new_id = (max_user['user_id'] + 1) if max_user else 1
            
            # 🔧 FIX: No password_hash field with None
            users_collection.insert_one({
                'user_id': new_id,
                'username': username,
                'email': email,
                'google_id': google_id,
                'balance': 0,
                'phone': '',
                'is_admin': False,
                'created_at': datetime.utcnow()
            })
    
    user_data = users_collection.find_one({'google_id': google_id})
    if user_data:
        login_user(User(user_data))
        flash('Google login successful!', 'success')
    else:
        flash('Google login failed!', 'error')
    
    return redirect(url_for('dashboard'))

# ============================================
# MAIN ROUTES
# ============================================

@app.route('/')
def index():
    if db is None:
        return "Database not connected!", 500
    maintenance = maintenance_collection.find_one({'key': 'maintenance'})
    if maintenance and maintenance.get('value', False):
        return render_template('maintenance.html', maintenance=maintenance)
    banners = list(banners_collection.find({'is_active': True}).sort('order', 1))
    return render_template('landing.html', user=current_user, banners=banners)

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if users_collection is None:
        flash('Database not connected!', 'error')
        return render_template('login.html', active_tab='login')
    
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard' if current_user.is_admin else 'dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'login':
            username = request.form.get('username')
            password = request.form.get('password')
            user = users_collection.find_one({'username': username})
            
            if user and user.get('password_hash') and check_password(password, user['password_hash']):
                login_user(User(user))
                return redirect(url_for('admin_dashboard' if user.get('is_admin') else 'dashboard'))
            flash('Invalid username or password!', 'error')
        
        elif action == 'register':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm = request.form.get('confirm_password')
            phone = request.form.get('phone', '')
            
            phone_digits = ''.join(filter(str.isdigit, phone))
            
            if not all([username, email, password]):
                flash('All fields are required!', 'error')
            elif password != confirm:
                flash('Passwords do not match!', 'error')
            elif len(password) < 6:
                flash('Password must be at least 6 characters!', 'error')
            elif len(phone_digits) < 11:
                flash('Phone number must be at least 11 digits!', 'error')
            elif users_collection.find_one({'username': username}):
                flash('Username already exists!', 'error')
            elif users_collection.find_one({'email': email}):
                flash('Email already registered!', 'error')
            else:
                max_user = users_collection.find_one(sort=[('user_id', -1)])
                new_id = (max_user['user_id'] + 1) if max_user else 1
                
                # 🔧 FIX: No google_id field with None
                users_collection.insert_one({
                    'user_id': new_id,
                    'username': username,
                    'email': email,
                    'phone': phone_digits,
                    'password_hash': hash_password(password),
                    'balance': 0,
                    'is_admin': False,
                    'created_at': datetime.utcnow()
                })
                flash('Registration successful! Please login.', 'success')
                return render_template('login.html', active_tab='login')
    
    return render_template('login.html', active_tab='login')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ============================================
# DASHBOARD
# ============================================

@app.route('/dashboard')
@login_required
def dashboard():
    if users_collection is None:
        flash('Database not connected!', 'error')
        return redirect(url_for('login_page'))
    
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    categories = list(categories_collection.find())
    products = list(products_collection.find({'is_active': True}))
    orders = list(orders_collection.find({'user_id': current_user.user_id}).sort('created_at', -1))
    transactions = list(transactions_collection.find({'user_id': current_user.user_id}).sort('created_at', -1))
    popup = popup_collection.find_one()
    banners = list(banners_collection.find({'is_active': True}).sort('order', 1))
    unread_count = notifications_collection.count_documents({'user_id': current_user.user_id, 'is_read': False})
    
    return render_template('dashboard.html', 
                         user=current_user, 
                         categories=categories,
                         products=products,
                         orders=orders,
                         transactions=transactions,
                         popup=popup,
                         banners=banners,
                         unread_count=unread_count)

@app.route('/my-profile')
@login_required
def my_profile():
    if users_collection is None:
        flash('Database not connected!', 'error')
        return redirect(url_for('login_page'))
    
    orders = list(orders_collection.find({'user_id': current_user.user_id}).sort('created_at', -1))
    transactions = list(transactions_collection.find({'user_id': current_user.user_id}))
    
    total_orders = len(orders)
    completed_orders = len([o for o in orders if o.get('status') == 'completed'])
    total_spent = sum(o.get('item_price', 0) for o in orders if o.get('status') == 'completed')
    total_deposit = sum(t.get('amount', 0) for t in transactions if t.get('type') == 'add')
    
    return render_template('my-profile.html',
                         user=current_user,
                         orders=orders,
                         total_orders=total_orders,
                         completed_orders=completed_orders,
                         total_spent=total_spent,
                         total_deposit=total_deposit)

@app.route('/my-orders')
@login_required
def my_orders():
    if users_collection is None:
        flash('Database not connected!', 'error')
        return redirect(url_for('login_page'))
    
    orders = list(orders_collection.find({'user_id': current_user.user_id}).sort('created_at', -1))
    
    orders_data = []
    for order in orders:
        product = products_collection.find_one({'_id': ObjectId(order['product_id'])})
        orders_data.append({
            'id': str(order['_id']),
            'order_id': order.get('order_id'),
            'item_name': order.get('item_name'),
            'variant_name': order.get('variant_name'),
            'variant_quantity': order.get('variant_quantity', 1),
            'item_price': order.get('item_price'),
            'discount': order.get('discount', 0),
            'coupon_code': order.get('coupon_code'),
            'final_price': order.get('final_price'),
            'status': order.get('status'),
            'code_used': order.get('code_used'),
            'created_at': order.get('created_at'),
            'product': {
                'product_type': product.get('product_type') if product else 'file',
                'file_link': product.get('file_link') if product else None
            }
        })
    
    return render_template('my-orders.html', user=current_user, orders=orders, orders_data=orders_data)

@app.route('/my-transactions')
@login_required
def my_transactions():
    if users_collection is None:
        flash('Database not connected!', 'error')
        return redirect(url_for('login_page'))
    
    transactions = list(transactions_collection.find({'user_id': current_user.user_id}).sort('created_at', -1))
    
    total_deposit = sum(t.get('amount', 0) for t in transactions if t.get('type') == 'add')
    total_spent = sum(t.get('amount', 0) for t in transactions if t.get('type') == 'purchase')
    
    return render_template('my-transactions.html',
                         user=current_user,
                         transactions=transactions,
                         total_deposit=total_deposit,
                         total_spent=total_spent)

@app.route('/add-balance')
@login_required
def add_balance():
    if users_collection is None:
        flash('Database not connected!', 'error')
        return redirect(url_for('login_page'))
    
    return render_template('add-balance.html', user=current_user)

# ============================================
# BOHUDUR PAYMENT ROUTES
# ============================================

pending_payments = {}

@app.route('/create-payment', methods=['POST'])
@login_required
def create_payment():
    if users_collection is None:
        return jsonify({'error': 'Database not connected'}), 500
    
    try:
        data = request.get_json()
        amount = int(data.get('amount', 0))
        
        if amount < 10:
            return jsonify({'error': 'Minimum deposit is ৳10!'}), 400
        
        if amount > 50000:
            return jsonify({'error': 'Maximum deposit is ৳50,000!'}), 400
        
        result = create_bohudur_payment(
            amount=amount,
            user_id=current_user.user_id,
            username=current_user.username
        )
        
        if result['success']:
            pending_payments[result['paymentkey']] = {
                'user_id': current_user.user_id,
                'amount': amount,
                'order_id': result['order_id'],
                'my_reference': result['my_reference'],
                'created_at': datetime.utcnow()
            }
            
            return jsonify({
                'success': True,
                'payment_url': result['payment_url'],
                'paymentkey': result['paymentkey'],
                'amount': amount
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Payment creation failed')
            }), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/payment/webhook', methods=['POST'])
def payment_webhook():
    if users_collection is None:
        return jsonify({'status': 'error', 'message': 'Database not connected'}), 500
    
    try:
        data = request.get_json()
        print(f"📩 Webhook Data: {data}")
        
        payment_key = data.get('paymentkey')
        user_id = data.get('user_id')
        amount = data.get('amount')
        status = data.get('status')
        
        if status != 'success':
            return jsonify({'status': 'ignored', 'message': 'Status not success'}), 200
        
        if not payment_key or not user_id or not amount:
            return jsonify({'status': 'error', 'message': 'Missing data'}), 400
        
        if payment_key in pending_payments:
            pending_payments.pop(payment_key)
        
        user = users_collection.find_one({'user_id': user_id})
        if not user:
            return jsonify({'status': 'error', 'message': 'User not found'}), 404
        
        new_balance = user.get('balance', 0) + amount
        users_collection.update_one({'_id': user['_id']}, {'$set': {'balance': new_balance}})
        
        transactions_collection.insert_one({
            'user_id': user_id,
            'amount': amount,
            'type': 'add',
            'description': f'Added ৳{amount} via Bohudur Payment (Webhook)',
            'status': 'completed',
            'created_at': datetime.utcnow()
        })
        
        notifications_collection.insert_one({
            'user_id': user_id,
            'title': '💰 Payment Successful',
            'message': f'Added ৳{amount} to your wallet via Bohudur Payment.',
            'is_read': False,
            'created_at': datetime.utcnow()
        })
        
        print(f"✅ Balance added: {amount} to user {user_id}")
        
        return jsonify({'status': 'success', 'message': 'Balance added'}), 200
        
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# TERMS, PRIVACY, SUPPORT
# ============================================

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/support')
def support():
    return render_template('support.html')

# ============================================
# VARIANT ROUTES
# ============================================

@app.route('/variants/<product_id>')
@login_required
def variants_page(product_id):
    if users_collection is None:
        flash('Database not connected!', 'error')
        return redirect(url_for('dashboard'))
    
    product = products_collection.find_one({'_id': ObjectId(product_id)})
    if not product:
        flash('Product not found!', 'error')
        return redirect(url_for('dashboard'))
    
    if not product.get('has_variants'):
        flash('This product does not have variants.', 'error')
        return redirect(url_for('dashboard'))
    
    variants = list(variants_collection.find({'product_id': product_id, 'is_active': True}))
    
    if not variants:
        flash('No variants available for this product.', 'error')
        return redirect(url_for('dashboard'))
    
    return render_template('variants.html', user=current_user, product=product, variants=variants)

@app.route('/select-variant', methods=['POST'])
@login_required
def select_variant():
    if users_collection is None:
        flash('Database not connected!', 'error')
        return redirect(url_for('dashboard'))
    
    variant_id = request.form.get('variant_id')
    product_id = request.form.get('product_id')
    
    if not variant_id or not product_id:
        flash('Invalid selection!', 'error')
        return redirect(url_for('dashboard'))
    
    product = products_collection.find_one({'_id': ObjectId(product_id)})
    if not product:
        flash('Product not found!', 'error')
        return redirect(url_for('dashboard'))
    
    variant = variants_collection.find_one({'_id': ObjectId(variant_id)})
    if not variant or variant['product_id'] != product_id:
        flash('Invalid variant selection!', 'error')
        return redirect(url_for('dashboard'))
    
    if product.get('product_type') == 'code':
        available_codes = airdrop_codes_collection.count_documents({
            'product_id': product_id,
            'is_used': False
        })
        
        if available_codes < variant.get('quantity', 1):
            flash(f'Sorry! Only {available_codes} codes available. You need {variant.get("quantity", 1)}.', 'error')
            return redirect(url_for('variants_page', product_id=product_id))
    
    order_id = generate_order_id(current_user.user_id)
    
    orders_collection.insert_one({
        'user_id': current_user.user_id,
        'product_id': product_id,
        'variant_id': variant_id,
        'variant_name': variant.get('name'),
        'variant_quantity': variant.get('quantity', 1),
        'order_id': order_id,
        'item_name': f"{product['name']} - {variant['name']}",
        'item_price': variant.get('price'),
        'discount': 0,
        'coupon_code': None,
        'final_price': variant.get('price'),
        'status': 'pending',
        'code_used': None,
        'created_at': datetime.utcnow()
    })
    
    return redirect(url_for('checkout', order_id=order_id))

# ============================================
# CHECKOUT ROUTES
# ============================================

@app.route('/checkout/<order_id>')
@login_required
def checkout(order_id):
    if users_collection is None:
        flash('Database not connected!', 'error')
        return redirect(url_for('dashboard'))
    
    order = orders_collection.find_one({'order_id': order_id, 'user_id': current_user.user_id})
    if not order:
        flash('Order not found!', 'error')
        return redirect(url_for('dashboard'))
    
    return render_template('checkout.html', user=current_user, order=order)

@app.route('/apply-coupon', methods=['POST'])
@login_required
def apply_coupon():
    if users_collection is None:
        return jsonify({'error': 'Database not connected'}), 500
    
    data = request.get_json()
    order_id = data.get('order_id')
    coupon_code = data.get('coupon_code', '').strip().upper()
    
    order = orders_collection.find_one({'order_id': order_id, 'user_id': current_user.user_id})
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    if order.get('status') != 'pending':
        return jsonify({'error': 'Order already processed'}), 400
    
    coupon, error = validate_coupon(coupon_code, current_user.user_id)
    if error:
        return jsonify({'error': error}), 400
    
    discount_amount = calculate_discount(order['item_price'], coupon)
    final_price = order['item_price'] - discount_amount
    
    orders_collection.update_one({'_id': order['_id']}, {
        '$set': {
            'discount': discount_amount,
            'coupon_code': coupon_code,
            'final_price': final_price
        }
    })
    
    coupons_collection.update_one({'_id': coupon['_id']}, {
        '$set': {
            'used_by': current_user.user_id,
            'used_at': datetime.utcnow(),
            'is_active': False
        }
    })
    
    return jsonify({
        'success': True,
        'discount': discount_amount,
        'final_price': final_price,
        'discount_percent': coupon['discount_percent']
    })

@app.route('/remove-coupon', methods=['POST'])
@login_required
def remove_coupon():
    if users_collection is None:
        return jsonify({'error': 'Database not connected'}), 500
    
    data = request.get_json()
    order_id = data.get('order_id')
    
    order = orders_collection.find_one({'order_id': order_id, 'user_id': current_user.user_id})
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    if not order.get('coupon_code'):
        return jsonify({'error': 'No coupon applied'}), 400
    
    coupon = coupons_collection.find_one({'code': order['coupon_code']})
    if coupon:
        coupons_collection.update_one({'_id': coupon['_id']}, {
            '$set': {
                'is_active': True,
                'used_by': None,
                'used_at': None
            }
        })
    
    orders_collection.update_one({'_id': order['_id']}, {
        '$set': {
            'discount': 0,
            'coupon_code': None,
            'final_price': order['item_price']
        }
    })
    
    return jsonify({
        'success': True,
        'final_price': order['item_price']
    })

@app.route('/success/<order_id>')
@login_required
def success_page(order_id):
    if users_collection is None:
        flash('Database not connected!', 'error')
        return redirect(url_for('dashboard'))
    
    order = orders_collection.find_one({'order_id': order_id, 'user_id': current_user.user_id})
    if not order:
        flash('Order not found!', 'error')
        return redirect(url_for('dashboard'))
    
    if order.get('status') != 'completed':
        flash('Order not completed!', 'error')
        return redirect(url_for('dashboard'))
    
    return render_template('success.html', user=current_user, order=order)

@app.route('/process-payment/<order_id>', methods=['POST'])
@login_required
def process_payment(order_id):
    if users_collection is None:
        return jsonify({'error': 'Database not connected'}), 500
    
    order = orders_collection.find_one({'order_id': order_id, 'user_id': current_user.user_id})
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    if order.get('status') == 'completed':
        return jsonify({'error': 'Order already completed'}), 400
    
    amount_to_pay = order.get('final_price') if order.get('final_price') else order['item_price']
    
    user = users_collection.find_one({'user_id': current_user.user_id})
    if user.get('balance', 0) < amount_to_pay:
        return jsonify({'error': 'Insufficient balance!'}), 400
    
    new_balance = user.get('balance', 0) - amount_to_pay
    users_collection.update_one({'_id': user['_id']}, {'$set': {'balance': new_balance}})
    
    update_data = {
        'status': 'completed',
        'final_price': amount_to_pay
    }
    
    product = products_collection.find_one({'_id': ObjectId(order['product_id'])})
    if product and product.get('product_type') == 'code':
        quantity = order.get('variant_quantity', 1)
        available_codes = list(airdrop_codes_collection.find({
            'product_id': order['product_id'],
            'is_used': False
        }).limit(quantity))
        
        if len(available_codes) >= quantity:
            codes_list = []
            for code_obj in available_codes:
                codes_list.append(code_obj['code'])
                airdrop_codes_collection.update_one({'_id': code_obj['_id']}, {
                    '$set': {
                        'is_used': True,
                        'used_by': current_user.user_id,
                        'used_at': datetime.utcnow()
                    }
                })
            update_data['code_used'] = ', '.join(codes_list)
    
    elif product and product.get('product_type') == 'file':
        if product.get('file_link'):
            update_data['code_used'] = product['file_link']
    
    orders_collection.update_one({'_id': order['_id']}, {'$set': update_data})
    
    transactions_collection.insert_one({
        'user_id': current_user.user_id,
        'amount': amount_to_pay,
        'type': 'purchase',
        'description': f'Purchased {order["item_name"]}' + (f' (Coupon: {order.get("coupon_code")})' if order.get('coupon_code') else ''),
        'status': 'completed',
        'created_at': datetime.utcnow()
    })
    
    return jsonify({
        'success': True,
        'order_id': order['order_id'],
        'item_name': order['item_name'],
        'amount': amount_to_pay,
        'discount': order.get('discount', 0),
        'coupon_code': order.get('coupon_code'),
        'quantity': order.get('variant_quantity', 1),
        'date': order.get('created_at'),
        'code': update_data.get('code_used'),
        'file_link': product.get('file_link') if product and product.get('product_type') == 'file' else None
    })

@app.route('/add-money', methods=['POST'])
@login_required
def add_money():
    if users_collection is None:
        flash('Database not connected!', 'error')
        return redirect(url_for('login_page'))
    
    amount = float(request.form.get('amount', 0))
    
    if amount < 10:
        flash('Minimum deposit is ৳10!', 'error')
        return redirect(url_for('add_balance'))
    
    if amount > 50000:
        flash('Maximum deposit is ৳50,000!', 'error')
        return redirect(url_for('add_balance'))
    
    if amount > 0:
        user = users_collection.find_one({'user_id': current_user.user_id})
        new_balance = user.get('balance', 0) + amount
        users_collection.update_one({'_id': user['_id']}, {'$set': {'balance': new_balance}})
        
        transactions_collection.insert_one({
            'user_id': current_user.user_id,
            'amount': amount,
            'type': 'add',
            'description': f'Added ৳{amount} to balance',
            'status': 'completed',
            'created_at': datetime.utcnow()
        })
        
        flash(f'Successfully added ৳{amount} to your balance!', 'success')
    
    return redirect(url_for('dashboard'))

@app.route('/buy-product/<product_id>', methods=['POST'])
@login_required
def buy_product(product_id):
    if users_collection is None:
        flash('Database not connected!', 'error')
        return redirect(url_for('dashboard'))
    
    product = products_collection.find_one({'_id': ObjectId(product_id)})
    if not product:
        flash('Product not found!', 'error')
        return redirect(url_for('dashboard'))
    
    if product.get('has_variants'):
        return redirect(url_for('variants_page', product_id=product_id))
    
    if product.get('product_type') == 'code':
        available_codes = airdrop_codes_collection.count_documents({
            'product_id': product_id,
            'is_used': False
        })
        if available_codes == 0:
            flash('Sorry! This product is out of stock.', 'error')
            return redirect(url_for('dashboard'))
    
    order_id = generate_order_id(current_user.user_id)
    orders_collection.insert_one({
        'user_id': current_user.user_id,
        'product_id': product_id,
        'variant_id': None,
        'variant_name': None,
        'variant_quantity': 1,
        'order_id': order_id,
        'item_name': product['name'],
        'item_price': product['price'],
        'discount': 0,
        'coupon_code': None,
        'final_price': product['price'],
        'status': 'pending',
        'code_used': None,
        'created_at': datetime.utcnow()
    })
    
    return redirect(url_for('checkout', order_id=order_id))

# ============================================
# NOTIFICATION API
# ============================================

@app.route('/notifications')
@login_required
def get_notifications():
    if notifications_collection is None:
        return jsonify([])
    
    notifications = list(notifications_collection.find({'user_id': current_user.user_id}).sort('created_at', -1))
    return jsonify([{
        'id': str(n['_id']),
        'title': n.get('title'),
        'message': n.get('message'),
        'is_read': n.get('is_read', False),
        'created_at': n.get('created_at')
    } for n in notifications])

@app.route('/notifications/<notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    if notifications_collection is None:
        return jsonify({'error': 'Database not connected'}), 500
    
    notification = notifications_collection.find_one({'_id': ObjectId(notif_id)})
    if notification and notification.get('user_id') == current_user.user_id:
        notifications_collection.update_one({'_id': ObjectId(notif_id)}, {'$set': {'is_read': True}})
        return jsonify({'success': True})
    return jsonify({'error': 'Not found'}), 404

@app.route('/notifications/mark-read', methods=['POST'])
@login_required
def mark_all_read():
    if notifications_collection is None:
        return jsonify({'error': 'Database not connected'}), 500
    
    notifications_collection.update_many(
        {'user_id': current_user.user_id, 'is_read': False},
        {'$set': {'is_read': True}}
    )
    return jsonify({'success': True})

# ============================================
# ADMIN ROUTES
# ============================================

@app.route('/admin')
@login_required
def admin_dashboard():
    if users_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    users = list(users_collection.find())
    categories = list(categories_collection.find())
    products = list(products_collection.find())
    orders = list(orders_collection.find().sort('created_at', -1))
    popup = popup_collection.find_one()
    maintenance = maintenance_collection.find_one({'key': 'maintenance'})
    banners = list(banners_collection.find())
    notifications = list(notifications_collection.find().sort('created_at', -1))
    coupons = list(coupons_collection.find())
    variants = list(variants_collection.find())
    
    # ===== FIX: Product এর সাথে Category Data যোগ করুন =====
    category_dict = {str(cat['_id']): cat for cat in categories}
    for product in products:
        cat_id = product.get('category_id')
        if cat_id and cat_id in category_dict:
            product['category_name'] = category_dict[cat_id].get('name', 'N/A')
            product['category_icon'] = category_dict[cat_id].get('icon', 'fa-tag')
        else:
            product['category_name'] = 'N/A'
            product['category_icon'] = 'fa-tag'
    
    # ===== FIX: Variant এর সাথে Product Data যোগ করুন =====
    product_dict = {str(p['_id']): p for p in products}
    for variant in variants:
        prod_id = variant.get('product_id')
        if prod_id and prod_id in product_dict:
            variant['product_name'] = product_dict[prod_id].get('name', 'N/A')
            variant['product'] = product_dict[prod_id]
        else:
            variant['product_name'] = 'N/A'
            variant['product'] = None
    
    # ===== FIX: Order এর সাথে User Data যোগ করুন =====
    user_dict_by_id = {str(u['_id']): u for u in users}
    for order in orders:
        if order.get('user_id'):
            user = users_collection.find_one({'user_id': order['user_id']})
            if user:
                order['user'] = user
            else:
                order['user'] = None
    
    total_users = users_collection.count_documents({})
    total_orders = orders_collection.count_documents({})
    total_revenue = sum(o.get('item_price', 0) for o in orders_collection.find())
    
    # User dict for admin.html (used by coupons)
    user_dict_for_template = {str(u['_id']): u for u in users}
    # Also add user_id lookup
    for u in users:
        user_dict_for_template[str(u.get('user_id'))] = u
    
    return render_template('admin.html',
                         users=users,
                         categories=categories,
                         products=products,
                         orders=orders,
                         popup=popup,
                         maintenance=maintenance,
                         banners=banners,
                         notifications=notifications,
                         coupons=coupons,
                         variants=variants,
                         user_dict=user_dict_for_template,
                         total_users=total_users,
                         total_orders=total_orders,
                         total_revenue=total_revenue)

# ============================================
# ADMIN CATEGORY ROUTES
# ============================================

@app.route('/admin/delete-category/<category_id>', methods=['POST'])
@login_required
def delete_category(category_id):
    if categories_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    category = categories_collection.find_one({'_id': ObjectId(category_id)})
    if not category:
        flash('Category not found!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    products_count = products_collection.count_documents({'category_id': category_id})
    if products_count > 0:
        flash(f'Cannot delete "{category["name"]}" because it has {products_count} products. Delete products first or reassign them.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    categories_collection.delete_one({'_id': ObjectId(category_id)})
    flash(f'Category "{category["name"]}" deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/create-category', methods=['POST'])
@login_required
def create_category():
    if categories_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    name = request.form.get('name')
    icon = request.form.get('icon', 'fa-tag')
    
    if categories_collection.find_one({'name': name}):
        flash('Category already exists!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    categories_collection.insert_one({
        'name': name,
        'icon': icon,
        'created_at': datetime.utcnow()
    })
    
    flash('Category created successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# ============================================
# ADMIN COUPON ROUTES
# ============================================

@app.route('/admin/create-coupon', methods=['POST'])
@login_required
def create_coupon():
    if coupons_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    code = request.form.get('code', '').strip().upper()
    discount_percent = float(request.form.get('discount_percent', 0))
    max_discount = request.form.get('max_discount')
    
    if not code:
        flash('Coupon code is required!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    if discount_percent <= 0 or discount_percent > 100:
        flash('Discount must be between 1 and 100!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    if coupons_collection.find_one({'code': code}):
        flash(f'Coupon "{code}" already exists!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    coupons_collection.insert_one({
        'code': code,
        'discount_percent': discount_percent,
        'max_discount': float(max_discount) if max_discount else None,
        'is_active': True,
        'used_by': None,
        'used_at': None,
        'created_at': datetime.utcnow()
    })
    
    flash(f'Coupon "{code}" created successfully! ({discount_percent}% discount)', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-coupon/<coupon_id>', methods=['POST'])
@login_required
def delete_coupon(coupon_id):
    if coupons_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    coupon = coupons_collection.find_one({'_id': ObjectId(coupon_id)})
    if not coupon:
        flash('Coupon not found!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    coupons_collection.delete_one({'_id': ObjectId(coupon_id)})
    flash('Coupon deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# ============================================
# ADMIN VARIANT ROUTES
# ============================================

@app.route('/admin/add-variant-page')
@login_required
def add_variant_page():
    if variants_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    products = list(products_collection.find())
    variants = list(variants_collection.find())
    return render_template('add-variant.html', products=products, variants=variants)

@app.route('/admin/add-variant', methods=['POST'])
@login_required
def add_variant():
    if variants_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    try:
        product_id = request.form.get('product_id')
        name = request.form.get('name', '').strip()
        price = float(request.form.get('price', 0))
        validity = request.form.get('validity', '').strip()
        quantity = int(request.form.get('quantity', 1))
        
        if not product_id or not name or price <= 0:
            flash('Product, name and valid price are required!', 'error')
            return redirect(url_for('admin_dashboard'))
        
        product = products_collection.find_one({'_id': ObjectId(product_id)})
        if not product:
            flash('Product not found!', 'error')
            return redirect(url_for('admin_dashboard'))
        
        products_collection.update_one({'_id': ObjectId(product_id)}, {'$set': {'has_variants': True}})
        
        variants_collection.insert_one({
            'product_id': product_id,
            'name': name,
            'price': price,
            'validity': validity,
            'quantity': quantity,
            'is_active': True,
            'created_at': datetime.utcnow()
        })
        
        flash(f'✅ Variant "{name}" added successfully! (Price: ৳{price}, Quantity: {quantity})', 'success')
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-variant/<variant_id>', methods(['POST'])
@login_required
def delete_variant(variant_id):
    if variants_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    variants_collection.delete_one({'_id': ObjectId(variant_id)})
    flash('Variant deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# ============================================
# ADMIN PRODUCT ROUTES
# ============================================

@app.route('/admin/create-product', methods=['POST'])
@login_required
def create_product():
    if products_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    name = request.form.get('name')
    price = float(request.form.get('price', 0))
    logo = request.form.get('logo')
    description = request.form.get('description')
    product_type = request.form.get('product_type')
    category_id = request.form.get('category_id')
    has_variants = request.form.get('has_variants') == 'on'
    
    category = categories_collection.find_one({'_id': ObjectId(category_id)})
    if not category:
        flash('Category not found!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    product_data = {
        'name': name,
        'price': price,
        'logo': logo,
        'description': description,
        'product_type': product_type,
        'file_link': '',
        'category_id': category_id,
        'is_active': True,
        'has_variants': has_variants,
        'created_at': datetime.utcnow()
    }
    
    if product_type == 'file':
        product_data['file_link'] = request.form.get('file_link')
    
    result = products_collection.insert_one(product_data)
    product_id = str(result.inserted_id)
    
    if product_type == 'code':
        codes_text = request.form.get('codes')
        added = add_codes_to_product(product_id, codes_text)
        if added > 0:
            flash(f'Added {added} codes!', 'success')
    
    users = users_collection.find()
    for user in users:
        notifications_collection.insert_one({
            'user_id': user.get('user_id'),
            'title': 'New Product Added!',
            'message': f'Check out our new product: {name}',
            'is_read': False,
            'created_at': datetime.utcnow()
        })
    
    flash('Product created successfully! Notification sent to all users.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-product/<product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    if products_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    products_collection.delete_one({'_id': ObjectId(product_id)})
    airdrop_codes_collection.delete_many({'product_id': product_id})
    variants_collection.delete_many({'product_id': product_id})
    
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update-product/<product_id>', methods=['POST'])
@login_required
def update_product(product_id):
    if products_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    product = products_collection.find_one({'_id': ObjectId(product_id)})
    if not product:
        flash('Product not found!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    update_data = {
        'name': request.form.get('name'),
        'price': float(request.form.get('price', 0)),
        'logo': request.form.get('logo'),
        'description': request.form.get('description'),
        'category_id': request.form.get('category_id'),
        'has_variants': request.form.get('has_variants') == 'on'
    }
    
    if product.get('product_type') == 'file':
        new_file_link = request.form.get('file_link')
        if new_file_link:
            update_data['file_link'] = new_file_link
    
    products_collection.update_one({'_id': ObjectId(product_id)}, {'$set': update_data})
    
    if product.get('product_type') == 'code':
        new_codes = request.form.get('new_codes')
        if new_codes:
            added = add_codes_to_product(product_id, new_codes)
            if added > 0:
                flash(f'Successfully added {added} new codes!', 'success')
    
    flash('Product updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/get-product/<product_id>')
@login_required
def get_product(product_id):
    if products_collection is None or not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    product = products_collection.find_one({'_id': ObjectId(product_id)})
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    available_codes = []
    if product.get('product_type') == 'code':
        codes = list(airdrop_codes_collection.find({'product_id': product_id, 'is_used': False}))
        available_codes = [c['code'] for c in codes]
    
    used_codes_count = airdrop_codes_collection.count_documents({'product_id': product_id, 'is_used': True})
    
    variants = list(variants_collection.find({'product_id': product_id}))
    variants_data = [{
        'id': str(v['_id']),
        'name': v.get('name'),
        'price': v.get('price'),
        'validity': v.get('validity'),
        'quantity': v.get('quantity', 1),
        'is_active': v.get('is_active', True)
    } for v in variants]
    
    return jsonify({
        'id': product_id,
        'name': product.get('name'),
        'price': product.get('price'),
        'logo': product.get('logo'),
        'description': product.get('description'),
        'category_id': product.get('category_id'),
        'product_type': product.get('product_type'),
        'file_link': product.get('file_link'),
        'has_variants': product.get('has_variants', False),
        'available_codes': available_codes,
        'total_available': len(available_codes),
        'used_codes': used_codes_count,
        'variants': variants_data
    })

@app.route('/admin/add-codes', methods=['POST'])
@login_required
def add_codes():
    if airdrop_codes_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    product_id = request.form.get('product_id')
    codes_text = request.form.get('codes')
    
    added = add_codes_to_product(product_id, codes_text)
    product = products_collection.find_one({'_id': ObjectId(product_id)})
    flash(f'Successfully added {added} codes to {product["name"]}!', 'success')
    return redirect(url_for('admin_dashboard'))

# ============================================
# ADMIN NOTIFICATION ROUTES
# ============================================

@app.route('/admin/send-notification', methods=['POST'])
@login_required
def send_notification():
    if notifications_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    title = request.form.get('title')
    message = request.form.get('message')
    user_id = request.form.get('user_id')
    
    if user_id == 'all':
        users = users_collection.find()
        for user in users:
            notifications_collection.insert_one({
                'user_id': user.get('user_id'),
                'title': title,
                'message': message,
                'is_read': False,
                'created_at': datetime.utcnow()
            })
    else:
        notifications_collection.insert_one({
            'user_id': int(user_id),
            'title': title,
            'message': message,
            'is_read': False,
            'created_at': datetime.utcnow()
        })
    
    flash('Notification sent successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# ============================================
# ADMIN POPUP ROUTES
# ============================================

@app.route('/admin/popup-on', methods=['POST'])
@login_required
def popup_on():
    if popup_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    popup = popup_collection.find_one()
    if popup:
        popup_collection.update_one({'_id': popup['_id']}, {'$set': {'is_enabled': True}})
    else:
        popup_collection.insert_one({'is_enabled': True})
    
    flash('Popup is now ON!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/popup-off', methods=['POST'])
@login_required
def popup_off():
    if popup_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    popup = popup_collection.find_one()
    if popup:
        popup_collection.update_one({'_id': popup['_id']}, {'$set': {'is_enabled': False}})
    else:
        popup_collection.insert_one({'is_enabled': False})
    
    flash('Popup is now OFF!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update-popup', methods=['POST'])
@login_required
def update_popup():
    if popup_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    popup = popup_collection.find_one()
    update_data = {
        'message': request.form.get('message'),
        'button_text': request.form.get('button_text', 'Join Now'),
        'button_link': request.form.get('button_link'),
        'photo': request.form.get('photo')
    }
    
    if popup:
        popup_collection.update_one({'_id': popup['_id']}, {'$set': update_data})
    else:
        update_data['is_enabled'] = False
        popup_collection.insert_one(update_data)
    
    flash('Popup settings updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# ============================================
# ADMIN MAINTENANCE ROUTES
# ============================================

@app.route('/admin/maintenance-on', methods=['POST'])
@login_required
def maintenance_on():
    if maintenance_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    maintenance = maintenance_collection.find_one({'key': 'maintenance'})
    if maintenance:
        maintenance_collection.update_one({'_id': maintenance['_id']}, {'$set': {'value': True}})
    else:
        maintenance_collection.insert_one({'key': 'maintenance', 'value': True})
    
    flash('Maintenance mode is now ON!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/maintenance-off', methods=['POST'])
@login_required
def maintenance_off():
    if maintenance_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    maintenance = maintenance_collection.find_one({'key': 'maintenance'})
    if maintenance:
        maintenance_collection.update_one({'_id': maintenance['_id']}, {'$set': {'value': False}})
    else:
        maintenance_collection.insert_one({'key': 'maintenance', 'value': False})
    
    flash('Maintenance mode is now OFF!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update-maintenance', methods=['POST'])
@login_required
def update_maintenance():
    if maintenance_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    maintenance = maintenance_collection.find_one({'key': 'maintenance'})
    update_data = {
        'message': request.form.get('message'),
        'photo': request.form.get('photo')
    }
    
    if maintenance:
        maintenance_collection.update_one({'_id': maintenance['_id']}, {'$set': update_data})
    else:
        update_data['key'] = 'maintenance'
        update_data['value'] = False
        maintenance_collection.insert_one(update_data)
    
    flash('Maintenance settings updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# ============================================
# ADMIN BANNER ROUTES
# ============================================

@app.route('/admin/add-banner', methods=['POST'])
@login_required
def add_banner():
    if banners_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    image = request.form.get('image')
    title = request.form.get('title')
    link = request.form.get('link')
    order = int(request.form.get('order', 0))
    
    banners_collection.insert_one({
        'image': image,
        'title': title,
        'link': link,
        'order': order,
        'is_active': True,
        'created_at': datetime.utcnow()
    })
    
    flash('Banner added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-banner/<banner_id>', methods=['POST'])
@login_required
def delete_banner(banner_id):
    if banners_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    banners_collection.delete_one({'_id': ObjectId(banner_id)})
    flash('Banner deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# ============================================
# ADMIN USER BALANCE ROUTES
# ============================================

@app.route('/admin/update-user-balance', methods=['POST'])
@login_required
def update_user_balance():
    if users_collection is None or not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    user_id = int(request.form.get('user_id'))
    amount = float(request.form.get('amount', 0))
    action = request.form.get('action')
    
    user = users_collection.find_one({'user_id': user_id})
    if not user:
        flash('User not found!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    current_balance = user.get('balance', 0)
    if action == 'add':
        new_balance = current_balance + amount
    else:
        new_balance = max(0, current_balance - amount)
    
    users_collection.update_one({'_id': user['_id']}, {'$set': {'balance': new_balance}})
    flash(f'Balance updated for {user["username"]}!', 'success')
    return redirect(url_for('admin_dashboard'))

# ============================================
# RUN APP
# ============================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
