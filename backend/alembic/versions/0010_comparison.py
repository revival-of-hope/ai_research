"""Add reviewer-confirmed ML/CV comparison snapshots."""

import sqlalchemy as sa

from alembic import op

revision = "0010_comparison"
down_revision = "0009_provider_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comparison_record",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_account.id"), nullable=False),
        sa.Column("paper_document_id", sa.Integer(), nullable=False),
        sa.Column("run_document_id", sa.Integer(), nullable=False),
        sa.Column("paper_name", sa.String(length=255), nullable=False),
        sa.Column("run_name", sa.String(length=255), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=True),
        sa.Column("metric", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_comparison_record_user_id", "comparison_record", ["user_id"])
    op.create_index("ix_comparison_record_created_at", "comparison_record", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_comparison_record_created_at", table_name="comparison_record")
    op.drop_index("ix_comparison_record_user_id", table_name="comparison_record")
    op.drop_table("comparison_record")
