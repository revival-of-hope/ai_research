"""Integrate existing experiment checks into research history without losing snapshots."""

import sqlalchemy as sa

from alembic import op

revision = "0011_research_comparisons"
down_revision = "0010_comparison"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("comparison_record", sa.Column("conversation_id", sa.Integer(), nullable=True))
    bind = op.get_bind()
    records = sa.table(
        "comparison_record", sa.column("id", sa.Integer()), sa.column("user_id", sa.Integer()),
        sa.column("metric", sa.String()), sa.column("created_at", sa.DateTime()),
        sa.column("conversation_id", sa.Integer()),
    )
    conversations = sa.table(
        "conversation", sa.column("id", sa.Integer()), sa.column("user_id", sa.Integer()),
        sa.column("title", sa.String()), sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    for row in bind.execute(sa.select(records)).mappings().all():
        conversation_id = bind.execute(
            conversations.insert().values(
                user_id=row["user_id"], title=f"实验核验：{row['metric']}"[:160],
                created_at=row["created_at"], updated_at=row["created_at"],
            ).returning(conversations.c.id)
        ).scalar_one()
        bind.execute(
            records.update().where(records.c.id == row["id"])
            .values(conversation_id=conversation_id)
        )
    with op.batch_alter_table("comparison_record") as batch:
        batch.alter_column("conversation_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            "fk_comparison_record_conversation_id", "conversation", ["conversation_id"], ["id"],
        )
        batch.create_index("ix_comparison_record_conversation_id", ["conversation_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("comparison_record") as batch:
        batch.drop_index("ix_comparison_record_conversation_id")
        batch.drop_constraint("fk_comparison_record_conversation_id", type_="foreignkey")
        batch.drop_column("conversation_id")
    # Keep conversation titles/history metadata rather than deleting user-renamed records.
