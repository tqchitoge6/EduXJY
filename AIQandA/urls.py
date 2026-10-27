"""URL routes for the AIQandA app."""

from django.urls import path

from . import views

app_name = "AIQandA"

urlpatterns = [
    path("", views.chat, name="chat"),
    path("api/ask/", views.ask, name="ask"),
    path(
        "api/messages/<int:message_id>/feedback/",
        views.feedback,
        name="feedback",
    ),
    path("materials/", views.materials, name="materials"),
    path("materials/upload/", views.material_upload, name="material_upload"),
    path("healthz/", views.healthz, name="healthz"),
]
