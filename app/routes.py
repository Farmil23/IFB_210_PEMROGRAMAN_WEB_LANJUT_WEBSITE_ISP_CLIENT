from flask import current_app as app
from flask import render_template, redirect, url_for, request, jsonify, flash
from flask_login import login_user, logout_user, login_required, current_user
from .models import db, User, Package, Transaction, Voucher
import requests
import random
import string
from functools import wraps

# ==========================================
# INFO = KONFIGURASI URL N8N
# ==========================================
# INFO = Ganti IP ini dengan IP VPS n8n kamu yang asli
N8N_WEBHOOK_CHECKOUT_URL = "https://n8n.srv1631432.hstgr.cloud/webhook/create_checkout"


# ==========================================
# INFO = HELPER FUNCTIONS
# ==========================================
def generate_wifi_code():
    """Menghasilkan kode unik untuk voucher Wi-Fi (Contoh: WF-A8K9Z)"""
    chars = string.ascii_uppercase + string.digits
    return "WF-" + ''.join(random.choice(chars) for _ in range(6))


# ==========================================
# INFO = WEB ROUTES (TAMPILAN HALAMAN)
# ==========================================

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Anda tidak memiliki akses ke halaman ini.')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    # INFO = --- DUMMY DATA INJECTION UNTUK TESTING ---

    if not User.query.first():
        dummy_user = User(username="testuser", email="test@itenas.id", password_hash="rahasia")
        db.session.add(dummy_user)
        db.session.commit()
        
    if not Package.query.first():
        paket1 = Package(name="Voucher 3 Jam", package_type="jam-jaman", price=5000, speed="Up to 10 Mbps")
        paket2 = Package(name="Paket Bulanan Basic", package_type="bulanan", price=150000, speed="20 Mbps")
        db.session.add_all([paket1, paket2])
        db.session.commit()
    # INFO = ------------------------------------------

    packages = Package.query.all()
    return render_template('index.html', packages=packages)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        # INFO = Untuk dummy testing, kita cek password_hash secara literal.
        # INFO = Di aplikasi sungguhan, gunakan werkzeug.security.check_password_hash
        if user and user.password_hash == password:
            login_user(user)
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('Email atau password salah')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # INFO = Cek apakah email atau username sudah dipakai
        existing_user = User.query.filter((User.email == email) | (User.username == username)).first()
        if existing_user:
            flash('Email atau Username sudah terdaftar. Silakan gunakan yang lain.')
            return redirect(url_for('register'))
            
        # INFO = Buat user baru
        new_user = User(username=username, email=email, password_hash=password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Pendaftaran berhasil! Silakan masuk.')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    # INFO = Ambil riwayat transaksi dan voucher milik user ini
    transaksi_user = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.id.desc()).all()
    
    return render_template('dashboard.html', transactions=transaksi_user)

# ==========================================
# INFO = ADMIN ROUTES
# ==========================================

@app.route('/admin')
@admin_required
def admin_dashboard():
    packages = Package.query.all()
    return render_template('admin_dashboard.html', packages=packages)

@app.route('/admin/package/add', methods=['GET', 'POST'])
@admin_required
def admin_package_add():
    if request.method == 'POST':
        name = request.form.get('name')
        package_type = request.form.get('package_type')
        price = request.form.get('price')
        speed = request.form.get('speed')
        
        new_package = Package(name=name, package_type=package_type, price=float(price), speed=speed)
        db.session.add(new_package)
        db.session.commit()
        flash('Paket berhasil ditambahkan!')
        return redirect(url_for('admin_dashboard'))
        
    return render_template('admin_package_form.html', package=None)

