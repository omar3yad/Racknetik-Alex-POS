import pytest
import json
from unittest.mock import patch

from models.audit_log import AuditLog
from repositories.audit_log_repo import AuditLogRepository
from services.audit_service import AuditService
from sqlalchemy import select

@pytest.mark.asyncio
async def test_log_creates_record(db_session, audit_service):
    await audit_service.log(
        actor_id=1,
        action="USER_CREATED",
        entity_type="user",
        entity_id=1,
        before=None,
        after={"name": "Ahmed"},
    )
    # Flush or query to check DB
    result = await db_session.execute(select(AuditLog))
    logs = result.scalars().all()
    
    assert len(logs) == 1
    assert logs[0].action == "USER_CREATED"
    assert logs[0].entity_id == 1
    assert logs[0].entity_type == "user"
    assert json.loads(logs[0].payload_after) == {"name": "Ahmed"}

@pytest.mark.asyncio
async def test_log_strips_hashed_password(db_session, audit_service):
    await audit_service.log(
        actor_id=1,
        action="USER_CREATED",
        entity_type="user",
        entity_id=1,
        before={"hashed_password": "old_hash", "username": "ali"},
        after={"hashed_password": "new_hash", "username": "ali"},
    )
    result = await db_session.execute(select(AuditLog))
    log = result.scalars().first()
    
    payload_before = json.loads(log.payload_before)
    payload_after = json.loads(log.payload_after)
    
    assert "hashed_password" not in payload_before
    assert "hashed_password" not in payload_after
    assert payload_before["username"] == "ali"
    assert payload_after["username"] == "ali"

@pytest.mark.asyncio
async def test_log_does_not_raise_on_db_error(db_session, audit_service):
    # Mock repositories AuditLogRepository.create to raise an Exception
    with patch.object(AuditLogRepository, "create", side_effect=Exception("Database error")):
        # Ensure log call doesn't raise exception
        try:
            await audit_service.log(
                actor_id=1,
                action="USER_CREATED",
                entity_type="user",
                entity_id=1,
                before=None,
                after={"name": "Ahmed"},
            )
        except Exception as e:
            pytest.fail(f"AuditService.log raised an exception: {e}")
