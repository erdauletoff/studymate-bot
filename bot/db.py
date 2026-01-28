import os
import sys
import django
from asgiref.sync import sync_to_async
from datetime import timedelta
from django.utils import timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.core.settings')
django.setup()

from backend.mentors.models import Mentor
from backend.materials.models import Topic, Material
from backend.students.models import Student
from backend.questions.models import Question
from backend.downloads.models import Download
from backend.quizzes.models import Quiz, QuizQuestion, QuizAttempt, QuizAnswer


# ==================== LANGUAGE ====================

@sync_to_async
def get_user_language(telegram_id: int) -> str:
    """Get user language (mentor or student)"""
    try:
        mentor = Mentor.objects.get(telegram_id=telegram_id)
        return mentor.language
    except Mentor.DoesNotExist:
        pass
    
    try:
        student = Student.objects.get(telegram_id=telegram_id)
        return student.language
    except Student.DoesNotExist:
        pass
    
    return "ru"  # default


@sync_to_async
def set_user_language(telegram_id: int, language: str) -> bool:
    """Set user language (mentor or student)"""
    try:
        mentor = Mentor.objects.get(telegram_id=telegram_id)
        mentor.language = language
        mentor.save()
        return True
    except Mentor.DoesNotExist:
        pass
    
    try:
        student = Student.objects.get(telegram_id=telegram_id)
        student.language = language
        student.save()
        return True
    except Student.DoesNotExist:
        pass
    
    return False


# ==================== MENTORS ====================

@sync_to_async
def get_mentor_by_telegram_id(telegram_id: int):
    try:
        return Mentor.objects.get(telegram_id=telegram_id, is_active=True)
    except Mentor.DoesNotExist:
        return None


@sync_to_async
def get_all_mentors():
    return list(Mentor.objects.filter(is_active=True))


@sync_to_async
def is_mentor(telegram_id: int) -> bool:
    return Mentor.objects.filter(telegram_id=telegram_id, is_active=True).exists()


# ==================== STUDENTS ====================

@sync_to_async
def get_or_create_student(telegram_id: int, username: str = None, first_name: str = '', last_name: str = '', language: str = 'ru'):
    student, created = Student.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'language': language
        }
    )
    if not created:
        student.username = username
        student.first_name = first_name
        student.last_name = last_name
        student.save()
    return student


@sync_to_async
def assign_student_to_mentor(student, mentor):
    student.mentor = mentor
    student.save()


@sync_to_async
def get_student_mentor(telegram_id: int):
    try:
        student = Student.objects.get(telegram_id=telegram_id)
        return student.mentor
    except Student.DoesNotExist:
        return None


@sync_to_async
def get_student_by_telegram_id(telegram_id: int):
    try:
        return Student.objects.get(telegram_id=telegram_id)
    except Student.DoesNotExist:
        return None


# ==================== TOPICS ====================

@sync_to_async
def get_topics_by_mentor(mentor):
    return list(Topic.objects.filter(mentor=mentor))


@sync_to_async
def get_topic_by_id(topic_id: int):
    try:
        return Topic.objects.get(id=topic_id)
    except Topic.DoesNotExist:
        return None


@sync_to_async
def create_topic(mentor, name: str):
    return Topic.objects.create(mentor=mentor, name=name)


@sync_to_async
def delete_topic(topic_id: int):
    try:
        topic = Topic.objects.get(id=topic_id)
        name = topic.name
        topic.delete()
        return name
    except Topic.DoesNotExist:
        return None


# ==================== MATERIALS ====================

@sync_to_async
def get_materials_by_topic(topic):
    return list(Material.objects.filter(topic=topic))


@sync_to_async
def get_material_by_id(material_id: int):
    try:
        return Material.objects.get(id=material_id)
    except Material.DoesNotExist:
        return None


@sync_to_async
def add_material(topic, title: str, file_id: str, file_name: str = ''):
    return Material.objects.create(
        topic=topic,
        title=title,
        file_id=file_id,
        file_name=file_name
    )


@sync_to_async
def delete_material(material_id: int) -> bool:
    try:
        Material.objects.get(id=material_id).delete()
        return True
    except Material.DoesNotExist:
        return False


@sync_to_async
def get_materials_count_by_topics(topics) -> dict:
    result = {}
    for topic in topics:
        result[topic.id] = Material.objects.filter(topic=topic).count()
    return result


# ==================== QUESTIONS ====================

@sync_to_async
def create_question(mentor, text: str, student=None):
    return Question.objects.create(mentor=mentor, text=text, student=student)


@sync_to_async
def get_unanswered_questions(mentor):
    return list(Question.objects.filter(mentor=mentor, is_answered=False))


@sync_to_async
def mark_question_answered(question_id: int) -> bool:
    try:
        question = Question.objects.get(id=question_id)
        question.is_answered = True
        question.save()
        return True
    except Question.DoesNotExist:
        return False


# ==================== DOWNLOADS ====================

@sync_to_async
def record_download(student, material):
    return Download.objects.create(student=student, material=material)


# ==================== STATISTICS ====================

