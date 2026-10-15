"""Create research conversations, messages, and searchable documents."""

import sqlalchemy as sa

from alembic import op

revision = "0002_research"
down_revision = "0001_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_conversation_user_id", "conversation", ["user_id"])
    op.create_index("ix_conversation_created_at", "conversation", ["created_at"])
    op.create_index("ix_conversation_updated_at", "conversation", ["updated_at"])
    op.create_table(
        "message",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversation.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_message_conversation_id", "message", ["conversation_id"])
    op.create_index("ix_message_created_at", "message", ["created_at"])
    op.create_index("ix_message_total_tokens", "message", ["total_tokens"])
    op.create_table(
        "source_document",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("stored_path", sa.String(600), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("error_message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_source_document_user_id", "source_document", ["user_id"])
    op.create_index("ix_source_document_status", "source_document", ["status"])
    op.create_index("ix_source_document_created_at", "source_document", ["created_at"])
    op.create_table(
        "document_chunk",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["source_document.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_document_chunk_document_id", "document_chunk", ["document_id"])
    op.create_index("ix_document_chunk_ordinal", "document_chunk", ["ordinal"])
    op.execute(
        "CREATE INDEX ix_document_chunk_fts ON document_chunk "
        "USING gin (to_tsvector('simple', content))"
    )


def downgrade() -> None:
    op.drop_table("document_chunk")
    op.drop_table("source_document")
    op.drop_table("message")
    op.drop_table("conversation")
