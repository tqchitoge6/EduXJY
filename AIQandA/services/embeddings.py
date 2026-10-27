"""Optional embedding client used to upgrade lexical retrieval."""

from __future__ import annotations

import logging

import requests
from django.conf import settings

from .provider import api_key, endpoint_url, has_api_key

logger = logging.getLogger(__name__)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return embeddings for texts, or an empty list when unavailable.

    Embeddings are an optional enhancement. A failure must never prevent a
    document from being searchable by the lexical retriever.
    """
    if not texts or not has_api_key() or not settings.AI_EMBEDDING_MODEL:
        return []
    try:
        response = requests.post(
            endpoint_url("embeddings"),
            headers={
                "Authorization": f"Bearer {api_key()}",
                "Content-Type": "application/json",
            },
            json={"model": settings.AI_EMBEDDING_MODEL, "input": texts},
            timeout=settings.AI_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        items = sorted(payload["data"], key=lambda item: item["index"])
        vectors = [item["embedding"] for item in items]
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        logger.warning("Embedding request failed; using lexical retrieval: %s", exc)
        return []
    if len(vectors) != len(texts):
        logger.warning("Embedding response length did not match input length")
        return []
    return vectors


def embed_query(text: str) -> list[float] | None:
    """Embed one query string, returning None when unavailable."""
    vectors = embed_texts([text])
    return vectors[0] if vectors else None
