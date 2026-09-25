from datetime import datetime, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.shift import Shift
from models.parking_session import ParkingSession, SessionStatus
from schemas.admin_reports import ShiftFilters
from utils.time import cairo_date_to_utc_start, cairo_date_to_utc_end


class AdminShiftRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_shifts_filtered(
        self,
        filters: ShiftFilters,
        page: int,
        size: int,
    ) -> tuple[list[Shift], int]:
        """Returns paginated shifts matching filters and total count
        ordered by started_at DESC.
        """
        conditions = []
        if filters.operator_id is not None:
            conditions.append(Shift.operator_id == filters.operator_id)
        if filters.gate_number is not None:
            conditions.append(Shift.gate_number == filters.gate_number)
        if filters.status == "open":
            conditions.append(Shift.ended_at.is_(None))
        elif filters.status == "closed":
            conditions.append(Shift.ended_at.isnot(None))
        if filters.start_date is not None:
            conditions.append(
                Shift.started_at >= cairo_date_to_utc_start(filters.start_date)
            )
        if filters.end_date is not None:
            conditions.append(
                Shift.started_at < cairo_date_to_utc_end(filters.end_date)
            )
        if filters.overdue:
            threshold = datetime.utcnow() - timedelta(hours=12)
            conditions.append(Shift.ended_at.is_(None))
            conditions.append(Shift.started_at < threshold)

        count_q = select(func.count(Shift.id))
        if conditions:
            count_q = count_q.where(and_(*conditions))
        total_count = (await self.db.execute(count_q)).scalar_one_or_none() or 0

        data_q = select(Shift)
        if conditions:
            data_q = data_q.where(and_(*conditions))
        data_q = (
            data_q.order_by(Shift.started_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        shifts = list((await self.db.execute(data_q)).scalars().all())
        return shifts, total_count

    async def get_shift_session_totals(
        self,
        shift_ids: list[int],
    ) -> dict[int, int]:
        """Calculates total revenue (in piastres) for COMPLETED and
        LOST_CARD sessions that were EXITED in the given shifts (exit_shift_id).
        Revenue is credited to the operator who checked the car OUT, not in.
        """
        if not shift_ids:
            return {}

        result_map = {sid: 0 for sid in shift_ids}
        q = (
            select(
                ParkingSession.exit_shift_id,
                func.coalesce(func.sum(ParkingSession.amount_charged), 0),
            )
            .where(
                ParkingSession.exit_shift_id.in_(shift_ids),
                ParkingSession.status.in_(
                    [SessionStatus.COMPLETED, SessionStatus.LOST_CARD]
                ),
            )
            .group_by(ParkingSession.exit_shift_id)
        )
        rows = (await self.db.execute(q)).all()
        for sid, total in rows:
            result_map[sid] = int(total or 0)
        return result_map

    async def get_shift_session_counts(
        self,
        shift_id: int,
    ) -> dict[str, int]:
        """Returns session counts grouped by status for a single shift.

        ACTIVE count is based on entry shift (shift_id).
        COMPLETED and LOST_CARD counts are based on exit shift (exit_shift_id)
        so the operator who checked the car out is credited.
        """
        counts = {"ACTIVE": 0, "COMPLETED": 0, "LOST_CARD": 0}

        # Active sessions: entered in this shift and not yet exited
        active_q = (
            select(func.count(ParkingSession.id))
            .where(
                ParkingSession.shift_id == shift_id,
                ParkingSession.status == SessionStatus.ACTIVE,
            )
        )
        active_count = (await self.db.execute(active_q)).scalar_one_or_none() or 0
        counts["ACTIVE"] = int(active_count)

        # Completed/lost-card: exited in this shift
        exit_q = (
            select(
                ParkingSession.status,
                func.count(ParkingSession.id),
            )
            .where(
                ParkingSession.exit_shift_id == shift_id,
                ParkingSession.status.in_([
                    SessionStatus.COMPLETED,
                    SessionStatus.LOST_CARD,
                ]),
            )
            .group_by(ParkingSession.status)
        )
        rows = (await self.db.execute(exit_q)).all()
        for status_val, count in rows:
            key = status_val.value if hasattr(status_val, "value") else str(status_val)
            counts[key] = int(count or 0)
        return counts


__all__ = ["AdminShiftRepository"]
