import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kunci-cadangan-default' ## NGAMBIL SECRET_KEY DARI FILE .ENV
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI')  
    SQLALCHEMY_TRACK_MODIFICATIONS = False 
    
    # Konfigurasi tambahan untuk SSL Aiven MySQL
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "ssl": {
                "ca": os.path.join(basedir, "ca.pem") ## MEMANGGIL SSL KEAMANAN (HIRAUKAN AJA YA)
            }
        }
    }