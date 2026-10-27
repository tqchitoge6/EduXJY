"""Tests for LLM generation and its fallback behavior."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
import requests

from AIQandA.models import Message
from AIQandA.services.llm import generate_answer
from AIQandA.services.retrieval import RetrievedChunk

pytestmark = pytest.mark.django_db


def make_chunk(document) -> RetrievedChunk:
    return RetrievedChunk(chunk=document.chunks.first(), score=0.8)


def test_no_chunks_returns_grounded_refusal(course) -> None:
    result = generate_answer(course.title, "未知问题", [], [])
    assert result.mode == Message.Mode.FALLBACK
    assert "暂未找到" in result.text


def test_missing_api_key_returns_retrieval_fallback(course, document) -> None:
    result = generate_answer(course.title, "什么是过拟合？", [make_chunk(document)], [])
    assert result.mode == Message.Mode.FALLBACK
    assert "未配置在线模型" in result.text


def test_successful_llm_call(course, document, settings) -> None:
    settings.AI_API_KEY = "test-key"
    settings.AI_MODEL = "test-model"
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "model": "test-model",
        "choices": [{"message": {"content": "这是模型回答 [1]。"}}],
    }
    with patch("AIQandA.services.llm.requests.post", return_value=response) as post:
        result = generate_answer(course.title, "什么是过拟合？", [make_chunk(document)], [])

    assert result.mode == Message.Mode.AI
    assert result.text == "这是模型回答 [1]。"
    assert result.model_name == "test-model"
    assert post.call_args.kwargs["timeout"] > 0
    assert "课程资料" in post.call_args.kwargs["json"]["messages"][0]["content"]


def test_provider_error_falls_back(course, document, settings) -> None:
    settings.AI_API_KEY = "test-key"
    with patch(
        "AIQandA.services.llm.requests.post",
        side_effect=requests.ConnectionError("network down"),
    ):
        result = generate_answer(course.title, "什么是过拟合？", [make_chunk(document)], [])

    assert result.mode == Message.Mode.FALLBACK
    assert "暂时不可用" in result.text


def test_empty_completion_falls_back(course, document, settings) -> None:
    settings.AI_API_KEY = "test-key"
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"choices": [{"message": {"content": "   "}}]}
    with patch("AIQandA.services.llm.requests.post", return_value=response):
        result = generate_answer(course.title, "问题", [make_chunk(document)], [])
    assert result.mode == Message.Mode.FALLBACK
