import csv
import io
from datetime import date, datetime

import pandas as pd
from flask import (Flask, Response, abort, flash, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import db
from config import Config
from ml import model as ml

app = Flask(__name__)
app.config.from_object(Config)
app.teardown_appcontext(db.close_db)

CATEGORIES = ["Excellent", "Good", "Average", "Poor"]
TABLES = {"marks": "marks", "attendance": "attendance",
          "study": "study_logs", "assignment": "assignments"}

LATEST_PRED = """(SELECT p.* FROM predictions p
                  JOIN (SELECT student_id, MAX(id) mid FROM predictions GROUP BY student_id) m
                  ON p.id = m.mid)"""

METRICS_SQL = """
SELECT s.id, s.name, s.roll_no, s.department,
  (SELECT AVG(percentage) FROM attendance a WHERE a.student_id = s.id) AS attendance,
  (SELECT AVG(marks) FROM marks m WHERE m.student_id = s.id) AS prev_marks,
  (SELECT AVG(hours) FROM study_logs l WHERE l.student_id = s.id) AS study_hours,
  (SELECT AVG(score * 100.0 / max_score) FROM assignments x WHERE x.student_id = s.id) AS assignment_score
FROM students s"""


# ------------------------------------------------------------------ helpers
def num(v, default=None):
    try:
        return round(float(v), 1)
    except (TypeError, ValueError):
        return default


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def metrics_for(sid):
    row = db.query(METRICS_SQL + " WHERE s.id = %s", (sid,), one=True)
    return {k: num(row[k]) for k in ml.FEATURES}


def all_metrics():
    rows = db.query(METRICS_SQL + " ORDER BY s.name")
    for r in rows:
        for k in ml.FEATURES:
            r[k] = num(r[k])
    return rows


def weak_subjects(sid):
    rows = db.query("SELECT subject, AVG(marks) AS avg FROM marks WHERE student_id = %s "
                    "GROUP BY subject HAVING AVG(marks) < %s ORDER BY avg", (sid, 50))
    return [(r["subject"], float(r["avg"])) for r in rows]


def get_student(sid):
    s = db.query("SELECT * FROM students WHERE id = %s", (sid,), one=True)
    if not s:
        abort(404)
    return s


def run_prediction(sid, vals, created_at=None):
    score = ml.predict(**vals)
    cat = ml.classify(score)
    risk = ml.risk_level(score, vals["attendance"], vals["assignment_score"])
    tips = ml.suggestions(vals, weak_subjects(sid), cat)
    cols = "student_id, attendance, prev_marks, study_hours, assignment_score, predicted_score, category, risk_level, suggestions"
    args = [sid, vals["attendance"], vals["prev_marks"], vals["study_hours"],
            vals["assignment_score"], score, cat, risk, "\n".join(tips)]
    if created_at:
        cols += ", created_at"
        args.append(created_at)
    marks = ",".join(["%s"] * len(args))
    pid = db.execute(f"INSERT INTO predictions ({cols}) VALUES ({marks})", args)
    return {"id": pid, "score": score, "category": cat, "risk": risk, "tips": tips}


def student_charts(sid):
    d = lambda x: str(x)[:10]
    subj = db.query("SELECT subject, AVG(marks) a FROM marks WHERE student_id=%s GROUP BY subject ORDER BY subject", (sid,))
    terms = db.query("SELECT term, AVG(marks) a FROM marks WHERE student_id=%s GROUP BY term ORDER BY MIN(id)", (sid,))
    att = db.query("SELECT record_date d, percentage v FROM attendance WHERE student_id=%s ORDER BY record_date", (sid,))
    study = db.query("SELECT log_date d, hours v FROM study_logs WHERE student_id=%s ORDER BY log_date", (sid,))
    preds = db.query("SELECT created_at d, predicted_score v FROM predictions WHERE student_id=%s ORDER BY id", (sid,))
    return {
        "subjects": {"x": [r["subject"] for r in subj], "y": [num(r["a"]) for r in subj]},
        "terms": {"x": [r["term"] for r in terms], "y": [num(r["a"]) for r in terms]},
        "attendance": {"x": [d(r["d"]) for r in att], "y": [num(r["v"]) for r in att]},
        "study": {"x": [d(r["d"]) for r in study], "y": [num(r["v"]) for r in study]},
        "predictions": {"x": [str(r["d"])[:16] for r in preds], "y": [num(r["v"]) for r in preds]},
    }


# ------------------------------------------------------------------ auth
@app.before_request
def require_login():
    if request.endpoint in ("login", "static") or request.endpoint is None:
        return
    if "user" not in session:
        return redirect(url_for("login"))


def admin_only():
    if session.get("role") != "admin":
        abort(403)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db.query("SELECT * FROM users WHERE username = %s", (request.form["username"].strip(),), one=True)
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session.update(user=u["username"], role=u["role"])
            return redirect(url_for("dashboard"))
        flash("Wrong username or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin/users", methods=["GET", "POST"])
def users():
    admin_only()
    if request.method == "POST":
        try:
            db.execute("INSERT INTO users (username, password_hash, role) VALUES (%s,%s,%s)",
                       (request.form["username"].strip(), generate_password_hash(request.form["password"]),
                        request.form["role"]))
            flash("User created.", "success")
        except db.IntegrityError:
            flash("That username is already taken.", "danger")
        return redirect(url_for("users"))
    return render_template("users.html", users=db.query("SELECT id, username, role FROM users ORDER BY id"))


@app.route("/admin/users/<int:uid>/delete", methods=["POST"])
def delete_user(uid):
    admin_only()
    u = db.query("SELECT username FROM users WHERE id=%s", (uid,), one=True)
    if u and u["username"] != session["user"]:
        db.execute("DELETE FROM users WHERE id = %s", (uid,))
        flash("User removed.", "success")
    return redirect(url_for("users"))


# ------------------------------------------------------------------ dashboard
@app.route("/")
def dashboard():
    metrics = all_metrics()
    latest = db.query(f"SELECT l.*, s.name, s.roll_no FROM {LATEST_PRED} l JOIN students s ON s.id = l.student_id")
    dist = {c: 0 for c in CATEGORIES}
    for p in latest:
        dist[p["category"]] += 1
    at_risk = sorted([p for p in latest if p["risk_level"] != "Low"],
                     key=lambda p: float(p["predicted_score"]))
    vals = lambda k: [m[k] for m in metrics if m[k] is not None]
    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else 0
    scatter = [{"name": m["name"], "x": m["attendance"], "y": m["prev_marks"]}
               for m in metrics if m["attendance"] is not None and m["prev_marks"] is not None]
    return render_template(
        "dashboard.html", total=len(metrics), predicted=len(latest), at_risk=at_risk,
        avg_att=avg(vals("attendance")), avg_marks=avg(vals("prev_marks")),
        dist=dist, scatter=scatter,
        recent=db.query("SELECT p.*, s.name FROM predictions p JOIN students s ON s.id=p.student_id ORDER BY p.id DESC LIMIT 6"))


@app.route("/at-risk")
def at_risk():
    rows = db.query(f"SELECT l.*, s.name, s.roll_no, s.department FROM {LATEST_PRED} l "
                    "JOIN students s ON s.id = l.student_id WHERE l.risk_level <> %s "
                    "ORDER BY l.predicted_score", ("Low",))
    return render_template("at_risk.html", rows=rows)


@app.route("/analytics")
def analytics():
    subjects = db.query("SELECT subject, AVG(marks) avg, MIN(marks) lo, MAX(marks) hi, COUNT(*) n, "
                        "SUM(CASE WHEN marks < 40 THEN 1 ELSE 0 END) failing FROM marks "
                        "GROUP BY subject ORDER BY avg")
    for r in subjects:
        r["avg"], r["lo"], r["hi"] = num(r["avg"]), num(r["lo"]), num(r["hi"])
    rows = all_metrics()
    df = pd.DataFrame(rows).dropna(subset=ml.FEATURES) if rows else pd.DataFrame()
    corr = {}
    if len(df) >= 3:
        for f in ("attendance", "study_hours", "assignment_score"):
            c = df[f].corr(df["prev_marks"])
            corr[ml.LABELS[f]] = round(float(c), 2) if c == c else 0
    return render_template("analytics.html", subjects=subjects, corr=corr, meta=ml.meta(), labels=ml.LABELS)


@app.route("/export/predictions.csv")
def export_predictions():
    rows = db.query("SELECT s.roll_no, s.name, p.created_at, p.attendance, p.prev_marks, p.study_hours, "
                    "p.assignment_score, p.predicted_score, p.category, p.risk_level "
                    "FROM predictions p JOIN students s ON s.id = p.student_id ORDER BY p.id DESC")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Roll No", "Name", "Date", "Attendance", "Previous Marks", "Study Hours",
                "Assignment %", "Predicted Score", "Category", "Risk"])
    for r in rows:
        w.writerow([r["roll_no"], r["name"], str(r["created_at"])[:16], r["attendance"], r["prev_marks"],
                    r["study_hours"], r["assignment_score"], r["predicted_score"], r["category"], r["risk_level"]])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=predictions.csv"})


