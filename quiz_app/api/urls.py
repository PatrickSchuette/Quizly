from django.urls import path

from .views import QuizDetailView, QuizListCreateView

urlpatterns = [
    path("quizzes/", QuizListCreateView.as_view(), name="quiz-list"),
    path("quizzes/<int:pk>/", QuizDetailView.as_view(), name="quiz-detail"),
]
