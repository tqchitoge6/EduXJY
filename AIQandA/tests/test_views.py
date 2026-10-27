"""HTTP-level tests for the chat, upload, feedback, and health endpoints."""

from __future__ import annotations

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from AIQandA.models import (
    AnswerFeedback,
    Citation,
    Conversation,
    Course,
    DocumentChunk,
    KnowledgeDocument,
    Message,
)

pytestmark = pytest.mark.django_db


def ask(client, course_id: int, question: str, conversation_id: int | None = None):
    payload = {"course_id": course_id, "question": question}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    return client.post(
        reverse("AIQandA:ask"),
        data=json.dumps(payload),
        content_type="application/json",
    )


def test_login_page_is_public(client) -> None:
    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert "登录课程空间" in response.content.decode()


def test_chat_requires_login(client) -> None:
    response = client.get(reverse("AIQandA:chat"))
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


def test_chat_renders_for_student(auth_client, document, course) -> None:
    response = auth_client.get(reverse("AIQandA:chat"))
    assert response.status_code == 200
    assert "今天想弄懂哪个概念" in response.content.decode()
    assert course.title in response.content.decode()


def test_ask_creates_conversation_message_and_citations(
    auth_client, student, course, document
) -> None:
    response = ask(auth_client, course.pk, "监督学习和无监督学习有什么区别？")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "fallback"
    assert payload["citations"]
    conversation = Conversation.objects.get(pk=payload["conversation_id"], user=student)
    assert conversation.messages.count() == 2
    assistant = conversation.messages.get(role=Message.Role.ASSISTANT)
    assert assistant.citations.count() == len(payload["citations"])
    assert assistant.mode == Message.Mode.FALLBACK


def test_ask_requires_authentication(client, course) -> None:
    response = ask(client, course.pk, "问题")
    assert response.status_code == 302


def test_ask_rejects_empty_and_long_questions(auth_client, course) -> None:
    assert ask(auth_client, course.pk, " ").status_code == 400
    assert ask(auth_client, course.pk, "问" * 1001).status_code == 400


def test_ask_rejects_foreign_conversation(auth_client, teacher, course) -> None:
    other = Conversation.objects.create(user=teacher, course=course, title="别人的对话")
    response = ask(auth_client, course.pk, "我能看吗？", conversation_id=other.pk)
    assert response.status_code == 404


def test_ask_rejects_course_mismatch(auth_client, student, course) -> None:
    other_course = Course.objects.create(code="OTHER", title="另一门课")
    conversation = Conversation.objects.create(user=student, course=other_course)
    response = ask(auth_client, course.pk, "问题", conversation_id=conversation.pk)
    assert response.status_code == 400


def test_daily_limit_applies_to_students(auth_client, course, document, settings) -> None:
    settings.AI_DAILY_LIMIT = 1
    assert ask(auth_client, course.pk, "第一个问题").status_code == 200
    response = ask(auth_client, course.pk, "第二个问题")
    assert response.status_code == 429


def test_daily_limit_exempts_staff(staff_client, course, document, settings) -> None:
    settings.AI_DAILY_LIMIT = 1
    assert ask(staff_client, course.pk, "第一个问题").status_code == 200
    assert ask(staff_client, course.pk, "第二个问题").status_code == 200


def test_feedback_creates_and_updates(auth_client, course, document) -> None:
    payload = ask(auth_client, course.pk, "什么是过拟合？").json()
    message_id = payload["message_id"]
    url = reverse("AIQandA:feedback", args=[message_id])

    response = auth_client.post(
        url,
        data=json.dumps({"rating": "up", "comment": "清楚"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert AnswerFeedback.objects.get(message_id=message_id).rating == "up"

    response = auth_client.post(
        url,
        data=json.dumps({"rating": "down"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert AnswerFeedback.objects.get(message_id=message_id).rating == "down"


def test_feedback_rejects_other_users_message(auth_client, teacher, course) -> None:
    conversation = Conversation.objects.create(user=teacher, course=course)
    message = Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content="教师的回答",
    )
    response = auth_client.post(
        reverse("AIQandA:feedback", args=[message.pk]),
        data=json.dumps({"rating": "up"}),
        content_type="application/json",
    )
    assert response.status_code == 404


def test_feedback_rejects_invalid_rating(auth_client, course, document) -> None:
    payload = ask(auth_client, course.pk, "什么是过拟合？").json()
    response = auth_client.post(
        reverse("AIQandA:feedback", args=[payload["message_id"]]),
        data=json.dumps({"rating": "stars"}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_materials_requires_staff(auth_client) -> None:
    assert auth_client.get(reverse("AIQandA:materials")).status_code == 403


def test_materials_renders_for_staff(staff_client, document) -> None:
    response = staff_client.get(reverse("AIQandA:materials"))
    assert response.status_code == 200
    assert "机器学习基础" in response.content.decode()
    assert "已就绪" in response.content.decode()


def test_upload_document_as_staff(staff_client, course, settings, tmp_path) -> None:
    settings.MEDIA_ROOT = tmp_path
    upload = SimpleUploadedFile(
        "notes.txt",
        "聚类是一种无监督学习方法。\n\n它把相似样本分到同一组。".encode("utf-8"),
        content_type="text/plain",
    )
    response = staff_client.post(
        reverse("AIQandA:material_upload"),
        data={"course": course.pk, "title": "聚类笔记", "file": upload},
    )
    assert response.status_code == 302
    document = KnowledgeDocument.objects.get(title="聚类笔记")
    assert document.status == KnowledgeDocument.Status.READY
    assert document.chunks.exists()


def test_upload_rejects_unsupported_extension(staff_client, course, settings, tmp_path) -> None:
    settings.MEDIA_ROOT = tmp_path
    upload = SimpleUploadedFile("malware.exe", b"nope", content_type="application/octet-stream")
    response = staff_client.post(
        reverse("AIQandA:material_upload"),
        data={"course": course.pk, "title": "坏文件", "file": upload},
    )
    assert response.status_code == 200
    assert not KnowledgeDocument.objects.filter(title="坏文件").exists()


def test_healthz_returns_ok(client) -> None:
    response = client.get(reverse("AIQandA:healthz"))
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_csrf_is_enforced_for_ask(student, course) -> None:
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(student)
    response = csrf_client.post(
        reverse("AIQandA:ask"),
        data=json.dumps({"course_id": course.pk, "question": "问题"}),
        content_type="application/json",
    )
    assert response.status_code == 403


def test_chat_loads_existing_conversation(auth_client, student, course) -> None:
    conversation = Conversation.objects.create(user=student, course=course, title="已有对话")
    Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content="这是之前的回答",
    )
    response = auth_client.get(
        reverse("AIQandA:chat"),
        {"course": course.pk, "conversation": conversation.pk},
    )
    assert response.status_code == 200
    assert "这是之前的回答" in response.content.decode()
