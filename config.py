import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "biblioregister-secret-key-change-me")

    # Firebase Hosting only forwards the cookie named "__session"
    SESSION_COOKIE_NAME = "__session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7   # 7 days

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Library settings
    MAX_LOANS_PER_STUDENT = int(os.environ.get("MAX_LOANS_PER_STUDENT", 3))
    DEFAULT_LOAN_DAYS = int(os.environ.get("DEFAULT_LOAN_DAYS", 30))
    MAX_RENEWALS = int(os.environ.get("MAX_RENEWALS", 2))

    # Default admin credentials (only used on first run)
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "biblio2025")

    # Firebase / Firestore
    FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "biblioutes")
    FIREBASE_CREDENTIALS = os.environ.get("FIREBASE_CREDENTIALS")  # path to service account JSON
