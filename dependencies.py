from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from models.user import User, UserRole
from repositories.user_repo import UserRepository
from services.auth_service import AuthService, AuthenticationError

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings = Depends(get_settings),
) -> User:
    token = request.cookies.get("pgms_token")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"X-Error-Code": "UNAUTHORIZED"},
        )

    auth_service = AuthService(settings)
    try:
        payload = auth_service.decode_token(token)
    except AuthenticationError:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"X-Error-Code": "UNAUTHORIZED"},
        )

    try:
        user_id = int(payload.sub)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"X-Error-Code": "UNAUTHORIZED"},
        )

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"X-Error-Code": "UNAUTHORIZED"},
        )

    return user

async def require_operator(
    user: User = Depends(get_current_user),
) -> User:
    if user.role != UserRole.OPERATOR:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions",
            headers={"X-Error-Code": "INSUFFICIENT_PERMISSIONS"},
        )
    return user

async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions",
            headers={"X-Error-Code": "INSUFFICIENT_PERMISSIONS"},
        )
    return user

async def require_any_role(
    user: User = Depends(get_current_user),
) -> User:
    return user

__all__ = ["get_current_user", "require_operator", "require_admin", "require_any_role"]
