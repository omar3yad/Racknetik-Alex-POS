import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from config import get_settings
from database import engine
from utils.jinja import create_jinja2_environment

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize Jinja2Templates environment at module-level
templates = create_jinja2_environment(settings)

# Database connection status check on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection checked and verified successfully.")
    except Exception as e:
        logger.critical("Database connection failed during startup check: %s", str(e))
    yield

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# CORS middleware configuration
if settings.ENVIRONMENT == "production" and "*" in settings.CORS_ORIGINS:
    raise RuntimeError("Wildcard CORS origin forbidden in production")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database availability middleware
@app.middleware("http")
async def db_availability_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") or path.startswith("/ui/"):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as e:
            logger.error("Database connection failed during request check: %s", str(e))
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Database is currently unavailable. Please try again later.",
                    "code": "DATABASE_UNAVAILABLE"
                }
            )
    return await call_next(request)

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    code = getattr(exc, "code", None)
    if not code and exc.headers:
        code = exc.headers.get("X-Error-Code")
    if not code:
        code = "ERROR"
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": code},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled server exception: %s", str(exc), exc_info=True)
    detail = "Internal server error"
    if settings.ENVIRONMENT == "development":
        detail = str(exc)
    return JSONResponse(
        status_code=500,
        content={"detail": detail, "code": "INTERNAL_ERROR"},
    )

# Import routers after templates definition to prevent circular imports
from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.ui_auth import router as ui_auth_router
from routes.cards import router as cards_router
from routes.sessions import router as sessions_router
from routes.shifts import router as shifts_router
from routes.rates import router as rates_router
from routes.ui_operator import router as ui_operator_router

# Include routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(ui_auth_router)
app.include_router(cards_router)
app.include_router(sessions_router)
app.include_router(shifts_router)
app.include_router(rates_router)
app.include_router(ui_operator_router)

@app.get("/")
async def root_redirect():
    return RedirectResponse("/ui/login", status_code=303)
