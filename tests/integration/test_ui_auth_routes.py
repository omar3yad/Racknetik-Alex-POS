import pytest

from models.user import User, UserRole

@pytest.mark.asyncio
async def test_login_page_renders(async_client):
    response = await async_client.get("/ui/login")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    # Check that "تسجيل الدخول" (which is the Arabic translation for login.title) appears in the body
    assert "تسجيل الدخول" in response.text

@pytest.mark.asyncio
async def test_ui_login_success_operator_redirect(async_client, db_session, auth_service):
    # Seed operator
    hashed = auth_service.hash_password("password123")
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

    # Submit login form
    response = await async_client.post(
        "/ui/login",
        data={"username": "op1", "password": "password123"},
    )
    assert response.status_code == 303
    assert response.headers.get("location") == "/ui/operator/dashboard"
    assert "pgms_token" in async_client.cookies

@pytest.mark.asyncio
async def test_ui_login_failure_rerenders_form(async_client, db_session, auth_service):
    # Seed operator
    hashed = auth_service.hash_password("password123")
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

    # Submit wrong credentials
    response = await async_client.post(
        "/ui/login",
        data={"username": "op1", "password": "wrongpassword"},
    )
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    # Should render form with the Arabic error message from translations/ar.json
    assert "اسم المستخدم أو كلمة المرور غير صحيحة." in response.text

@pytest.mark.asyncio
async def test_ui_logout_redirects_to_login(async_client):
    response = await async_client.post("/ui/logout")
    assert response.status_code == 303
    assert response.headers.get("location") == "/ui/login"
    assert async_client.cookies.get("pgms_token") in (None, "")

@pytest.mark.asyncio
async def test_protected_ui_route_redirects_unauthenticated(async_client):
    # Try to access dashboard without cookie
    response = await async_client.get("/ui/operator/dashboard")
    assert response.status_code == 303
    assert response.headers.get("location") == "/ui/login"
