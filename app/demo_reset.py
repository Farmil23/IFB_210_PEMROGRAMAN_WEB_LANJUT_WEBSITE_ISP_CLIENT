"""
Reset & seed data untuk presentasi.

Hanya jalan jika PRODUCTION=false DAN DEMO_RESET_ON_START=true.
Menghapus voucher, transaksi, paket, router lalu mengisi ulang dummy yang konsisten.

Pengguna produksi: jangan set kedua flag tersebut.
"""

from flask import Flask

from . import db
from .models import HotspotRouter, Package, Transaction, Voucher


def maybe_reset_demo_environment(app: Flask) -> None:

    if app.config.get('PRODUCTION', True):

        return

    if not app.config.get('DEMO_RESET_ON_START'):

        return

    Voucher.query.delete()
    Transaction.query.delete()
    HotspotRouter.query.delete()
    Package.query.delete()

    db.session.commit()

    packages = [
        Package(
            name='Voucher 8 Jam',
            package_type='jam-jaman',
            price=15000,
            speed='Up to 10 Mbps',
            voucher_duration_hours=8,
        ),
        Package(
            name='Voucher 3 Jam',
            package_type='jam-jaman',
            price=5000,
            speed='Up to 10 Mbps',
            voucher_duration_hours=3,
        ),
        Package(
            name='Paket Bulanan Basic',
            package_type='bulanan',
            price=150000,
            speed='20 Mbps',
            voucher_duration_hours=None,
        ),
    ]

    routers = [
        HotspotRouter(
            name='North Router (Campus)',
            notes='Dummy presentasi',
            is_active=True,
            sort_order=10,
        ),
        HotspotRouter(
            name='South Router (Dormitory)',
            notes='Dummy presentasi',
            is_active=True,
            sort_order=20,
        ),
        HotspotRouter(
            name='West Router (Cafeteria)',
            notes='Dummy presentasi',
            is_active=True,
            sort_order=30,
        ),
    ]

    db.session.add_all(packages)
    db.session.add_all(routers)
    db.session.commit()

    msg = (
        'DEMO_RESET_ON_START: transaksi/voucher/paket/router lama dihapus; '
        'data dummy presentasi dimasukkan (3 router + paket voucher).'
    )

    app.logger.warning(msg)
    print(msg)
