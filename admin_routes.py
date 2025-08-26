"""
Admin routes for managing grade changes and monitoring system
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pathlib import Path
from database import get_db, StudentLoginLog

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Create router for admin routes
router = APIRouter(prefix="/admin")


def is_admin_authenticated(request: Request) -> bool:
    """Check if admin is authenticated in the session"""
    return request.session.get("admin_authenticated", False)


@router.get("/dashboard/")
async def admin_dashboard(request: Request):
    """Main admin dashboard - redirects to grade changes for now"""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/admin/login/", status_code=302)

    return templates.TemplateResponse(
        "admin_dashboard.html",
        {"request": request, "page_title": "Grade Changes Management"},
    )


@router.get("/student-logs-data")
async def student_logs_data(request: Request, db: Session = Depends(get_db)):
    """API endpoint for student logs data"""
    if not is_admin_authenticated(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        # Get recent student login logs (last 100)
        student_logs = (
            db.query(StudentLoginLog)
            .order_by(desc(StudentLoginLog.login_time))
            .limit(100)
            .all()
        )

        # Calculate statistics
        total_logins = len(student_logs)
        unique_students = len(set(log.regno for log in student_logs))

        # Format logs for frontend
        formatted_logs = []
        for log in student_logs:
            session_duration = None

            formatted_logs.append(
                {
                    "name": log.student_name,
                    "regno": log.regno,
                    "login_time": log.login_time.isoformat(),
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                }
            )

        return JSONResponse(
            {
                "logs": formatted_logs,
                "stats": {
                    "total_logins": total_logins,
                    "unique_students": unique_students,
                },
            }
        )

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
