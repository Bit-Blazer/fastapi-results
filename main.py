import re
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import zipfile
import io
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel
from datetime import datetime

from starlette.middleware.sessions import SessionMiddleware
from fastapi import Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import (
    get_db,
    Student,
    Subject,
    Grade,
    Semester,
    GradeChange,
    download_pdf,
)

app = FastAPI()
app.add_middleware(
    SessionMiddleware, secret_key="super-secret-key"
)  # use env var in prod

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# Pydantic models for API requests
class GradeChangeRequest(BaseModel):
    regno: str
    subject_code: str
    semester: int
    original_grade: str
    new_grade: str
    credits: int
    timestamp: str


# API endpoint to save grade changes
@app.post("/api/save-grade-change")
async def save_grade_change(
    grade_change: GradeChangeRequest, request: Request, db: Session = Depends(get_db)
):
    try:
        # Validate that the student exists
        student = db.query(Student).filter(Student.regno == grade_change.regno).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        # Create new grade change record
        grade_change_record = GradeChange(
            regno=grade_change.regno,
            subject_code=grade_change.subject_code,
            semester=grade_change.semester,
            original_grade=grade_change.original_grade,
            new_grade=grade_change.new_grade,
            credits=grade_change.credits,
            changed_at=datetime.utcnow(),
        )

        # Save to database
        db.add(grade_change_record)
        db.commit()
        db.refresh(grade_change_record)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Grade change saved successfully",
                "change_id": grade_change_record.id,
                "timestamp": grade_change_record.changed_at.isoformat(),
            },
        )

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Failed to save grade change: {str(e)}",
            },
        )


@app.get("/auth/{regno}")
def auth_form(regno: str, request: Request, db: Session = Depends(get_db)):
    # Check if student exists in database
    student = db.query(Student).filter(Student.regno == regno).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return templates.TemplateResponse(
        "auth.html",
        {
            "request": request,
            "regno": regno,
            "student_name": student.name,
            "error": None,
        },
    )


