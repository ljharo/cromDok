"""runner dependencies (per-runner install manifest, cached by DockerExecutor)

Revision ID: 14647ed74b75
Revises: 5e8a2c4f91bd
Create Date: 2026-07-25 19:58:15.787657

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "14647ed74b75"
down_revision: Union[str, Sequence[str], None] = "5e8a2c4f91bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("runners", sa.Column("dependencies", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("runners", "dependencies")
