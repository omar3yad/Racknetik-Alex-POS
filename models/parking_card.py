import enum
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Enum
from database import Base
from models.mixins import TimestampMixin

class CardStatus(enum.Enum):
    AVAILABLE = "available"
    IN_USE = "in_use"
    LOST = "lost"
    DAMAGED = "damaged"

class ParkingCard(Base, TimestampMixin):
    __tablename__ = "parking_cards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    card_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    status: Mapped[CardStatus] = mapped_column(Enum(CardStatus), nullable=False, server_default="available")
    last_seen_at: Mapped[datetime | None] = mapped_column(nullable=True)

__all__ = ["CardStatus", "ParkingCard"]
