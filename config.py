import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "biblioregister-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(basedir, "biblioregister.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Library settings
    MAX_LOANS_PER_STUDENT = int(os.environ.get("MAX_LOANS_PER_STUDENT", 3))
    DEFAULT_LOAN_DAYS = int(os.environ.get("DEFAULT_LOAN_DAYS", 14))
    MAX_RENEWALS = int(os.environ.get("MAX_RENEWALS", 2))
