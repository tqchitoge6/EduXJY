"""Tests for the demo seeding command."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from AIQandA.models import Course, KnowledgeDocument

pytestmark = pytest.mark.django_db


def test_seed_demo_creates_course_materials_and_accounts(settings, tmp_path) -> None:
    settings.MEDIA_ROOT = tmp_path
    call_command("seed_demo", password="demo-password", verbosity=0)
    assert Course.objects.filter(code="AI101").exists()
    assert KnowledgeDocument.objects.filter(course__code="AI101", status="ready").count() == 3
    assert get_user_model().objects.filter(username="teacher", is_staff=True).exists()
    assert get_user_model().objects.filter(username="student", is_staff=False).exists()


def test_seed_demo_is_idempotent(settings, tmp_path) -> None:
    settings.MEDIA_ROOT = tmp_path
    call_command("seed_demo", password="demo-password", verbosity=0)
    call_command("seed_demo", password="demo-password", verbosity=0)
    assert KnowledgeDocument.objects.filter(course__code="AI101").count() == 3