@app.route('/admin/package/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def admin_package_edit(id):
    paket = Package.query.get_or_404(id)
    if request.method == 'POST':
        paket.name = request.form.get('name')
        paket.package_type = request.form.get('package_type')
        paket.price = float(request.form.get('price'))
        paket.speed = request.form.get('speed')
        
        db.session.commit()
        flash('Paket berhasil diperbarui!')
        return redirect(url_for('admin_dashboard'))
        
    return render_template('admin_package_form.html', package=paket)

@app.route('/admin/package/delete/<int:id>', methods=['POST'])
@admin_required
def admin_package_delete(id):
    paket = Package.query.get_or_404(id)
    db.session.delete(paket)
    db.session.commit()
    flash('Paket berhasil dihapus!')
    return redirect(url_for('admin_dashboard'))

# ==========================================
# INFO = API ROUTES (LOGIKA CHECKOUT & N8N)
# ==========================================

@app.route('/order/<int:package_id>')
@login_required
def order(package_id):
    """Fase 3: Menampilkan halaman form pemesanan berdasarkan jenis paket"""
    paket = Package.query.get_or_404(package_id)
    
    if paket.package_type == 'jam-jaman':
        return render_template('order_voucher.html', package=paket)
    else:
        return render_template('order_subscription.html', package=paket)

@app.route('/checkout/<int:package_id>', methods=['POST'])
@login_required
def checkout(package_id):
    """Fase 3: Menyimpan data pesanan dan mengirim data keranjang ke n8n untuk dibuatkan link Stripe"""
    
    # INFO = 1. Cari data paket yang mau dibeli
    paket = Package.query.get_or_404(package_id)
    
    # INFO = Ambil data dari form HTML
    router_location = request.form.get('router_location')
    address = request.form.get('address')
    phone_number = request.form.get('phone_number')
    
    # INFO = 2. Buat record transaksi dengan status 'pending'
    transaksi_baru = Transaction(
        user_id=current_user.id,
        package_id=paket.id,
        status='pending',
        router_location=router_location,
        address=address,
        phone_number=phone_number
    )
    db.session.add(transaksi_baru)
    db.session.commit()
    
    # INFO = 3. Siapkan payload untuk n8n
    payload = {
        "title": paket.name,
        "price": int(paket.price),
        "transaction_id": transaksi_baru.id
    }
    
    try:
        # INFO = 4. Tembak webhook n8n
        # INFO = Set allow_redirects=False agar bisa menangkap header Location jika n8n merespon dengan Redirect
        response = requests.post(N8N_WEBHOOK_CHECKOUT_URL, json=payload, allow_redirects=False)
        
        # INFO = 5. Arahkan browser user ke link Stripe yang dihasilkan n8n
        # INFO = Jika n8n membalas dengan status redirect (301, 302, 303, 307, 308)
        if response.status_code in (301, 302, 303, 307, 308):
            checkout_url = response.headers.get('Location')
            if checkout_url:
                return redirect(checkout_url)
                
        # INFO = Jika n8n membalas dengan JSON 200 OK yang berisi URL
        if response.status_code == 200:
            try:
                data = response.json()
                checkout_url = data.get('url')
                if checkout_url:
                    return redirect(checkout_url)
            except ValueError:
                pass # INFO = Abaikan error parsing JSON jika response bukan JSON
                
        return f"Gagal mendapatkan link pembayaran dari n8n. Status: {response.status_code}", 500
            
    except Exception as e:
        return f"Terjadi kesalahan koneksi ke server n8n: {str(e)}", 500


@app.route('/api/payment-success', methods=['POST'])
def payment_success():
    """Fase 4: Pintu penerima webhook dari n8n (Stripe Listener)"""
    
    data = request.get_json()
    if not data or 'transaction_id' not in data:
        return jsonify({"status": "error", "message": "Invalid payload"}), 400

    trx_id = data['transaction_id']

    # INFO = 1. Cari transaksi di Database Aiven
    transaksi = Transaction.query.get(trx_id)
    if not transaksi:
        return jsonify({"status": "error", "message": "Transaction not found"}), 404

    # INFO = 2. Keamanan: Cegah voucher ter-generate 2 kali untuk pesanan yang sama
    if transaksi.status == 'paid':
        return jsonify({"status": "success", "message": "Already paid"}), 200

    try:
        # INFO = 3. Ubah Status Transaksi
        transaksi.status = 'paid'

        # INFO = 4. Buat Voucher Baru
        kode_baru = generate_wifi_code()
        voucher_baru = Voucher(
            transaction_id=transaksi.id,
            code=kode_baru,
            status='active'
        )
        
        db.session.add(voucher_baru)
        db.session.commit()

        # INFO = Respon ini akan dibaca oleh n8n sebagai pertanda sukses
        return jsonify({"status": "success", "voucher_code": kode_baru}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500