"""Responses request settings shared by connectivity checks and research."""


def responses_settings() -> dict:
    """Use the same medium reasoning default for every conversation mode."""
    return {"openai_store": False, "openai_reasoning_effort": "medium"}
