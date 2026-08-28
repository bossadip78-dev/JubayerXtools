from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import secrets
import string
import requests
import time
import random
import json
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'JubayerXtools-Secret-Key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jubayerxtools.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

# ============================================
# GOOGLE OAUTH CONFIG
# ============================================
GOOGLE_CLIENT_ID = '496748598869-ssp5n2hul7te1153qvg0htk0kgr0v2c0.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET = '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'
GOOGLE_REDIRECT_URI = 'http://localhost:5000/google-callback'

# ============================================
# BOHUDUR PAYMENT CONFIG
# ============================================
BOHUDUR_API_KEY = "t3Q7lrUau2E8dHg0oyjc4pvKWsRAOqmD"
BOHUDUR_API_URL = "https://request.bohudur.one/create/v2/"

# ============================================
# WEBHOOK URL
# ============================================
WEBHOOK_URL = "https://jubayerxtools-webhook.vercel.app"

# ============================================
# DATABASE MODELS
# ============================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200))
    balance = db.Column(db.Float, default=0.0)
    phone = db.Column(db.String(20))
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='user', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('Transaction', backref='user', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    icon = db.Column(db.String(100), default='fa-tag')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    products = db.relationship('Product', backref='category', lazy=True, cascade='all, delete-orphan')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    logo = db.Column(db.String(200))
    description = db.Column(db.Text)
    product_type = db.Column(db.String(20), default='file')
    file_link = db.Column(db.String(500))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    has_variants = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='product', lazy=True, cascade='all, delete-orphan')
    codes = db.relationship('AirdropCode', backref='product', lazy=True, cascade='all, delete-orphan')
    variants = db.relationship('ProductVariant', backref='product', lazy=True, cascade='all, delete-orphan')

class ProductVariant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    validity = db.Column(db.String(50))
    quantity = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='variant', lazy=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variant.id'), nullable=True)
    variant_name = db.Column(db.String(100))
    variant_quantity = db.Column(db.Integer, default=1)
    order_id = db.Column(db.String(50), unique=True)
    item_name = db.Column(db.String(100))
    item_price = db.Column(db.Float)
    discount = db.Column(db.Float, default=0.0)
    coupon_code = db.Column(db.String(50), nullable=True)
    final_price = db.Column(db.Float)
    status = db.Column(db.String(20), default='pending')
    code_used = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(20))
    description = db.Column(db.String(200))
    status = db.Column(db.String(20), default='completed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    discount_percent = db.Column(db.Float, nullable=False)
    max_discount = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    used_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', foreign_keys=[used_by], backref='used_coupons')

class PopupSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    is_enabled = db.Column(db.Boolean, default=False)
    photo = db.Column(db.String(200))
    message = db.Column(db.Text, default='Join our Telegram channel for updates!')
    button_text = db.Column(db.String(50), default='Join Now')
    button_link = db.Column(db.String(500), default='https://t.me/jubayerxtools')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MaintenanceSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    is_enabled = db.Column(db.Boolean, default=False)
    message = db.Column(db.Text, default='Site is under maintenance. Please check back later.')
    photo = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AirdropCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), unique=True, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    used_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Banner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(100))
    link = db.Column(db.String(500))
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ============================================
# HELPER FUNCTIONS
# ============================================

def add_codes_to_product(product_id, codes_text):
    if not codes_text:
        return 0
    codes = [c.strip() for c in codes_text.split('\n') if c.strip()]
    added = 0
    for code in codes:
        if code:
            existing = AirdropCode.query.filter_by(code=code).first()
            if not existing:
                airdrop = AirdropCode(
                    code=code,
                    product_id=product_id,
                    is_used=False
                )
                db.session.add(airdrop)
                added += 1
    db.session.commit()
    return added

def validate_coupon(coupon_code, user_id):
    coupon = Coupon.query.filter_by(code=coupon_code.upper(), is_active=True).first()
    if not coupon:
        return None, "Invalid coupon code!"
    if coupon.used_by is not None:
        return None, "This coupon has already been used!"
    return coupon, None

def calculate_discount(price, coupon):
    discount_amount = price * (coupon.discount_percent / 100)
    if coupon.max_discount and discount_amount > coupon.max_discount:
        discount_amount = coupon.max_discount
    return discount_amount

def is_maintenance_on():
    maintenance = MaintenanceSetting.query.first()
    return maintenance and maintenance.is_enabled

def generate_order_id(user_id: int) -> str:
    """ইউনিক অর্ডার আইডি জেনারেট করে"""
    return f"JX{int(time.time())}{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"

