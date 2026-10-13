import logging

from django.db.models import QuerySet
from rest_framework import generics, status
from rest_framework.exceptions import APIException, ParseError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from yt_dlp.utils import DownloadError

from quiz_app.models import Quiz
from quiz_app.utils import create_quiz_from_url
from .permissions import IsQuizOwner
from .serializers import QuizCreateSerializer, QuizDetailSerializer, QuizSerializer

logger = logging.getLogger(__name__)


class QuizListCreateView(generics.ListAPIView):
    """Returns all quizzes of the logged-in user or creates a new one from a YouTube URL."""

    serializer_class = QuizSerializer

    def get_queryset(self) -> QuerySet[Quiz]:
        """Return only the quizzes that belong to the current user."""
        return Quiz.objects.filter(owner=self.request.user)

    def post(self, request: Request) -> Response:
        """Validate the URL, generate the quiz and return it with all questions."""
        input_serializer = QuizCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        quiz = self.generate_quiz(input_serializer.validated_data["url"])
        return Response(QuizDetailSerializer(quiz).data, status=status.HTTP_201_CREATED)

    def generate_quiz(self, video_url: str) -> Quiz:
        """Run the quiz pipeline and turn its errors into API error responses."""
        try:
            return create_quiz_from_url(self.request.user, video_url)
        except DownloadError:
            raise ParseError("The video could not be downloaded.")
        except Exception:
            logger.exception("Quiz generation failed for %s", video_url)
            raise APIException("The quiz could not be generated.")


class QuizDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Returns, updates or deletes a single quiz of the logged-in user."""

    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    permission_classes = [IsAuthenticated, IsQuizOwner]
    http_method_names = ["get", "patch", "delete"]
