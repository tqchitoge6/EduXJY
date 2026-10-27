"""HTTP views for the AIQandA teaching assistant."""

from __future__ import annotations

import json
import logging
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.models import Count, Prefetch
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import DocumentUploadForm
from .models import (
    AnswerFeedback,
    Citation,
    Conversation,
    Course,
    KnowledgeDocument,
    Message,
)
from .services.documents import DocumentIngestError, ingest_document
from .services.qa import answer_question

logger = logging.getLogger(__name__)

SUGGESTED_QUESTIONS = [
    "监督学习和无监督学习有什么区别？",
    "什么是过拟合，如何缓解？",
    "准确率高就一定说明模型好吗？",
]


def staff_required(view):
    """Require an authenticated staff user."""

    @wraps(view)
    @login_required
    def wrapped(request: HttpRequest, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied("仅教师可以管理课程资料。")
        return view(request, *args, **kwargs)

    return wrapped


def _error(message: str, status: int) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def _load_messages(conversation: Conversation) -> list[Message]:
    citations = Citation.objects.select_related("chunk__document").order_by("rank")
    return list(
        conversation.messages.select_related("feedback")
        .prefetch_related(Prefetch("citations", queryset=citations))
        .order_by("created_at", "id")
    )


@login_required
def chat(request: HttpRequest) -> HttpResponse:
    """Render the chat workspace, optionally loading a conversation."""
    courses = list(Course.objects.all())
    selected_course: Course | None = None
    requested_course = request.GET.get("course")
    if requested_course:
        selected_course = next(
            (course for course in courses if str(course.pk) == requested_course),
            None,
        )
    if selected_course is None and courses:
        selected_course = courses[0]

    conversation = None
    conversation_id = request.GET.get("conversation")
    if conversation_id:
        conversation = get_object_or_404(
            Conversation,
            pk=conversation_id,
            user=request.user,
        )
        selected_course = conversation.course
    elif request.GET.get("new") != "1" and selected_course is not None:
        conversation = (
            Conversation.objects.filter(user=request.user, course=selected_course)
            .order_by("-updated_at")
            .first()
        )

    chat_messages = _load_messages(conversation) if conversation else []
    conversations = (
        Conversation.objects.filter(user=request.user, course=selected_course)[:20]
        if selected_course
        else Conversation.objects.none()
    )
    context = {
        "courses": courses,
        "selected_course": selected_course,
        "conversations": conversations,
        "conversation": conversation,
        "chat_messages": chat_messages,
        "suggestions": SUGGESTED_QUESTIONS,
    }
    return render(request, "AIQandA/chat.html", context)


# pylint: disable=too-many-return-statements,too-many-branches
@login_required
@require_POST
def ask(
    request: HttpRequest,
) -> JsonResponse:
    """Answer a question and persist the conversation with citations."""
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _error("请求格式不正确。", 400)
    if not isinstance(payload, dict):
        return _error("请求格式不正确。", 400)

    question = str(payload.get("question", "")).strip()
    if len(question) < 2:
        return _error("问题至少需要 2 个字。", 400)
    if len(question) > 1000:
        return _error("问题不能超过 1000 个字。", 400)

    conversation_id = payload.get("conversation_id")
    course_id = payload.get("course_id")
    conversation: Conversation | None = None
    course: Course | None = None

    if conversation_id not in (None, ""):
        try:
            conversation = Conversation.objects.select_related("course").get(
                pk=int(conversation_id),
                user=request.user,
            )
        except (Conversation.DoesNotExist, TypeError, ValueError):
            return _error("对话不存在。", 404)
        course = conversation.course
        if course_id not in (None, "") and str(course.pk) != str(course_id):
            return _error("对话与课程不匹配。", 400)
    else:
        try:
            course = Course.objects.get(pk=int(course_id))
        except (Course.DoesNotExist, TypeError, ValueError):
            return _error("请选择有效的课程。", 400)
        conversation = Conversation.objects.create(
            user=request.user,
            course=course,
            title=question[:30],
        )

    if not request.user.is_staff and settings.AI_DAILY_LIMIT > 0:
        today = timezone.localdate()
        used = Message.objects.filter(
            conversation__user=request.user,
            role=Message.Role.USER,
            created_at__date=today,
        ).count()
        if used >= settings.AI_DAILY_LIMIT:
            return _error("今日提问次数已达上限，请明天再试。", 429)

    history = list(conversation.messages.order_by("-created_at", "-id")[:6])
    history.reverse()
    Message.objects.create(
        conversation=conversation,
        role=Message.Role.USER,
        content=question,
    )

    try:
        result = answer_question(course, question, history)
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected QA failure for conversation %s", conversation.pk)
        return _error("回答生成失败，请稍后重试。", 502)

    with transaction.atomic():
        assistant_message = Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content=result.answer,
            mode=result.mode,
            model_name=result.model_name,
            latency_ms=result.latency_ms,
        )
        Citation.objects.bulk_create(
            [
                Citation(
                    message=assistant_message,
                    chunk_id=citation.chunk_id,
                    rank=citation.rank,
                    score=citation.score,
                    quote=citation.quote,
                )
                for citation in result.citations
            ]
        )
        if not conversation.title:
            conversation.title = question[:30]
        conversation.save(update_fields=["title", "updated_at"])

    return JsonResponse(
        {
            "conversation_id": conversation.pk,
            "message_id": assistant_message.pk,
            "answer": result.answer,
            "mode": result.mode,
            "citations": [
                {
                    "index": citation.rank,
                    "document": citation.document_title,
                    "page": citation.page_number,
                    "quote": citation.quote,
                    "score": citation.score,
                }
                for citation in result.citations
            ],
        }
    )


