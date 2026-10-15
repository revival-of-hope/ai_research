"""Create accounts and provider credentials."""

import sqlalchemy as sa

from alembic import op

revision = "0001_accounts"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_account",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_user_account_email"),
    )
    op.create_index("ix_user_account_email", "user_account", ["email"], unique=True)
    op.create_index("ix_user_account_is_active", "user_account", ["is_active"])
    op.create_index("ix_user_account_is_admin", "user_account", ["is_admin"])
    op.create_table(
        "api_provider",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_api_provider_user"),
    )
    op.create_index("ix_api_provider_user_id", "api_provider", ["user_id"])
def downgrade() -> None:
    op.drop_table("api_provider")
    op.drop_table("user_account")
