from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import db
from ml import model as ml


class PredictionInput(BaseModel):
    attendance: float = Field(ge=0, le=100)
    prev_marks: float = Field(ge=0, le=100)
    study_hours: float = Field(ge=0, le=80)
    assignment_score: float = Field(ge=0, le=100)


app = FastAPI(
    title="Student Performance Prediction API",
    description="API for managing student performance data",
    version="1.0"
)


@app.get("/")
def home():
    return {
        "message": "Student Performance Prediction API is running!"
    }


@app.get("/students")
def get_students():
    conn = db.connect()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, roll_no, name, email, phone,
                   department, year_of_study
            FROM students
            ORDER BY name
            """
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/students/{student_id}")
def get_student(student_id: int):
    conn = db.connect()
    try:
        cursor = conn.cursor()
        placeholder = "?" if db.IS_SQLITE else "%s"

        cursor.execute(
            f"SELECT * FROM students WHERE id = {placeholder}",
            (student_id,)
        )

        student = cursor.fetchone()

        if student is None:
            raise HTTPException(
                status_code=404,
                detail="Student not found"
            )

        return dict(student)
    finally:
        conn.close()


@app.post("/students/{student_id}/predict")
def predict_student(student_id: int, data: PredictionInput):
    conn = db.connect()

    try:
        cursor = conn.cursor()
        placeholder = "?" if db.IS_SQLITE else "%s"

        # Check student
        cursor.execute(
            f"SELECT id FROM students WHERE id = {placeholder}",
            (student_id,)
        )

        student = cursor.fetchone()

        if student is None:
            raise HTTPException(
                status_code=404,
                detail="Student not found"
            )

        # Input values
        vals = {
            "attendance": data.attendance,
            "prev_marks": data.prev_marks,
            "study_hours": data.study_hours,
            "assignment_score": data.assignment_score
        }

        # Machine Learning prediction
        score = ml.predict(**vals)
        category = ml.classify(score)

        risk = ml.risk_level(
            score,
            vals["attendance"],
            vals["assignment_score"]
        )

        tips = ml.suggestions(vals, [], category)

        # Save prediction
        placeholders = ", ".join([placeholder] * 9)

        cursor.execute(
            f"""
            INSERT INTO predictions
            (
                student_id, attendance, prev_marks,
                study_hours, assignment_score,
                predicted_score, category, risk_level,
                suggestions
            )
            VALUES ({placeholders})
            """,
            (
                student_id,
                vals["attendance"],
                vals["prev_marks"],
                vals["study_hours"],
                vals["assignment_score"],
                score,
                category,
                risk,
                "\n".join(tips)
            )
        )

        prediction_id = cursor.lastrowid
        conn.commit()

        return {
            "prediction_id": prediction_id,
            "student_id": student_id,
            "predicted_score": score,
            "category": category,
            "risk_level": risk,
            "suggestions": tips
        }

    except HTTPException:
        conn.rollback()
        raise

    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        conn.close()
