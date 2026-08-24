from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, SmallInteger, ForeignKey
from database import Base
from models.mixins import TimestampMixin

class PricingRule(Base, TimestampMixin):
    __tablename__ = "pricing_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    rate_per_hour: Mapped[int] = mapped_column(nullable=False)
    minimum_charge: Mapped[int] = mapped_column(nullable=False, server_default="0")
    grace_period_mins: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="15")
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="0")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(nullable=False)
    effective_until: Mapped[datetime | None] = mapped_column(nullable=True)
