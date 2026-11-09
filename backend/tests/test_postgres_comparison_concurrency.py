"""PostgreSQL check for serializing edits against confirmation."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import psycopg
import pytest
from alembic.config import Config
from psycopg import sql
from sqlalchemy.engine import make_url
from sqlmodel import Session, create_engine

from alembic import command
from app.application.service.comparison import ComparisonService
from app.core.config import settings
from app.domain.comparison import (
    ComparisonConflict,
    Evidence,
    build_fields,
    confirm_fields,
    field_dicts,
    read_fields,
)
from app.domain.research import ProviderConfig
from app.infrastructure.uow.comparison import SqlComparisonUnitOfWork
from app.models.accounts import User
from app.models.comparison import ComparisonRecord
from app.models.conversations import Conversation

TEST_URL = os.environ.get("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not TEST_URL, reason="Set TEST_POSTGRES_URL to a dedicated test DB")
BACKEND = Path(__file__).resolve().parents[1]


def test_stale_field_edit_cannot_overwrite_a_committed_confirmation(monkeypatch):
    url = make_url(TEST_URL)
    assert url.get_backend_name() == "postgresql", "A PostgreSQL test URL is required"
    connect_url = url.set(drivername="postgresql").render_as_string(hide_password=False)
    schema = "ai_research_comparison_" + uuid4().hex
    allow_confirmation_commit = Event()

    with psycopg.connect(connect_url, autocommit=True, connect_timeout=5) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        engine = None
        try:
            connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            migration_url = url.set(
                drivername="postgresql+psycopg",
                query={key: value for key, value in url.query.items() if key != "options"},
            ).render_as_string(hide_password=False)
            monkeypatch.setattr(settings, "database_url", migration_url)
            monkeypatch.setenv("PGOPTIONS", "-csearch_path=" + schema)
            config = Config(str(BACKEND / "alembic.ini"))
            config.set_main_option("script_location", str(BACKEND / "alembic"))
            command.upgrade(config, "head")

            engine = create_engine(
                migration_url,
                connect_args={"application_name": "uc08_comparison_lock_test"},
            )
            with Session(engine) as session:
                user = User(
                    email=f"uc08-lock-{uuid4().hex}@example.invalid",
                    password_hash="test-only",
                    is_active=True,
                    is_admin=False,
                )
                session.add(user)
                session.flush()
                conversation = Conversation(user_id=user.id, title="实验核验")
                session.add(conversation)
                session.flush()
                fields = field_dicts(build_fields(
                    {"dataset": Evidence("ImageNet", "Dataset ImageNet", 1)},
                    {"dataset": Evidence("ImageNet", "Dataset ImageNet", 2)},
                ))
                record = ComparisonRecord(
                    user_id=user.id,
                    conversation_id=conversation.id,
                    paper_document_id=1,
                    run_document_id=2,
                    paper_name="paper",
                    run_name="run",
                    provider_id=None,
                    metric="top-1 error",
                    fields=fields,
                )
                session.add(record)
                session.commit()
                user_id, record_id = user.id, record.id

            locked = Event()
            late_request_started = Event()

            async def unused_extractor(
                _provider: ProviderConfig, _document: dict, _metric: str,
            ):
                raise AssertionError("The update path must not call the extractor")

            def uow_factory():
                return SqlComparisonUnitOfWork(Session(engine), owns_session=True)

            service = ComparisonService(uow_factory, unused_extractor)

            def confirm_first_request():
                with uow_factory() as uow:
                    record_data = uow.comparisons.get_for_update(user_id, record_id)
                    reviewed = read_fields(record_data["fields"])
                    for field in reviewed:
                        field.review_status = (
                            "unresolved" if field.status == "unknown" else "confirmed"
                        )
                    confirm_fields(reviewed)
                    uow.comparisons.update(
                        user_id, record_id, field_dicts(reviewed), "confirmed",
                    )
                    locked.set()
                    if not allow_confirmation_commit.wait(timeout=10):
                        raise TimeoutError("confirmation test gate timed out")
                    uow.commit()

            def send_late_edit():
                late_request_started.set()
                return service.update(user_id, record_id, [{
                    "key": "dataset",
                    "paper_value": "ImageNet",
                    "run_value": "ImageNet",
                    "review_status": "confirmed",
                    "note": "late edit",
                }], False)

            try:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    confirmation = executor.submit(confirm_first_request)
                    assert locked.wait(timeout=5), "confirmation did not acquire the row lock"
                    late_edit = executor.submit(send_late_edit)
                    assert late_request_started.wait(timeout=5)
                    deadline = time.monotonic() + 5
                    waiting_on_row = False
                    while time.monotonic() < deadline:
                        waiting_on_row = connection.execute(
                            "SELECT 1 FROM pg_stat_activity "
                            "WHERE datname=current_database() "
                            "AND application_name='uc08_comparison_lock_test' "
                            "AND wait_event_type='Lock' LIMIT 1"
                        ).fetchone() is not None
                        if waiting_on_row or late_edit.done():
                            break
                        time.sleep(0.02)
                    allow_confirmation_commit.set()
                    confirmation.result(timeout=5)
                    assert waiting_on_row, "the concurrent edit did not wait for confirmation"
                    with pytest.raises(ComparisonConflict):
                        late_edit.result(timeout=5)
            finally:
                allow_confirmation_commit.set()

            with Session(engine) as session:
                saved = session.get(ComparisonRecord, record_id)
                assert saved is not None
                assert saved.status == "confirmed"
                assert all(field["review_status"] != "pending" for field in saved.fields)
        finally:
            if engine is not None:
                engine.dispose()
            connection.execute("SET search_path TO pg_catalog")
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
