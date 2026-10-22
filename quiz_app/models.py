from django.contrib.auth.models import User
from django.db import models


class Quiz(models.Model):
    """A quiz that was generated from a YouTube video for one user.

    Every quiz belongs to exactly one user. If the user is deleted, all of
    the user's quizzes are deleted as well. The questions are stored in the
    separate ``Question`` model and can be reached with
    ``quiz.questions``. Quizzes are sorted from newest to oldest.

    Attributes:
        owner: The user who created the quiz.
        title: The title created by Gemini; the user can change it.
        description: A short summary created by Gemini; the user can
            change it.
        video_url: The YouTube URL in the format
            ``https://www.youtube.com/watch?v=VIDEO_ID``.
        created_at: Set automatically when the quiz is created.
        updated_at: Updated automatically every time the quiz is saved.
    """

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
        """Return the title of the quiz as readable name.

        Django uses this text wherever a quiz is shown as text, for example in
        the admin panel or in the Django shell.

        Returns:
            The title of the quiz.
        """
        return self.title


class Question(models.Model):
    """A single multiple-choice question that belongs to a quiz.

    If the quiz is deleted, all of its questions are deleted as well.

    Attributes:
        quiz: The quiz the question belongs to.
        question_title: The text of the question.
        question_options: A JSON list with exactly 4 answer options.
        answer: The correct answer; always one of ``question_options``.
        created_at: Set automatically when the question is created.
        updated_at: Updated automatically every time the question is saved.
    """

    quiz = models.ForeignKey(
        Quiz, on_delete=models.CASCADE, related_name="questions"
    )
    question_title = models.CharField(max_length=255)
    question_options = models.JSONField()
    answer = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        """Return the text of the question as readable name.

        Django uses this text wherever a question is shown as text, for
        example in the admin panel or in the Django shell.

        Returns:
            The text of the question.
        """
        return self.question_title
