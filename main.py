import re
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import zipfile
import fitz  # PyMuPDF
from starlette.exceptions import HTTPException as StarletteHTTPException

from starlette.middleware.sessions import SessionMiddleware
import json
from fastapi import Form
from fastapi.responses import RedirectResponse

app = FastAPI()
app.add_middleware(
    SessionMiddleware, secret_key="super-secret-key"
)  # use env var in prod

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

with open(BASE_DIR / "subjects.json") as f:
    subject_map = json.load(f)

with open(BASE_DIR / "students.json") as f:
    students = json.load(f)


def extract_gpa(pdf_path: Path):
    gpa_pattern = r"=> (.*)"
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text = page.get_text()
                match = re.search(gpa_pattern, text)
                if match:
                    return match.group(1).strip()
    except Exception:
        return None
    return None


def extract_name(pdf_path: Path):
    name_pattern = r"Name\s: ([A-Z ]+)"
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text = page.get_text()
                match = re.search(name_pattern, text)
                if match:
                    # Title-case it nicely
                    return match.group(1).strip().title()
    except Exception:
        return None
    return None


@app.get("/auth/{regno}")
def auth_form(regno: str, request: Request):
    if regno not in students:
        raise HTTPException(status_code=404, detail="Student not found")
    student_name = students.get(regno, {}).get("name")
    return templates.TemplateResponse(
        "auth.html",
        {
            "request": request,
            "regno": regno,
            "student_name": student_name,
            "error": None,
        },
    )


@app.post("/auth/{regno}")
def auth_submit(regno: str, dob: str = Form(...), request: Request = None):
    actual_dob = students.get(regno, {}).get("dob")
    student_name = students.get(regno, {}).get("name")
    if actual_dob and dob.strip() == actual_dob:
        request.session[regno] = True
        return RedirectResponse(url=f"/{regno}/", status_code=302)
    else:
        return templates.TemplateResponse(
            "auth.html",
            {
                "request": request,
                "regno": regno,
                "student_name": student_name,
                "error": "Incorrect DOB",
            },
        )


@app.get("/")
def index(request: Request, q: str = ""):
    q = q.lower()
    results = []

    for regno, data in students.items():
        name = data.get("name", "").lower()
        if not q or q in regno.lower() or q in name:
            results.append({"regno": regno, "name": data.get("name", "")})

    return templates.TemplateResponse(
        "index.html", {"request": request, "results": results, "q": q}
    )


@app.get("/{regno}/")
def student_page(regno: str, request: Request):
    if not request.session.get(regno):
        return RedirectResponse(url=f"/auth/{regno}", status_code=302)

    student_folder = RESULTS_DIR / regno
    if not student_folder.exists():
        raise HTTPException(status_code=404, detail="Student not found")

    files = sorted([f for f in student_folder.glob(f"{regno}_*.pdf")])
    file_data = {}
    student_name = students.get(regno, {}).get("name")

    grade_points = {
        "O": 10,
        "A+": 9,
        "A": 8,
        "B+": 7,
        "B": 6,
        "C": 5,
        "U": 0,
        "RA": 0,
        "AB": 0,
        "NA": 0,
    }

    subject_regex = re.compile(
        r"(\d)\s*(2[123][A-Z]{2,3}\d{2,3}[TL])\s*(?:-\s|\s)([A-Za-z,\s]+)\s(A\+?|B\+?|C|O|U|AB|NA)\s",
        re.IGNORECASE,
    )

    # Process PDF files
    for f in files:
        sem = f.name.replace(f"{regno}_", "").replace(".pdf", "")
        gpa = extract_gpa(f)
        try:
            with fitz.open(f) as doc:
                text = "\n".join(page.get_text() for page in doc)
                matches = subject_regex.findall(text)

                for subject_sem, code, name, grade in matches:
                    subject_sem = subject_sem.strip()
                    code = code.strip().upper()
                    name = name.strip().title()
                    grade = grade.strip().upper()

                    # Get subject name from subject map if available
                    subject_info = subject_map.get(code, {})
                    subject_name = subject_info.get("name", name) or name
                    credits = subject_info.get("credits")

                    # Calculate grade points earned (credits × grade point value)
                    gp = grade_points.get(grade)
                    grade_points_earned = credits * gp

                    subject_data = {
                        "code": code,
                        "name": subject_name,
                        "grade": grade,
                        "credits": credits,
                        "grade_points_earned": grade_points_earned,
                    }

                    # Check if subject semester matches PDF semester
                    if subject_sem == sem:
                        # Normal case - subject belongs to this semester
                        file_data[sem]["subjects"].append(subject_data)
                        file_data[sem]["total_credits"] += credits
                        file_data[sem]["total_grade_points"] += grade_points_earned
                    else:
                        # Arrear case - subject is from a different semester
                        # Check if we have data for the original semester
                        if subject_sem in file_data:
                            # Remove any existing entry for this subject in the original semester
                            original_subjects = file_data[subject_sem]["subjects"]
                            for i, existing_subject in enumerate(original_subjects):
                                if existing_subject["code"] == code:
                                    # Remove old data
                                    file_data[subject_sem][
                                        "total_credits"
                                    ] -= existing_subject["credits"]
                                    file_data[subject_sem][
                                        "total_grade_points"
                                    ] -= existing_subject["grade_points_earned"]
                                    original_subjects.pop(i)
                                    break

                            # Add updated data to the original semester
                            file_data[subject_sem]["subjects"].append(subject_data)
                            file_data[subject_sem]["total_credits"] += credits
                            file_data[subject_sem][
                                "total_grade_points"
                            ] += grade_points_earned
                        else:
                            # Original semester doesn't exist yet, create it
                            file_data[subject_sem] = {
                                "filename": f"{regno}_{subject_sem}.pdf",
                                "sem": subject_sem,
                                "gpa": gpa,
                                "subjects": [subject_data],
                                "total_grade_points": grade_points_earned,
                                "total_credits": credits,
                            }

        except Exception as e:
            print(f"[ERROR Processing] {f.name}: {e}")

    # Convert back to list format for template compatibility
    file_data_list = []
    for sem in sorted(file_data.keys()):
        file_data_list.append(file_data[sem])

    return templates.TemplateResponse(
        "student.html",
        {
            "request": request,
            "regno": regno,
            "files": file_data_list,
            "student_name": student_name,
        },
    )


@app.get("/pdf/{regno}/{filename}")
def serve_pdf(regno: str, filename: str):
    filepath = RESULTS_DIR / regno / filename
    if filepath.exists():
        headers = {"Content-Disposition": f"inline; filename={filename}"}
        return FileResponse(filepath, media_type="application/pdf", headers=headers)
    raise HTTPException(status_code=404, detail="PDF not found")


@app.get("/zip/{regno}")
def zip_and_download_all(regno: str):
    student_folder = RESULTS_DIR / regno
    if not student_folder.exists():
        raise HTTPException(status_code=404, detail="Student not found")

    zip_path = BASE_DIR / f"{regno}_results.zip"
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for f in student_folder.glob(f"{regno}_*.pdf"):
            zipf.write(f, arcname=f.name)

    def cleanup_file():
        try:
            zip_path.unlink(missing_ok=True)
        except Exception:
            pass

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"{regno}_results.zip",
        background=cleanup_file,
    )


@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "404.html", {"request": request}, status_code=404
        )
    raise exc
