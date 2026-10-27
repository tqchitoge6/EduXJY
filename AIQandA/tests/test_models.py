"""Tests for the AIQandA data model."""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from AIQandA.models import (
    AnswerFeedback,
    Citation,
    Conversation,
    Course,
    DocumentChunk,
    Message,
)

pytestmark = pytest.mark.django_db


def test_course_string(course) -> None:
    assert str(course) == "TEST101 测试课程"


def test_document_and_chunk_strings(document) -> None:
    chunk = document.chunks.first()
    assert str(document) == "机器学习基础 (已就绪)"
    assert str(chunk).startswith("机器学习基础 #0")


def test_conversation_and_message_strings(student, course) -> None:
    conversation = Conversation.objects.create(user=student, course=course, title="测试对话")
    message = Message.objects.create(
        conversation=conversation,
        role=Message.Role.USER,
        content="这是一个问题",
    )
    assert str(conversation) == "测试对话"
    assert str(message).startswith("学生: 这是一个问题")


def test_chunk_index_is_unique(document) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        DocumentChunk.objects.create(
            document=document,
            chunk_index=0,
            content="重复片段",
            char_count=4,
        )


def test_citation_rank_is_unique(document, student, course) -> None:
    conversation = Conversation.objects.create(user=student, course=course)
    message = Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content="回答",
    )
    chunk = document.chunks.first()
    Citation.objects.create(message=message, chunk=chunk, rank=1, quote="a")
    with pytest.raises(IntegrityError), transaction.atomic():
        Citation.objects.create(
            message=message,
            chunk=document.chunks.last(),
            rank=1,
            quote="b",
        )


def test_feedback_one_to_one(document, student, course) -> None:
    conversation = Conversation.objects.create(user=student, course=course)
    message = Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content="回答",
    )
    AnswerFeedback.objects.create(message=message, user=student, rating="up")
    with pytest.raises(IntegrityError), transaction.atomic():
        AnswerFeedback.objects.create(message=message, user=student, rating="down")


def test_course_code_unique(course) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Course.objects.create(code=course.code, title="另一门课")
