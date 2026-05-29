from flask import (
    current_app,
    render_template,
    redirect,
    url_for,
    request,
    jsonify,
    flash,
    abort,
)

from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user
)

from .models import (
    db,
    User,
    Package,
    Transaction,
    Voucher,
    HotspotRouter,
    Notification,
)
from .forms import LoginForm

import requests
import random
import string
import re

from datetime import datetime, timedelta

from .timezone_util import now_wib, ensure_wib

from functools import wraps
import os
from werkzeug.utils import secure_filename


N8N_WEBHOOK_CHECKOUT_URL = "https://n8n.srv1631432.hstgr.cloud/webhook/create_checkout"

DEMO_ROUTER_LABEL = 'Demo (presentasi — tanpa router fisik)'


def _presentation_mode():

    return not current_app.config.get('PRODUCTION', True)


def _app_base_url():

    configured = current_app.config.get('APP_BASE_URL') or ''

    if configured:

        return configured.rstrip('/')

    space_host = os.environ.get('SPACE_HOST')
    if space_host:
        return f"https://{space_host}"

    return request.url_root.rstrip('/')


def _finalize_transaction_payment(transaksi):

    paket = transaksi.package

    if transaksi.status == 'paid':

        existing_v = None

        if paket and paket.package_type == 'jam-jaman':

            existing_v = Voucher.query.filter_by(
                transaction_id=transaksi.id,
            ).first()

        return {
            'ok': True,
            'already_paid': True,
            'voucher_code': existing_v.code if existing_v else None,
        }

    paid_moment = now_wib()

    transaksi.status = 'paid'

    transaksi.paid_at = paid_moment

    notif = Notification(
        message=f"Pembayaran berhasil untuk transaksi #{transaksi.id} oleh {transaksi.customer.username if transaksi.customer else 'Unknown'}",
        transaction_id=transaksi.id
    )
    db.session.add(notif)

    if not paket or paket.package_type != 'jam-jaman':

        db.session.commit()

        return {
            'ok': True,
            'voucher_code': None,
        }

    existing_v = Voucher.query.filter_by(
        transaction_id=transaksi.id,
    ).first()

    if existing_v:

        db.session.commit()

        return {
            'ok': True,
            'voucher_code': existing_v.code,
        }

    hours = _package_voucher_hours(paket)

    valid_from = paid_moment

    expires_at = valid_from + timedelta(hours=hours)

    kode_baru = generate_wifi_code()

    voucher_baru = Voucher(
        transaction_id=transaksi.id,
        code=kode_baru,
        status='unused',
        valid_from=valid_from,
        expires_at=expires_at,
    )

    db.session.add(voucher_baru)

    db.session.commit()

    return {
        'ok': True,
        'voucher_code': kode_baru,
    }


def generate_wifi_code():

    chars = string.ascii_uppercase + string.digits

    return "WF-" + ''.join(
        random.choice(chars) for _ in range(6)
    )


def _parse_mbps(speed_str):

    if not speed_str:

        return None

    m = re.search(
        r'(\d+(?:\.\d+)?)',
        str(speed_str),
    )

    if not m:

        return None

    return int(float(m.group(1)))


def _relative_time_id(dt):

    if dt is None:

        return None

    now = now_wib()

    dt = ensure_wib(dt)

    secs = int((now - dt).total_seconds())

    if secs < 60:

        return 'Baru saja'

    if secs < 3600:

        return f'{secs // 60} menit lalu'

    if secs < 86400:

        return f'{secs // 3600} jam lalu'

    days = (now - dt).days

    if days == 1:

        return 'Kemarin'

    return f'{days} hari lalu'


def _package_voucher_hours(pkg):

    if not pkg or pkg.package_type != 'jam-jaman':

        return None

    h = pkg.voucher_duration_hours

    if h is not None and h > 0:

        return int(h)

    return 8


