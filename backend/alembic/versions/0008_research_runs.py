"""Persist observable multi-agent runs without replacing existing chat data."""

import sqlalchemy as sa

from alembic import op

revision = "0008_research_runs"
down_revision = "0007_responses_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("sources", "events"):
        op.add_column("message", sa.Column(name, sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("message", sa.Column("usage", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("message", sa.Column("run_id", sa.String(36), nullable=True))
    op.add_column(
        "message", sa.Column("status", sa.String(20), nullable=False, server_default="completed")
    )
    op.create_index("ix_message_run_id", "message", ["run_id"])
    op.create_table(
        "research_run",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id", sa.Integer(), sa.ForeignKey("conversation.id"), nullable=False
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_account.id"), nullable=False),
        sa.Column(
            "provider_id",
            sa.Integer(),
            sa.ForeignKey("api_provider.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider_name", sa.String(80), nullable=True),
        sa.Column("model", sa.String(120), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    for name in ("conversation_id", "user_id", "provider_id", "status", "created_at"):
        op.create_index(f"ix_research_run_{name}", "research_run", [name])


def downgrade() -> None:
    op.drop_table("research_run")
    op.drop_index("ix_message_run_id", table_name="message")
    for name in ("status", "run_id", "usage", "events", "sources"):
        op.drop_column("message", name)
