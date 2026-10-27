"""Business models for the AIQandA teaching assistant."""

from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Q


def course_material_path(instance: "KnowledgeDocument", filename: str) -> str:
    """Return a collision-resistant, non-user-controlled upload path."""
    suffix = Path(filename).suffix.lower()
    return f"materials/course_{instance.course_id}/{uuid.uuid4().hex}{suffix}"


class Course(models.Model):
    """A course whose materials ground the assistant's answers."""

    code = models.CharField("课程代码", max_length=32, unique=True)
    title = models.CharField("课程名称", max_length=120)
    description = models.TextField("课程简介", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ("code",)
        verbose_name = "课程"
        verbose_name_plural = "课程"

    def __str__(self) -> str:
        return f"{self.code} {self.title}"


class KnowledgeDocument(models.Model):
    """An uploaded course document and its processing state."""

    class Status(models.TextChoices):
        """Lifecycle states for an uploaded document."""

        PENDING = "pending", "待处理"
        READY = "ready", "已就绪"
        FAILED = "failed", "处理失败"

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="所属课程",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_documents",
        verbose_name="上传教师",
    )
    title = models.CharField("资料标题", max_length=200)
    file = models.FileField(
        "资料文件",
        upload_to=course_material_path,
        validators=[FileExtensionValidator(["txt", "md", "pdf", "docx"])],
    )
    status = models.CharField(
        "处理状态",
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    page_count = models.PositiveIntegerField("页数", default=0)
    extracted_text = models.TextField("提取文本", blank=True)
    error_message = models.TextField("错误信息", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    processed_at = models.DateTimeField("处理完成时间", null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "课程资料"
        verbose_name_plural = "课程资料"
        constraints = [
            models.UniqueConstraint(
                fields=("course", "title"),
                name="uniq_document_title_per_course",
            )
        ]
        indexes = [models.Index(fields=("course", "status"), name="doc_course_status_idx")]

    def __str__(self) -> str:
        return f"{self.title} ({self.get_status_display()})"


class DocumentChunk(models.Model):
    """A retrievable fragment of a course document."""

    document = models.ForeignKey(
        KnowledgeDocument,
        on_delete=models.CASCADE,
        related_name="chunks",
        verbose_name="所属资料",
    )
    chunk_index = models.PositiveIntegerField("片段序号")
    page_number = models.PositiveIntegerField("页码", null=True, blank=True)
    content = models.TextField("片段内容")
    char_count = models.PositiveIntegerField("字符数", default=0)
    embedding = models.JSONField("向量", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ("document_id", "chunk_index")
        verbose_name = "资料片段"
        verbose_name_plural = "资料片段"
        constraints = [
            models.UniqueConstraint(
                fields=("document", "chunk_index"),
                name="uniq_chunk_index_per_document",
            )
        ]
        indexes = [
            models.Index(
                fields=("document", "chunk_index"),
                name="chunk_document_index_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.document.title} #{self.chunk_index}"


class Conversation(models.Model):
    """A student's question-and-answer session for one course."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations",
        verbose_name="学生",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="conversations",
        verbose_name="课程",
    )
    title = models.CharField("会话标题", max_length=120, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        verbose_name = "对话"
        verbose_name_plural = "对话"
        indexes = [
            models.Index(
                fields=("user", "-updated_at"),
                name="conversation_user_updated_idx",
            )
        ]

    def __str__(self) -> str:
        return self.title or f"对话 #{self.pk}"


class Message(models.Model):
    """A stored user question or assistant answer."""

    class Role(models.TextChoices):
        """Who authored a stored message."""

        USER = "user", "学生"
        ASSISTANT = "assistant", "助教"

    class Mode(models.TextChoices):
        """Whether an answer came from the model or the fallback."""

        AI = "ai", "AI 生成"
        FALLBACK = "fallback", "检索降级"

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="所属对话",
    )
    role = models.CharField("角色", max_length=16, choices=Role.choices)
    content = models.TextField("内容")
    mode = models.CharField(
        "生成模式",
        max_length=16,
        choices=Mode.choices,
        default=Mode.AI,
    )
    model_name = models.CharField("模型名称", max_length=100, blank=True)
    latency_ms = models.PositiveIntegerField("耗时(毫秒)", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        verbose_name = "消息"
        verbose_name_plural = "消息"
        constraints = [
            models.CheckConstraint(
                condition=Q(role__in=["user", "assistant"]),
                name="message_role_valid",
            )
        ]
        indexes = [
            models.Index(
                fields=("conversation", "created_at"),
                name="message_conv_created_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_role_display()}: {self.content[:40]}"


class Citation(models.Model):
    """A link between an assistant answer and a retrieved document chunk."""

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="citations",
        verbose_name="回答",
    )
    chunk = models.ForeignKey(
        DocumentChunk,
        on_delete=models.CASCADE,
        related_name="citations",
        verbose_name="资料片段",
    )
    rank = models.PositiveSmallIntegerField("引用编号")
    score = models.FloatField("检索得分", default=0)
    quote = models.TextField("引用摘录")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ("rank",)
        verbose_name = "引用"
        verbose_name_plural = "引用"
        constraints = [
            models.UniqueConstraint(
                fields=("message", "chunk"),
                name="uniq_citation_chunk_msg",
            ),
            models.UniqueConstraint(
                fields=("message", "rank"),
                name="uniq_citation_rank_msg",
            ),
        ]
        indexes = [models.Index(fields=("message", "rank"), name="citation_message_rank_idx")]

    def __str__(self) -> str:
        return f"[{self.rank}] {self.chunk.document.title}"


class AnswerFeedback(models.Model):
    """A learner's rating of one assistant answer."""

    class Rating(models.TextChoices):
        """Learner ratings for an assistant answer."""

        UP = "up", "有帮助"
        DOWN = "down", "需改进"

    message = models.OneToOneField(
        Message,
        on_delete=models.CASCADE,
        related_name="feedback",
        verbose_name="回答",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="answer_feedback",
        verbose_name="反馈学生",
    )
    rating = models.CharField("评价", max_length=8, choices=Rating.choices)
    comment = models.TextField("补充意见", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "回答反馈"
        verbose_name_plural = "回答反馈"
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__in=["up", "down"]),
                name="feedback_rating_valid",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_rating_display()} - {self.message_id}"
