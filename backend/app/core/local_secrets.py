"""Generate development secrets once and preserve them across application restarts."""

import json
import os
import secrets
import tempfile
from contextlib import contextmanager
from pathlib import Path
from threading import Lock

from cryptography.fernet import Fernet

if os.name == "nt":
    import msvcrt
else:
    import fcntl


_thread_lock = Lock()


@contextmanager
def _creation_lock(path: Path):
    # Retain the lock file so every process locks the same inode/handle.
    descriptor = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, "r+b") as lock_file:
        if os.name == "nt":
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _read_secrets(path: Path) -> dict[str, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TypeError("Expected a secrets object")
        jwt_secret = value["jwt_secret"]
        encryption_key = value["encryption_key"]
        if not isinstance(jwt_secret, str) or len(jwt_secret) < 32:
            raise ValueError("Invalid JWT secret")
        if not isinstance(encryption_key, str):
            raise TypeError("Invalid encryption key")
        Fernet(encryption_key.encode())
        return {"jwt_secret": jwt_secret, "encryption_key": encryption_key}
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RuntimeError(
            f"Cannot read local secrets at {path}. Restore the original file or configure "
            "JWT_SECRET and ENCRYPTION_KEY; replacing keys would invalidate stored credentials."
        ) from error


def load_or_create_local_secrets(path: Path) -> dict[str, str]:
    """Atomically publish a complete file; concurrent workers use the same winning keys.

    Files have owner-only permissions on POSIX; Windows inherits directory ACLs.
    Locks serialize first-time creation across processes; atomic rename means
    readers only see a complete file. An existing file is never overwritten,
    including when it is invalid or unreadable. Process exit releases kernel locks.
    """
    if os.path.lexists(path):
        return _read_secrets(path)

    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with _thread_lock, _creation_lock(path):
        if os.path.lexists(path):
            return _read_secrets(path)
        generated = {
            "jwt_secret": secrets.token_urlsafe(48),
            "encryption_key": Fernet.generate_key().decode(),
        }
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as target:
                json.dump(generated, target)
                target.write("\n")
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, path)
            if os.name != "nt":
                # Persist the directory entry before callers store encrypted data.
                directory = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return _read_secrets(path)
