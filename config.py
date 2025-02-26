import os
from dotenv import load_dotenv
from datetime import timedelta
# Load environment variables from .env
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "default_secret_key")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)  # Token expiration time
#     TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
#     TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
#     TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
# # 