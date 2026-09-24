"""phase3_performance_indexes

Revision ID: 2a316cd66e8b
Revises: aebc83f33383
Create Date: 2026-09-24 13:21:36.735203

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a316cd66e8b'
down_revision: Union[str, None] = 'aebc83f33383'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    existing_ps_indexes = {idx["name"] for idx in insp.get_indexes("parking_sessions")}
    existing_shift_indexes = {idx["name"] for idx in insp.get_indexes("shifts")}

    if "ix_parking_sessions_exit_time" not in existing_ps_indexes:
        op.create_index(
            "ix_parking_sessions_exit_time",
            "parking_sessions",
            ["exit_time"],
            unique=False,
        )

    if "ix_parking_sessions_entry_time" not in existing_ps_indexes:
        op.create_index(
            "ix_parking_sessions_entry_time",
            "parking_sessions",
            ["entry_time"],
            unique=False,
        )

    if "ix_parking_sessions_status" not in existing_ps_indexes:
        op.create_index(
            "ix_parking_sessions_status",
            "parking_sessions",
            ["status"],
            unique=False,
        )

    if "ix_shifts_started_at" not in existing_shift_indexes:
        op.create_index(
            "ix_shifts_started_at",
            "shifts",
            ["started_at"],
            unique=False,
        )

    if "ix_shifts_ended_at" not in existing_shift_indexes:
        op.create_index(
            "ix_shifts_ended_at",
            "shifts",
            ["ended_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    existing_ps_indexes = {idx["name"] for idx in insp.get_indexes("parking_sessions")}
    existing_shift_indexes = {idx["name"] for idx in insp.get_indexes("shifts")}

    if "ix_shifts_ended_at" in existing_shift_indexes:
        op.drop_index("ix_shifts_ended_at", table_name="shifts")

    if "ix_shifts_started_at" in existing_shift_indexes:
        op.drop_index("ix_shifts_started_at", table_name="shifts")

    if "ix_parking_sessions_status" in existing_ps_indexes:
        op.drop_index("ix_parking_sessions_status", table_name="parking_sessions")

    if "ix_parking_sessions_entry_time" in existing_ps_indexes:
        op.drop_index("ix_parking_sessions_entry_time", table_name="parking_sessions")

    if "ix_parking_sessions_exit_time" in existing_ps_indexes:
        op.drop_index("ix_parking_sessions_exit_time", table_name="parking_sessions")
