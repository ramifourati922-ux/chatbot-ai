"""agents : comptes conseillers du tableau de bord /admin

Revision ID: b7d2e4f19a3c
Revises: 457f5fafa798
Create Date: 2026-09-29 01:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7d2e4f19a3c'
down_revision: Union[str, None] = '457f5fafa798'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'agents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('password_hash', sa.String(length=100), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_agents_username'), 'agents', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_agents_username'), table_name='agents')
    op.drop_table('agents')
