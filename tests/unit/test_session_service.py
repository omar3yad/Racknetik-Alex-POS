import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from sqlalchemy import select

from models.user import User, UserRole
from models.parking_card import ParkingCard, CardStatus
from models.parking_session import ParkingSession, SessionStatus
from models.pricing_rule import PricingRule
from models.shift import Shift
from services.card_service import CardService
from services.pricing_service import PricingService
from services.shift_service import ShiftService
from services.audit_service import AuditService
from services.plate_service import PlateService
from services.session_service import SessionService
from repositories.session_repo import ParkingSessionRepository
from services.exceptions import (
    NoActiveShiftError,
    CardAlreadyActiveError,
    CardNotFoundError,
    SessionNotActiveError,
    NoPricingRuleError,
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

async def setup_pricing_rule(db_session):
    rule = PricingRule(
        label="Standard Rule",
        rate_per_hour=1000,
        minimum_charge=500,
        grace_period_mins=15,
        lost_card_penalty=2000,
        is_active=True,
        created_by=1,
        effective_from=datetime.utcnow()
    )
    db_session.add(rule)
    await db_session.commit()
    return rule

async def open_operator_shift(db_session, operator_id):
    shift = Shift(
        operator_id=operator_id,
        gate_number=1,
        started_at=datetime.utcnow(),
        opening_cash_egp=5000,
    )
    db_session.add(shift)
    await db_session.commit()
    return shift

def get_session_service(db_session) -> SessionService:
    card_service = CardService(db_session)
    session_repo = ParkingSessionRepository(db_session)
    pricing_service = PricingService(db_session)
    audit_service = AuditService(db_session)
    shift_service = ShiftService(db_session, audit_service)
    plate_service = PlateService()
    return SessionService(
        db=db_session,
        card_service=card_service,
        session_repo=session_repo,
        pricing_service=pricing_service,
        shift_service=shift_service,
        audit_service=audit_service,
        plate_service=plate_service,
    )

@pytest.mark.asyncio
async def test_open_session_success(db_session):
    op = await setup_operator(db_session)
    await open_operator_shift(db_session, op.id)
    
    card = ParkingCard(card_code="CARD-0001", status=CardStatus.AVAILABLE)
    db_session.add(card)
    await db_session.commit()

    service = get_session_service(db_session)
    session = await service.open_session("CARD-0001", op.id)

    assert session.status == SessionStatus.ACTIVE
    assert session.card_code == "CARD-0001"
    
    await db_session.refresh(card)
    assert card.status == CardStatus.IN_USE

@pytest.mark.asyncio
async def test_open_session_no_shift(db_session):
    op = await setup_operator(db_session)
    # No active shift opened
    
    card = ParkingCard(card_code="CARD-0001", status=CardStatus.AVAILABLE)
    db_session.add(card)
    await db_session.commit()

    service = get_session_service(db_session)
    with pytest.raises(NoActiveShiftError):
        await service.open_session("CARD-0001", op.id)

@pytest.mark.asyncio
async def test_open_session_card_already_active(db_session):
    op = await setup_operator(db_session)
    await open_operator_shift(db_session, op.id)
    
    card = ParkingCard(card_code="CARD-0001", status=CardStatus.IN_USE)
    sess = ParkingSession(
        card_code="CARD-0001",
        status=SessionStatus.ACTIVE,
        entry_time=datetime.utcnow(),
        gate_number=1,
        operator_id=op.id,
    )
    db_session.add_all([card, sess])
    await db_session.commit()

    service = get_session_service(db_session)
    with pytest.raises(CardAlreadyActiveError):
        await service.open_session("CARD-0001", op.id)

@pytest.mark.asyncio
async def test_open_session_card_not_found(db_session):
    op = await setup_operator(db_session)
    await open_operator_shift(db_session, op.id)

    service = get_session_service(db_session)
    with pytest.raises(CardNotFoundError):
        await service.open_session("CARD-NONEXISTENT", op.id)

@pytest.mark.asyncio
async def test_open_session_atomicity(db_session):
    op = await setup_operator(db_session)
    await open_operator_shift(db_session, op.id)
    
    card = ParkingCard(card_code="CARD-0001", status=CardStatus.AVAILABLE)
    db_session.add(card)
    await db_session.commit()

    service = get_session_service(db_session)
    
    # Patch CardService.set_status to raise an exception
    with patch.object(service.card_service, "set_status", side_effect=ValueError("mock error")):
        with pytest.raises(ValueError):
            await service.open_session("CARD-0001", op.id)

    # Verify that no session row was committed
    stmt = select(ParkingSession).where(ParkingSession.card_code == "CARD-0001")
    res = await db_session.execute(stmt)
    sessions = res.scalars().all()
    assert len(sessions) == 0

@pytest.mark.asyncio
async def test_close_session_success(db_session):
    op = await setup_operator(db_session)
    await setup_pricing_rule(db_session)
    await open_operator_shift(db_session, op.id)

    card = ParkingCard(card_code="CARD-0001", status=CardStatus.IN_USE)
    sess = ParkingSession(
        card_code="CARD-0001",
        status=SessionStatus.ACTIVE,
        entry_time=datetime.utcnow() - timedelta(hours=2),
        gate_number=1,
        operator_id=op.id,
    )
    db_session.add_all([card, sess])
    await db_session.commit()

    service = get_session_service(db_session)
    closed_sess, calc = await service.close_session(sess.id, op.id)

    assert closed_sess.status == SessionStatus.COMPLETED
    assert closed_sess.is_paid is True
    assert isinstance(closed_sess.amount_charged, int)
    assert closed_sess.amount_charged == 2000 # 2 hours * 10 EGP
    
    await db_session.refresh(card)
    assert card.status == CardStatus.AVAILABLE

@pytest.mark.asyncio
async def test_close_session_not_active(db_session):
    op = await setup_operator(db_session)
    await setup_pricing_rule(db_session)
    await open_operator_shift(db_session, op.id)

    card = ParkingCard(card_code="CARD-0001", status=CardStatus.AVAILABLE)
    sess = ParkingSession(
        card_code="CARD-0001",
        status=SessionStatus.COMPLETED,
        entry_time=datetime.utcnow() - timedelta(hours=2),
        exit_time=datetime.utcnow(),
        gate_number=1,
        operator_id=op.id,
        exit_operator_id=op.id,
        amount_charged=2000,
    )
    db_session.add_all([card, sess])
    await db_session.commit()

    service = get_session_service(db_session)
    with pytest.raises(SessionNotActiveError):
        await service.close_session(sess.id, op.id)

@pytest.mark.asyncio
async def test_close_session_no_pricing_rule(db_session):
    op = await setup_operator(db_session)
    await open_operator_shift(db_session, op.id)
    # No pricing rules seeded

    card = ParkingCard(card_code="CARD-0001", status=CardStatus.IN_USE)
    sess = ParkingSession(
        card_code="CARD-0001",
        status=SessionStatus.ACTIVE,
        entry_time=datetime.utcnow() - timedelta(hours=2),
        gate_number=1,
        operator_id=op.id,
    )
    db_session.add_all([card, sess])
    await db_session.commit()

    service = get_session_service(db_session)
    with pytest.raises(NoPricingRuleError):
        await service.close_session(sess.id, op.id)

    await db_session.refresh(sess)
    assert sess.status == SessionStatus.ACTIVE

@pytest.mark.asyncio
async def test_resolve_lost_card_success(db_session):
    op = await setup_operator(db_session)
    await setup_pricing_rule(db_session)
    await open_operator_shift(db_session, op.id)

    card = ParkingCard(card_code="CARD-0001", status=CardStatus.IN_USE)
    sess = ParkingSession(
        card_code="CARD-0001",
        status=SessionStatus.ACTIVE,
        entry_time=datetime.utcnow() - timedelta(hours=2),
        gate_number=1,
        operator_id=op.id,
    )
    db_session.add_all([card, sess])
    await db_session.commit()

    service = get_session_service(db_session)
    resolved_sess = await service.resolve_lost_card(sess.id, op.id, notes="lost card report")

    assert resolved_sess.status == SessionStatus.LOST_CARD
    assert resolved_sess.is_lost_card is True
    assert resolved_sess.lost_card_penalty_applied == 2000
    
    await db_session.refresh(card)
    assert card.status == CardStatus.LOST

@pytest.mark.asyncio
async def test_mark_receipt_printed_idempotent(db_session):
    op = await setup_operator(db_session)
    await setup_pricing_rule(db_session)
    await open_operator_shift(db_session, op.id)

    sess = ParkingSession(
        card_code="CARD-0001",
        status=SessionStatus.COMPLETED,
        entry_time=datetime.utcnow() - timedelta(hours=2),
        exit_time=datetime.utcnow(),
        gate_number=1,
        operator_id=op.id,
        exit_operator_id=op.id,
        amount_charged=2000,
    )
    db_session.add(sess)
    await db_session.commit()

    service = get_session_service(db_session)
    
    # First print
    await service.mark_receipt_printed(sess.id)
    await db_session.refresh(sess)
    first_printed = sess.receipt_printed_at
    assert first_printed is not None

    # Second print
    await service.mark_receipt_printed(sess.id)
    await db_session.refresh(sess)
    assert sess.receipt_printed_at == first_printed

@pytest.mark.asyncio
async def test_find_active_by_plate_normalizes(db_session):
    op = await setup_operator(db_session)
    await open_operator_shift(db_session, op.id)
    
    sess = ParkingSession(
        card_code="CARD-0001",
        status=SessionStatus.ACTIVE,
        entry_time=datetime.utcnow(),
        gate_number=1,
        operator_id=op.id,
        plate_number="ن ي ش 159",
    )
    db_session.add(sess)
    await db_session.commit()

    service = get_session_service(db_session)
    sessions = await service.find_active_by_plate("ن ي ش ١٥٩") # Eastern digits input
    assert len(sessions) == 1
    assert sessions[0].id == sess.id
