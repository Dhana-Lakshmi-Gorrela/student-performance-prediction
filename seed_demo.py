"""Fill the database with 30 demo students (marks, attendance, study, assignments, predictions)."""
import random
from datetime import date, datetime, timedelta

import db
from app import app, metrics_for, run_prediction

random.seed(7)
SUBJECTS = ["Mathematics", "Physics", "Chemistry", "English", "Computer Science"]
TERMS = ["Unit Test 1", "Mid Term", "Unit Test 2"]
NAMES = ("Aarav Sharma,Diya Reddy,Vihaan Patel,Ananya Iyer,Aditya Verma,Saanvi Gupta,Arjun Nair,Isha Kapoor,"
         "Rohan Mehta,Meera Joshi,Kabir Singh,Priya Das,Karthik Rao,Neha Bansal,Siddharth Menon,Tanvi Shah,"
         "Harsh Vardhan,Pooja Pillai,Manish Yadav,Kavya Krishnan,Rahul Chopra,Sneha Kulkarni,Varun Malhotra,"
         "Aisha Khan,Nikhil Jain,Riya Sen,Yash Agarwal,Divya Bhat,Imran Ali,Lakshmi Narayan").split(",")


def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


with app.app_context():
    if db.query("SELECT COUNT(*) c FROM students", one=True)["c"]:
        raise SystemExit("Students already exist - seed skipped.")
    for i, name in enumerate(NAMES, start=1):
        ability = random.gauss(0, 1)
        sid = db.execute("INSERT INTO students (roll_no, name, email, phone, department, year_of_study) "
                         "VALUES (%s,%s,%s,%s,%s,%s)",
                         (f"CS{2400 + i}", name, name.split()[0].lower() + "@college.edu",
                          f"98{random.randint(10000000, 99999999)}", "Computer Science", random.choice([1, 2, 3])))
        for subj in SUBJECTS:
            bias = random.gauss(0, 8)
            for t, term in enumerate(TERMS):
                db.execute("INSERT INTO marks (student_id, subject, term, marks) VALUES (%s,%s,%s,%s)",
                           (sid, subj, term, round(clamp(62 + 13 * ability + bias + t * 1.5 + random.gauss(0, 5)), 1)))
            for k in (1, 2):
                db.execute("INSERT INTO assignments (student_id, subject, title, score, max_score) VALUES (%s,%s,%s,%s,%s)",
                           (sid, subj, f"Assignment {k}", round(clamp(20 * (0.66 + 0.11 * ability + random.gauss(0, 0.08)), 0, 20), 1), 20))
        for w in range(4):
            db.execute("INSERT INTO attendance (student_id, record_date, percentage) VALUES (%s,%s,%s)",
                       (sid, (date.today() - timedelta(days=30 * (3 - w))).isoformat(),
                        round(clamp(78 + 9 * ability + random.gauss(0, 6)), 1)))
        for w in range(6):
            db.execute("INSERT INTO study_logs (student_id, log_date, hours) VALUES (%s,%s,%s)",
                       (sid, (date.today() - timedelta(days=7 * (5 - w))).isoformat(),
                        round(clamp(12 + 4 * ability + random.gauss(0, 2.5), 0, 40), 1)))
        m = metrics_for(sid)
        older = {k: round(m[k] * 0.93, 1) for k in m}
        run_prediction(sid, older, created_at=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S"))
        run_prediction(sid, m)
print("Seeded 30 demo students with prediction history.")
