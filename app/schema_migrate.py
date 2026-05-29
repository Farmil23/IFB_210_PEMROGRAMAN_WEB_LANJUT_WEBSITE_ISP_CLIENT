from sqlalchemy import inspect, text

from . import db
from .models import Package, Voucher, Transaction


def ensure_schema():

    dialect = db.engine.dialect.name

    def _add_package_voucher_hours():

        insp = inspect(db.engine)

        table = Package.__tablename__

        if table not in insp.get_table_names():

            return

        cols = {c['name'] for c in insp.get_columns(table)}

        if 'voucher_duration_hours' in cols:

            return

        if dialect == 'sqlite':

            sql = text(
                f'ALTER TABLE {table} ADD COLUMN voucher_duration_hours INTEGER'
            )

        else:

            sql = text(
                f'ALTER TABLE {table} ADD COLUMN voucher_duration_hours INT NULL'
            )

        db.session.execute(sql)

        db.session.commit()

    def _add_voucher_expires_at():

        insp = inspect(db.engine)

        table = Voucher.__tablename__

        if table not in insp.get_table_names():

            return

        cols = {c['name'] for c in insp.get_columns(table)}

        if 'expires_at' in cols:

            return

        if dialect == 'sqlite':

            sql = text(
                f'ALTER TABLE {table} ADD COLUMN expires_at DATETIME'
            )

        else:

            sql = text(
                f'ALTER TABLE {table} ADD COLUMN expires_at DATETIME NULL'
            )

        db.session.execute(sql)

        db.session.commit()

    def _unique_voucher_per_transaction():

        insp = inspect(db.engine)

        table = Voucher.__tablename__

        if table not in insp.get_table_names():

            return

        for ix in insp.get_indexes(table):

            if not ix.get('unique'):

                continue

            ix_cols = list(ix.get('column_names') or [])

            if ix_cols == ['transaction_id']:

                return

        if dialect == 'sqlite':

            stmt = text(
                'CREATE UNIQUE INDEX IF NOT EXISTS uq_voucher_transaction_id '
                f'ON {table} (transaction_id)'
            )

        else:

            stmt = text(
                f'ALTER TABLE {table} ADD UNIQUE KEY uq_voucher_transaction_id '
                '(transaction_id)'
            )

        db.session.execute(stmt)

        db.session.commit()

    def _add_transaction_paid_at():

        insp = inspect(db.engine)

        table = Transaction.__tablename__

        if table not in insp.get_table_names():

            return

        cols = {c['name'] for c in insp.get_columns(table)}

        if 'paid_at' in cols:

            return

        if dialect == 'sqlite':

            sql = text(
                f'ALTER TABLE {table} ADD COLUMN paid_at DATETIME'
            )

        else:

            sql = text(
                f'ALTER TABLE {table} ADD COLUMN paid_at DATETIME NULL'
            )

        db.session.execute(sql)

        db.session.commit()

    def _add_voucher_valid_from():

        insp = inspect(db.engine)

        table = Voucher.__tablename__

        if table not in insp.get_table_names():

            return

        cols = {c['name'] for c in insp.get_columns(table)}

        if 'valid_from' in cols:

            return

        if dialect == 'sqlite':

            sql = text(
                f'ALTER TABLE {table} ADD COLUMN valid_from DATETIME'
            )

        else:

            sql = text(
                f'ALTER TABLE {table} ADD COLUMN valid_from DATETIME NULL'
            )

        db.session.execute(sql)

        db.session.commit()

    def _add_router_ip_address():

        from .models import HotspotRouter

        insp = inspect(db.engine)

        table = HotspotRouter.__tablename__

        if table not in insp.get_table_names():

            return

        cols = {c['name'] for c in insp.get_columns(table)}

        if 'ip_address' in cols:

            return

        if dialect == 'sqlite':

            sql = text(
                f'ALTER TABLE {table} ADD COLUMN ip_address VARCHAR(64)'
            )

        else:

            sql = text(
                f'ALTER TABLE {table} ADD COLUMN ip_address VARCHAR(64) NULL'
            )

        db.session.execute(sql)

        db.session.commit()

    def _create_notification_table():

        from .models import Notification

        insp = inspect(db.engine)

        if Notification.__tablename__ not in insp.get_table_names():

            Notification.__table__.create(db.engine)

    for fn in (
        _add_package_voucher_hours,
        _add_voucher_expires_at,
        _add_transaction_paid_at,
        _add_voucher_valid_from,
        _unique_voucher_per_transaction,
        _add_router_ip_address,
        _create_notification_table,
    ):

        try:

            fn()

        except Exception:

            db.session.rollback()

