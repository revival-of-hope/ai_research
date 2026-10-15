"""Use the Responses API exclusively."""

from alembic import op

revision = "0007_responses_only"
down_revision = "0006_streaming_thinking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("api_provider", "api_mode")


def downgrade() -> None:
    import sqlalchemy as sa

    op.add_column(
        "api_provider",
        sa.Column("api_mode", sa.String(30), nullable=False, server_default="responses"),
    )