@sync_to_async
def get_mentor_stats(mentor):
    now = timezone.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    students_count = Student.objects.filter(mentor=mentor).count()
    topics_count = Topic.objects.filter(mentor=mentor).count()
    materials_count = Material.objects.filter(topic__mentor=mentor).count()

    questions_total = Question.objects.filter(mentor=mentor).count()
    questions_unanswered = Question.objects.filter(mentor=mentor, is_answered=False).count()

    active_today = Download.objects.filter(
        material__topic__mentor=mentor,
        downloaded_at__gte=today
    ).values('student').distinct().count()

    active_week = Download.objects.filter(
        material__topic__mentor=mentor,
        downloaded_at__gte=week_ago
    ).values('student').distinct().count()

    from django.db.models import Count
    popular = Material.objects.filter(
        topic__mentor=mentor
    ).annotate(
        download_count=Count('downloads')
    ).order_by('-download_count')[:3]

    popular_list = [(m.title, m.download_count) for m in popular]

    return {
        'students': students_count,
        'topics': topics_count,
        'materials': materials_count,
        'questions_total': questions_total,
        'questions_unanswered': questions_unanswered,
        'active_today': active_today,
        'active_week': active_week,
        'popular': popular_list
    }


# ==================== QUIZZES ====================

@sync_to_async
def create_quiz(mentor, title, topic=None):
    return Quiz.objects.create(mentor=mentor, title=title, topic=topic)


@sync_to_async
def get_quizzes_by_mentor(mentor):
    return list(Quiz.objects.filter(mentor=mentor, is_active=True))


@sync_to_async
def get_active_quizzes_by_mentor(mentor):
    """Get active quizzes for students"""
    return list(Quiz.objects.filter(mentor=mentor, is_active=True))


@sync_to_async
def get_quiz_by_id(quiz_id: int):
    try:
        return Quiz.objects.get(id=quiz_id)
    except Quiz.DoesNotExist:
        return None


@sync_to_async
def delete_quiz(quiz_id: int) -> bool:
    try:
        Quiz.objects.get(id=quiz_id).delete()
        return True
    except Quiz.DoesNotExist:
        return False


@sync_to_async
def create_quiz_question(quiz, question_text, option_a, option_b, option_c, option_d, correct_answer, order):
    return QuizQuestion.objects.create(
        quiz=quiz,
        question_text=question_text,
        option_a=option_a,
        option_b=option_b,
        option_c=option_c,
        option_d=option_d,
        correct_answer=correct_answer,
        order=order
    )


@sync_to_async
def get_questions_by_quiz(quiz):
    return list(QuizQuestion.objects.filter(quiz=quiz).order_by('order'))


@sync_to_async
def get_question_by_id(question_id: int):
    try:
        return QuizQuestion.objects.get(id=question_id)
    except QuizQuestion.DoesNotExist:
        return None


@sync_to_async
def create_quiz_attempt(student, quiz):
    total = QuizQuestion.objects.filter(quiz=quiz).count()
    return QuizAttempt.objects.create(student=student, quiz=quiz, total=total)


@sync_to_async
def finish_quiz_attempt(attempt_id: int, score: int):
    try:
        attempt = QuizAttempt.objects.get(id=attempt_id)
        attempt.score = score
        attempt.finished_at = timezone.now()
        attempt.save()
        return attempt
    except QuizAttempt.DoesNotExist:
        return None


@sync_to_async
def get_student_best_attempt(student, quiz):
    attempts = QuizAttempt.objects.filter(
        student=student,
        quiz=quiz,
        finished_at__isnull=False
    ).order_by('-score')
    return attempts.first() if attempts.exists() else None


@sync_to_async
def get_student_attempt(student, quiz):
    """Get student's attempt for a quiz (only one attempt allowed)"""
    try:
        return QuizAttempt.objects.get(student=student, quiz=quiz)
    except QuizAttempt.DoesNotExist:
        return None


@sync_to_async
def has_student_attempted(student, quiz) -> bool:
    """Check if student has already attempted this quiz"""
    return QuizAttempt.objects.filter(student=student, quiz=quiz, finished_at__isnull=False).exists()


@sync_to_async
def get_quiz_attempts(quiz):
    return list(QuizAttempt.objects.filter(quiz=quiz, finished_at__isnull=False))


@sync_to_async
def get_quiz_average_score(quiz):
    from django.db.models import Avg
    result = QuizAttempt.objects.filter(
        quiz=quiz,
        finished_at__isnull=False
    ).aggregate(avg_score=Avg('score'))
    return result['avg_score'] or 0


@sync_to_async
def get_quiz_stats(quiz):
    from django.db.models import Avg
    attempts = QuizAttempt.objects.filter(quiz=quiz, finished_at__isnull=False)
    count = attempts.count()
    avg = attempts.aggregate(avg_score=Avg('score'))['avg_score'] or 0
    questions_count = QuizQuestion.objects.filter(quiz=quiz).count()
    return {
        'attempts': count,
        'avg': round(avg, 1),
        'questions': questions_count
    }


@sync_to_async
def get_quiz_top_students(quiz, limit=5):
    attempts = QuizAttempt.objects.filter(
        quiz=quiz,
        finished_at__isnull=False
    ).select_related('student').order_by('-score', 'finished_at')[:limit]
    return [(a.student, a.score, a.total) for a in attempts]


@sync_to_async
def save_quiz_answer(attempt, question, selected_answer):
    is_correct = selected_answer == question.correct_answer
    return QuizAnswer.objects.create(
        attempt=attempt,
        question=question,
        selected_answer=selected_answer,
        is_correct=is_correct
    )


@sync_to_async
def get_attempt_by_id(attempt_id: int):
    try:
        return QuizAttempt.objects.get(id=attempt_id)
    except QuizAttempt.DoesNotExist:
        return None


@sync_to_async
def get_attempt_answers(attempt):
    """Get all answers for an attempt with questions for review"""
    return list(QuizAnswer.objects.filter(attempt=attempt).select_related('question').order_by('question__order'))
