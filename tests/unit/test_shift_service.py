import pytest
from datetime import datetime, timedelta
from models.user import User, UserRole
from models.parking_card import ParkingCard, CardStatus
from models.parking_session import ParkingSession, SessionStatus
from models.shift import Shift
from services.shift_service import ShiftService
from services.audit_service import AuditService
from services.exceptions import (
    ShiftAlreadyOpenError,
    NoActiveShiftError,
    ShiftNotOwnedError,
)

async def setup_operator(db_session, username="op1"):
    user = User(
        full_name="Operator User",
        username=username,
        hashed_password="hashed_password",
        role=UserRole.OPERATOR,
        gate_number=1,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user

@pytest.mark.asyncio
async def test_open_shift_success(db_session, audit_service):
    op = await setup_operator(db_session)
    service = ShiftService(db_session, audit_service)
    
    shift = await service.open_shift(
        operator_id=op.id,
        gate_number=1,
        opening_cash_egp=50000 # in piastres
    )
    assert shift.id is not None
    assert shift.operator_id == op.id
    assert shift.gate_number == 1
    assert shift.ended_at is None
    assert shift.opening_cash_egp == 50000

@pytest.mark.asyncio
async def test_open_shift_already_open(db_session, audit_service):
    op = await setup_operator(db_session)
    service = ShiftService(db_session, audit_service)
    
    await service.open_shift(operator_id=op.id, gate_number=1, opening_cash_egp=50000)
    
    with pytest.raises(ShiftAlreadyOpenError):
        await service.open_shift(operator_id=op.id, gate_number=1, opening_cash_egp=50000)

@pytest.mark.asyncio
async def test_require_active_shift_no_shift(db_session, audit_service):
    op = await setup_operator(db_session)
    service = ShiftService(db_session, audit_service)
    
    with pytest.raises(NoActiveShiftError):
        await service.require_active_shift(operator_id=op.id)

@pytest.mark.asyncio
async def test_close_shift_success(db_session, audit_service):
    op = await setup_operator(db_session)
    service = ShiftService(db_session, audit_service)
    
    shift = await service.open_shift(operator_id=op.id, gate_number=1, opening_cash_egp=50000)
    
    summary = await service.close_shift(
        shift_id=shift.id,
        operator_id=op.id,
        closing_cash_piastres=60000
    )
    assert summary.ended_at is not None
    assert summary.closing_cash_piastres == 60000
    assert summary.opening_cash_piastres == 50000

@pytest.mark.asyncio
async def test_close_shift_not_owned(db_session, audit_service):
    op1 = await setup_operator(db_session, username="op1")
    op2 = await setup_operator(db_session, username="op2")
    service = ShiftService(db_session, audit_service)
    
    shift = await service.open_shift(operator_id=op1.id, gate_number=1, opening_cash_egp=50000)
    
    with pytest.raises(ShiftNotOwnedError):
        await service.close_shift(
            shift_id=shift.id,
            operator_id=op2.id,
            closing_cash_piastres=60000
        )

@pytest.mark.asyncio
async def test_compute_summary_counts(db_session, audit_service):
    op = await setup_operator(db_session)
    service = ShiftService(db_session, audit_service)
    
    shift = await service.open_shift(operator_id=op.id, gate_number=1, opening_cash_egp=50000)
    
    # 2 Completed, 1 Active
    s1 = ParkingSession(
        card_code="CARD-1",
        status=SessionStatus.COMPLETED,
        entry_time=datetime.utcnow() - timedelta(hours=2),
        exit_time=datetime.utcnow(),
        gate_number=1,
        operator_id=op.id,
        exit_operator_id=op.id,
        amount_charged=1000,
        shift_id=shift.id,
    )
    s2 = ParkingSession(
        card_code="CARD-2",
        status=SessionStatus.COMPLETED,
        entry_time=datetime.utcnow() - timedelta(hours=1),
        exit_time=datetime.utcnow(),
        gate_number=1,
        operator_id=op.id,
        exit_operator_id=op.id,
        amount_charged=1500,
        shift_id=shift.id,
    )
    s3 = ParkingSession(
        card_code="CARD-3",
        status=SessionStatus.ACTIVE,
        entry_time=datetime.utcnow(),
        gate_number=1,
        operator_id=op.id,
        shift_id=shift.id,
    )
    db_session.add_all([s1, s2, s3])
    await db_session.commit()
    
    summary = await service._compute_summary(shift, closing_cash_piastres=60000)
    assert summary.total_sessions == 3
    assert summary.completed_sessions == 2
    assert summary.active_sessions == 1
    assert summary.computed_total_piastres == 2500
