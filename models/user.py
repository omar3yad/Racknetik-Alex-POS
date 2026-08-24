import enum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Enum, SmallInteger, CheckConstraint
from database import Base
from models.mixins import TimestampMixin

class UserRole(enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    gate_number: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="1")

    __table_args__ = (
        CheckConstraint(
            "(role = 'operator' AND gate_number IS NOT NULL AND gate_number BETWEEN 1 AND 5) "
            "OR (role = 'admin' AND gate_number IS NULL)",
            name="ck_users_role_gate_consistency"
        ),
    )
