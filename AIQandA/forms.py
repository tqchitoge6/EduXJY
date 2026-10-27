"""Forms used by the AIQandA app."""

from __future__ import annotations

from django import forms
from django.core.validators import FileExtensionValidator

from .models import Course, KnowledgeDocument

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = ["txt", "md", "pdf", "docx"]


class DocumentUploadForm(forms.Form):
    """Validate and normalize a course material upload."""

    course = forms.ModelChoiceField(
        queryset=Course.objects.all(),
        label="所属课程",
        empty_label=None,
    )
    title = forms.CharField(
        max_length=200,
        label="资料标题",
        widget=forms.TextInput(attrs={"placeholder": "例如：机器学习基础"}),
    )
    file = forms.FileField(
        label="资料文件",
        validators=[FileExtensionValidator(ALLOWED_EXTENSIONS)],
        help_text="支持 TXT、Markdown、PDF、DOCX，单个文件不超过 10 MB。",
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_title(self) -> str:
        """Strip whitespace and reject an empty title."""
        title = self.cleaned_data["title"].strip()
        if not title:
            raise forms.ValidationError("资料标题不能为空。")
        return title

    def clean_file(self):
        """Enforce the upload size limit."""
        uploaded = self.cleaned_data["file"]
        if uploaded.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError("文件不能超过 10 MB。")
        if uploaded.size == 0:
            raise forms.ValidationError("文件内容为空。")
        return uploaded

    def clean(self):
        """Reject duplicate titles within the same course."""
        cleaned_data = super().clean()
        course = cleaned_data.get("course")
        title = cleaned_data.get("title")
        if (
            course
            and title
            and KnowledgeDocument.objects.filter(
                course=course,
                title=title,
            ).exists()
        ):
            self.add_error("title", "该课程下已存在同名资料。")
        return cleaned_data
