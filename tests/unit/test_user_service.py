import pytest
from fastapi import HTTPException

from models.user import User, UserRole
from schemas.user import UserCreate
from services.user_service import UserService

@pytest.fixture
def user_service(db_session, user_repo, auth_service, audit_service) -> UserService:
    return UserService(db_session, user_repo, auth_service, audit_service)

@pytest.mark.asyncio
async def test_create_user_success(db_session, user_service):
    data = UserCreate(
        full_name="Imad Ahmed",
        username="imad_op",
        password="operatorpassword123",
        role=UserRole.OPERATOR,
        gate_number=1,
    )
    user = await user_service.create_user(data)
    assert user.username == "imad_op"
    assert user.role == UserRole.OPERATOR
    assert user.gate_number == 1
    assert user.hashed_password != "operatorpassword123"
    assert user.is_active is True

@pytest.mark.asyncio
async def test_create_user_duplicate_username(db_session, user_service):
    data = UserCreate(
        full_name="Imad Ahmed",
        username="imad_op",
        password="operatorpassword123",
        role=UserRole.OPERATOR,
        gate_number=1,
    )
    await user_service.create_user(data)
    
    # Attempt to create again with same username
    with pytest.raises(HTTPException) as exc_info:
        await user_service.create_user(data)
    
    assert exc_info.value.status_code == 409
    assert exc_info.value.headers.get("X-Error-Code") == "USERNAME_ALREADY_EXISTS"

@pytest.mark.asyncio
async def test_deactivate_user_success(db_session, user_service, auth_service):
    # Create admin actor
    admin = User(
        full_name="Admin Actor",
        username="admin_actor",
        hashed_password=auth_service.hash_password("adminpass"),
        role=UserRole.ADMIN,
        gate_number=None,
        is_active=True,
    )
    db_session.add(admin)
    
    # Create target operator user
    user = User(
        full_name="Target User",
        username="target_op",
        hashed_password=auth_service.hash_password("targetpass"),
        role=UserRole.OPERATOR,
        gate_number=2,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    deactivated = await user_service.deactivate_user(user.id, actor_id=admin.id)
    assert deactivated.is_active is False
    assert user.is_active is False

@pytest.mark.asyncio
async def test_deactivate_user_self(db_session, user_service, auth_service):
    admin = User(
        full_name="Admin Actor",
        username="admin_actor",
        hashed_password=auth_service.hash_password("adminpass"),
        role=UserRole.ADMIN,
        gate_number=None,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await user_service.deactivate_user(admin.id, actor_id=admin.id)
    
    assert exc_info.value.status_code == 403
    assert exc_info.value.headers.get("X-Error-Code") == "CANNOT_DEACTIVATE_SELF"

@pytest.mark.asyncio
async def test_deactivate_user_already_inactive(db_session, user_service, auth_service):
    admin = User(
        full_name="Admin Actor",
        username="admin_actor",
        hashed_password=auth_service.hash_password("adminpass"),
        role=UserRole.ADMIN,
        gate_number=None,
        is_active=True,
    )
    db_session.add(admin)
    
    user = User(
        full_name="Target User",
        username="target_op",
        hashed_password=auth_service.hash_password("targetpass"),
        role=UserRole.OPERATOR,
        gate_number=2,
        is_active=False, # Already inactive
    )
    db_session.add(user)
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await user_service.deactivate_user(user.id, actor_id=admin.id)
        
    assert exc_info.value.status_code == 409
    assert exc_info.value.headers.get("X-Error-Code") == "USER_ALREADY_INACTIVE"

@pytest.mark.asyncio
async def test_reset_password_success(db_session, user_service, auth_service):
    admin = User(
        full_name="Admin Actor",
        username="admin_actor",
        hashed_password=auth_service.hash_password("adminpass"),
        role=UserRole.ADMIN,
        gate_number=None,
        is_active=True,
    )
    db_session.add(admin)
    
    user = User(
        full_name="Target User",
        username="target_op",
        hashed_password=auth_service.hash_password("targetpass"),
        role=UserRole.OPERATOR,
        gate_number=2,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    updated_user = await user_service.reset_password(user.id, "newpassword12345", actor_id=admin.id)
    assert auth_service.verify_password("newpassword12345", updated_user.hashed_password) is True
