"""Remove the retired verification and external tool tables."""

from alembic import op

revision = "0004_remove_legacy"
down_revision = "0003_email_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS email_verification CASCADE")
    op.execute("DROP TABLE IF EXISTS mcp_server CASCADE")


def downgrade() -> None:
    # Retired integration data cannot be reconstructed safely.
    pass
