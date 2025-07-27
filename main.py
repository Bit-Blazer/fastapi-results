import re
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import zipfile
import fitz  # PyMuPDF
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from starlette.middleware.sessions import SessionMiddleware
import json
from fastapi import Form
from fastapi.responses import RedirectResponse
from datetime import datetime

app = FastAPI()
app.add_middleware(
    SessionMiddleware, secret_key="super-secret-key"
)  # use env var in prod

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


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


with open(BASE_DIR / "students.json") as f:
    students = json.load(f)


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

    # print the time
    print(f"Index accessed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    q = q.lower()
    results = []

    for regno, data in students.items():
        name = data.get("name", "").lower()
        if not q or q in regno.lower() or q in name:
            results.append({"regno": regno, "name": data.get("name", "")})

    # print time
    print(f"Filtered for query '{q}' at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
    file_data = []
    student_name = students.get(regno, {}).get("name")

    for f in files:
        sem = f.name.replace(f"{regno}_", "").replace(".pdf", "")
        gpa = extract_gpa(f)
        file_data.append({"filename": f.name, "sem": sem, "gpa": gpa})

    return templates.TemplateResponse(
        "student.html",
        {
            "request": request,
            "regno": regno,
            "files": file_data,
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

    return FileResponse(
        zip_path, media_type="application/zip", filename=f"{regno}_results.zip"
    )


@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "404.html", {"request": request}, status_code=404
        )
    raise exc
