from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import SmallInteger, ForeignKey, Text
from database import Base
from models.mixins import TimestampMixin

class Shift(Base, TimestampMixin):
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    gate_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    opening_cash_egp: Mapped[int] = mapped_column(nullable=False, server_default="0")
    closing_cash_egp: Mapped[int | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