# ------------------------------------------------------------------ students
@app.route("/students")
def students():
    q = f"%{request.args.get('q', '').strip()}%"
    rows = db.query(f"SELECT s.*, p.predicted_score, p.category, p.risk_level FROM students s "
                    f"LEFT JOIN {LATEST_PRED} p ON p.student_id = s.id "
                    "WHERE s.name LIKE %s OR s.roll_no LIKE %s ORDER BY s.name", (q, q))
    return render_template("students.html", rows=rows, q=request.args.get("q", ""))


@app.route("/students/add", methods=["GET", "POST"])
@app.route("/students/<int:sid>/edit", methods=["GET", "POST"])
def student_form(sid=None):
    student = get_student(sid) if sid else {}
    if request.method == "POST":
        f = request.form
        data = (f["roll_no"].strip(), f["name"].strip(), f.get("email", "").strip(), f.get("phone", "").strip(),
                f.get("department", "").strip(), int(f.get("year_of_study") or 1))
        try:
            if sid:
                db.execute("UPDATE students SET roll_no=%s, name=%s, email=%s, phone=%s, department=%s, "
                           "year_of_study=%s WHERE id=%s", data + (sid,))
            else:
                sid = db.execute("INSERT INTO students (roll_no, name, email, phone, department, year_of_study) "
                                 "VALUES (%s,%s,%s,%s,%s,%s)", data)
            flash("Student saved.", "success")
            return redirect(url_for("student_detail", sid=sid))
        except db.IntegrityError:
            flash("A student with this roll number already exists.", "danger")
            student = dict(zip(["roll_no", "name", "email", "phone", "department", "year_of_study"], data))
    return render_template("student_form.html", s=student, editing=bool(sid))


