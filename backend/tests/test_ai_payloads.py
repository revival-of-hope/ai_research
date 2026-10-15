"""Validate user-configured Responses endpoints without a guessed model catalog."""

import pytest

from app.core.endpoints import validate_provider_url, validate_responses_model
from app.domain.workspace import InvalidInput


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/v1",
        "http://127.0.0.1/v1",
        "http://[::1]/v1",
        "https://api.local/v1",
        "file:///secret",
        "https://key:secret@example.com/v1",
        "https://example.com/v1?api_key=secret",
        "https://example.com/v1/responses",
    ],
)
def test_rejects_invalid_or_private_provider_endpoint(url):
    with pytest.raises(InvalidInput):
        validate_provider_url(url)


def test_accepts_user_selected_models_without_false_compatibility_claims():
    validate_responses_model("https://api.openai.com/v1", "user-selected-model")
    assert validate_provider_url("https://example.com/v1/") == "https://example.com/v1"
    with pytest.raises(InvalidInput):
        validate_responses_model("https://example.com/v1", " ")
