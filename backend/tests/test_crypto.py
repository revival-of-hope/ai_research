from app.core.crypto import decrypt_secret, encrypt_secret
from app.schemas.auth import RegisterRequest
from app.schemas.provider import ProviderUpsert


def test_secret_round_trip():
    encrypted = encrypt_secret("sk-user-secret")
    assert encrypted != "sk-user-secret"
    assert decrypt_secret(encrypted) == "sk-user-secret"


def test_empty_secret_is_none():
    assert decrypt_secret(None) is None


def test_registration_needs_no_verification_code():
    request = RegisterRequest(email="reader@example.com", password="long-enough-password")
    assert request.model_dump() == {
        "email": "reader@example.com",
        "password": "long-enough-password",
    }


def test_provider_secret_is_trimmed_before_encryption():
    request = ProviderUpsert(
        name="DeepSeek",
        base_url="https://api.deepseek.com",
        model="deepseek-flash",
        api_key="  sk-provider-secret  ",
    )
    assert request.api_key == "sk-provider-secret"
