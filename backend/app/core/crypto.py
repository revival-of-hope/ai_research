from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _cipher() -> Fernet:
    # Recreate cheaply so tests can replace settings without module reloads.
    return Fernet(settings.encryption_key.encode())


def encrypt_secret(value: str) -> str:
    return _cipher().encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _cipher().decrypt(value.encode()).decode()
    except InvalidToken as error:
        raise ValueError("Stored credential cannot be decrypted") from error
