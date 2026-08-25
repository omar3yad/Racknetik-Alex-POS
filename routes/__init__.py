from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.ui_auth import router as ui_auth_router

__all__ = ["auth_router", "users_router", "ui_auth_router"]
