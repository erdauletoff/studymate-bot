from django.contrib import admin
from .models import Quiz, QuizQuestion, QuizAttempt, QuizAnswer


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'topic', 'mentor', 'questions_count', 'attempts_count', 'is_active', 'created_at')
    list_filter = ('mentor', 'is_active', 'created_at')
    search_fields = ('title', 'topic')

    def questions_count(self, obj):
        return obj.questions.count()
    questions_count.short_description = 'Questions'

    def attempts_count(self, obj):
        return obj.attempts.filter(finished_at__isnull=False).count()
    attempts_count.short_description = 'Attempts'


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'order', 'question_text_short', 'correct_answer')
    list_filter = ('quiz',)
    ordering = ('quiz', 'order')

    def question_text_short(self, obj):
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text
    question_text_short.short_description = 'Question'


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('student', 'quiz', 'score', 'total', 'percentage', 'started_at', 'finished_at')
    list_filter = ('quiz', 'finished_at')
    ordering = ('-finished_at',)

    def percentage(self, obj):
        if obj.total == 0:
            return '0%'
        return f'{round(obj.score / obj.total * 100)}%'
    percentage.short_description = '%'


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = ('get_student', 'get_quiz', 'question_short', 'selected_answer', 'correct_answer', 'is_correct')
    list_filter = ('attempt__quiz', 'attempt__student', 'is_correct')
    ordering = ('attempt', 'question__order')

    def get_student(self, obj):
        return obj.attempt.student
    get_student.short_description = 'Student'

    def get_quiz(self, obj):
        return obj.attempt.quiz
    get_quiz.short_description = 'Quiz'

    def question_short(self, obj):
        return f"Q{obj.question.order}"
    question_short.short_description = 'Question'

    def correct_answer(self, obj):
        return obj.question.correct_answer
    correct_answer.short_description = 'Correct'
