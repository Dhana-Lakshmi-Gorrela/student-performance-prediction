"""Create the database/tables and the default admin account (admin / admin123)."""
import db
from app import app
from werkzeug.security import generate_password_hash

db.init_db()
with app.app_context():
    if not db.query("SELECT id FROM users WHERE username = %s", ("admin",), one=True):
        db.execute("INSERT INTO users (username, password_hash, role) VALUES (%s,%s,%s)",
                   ("admin", generate_password_hash("admin123"), "admin"))
print("Database ready. Login: admin / admin123  (change it after first login)")