def create_bohudur_payment(amount: int, user_id: int, username: str = None) -> dict:
    """
    Bohudur API ব্যবহার করে পেমেন্ট লিংক তৈরি করে
    """
    try:
        order_id = generate_order_id(user_id)
        my_reference = f"JX_{amount}TAKA_{order_id}_{user_id}"
        
        # Webhook URL
        base_url = WEBHOOK_URL
        redirect_url = f"{base_url}/payment/success?paymentkey={my_reference}&user_id={user_id}&amount={amount}"
        cancel_url = f"{base_url}/payment/cancel"
        
        payload = {
            "full_name": username or f"User_{user_id}",
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
        
        print(f"Bohudur Response: {result}")  # Debug
        
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
# CREATE TABLES & DEFAULT DATA
# ============================================

with app.app_context():
    db.create_all()
    
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@jubayerxtools.com',
            password_hash=generate_password_hash('admin123'),
            is_admin=True,
            balance=999999
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin created: admin / admin123")
    
    default_categories = ['Others Item', 'Non Root Panel', 'Root Panel', 'iPhone Panel', 'PC Panel']
    default_logo = 'https://i.ibb.co.com/KxSnyTjy/635d5463-6cd3-485e-bd05-907c07468d3a.png'
    
    default_products = [
        ('FF Guild Glory', 130.00, 'Others Item', 'Free Fire Guild Level Up Bot. Guild Glory'),
        ('BalaMod Android', 80.00, 'Non Root Panel', 'Premium Android mod panel'),
        ('HG CHEAT', 120.00, 'Root Panel', 'Root panel cheat tool'),
        ('Fluorite IOS', 110.00, 'iPhone Panel', 'iOS fluorite panel'),
        ('PC Panel Pro', 200.00, 'PC Panel', 'Pro PC gaming panel'),
    ]
    
    for cat_name in default_categories:
        if not Category.query.filter_by(name=cat_name).first():
            cat = Category(name=cat_name, icon='fa-tag')
            db.session.add(cat)
    db.session.commit()
    
    for name, price, cat_name, desc in default_products:
        category = Category.query.filter_by(name=cat_name).first()
        if category and not Product.query.filter_by(name=name).first():
            product = Product(
                name=name,
                price=price,
                logo=default_logo,
                description=desc,
                product_type='file',
                category_id=category.id,
                is_active=True,
                has_variants=False
            )
            db.session.add(product)
    db.session.commit()
    
    if not Banner.query.first():
        banners = [
            Banner(
                image='https://i.ibb.co.com/KxSnyTjy/635d5463-6cd3-485e-bd05-907c07468d3a.png',
                title='Welcome to JubayerXtools',
                order=0,
                is_active=True
            ),
            Banner(
                image='https://i.ibb.co.com/KxSnyTjy/635d5463-6cd3-485e-bd05-907c07468d3a.png',
                title='Premium Products Available',
                order=1,
                is_active=True
            )
        ]
        for banner in banners:
            db.session.add(banner)
        db.session.commit()
    
    if not PopupSetting.query.first():
        db.session.add(PopupSetting(is_enabled=False))
        db.session.commit()
    
    if not MaintenanceSetting.query.first():
        db.session.add(MaintenanceSetting(is_enabled=False))
        db.session.commit()

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
    
    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User.query.filter_by(email=email).first()
        if user:
            user.google_id = google_id
        else:
            user = User(
                email=email,
                username=username,
                google_id=google_id,
                balance=0
            )
            db.session.add(user)
        db.session.commit()
    
    login_user(user)
    flash('Google login successful! Redirecting to dashboard...', 'success')
    return redirect(url_for('login_page'))

# ============================================
# MAIN ROUTES
# ============================================

@app.route('/')
def index():
    maintenance = MaintenanceSetting.query.first()
    if maintenance and maintenance.is_enabled:
        return render_template('maintenance.html', maintenance=maintenance)
    banners = Banner.query.filter_by(is_active=True).order_by(Banner.order).all()
    return render_template('landing.html', user=current_user, banners=banners)

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    maintenance = MaintenanceSetting.query.first()
    
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard' if current_user.is_admin else 'dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'login':
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                if maintenance and maintenance.is_enabled and not user.is_admin:
                    flash('Site is under maintenance. Only admin can access.', 'error')
                    return render_template('login.html', active_tab='login')
                login_user(user)
                return redirect(url_for('admin_dashboard' if user.is_admin else 'dashboard'))
            flash('Invalid username or password!', 'error')
        
        elif action == 'register':
            if maintenance and maintenance.is_enabled:
                flash('Registration is disabled during maintenance!', 'error')
                return render_template('login.html', active_tab='login')
            
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
            elif User.query.filter_by(username=username).first():
                flash('Username already exists!', 'error')
            elif User.query.filter_by(email=email).first():
                flash('Email already registered!', 'error')
            else:
                new_user = User(
                    username=username,
                    email=email,
                    phone=phone_digits,
                    password_hash=generate_password_hash(password),
                    balance=0
                )
                db.session.add(new_user)
                db.session.commit()
                flash('Registration successful! Please login.', 'success')
                return render_template('login.html', active_tab='login')
    
    return render_template('login.html', active_tab='login')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if is_maintenance_on() and not current_user.is_admin:
        flash('Site is under maintenance. Please check back later.', 'error')
        return redirect(url_for('login_page'))
    
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    categories = Category.query.all()
    products = Product.query.filter_by(is_active=True).all()
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.created_at.desc()).all()
    popup = PopupSetting.query.first()
    banners = Banner.query.filter_by(is_active=True).order_by(Banner.order).all()
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    
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
    if is_maintenance_on() and not current_user.is_admin:
        flash('Site is under maintenance. Please check back later.', 'error')
        return redirect(url_for('login_page'))
    
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    
    total_orders = len(orders)
    completed_orders = len([o for o in orders if o.status == 'completed'])
    total_spent = sum(o.item_price for o in orders if o.status == 'completed')
    total_deposit = sum(t.amount for t in transactions if t.type == 'add')
    
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
    if is_maintenance_on() and not current_user.is_admin:
        flash('Site is under maintenance. Please check back later.', 'error')
        return redirect(url_for('login_page'))
    
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    
    orders_data = []
    for order in orders:
        orders_data.append({
            'id': order.id,
            'order_id': order.order_id,
            'item_name': order.item_name,
            'variant_name': order.variant_name,
            'variant_quantity': order.variant_quantity,
            'item_price': order.item_price,
            'discount': order.discount,
            'coupon_code': order.coupon_code,
            'final_price': order.final_price,
            'status': order.status,
            'code_used': order.code_used,
            'created_at': order.created_at.strftime('%Y-%m-%d %H:%M'),
            'product': {
                'product_type': order.product.product_type if order.product else 'file',
                'file_link': order.product.file_link if order.product and order.product.file_link else None
            }
        })
    
    return render_template('my-orders.html', user=current_user, orders=orders, orders_data=orders_data)

