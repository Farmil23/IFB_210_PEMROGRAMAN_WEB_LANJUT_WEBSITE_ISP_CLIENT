from flask import (
    current_app,
    render_template,
    redirect,
    url_for,
    request,
    jsonify,
    flash
)

from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user
)

from .models import db, User, Package, Transaction, Voucher
from .forms import LoginForm

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
    """
    Menghasilkan kode unik untuk voucher Wi-Fi
    Contoh: WF-A8K9Z
    """

    chars = string.ascii_uppercase + string.digits

    return "WF-" + ''.join(
        random.choice(chars) for _ in range(6)
    )


# ==========================================
# INFO = ADMIN DECORATOR
# ==========================================
def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not current_user.is_authenticated or not current_user.is_admin:

            flash('Anda tidak memiliki akses ke halaman ini.')

            return redirect(url_for('index'))

        return f(*args, **kwargs)

    return decorated_function


# ==========================================
# INFO = WEB ROUTES
# ==========================================

@current_app.route('/')
def index():

    # ==========================================
    # DUMMY DATA
    # ==========================================

    if not User.query.first():

        dummy_user = User(
            username="testuser",
            email="test@itenas.id",
            password_hash="rahasia"
        )

        db.session.add(dummy_user)
        db.session.commit()

    if not Package.query.first():

        paket1 = Package(
            name="Voucher 3 Jam",
            package_type="jam-jaman",
            price=5000,
            speed="Up to 10 Mbps"
        )

        paket2 = Package(
            name="Paket Bulanan Basic",
            package_type="bulanan",
            price=150000,
            speed="20 Mbps"
        )

        db.session.add_all([paket1, paket2])
        db.session.commit()

    # ==========================================
    # GET PACKAGES
    # ==========================================

    packages = Package.query.all()

    return render_template(
        'index.html',
        packages=packages
    )


# ==========================================
# LOGIN
# ==========================================

@current_app.route('/login', methods=['GET', 'POST'])
def login():

    form = LoginForm()

    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(
            email=email
        ).first()

        # ==========================================
        # DUMMY PASSWORD CHECK
        # ==========================================

        if user and user.password_hash == password:

            login_user(user)

            flash('Login berhasil!', 'success')

            if user.is_admin:

                return redirect(
                    url_for('admin_dashboard')
                )

            return redirect(
                url_for('dashboard')
            )

        else:

            flash(
                'Email atau password salah',
                'danger'
            )

    return render_template(
        'login.html',
        form=form
    )


# ==========================================
# REGISTER
# ==========================================

@current_app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # ==========================================
        # CHECK EXISTING USER
        # ==========================================

        existing_user = User.query.filter(
            (User.email == email) |
            (User.username == username)
        ).first()

        if existing_user:

            flash(
                'Email atau Username sudah terdaftar.',
                'warning'
            )

            return redirect(
                url_for('register')
            )

        # ==========================================
        # CREATE USER
        # ==========================================

        new_user = User(
            username=username,
            email=email,
            password_hash=password
        )

        db.session.add(new_user)
        db.session.commit()

        flash(
            'Pendaftaran berhasil! Silakan login.',
            'success'
        )

        return redirect(
            url_for('login')
        )

    return render_template('register.html')


# ==========================================
# LOGOUT
# ==========================================

@current_app.route('/logout')
@login_required
def logout():

    logout_user()

    flash('Logout berhasil.', 'success')

    return redirect(
        url_for('index')
    )


# ==========================================
# DASHBOARD
# ==========================================

@current_app.route('/dashboard')
@login_required
def dashboard():

    transaksi_user = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Transaction.id.desc()
    ).all()

    return render_template(
        'dashboard.html',
        transactions=transaksi_user
    )


# ==========================================
# ADMIN DASHBOARD
# ==========================================

@current_app.route('/admin')
@login_required
@admin_required
def admin_dashboard():

    packages = Package.query.all()

    return render_template(
        'admin_dashboard.html',
        packages=packages
    )


# ==========================================
# ADD PACKAGE
# ==========================================

@current_app.route(
    '/admin/package/add',
    methods=['GET', 'POST']
)

@login_required
@admin_required
def admin_package_add():

    if request.method == 'POST':

        name = request.form.get('name')
        package_type = request.form.get('package_type')
        price = request.form.get('price')
        speed = request.form.get('speed')

        new_package = Package(
            name=name,
            package_type=package_type,
            price=float(price),
            speed=speed
        )

        db.session.add(new_package)
        db.session.commit()

        flash(
            'Paket berhasil ditambahkan!',
            'success'
        )

        return redirect(
            url_for('admin_dashboard')
        )

    return render_template(
        'admin_package_form.html',
        package=None
    )


