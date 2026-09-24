import enum
from datetime import date, datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, SmallInteger, Integer, Date, ForeignKey, Enum, Text
from database import Base
from models.mixins import TimestampMixin


class SubscriptionStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    PENDING = "PENDING"


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subscriber_id: Mapped[int] = mapped_column(ForeignKey("subscribers.id"), nullable=False, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("subscription_plans.id"), nullable=False)
    card_id: Mapped[int] = mapped_column(ForeignKey("parking_cards.id"), nullable=False, index=True)
    plate_number: Mapped[str] = mapped_column(String(30), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscriptionstatus"),
        nullable=False,
        server_default="ACTIVE",
        index=True,
    )
    amount_paid_piastres: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_price_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(nullable=True)
    collected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    renewal_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    previous_subscription_id: Mapped[int | None] = mapped_column(ForeignKey("subscriptions.id"), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = ["SubscriptionStatus", "Subscription"]
