"""Tests for the upload form validation."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from AIQandA.forms import MAX_UPLOAD_BYTES, DocumentUploadForm

pytestmark = pytest.mark.django_db


def test_form_rejects_large_file(course) -> None:
    upload = SimpleUploadedFile("big.txt", b"x" * (MAX_UPLOAD_BYTES + 1))
    form = DocumentUploadForm(
        data={"course": course.pk, "title": "大文件"},
        files={"file": upload},
    )
    assert not form.is_valid()
    assert "file" in form.errors


def test_form_rejects_empty_file(course) -> None:
    upload = SimpleUploadedFile("empty.txt", b"")
    form = DocumentUploadForm(
        data={"course": course.pk, "title": "空文件"},
        files={"file": upload},
    )
    assert not form.is_valid()
    assert "file" in form.errors


def test_form_rejects_duplicate_title(course, document) -> None:
    upload = SimpleUploadedFile("again.txt", "一些内容".encode())
    form = DocumentUploadForm(
        data={"course": course.pk, "title": document.title},
        files={"file": upload},
    )
    assert not form.is_valid()
    assert "title" in form.errors


def test_form_accepts_valid_upload(course) -> None:
    upload = SimpleUploadedFile("valid.txt", "聚类是一种无监督学习方法。".encode())
    form = DocumentUploadForm(
        data={"course": course.pk, "title": "有效资料"},
        files={"file": upload},
    )
    assert form.is_valid(), form.errors