def _apply_voucher_expiry(vouchers):

    now = now_wib()

    changed = False

    for v in vouchers:

        if not v:

            continue

        if v.status == 'expired':

            continue

        trx = v.transaction

        pkg = trx.package if trx else None

        if not pkg or pkg.package_type != 'jam-jaman':

            continue

        hours = _package_voucher_hours(pkg)

        vf = v.valid_from or trx.paid_at or trx.created_at or now

        if v.valid_from is None:

            v.valid_from = vf

            changed = True

        if v.expires_at is None:

            v.expires_at = vf + timedelta(hours=hours)

            changed = True

        if v.status in ('unused', 'active') and v.expires_at and now > v.expires_at:

            v.status = 'expired'

            changed = True

    if changed:

        db.session.commit()


def _voucher_timeline(voucher, transaction, package):

    now = now_wib()

    if transaction.status != 'paid':

        return {
            'kind': 'pending_payment',
            'label': 'Menunggu pembayaran',
        }

    if not package:

        return {'kind': 'unknown', 'label': 'Paket tidak ditemukan'}

    if package.package_type == 'bulanan':

        return {
            'kind': 'subscription',
            'label': 'Langganan bulanan',
            'paid_at': transaction.paid_at,
        }

    if not voucher:

        return {
            'kind': 'voucher_missing',
            'label': 'Voucher belum tersedia',
        }

    hours = _package_voucher_hours(package) or 8

    vf = voucher.valid_from or transaction.paid_at or transaction.created_at

    exp = voucher.expires_at

    if exp is None and vf is not None:

        exp = vf + timedelta(hours=hours)

    if vf and now < vf:

        return {
            'kind': 'scheduled',
            'label': 'Belum aktif',
            'valid_from': vf,
            'expires_at': exp,
            'hours': hours,
        }

    if exp and now >= exp:

        return {
            'kind': 'expired',
            'label': 'Tidak berlaku',
            'valid_from': vf,
            'expires_at': exp,
            'hours': hours,
            'status': voucher.status,
        }

    return {
        'kind': 'active',
        'label': 'Aktif',
        'valid_from': vf,
        'expires_at': exp,
        'hours': hours,
        'remaining': exp - now if exp else None,
        'status': voucher.status,
    }


def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not current_user.is_authenticated or not current_user.is_admin:

            flash('Anda tidak memiliki akses ke halaman ini.')

            return redirect(url_for('index'))

        return f(*args, **kwargs)

    return decorated_function


@current_app.route('/')
def index():

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
            speed="Up to 10 Mbps",
            voucher_duration_hours=3,
        )

        paket2 = Package(
            name="Paket Bulanan Basic",
            package_type="bulanan",
            price=150000,
            speed="20 Mbps",
            voucher_duration_hours=None,
        )

        db.session.add_all([paket1, paket2])
        db.session.commit()

    packages = Package.query.all()

    return render_template(
        'index.html',
        packages=packages
    )


@current_app.route('/login', methods=['GET', 'POST'])
def login():

    # Already authenticated → route to correct dashboard immediately
    if current_user.is_authenticated:

        if current_user.is_admin:

            return redirect(url_for('admin_dashboard'))

        return redirect(url_for('dashboard'))

    form = LoginForm()

    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(
            email=email
        ).first()

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


@current_app.route('/register', methods=['GET', 'POST'])
def register():

    # Already authenticated → route to correct dashboard immediately
    if current_user.is_authenticated:

        if current_user.is_admin:

            return redirect(url_for('admin_dashboard'))

        return redirect(url_for('dashboard'))

    if request.method == 'POST':

        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

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

        new_user = User(
            username=username,
            email=email,
            password_hash=password
        )

        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)

        flash(
            'Pendaftaran berhasil! Selamat datang, ' + (new_user.username or '') + '.',
            'success'
        )

        if new_user.is_admin:

            return redirect(url_for('admin_dashboard'))

        return redirect(url_for('dashboard'))

    return render_template('register.html')


@current_app.route('/logout')
@login_required
def logout():

    logout_user()

    flash('Logout berhasil.', 'success')

    return redirect(
        url_for('index')
    )