# ==========================================
# EDIT PACKAGE
# ==========================================

@current_app.route(
    '/admin/package/edit/<int:id>',
    methods=['GET', 'POST']
)

@login_required
@admin_required
def admin_package_edit(id):

    paket = Package.query.get_or_404(id)

    if request.method == 'POST':

        paket.name = request.form.get('name')
        paket.package_type = request.form.get('package_type')
        paket.price = float(
            request.form.get('price')
        )
        paket.speed = request.form.get('speed')

        db.session.commit()

        flash(
            'Paket berhasil diperbarui!',
            'success'
        )

        return redirect(
            url_for('admin_dashboard')
        )

    return render_template(
        'admin_package_form.html',
        package=paket
    )


# ==========================================
# DELETE PACKAGE
# ==========================================

@current_app.route(
    '/admin/package/delete/<int:id>',
    methods=['POST']
)

@login_required
@admin_required
def admin_package_delete(id):

    paket = Package.query.get_or_404(id)

    db.session.delete(paket)
    db.session.commit()

    flash(
        'Paket berhasil dihapus!',
        'success'
    )

    return redirect(
        url_for('admin_dashboard')
    )


# ==========================================
# ORDER PAGE
# ==========================================

@current_app.route('/order/<int:package_id>')
@login_required
def order(package_id):

    paket = Package.query.get_or_404(package_id)

    if paket.package_type == 'jam-jaman':

        return render_template(
            'order_voucher.html',
            package=paket
        )

    return render_template(
        'order_subscription.html',
        package=paket
    )


# ==========================================
# CHECKOUT
# ==========================================

@current_app.route(
    '/checkout/<int:package_id>',
    methods=['POST']
)

@login_required
def checkout(package_id):

    paket = Package.query.get_or_404(package_id)

    router_location = request.form.get(
        'router_location'
    )

    address = request.form.get(
        'address'
    )

    phone_number = request.form.get(
        'phone_number'
    )

    # ==========================================
    # CREATE TRANSACTION
    # ==========================================

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

    # ==========================================
    # PAYLOAD N8N
    # ==========================================

    payload = {
        "title": paket.name,
        "price": int(paket.price),
        "transaction_id": transaksi_baru.id
    }

    try:

        response = requests.post(
            N8N_WEBHOOK_CHECKOUT_URL,
            json=payload,
            allow_redirects=False
        )

        # ==========================================
        # REDIRECT
        # ==========================================

        if response.status_code in (
            301,
            302,
            303,
            307,
            308
        ):

            checkout_url = response.headers.get(
                'Location'
            )

            if checkout_url:

                return redirect(checkout_url)

        # ==========================================
        # JSON URL
        # ==========================================

        if response.status_code == 200:

            try:

                data = response.json()

                checkout_url = data.get('url')

                if checkout_url:

                    return redirect(checkout_url)

            except ValueError:
                pass

        return f"""
        Gagal mendapatkan link pembayaran dari n8n.
        Status: {response.status_code}
        """, 500

    except Exception as e:

        return f"""
        Terjadi kesalahan koneksi ke server n8n:
        {str(e)}
        """, 500


# ==========================================
# PAYMENT SUCCESS WEBHOOK
# ==========================================

@current_app.route(
    '/api/payment-success',
    methods=['POST']
)

def payment_success():

    data = request.get_json()

    if not data or 'transaction_id' not in data:

        return jsonify({
            "status": "error",
            "message": "Invalid payload"
        }), 400

    trx_id = data['transaction_id']

    transaksi = Transaction.query.get(trx_id)

    if not transaksi:

        return jsonify({
            "status": "error",
            "message": "Transaction not found"
        }), 404

    # ==========================================
    # ALREADY PAID
    # ==========================================

    if transaksi.status == 'paid':

        return jsonify({
            "status": "success",
            "message": "Already paid"
        }), 200

    try:

        # ==========================================
        # UPDATE STATUS
        # ==========================================

        transaksi.status = 'paid'

        # ==========================================
        # CREATE VOUCHER
        # ==========================================

        kode_baru = generate_wifi_code()

        voucher_baru = Voucher(
            transaction_id=transaksi.id,
            code=kode_baru,
            status='active'
        )

        db.session.add(voucher_baru)
        db.session.commit()

        return jsonify({
            "status": "success",
            "voucher_code": kode_baru
        }), 200

    except Exception as e:

        db.session.rollback()

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500