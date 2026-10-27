"""Shared pytest fixtures for AIQandA tests."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from AIQandA.models import Course, KnowledgeDocument
from AIQandA.services.documents import ingest_document

SAMPLE_TEXT = """机器学习基础

机器学习是让计算机从数据中学习规律的方法。监督学习使用带标签的数据，无监督学习不提供标签。
过拟合是指模型把训练数据中的噪声也学了进去，可以通过正则化和增加数据缓解。
模型评估不能只看准确率，还要看精确率、召回率和 F1 值。
"""


@pytest.fixture(autouse=True)
def isolated_media(settings, tmp_path):
    """Keep uploaded files out of the repository during tests."""
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture(autouse=True)
def no_live_ai(settings):
    """Never make a paid network call from the test suite."""
    settings.AI_API_KEY = ""
    settings.AI_EMBEDDING_MODEL = ""


@pytest.fixture
def course(db) -> Course:
    """A course fixture."""
    return Course.objects.create(
        code="TEST101",
        title="测试课程",
        description="用于自动化测试的课程。",
    )


@pytest.fixture
def teacher(db):
    """A staff user fixture."""
    return get_user_model().objects.create_user(
        username="teacher_test",
        password="test-password-123",
        is_staff=True,
    )


@pytest.fixture
def student(db):
    """A student user fixture."""
    return get_user_model().objects.create_user(
        username="student_test",
        password="test-password-123",
    )


@pytest.fixture
def document(course, teacher) -> KnowledgeDocument:
    """A ready document with parsed chunks."""
    record = KnowledgeDocument(
        course=course,
        uploaded_by=teacher,
        title="机器学习基础",
    )
    record.file.save("machine_learning.txt", ContentFile(SAMPLE_TEXT.encode("utf-8")), save=False)
    record.save()
    ingest_document(record)
    record.refresh_from_db()
    return record


@pytest.fixture
def auth_client(client, student):
    """A Django test client logged in as a student."""
    client.force_login(student)
    return client


@pytest.fixture
def staff_client(client, teacher):
    """A Django test client logged in as a teacher."""
    client.force_login(teacher)
    return client
