"""Tests for the optional embedding client."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
import requests

from AIQandA.services.embeddings import embed_query, embed_texts

pytestmark = pytest.mark.django_db


def test_embedding_is_disabled_without_key(settings) -> None:
    settings.AI_API_KEY = ""
    settings.AI_EMBEDDING_MODEL = "embedding-model"
    assert embed_texts(["文本"]) == []
    assert embed_query("文本") is None


def test_embedding_is_disabled_without_model(settings) -> None:
    settings.AI_API_KEY = "key"
    settings.AI_EMBEDDING_MODEL = ""
    assert embed_texts(["文本"]) == []


def test_embedding_success(settings) -> None:
    settings.AI_API_KEY = "key"
    settings.AI_EMBEDDING_MODEL = "embedding-model"
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "data": [
            {"index": 1, "embedding": [0.0, 1.0]},
            {"index": 0, "embedding": [1.0, 0.0]},
        ]
    }
    with patch("AIQandA.services.embeddings.requests.post", return_value=response):
        vectors = embed_texts(["第一段", "第二段"])
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]


def test_embedding_provider_error_returns_empty(settings) -> None:
    settings.AI_API_KEY = "key"
    settings.AI_EMBEDDING_MODEL = "embedding-model"
    with patch(
        "AIQandA.services.embeddings.requests.post",
        side_effect=requests.ConnectionError("down"),
    ):
        assert embed_texts(["文本"]) == []


def test_embedding_shape_mismatch_returns_empty(settings) -> None:
    settings.AI_API_KEY = "key"
    settings.AI_EMBEDDING_MODEL = "embedding-model"
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"data": [{"index": 0, "embedding": [1.0]}]}
    with patch("AIQandA.services.embeddings.requests.post", return_value=response):
        assert embed_texts(["第一段", "第二段"]) == []