@app.route('/my-transactions')
@login_required
def my_transactions():
    if is_maintenance_on() and not current_user.is_admin:
        flash('Site is under maintenance. Please check back later.', 'error')
        return redirect(url_for('login_page'))
    
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.created_at.desc()).all()
    
    total_deposit = sum(t.amount for t in transactions if t.type == 'add')
    total_spent = sum(t.amount for t in transactions if t.type == 'purchase')
    
    return render_template('my-transactions.html',
                         user=current_user,
                         transactions=transactions,
                         total_deposit=total_deposit,
                         total_spent=total_spent)

@app.route('/add-balance')
@login_required
def add_balance():
    if is_maintenance_on() and not current_user.is_admin:
        flash('Site is under maintenance. Please check back later.', 'error')
        return redirect(url_for('login_page'))
    
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    return render_template('add-balance.html', user=current_user)

# ============================================
# BOHUDUR PAYMENT ROUTES
# ============================================

pending_payments = {}

@app.route('/create-payment', methods=['POST'])
@login_required
def create_payment():
    """Create Bohudur payment link"""
    if is_maintenance_on() and not current_user.is_admin:
        return jsonify({'error': 'Site is under maintenance'}), 503
    
    try:
        data = request.get_json()
        amount = int(data.get('amount', 0))
        
        if amount < 10:
            return jsonify({'error': 'Minimum deposit is ৳10!'}), 400
        
        if amount > 50000:
            return jsonify({'error': 'Maximum deposit is ৳50,000!'}), 400
        
        result = create_bohudur_payment(
            amount=amount,
            user_id=current_user.id,
            username=current_user.username
        )
        
        if result['success']:
            pending_payments[result['paymentkey']] = {
                'user_id': current_user.id,
                'amount': amount,
                'order_id': result['order_id'],
                'my_reference': result['my_reference'],
                'created_at': datetime.utcnow().isoformat()
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

# ============================================
# TERMS, PRIVACY, SUPPORT ROUTES
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
# VARIANT ROUTES (User Side)
# ============================================

@app.route('/variants/<int:product_id>')
@login_required
def variants_page(product_id):
    if is_maintenance_on() and not current_user.is_admin:
        flash('Site is under maintenance. Please check back later.', 'error')
        return redirect(url_for('login_page'))
    
    product = Product.query.get_or_404(product_id)
    
    if not product.has_variants:
        flash('This product does not have variants.', 'error')
        return redirect(url_for('dashboard'))
    
    variants = ProductVariant.query.filter_by(product_id=product_id, is_active=True).all()
    
    if not variants:
        flash('No variants available for this product.', 'error')
        return redirect(url_for('dashboard'))
    
    return render_template('variants.html', user=current_user, product=product, variants=variants)

@app.route('/select-variant', methods=['POST'])
@login_required
def select_variant():
    if is_maintenance_on() and not current_user.is_admin:
        flash('Site is under maintenance. Please check back later.', 'error')
        return redirect(url_for('login_page'))
    
    variant_id = request.form.get('variant_id')
    product_id = request.form.get('product_id')
    
    if not variant_id or not product_id:
        flash('Invalid selection!', 'error')
        return redirect(url_for('dashboard'))
    
    product = Product.query.get_or_404(product_id)
    variant = ProductVariant.query.get_or_404(variant_id)
    
    if variant.product_id != product.id:
        flash('Invalid variant selection!', 'error')
        return redirect(url_for('dashboard'))
    
    if product.product_type == 'code':
        available_codes = AirdropCode.query.filter_by(
            product_id=product.id,
            is_used=False
        ).count()
        
        if available_codes < variant.quantity:
            flash(f'Sorry! Only {available_codes} codes available. You need {variant.quantity}.', 'error')
            return redirect(url_for('variants_page', product_id=product.id))
    
    order_id = 'JX' + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    order = Order(
        user_id=current_user.id,
        product_id=product.id,
        variant_id=variant.id,
        variant_name=variant.name,
        variant_quantity=variant.quantity,
        order_id=order_id,
        item_name=f"{product.name} - {variant.name}",
        item_price=variant.price,
        final_price=variant.price,
        status='pending'
    )
    db.session.add(order)
    db.session.commit()
    
    return redirect(url_for('checkout', order_id=order_id))

# ============================================
# CHECKOUT & PAYMENT ROUTES
# ============================================

@app.route('/checkout/<order_id>')
@login_required
def checkout(order_id):
    if is_maintenance_on() and not current_user.is_admin:
        flash('Site is under maintenance. Please check back later.', 'error')
        return redirect(url_for('login_page'))
    
    order = Order.query.filter_by(order_id=order_id, user_id=current_user.id).first()
    if not order:
        flash('Order not found!', 'error')
        return redirect(url_for('dashboard'))
    
    return render_template('checkout.html', user=current_user, order=order)

@app.route('/apply-coupon', methods=['POST'])
@login_required
def apply_coupon():
    data = request.get_json()
    order_id = data.get('order_id')
    coupon_code = data.get('coupon_code', '').strip().upper()
    
    order = Order.query.filter_by(order_id=order_id, user_id=current_user.id).first()
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    if order.status != 'pending':
        return jsonify({'error': 'Order already processed'}), 400
    
    coupon, error = validate_coupon(coupon_code, current_user.id)
    if error:
        return jsonify({'error': error}), 400
    
    discount_amount = calculate_discount(order.item_price, coupon)
    final_price = order.item_price - discount_amount
    
    order.discount = discount_amount
    order.coupon_code = coupon_code
    order.final_price = final_price
    
    coupon.used_by = current_user.id
    coupon.used_at = datetime.utcnow()
    coupon.is_active = False
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'discount': discount_amount,
        'final_price': final_price,
        'discount_percent': coupon.discount_percent
    })

