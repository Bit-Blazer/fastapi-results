"""
Authentication routes for admin login functionality
"""

import os
from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Create router for authentication routes
router = APIRouter()


# Admin authentication helper functions
def is_admin_authenticated(request: Request) -> bool:
    """Check if admin is authenticated in the session"""
    return request.session.get("admin_authenticated", False)


def require_admin_auth(request: Request):
    """Dependency to require admin authentication"""
    if not is_admin_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    return True


# Admin authentication routes
@router.get("/admin/")
async def admin_base(request: Request):
    """Base admin route that redirects to appropriate page"""
    if is_admin_authenticated(request):
        return RedirectResponse(url="/admin/dashboard/", status_code=302)
    else:
        return RedirectResponse(url="/admin/login/", status_code=302)


@router.get("/admin/login/")
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


@router.post("/admin/login/")
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


@router.post("/admin/logout/")
async def admin_logout(request: Request):
    """Handle admin logout"""
    request.session.pop("admin_authenticated", None)
    return RedirectResponse(url="/", status_code=302)
