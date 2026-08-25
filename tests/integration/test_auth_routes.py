import pytest
import freezegun
from datetime import datetime, timezone

from models.user import User, UserRole

@pytest.mark.asyncio
async def test_login_success(async_client, db_session, auth_service):
    # Seed operator user
    hashed = auth_service.hash_password("operatorpass")
    user = User(
        full_name="Test Operator",
        username="op1",
        hashed_password=hashed,
        role=UserRole.OPERATOR,
        gate_number=1,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/auth/login",
        data={"username": "op1", "password": "operatorpass"},
    )
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["user_id"] == user.id
    assert json_data["data"]["role"] == "operator"
    assert "pgms_token" in async_client.cookies

@pytest.mark.asyncio
async def test_login_wrong_password(async_client, db_session, auth_service):
    # Seed operator user
    hashed = auth_service.hash_password("operatorpass")
    user = User(
        full_name="Test Operator",
        username="op1",
        hashed_password=hashed,
        role=UserRole.OPERATOR,
        gate_number=1,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/auth/login",
        data={"username": "op1", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"

@pytest.mark.asyncio
async def test_login_unknown_username(async_client, db_session, auth_service):
    response = await async_client.post(
        "/api/v1/auth/login",
        data={"username": "nonexistent_op", "password": "password"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"

@pytest.mark.asyncio
async def test_login_inactive_user(async_client, db_session, auth_service):
    # Seed inactive operator user
    hashed = auth_service.hash_password("operatorpass")
    user = User(
        full_name="Inactive Operator",
        username="op_inactive",
        hashed_password=hashed,
        role=UserRole.OPERATOR,
        gate_number=1,
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/auth/login",
        data={"username": "op_inactive", "password": "operatorpass"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"

@pytest.mark.asyncio
async def test_logout_clears_cookie(async_client, db_session, auth_service):
    # Log in first
    hashed = auth_service.hash_password("operatorpass")
    user = User(
        full_name="Test Operator",
        username="op1",
        hashed_password=hashed,
        role=UserRole.OPERATOR,
        gate_number=1,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    # Successful login
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        data={"username": "op1", "password": "operatorpass"},
    )
    assert "pgms_token" in async_client.cookies

    # Logout
    logout_resp = await async_client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 200
    
    # Check that pgms_token cookie is deleted or expired (value empty or max_age 0)
    # Note: HTTPX client updates cookies dictionary. If cookie is expired with max-age=0,
    # it gets deleted or set to empty string. Let's assert:
    assert async_client.cookies.get("pgms_token") in (None, "")

@pytest.mark.asyncio
async def test_logout_without_session(async_client):
    response = await async_client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json()["data"] == "logged out"

@pytest.mark.asyncio
async def test_get_me_authenticated(async_client, db_session, auth_service):
    # Seed and log in
    hashed = auth_service.hash_password("operatorpass")
    user = User(
        full_name="Test Operator",
        username="op1",
        hashed_password=hashed,
        role=UserRole.OPERATOR,
        gate_number=1,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    await async_client.post(
        "/api/v1/auth/login",
        data={"username": "op1", "password": "operatorpass"},
    )

    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["username"] == "op1"
    assert json_data["data"]["full_name"] == "Test Operator"

@pytest.mark.asyncio
async def test_get_me_unauthenticated(async_client):
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"

@pytest.mark.asyncio
async def test_get_me_expired_token(async_client, db_session, auth_service):
    # Seed operator
    hashed = auth_service.hash_password("operatorpass")
    user = User(
        full_name="Test Operator",
        username="op1",
        hashed_password=hashed,
        role=UserRole.OPERATOR,
        gate_number=1,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    with freezegun.freeze_time("2026-08-25 10:00:00") as frozen_time:
        # Create token
        token = auth_service.create_access_token(user.id, user.role.value)
        async_client.cookies.set("pgms_token", token)
        
        # Verify it works initially
        response = await async_client.get("/api/v1/auth/me")
        assert response.status_code == 200
        
        # Advance time past expiration (1 hour)
        frozen_time.move_to("2026-08-25 12:00:00")
        
        response2 = await async_client.get("/api/v1/auth/me")
        assert response2.status_code == 401
        assert response2.json()["code"] == "UNAUTHORIZED"
