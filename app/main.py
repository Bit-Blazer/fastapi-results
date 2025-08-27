"""
FastAPI application for student results portal
"""

import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

# Import our modular routers
from .admin_routes import router as admin_router
from .api import router as api_router
from .student_routes import router as student_router

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Student Results Portal",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Add session middleware for authentication
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", ""))

# Set up templates and static files
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Include routers
app.include_router(admin_router)  # Admin management routes (/admin/*)
app.include_router(api_router)  # API routes (/api/*)
app.include_router(student_router)  # Student routes (/, /{regno}/, /pdf/*, /zip/*)


# Custom exception handlers
@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "error_404.html", {"request": request}, status_code=404
        )
    raise exc


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Student Results Portal is running"}
