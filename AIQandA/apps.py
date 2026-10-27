"""Application configuration for AIQandA."""

from django.apps import AppConfig


class AiqandaConfig(AppConfig):
    """Configuration for the AIQandA app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "AIQandA"
    verbose_name = "AI 课程问答"
