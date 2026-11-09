"""Replay the integration migration on old snapshots using an isolated database."""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlmodel import SQLModel, create_engine

from app.models.accounts import User
from app.models.conversations import Conversation

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def migration(name):
    spec = importlib.util.spec_from_file_location(name, VERSIONS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_preserves_old_checks_and_adds_owned_research_history():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine, tables=[User.__table__, Conversation.__table__])
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration("0010_comparison").upgrade()
        users = User.__table__
        connection.execute(users.insert(), [
            {"id": 1, "email": "first@example.invalid", "password_hash": "kept"},
            {"id": 2, "email": "second@example.invalid", "password_hash": "kept-too"},
        ])
        connection.execute(Conversation.__table__.insert().values(
            id=1, user_id=1, title="已有研究，请保留", created_at=datetime(2026, 10, 1, tzinfo=UTC),
            updated_at=datetime(2026, 10, 2, tzinfo=UTC),
        ))
        old_table = sa.Table("comparison_record", sa.MetaData(), autoload_with=connection)
        connection.execute(old_table.insert(), [
            {"id": index, "user_id": index, "paper_document_id": 11, "run_document_id": 12,
             "paper_name": "paper.pdf", "run_name": "run.md", "metric": "top-1 error",
             "status": status, "fields": [{"key": "value", "note": "原文摘录与复核保留"}],
             "created_at": datetime(2026, 10, index, tzinfo=UTC)}
            for index, status in [(1, "pending"), (2, "confirmed")]
        ])
        original = connection.execute(sa.select(old_table).order_by(old_table.c.id)).all()
        with Operations.context(context):
            migration("0011_research_comparisons").upgrade()
        assert connection.execute(sa.select(old_table).order_by(old_table.c.id)).all() == original
        new_table = sa.Table("comparison_record", sa.MetaData(), autoload_with=connection)
        rows = connection.execute(sa.select(new_table)).mappings().all()
        assert len({row["conversation_id"] for row in rows}) == 2
        for row in rows:
            history = connection.execute(sa.select(Conversation.__table__).where(
                Conversation.id == row["conversation_id"],
            )).mappings().one()
            assert history["user_id"] == row["user_id"]
            assert history["created_at"] == row["created_at"]
            assert history["title"] == "实验核验：top-1 error"
        assert connection.execute(sa.select(Conversation.title).where(
            Conversation.id == 1,
        )).scalar_one() == "已有研究，请保留"
        with Operations.context(context):
            migration("0011_research_comparisons").downgrade()
        assert connection.execute(sa.select(old_table).order_by(old_table.c.id)).all() == original
        with Operations.context(context):
            migration("0011_research_comparisons").upgrade()
        assert connection.execute(sa.select(old_table).order_by(old_table.c.id)).all() == original
    engine.dispose()