@current_app.route('/dashboard')
@login_required
def dashboard():

    transaksi_user = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Transaction.id.desc()
    ).all()

    paid_list = [
        t for t in transaksi_user
        if t.status == 'paid'
    ]

    last_paid = paid_list[0] if paid_list else None

    last_paid_bulanan = next(
        (
            t for t in transaksi_user
            if t.status == 'paid'
            and t.package
            and t.package.package_type == 'bulanan'
        ),
        None,
    )

    hero_mbps = _parse_mbps(
        last_paid_bulanan.package.speed
        if last_paid_bulanan and last_paid_bulanan.package
        else None,
    )

    if hero_mbps is None and last_paid and last_paid.package:

        hero_mbps = _parse_mbps(last_paid.package.speed)

    hero_speed_num = str(hero_mbps if hero_mbps is not None else 0)

    fiber_mbps = _parse_mbps(
        last_paid_bulanan.package.speed
        if last_paid_bulanan and last_paid_bulanan.package
        else None,
    )

    fiber_speed_num = str(fiber_mbps if fiber_mbps is not None else 0)

    fiber_caption = (
        last_paid_bulanan.package.name
        if last_paid_bulanan and last_paid_bulanan.package
        else 'Belum ada langganan fiber aktif'
    )

    active_router_count = HotspotRouter.query.filter_by(
        is_active=True,
    ).count()

    active_devices = active_router_count or 0

    is_router_online = active_devices > 0

    has_active_subscription = last_paid_bulanan is not None

    uptime_label = '99.9%' if is_router_online else '0%'

    latency_label = '5ms' if is_router_online else '0ms'

    if is_router_online and has_active_subscription:

        connection_status = 'Stable'

        connection_footer = '99.9% uptime monitoring'

    elif is_router_online:

        connection_status = 'Limited'

        connection_footer = 'Router aktif, belum ada langganan fiber'

    else:

        connection_status = 'Offline'

        connection_footer = '0 router tersambung ke sistem'

    if is_router_online and has_active_subscription:

        network_badge_label = 'Network Stable'

        network_badge_tone = 'green'

    elif is_router_online:

        network_badge_label = 'Limited'

        network_badge_tone = 'amber'

    else:

        network_badge_label = 'No Router Link'

        network_badge_tone = 'zinc'

    jam_vouchers = Voucher.query.join(
        Transaction,
        Transaction.id == Voucher.transaction_id,
    ).join(
        Package,
        Package.id == Transaction.package_id,
    ).filter(
        Transaction.user_id == current_user.id,
        Package.package_type == 'jam-jaman',
        Transaction.status == 'paid',
    ).all()

    _apply_voucher_expiry(jam_vouchers)

    voucher_display = sum(
        1 for v in jam_vouchers
        if v.status in ('unused', 'active')
    )

    last_payment_rel = (
        _relative_time_id(last_paid.created_at)
        if last_paid
        else None
    )

    transaction_count = len(transaksi_user)

    recent_activity_rows = []

    for t in transaksi_user[:5]:

        pkg_name = t.package.name if t.package else 'Paket'

        tone = (
            'green' if t.status == 'paid'
            else 'amber' if t.status == 'pending'
            else 'zinc'
        )

        abbr = (
            'PAY' if t.status == 'paid'
            else 'PEN' if t.status == 'pending'
            else 'TRX'
        )

        recent_activity_rows.append({
            'title': f'Pembelian {pkg_name}',
            'subtitle': f'#{t.id} — {t.status}',
            'when': _relative_time_id(t.created_at) or '',
            'tone': tone,
            'abbr': abbr,
        })

    return render_template(
        'dashboard.html',
        transactions=transaksi_user,
        hero_speed_num=hero_speed_num,
        uptime_label=uptime_label,
        latency_label=latency_label,
        active_devices=active_devices,
        transaction_count=transaction_count,
        last_payment_rel=last_payment_rel,
        connection_status=connection_status,
        connection_footer=connection_footer,
        voucher_display=voucher_display,
        fiber_speed_num=fiber_speed_num,
        fiber_caption=fiber_caption,
        network_badge_label=network_badge_label,
        network_badge_tone=network_badge_tone,
        recent_activity_rows=recent_activity_rows,
    )


