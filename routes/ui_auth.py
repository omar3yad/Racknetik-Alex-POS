import json
import os
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from main import templates
from config import get_settings
from database import get_db
from models.user import UserRole
from repositories.user_repo import UserRepository
from services.audit_service import AuditService
from services.auth_service import AuthService, AuthenticationError

router = APIRouter(prefix="/ui", tags=["ui-auth"])

# Load translations
translations_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "translations", "ar.json"
)
try:
    with open(translations_path, "r", encoding="utf-8") as f:
        translations = json.load(f)
except Exception:
    translations = {}

@router.get("/login")
async def get_login(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings = Depends(get_settings),
):
    token = request.cookies.get("pgms_token")
    if token:
        try:
            auth_service = AuthService(settings)
            payload = auth_service.decode_token(token)
            
            user_repo = UserRepository(db)
            user = await user_repo.get_by_id(int(payload.sub))
            if user and user.is_active:
                if user.role == UserRole.ADMIN:
                    return RedirectResponse("/ui/admin/dashboard", status_code=303)
                else:
                    return RedirectResponse("/ui/operator/dashboard", status_code=303)
        except Exception:
            pass

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {"error": None},
    )

@router.post("/login")
async def post_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
    settings = Depends(get_settings),
):
    auth_service = AuthService(settings)
    user_repo = UserRepository(db)
    audit_service = AuditService(db)

    try:
        user = await auth_service.authenticate_user(username, password, user_repo)
    except AuthenticationError:
        error_msg = translations.get(
            "login.error_invalid_credentials",
            "اسم المستخدم أو كلمة المرور غير صحيحة.",
        )
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"error": error_msg},
        )

    token = auth_service.create_access_token(user.id, user.role.value)
    
    dest = "/ui/admin/dashboard" if user.role == UserRole.ADMIN else "/ui/operator/dashboard"
    response = RedirectResponse(dest, status_code=303)
    
    secure_cookie = settings.ENVIRONMENT in ("staging", "production")
    response.set_cookie(
        key="pgms_token",
        value=token,
        max_age=settings.JWT_EXPIRE_HOURS * 3600,
        httponly=True,
        samesite="strict",
        secure=secure_cookie,
    )

    await audit_service.log(
        actor_id=user.id,
        action="USER_LOGIN",
        entity_type="user",
        entity_id=user.id,
        before=None,
        after=None,
    )
    
    await db.commit()
    return response

@router.post("/logout")
async def post_logout(request: Request):
    response = RedirectResponse("/ui/login", status_code=303)
    response.set_cookie(
        key="pgms_token",
        value="",
        max_age=0,
        httponly=True,
        samesite="strict",
    )
    return response


@router.get("/admin/dashboard")
async def get_admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings = Depends(get_settings),
):
    token = request.cookies.get("pgms_token")
    if not token:
        return RedirectResponse("/ui/login", status_code=303)
    try:
        auth_service = AuthService(settings)
        payload = auth_service.decode_token(token)
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(int(payload.sub))
        if not user or not user.is_active or user.role != UserRole.ADMIN:
            return RedirectResponse("/ui/login", status_code=303)
    except Exception:
        return RedirectResponse("/ui/login", status_code=303)

    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {"user": user},
    )
