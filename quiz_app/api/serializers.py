from rest_framework import serializers

from quiz_app.models import Question, Quiz
from quiz_app.utils import build_watch_url, extract_video_id


class QuestionSerializer(serializers.ModelSerializer):
    """Serializes a single question with its answer options."""

    class Meta:
        model = Question
        fields = ["id", "question_title", "question_options", "answer"]


class QuizSerializer(serializers.ModelSerializer):
    """Serializes a quiz with all of its questions."""

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
    """Serializes a single question including its timestamps."""

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
    """Serializes a newly created quiz with the timestamps of every question."""

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
    """Validates the YouTube URL that is sent to create a new quiz."""

    url = serializers.CharField()

    def validate_url(self, value: str) -> str:
        """Accept only YouTube links and return them in the standard watch format."""
        video_id = extract_video_id(value)
        if video_id is None:
            raise serializers.ValidationError(
                "Please enter a valid YouTube URL.")
        return build_watch_url(video_id)
