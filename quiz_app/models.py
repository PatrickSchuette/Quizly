from django.contrib.auth.models import User
from django.db import models


class Quiz(models.Model):
    """A quiz that was generated from a YouTube video for one user."""

    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="quizzes"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    video_url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Quizzes"

    def __str__(self) -> str:
        """Return the quiz title as readable name, e.g. in the admin panel."""
        return self.title


class Question(models.Model):
    """A single multiple-choice question that belongs to a quiz."""

    quiz = models.ForeignKey(
        Quiz, on_delete=models.CASCADE, related_name="questions"
    )
    question_title = models.CharField(max_length=255)
    question_options = models.JSONField()
    answer = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        """Return the question text as readable name, e.g. in the admin panel."""
        return self.question_title