@login_required
@require_POST
def feedback(request: HttpRequest, message_id: int) -> JsonResponse:
    """Create or update feedback for one of the user's assistant messages."""
    message = get_object_or_404(
        Message.objects.select_related("conversation"),
        pk=message_id,
        conversation__user=request.user,
        role=Message.Role.ASSISTANT,
    )
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _error("请求格式不正确。", 400)
    rating = payload.get("rating")
    if rating not in {AnswerFeedback.Rating.UP, AnswerFeedback.Rating.DOWN}:
        return _error("请选择有效的评价。", 400)
    comment = str(payload.get("comment", "")).strip()[:500]

    record, _ = AnswerFeedback.objects.update_or_create(
        message=message,
        defaults={"user": request.user, "rating": rating, "comment": comment},
    )
    return JsonResponse(
        {
            "ok": True,
            "rating": record.rating,
            "message": "感谢反馈。",
        }
    )


@staff_required
def materials(request: HttpRequest) -> HttpResponse:
    """Show the teacher's material library."""
    documents = (
        KnowledgeDocument.objects.select_related("course", "uploaded_by")
        .annotate(chunk_count=Count("chunks"))
        .order_by("-created_at")
    )
    return render(
        request,
        "AIQandA/materials.html",
        {
            "documents": documents,
            "courses": Course.objects.all(),
            "page_title": "课程资料",
            "page_kicker": "Teacher workspace",
        },
    )


@staff_required
def material_upload(request: HttpRequest) -> HttpResponse:
    """Upload and index a course document."""
    if request.method == "POST":
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            document = KnowledgeDocument(
                course=form.cleaned_data["course"],
                uploaded_by=request.user,
                title=form.cleaned_data["title"],
            )
            uploaded = form.cleaned_data["file"]
            document.file.save(uploaded.name, uploaded, save=False)
            document.save()
            try:
                chunk_count = ingest_document(document)
            except DocumentIngestError as exc:
                messages.error(request, f"资料保存成功，但解析失败：{exc}")
                return redirect("AIQandA:materials")
            messages.success(
                request,
                f"《{document.title}》已就绪，共切分 {chunk_count} 个片段。",
            )
            return redirect("AIQandA:materials")
    else:
        form = DocumentUploadForm()

    return render(
        request,
        "AIQandA/upload.html",
        {
            "form": form,
            "courses": Course.objects.all(),
            "page_title": "上传资料",
            "page_kicker": "Add course material",
        },
    )


def healthz(request: HttpRequest) -> JsonResponse:
    """Public liveness/readiness check used by deployment verification."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        return JsonResponse({"status": "error", "database": "down"}, status=503)
    response = JsonResponse({"status": "ok", "database": "ok"})
    response["Cache-Control"] = "no-store"
    return response