@app.route("/students/<int:sid>/delete", methods=["POST"])
def delete_student(sid):
    admin_only()
    db.execute("DELETE FROM students WHERE id = %s", (sid,))
    flash("Student deleted.", "success")
    return redirect(url_for("students"))


@app.route("/students/<int:sid>")
def student_detail(sid):
    s = get_student(sid)
    q = lambda t, order: db.query(f"SELECT * FROM {t} WHERE student_id = %s ORDER BY {order}", (sid,))
    latest = db.query("SELECT * FROM predictions WHERE student_id=%s ORDER BY id DESC LIMIT 1", (sid,), one=True)
    return render_template(
        "student_detail.html", s=s, m=metrics_for(sid), charts=student_charts(sid), latest=latest,
        weak=weak_subjects(sid), today=date.today().isoformat(),
        marks=q("marks", "id DESC"), attendance=q("attendance", "record_date DESC"),
        study=q("study_logs", "log_date DESC"), assignments=q("assignments", "id DESC"))


@app.route("/students/<int:sid>/add/<kind>", methods=["POST"])
def add_record(sid, kind):
    get_student(sid)
    f = request.form
    try:
        if kind == "marks":
            db.execute("INSERT INTO marks (student_id, subject, term, marks) VALUES (%s,%s,%s,%s)",
                       (sid, f["subject"].strip(), f["term"].strip(), clamp(float(f["marks"]), 0, 100)))
        elif kind == "attendance":
            db.execute("INSERT INTO attendance (student_id, record_date, percentage) VALUES (%s,%s,%s)",
                       (sid, f["date"], clamp(float(f["percentage"]), 0, 100)))
        elif kind == "study":
            db.execute("INSERT INTO study_logs (student_id, log_date, hours) VALUES (%s,%s,%s)",
                       (sid, f["date"], clamp(float(f["hours"]), 0, 80)))
        elif kind == "assignment":
            mx = float(f["max_score"])
            if mx <= 0:
                raise ValueError
            db.execute("INSERT INTO assignments (student_id, subject, title, score, max_score) VALUES (%s,%s,%s,%s,%s)",
                       (sid, f["subject"].strip(), f["title"].strip(), clamp(float(f["score"]), 0, mx), mx))
        else:
            abort(404)
        flash("Record added.", "success")
    except (ValueError, KeyError):
        flash("Please fill every field with valid values.", "danger")
    return redirect(url_for("student_detail", sid=sid) + f"#tab-{kind}")


