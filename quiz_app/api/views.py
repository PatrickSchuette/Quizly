from django.db.models import QuerySet
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from yt_dlp.utils import DownloadError

from quiz_app.models import Quiz
from quiz_app.utils import create_quiz_from_url
from .permissions import IsQuizOwner
from .serializers import QuizCreateSerializer, QuizDetailSerializer, QuizSerializer

DOWNLOAD_ERROR = {"detail": "The video could not be downloaded."}
GENERATION_ERROR = {"detail": "The quiz could not be generated."}


class QuizListCreateView(generics.ListAPIView):
    """Returns all quizzes of the logged-in user or creates a new one from a YouTube URL."""

    serializer_class = QuizSerializer

    def get_queryset(self) -> QuerySet:
        """Return only the quizzes that belong to the current user."""
        return Quiz.objects.filter(owner=self.request.user)

    def post(self, request: Request) -> Response:
        """Validate the URL, create the quiz and return it with all questions."""
        serializer = QuizCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        video_url = serializer.validated_data["url"]
        try:
            quiz = create_quiz_from_url(request.user, video_url)
        except DownloadError:
            return Response(DOWNLOAD_ERROR, status=400)
        except Exception as error:
            print("Quiz generation failed:", error)
            return Response(GENERATION_ERROR, status=500)
        return Response(QuizDetailSerializer(quiz).data, status=201)


class QuizDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Returns, updates or deletes a single quiz of the logged-in user."""

    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    permission_classes = [IsAuthenticated, IsQuizOwner]
    http_method_names = ["get", "patch", "delete"]
