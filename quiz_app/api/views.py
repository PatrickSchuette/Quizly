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
    """List the quizzes of the user or create a new quiz (``/api/quizzes/``).

    ``GET`` returns all quizzes of the logged-in user, newest first.
    ``POST`` takes a YouTube URL and creates a new quiz from it. Only
    logged-in users can use this endpoint (default permission
    ``IsAuthenticated`` in ``core/settings.py``).
    """

    serializer_class = QuizSerializer

    def get_queryset(self) -> QuerySet:
        """Return only the quizzes that belong to the logged-in user.

        Returns:
            A queryset with all quizzes of the current user. The order comes
            from ``Meta.ordering`` of the ``Quiz`` model (newest first).
        """
        return Quiz.objects.filter(owner=self.request.user)

    def post(self, request: Request) -> Response:
        """Create a new quiz from a YouTube URL.

        The URL is validated with ``QuizCreateSerializer`` first. Then
        ``create_quiz_from_url`` downloads the audio, transcribes it, lets
        Gemini create the quiz and saves it. This can take a while, because
        the transcription runs on the server.

        Args:
            request: The request with the YouTube URL as ``url`` in its body.

        Returns:
            The created quiz with all questions and status ``201``.
            Status ``400`` if the URL is invalid or the video can not be
            downloaded. Status ``500`` if the quiz could not be generated, for
            example because Gemini returned invalid data.
        """
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
    """Read, update or delete a single quiz (``/api/quizzes/{id}/``).

    Only ``GET``, ``PATCH`` and ``DELETE`` are allowed; ``PUT`` returns
    status ``405``. The user must be logged in and must be the owner of
    the quiz (``IsQuizOwner``), otherwise the response is ``401`` or
    ``403``. If the quiz does not exist, the response is ``404``.
    Deleting a quiz also deletes all of its questions.
    """

    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    permission_classes = [IsAuthenticated, IsQuizOwner]
    http_method_names = ["get", "patch", "delete"]
