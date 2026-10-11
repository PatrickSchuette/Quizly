from rest_framework import serializers

from quiz_app.models import Question, Quiz


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