@app.post("/auth/{regno}")
def auth_submit(
    regno: str,
    dob: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    # Get student from database
    student = db.query(Student).filter(Student.regno == regno).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if dob.strip() == student.dob:
        request.session[regno] = True
        return RedirectResponse(url=f"/{regno}/", status_code=302)
    else:
        return templates.TemplateResponse(
            "auth.html",
            {
                "request": request,
                "regno": regno,
                "student_name": student.name,
                "error": "Incorrect DOB",
            },
        )


@app.get("/")
def index(request: Request, q: str = "", db: Session = Depends(get_db)):
    q = q.lower()

    # Query students from database
    query = db.query(Student)
    if q:
        query = query.filter(
            (Student.regno.ilike(f"%{q}%")) | (Student.name.ilike(f"%{q}%"))
        )

    students = query.all()
    results = [{"regno": student.regno, "name": student.name} for student in students]

    return templates.TemplateResponse(
        "index.html", {"request": request, "results": results, "q": q}
    )


@app.get("/{regno}/")
def student_page(regno: str, request: Request, db: Session = Depends(get_db)):
    if not request.session.get(regno):
        return RedirectResponse(url=f"/auth/{regno}", status_code=302)

    student = db.query(Student).filter(Student.regno == regno).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get semesters with grades from database
    semesters = (
        db.query(Semester)
        .filter(Semester.student_id == student.id)
        .order_by(Semester.semester)
        .all()
    )

    if not semesters:
        raise HTTPException(
            status_code=404, detail="No semester data found for student"
        )

    # Fetch latest grade changes and create a mapping
    grade_changes = (
        db.query(GradeChange)
        .filter(GradeChange.regno == regno)
        .order_by(GradeChange.changed_at.desc())
        .all()
    )

    # Create a mapping of latest grade changes by (subject_code, semester)
    latest_changes = {}
    for change in grade_changes:
        key = (change.subject_code, change.semester)
        if key not in latest_changes:  # Keep only the most recent change
            latest_changes[key] = change

    # Grade points mapping
    grade_points_map = {
        "O": 10,
        "A+": 9,
        "A": 8,
        "B+": 7,
        "B": 6,
        "C": 5,
        "U": 0,
        "AB": 0,
        "NA": 0,
    }

    # Prepare data for template
    file_data_list = []

    for semester in semesters:
        # Get grades for this semester with subject details
        grades = (
            db.query(Grade, Subject)
            .join(Subject, Grade.subject_id == Subject.id)
            .filter(Grade.semester_id == semester.id)
            .all()
        )

        # Calculate totals and prepare subjects list
        total_credits = 0
        updated_total_grade_points = 0
        subjects = []

        for grade, subject in grades:
            # Check if there's a grade change for this subject
            key = (subject.code, semester.semester)

            if key in latest_changes:
                # Use the changed grade
                change = latest_changes[key]
                current_grade = change.new_grade
                grade_points_earned = (
                    grade_points_map.get(change.new_grade, 0) * subject.credits
                )
            else:
                # Use original grade
                current_grade = grade.grade
                grade_points_earned = grade.grade_points_earned

            subjects.append(
                {
                    "code": subject.code,
                    "name": subject.name,
                    "grade": current_grade,
                    "credits": subject.credits,
                    "grade_points_earned": grade_points_earned,
                }
            )

            total_credits += subject.credits
            updated_total_grade_points += grade_points_earned

        # Calculate updated GPA
        updated_gpa = (
            updated_total_grade_points / total_credits if total_credits > 0 else 0
        )

        # Create semester data for template
        file_data_list.append(
            {
                "filename": f"{regno}_sem{semester.semester}.pdf",
                "sem": semester.semester,
                "gpa": float(semester.gpa) if semester.gpa else None,
                    "subjects": subjects,
                "total_credits": total_credits,
                "total_grade_points": updated_total_grade_points,
            }
        )

    return templates.TemplateResponse(
        "student.html",
        {
            "request": request,
            "regno": regno,
            "files": file_data_list,
            "student_name": student.name,
        },
    )


@app.get("/pdf/{regno}/{filename}")
def serve_pdf(
    regno: str, filename: str, request: Request, db: Session = Depends(get_db)
):
    # Check if user is authenticated for this student
    if not request.session.get(regno):
        raise HTTPException(status_code=403, detail="Access denied")

    # Get student from database
    student = db.query(Student).filter(Student.regno == regno).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    # Extract semester from filename (e.g., "113222031001_sem3.pdf" -> 3)
    semester_str = filename.replace(f"{regno}_sem", "").replace(".pdf", "")
    try:
        semester_num = int(semester_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename format")

    # Verify semester exists for this student
    semester_record = (
        db.query(Semester)
        .filter(Semester.student_id == student.id, Semester.semester == semester_num)
        .first()
    )

    if not semester_record:
        raise HTTPException(
            status_code=404, detail="Semester not found"
        )  # Build storage path directly (no need to query database)
    storage_path = f"{regno}/{regno}_sem{semester_num}.pdf"

    # Download PDF content from Supabase Storage
    pdf_content = download_pdf(storage_path)

    if not pdf_content:
        raise HTTPException(status_code=404, detail="PDF file not available")

    # Return PDF content with proper headers
    headers = {
        "Content-Disposition": f"inline; filename={filename}",
        "Content-Type": "application/pdf",
    }

    return Response(content=pdf_content, headers=headers)


@app.get("/zip/{regno}")
def zip_and_download_all(regno: str, request: Request, db: Session = Depends(get_db)):
    # Check if user is authenticated for this student
    if not request.session.get(regno):
        raise HTTPException(status_code=403, detail="Access denied")

    # Get student from database
    student = db.query(Student).filter(Student.regno == regno).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    # Get all semesters for this student
    semesters = db.query(Semester).filter(Semester.student_id == student.id).all()

    if not semesters:
        raise HTTPException(status_code=404, detail="No PDFs found for student")

    # Create a zip file in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for semester in semesters:
            # Build storage path directly
            storage_path = f"{regno}/{regno}_sem{semester.semester}.pdf"

            # Download PDF content from Supabase Storage
            pdf_content = download_pdf(storage_path)
            if pdf_content:
                filename = f"{regno}_sem{semester.semester}.pdf"
                zip_file.writestr(filename, pdf_content)

    zip_buffer.seek(0)

    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={regno}_results.zip"},
    )


# API endpoint to view grade changes (for administrative purposes)
@app.get("/api/grade-changes/{regno}")
async def get_grade_changes(regno: str, db: Session = Depends(get_db), limit: int = 50):
    """Get grade changes for a specific student (most recent first)"""
    try:
        # Verify student exists
        student = db.query(Student).filter(Student.regno == regno).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        # Get grade changes for this student
        grade_changes = (
            db.query(GradeChange)
            .filter(GradeChange.regno == regno)
            .order_by(GradeChange.changed_at.desc())
            .limit(limit)
            .all()
        )

        # Format the response
        changes_data = []
        for change in grade_changes:
            changes_data.append(
                {
                    "id": change.id,
                    "subject_code": change.subject_code,
                    "semester": change.semester,
                    "original_grade": change.original_grade,
                    "new_grade": change.new_grade,
                    "credits": change.credits,
                    "changed_at": change.changed_at.isoformat(),
                    "grade_difference": f"{change.original_grade} → {change.new_grade}",
                }
            )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "student_regno": regno,
                "student_name": student.name,
                "total_changes": len(changes_data),
                "changes": changes_data,
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Failed to retrieve grade changes: {str(e)}",
            },
        )


# API endpoint to get all grade changes (admin only)
@app.get("/api/grade-changes")
async def get_all_grade_changes(
    db: Session = Depends(get_db), limit: int = 100, offset: int = 0
):
    """Get all grade changes across all students (for administrative monitoring)"""
    try:
        # Get grade changes with student names
        grade_changes = (
            db.query(GradeChange, Student.name)
            .join(Student, GradeChange.regno == Student.regno)
            .order_by(GradeChange.changed_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        # Format the response
        changes_data = []
        for change, student_name in grade_changes:
            changes_data.append(
                {
                    "id": change.id,
                    "regno": change.regno,
                    "student_name": student_name,
                    "subject_code": change.subject_code,
                    "semester": change.semester,
                    "original_grade": change.original_grade,
                    "new_grade": change.new_grade,
                    "credits": change.credits,
                    "changed_at": change.changed_at.isoformat(),
                    "grade_difference": f"{change.original_grade} → {change.new_grade}",
                }
            )

        # Get total count
        total_changes = db.query(GradeChange).count()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "total_changes": total_changes,
                "showing": len(changes_data),
                "offset": offset,
                "limit": limit,
                "changes": changes_data,
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Failed to retrieve grade changes: {str(e)}",
            },
        )


# Admin route to view grade changes
@app.get("/admin/grade-changes")
async def admin_grade_changes(request: Request):
    """Admin page to monitor grade changes"""
    return templates.TemplateResponse("admin_grade_changes.html", {"request": request})


@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "404.html", {"request": request}, status_code=404
        )
    raise exc
