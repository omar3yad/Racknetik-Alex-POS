import pytest
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from config import Settings, get_settings
from database import Base, get_db
from main import app
from repositories.user_repo import UserRepository
from services.audit_service import AuditService
from services.auth_service import AuthService

import os

@pytest.fixture(scope="session")
def settings_override() -> Settings:
    return Settings(
        DATABASE_URL="sqlite+aiosqlite:///test_temp.db",
        SECRET_KEY="a" * 32,
        ENVIRONMENT="development",
        DEBUG=True,
        JWT_EXPIRE_HOURS=1,
    )

@pytest.fixture(scope="session")
async def engine(settings_override: Settings):
    # Remove old test_temp.db if it exists
    if os.path.exists("test_temp.db"):
        try:
            os.remove("test_temp.db")
        except Exception:
            pass

    # Create the test async engine
    test_engine = create_async_engine(
        settings_override.DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    yield test_engine
    # dispose engine on cleanup
    await test_engine.dispose()

    # Clean up test_temp.db file
    if os.path.exists("test_temp.db"):
        try:
            os.remove("test_temp.db")
        except Exception:
            pass

@pytest.fixture(scope="function", autouse=True)
async def db_tables(engine):
    # Recreate tables for every test function to guarantee a clean state
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncSession:
    # Simplify db_session: tables are dropped and recreated per-test
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

@pytest.fixture(scope="function")
def auth_service(settings_override: Settings) -> AuthService:
    return AuthService(settings_override)

@pytest.fixture(scope="function")
def user_repo(db_session: AsyncSession) -> UserRepository:
    return UserRepository(db_session)

@pytest.fixture(scope="function")
def audit_service(db_session: AsyncSession) -> AuditService:
    return AuditService(db_session)

@pytest.fixture(scope="function")
async def async_client(engine, settings_override: Settings):
    async def override_get_db():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    def override_get_settings():
        return settings_override

    # Apply overrides
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    # Instantiate HTTPX client using ASGITransport
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test.local") as client:
        yield client

    # Clean up overrides
    app.dependency_overrides.clear()
