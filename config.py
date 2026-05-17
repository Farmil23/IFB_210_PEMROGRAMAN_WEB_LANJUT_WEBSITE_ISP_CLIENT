import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


def _env_bool(key, default=False):

    v = os.environ.get(key)

    if v is None:

        return default

    return str(v).strip().lower() in ('1', 'true', 'yes', 'on')


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kunci-cadangan-default' ## NGAMBIL SECRET_KEY DARI FILE .ENV
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI')  
    SQLALCHEMY_TRACK_MODIFICATIONS = False 

    # PRODUCTION=false → mode presentasi/demo: voucher bisa checkout walau belum ada router di DB
    PRODUCTION = _env_bool('PRODUCTION', default=True)

    # Hanya jika PRODUCTION=false: hapus transaksi/voucher/paket/router & isi dummy (satu kali tiap start app)
    DEMO_RESET_ON_START = _env_bool('DEMO_RESET_ON_START', default=False)

    # URL publik aplikasi (wajib untuk Stripe success_url saat dev pakai ngrok), contoh:
    # https://abc123.ngrok-free.app
    APP_BASE_URL = (os.environ.get('APP_BASE_URL') or '').rstrip('/')

    APP_TIMEZONE = 'Asia/Jakarta'
    
    # Konfigurasi tambahan untuk SSL Aiven MySQL
    SQLALCHEMY_ENGINE_OPTIONS = {}