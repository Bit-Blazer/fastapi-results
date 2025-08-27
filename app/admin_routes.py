"""
Admin routes for admin login functionality
"""

import os
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Create router for admin routes
router = APIRouter(prefix="/admin")


# Admin authentication helper functions
def is_admin_authenticated(request: Request) -> bool:
    """Check if admin is authenticated in the session"""
    return request.session.get("admin_authenticated", False)


@router.get("/dashboard/")
async def admin_dashboard(request: Request):
    """Main admin dashboard"""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/admin/login/", status_code=302)

    return templates.TemplateResponse(
        "admin_dashboard.html",
        {"request": request, "page_title": "Grade Changes Management"},
    )


# Admin authentication routes
@router.get("/login/")
async def admin_login_page(request: Request, error: str = None):
    """Display admin login page"""
    if is_admin_authenticated(request):
        return RedirectResponse(url="/admin/dashboard/", status_code=302)

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": error,
            "page_title": "Admin Login",
            "action_url": "/admin/login/",
            "auth_type": "admin",
        },
    )


@router.post("/login/")
async def admin_login(request: Request, password: str = Form(...)):
    """Handle admin login submission"""
    admin_password = os.getenv("ADMIN_PASSWORD", "")

    if password == admin_password:
        request.session["admin_authenticated"] = True
        return RedirectResponse(url="/admin/dashboard/", status_code=302)
    else:
        return RedirectResponse(
            url="/admin/login/?error=Invalid password", status_code=302
        )


@router.post("/logout/")
async def admin_logout(request: Request):
    """Handle admin logout"""
    request.session.pop("admin_authenticated", None)
    return RedirectResponse(url="/", status_code=302)
