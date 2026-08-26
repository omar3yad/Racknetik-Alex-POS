# tests/unit/test_auth_service.py
import pytest
from datetime import datetime, timezone
import freezegun

from services.auth_service import AuthService, AuthenticationError
from models.user import User, UserRole

def test_hash_password_returns_string(auth_service: AuthService):
    hashed = auth_service.hash_password("secret123")
    assert isinstance(hashed, str)
    assert hashed != ""
    assert hashed != "secret123"

def test_hash_password_different_hashes_for_same_input(auth_service: AuthService):
    hashed1 = auth_service.hash_password("secret123")
    hashed2 = auth_service.hash_password("secret123")
    assert hashed1 != hashed2

def test_verify_password_correct(auth_service: AuthService):
    hashed = auth_service.hash_password("secret123")
    assert auth_service.verify_password("secret123", hashed) is True

def test_verify_password_wrong_password(auth_service: AuthService):
    hashed = auth_service.hash_password("secret123")
    assert auth_service.verify_password("wrongpassword", hashed) is False

def test_create_access_token_returns_string(auth_service: AuthService):
    token = auth_service.create_access_token(user_id=1, role="operator")
    assert isinstance(token, str)
    assert token != ""
    assert token.count(".") == 2

def test_decode_token_valid(auth_service: AuthService):
    token = auth_service.create_access_token(user_id=1, role="operator")
    payload = auth_service.decode_token(token)
    assert payload.sub == "1"
    assert payload.role == "operator"

def test_decode_token_expired(auth_service: AuthService):
    with freezegun.freeze_time("2026-08-25 10:00:00") as frozen_time:
        token = auth_service.create_access_token(user_id=1, role="operator")
        
        # Advance time by 9 hours (JWT expires in 1 hour in tests/conftest.py settings override)
        frozen_time.move_to("2026-08-25 19:00:00")
        
        with pytest.raises(AuthenticationError):
            auth_service.decode_token(token)

def test_decode_token_tampered(auth_service: AuthService):
    token = auth_service.create_access_token(user_id=1, role="operator")
    
    # نقوم بتعديل حرف في منتصف التوقيع بدلاً من الحرف الأخير
    parts = token.split(".")
    tampered_signature = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_signature}"
    
    with pytest.raises(AuthenticationError):
        auth_service.decode_token(tampered_token)

@pytest.mark.asyncio
async def test_authenticate_user_success(db_session, auth_service, user_repo):
    hashed = auth_service.hash_password("correct_pass")
    user = User(
        full_name="Test Operator",
        username="test_op",
        hashed_password=hashed,
        role=UserRole.OPERATOR,
        gate_number=1,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    authenticated_user = await auth_service.authenticate_user("test_op", "correct_pass", user_repo)
    assert authenticated_user.id == user.id
    assert authenticated_user.username == "test_op"

@pytest.mark.asyncio
async def test_authenticate_user_wrong_password(db_session, auth_service, user_repo):
    hashed = auth_service.hash_password("correct_pass")
    user = User(
        full_name="Test Operator",
        username="test_op",
        hashed_password=hashed,
        role=UserRole.OPERATOR,
        gate_number=1,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    with pytest.raises(AuthenticationError):
        await auth_service.authenticate_user("test_op", "wrong_pass", user_repo)

@pytest.mark.asyncio
async def test_authenticate_user_not_found(db_session, auth_service, user_repo):
    with pytest.raises(AuthenticationError):
        await auth_service.authenticate_user("nonexistent_user", "some_pass", user_repo)

@pytest.mark.asyncio
async def test_authenticate_user_inactive(db_session, auth_service, user_repo):
    hashed = auth_service.hash_password("correct_pass")
    user = User(
        full_name="Inactive Operator",
        username="inactive_op",
        hashed_password=hashed,
        role=UserRole.OPERATOR,
        gate_number=1,
        is_active=False,
    )
    db_session.add(user)
    await db_session.flush()

    with pytest.raises(AuthenticationError):
        await auth_service.authenticate_user("inactive_op", "correct_pass", user_repo)
