import enum
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, SmallInteger, ForeignKey, Enum, Text, Index, text
from database import Base
from models.mixins import TimestampMixin

class SessionStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    LOST_CARD = "LOST_CARD"

class PaymentMethod(enum.Enum):
    CASH = "cash"

class ParkingSession(Base, TimestampMixin):
    __tablename__ = "parking_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("parking_cards.id"), nullable=False, index=True)
    card_code: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), nullable=False, server_default="ACTIVE", index=True)
    gate_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    shift_id: Mapped[int] = mapped_column(ForeignKey("shifts.id"), nullable=False, index=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    entry_time: Mapped[datetime] = mapped_column(nullable=False)
    exit_time: Mapped[datetime | None] = mapped_column(nullable=True)
    plate_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(nullable=True)
    pricing_rule_id: Mapped[int | None] = mapped_column(ForeignKey("pricing_rules.id"), nullable=True)
    amount_charged: Mapped[int | None] = mapped_column(nullable=True)
    is_lost_card: Mapped[bool] = mapped_column(nullable=False, server_default="0")
    lost_card_penalty_applied: Mapped[int | None] = mapped_column(nullable=True)
    payment_method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod), nullable=False, server_default="cash")
    is_paid: Mapped[bool] = mapped_column(nullable=False, server_default="0")
    exit_operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    exit_shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id"), nullable=True)
    receipt_printed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    admin_override_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    admin_override_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(nullable=False, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "idx_active_card_id",
            "card_id",
            unique=True,
            sqlite_where=text("exit_time IS NULL"),
            postgresql_where=text("exit_time IS NULL"),
        ),
    )

__all__ = ["SessionStatus", "PaymentMethod", "ParkingSession"]
