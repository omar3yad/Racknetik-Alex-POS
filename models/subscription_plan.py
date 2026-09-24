from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, SmallInteger, Integer, ForeignKey, Text
from database import Base
from models.mixins import TimestampMixin


class SubscriptionPlan(Base, TimestampMixin):
    __tablename__ = "subscription_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    duration_days: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    price_piastres: Mapped[int] = mapped_column(Integer, nullable=False)
    max_entries_per_day: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="1")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


__all__ = ["SubscriptionPlan"]