@current_app.route('/admin')
@login_required
@admin_required
def admin_dashboard():

    packages = Package.query.all()

    routers = HotspotRouter.query.order_by(
        HotspotRouter.sort_order,
        HotspotRouter.id,
    ).all()

    active_router_count = HotspotRouter.query.filter_by(
        is_active=True
    ).count()

    # ---- Read-only monitoring queries (SELECT only, no mutations) ----

    total_routers = HotspotRouter.query.count()

    total_users = User.query.count()

    total_transactions = Transaction.query.count()

    paid_transactions = Transaction.query.filter_by(
        status='paid'
    ).count()

    pending_transactions = Transaction.query.filter_by(
        status='pending'
    ).count()

    total_vouchers = Voucher.query.count()

    recent_transactions = Transaction.query.order_by(
        Transaction.id.desc()
    ).limit(10).all()

    return render_template(
        'admin_dashboard.html',
        packages=packages,
        routers=routers,
        active_router_count=active_router_count or 0,
        total_routers=total_routers or 0,
        total_users=total_users or 0,
        total_transactions=total_transactions or 0,
        paid_transactions=paid_transactions or 0,
        pending_transactions=pending_transactions or 0,
        total_vouchers=total_vouchers or 0,
        recent_transactions=recent_transactions,
    )


@current_app.route('/admin/transactions/report')
@login_required
@admin_required
def admin_transactions_report():
    
    transactions = Transaction.query.order_by(Transaction.id.desc()).all()
    
    total_tx = len(transactions)
    paid_tx = sum(1 for t in transactions if t.status == 'paid')
    total_amount = sum((t.package.price if t.package and t.package.price else 0) for t in transactions if t.status == 'paid')
    
    return render_template(
        'admin_transactions_report.html',
        transactions=transactions,
        total_tx=total_tx,
        paid_tx=paid_tx,
        total_amount=total_amount,
        current_time=now_wib()
    )


@current_app.route(
    '/admin/package/add',
    methods=['GET', 'POST']
)

@login_required
@admin_required
def admin_package_add():

    if request.method == 'POST':

        name = (request.form.get('name') or '').strip()
        package_type = request.form.get('package_type') or 'bulanan'
        price_raw = (request.form.get('price') or '').strip()
        speed = (request.form.get('speed') or '').strip()
        vdh_raw = request.form.get('voucher_duration_hours')

        if not name:

            flash('Nama paket wajib diisi.', 'danger')

            return redirect(url_for('admin_package_add'))

        if not price_raw:

            flash('Harga paket wajib diisi.', 'danger')

            return redirect(url_for('admin_package_add'))

        try:

            price = float(price_raw)

            if price < 0:

                raise ValueError

        except ValueError:

            flash('Harga harus berupa angka positif.', 'danger')

            return redirect(url_for('admin_package_add'))

        if not speed:

            flash('Kecepatan paket wajib diisi.', 'danger')

            return redirect(url_for('admin_package_add'))

        if package_type == 'jam-jaman':

            try:

                voucher_duration_hours = int(vdh_raw) if vdh_raw else 8

            except ValueError:

                voucher_duration_hours = 8

            if voucher_duration_hours < 1:

                voucher_duration_hours = 8

        else:

            voucher_duration_hours = None

        new_package = Package(
            name=name,
            package_type=package_type,
            price=price,
            speed=speed,
            voucher_duration_hours=voucher_duration_hours,
        )

        db.session.add(new_package)
        db.session.commit()

        flash('Paket berhasil ditambahkan!', 'success')

        return redirect(url_for('admin_dashboard'))

    return render_template(
        'admin_package_form.html',
        package=None
    )


@current_app.route(
    '/admin/package/edit/<int:id>',
    methods=['GET', 'POST']
)

