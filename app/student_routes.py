"""
Student routes for viewing results and downloading PDFs
"""

import io
import zipfile
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends, Form
from fastapi.responses import Response, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from .database import (
    get_db,
    Student,
    Subject,
    Grade,
    Semester,
    GradeChange,
    StudentLoginLog,
    IST,
    download_pdf,
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Create router for student routes
router = APIRouter()


@router.head("/")
@router.get("/")
def landing_page(request: Request):
    """Landing page with navigation options"""
    return templates.TemplateResponse("home.html", {"request": request})


@router.get("/users/")
def users_dashboard(request: Request, q: str = "", db: Session = Depends(get_db)):
    """Users dashboard - search and list students"""
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
        "students_list.html", {"request": request, "results": results, "q": q}
    )


@router.get("/users/{regno}/")
def student_auth_page(regno: str, request: Request, db: Session = Depends(get_db)):
    """Student authentication page"""
    # Check if student exists in database
    student = db.query(Student).filter(Student.regno == regno).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "regno": regno,
            "student_name": student.name,
            "error": None,
            "page_title": "Student Authentication",
            "action_url": f"/users/{regno}/",
            "auth_type": "student",
        },
    )


@router.post("/users/{regno}/")
def student_auth_submit(
    regno: str,
    dob: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Handle student authentication submission"""
    # Get student from database
    student = db.query(Student).filter(Student.regno == regno).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if dob.strip() == student.dob:
        # Get client information for logging
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # Create student login log entry
        login_log = StudentLoginLog(
            regno=regno,
            student_name=student.name,
            login_time=datetime.now(IST),
            ip_address=client_ip,
            user_agent=user_agent,
        )
        db.add(login_log)
        db.commit()

        # Store login log ID in session for logout tracking
        request.session[f"student_{regno}"] = True
        request.session[f"student_login_log_id_{regno}"] = login_log.id

        return RedirectResponse(url=f"/users/{regno}/results/", status_code=302)
    else:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "regno": regno,
                "student_name": student.name,
                "error": "Incorrect Date of Birth",
                "page_title": "Student Authentication",
                "action_url": f"/users/{regno}/",
                "auth_type": "student",
            },
        )


@router.get("/users/{regno}/results/")
def student_results_page(regno: str, request: Request, db: Session = Depends(get_db)):
    """Display student results page with grades and downloadable PDFs"""
    # Check if user is authenticated for this student
    if not request.session.get(f"student_{regno}"):
        return RedirectResponse(url=f"/users/{regno}/", status_code=302)

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
        "student_results.html",
        {
            "request": request,
            "regno": regno,
            "files": file_data_list,
            "student_name": student.name,
        },
    )


@router.get("/users/{regno}/zip/")
def download_student_zip(regno: str, request: Request, db: Session = Depends(get_db)):
    """Download all PDFs for a student as a ZIP file"""
    # Check if user is authenticated for this student
    if not request.session.get(f"student_{regno}"):
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
