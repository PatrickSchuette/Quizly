from rest_framework import serializers

from quiz_app.models import Question, Quiz
from quiz_app.utils import build_watch_url, extract_video_id


class QuestionSerializer(serializers.ModelSerializer):
    """Serialize a single question with its answer options.

    Used inside ``QuizSerializer`` for the quiz list and the quiz detail
    endpoints. The timestamps of the question are not included.
    """

    class Meta:
        model = Question
        fields = ["id", "question_title", "question_options", "answer"]


class QuizSerializer(serializers.ModelSerializer):
    """Serialize a quiz together with all of its questions.

    Used for ``GET /api/quizzes/`` and for ``GET`` and ``PATCH`` on
    ``/api/quizzes/{id}/``. The questions are nested in the quiz and are
    read-only. ``id``, ``created_at``, ``updated_at`` and ``video_url``
    are read-only as well, so a ``PATCH`` request can only change
    ``title`` and ``description``.
    """

    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = [
            "id",
            "title",
            "description",
            "created_at",
            "updated_at",
            "video_url",
            "questions",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "video_url"]


class QuestionDetailSerializer(serializers.ModelSerializer):
    """Serialize a single question including its timestamps.

    Used inside ``QuizDetailSerializer``. The endpoint documentation
    requires ``created_at`` and ``updated_at`` for every question only in
    the response after a quiz was created.
    """

    class Meta:
        model = Question
        fields = [
            "id",
            "question_title",
            "question_options",
            "answer",
            "created_at",
            "updated_at",
        ]


class QuizDetailSerializer(serializers.ModelSerializer):
    """Serialize a newly created quiz with the timestamps of every question.

    Used only for the response of ``POST /api/quizzes/``. It contains the
    same fields as ``QuizSerializer``, but uses
    ``QuestionDetailSerializer`` for the questions.
    """

    questions = QuestionDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = [
            "id",
            "title",
            "description",
            "created_at",
            "updated_at",
            "video_url",
            "questions",
        ]


class QuizCreateSerializer(serializers.Serializer):
    """Validate the YouTube URL that is sent to create a new quiz.

    It is a plain ``Serializer`` and not a ``ModelSerializer``, because the
    request only contains the URL. All other fields of the quiz are
    created later by Whisper and Gemini.
    """

    url = serializers.CharField()

    def validate_url(self, value: str) -> str:
        """Check that the URL is a YouTube link and normalize it.

        All supported YouTube link formats (``watch?v=``, ``youtu.be/``,
        ``shorts/``, ``embed/`` and ``live/``) are accepted. The video id is
        taken from the link and a clean watch URL is built from it. This
        removes extra parameters like ``?si=...`` or ``&t=9s``, so every quiz
        stores its video URL in the same format.

        Args:
            value: The URL from the request body.

        Returns:
            The URL in the format ``https://www.youtube.com/watch?v=VIDEO_ID``.

        Raises:
            serializers.ValidationError: If the URL is not a YouTube link.
        """
        video_id = extract_video_id(value)
        if video_id is None:
            raise serializers.ValidationError(
                "Please enter a valid YouTube URL.")
        return build_watch_url(video_id)