@login_required
@admin_required
def admin_package_edit(id):

    paket = Package.query.get_or_404(id)

    if request.method == 'POST':

        name = (request.form.get('name') or '').strip()
        package_type = request.form.get('package_type') or 'bulanan'
        price_raw = (request.form.get('price') or '').strip()
        speed = (request.form.get('speed') or '').strip()
        vdh_raw = request.form.get('voucher_duration_hours')

        if not name:

            flash('Nama paket wajib diisi.', 'danger')

            return redirect(url_for('admin_package_edit', id=id))

        if not price_raw:

            flash('Harga paket wajib diisi.', 'danger')

            return redirect(url_for('admin_package_edit', id=id))

        try:

            price = float(price_raw)

            if price < 0:

                raise ValueError

        except ValueError:

            flash('Harga harus berupa angka positif.', 'danger')

            return redirect(url_for('admin_package_edit', id=id))

        if not speed:

            flash('Kecepatan paket wajib diisi.', 'danger')

            return redirect(url_for('admin_package_edit', id=id))

        paket.name = name
        paket.package_type = package_type
        paket.price = price
        paket.speed = speed
        vdh_raw = request.form.get('voucher_duration_hours')

        if package_type == 'jam-jaman':

            try:

                paket.voucher_duration_hours = int(vdh_raw) if vdh_raw else 8

            except ValueError:

                paket.voucher_duration_hours = 8

            if paket.voucher_duration_hours < 1:

                paket.voucher_duration_hours = 8

        else:

            paket.voucher_duration_hours = None

        db.session.commit()

        flash('Paket berhasil diperbarui!', 'success')

        return redirect(url_for('admin_dashboard'))

    return render_template(
        'admin_package_form.html',
        package=paket
    )


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


@current_app.route(
    '/admin/router/add',
    methods=['GET', 'POST'],
)

@login_required
@admin_required
def admin_router_add():

    if request.method == 'POST':

        name = (request.form.get('name') or '').strip()
        notes = (request.form.get('notes') or '').strip() or None
        ip_address = (request.form.get('ip_address') or '').strip() or None
        sort_order = int(request.form.get('sort_order') or 0)
        is_active = request.form.get('is_active') == 'on'

        if not name:

            flash('Nama router wajib diisi.', 'danger')

            return redirect(url_for('admin_router_add'))

        if not ip_address:

            flash('IP address router wajib diisi.', 'danger')

            return redirect(url_for('admin_router_add'))

        if HotspotRouter.query.filter_by(name=name).first():

            flash('Nama router sudah dipakai.', 'warning')

            return redirect(url_for('admin_router_add'))

        db.session.add(
            HotspotRouter(
                name=name,
                notes=notes,
                ip_address=ip_address,
                sort_order=sort_order,
                is_active=is_active,
            )
        )

        db.session.commit()

        flash('Titik router berhasil ditambahkan.', 'success')

        return redirect(url_for('admin_dashboard'))

    return render_template(
        'admin_router_form.html',
        router=None,
    )


@current_app.route(
    '/admin/router/edit/<int:id>',
    methods=['GET', 'POST'],
)

@login_required
@admin_required
def admin_router_edit(id):

    router = HotspotRouter.query.get_or_404(id)

    if request.method == 'POST':

        name = (request.form.get('name') or '').strip()
        notes = (request.form.get('notes') or '').strip() or None
        ip_address = (request.form.get('ip_address') or '').strip() or None
        sort_order = int(request.form.get('sort_order') or 0)
        is_active = request.form.get('is_active') == 'on'

        if not name:

            flash('Nama router wajib diisi.', 'danger')

            return redirect(
                url_for('admin_router_edit', id=id)
            )

        if not ip_address:

            flash('IP address router wajib diisi.', 'danger')

            return redirect(
                url_for('admin_router_edit', id=id)
            )

        other = HotspotRouter.query.filter(
            HotspotRouter.name == name,
            HotspotRouter.id != id,
        ).first()

        if other:

            flash('Nama router sudah dipakai.', 'warning')

            return redirect(
                url_for('admin_router_edit', id=id)
            )

        router.name = name
        router.notes = notes
        router.ip_address = ip_address
        router.sort_order = sort_order
        router.is_active = is_active

        db.session.commit()

        flash('Titik router diperbarui.', 'success')

        return redirect(url_for('admin_dashboard'))

    return render_template(
        'admin_router_form.html',
        router=router,
    )


