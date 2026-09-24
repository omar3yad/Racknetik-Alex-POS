import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, UserRole
from services.auth_service import AuthService


async def setup_admin(
    db: AsyncSession, auth_service: AuthService, client: AsyncClient
) -> User:
    admin = User(
        username="admin_auth_test",
        full_name="Admin Auth Tester",
        role=UserRole.ADMIN,
        is_active=True,
        hashed_password=auth_service.hash_password("adminpass123"),
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)

    token = auth_service.create_access_token(admin.id, admin.role.value)
    client.cookies.set("pgms_token", token)
    return admin


async def setup_operator(
    db: AsyncSession, auth_service: AuthService, client: AsyncClient
) -> User:
    op = User(
        username="operator_auth_test",
        full_name="Operator Auth Tester",
        role=UserRole.OPERATOR,
        gate_number=1,
        is_active=True,
        hashed_password=auth_service.hash_password("oppass123"),
    )
    db.add(op)
    await db.commit()
    await db.refresh(op)

    token = auth_service.create_access_token(op.id, op.role.value)
    client.cookies.set("pgms_token", token)
    return op


@pytest.mark.asyncio
async def test_admin_stats_requires_auth(async_client: AsyncClient):
    res = await async_client.get("/api/v1/admin/stats/live")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_admin_stats_requires_admin_role(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_operator(db_session, auth_service, async_client)
    res = await async_client.get("/api/v1/admin/stats/live")
    assert res.status_code == 403
    assert res.json().get("code") == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_admin_stats_succeeds_as_admin(
    async_client: AsyncClient, db_session: AsyncSession, auth_service: AuthService
):
    await setup_admin(db_session, auth_service, async_client)
    res = await async_client.get("/api/v1/admin/stats/live")
    assert res.status_code == 200
    assert "data" in res.json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/admin/stats/live",
        "/api/v1/admin/stats/gates",
        "/api/v1/admin/sessions",
        "/api/v1/admin/sessions/export/csv",
        "/api/v1/admin/shifts",
        "/api/v1/admin/reports/revenue",
        "/api/v1/admin/reports/export/csv",
        "/api/v1/admin/stats/subscriptions",
    ],
)
async def test_all_admin_routes_reject_operator(
    path: str,
    async_client: AsyncClient,
    db_session: AsyncSession,
    auth_service: AuthService,
):
    await setup_operator(db_session, auth_service, async_client)
    res = await async_client.get(path)
    assert res.status_code == 403
    assert res.json().get("code") == "INSUFFICIENT_PERMISSIONS"