@app.route("/students/<int:sid>/delete/<kind>/<int:rid>", methods=["POST"])
def delete_record(sid, kind, rid):
    if kind not in TABLES:
        abort(404)
    db.execute(f"DELETE FROM {TABLES[kind]} WHERE id = %s AND student_id = %s", (rid, sid))
    return redirect(url_for("student_detail", sid=sid) + f"#tab-{kind}")


# ------------------------------------------------------------------ predictions
@app.route("/students/<int:sid>/predict", methods=["GET", "POST"])
def predict(sid):
    s = get_student(sid)
    m = metrics_for(sid)
    result = None
    if request.method == "POST":
        try:
            vals = {
                "attendance": clamp(float(request.form["attendance"]), 0, 100),
                "prev_marks": clamp(float(request.form["prev_marks"]), 0, 100),
                "study_hours": clamp(float(request.form["study_hours"]), 0, 80),
                "assignment_score": clamp(float(request.form["assignment_score"]), 0, 100),
            }
            previous = db.query("SELECT predicted_score FROM predictions WHERE student_id=%s ORDER BY id DESC LIMIT 1",
                                (sid,), one=True)
            result = run_prediction(sid, vals)
            result["previous"] = float(previous["predicted_score"]) if previous else None
            m = vals
        except (ValueError, KeyError):
            flash("Enter valid numbers in every field.", "danger")
    prefill = {k: (m[k] if m[k] is not None else 0) for k in ml.FEATURES}
    missing = [ml.LABELS[k] for k in ml.FEATURES if metrics_for(sid)[k] is None]
    return render_template("predict.html", s=s, v=prefill, result=result, missing=missing, labels=ml.LABELS)


@app.route("/students/<int:sid>/history")
def history(sid):
    s = get_student(sid)
    rows = db.query("SELECT * FROM predictions WHERE student_id=%s ORDER BY id DESC", (sid,))
    for i, r in enumerate(rows):
        older = rows[i + 1] if i + 1 < len(rows) else None
        r["delta"] = round(float(r["predicted_score"]) - float(older["predicted_score"]), 1) if older else None
        r["tips"] = (r["suggestions"] or "").split("\n")
    return render_template("history.html", s=s, rows=rows, charts=student_charts(sid))


@app.route("/students/<int:sid>/report")
def report(sid):
    s = get_student(sid)
    latest = db.query("SELECT * FROM predictions WHERE student_id=%s ORDER BY id DESC LIMIT 1", (sid,), one=True)
    subjects = db.query("SELECT subject, AVG(marks) avg, MIN(marks) lo, MAX(marks) hi FROM marks "
                        "WHERE student_id=%s GROUP BY subject ORDER BY avg", (sid,))
    for r in subjects:
        r["avg"], r["lo"], r["hi"] = num(r["avg"]), num(r["lo"]), num(r["hi"])
    return render_template("report.html", s=s, m=metrics_for(sid), latest=latest, subjects=subjects,
                           tips=(latest["suggestions"].split("\n") if latest else []),
                           charts=student_charts(sid), now=datetime.now().strftime("%d %b %Y, %H:%M"))


if __name__ == "__main__":
    app.run(debug=False)
