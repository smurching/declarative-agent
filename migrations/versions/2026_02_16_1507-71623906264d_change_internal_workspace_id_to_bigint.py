"""Change internal_workspace_id to BIGINT

Revision ID: 71623906264d
Revises: 001
Create Date: 2026-02-16 15:07:04.450389

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71623906264d'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Change internal_workspace_id and user_id from INTEGER to BIGINT
    op.alter_column('conversations', 'internal_workspace_id',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)
    op.alter_column('conversations', 'user_id',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)


def downgrade() -> None:
    # Revert back to INTEGER (may fail if values exceed int32 range)
    op.alter_column('conversations', 'internal_workspace_id',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=False)
    op.alter_column('conversations', 'user_id',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=False)
