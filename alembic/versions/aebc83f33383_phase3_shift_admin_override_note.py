"""phase3_shift_admin_override_note

Revision ID: aebc83f33383
Revises: 3db202ff13a1
Create Date: 2026-09-24 13:21:14.317828

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aebc83f33383'
down_revision: Union[str, None] = '3db202ff13a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('shifts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('admin_override_note', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('shifts', schema=None) as batch_op:
        batch_op.drop_column('admin_override_note')
