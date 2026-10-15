"""Persist streamed reasoning summaries."""

import sqlalchemy as sa

from alembic import op

revision = "0006_streaming_thinking"
down_revision = "0005_model_presets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("message", sa.Column("thinking", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("message", "thinking")