@current_app.route(
    '/admin/router/delete/<int:id>',
    methods=['POST'],
)

@login_required
@admin_required
def admin_router_delete(id):

    router = HotspotRouter.query.get_or_404(id)

    db.session.delete(router)
    db.session.commit()

    flash('Titik router dihapus.', 'success')

    return redirect(url_for('admin_dashboard'))


@current_app.route('/order/<int:package_id>')
@login_required
def order(package_id):

    paket = Package.query.get_or_404(package_id)

    if paket.package_type == 'jam-jaman':

        routers = HotspotRouter.query.filter_by(
            is_active=True
        ).order_by(
            HotspotRouter.sort_order,
            HotspotRouter.id,
        ).all()

        router_count = len(routers) or 0

        return render_template(
            'order_voucher.html',
            package=paket,
            routers=routers,
            router_count=router_count or 0,
            demo_router_label=DEMO_ROUTER_LABEL,
        )

    return render_template(
        'order_subscription.html',
        package=paket
    )


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

    if paket.package_type == 'jam-jaman':

        allowed = [
            r.name for r in HotspotRouter.query.filter_by(
                is_active=True
            ).order_by(
                HotspotRouter.sort_order,
                HotspotRouter.id,
            ).all()
        ]

        presentation = _presentation_mode()

        if not allowed:

            if presentation:

                router_location = DEMO_ROUTER_LABEL

            else:

                flash(
                    'Belum ada titik hotspot/router aktif. Hubungi admin.',
                    'danger',
                )

                return redirect(
                    url_for('order', package_id=package_id)
                )

        elif not router_location or router_location not in allowed:

            flash(
                'Pilih lokasi router yang valid.',
                'danger',
            )

            return redirect(
                url_for('order', package_id=package_id)
            )

    cutoff = now_wib() - timedelta(minutes=15)

    transaksi_baru = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.package_id == paket.id,
        Transaction.status == 'pending',
        Transaction.created_at >= cutoff,
    ).order_by(
        Transaction.id.desc()
    ).first()

    if not transaksi_baru:

        transaksi_baru = Transaction(
            user_id=current_user.id,
            package_id=paket.id,
            status='pending',
            router_location=router_location,
            address=address,
            phone_number=phone_number,
        )

        db.session.add(transaksi_baru)
        db.session.commit()

        notif = Notification(
            message=f"Transaksi baru #{transaksi_baru.id} dibuat oleh {current_user.username}",
            transaction_id=transaksi_baru.id
        )
        db.session.add(notif)
        db.session.commit()

    else:

        transaksi_baru.router_location = router_location
        transaksi_baru.address = address
        transaksi_baru.phone_number = phone_number
        db.session.commit()

    base = _app_base_url()

    success_path = url_for(
        'payment_complete',
        transaction_id=transaksi_baru.id,
    )

    cancel_path = url_for(
        'transaction_detail',
        transaction_id=transaksi_baru.id,
    )

    payload = {
        "title": paket.name,
        "price": int(paket.price),
        "transaction_id": transaksi_baru.id,
        "success_url": f"{base}{success_path}",
        "cancel_url": f"{base}{cancel_path}",
    }

    try:

        response = requests.post(
            N8N_WEBHOOK_CHECKOUT_URL,
            json=payload,
            allow_redirects=False
        )

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

        if response.status_code == 200:

            try:

                data = response.json()

                checkout_url = (
                    data.get('url')
                    or data.get('checkout_url')
                    or data.get('checkoutUrl')
                    or data.get('payment_url')
                    or data.get('paymentUrl')
                    or data.get('session_url')
                    or data.get('sessionUrl')
                )

                session_id = (
                    data.get('session_id')
                    or data.get('stripe_session_id')
                    or data.get('id')
                )

                if session_id:

                    transaksi_baru.stripe_session_id = str(session_id)

                    db.session.commit()

                if checkout_url:

                    return redirect(checkout_url)

            except ValueError:
                pass

        flash(
            'Checkout gateway tidak merespon dengan URL pembayaran. Pembayaran ditunda.',
            'warning',
        )

        return redirect(
            url_for('transaction_detail', transaction_id=transaksi_baru.id)
        )

    except Exception as e:

        flash(
            'Koneksi ke gateway pembayaran gagal.',
            'danger',
        )

        return redirect(
            url_for('transaction_detail', transaction_id=transaksi_baru.id)
        )


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

    try:

        result = _finalize_transaction_payment(transaksi)

        return jsonify({
            "status": "success",
            "message": "Already paid" if result.get('already_paid') else "Payment confirmed",
            "voucher_code": result.get('voucher_code'),
        }), 200

    except Exception as e:

        db.session.rollback()

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@current_app.route('/payment/complete/<int:transaction_id>')
@login_required
def payment_complete(transaction_id):

    transaksi = Transaction.query.get_or_404(transaction_id)

    if transaksi.user_id != current_user.id:

        abort(403)

    try:

        result = _finalize_transaction_payment(transaksi)

        if result.get('voucher_code'):

            flash(
                f'Pembayaran berhasil. Kode voucher: {result["voucher_code"]}',
                'success',
            )

        else:

            flash('Pembayaran berhasil dicatat.', 'success')

    except Exception as e:

        db.session.rollback()

        flash(f'Gagal memproses pembayaran: {e}', 'danger')

    return redirect(
        url_for('transaction_detail', transaction_id=transaction_id)
    )


