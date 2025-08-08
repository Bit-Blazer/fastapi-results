"""
Admin routes for managing grade changes and monitoring system
"""
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

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
        {
            "request": request,
            "page_title": "Grade Changes Management"
        }
    )
