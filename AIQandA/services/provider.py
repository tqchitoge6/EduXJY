"""Helpers for building OpenAI-compatible provider URLs."""

from __future__ import annotations

from django.conf import settings


def endpoint_url(path: str) -> str:
    """Return a provider endpoint URL without duplicating slashes."""
    base = settings.AI_BASE_URL.rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def api_key() -> str:
    """Return the configured API key, if any."""
    return settings.AI_API_KEY.strip()


def has_api_key() -> bool:
    """Whether an API key is configured."""
    return bool(api_key())