@current_app.route(
    '/payment/demo-confirm/<int:transaction_id>',
    methods=['POST'],
)
@login_required
def payment_demo_confirm(transaction_id):

    if current_app.config.get('PRODUCTION', True):

        abort(404)

    transaksi = Transaction.query.get_or_404(transaction_id)

    if transaksi.user_id != current_user.id:

        abort(403)

    if transaksi.status != 'pending':

        flash('Transaksi ini sudah diproses.', 'warning')

        return redirect(
            url_for('transaction_detail', transaction_id=transaction_id)
        )

    try:

        result = _finalize_transaction_payment(transaksi)

        if result.get('voucher_code'):

            flash(
                f'[Demo] Pembayaran dikonfirmasi. Voucher: {result["voucher_code"]}',
                'success',
            )

        else:

            flash('[Demo] Pembayaran dikonfirmasi.', 'success')

    except Exception as e:

        db.session.rollback()

        flash(f'Gagal: {e}', 'danger')

    return redirect(
        url_for('transaction_detail', transaction_id=transaction_id)
    )


@current_app.route('/transactions')
@login_required
def transactions():

    transaksi_user = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Transaction.id.desc()
    ).all()

    return render_template(
        'transactions.html',
        transactions=transaksi_user
    )


@current_app.route('/transactions/<int:transaction_id>')
@login_required
def transaction_detail(transaction_id):

    trx = Transaction.query.get_or_404(transaction_id)

    if trx.user_id != current_user.id and not current_user.is_admin:

        abort(403)

    pkg = trx.package

    v = trx.voucher

    if v:

        _apply_voucher_expiry([v])

        db.session.refresh(v)

    timeline = _voucher_timeline(v, trx, pkg)

    return render_template(
        'transaction_detail.html',
        transaction=trx,
        package=pkg,
        voucher=v,
        timeline=timeline,
        presentation_mode=_presentation_mode(),
        payment_complete_url=url_for(
            'payment_complete',
            transaction_id=trx.id,
        ),
    )


