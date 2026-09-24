"""phase4_subscriptions_initial

Revision ID: 3db202ff13a1
Revises: 140759ec5905
Create Date: 2026-09-24 06:51:12.433007

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3db202ff13a1'
down_revision: Union[str, None] = '140759ec5905'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. subscription_plans table
    op.create_table(
        'subscription_plans',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('duration_days', sa.SmallInteger(), nullable=False),
        sa.Column('price_piastres', sa.Integer(), nullable=False),
        sa.Column('max_entries_per_day', sa.SmallInteger(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('subscription_plans', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_subscription_plans_label'), ['label'], unique=True)

    # 2. subscribers table
    op.create_table(
        'subscribers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('full_name', sa.String(length=120), nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=True),
        sa.Column('plate_number', sa.String(length=30), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('subscribers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_subscribers_plate_number'), ['plate_number'], unique=True)

    # 3. subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('subscriber_id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('plate_number', sa.String(length=30), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'EXPIRED', 'CANCELLED', 'PENDING', name='subscriptionstatus'), server_default='ACTIVE', nullable=False),
        sa.Column('amount_paid_piastres', sa.Integer(), nullable=False),
        sa.Column('plan_price_snapshot', sa.Integer(), nullable=False),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('collected_by', sa.Integer(), nullable=True),
        sa.Column('renewal_count', sa.SmallInteger(), server_default='0', nullable=False),
        sa.Column('previous_subscription_id', sa.Integer(), nullable=True),
        sa.Column('cancel_reason', sa.Text(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['card_id'], ['parking_cards.id'], ),
        sa.ForeignKeyConstraint(['collected_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['plan_id'], ['subscription_plans.id'], ),
        sa.ForeignKeyConstraint(['previous_subscription_id'], ['subscriptions.id'], ),
        sa.ForeignKeyConstraint(['subscriber_id'], ['subscribers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_subscriptions_card_id'), ['card_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_subscriptions_end_date'), ['end_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_subscriptions_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_subscriptions_subscriber_id'), ['subscriber_id'], unique=False)
        # Composite performance indexes
        batch_op.create_index('ix_subscriptions_subscriber_id_status', ['subscriber_id', 'status'], unique=False)
        batch_op.create_index('ix_subscriptions_card_id_status', ['card_id', 'status'], unique=False)
        batch_op.create_index('ix_subscriptions_end_date_status', ['end_date', 'status'], unique=False)

    # 4. parking_sessions alterations
    with op.batch_alter_table('parking_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('subscription_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_subscribed', sa.Boolean(), server_default='0', nullable=False))
        batch_op.create_foreign_key('fk_parking_sessions_subscription_id', 'subscriptions', ['subscription_id'], ['id'])
        batch_op.create_index('ix_parking_sessions_subscription_id', ['subscription_id'], unique=False)

    # 5. Check constraint on parking_sessions
    op.create_check_constraint(
        "ck_sessions_subscribed_zero_charge",
        "parking_sessions",
        "is_subscribed = FALSE OR amount_charged = 0 OR amount_charged IS NULL"
    )


def downgrade() -> None:
    op.drop_constraint("ck_sessions_subscribed_zero_charge", "parking_sessions", type_="check")

    with op.batch_alter_table('parking_sessions', schema=None) as batch_op:
        batch_op.drop_index('ix_parking_sessions_subscription_id')
        batch_op.drop_constraint('fk_parking_sessions_subscription_id', type_='foreignkey')
        batch_op.drop_column('is_subscribed')
        batch_op.drop_column('subscription_id')

    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.drop_index('ix_subscriptions_end_date_status')
        batch_op.drop_index('ix_subscriptions_card_id_status')
        batch_op.drop_index('ix_subscriptions_subscriber_id_status')
        batch_op.drop_index(batch_op.f('ix_subscriptions_subscriber_id'))
        batch_op.drop_index(batch_op.f('ix_subscriptions_status'))
        batch_op.drop_index(batch_op.f('ix_subscriptions_end_date'))
        batch_op.drop_index(batch_op.f('ix_subscriptions_card_id'))

    op.drop_table('subscriptions')

    with op.batch_alter_table('subscribers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_subscribers_plate_number'))

    op.drop_table('subscribers')

    with op.batch_alter_table('subscription_plans', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_subscription_plans_label'))

    op.drop_table('subscription_plans')
