from django.contrib import admin

from .models import Question, Quiz


class QuestionInline(admin.StackedInline):
    """Shows and edits the questions directly inside the quiz page."""

    model = Question
    extra = 0


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    """Admin configuration for quizzes including their questions."""

    list_display = ["id", "title", "owner", "created_at"]
    list_filter = ["owner"]
    search_fields = ["title", "description"]
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """Admin configuration for editing single questions."""

    list_display = ["id", "question_title", "quiz"]
    search_fields = ["question_title"]
