from fastapi import APIRouter, Depends, Form, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from dependencies import require_any_role
from models.user import User
from repositories.user_repo import UserRepository
from schemas.auth import LoginResponse
from schemas.user import UserResponse
from services.audit_service import AuditService
from services.auth_service import AuthService, AuthenticationError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

@router.post("/login")
async def login(
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
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid credentials", "code": "INVALID_CREDENTIALS"},
        )

    token = auth_service.create_access_token(user.id, user.role.value)
    
    login_resp = LoginResponse(
        user_id=user.id,
        role=user.role,
        full_name=user.full_name,
    )
    
    response = JSONResponse(content={"data": login_resp.model_dump(mode="json")})
    
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
async def logout():
    response = JSONResponse(content={"data": "logged out"})
    response.set_cookie(
        key="pgms_token",
        value="",
        max_age=0,
        httponly=True,
        samesite="strict",
    )
    return response

@router.get("/me")
async def get_me(current_user: User = Depends(require_any_role)):
    return {"data": UserResponse.model_validate(current_user).model_dump(mode="json")}
