"""Admin configuration for the teaching assistant data."""

from django.contrib import admin

from .models import (
    AnswerFeedback,
    Citation,
    Conversation,
    Course,
    DocumentChunk,
    KnowledgeDocument,
    Message,
)


class DocumentChunkInline(admin.TabularInline):
    """Read-only preview of chunks inside a document."""

    model = DocumentChunk
    extra = 0
    can_delete = False
    fields = ("chunk_index", "page_number", "char_count", "content")
    readonly_fields = fields
    show_change_link = True


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Admin for courses."""

    list_display = ("code", "title", "document_count", "created_at")
    search_fields = ("code", "title", "description")
    ordering = ("code",)

    @admin.display(description="资料数")
    def document_count(self, obj: Course) -> int:
        """Return the number of materials in this course."""
        return obj.documents.count()


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    """Admin for uploaded course documents."""

    list_display = ("title", "course", "status", "page_count", "created_at")
    list_filter = ("status", "course")
    search_fields = ("title", "extracted_text")
    readonly_fields = ("status", "page_count", "extracted_text", "error_message", "processed_at")
    inlines = (DocumentChunkInline,)


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    """Admin for retrievable chunks."""

    list_display = ("document", "chunk_index", "page_number", "char_count")
    list_filter = ("document__course",)
    search_fields = ("content", "document__title")
    readonly_fields = ("embedding",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin for conversations."""

    list_display = ("id", "user", "course", "title", "updated_at")
    list_filter = ("course",)
    search_fields = ("title", "user__username")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin for messages."""

    list_display = ("id", "conversation", "role", "mode", "created_at")
    list_filter = ("role", "mode")
    search_fields = ("content",)


@admin.register(Citation)
class CitationAdmin(admin.ModelAdmin):
    """Admin for answer citations."""

    list_display = ("message", "rank", "chunk", "score")
    list_filter = ("chunk__document__course",)


@admin.register(AnswerFeedback)
class AnswerFeedbackAdmin(admin.ModelAdmin):
    """Admin for learner feedback."""

    list_display = ("message", "user", "rating", "created_at")
    list_filter = ("rating",)
    search_fields = ("comment", "user__username")