@current_app.route('/packages')
@login_required
def browse_packages():

    available_packages = Package.query.all()

    return render_template(
        'packages.html',
        packages=available_packages
    )

@current_app.route('/vouchers')
@login_required
def vouchers():

    user_vouchers = Voucher.query.join(
        Transaction,
        Transaction.id == Voucher.transaction_id,
    ).join(
        Package,
        Package.id == Transaction.package_id,
    ).filter(
        Transaction.user_id == current_user.id,
        Package.package_type == 'jam-jaman',
        Transaction.status == 'paid',
    ).order_by(
        Voucher.id.desc()
    ).all()

    _apply_voucher_expiry(user_vouchers)

    vouchers_valid = [
        v for v in user_vouchers
        if v.status in ('unused', 'active')
    ]

    vouchers_expired = [
        v for v in user_vouchers
        if v.status == 'expired'
    ]

    return render_template(
        'vouchers.html',
        vouchers_valid=vouchers_valid,
        vouchers_expired=vouchers_expired,
        voucher_active_count=len(vouchers_valid),
        server_now=now_wib(),
    )


@current_app.route('/account')
@login_required
def account():

    return render_template(
        'account.html',
        user=current_user
    )


@current_app.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():

    if request.method == 'POST':

        username = request.form.get('username')
        email = request.form.get('email')

        if username and username.strip() != '':
            current_user.username = username.strip()

        if email and email.strip() != '':
            current_user.email = email.strip()

        image = request.files.get('profile_image')

        if image and image.filename != '':

            filename = secure_filename(image.filename)

            ext = filename.rsplit('.', 1)[1].lower()

            new_filename = f"user_{current_user.id}.{ext}"

            upload_folder = os.path.join(
                current_app.root_path,
                'static',
                'uploads',
                'profile'
            )

            os.makedirs(upload_folder, exist_ok=True)

            upload_path = os.path.join(
                upload_folder,
                new_filename
            )

            image.save(upload_path)

            current_user.profile_image = (
                f'uploads/profile/{new_filename}'
            )

        db.session.commit()

        flash(
            'Profile updated successfully!',
            'success'
        )

        return redirect(url_for('account'))

    return render_template(
        'edit_profile.html',
        user=current_user
    )


@current_app.route('/change-password', methods=['POST'])
@login_required
def change_password():

    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    # cek password lama
    if current_user.password_hash != current_password:

        flash('Current password is incorrect', 'danger')

        return redirect(
            url_for('account')
        )

    # cek konfirmasi password
    if new_password != confirm_password:

        flash('New password does not match', 'danger')

        return redirect(
            url_for('account')
        )

    # update password baru
    current_user.password_hash = new_password

    db.session.commit()

    flash(
        'Password changed successfully!',
        'success'
    )

    return redirect(
        url_for('account')
    )

@current_app.route('/api/admin/notifications', methods=['GET'])
@login_required
@admin_required
def api_admin_notifications():
    unread_only = request.args.get('unread_only', 'true').lower() == 'true'
    query = Notification.query
    if unread_only:
        query = query.filter_by(is_read=False)
    
    notifs = query.order_by(Notification.id.desc()).limit(20).all()
    
    data = []
    for n in notifs:
        data.append({
            'id': n.id,
            'message': n.message,
            'is_read': n.is_read,
            'created_at': _relative_time_id(n.created_at),
            'transaction_id': n.transaction_id,
            'url': url_for('transaction_detail', transaction_id=n.transaction_id) if n.transaction_id else '#'
        })
        
    return jsonify({'status': 'success', 'data': data})

@current_app.route('/api/admin/notifications/<int:id>/read', methods=['POST'])
@login_required
@admin_required
def api_admin_notification_read(id):
    notif = Notification.query.get_or_404(id)
    notif.is_read = True
    db.session.commit()
    return jsonify({'status': 'success'})

@current_app.route('/api/admin/notifications/read-all', methods=['POST'])
@login_required
@admin_required
def api_admin_notification_read_all():
    Notification.query.filter_by(is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'status': 'success'})