"""Tests for lexical and embedding retrieval helpers."""

from __future__ import annotations

import pytest

from AIQandA.models import Conversation, Message
from AIQandA.services.retrieval import (
    build_retrieval_query,
    embedding_similarity,
    lexical_similarity,
    retrieve_chunks,
    tokenize,
)

pytestmark = pytest.mark.django_db


def test_tokenize_chinese_and_english() -> None:
    tokens = tokenize("监督 learning 模型")
    assert "监督" in tokens
    assert "learning" in tokens
    assert "模型" in tokens


def test_lexical_similarity_prefers_relevant_text() -> None:
    query = tokenize("监督学习需要标签")
    relevant = lexical_similarity(query, "监督学习使用带标签的数据训练模型。")
    irrelevant = lexical_similarity(query, "今天食堂的午饭很好吃。")
    assert relevant > irrelevant


def test_embedding_similarity() -> None:
    assert embedding_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert embedding_similarity([1, 0], [0, 1]) == 0.0
    assert embedding_similarity([1, 0], [1, 0, 1]) == 0.0


def test_retrieve_chunks_returns_relevant_document(document, course) -> None:
    results = retrieve_chunks(course.id, "监督学习和无监督学习有什么区别？")
    assert results
    assert results[0].chunk.document.title == "机器学习基础"
    assert results[0].score > 0


def test_retrieve_chunks_handles_empty_query(course) -> None:
    assert retrieve_chunks(course.id, "   ") == []


def test_build_retrieval_query_adds_previous_question(student, course) -> None:
    conversation = Conversation.objects.create(user=student, course=course)
    previous = Message.objects.create(
        conversation=conversation,
        role=Message.Role.USER,
        content="监督学习是什么？",
    )
    query = build_retrieval_query("它有什么例子？", [previous])
    assert "监督学习是什么" in query
    assert "它有什么例子" in query
