"""Opt-in migration checks against an explicitly supplied empty PostgreSQL test DB.

Never reads DATABASE_URL and never drops existing user schemas. Every object this
test creates lives in a unique temporary schema, removed in the finalizer.
"""

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic.config import Config
from cryptography.fernet import Fernet
from psycopg import sql
from sqlalchemy.engine import make_url

from alembic import command

TEST_URL = os.environ.get("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not TEST_URL, reason="Set TEST_POSTGRES_URL to an empty test DB")
BACKEND = Path(__file__).resolve().parents[1]
LEGACY_TABLES = (
    "user_account",
    "api_provider",
    "conversation",
    "message",
    "source_document",
    "document_chunk",
)


def test_legacy_upgrade_downgrade_and_reupgrade_preserve_data(monkeypatch):
    from app.core.config import settings

    url = make_url(TEST_URL)
    assert url.get_backend_name() == "postgresql", "A PostgreSQL test URL is required"
    connect_url = url.set(drivername="postgresql").render_as_string(hide_password=False)
    schema = "ai_research_migration_" + uuid4().hex
    key = Fernet.generate_key()
    encrypted = Fernet(key).encrypt(b"migration-test-secret").decode()
    with psycopg.connect(connect_url, autocommit=True, connect_timeout=5) as connection:
        occupied = connection.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema NOT IN ('pg_catalog', 'information_schema')"
        ).fetchall()
        assert not occupied, "Refusing a nonempty DB; provide a dedicated empty test database"
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            migration_url = url.set(
                drivername="postgresql+psycopg",
                query={key: value for key, value in url.query.items() if key != "options"},
            ).render_as_string(hide_password=False)
            monkeypatch.setattr(settings, "database_url", migration_url)
            monkeypatch.setenv("PGOPTIONS", "-csearch_path=" + schema)

            def migrate(direction, revision):
                config = Config(str(BACKEND / "alembic.ini"))
                config.set_main_option("script_location", str(BACKEND / "alembic"))
                getattr(command, direction)(config, revision)

            def columns(table):
                return [
                    row[0]
                    for row in connection.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",
                        (schema, table),
                    )
                ]

            migrate("upgrade", "0007_responses_only")
            user_id = connection.execute(
                "INSERT INTO user_account (email,password_hash,is_active,is_admin,created_at) "
                "VALUES ('legacy@example.com','legacy-hash',true,true,now()) RETURNING id"
            ).fetchone()[0]
            provider_ids = []
            for number in (1, 2):
                provider_ids.append(
                    connection.execute(
                        "INSERT INTO api_provider "
                        "(user_id,name,base_url,model,api_key_encrypted,updated_at) "
                        "VALUES (%s,%s,'https://models.example.com/v1','legacy-model',%s,now()) "
                        "RETURNING id",
                        (user_id, f"Legacy preset {number}", encrypted),
                    ).fetchone()[0]
                )
            conversation_id = connection.execute(
                "INSERT INTO conversation (user_id,title,created_at,updated_at) "
                "VALUES (%s,'旧研究 conversation',now(),now()) RETURNING id",
                (user_id,),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO message "
                "(conversation_id,role,content,thinking,provider_id,provider_name,model,"
                "input_tokens,output_tokens,total_tokens,created_at) "
                "VALUES (%s,'assistant','旧结论 preserved','legacy thinking',%s,"
                "'Legacy preset 1','legacy-model',17,23,40,now())",
                (conversation_id, provider_ids[0]),
            )
            document_id = connection.execute(
                "INSERT INTO source_document "
                "(user_id,filename,media_type,size_bytes,stored_path,status,created_at) "
                "VALUES (%s,'论文.txt','text/plain',42,'/data/uploads/legacy.txt','ready',now()) "
                "RETURNING id",
                (user_id,),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO document_chunk (document_id,ordinal,content) VALUES (%s,0,%s)",
                (document_id, "旧资料中的 transformer evidence"),
            )
            old_columns = {table: columns(table) for table in LEGACY_TABLES}

            def snapshot():
                return {
                    table: connection.execute(
                        sql.SQL("SELECT {} FROM {} ORDER BY id").format(
                            sql.SQL(",").join(map(sql.Identifier, old_columns[table])),
                            sql.Identifier(table),
                        )
                    ).fetchall()
                    for table in LEGACY_TABLES
                }

            original = snapshot()

            def verify_legacy():
                assert snapshot() == original
                ciphertext = connection.execute(
                    "SELECT api_key_encrypted FROM api_provider WHERE id=%s",
                    (provider_ids[0],),
                ).fetchone()[0]
                assert Fernet(key).decrypt(ciphertext.encode()) == b"migration-test-secret"
                assert connection.execute(
                    "SELECT indexdef FROM pg_indexes WHERE schemaname=%s "
                    "AND indexname='ix_document_chunk_fts'",
                    (schema,),
                ).fetchone(), "Legacy PostgreSQL full-text index must remain present"

            def verify_new_defaults():
                assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
                    "0008_research_runs",
                )
                assert connection.execute(
                    "SELECT sources,events,usage,run_id,status FROM message"
                ).fetchone() == ([], [], {}, None, "completed")
                assert {"provider_name", "model", "sources", "events", "usage"} <= set(
                    columns("research_run")
                )

            migrate("upgrade", "head")
            verify_legacy()
            verify_new_defaults()
            # Exercise real PostgreSQL SET NULL behavior without deleting a legacy preset.
            disposable_id = connection.execute(
                "INSERT INTO api_provider "
                "(user_id,name,base_url,model,api_key_encrypted,updated_at) "
                "VALUES (%s,'Disposable','https://models.example.com/v1','model',%s,now()) "
                "RETURNING id",
                (user_id, encrypted),
            ).fetchone()[0]
            run_id = str(uuid4())
            connection.execute(
                "INSERT INTO research_run "
                "(id,conversation_id,user_id,provider_id,provider_name,model,status,mode,question,"
                "sources,events,usage,created_at) "
                "VALUES (%s,%s,%s,%s,'Disposable','model','running','deep','FK check',"
                "'[]'::json,'[]'::json,'{}'::json,now())",
                (run_id, conversation_id, user_id, disposable_id),
            )
            connection.execute("DELETE FROM api_provider WHERE id=%s", (disposable_id,))
            assert connection.execute(
                "SELECT provider_id FROM research_run WHERE id=%s",
                (run_id,),
            ).fetchone() == (None,)
            connection.execute("DELETE FROM research_run WHERE id=%s", (run_id,))
            verify_legacy()

            migrate("downgrade", "0007_responses_only")
            verify_legacy()
            assert not columns("research_run")
            assert not {"sources", "events", "usage", "run_id", "status"} & set(columns("message"))
            migrate("upgrade", "head")
            verify_legacy()
            verify_new_defaults()
        finally:
            connection.execute("SET search_path TO pg_catalog")
            # The exact generated schema was created above; existing schemas are untouched.
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
