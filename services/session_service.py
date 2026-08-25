from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.parking_card import ParkingCard, CardStatus
from models.parking_session import ParkingSession, SessionStatus
from repositories.session_repo import ParkingSessionRepository
from services.audit_service import AuditService
from services.card_service import CardService
from services.exceptions import SessionNotFoundError, SessionNotActiveError
from services.plate_service import PlateService
from services.pricing_calculation import PriceCalculation
from services.pricing_service import PricingService
from services.shift_service import ShiftService

class SessionService:
    def __init__(
        self,
        db: AsyncSession,
        card_service: CardService,
        session_repo: ParkingSessionRepository,
        pricing_service: PricingService,
        shift_service: ShiftService,
        audit_service: AuditService,
        plate_service: PlateService,
    ):
        self.db = db
        self.card_service = card_service
        self.session_repo = session_repo
        self.pricing_service = pricing_service
        self.shift_service = shift_service
        self.audit_service = audit_service
        self.plate_service = plate_service

    async def open_session(
        self,
        card_code: str,
        operator_id: int,
        plate_number: str | None = None,
    ) -> ParkingSession:
        """Atomically opens a new parking session."""
        shift = await self.shift_service.require_active_shift(operator_id)
        card = await self.card_service.validate_for_entry(card_code)

        if plate_number is not None:
            normalized_plate = self.plate_service.normalize(plate_number)
            if normalized_plate == "":
                plate_number = None
            else:
                plate_number = normalized_plate

        try:
            session = await self.session_repo.create(
                card_id=card.id,
                card_code=card.card_code,
                gate_number=shift.gate_number,
                shift_id=shift.id,
                operator_id=operator_id,
                plate_number=plate_number,
            )
            await self.card_service.set_status(card, CardStatus.IN_USE)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        await self.audit_service.log(
            actor_id=operator_id,
            action="SESSION_OPENED",
            entity_type="parking_session",
            entity_id=session.id,
            before=None,
            after={
                "card_code": card.card_code,
                "gate_number": shift.gate_number,
            },
        )
        return session

    async def close_session(
        self,
        session_id: int,
        exit_operator_id: int,
    ) -> tuple[ParkingSession, PriceCalculation]:
        """Atomically closes an active parking session, computing total fees."""
        exit_shift = await self.shift_service.require_active_shift(exit_operator_id)
        session = await self.session_repo.get_by_id_for_update(session_id)
        if not session:
            raise SessionNotFoundError("Session not found")

        if session.status != SessionStatus.ACTIVE:
            raise SessionNotActiveError("Session is not active")

        rule = await self.pricing_service.get_active_rule()
        exit_time = datetime.utcnow()
        calc = self.pricing_service.calculate(session, rule, exit_time)

        # Update session details
        session.status = SessionStatus.COMPLETED
        session.exit_time = exit_time
        session.exit_operator_id = exit_operator_id
        session.exit_shift_id = exit_shift.id
        session.duration_minutes = calc.duration_minutes
        session.amount_charged = calc.total_amount
        session.pricing_rule_id = rule.id
        session.is_paid = True

        # Fetch card and update status
        result = await self.db.execute(
            select(ParkingCard).where(ParkingCard.id == session.card_id).limit(1)
        )
        card = result.scalars().first()
        if card:
            await self.card_service.set_status(card, CardStatus.AVAILABLE)

        await self.db.commit()

        await self.audit_service.log(
            actor_id=exit_operator_id,
            action="SESSION_CLOSED",
            entity_type="parking_session",
            entity_id=session.id,
            before={
                "id": session.id,
                "status": "ACTIVE",
            },
            after={
                "status": "COMPLETED",
                "exit_time": exit_time.isoformat(),
                "amount_charged": calc.total_amount,
            },
        )
        return session, calc

    async def resolve_lost_card(
        self,
        session_id: int,
        operator_id: int,
        notes: str | None = None,
    ) -> tuple[ParkingSession, PriceCalculation]:
        """Resolves a session in which the user lost their card, applying penalty fees."""
        shift = await self.shift_service.require_active_shift(operator_id)
        session = await self.session_repo.get_by_id_for_update(session_id)
        if not session:
            raise SessionNotFoundError("Session not found")

        if session.status != SessionStatus.ACTIVE:
            raise SessionNotActiveError("Session is not active")

        rule = await self.pricing_service.get_active_rule()
        exit_time = datetime.utcnow()
        calc = self.pricing_service.calculate_lost_card(session, rule, exit_time)

        # Update session details
        session.status = SessionStatus.LOST_CARD
        session.exit_time = exit_time
        session.is_lost_card = True
        session.exit_operator_id = operator_id
        session.exit_shift_id = shift.id
        session.duration_minutes = calc.duration_minutes
        session.amount_charged = calc.total_amount
        session.pricing_rule_id = rule.id
        session.lost_card_penalty_applied = rule.lost_card_penalty
        session.is_paid = True
        session.notes = notes

        # Fetch card and update status to LOST
        result = await self.db.execute(
            select(ParkingCard).where(ParkingCard.id == session.card_id).limit(1)
        )
        card = result.scalars().first()
        if card:
            await self.card_service.set_status(card, CardStatus.LOST)

        await self.db.commit()

        await self.audit_service.log(
            actor_id=operator_id,
            action="LOST_CARD_RESOLVED",
            entity_type="parking_session",
            entity_id=session.id,
            before={
                "id": session.id,
                "status": "ACTIVE",
            },
            after={
                "status": "LOST_CARD",
                "exit_time": exit_time.isoformat(),
                "amount_charged": calc.total_amount,
                "is_lost_card": True,
            },
        )
        return session, calc

    async def find_active_by_plate(self, plate: str) -> list[ParkingSession]:
        """Finds active sessions by normalized plate string."""
        normalized = self.plate_service.normalize(plate)
        return await self.session_repo.get_active_by_plate(normalized)

    async def mark_receipt_printed(self, session_id: int) -> None:
        """Idempotently records that the receipt for a session has been printed."""
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            return

        if session.receipt_printed_at is None:
            session.receipt_printed_at = datetime.utcnow()
            await self.db.flush()
            await self.db.commit()

__all__ = ["SessionService"]