@app.route('/remove-coupon', methods=['POST'])
@login_required
def remove_coupon():
    data = request.get_json()
    order_id = data.get('order_id')
    
    order = Order.query.filter_by(order_id=order_id, user_id=current_user.id).first()
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    if not order.coupon_code:
        return jsonify({'error': 'No coupon applied'}), 400
    
    coupon = Coupon.query.filter_by(code=order.coupon_code).first()
    if coupon:
        coupon.is_active = True
        coupon.used_by = None
        coupon.used_at = None
    
    order.discount = 0.0
    order.coupon_code = None
    order.final_price = order.item_price
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'final_price': order.item_price
    })

@app.route('/success/<order_id>')
@login_required
def success_page(order_id):
    if is_maintenance_on() and not current_user.is_admin:
        flash('Site is under maintenance. Please check back later.', 'error')
        return redirect(url_for('login_page'))
    
    order = Order.query.filter_by(order_id=order_id, user_id=current_user.id).first()
    if not order:
        flash('Order not found!', 'error')
        return redirect(url_for('dashboard'))
    
    if order.status != 'completed':
        flash('Order not completed!', 'error')
        return redirect(url_for('dashboard'))
    
    return render_template('success.html', user=current_user, order=order)

@app.route('/process-payment/<order_id>', methods=['POST'])
@login_required
def process_payment(order_id):
    order = Order.query.filter_by(order_id=order_id, user_id=current_user.id).first()
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    if order.status == 'completed':
        return jsonify({'error': 'Order already completed'}), 400
    
    amount_to_pay = order.final_price if order.final_price else order.item_price
    
    if current_user.balance < amount_to_pay:
        return jsonify({'error': 'Insufficient balance!'}), 400
    
    current_user.balance -= amount_to_pay
    order.status = 'completed'
    order.final_price = amount_to_pay
    
    if order.product.product_type == 'code':
        quantity = order.variant_quantity or 1
        available_codes = AirdropCode.query.filter_by(
            product_id=order.product_id, 
            is_used=False
        ).limit(quantity).all()
        
        if len(available_codes) >= quantity:
            codes_list = []
            for code_obj in available_codes:
                codes_list.append(code_obj.code)
                code_obj.is_used = True
                code_obj.used_by = current_user.id
                code_obj.used_at = datetime.utcnow()
            order.code_used = ', '.join(codes_list)
        else:
            return jsonify({'error': 'Not enough codes available!'}), 400
    
    elif order.product.product_type == 'file':
        if order.product.file_link:
            order.code_used = order.product.file_link
    
    tx = Transaction(
        user_id=current_user.id,
        amount=amount_to_pay,
        type='purchase',
        description=f'Purchased {order.item_name} (x{order.variant_quantity or 1})' + 
                    (f' (Coupon: {order.coupon_code})' if order.coupon_code else ''),
        status='completed'
    )
    db.session.add(tx)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'order_id': order.order_id,
        'item_name': order.item_name,
        'amount': amount_to_pay,
        'discount': order.discount,
        'coupon_code': order.coupon_code,
        'quantity': order.variant_quantity or 1,
        'date': order.created_at.strftime('%Y-%m-%d %H:%M'),
        'code': order.code_used,
        'file_link': order.product.file_link if order.product.product_type == 'file' else None
    })

