import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlmodel import Session, SQLModel, create_engine, select

from app.core import bootstrap
from app.core.config import Settings
from app.core.local_secrets import load_or_create_local_secrets
from app.models.accounts import User


@pytest.fixture
def clean_settings_env(monkeypatch, tmp_path):
    for name in (
        "JWT_SECRET",
        "ENCRYPTION_KEY",
        "ADMIN_EMAIL",
        "ADMIN_PASSWORD",
        "DATABASE_URL",
        "LOCAL_SECRETS_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_defaults_start_without_env_and_keep_generated_keys(clean_settings_env):
    first = Settings(_env_file=None)
    persisted = Path("data/local-secrets.json").read_bytes()
    second = Settings(_env_file=None)

    assert first.admin_email == "admin@example.com"
    assert first.admin_password == "administrator-password"
    assert first.database_url == "postgresql+psycopg://research:research@postgres:5432/research"
    assert len(first.jwt_secret) >= 48
    cipher = Fernet(first.encryption_key.encode())
    token = cipher.encrypt(b"preserved provider credential")
    assert Fernet(second.encryption_key.encode()).decrypt(token) == b"preserved provider credential"
    assert first.jwt_secret == second.jwt_secret
    assert Path("data/local-secrets.json").read_bytes() == persisted
    assert first.jwt_secret not in repr(first)
    assert first.encryption_key not in repr(first)
    assert first.admin_password not in repr(first)
    if os.name != "nt":
        assert Path("data/local-secrets.json").stat().st_mode & 0o777 == 0o600


def test_explicit_env_secrets_take_precedence_and_do_not_require_writable_storage(
    clean_settings_env, monkeypatch
):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("JWT_SECRET", "existing-deployment-jwt")
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    # An invalid existing file must be irrelevant when both explicit keys are supplied.
    path = clean_settings_env / "local-secrets.json"
    path.write_text("invalid existing contents", encoding="utf-8")

    settings = Settings(_env_file=None, local_secrets_file=path)

    assert settings.jwt_secret == "existing-deployment-jwt"
    assert settings.encryption_key == key
    assert path.read_text(encoding="utf-8") == "invalid existing contents"


def test_env_file_secrets_remain_compatible(clean_settings_env):
    key = Fernet.generate_key().decode()
    env_file = clean_settings_env / ".env"
    env_file.write_text(
        f"JWT_SECRET=legacy-jwt\nENCRYPTION_KEY={key}\nADMIN_PASSWORD=legacy-password\n",
        encoding="utf-8",
    )

    settings = Settings()

    assert settings.jwt_secret == "legacy-jwt"
    assert settings.encryption_key == key
    assert settings.admin_password == "legacy-password"
    assert not Path("data/local-secrets.json").exists()


def test_default_admin_startup_preserves_an_existing_password(clean_settings_env, monkeypatch):
    settings = Settings(_env_file=None)
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(bootstrap, "engine", engine)
    monkeypatch.setattr(bootstrap, "settings", settings)
    try:
        with Session(engine) as session:
            session.add(
                User(
                    email=str(settings.admin_email),
                    password_hash="existing-password-hash",
                    is_admin=False,
                    is_active=False,
                )
            )
            session.commit()

        bootstrap.ensure_admin()
        bootstrap.ensure_admin()

        with Session(engine) as session:
            users = session.exec(select(User)).all()
            assert len(users) == 1
            assert users[0].password_hash == "existing-password-hash"
            assert users[0].is_admin and users[0].is_active
    finally:
        engine.dispose()


@pytest.mark.parametrize("explicit", ["JWT_SECRET", "ENCRYPTION_KEY"])
def test_one_explicit_secret_does_not_replace_it_with_generated_value(
    clean_settings_env, monkeypatch, explicit
):
    value = "existing-jwt" if explicit == "JWT_SECRET" else Fernet.generate_key().decode()
    monkeypatch.setenv(explicit, value)

    first = Settings(_env_file=None)
    second = Settings(_env_file=None)

    assert getattr(first, explicit.lower()) == value
    assert first.jwt_secret == second.jwt_secret
    assert first.encryption_key == second.encryption_key


def test_concurrent_initialization_uses_one_complete_secret_file(clean_settings_env):
    path = clean_settings_env / "concurrent" / "secrets.json"

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(lambda _: load_or_create_local_secrets(path), range(48)))

    assert all(result == results[0] for result in results)
    assert json.loads(path.read_text(encoding="utf-8")) == results[0]
    assert set(path.parent.iterdir()) == {path, Path(str(path) + ".lock")}


def _settings_fingerprint_in_subprocess(path, directory):
    backend = Path(__file__).resolve().parents[1]
    environment = dict(os.environ, LOCAL_SECRETS_FILE=str(path), PYTHONPATH=str(backend))

    restarted = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import hashlib; from app.core.config import settings; "
                "print(hashlib.sha256((settings.jwt_secret + settings.encryption_key).encode())"
                ".hexdigest())"
            ),
        ],
        env=environment,
        cwd=directory,
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    return restarted.stdout.strip()


def test_restart_in_another_process_reads_the_persisted_secrets(clean_settings_env):
    path = clean_settings_env / "restart" / "secrets.json"
    settings = Settings(_env_file=None, local_secrets_file=path)
    expected = hashlib.sha256((settings.jwt_secret + settings.encryption_key).encode()).hexdigest()

    assert _settings_fingerprint_in_subprocess(path, clean_settings_env) == expected


def test_concurrent_processes_create_and_share_the_same_secrets(clean_settings_env):
    path = clean_settings_env / "processes" / "secrets.json"

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(
            executor.map(
                lambda _: _settings_fingerprint_in_subprocess(path, clean_settings_env), range(6)
            )
        )

    assert len(set(results)) == 1
    assert len(results[0]) == 64


@pytest.mark.parametrize(
    "contents",
    [
        "partial-json{",
        "[]",
        "{}",
        '{"jwt_secret":"too-short","encryption_key":"invalid"}',
        json.dumps({"jwt_secret": "a" * 64, "encryption_key": "invalid"}),
    ],
)
def test_corrupt_secret_file_fails_without_silent_key_rotation(clean_settings_env, contents):
    path = clean_settings_env / "secrets.json"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(RuntimeError, match="Restore the original file"):
        Settings(_env_file=None, local_secrets_file=path)

    assert path.read_text(encoding="utf-8") == contents
