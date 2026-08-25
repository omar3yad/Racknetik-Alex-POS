from datetime import datetime
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.shift import Shift
from models.parking_session import ParkingSession, SessionStatus
from services.audit_service import AuditService
from services.exceptions import (
    ShiftAlreadyOpenError,
    NoActiveShiftError,
    ShiftNotFoundError,
    ShiftNotOwnedError,
)
from services.shift_summary import ShiftSummary

class ShiftService:
    def __init__(self, db: AsyncSession, audit_service: AuditService):
        self.db = db
        self.audit_service = audit_service

    async def get_active_shift(self, operator_id: int) -> Shift | None:
        """Queries for an active (not ended) shift for the operator."""
        result = await self.db.execute(
            select(Shift).where(
                Shift.operator_id == operator_id,
                Shift.ended_at.is_(None)
            ).limit(1)
        )
        return result.scalars().first()

    async def require_active_shift(self, operator_id: int) -> Shift:
        """Guard method that returns the active shift or raises NoActiveShiftError."""
        shift = await self.get_active_shift(operator_id)
        if not shift:
            raise NoActiveShiftError("No active shift found for this operator")
        return shift

    async def open_shift(
        self, operator_id: int, gate_number: int, opening_cash_egp: int
    ) -> Shift:
        """Opens a new shift for the operator if none is currently active."""
        active = await self.get_active_shift(operator_id)
        if active:
            raise ShiftAlreadyOpenError("Operator already has an active shift")

        shift = Shift(
            operator_id=operator_id,
            gate_number=gate_number,
            opening_cash_egp=opening_cash_egp,
            started_at=datetime.utcnow(),
        )
        self.db.add(shift)
        await self.db.flush()
        await self.db.commit()

        await self.audit_service.log(
            actor_id=operator_id,
            action="SHIFT_OPENED",
            entity_type="shift",
            entity_id=shift.id,
            after={
                "operator_id": operator_id,
                "gate_number": gate_number,
                "opening_cash_egp": opening_cash_egp,
            }
        )
        return shift

    async def close_shift(
        self,
        shift_id: int,
        operator_id: int,
        closing_cash_piastres: int,
    ) -> ShiftSummary:
        """Closes an active shift, computes financial summary, and logs the action."""
        result = await self.db.execute(
            select(Shift).where(Shift.id == shift_id).limit(1)
        )
        shift = result.scalars().first()
        if not shift:
            raise ShiftNotFoundError("Shift not found")

        if shift.operator_id != operator_id:
            raise ShiftNotOwnedError("Shift belongs to a different operator")

        shift.ended_at = datetime.utcnow()
        shift.closing_cash_egp = closing_cash_piastres

        summary = await self._compute_summary(shift, closing_cash_piastres)
        await self.db.flush()
        await self.db.commit()

        await self.audit_service.log(
            actor_id=operator_id,
            action="SHIFT_CLOSED",
            entity_type="shift",
            entity_id=shift.id,
            before={
                "id": shift.id,
                "operator_id": shift.operator_id,
                "gate_number": shift.gate_number,
                "started_at": shift.started_at.isoformat() if shift.started_at else None,
            },
            after={
                "ended_at": shift.ended_at.isoformat() if shift.ended_at else None,
                "closing_cash_egp": closing_cash_piastres,
            }
        )
        return summary

    async def _compute_summary(
        self, shift: Shift, closing_cash_piastres: int | None
    ) -> ShiftSummary:
        """Helper that computes the financial and session statistics for the shift."""
        result = await self.db.execute(
            select(ParkingSession).where(ParkingSession.shift_id == shift.id)
        )
        sessions = result.scalars().all()

        total_sessions = len(sessions)
        completed_sessions = sum(1 for s in sessions if s.status == SessionStatus.COMPLETED)
        lost_card_sessions = sum(1 for s in sessions if s.status == SessionStatus.LOST_CARD)
        active_sessions = sum(1 for s in sessions if s.status == SessionStatus.ACTIVE)

        computed_total = sum(
            s.amount_charged for s in sessions
            if s.status in (SessionStatus.COMPLETED, SessionStatus.LOST_CARD) and s.amount_charged is not None
        )

        discrepancy = None
        if closing_cash_piastres is not None:
            discrepancy = closing_cash_piastres - computed_total

        return ShiftSummary(
            shift_id=shift.id,
            operator_id=shift.operator_id,
            gate_number=shift.gate_number,
            started_at=shift.started_at,
            ended_at=shift.ended_at,
            total_sessions=total_sessions,
            completed_sessions=completed_sessions,
            lost_card_sessions=lost_card_sessions,
            active_sessions=active_sessions,
            computed_total_piastres=computed_total,
            closing_cash_piastres=closing_cash_piastres,
            discrepancy_piastres=discrepancy,
        )

__all__ = ["ShiftService"]