@app.route('/add-money', methods=['POST'])
@login_required
def add_money():
    if is_maintenance_on() and not current_user.is_admin:
        flash('Site is under maintenance. Please check back later.', 'error')
        return redirect(url_for('login_page'))
    
    amount = float(request.form.get('amount', 0))
    
    if amount < 10:
        flash('Minimum deposit is ৳10!', 'error')
        return redirect(url_for('add_balance'))
    
    if amount > 50000:
        flash('Maximum deposit is ৳50,000!', 'error')
        return redirect(url_for('add_balance'))
    
    if amount > 0:
        current_user.balance += amount
        tx = Transaction(
            user_id=current_user.id,
            amount=amount,
            type='add',
            description=f'Added ৳{amount} to balance',
            status='completed'
        )
        db.session.add(tx)
        db.session.commit()
        flash(f'Successfully added ৳{amount} to your balance!', 'success')
    
    return redirect(url_for('dashboard'))

@app.route('/buy-product/<int:product_id>', methods=['POST'])
@login_required
def buy_product(product_id):
    if is_maintenance_on() and not current_user.is_admin:
        flash('Site is under maintenance. Please check back later.', 'error')
        return redirect(url_for('login_page'))
    
    product = Product.query.get_or_404(product_id)
    
    if product.has_variants:
        return redirect(url_for('variants_page', product_id=product_id))
    
    if product.product_type == 'code':
        available_codes = AirdropCode.query.filter_by(
            product_id=product.id,
            is_used=False
        ).count()
        if available_codes == 0:
            flash('Sorry! This product is out of stock.', 'error')
            return redirect(url_for('dashboard'))
    
    order_id = 'JX' + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    order = Order(
        user_id=current_user.id,
        product_id=product.id,
        order_id=order_id,
        item_name=product.name,
        item_price=product.price,
        final_price=product.price,
        variant_quantity=1,
        status='pending'
    )
    db.session.add(order)
    db.session.commit()
    
    return redirect(url_for('checkout', order_id=order_id))

