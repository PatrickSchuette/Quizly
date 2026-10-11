from django.db.models import QuerySet
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from quiz_app.models import Quiz
from .permissions import IsQuizOwner
from .serializers import QuizSerializer


class QuizListView(generics.ListAPIView):
    """Returns all quizzes of the logged-in user."""

    serializer_class = QuizSerializer

    def get_queryset(self) -> QuerySet[Quiz]:
        """Return only the quizzes that belong to the current user."""
        return Quiz.objects.filter(owner=self.request.user)


class QuizDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Returns, updates or deletes a single quiz of the logged-in user."""

    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    permission_classes = [IsAuthenticated, IsQuizOwner]
    http_method_names = ["get", "patch", "delete"]
