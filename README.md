# Student Performance Prediction System

Flask + MySQL + scikit-learn web app that predicts student results, classifies them
(Excellent / Good / Average / Poor), flags at-risk students and gives personalised advice.

## Quick start

```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then put your MySQL password in .env
python init_db.py             # creates database, tables and admin user
python seed_demo.py           # optional: 30 demo students with history
python app.py                 # open http://127.0.0.1:5000
```
Login: `admin` / `admin123` (change it: Users page -> add a new admin, remove the old one).

No MySQL? Set `DB_TYPE=sqlite` in `.env` and run the same commands.

## Features -> where to find them
| Feature | Location |
|---|---|
| Student data & profiles | Students, `/students/<id>` |
| Attendance, marks, study hours, assignments | tabs on the student profile |
| Visualisation (Plotly) | profile, dashboard, analytics |
| ML prediction + category + risk | `Predict performance` button |
| Weak student identification | At-risk page, dashboard |
| Subject-wise analysis | profile charts, Analytics |
| Improvement suggestions | prediction result, report |
| Prediction history | `/students/<id>/history` |
| Reports | `/students/<id>/report` (print / save as PDF), CSV export on dashboard |
| Admin dashboard and users | Dashboard, Users (admin only) |

## Machine learning
`ml/model.py` trains a RandomForestRegressor on 4 features: attendance %, previous marks,
study hours/week and assignment %. It predicts the final score (0-100):
Excellent >= 85, Good >= 70, Average >= 50, Poor < 50. Risk (High/Medium/Low) uses the score,
attendance and assignments.

By default it trains on generated data. To use your own records, make a CSV with columns
`attendance, prev_marks, study_hours, assignment_score, final_score` and run:
`python -m ml.train data/students.csv`

## Structure
```
app.py          routes and logic        db.py / schema.sql   database
ml/model.py     training + prediction   templates/ static/   UI
init_db.py      setup                   seed_demo.py         demo data
```