# ============================================
# ADMIN ROUTES
# ============================================

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    users = User.query.all()
    categories = Category.query.all()
    products = Product.query.all()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    popup = PopupSetting.query.first()
    maintenance = MaintenanceSetting.query.first()
    banners = Banner.query.all()
    notifications = Notification.query.order_by(Notification.created_at.desc()).all()
    coupons = Coupon.query.all()
    variants = ProductVariant.query.all()
    
    user_dict = {user.id: user for user in users}
    
    total_users = User.query.count()
    total_orders = Order.query.count()
    total_revenue = db.session.query(db.func.sum(Order.item_price)).scalar() or 0
    
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
                         user_dict=user_dict,
                         total_users=total_users,
                         total_orders=total_orders,
                         total_revenue=total_revenue)

@app.route('/admin/create-coupon', methods=['POST'])
@login_required
def create_coupon():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    code = request.form.get('code', '').strip().upper()
    discount_percent = float(request.form.get('discount_percent', 0))
    max_discount = request.form.get('max_discount')
    
    if not code:
        flash('Coupon code is required!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    if discount_percent <= 0 or discount_percent > 100:
        flash('Discount must be between 1 and 100!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    if Coupon.query.filter_by(code=code).first():
        flash(f'Coupon "{code}" already exists!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    coupon = Coupon(
        code=code,
        discount_percent=discount_percent,
        max_discount=float(max_discount) if max_discount else None,
        is_active=True
    )
    db.session.add(coupon)
    db.session.commit()
    
    flash(f'Coupon "{code}" created successfully! ({discount_percent}% discount)', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-coupon/<int:coupon_id>', methods=['POST'])
@login_required
def delete_coupon(coupon_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    coupon = Coupon.query.get_or_404(coupon_id)
    db.session.delete(coupon)
    db.session.commit()
    
    flash('Coupon deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# ============================================
# VARIANT ADMIN ROUTES
# ============================================

@app.route('/admin/add-variant-page')
@login_required
def add_variant_page():
    if not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    products = Product.query.all()
    variants = ProductVariant.query.all()
    return render_template('add-variant.html', products=products, variants=variants)

@app.route('/admin/add-variant', methods=['POST'])
@login_required
def add_variant():
    if not current_user.is_admin:
        flash('Access denied!', 'error')
        return redirect(url_for('login_page'))
    
    try:
        product_id = request.form.get('product_id')
        name = request.form.get('name', '').strip()
        price = request.form.get('price', '0')
        validity = request.form.get('validity', '').strip()
        quantity = request.form.get('quantity', '1')
        
        if not product_id:
            flash('Please select a product!', 'error')
            return redirect(url_for('admin_dashboard'))
        
        if not name:
            flash('Variant name is required!', 'error')
            return redirect(url_for('admin_dashboard'))
        
        try:
            price = float(price)
        except:
            flash('Valid price is required!', 'error')
            return redirect(url_for('admin_dashboard'))
        
        if price <= 0:
            flash('Price must be greater than 0!', 'error')
            return redirect(url_for('admin_dashboard'))
        
        try:
            quantity = int(quantity)
        except:
            quantity = 1
        
        if quantity < 1:
            quantity = 1
        
        product = Product.query.get(int(product_id))
        if not product:
            flash('Product not found!', 'error')
            return redirect(url_for('admin_dashboard'))
        
        product.has_variants = True
        
        variant = ProductVariant(
            product_id=int(product_id),
            name=name,
            price=price,
            validity=validity,
            quantity=quantity,
            is_active=True
        )
        
        db.session.add(variant)
        db.session.commit()
        
        flash(f'✅ Variant "{name}" added successfully! (Price: ৳{price}, Quantity: {quantity})', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-variant/<int:variant_id>', methods=['POST'])
@login_required
def delete_variant(variant_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    variant = ProductVariant.query.get_or_404(variant_id)
    db.session.delete(variant)
    db.session.commit()
    
    flash('Variant deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# ============================================
# OTHER ADMIN ROUTES
# ============================================

@app.route('/admin/send-notification', methods=['POST'])
@login_required
def send_notification():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    title = request.form.get('title')
    message = request.form.get('message')
    user_id = request.form.get('user_id')
    
    if user_id == 'all':
        users = User.query.all()
        for user in users:
            notif = Notification(
                user_id=user.id,
                title=title,
                message=message,
                is_read=False
            )
            db.session.add(notif)
    else:
        notif = Notification(
            user_id=int(user_id),
            title=title,
            message=message,
            is_read=False
        )
        db.session.add(notif)
    
    db.session.commit()
    flash('Notification sent successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/create-category', methods=['POST'])
@login_required
def create_category():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    name = request.form.get('name')
    icon = request.form.get('icon', 'fa-tag')
    
    category = Category(name=name, icon=icon)
    db.session.add(category)
    db.session.commit()
    
    flash('Category created successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/create-product', methods=['POST'])
@login_required
def create_product():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    name = request.form.get('name')
    price = float(request.form.get('price', 0))
    logo = request.form.get('logo')
    description = request.form.get('description')
    product_type = request.form.get('product_type')
    category_id = int(request.form.get('category_id'))
    has_variants = request.form.get('has_variants') == 'on'
    
    product = Product(
        name=name,
        price=price,
        logo=logo,
        description=description,
        product_type=product_type,
        category_id=category_id,
        is_active=True,
        has_variants=has_variants
    )
    
    if product_type == 'file':
        product.file_link = request.form.get('file_link')
    
    db.session.add(product)
    db.session.commit()
    
    if product_type == 'code':
        codes_text = request.form.get('codes')
        added = add_codes_to_product(product.id, codes_text)
        if added > 0:
            flash(f'Added {added} codes!', 'success')
    
    users = User.query.all()
    for user in users:
        notif = Notification(
            user_id=user.id,
            title=f'New Product Added!',
            message=f'Check out our new product: {name}',
            is_read=False
        )
        db.session.add(notif)
    db.session.commit()
    
    flash('Product created successfully! Notification sent to all users.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-product/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update-product/<int:product_id>', methods=['POST'])
@login_required
def update_product(product_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    product = Product.query.get_or_404(product_id)
    
    product.name = request.form.get('name')
    product.price = float(request.form.get('price', 0))
    product.logo = request.form.get('logo')
    product.description = request.form.get('description')
    product.category_id = int(request.form.get('category_id'))
    product.has_variants = request.form.get('has_variants') == 'on'
    
    if product.product_type == 'file':
        new_file_link = request.form.get('file_link')
        if new_file_link:
            product.file_link = new_file_link
    
    if product.product_type == 'code':
        new_codes = request.form.get('new_codes')
        if new_codes:
            added = add_codes_to_product(product.id, new_codes)
            if added > 0:
                flash(f'Successfully added {added} new codes!', 'success')
    
    db.session.commit()
    flash('Product updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/get-product/<int:product_id>')
@login_required
def get_product(product_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    product = Product.query.get_or_404(product_id)
    
    available_codes = []
    if product.product_type == 'code':
        codes = AirdropCode.query.filter_by(
            product_id=product.id,
            is_used=False
        ).all()
        available_codes = [c.code for c in codes]
    
    used_codes_count = AirdropCode.query.filter_by(
        product_id=product.id,
        is_used=True
    ).count()
    
    variants = ProductVariant.query.filter_by(product_id=product.id).all()
    variants_data = [{
        'id': v.id, 
        'name': v.name, 
        'price': v.price, 
        'validity': v.validity,
        'quantity': v.quantity,
        'is_active': v.is_active
    } for v in variants]
    
    return jsonify({
        'id': product.id,
        'name': product.name,
        'price': product.price,
        'logo': product.logo,
        'description': product.description,
        'category_id': product.category_id,
        'product_type': product.product_type,
        'file_link': product.file_link,
        'has_variants': product.has_variants,
        'available_codes': available_codes,
        'total_available': len(available_codes),
        'used_codes': used_codes_count,
        'variants': variants_data
    })

@app.route('/admin/add-codes', methods=['POST'])
@login_required
def add_codes():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    product_id = int(request.form.get('product_id'))
    codes_text = request.form.get('codes')
    
    added = add_codes_to_product(product_id, codes_text)
    product = Product.query.get(product_id)
    flash(f'Successfully added {added} codes to {product.name}!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/popup-on', methods=['POST'])
@login_required
def popup_on():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    popup = PopupSetting.query.first()
    if not popup:
        popup = PopupSetting()
        db.session.add(popup)
    
    popup.is_enabled = True
    db.session.commit()
    
    flash('Popup is now ON!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/popup-off', methods=['POST'])
@login_required
def popup_off():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    popup = PopupSetting.query.first()
    if not popup:
        popup = PopupSetting()
        db.session.add(popup)
    
    popup.is_enabled = False
    db.session.commit()
    
    flash('Popup is now OFF!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update-popup', methods=['POST'])
@login_required
def update_popup():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    popup = PopupSetting.query.first()
    if not popup:
        popup = PopupSetting()
        db.session.add(popup)
    
    popup.message = request.form.get('message')
    popup.button_text = request.form.get('button_text', 'Join Now')
    popup.button_link = request.form.get('button_link')
    popup.photo = request.form.get('photo')
    
    db.session.commit()
    
    flash('Popup settings updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/maintenance-on', methods=['POST'])
@login_required
def maintenance_on():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    maintenance = MaintenanceSetting.query.first()
    if not maintenance:
        maintenance = MaintenanceSetting()
        db.session.add(maintenance)
    
    maintenance.is_enabled = True
    db.session.commit()
    
    flash('Maintenance mode is now ON!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/maintenance-off', methods=['POST'])
@login_required
def maintenance_off():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    maintenance = MaintenanceSetting.query.first()
    if not maintenance:
        maintenance = MaintenanceSetting()
        db.session.add(maintenance)
    
    maintenance.is_enabled = False
    db.session.commit()
    
    flash('Maintenance mode is now OFF!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update-maintenance', methods=['POST'])
@login_required
def update_maintenance():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    maintenance = MaintenanceSetting.query.first()
    if not maintenance:
        maintenance = MaintenanceSetting()
        db.session.add(maintenance)
    
    maintenance.message = request.form.get('message')
    maintenance.photo = request.form.get('photo')
    
    db.session.commit()
    
    flash('Maintenance settings updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add-banner', methods=['POST'])
@login_required
def add_banner():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    image = request.form.get('image')
    title = request.form.get('title')
    link = request.form.get('link')
    order = int(request.form.get('order', 0))
    
    banner = Banner(
        image=image,
        title=title,
        link=link,
        order=order,
        is_active=True
    )
    db.session.add(banner)
    db.session.commit()
    
    flash('Banner added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-banner/<int:banner_id>', methods=['POST'])
@login_required
def delete_banner(banner_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    banner = Banner.query.get_or_404(banner_id)
    db.session.delete(banner)
    db.session.commit()
    
    flash('Banner deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update-user-balance', methods=['POST'])
@login_required
def update_user_balance():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    user_id = int(request.form.get('user_id'))
    amount = float(request.form.get('amount', 0))
    action = request.form.get('action')
    
    user = User.query.get_or_404(user_id)
    
    if action == 'add':
        user.balance += amount
    else:
        user.balance = max(0, user.balance - amount)
    
    db.session.commit()
    flash(f'Balance updated for {user.username}!', 'success')
    return redirect(url_for('admin_dashboard'))

# ============================================
# WEBHOOK HANDLER (Flask App)
# ============================================

@app.route('/payment/webhook', methods=['POST'])
def payment_webhook():
    """Webhook থেকে ডেটা গ্রহণ করে ব্যালেন্স যোগ করে"""
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
        
        # Check if already processed
        if payment_key in pending_payments:
            pending_payments.pop(payment_key)
        
        # Add balance
        user = User.query.get(user_id)
        if not user:
            return jsonify({'status': 'error', 'message': 'User not found'}), 404
        
        user.balance += amount
        
        # Create transaction
        tx = Transaction(
            user_id=user.id,
            amount=amount,
            type='add',
            description=f'Added ৳{amount} via Bohudur Payment (Webhook)',
            status='completed'
        )
        db.session.add(tx)
        
        # Create notification
        notif = Notification(
            user_id=user.id,
            title='💰 Payment Successful',
            message=f'Added ৳{amount} to your wallet via Bohudur Payment.',
            is_read=False
        )
        db.session.add(notif)
        
        db.session.commit()
        
        print(f"✅ Balance added: {amount} to user {user_id}")
        
        return jsonify({'status': 'success', 'message': 'Balance added'}), 200
        
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# NOTIFICATION API ROUTES
# ============================================

@app.route('/notifications')
@login_required
def get_notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return jsonify([{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'is_read': n.is_read,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
    } for n in notifications])

@app.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notification = Notification.query.get_or_404(notif_id)
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    notification.is_read = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/notifications/mark-read', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)