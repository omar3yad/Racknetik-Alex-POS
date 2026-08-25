from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.shift import Shift

class ShiftRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, shift_id: int) -> Shift | None:
        """Fetches a shift by its id."""
        result = await self.db.execute(
            select(Shift).where(Shift.id == shift_id).limit(1)
        )
        return result.scalars().first()

    async def get_active_for_operator(self, operator_id: int) -> Shift | None:
        """Queries for the active (not ended) shift of an operator."""
        result = await self.db.execute(
            select(Shift).where(
                Shift.operator_id == operator_id,
                Shift.ended_at.is_(None)
            ).limit(1)
        )
        return result.scalars().first()

    async def create(self, **kwargs) -> Shift:
        """Creates a shift with the given attributes, flushing changes."""
        shift = Shift(**kwargs)
        self.db.add(shift)
        await self.db.flush()
        return shift

    async def get_all(
        self,
        operator_id: int | None = None,
        gate_number: int | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Shift], int]:
        """Returns a paginated list of shifts (filtered by operator_id and/or gate_number) and total count."""
        query = select(Shift)
        count_query = select(func.count()).select_from(Shift)

        if operator_id is not None:
            query = query.where(Shift.operator_id == operator_id)
            count_query = count_query.where(Shift.operator_id == operator_id)

        if gate_number is not None:
            query = query.where(Shift.gate_number == gate_number)
            count_query = count_query.where(Shift.gate_number == gate_number)

        # Count total
        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar_one()

        # Paginated query ordered by started_at descending
        offset_val = (page - 1) * size
        query = query.order_by(Shift.started_at.desc()).offset(offset_val).limit(size)
        result = await self.db.execute(query)
        shifts = list(result.scalars().all())

        return shifts, total_count

__all__ = ["ShiftRepository"]
