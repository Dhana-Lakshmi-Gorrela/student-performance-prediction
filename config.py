import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    DB_TYPE = os.getenv("DB_TYPE", "mysql").lower()      # "mysql" or "sqlite"
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "student_performance")
    SQLITE_PATH = os.getenv("SQLITE_PATH", "student_performance.db")
