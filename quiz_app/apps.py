from django.apps import AppConfig


class QuizAppConfig(AppConfig):
    """Configuration of the ``quiz_app`` app.

    The app contains the ``Quiz`` and ``Question`` models, the creation of
    quizzes from YouTube videos and the endpoints to read, update and
    delete quizzes.
    """

    name = 'quiz_app'
