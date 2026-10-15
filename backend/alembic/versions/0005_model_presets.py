"""Support multiple model presets and per-preset usage."""

import sqlalchemy as sa

from alembic import op

revision = "0005_model_presets"
down_revision = "0004_remove_legacy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE api_provider DROP CONSTRAINT IF EXISTS uq_api_provider_user")
    op.add_column(
        "api_provider",
        sa.Column("api_mode", sa.String(30), nullable=False, server_default="responses"),
    )
    op.add_column("message", sa.Column("provider_id", sa.Integer(), nullable=True))
    op.add_column("message", sa.Column("provider_name", sa.String(80), nullable=True))
    op.add_column("message", sa.Column("model", sa.String(120), nullable=True))
    op.create_index("ix_message_provider_id", "message", ["provider_id"])
    op.create_foreign_key(
        "fk_message_provider_id",
        "message",
        "api_provider",
        ["provider_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_message_provider_id", "message", type_="foreignkey")
    op.drop_index("ix_message_provider_id", table_name="message")
    op.drop_column("message", "model")
    op.drop_column("message", "provider_name")
    op.drop_column("message", "provider_id")
    op.drop_column("api_provider", "api_mode")
    op.create_unique_constraint("uq_api_provider_user", "api_provider", ["user_id"])
