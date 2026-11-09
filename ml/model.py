"""Machine-learning core: training, prediction, classification, risk and advice."""
import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

BASE = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE, "model.joblib")
META_PATH = os.path.join(BASE, "model_meta.json")

FEATURES = ["attendance", "prev_marks", "study_hours", "assignment_score"]
LABELS = {
    "attendance": "Attendance %",
    "prev_marks": "Previous marks",
    "study_hours": "Study hours / week",
    "assignment_score": "Assignment score %",
}
_cache = {}


def synthetic_data(n=3000, seed=42):
    """Realistic training data used when no real CSV is supplied."""
    rng = np.random.default_rng(seed)
    ability = rng.normal(0, 1, n)
    prev = np.clip(62 + 13 * ability + rng.normal(0, 6, n), 15, 100)
    att = np.clip(78 + 9 * ability + rng.normal(0, 10, n), 30, 100)
    study = np.clip(12 + 4 * ability + rng.normal(0, 4, n), 0, 40)
    assign = np.clip(66 + 11 * ability + rng.normal(0, 9, n), 0, 100)
    final = (0.42 * prev + 0.18 * att + 0.15 * assign
             + 0.9 * np.minimum(study, 20) - np.maximum(60 - att, 0) * 0.3
             + rng.normal(0, 3.5, n))
    return pd.DataFrame({
        "attendance": att, "prev_marks": prev, "study_hours": study,
        "assignment_score": assign, "final_score": np.clip(final, 0, 100),
    })


def train(csv_path=None):
    """Train the model. CSV columns: attendance, prev_marks, study_hours,
    assignment_score, final_score."""
    if csv_path and os.path.exists(csv_path):
        df, source = pd.read_csv(csv_path), os.path.basename(csv_path)
    else:
        df, source = synthetic_data(), "synthetic"
    X, y = df[FEATURES], df["final_score"]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=42, n_jobs=-1)
    model.fit(X_tr, y_tr)
    pred = model.predict(X_te)
    meta = {
        "source": source, "samples": int(len(df)),
        "r2": round(float(r2_score(y_te, pred)), 3),
        "mae": round(float(mean_absolute_error(y_te, pred)), 2),
        "importance": {f: round(float(i), 3) for f, i in zip(FEATURES, model.feature_importances_)},
    }
    joblib.dump(model, MODEL_PATH)
    json.dump(meta, open(META_PATH, "w"), indent=2)
    _cache.clear()
    return meta


def _model():
    if "m" not in _cache:
        if not os.path.exists(MODEL_PATH):
            train()
        _cache["m"] = joblib.load(MODEL_PATH)
    return _cache["m"]


def meta():
    if not os.path.exists(META_PATH):
        train()
    return json.load(open(META_PATH))


def predict(attendance, prev_marks, study_hours, assignment_score):
    row = pd.DataFrame([[attendance, prev_marks, study_hours, assignment_score]], columns=FEATURES)
    return round(float(np.clip(_model().predict(row)[0], 0, 100)), 1)


def classify(score):
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 50:
        return "Average"
    return "Poor"


def risk_level(score, attendance, assignment_score):
    if score < 50 or attendance < 60:
        return "High"
    if score < 65 or attendance < 75 or assignment_score < 50:
        return "Medium"
    return "Low"


def suggestions(v, weak_subjects, category):
    """Rule-based, personalised advice built from the student's weakest signals."""
    tips = []
    if v["attendance"] < 75:
        tips.append(f"Attendance is {v['attendance']:.0f}%. Aim for at least 85%: missed classes are the "
                    "fastest way to fall behind. Agree a weekly attendance target with a mentor.")
    if v["study_hours"] < 10:
        tips.append(f"Study time is {v['study_hours']:.0f} h/week. Build up to 12-15 h with short daily "
                    "sessions (45 min study, 10 min break) at a fixed time.")
    if v["assignment_score"] < 60:
        tips.append(f"Assignment average is {v['assignment_score']:.0f}%. Start assignments earlier and "
                    "ask for feedback on each one before the next is due.")
    if v["prev_marks"] < 50:
        tips.append("Previous marks are below the pass-comfort zone. Revise fundamentals and solve past "
                    "papers weekly; consider remedial classes.")
    for subject, avg in weak_subjects[:3]:
        tips.append(f"{subject} is a weak subject (average {avg:.0f}). Schedule extra practice and a "
                    "doubt-clearing session with the subject teacher.")
    if category == "Poor":
        tips.append("Priority: arrange a one-to-one meeting with a teacher and a short weekly progress review.")
    if not tips:
        tips.append("Strong profile. Keep the routine going and try advanced problems or peer tutoring "
                    "to stay challenged.")
    return tips
