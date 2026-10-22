from django.contrib import admin

from .models import Question, Quiz


class QuestionInline(admin.StackedInline):
    """Show and edit the questions directly on the admin page of their quiz.

    ``extra = 0`` means that no empty forms for new questions are shown,
    because the questions are normally created by Gemini.
    """

    model = Question
    extra = 0


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    """Admin configuration for quizzes.

    The list shows the id, the title, the owner and the creation date.
    Quizzes can be filtered by owner and searched by title and
    description. On the detail page all questions of the quiz are shown
    below the quiz fields.
    """

    list_display = ["id", "title", "owner", "created_at"]
    list_display_links = ["id", "title"]
    list_filter = ["owner"]
    search_fields = ["title", "description"]
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """Admin configuration for editing single questions.

    The list shows the id, the question text and the related quiz. It can
    be searched by the question text.
    """

    list_display = ["id", "question_title", "quiz"]
    list_display_links = ["id", "question_title"]
    search_fields = ["question_title"]
