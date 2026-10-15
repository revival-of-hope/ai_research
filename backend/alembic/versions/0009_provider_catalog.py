"""Remember provider selections, preserving all existing Responses presets."""

import sqlalchemy as sa

from alembic import op

revision = "0009_provider_catalog"
down_revision = "0008_research_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_provider",
        sa.Column("provider_type", sa.String(30), nullable=False, server_default="custom"),
    )


def downgrade() -> None:
    op.drop_column("api_provider", "provider_type")
