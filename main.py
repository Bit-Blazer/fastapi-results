import re
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import zipfile
import io
from starlette.exceptions import HTTPException as StarletteHTTPException

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
    download_pdf,
)

app = FastAPI()
app.add_middleware(
    SessionMiddleware, secret_key="super-secret-key"
)  # use env var in prod

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


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

    # Prepare data for template (maintaining compatibility)
    file_data_list = []

    for semester in semesters:
        # Get grades for this semester with subject details
        grades = (
            db.query(Grade, Subject)
            .join(Subject, Grade.subject_id == Subject.id)
            .filter(Grade.semester_id == semester.id)
            .all()
        )
        # Calculate totals
        total_credits = sum(subject.credits for _, subject in grades)
        total_grade_points = sum(grade.grade_points_earned for grade, _ in grades)

        # Prepare subjects list for template
        subjects = []
        for grade, subject in grades:
            subjects.append(
                {
                    "code": subject.code,
                    "name": subject.name,
                    "grade": grade.grade,
                    "credits": subject.credits,
                    "grade_points_earned": grade.grade_points_earned,  # Now integer, no conversion needed
                }
            )

        # Create semester data for template
        file_data_list.append(
            {
                "filename": f"{regno}_sem{semester.semester}.pdf",
                "sem": semester.semester,
                "gpa": float(semester.gpa) if semester.gpa else None,
                "subjects": subjects,
                "total_credits": total_credits,
                "total_grade_points": total_grade_points,  # Also integer now
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


@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "404.html", {"request": request}, status_code=404
        )
    raise exc
