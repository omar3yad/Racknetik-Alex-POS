import pytest

from models.user import User, UserRole

async def login_as(async_client, db_session, auth_service, role: UserRole, username: str, gate_number: int | None = None):
    # Helper to seed a user and log in
    hashed = auth_service.hash_password("password123")
    user = User(
        full_name=f"Test {role.value.capitalize()}",
        username=username,
        hashed_password=hashed,
        role=role,
        gate_number=gate_number,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    await async_client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "password123"},
    )
    return user

@pytest.mark.asyncio
async def test_create_user_as_admin(async_client, db_session, auth_service):
    await login_as(async_client, db_session, auth_service, UserRole.ADMIN, "admin_user")

    response = await async_client.post(
        "/api/v1/users/",
        json={
            "full_name": "New Operator",
            "username": "new_op",
            "password": "oppassword123",
            "role": "operator",
            "gate_number": 1,
        },
    )
    assert response.status_code == 201
    json_data = response.json()
    assert json_data["data"]["username"] == "new_op"
    assert json_data["data"]["role"] == "operator"

@pytest.mark.asyncio
async def test_create_user_as_operator_forbidden(async_client, db_session, auth_service):
    await login_as(async_client, db_session, auth_service, UserRole.OPERATOR, "op_user", gate_number=1)

    response = await async_client.post(
        "/api/v1/users/",
        json={
            "full_name": "Another Operator",
            "username": "another_op",
            "password": "oppassword123",
            "role": "operator",
            "gate_number": 2,
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == "INSUFFICIENT_PERMISSIONS"

@pytest.mark.asyncio
async def test_create_user_duplicate_username(async_client, db_session, auth_service):
    await login_as(async_client, db_session, auth_service, UserRole.ADMIN, "admin_user")

    # Create first operator
    await async_client.post(
        "/api/v1/users/",
        json={
            "full_name": "New Operator",
            "username": "new_op",
            "password": "oppassword123",
            "role": "operator",
            "gate_number": 1,
        },
    )

    # Attempt to create second operator with same username
    response = await async_client.post(
        "/api/v1/users/",
        json={
            "full_name": "Different Name",
            "username": "new_op",
            "password": "diffpassword123",
            "role": "operator",
            "gate_number": 2,
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "USERNAME_ALREADY_EXISTS"

@pytest.mark.asyncio
async def test_create_operator_without_gate(async_client, db_session, auth_service):
    await login_as(async_client, db_session, auth_service, UserRole.ADMIN, "admin_user")

    response = await async_client.post(
        "/api/v1/users/",
        json={
            "full_name": "Invalid Operator",
            "username": "invalid_op",
            "password": "password123",
            "role": "operator",
            "gate_number": None,
        },
    )
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_create_operator_invalid_gate(async_client, db_session, auth_service):
    await login_as(async_client, db_session, auth_service, UserRole.ADMIN, "admin_user")

    response = await async_client.post(
        "/api/v1/users/",
        json={
            "full_name": "Invalid Operator",
            "username": "invalid_op",
            "password": "password123",
            "role": "operator",
            "gate_number": 6,  # Out of range 1-5
        },
    )
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_create_admin_with_gate(async_client, db_session, auth_service):
    await login_as(async_client, db_session, auth_service, UserRole.ADMIN, "admin_user")

    response = await async_client.post(
        "/api/v1/users/",
        json={
            "full_name": "Invalid Admin",
            "username": "invalid_admin",
            "password": "password123",
            "role": "admin",
            "gate_number": 1,  # Admin cannot have gate number
        },
    )
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_list_users_as_admin(async_client, db_session, auth_service):
    admin = await login_as(async_client, db_session, auth_service, UserRole.ADMIN, "admin_user")
    
    # Create 2 more users directly in DB
    hashed = auth_service.hash_password("pass")
    u1 = User(full_name="User One", username="u1", hashed_password=hashed, role=UserRole.OPERATOR, gate_number=1)
    u2 = User(full_name="User Two", username="u2", hashed_password=hashed, role=UserRole.OPERATOR, gate_number=2)
    db_session.add_all([u1, u2])
    await db_session.commit()

    response = await async_client.get("/api/v1/users/?page=1&size=10")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["total"] >= 3
    assert len(json_data["data"]) >= 3

@pytest.mark.asyncio
async def test_list_users_filter_by_role(async_client, db_session, auth_service):
    admin = await login_as(async_client, db_session, auth_service, UserRole.ADMIN, "admin_user")
    
    hashed = auth_service.hash_password("pass")
    u1 = User(full_name="Op One", username="op1", hashed_password=hashed, role=UserRole.OPERATOR, gate_number=1)
    u2 = User(full_name="Admin Two", username="admin2", hashed_password=hashed, role=UserRole.ADMIN, gate_number=None)
    db_session.add_all([u1, u2])
    await db_session.commit()

    response = await async_client.get("/api/v1/users/?role=operator")
    assert response.status_code == 200
    json_data = response.json()
    for item in json_data["data"]:
        assert item["role"] == "operator"

@pytest.mark.asyncio
async def test_get_user_by_id(async_client, db_session, auth_service):
    admin = await login_as(async_client, db_session, auth_service, UserRole.ADMIN, "admin_user")
    
    hashed = auth_service.hash_password("pass")
    user = User(full_name="User One", username="u1", hashed_password=hashed, role=UserRole.OPERATOR, gate_number=1)
    db_session.add(user)
    await db_session.commit()

    response = await async_client.get(f"/api/v1/users/{user.id}")
    assert response.status_code == 200
    assert response.json()["data"]["username"] == "u1"

@pytest.mark.asyncio
async def test_get_user_not_found(async_client, db_session, auth_service):
    await login_as(async_client, db_session, auth_service, UserRole.ADMIN, "admin_user")

    response = await async_client.get("/api/v1/users/99999")
    assert response.status_code == 404
    assert response.json()["code"] == "USER_NOT_FOUND"

@pytest.mark.asyncio
async def test_deactivate_user(async_client, db_session, auth_service):
    admin = await login_as(async_client, db_session, auth_service, UserRole.ADMIN, "admin_user")
    
    hashed = auth_service.hash_password("pass")
    user = User(full_name="User One", username="u1", hashed_password=hashed, role=UserRole.OPERATOR, gate_number=1, is_active=True)
    db_session.add(user)
    await db_session.commit()

    response = await async_client.patch(f"/api/v1/users/{user.id}/deactivate")
    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is False

@pytest.mark.asyncio
async def test_deactivate_self_forbidden(async_client, db_session, auth_service):
    admin = await login_as(async_client, db_session, auth_service, UserRole.ADMIN, "admin_user")

    response = await async_client.patch(f"/api/v1/users/{admin.id}/deactivate")
    assert response.status_code == 403
    assert response.json()["code"] == "CANNOT_DEACTIVATE_SELF"

@pytest.mark.asyncio
async def test_deactivate_already_inactive(async_client, db_session, auth_service):
    admin = await login_as(async_client, db_session, auth_service, UserRole.ADMIN, "admin_user")
    
    hashed = auth_service.hash_password("pass")
    user = User(full_name="User One", username="u1", hashed_password=hashed, role=UserRole.OPERATOR, gate_number=1, is_active=False)
    db_session.add(user)
    await db_session.commit()

    response = await async_client.patch(f"/api/v1/users/{user.id}/deactivate")
    assert response.status_code == 409
    assert response.json()["code"] == "USER_ALREADY_INACTIVE"

@pytest.mark.asyncio
async def test_reset_password(async_client, db_session, auth_service):
    admin = await login_as(async_client, db_session, auth_service, UserRole.ADMIN, "admin_user")
    
    hashed = auth_service.hash_password("pass")
    user = User(full_name="User One", username="u1", hashed_password=hashed, role=UserRole.OPERATOR, gate_number=1, is_active=True)
    db_session.add(user)
    await db_session.commit()

    response = await async_client.patch(
        f"/api/v1/users/{user.id}/reset-password",
        json={"new_password": "brandnewpassword123"},
    )
    assert response.status_code == 200
    
    # Try to login with new password
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        data={"username": "u1", "password": "brandnewpassword123"},
    )
    assert login_resp.status_code == 200

@pytest.mark.asyncio
async def test_hashed_password_never_in_response(async_client, db_session, auth_service):
    # Seed admin and get current user info
    admin = await login_as(async_client, db_session, auth_service, UserRole.ADMIN, "admin_user")

    # 1. Check me response
    response_me = await async_client.get("/api/v1/auth/me")
    assert "hashed_password" not in response_me.text

    # 2. Check create user response
    response_create = await async_client.post(
        "/api/v1/users/",
        json={
            "full_name": "New Operator",
            "username": "new_op",
            "password": "oppassword123",
            "role": "operator",
            "gate_number": 1,
        },
    )
    assert "hashed_password" not in response_create.text
    created_id = response_create.json()["data"]["id"]

    # 3. Check get user by id response
    response_get = await async_client.get(f"/api/v1/users/{created_id}")
    assert "hashed_password" not in response_get.text

    # 4. Check list users response
    response_list = await async_client.get("/api/v1/users/")
    assert "hashed_password" not in response_list.text
