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
from backend.students.season_models import Season, SeasonRating
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
def update_student_full_name(telegram_id: int, full_name: str):
    """Update student's full name and mark profile as completed"""
    try:
        student = Student.objects.get(telegram_id=telegram_id)
        student.full_name = full_name.strip()
        student.profile_completed = True
        student.save()
        return student
    except Student.DoesNotExist:
        return None


@sync_to_async
def is_student_profile_completed(telegram_id: int) -> bool:
    """Check if student has completed their profile"""
    try:
        student = Student.objects.get(telegram_id=telegram_id)
        return student.profile_completed
    except Student.DoesNotExist:
        return False


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


@sync_to_async
def get_student_by_id(student_id: int):
    try:
        return Student.objects.get(id=student_id)
    except Student.DoesNotExist:
        return None


@sync_to_async
def get_students_by_mentor(mentor):
    """Get all students for a given mentor"""
    return list(Student.objects.filter(mentor=mentor))


@sync_to_async
def get_student_quiz_stats(telegram_id: int):
    """Get student's quiz statistics"""
    try:
        student = Student.objects.get(telegram_id=telegram_id)
        return student.get_quiz_stats()
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
    if not topics:
        return {}

    from django.db.models import Count
    topic_ids = [topic.id for topic in topics]
    counts = (
        Material.objects
        .filter(topic_id__in=topic_ids)
        .values('topic_id')
        .annotate(count=Count('id'))
    )
    return {item['topic_id']: item['count'] for item in counts}


# ==================== QUESTIONS ====================

@sync_to_async
def create_question(mentor, text: str, student=None):
    question = Question.objects.create(mentor=mentor, text=text, student=student)
    question.refresh_from_db()
    return question


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


@sync_to_async
def get_question_by_id(question_id: int):
    try:
        return Question.objects.get(id=question_id)
    except Question.DoesNotExist:
        return None


@sync_to_async
def add_question_reply(question_id: int, reply_text: str) -> bool:
    """Add or append reply to a question"""
    try:
        question = Question.objects.get(id=question_id)
        if question.reply_text:
            # Append to existing reply
            question.reply_text += f"\n\n---\n\n{reply_text}"
        else:
            # First reply
            question.reply_text = reply_text
        question.is_answered = True
        question.replied_at = timezone.now()
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
def get_quizzes_by_mentor(mentor, include_inactive: bool = False):
    qs = Quiz.objects.filter(mentor=mentor)
    if not include_inactive:
        qs = qs.filter(is_active=True)
    return list(qs)


@sync_to_async
def get_active_quizzes_by_mentor(mentor):
    """Get active quizzes for students"""
    return list(Quiz.objects.filter(mentor=mentor, is_active=True))


@sync_to_async
def get_ranked_quizzes_by_mentor(mentor):
    """Get active ranked quizzes (exam mode) for students"""
    from django.utils import timezone
    now = timezone.now()
    return list(Quiz.objects.filter(
        mentor=mentor,
        is_active=True,
        quiz_type='ranked',
        available_until__gt=now
    ))


@sync_to_async
def get_practice_quizzes_by_mentor(mentor):
    """Get practice quizzes + expired ranked quizzes (review mode) for students"""
    from django.utils import timezone
    now = timezone.now()
    from django.db.models import Q

    # Practice quizzes OR expired ranked quizzes
    return list(Quiz.objects.filter(
        mentor=mentor,
        is_active=True
    ).filter(
        Q(quiz_type='practice') |
        Q(quiz_type='ranked', available_until__lte=now)
    ))


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
def set_quiz_active(quiz_id: int, is_active: bool) -> bool:
    updated = Quiz.objects.filter(id=quiz_id).update(is_active=is_active)
    return updated > 0


@sync_to_async
def archive_quizzes_by_title(mentor, title: str) -> int:
    """Archive all quizzes for mentor with the same title (case-insensitive)."""
    return Quiz.objects.filter(mentor=mentor, title__iexact=title).update(is_active=False)


@sync_to_async
def quiz_title_exists(mentor, title: str) -> bool:
    return Quiz.objects.filter(mentor=mentor, title__iexact=title).exists()


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
def delete_quiz_question(question_id: int) -> bool:
    deleted, _ = QuizQuestion.objects.filter(id=question_id).delete()
    return deleted > 0


@sync_to_async
def update_quiz_question(question_id: int, **fields) -> bool:
    updated = QuizQuestion.objects.filter(id=question_id).update(**fields)
    return updated > 0


@sync_to_async
def get_next_quiz_question_order(quiz) -> int:
    from django.db.models import Max
    result = QuizQuestion.objects.filter(quiz=quiz).aggregate(max_order=Max('order'))
    return (result['max_order'] or 0) + 1


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

        # Update student's learning streak
        student = attempt.student
        from datetime import timedelta
        today = timezone.localdate()  # Use timezone-aware date

        # If this is the first quiz ever
        if student.last_quiz_date is None:
            student.current_streak = 1
            student.longest_streak = 1
            student.last_quiz_date = today
            student.save()
        # If already completed a quiz today, streak doesn't change
        elif student.last_quiz_date == today:
            pass
        # If completed yesterday, increment streak
        else:
            yesterday = today - timedelta(days=1)
            if student.last_quiz_date == yesterday:
                student.current_streak += 1
                if student.current_streak > student.longest_streak:
                    student.longest_streak = student.current_streak
            else:
                # Streak broken, reset to 1
                student.current_streak = 1
            student.last_quiz_date = today
            student.save()

        # Update season rating (only for ranked quizzes)
        if attempt.quiz.quiz_type == 'ranked':
            mentor = attempt.quiz.mentor
            # Use the date when the attempt was started, not today's date
            # This ensures attempts go to the correct season
            season = Season.get_or_create_season_for_date(mentor, attempt.started_at)
            rating = SeasonRating.get_or_create_for_student(student, season)
            rating.recalculate()

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
    return attempts.first()


@sync_to_async
def get_student_attempt(student, quiz):
    """Get student's latest attempt for a quiz"""
    try:
        return QuizAttempt.objects.filter(student=student, quiz=quiz).order_by('-started_at').first()
    except QuizAttempt.DoesNotExist:
        return None


@sync_to_async
def get_student_first_attempt(student, quiz):
    """Get student's first attempt for a quiz (used for statistics)"""
    try:
        return QuizAttempt.objects.filter(student=student, quiz=quiz, finished_at__isnull=False).order_by('started_at').first()
    except QuizAttempt.DoesNotExist:
        return None


@sync_to_async
def has_student_attempted(student, quiz) -> bool:
    """Check if student has already attempted this quiz"""
    return QuizAttempt.objects.filter(student=student, quiz=quiz, finished_at__isnull=False).exists()


@sync_to_async
def get_quiz_attempts(quiz):
    """Get all attempts for export (includes all attempts, not just first)"""
    return list(QuizAttempt.objects.filter(
        quiz=quiz,
        finished_at__isnull=False
    ).select_related('student').order_by('finished_at'))


@sync_to_async
def get_quiz_average_score(quiz):
    """Get average score from first attempts only"""
    from django.db.models import Avg, Min, Q

    # Get first attempt time for each student
    first_attempts = QuizAttempt.objects.filter(
        quiz=quiz,
        finished_at__isnull=False
    ).values('student_id').annotate(
        first_started=Min('started_at')
    )

    if not first_attempts:
        return 0

    # Build OR condition for all (student_id, started_at) pairs
    conditions = Q()
    for fa in first_attempts:
        conditions |= Q(student_id=fa['student_id'], started_at=fa['first_started'])

    # Single query to get all first attempts
    result = QuizAttempt.objects.filter(
        quiz=quiz,
        finished_at__isnull=False
    ).filter(conditions).aggregate(avg_score=Avg('score'))

    return result['avg_score'] or 0


@sync_to_async
def get_quiz_stats(quiz):
    """Get quiz statistics based on first attempts only"""
    from django.db.models import Avg, Count, Min, Q

    # Get first attempt time for each student
    first_attempts = QuizAttempt.objects.filter(
        quiz=quiz,
        finished_at__isnull=False
    ).values('student_id').annotate(
        first_started=Min('started_at')
    )

    # Calculate stats from first attempts only
    if first_attempts:
        # Build OR condition for all (student_id, started_at) pairs
        conditions = Q()
        for fa in first_attempts:
            conditions |= Q(student_id=fa['student_id'], started_at=fa['first_started'])

        # Single query to get stats from all first attempts
        attempt_stats = QuizAttempt.objects.filter(
            quiz=quiz,
            finished_at__isnull=False
        ).filter(conditions).aggregate(
            attempts=Count('id'),
            avg_score=Avg('score')
        )
        count = attempt_stats['attempts'] or 0
        avg = attempt_stats['avg_score'] or 0
    else:
        count = 0
        avg = 0

    questions_count = QuizQuestion.objects.filter(quiz=quiz).aggregate(
        questions=Count('id')
    )['questions']

    return {
        'attempts': count,
        'avg': round(avg, 1),
        'questions': questions_count
    }


@sync_to_async
def get_quiz_stats_by_ids(quiz_ids):
    """Batch stats for quiz lists (based on first attempts only)."""
    if not quiz_ids:
        return {}

    from django.db.models import Avg, Count, Min, Q

    # Get first attempts for each student in each quiz
    first_attempts_data = QuizAttempt.objects.filter(
        quiz_id__in=quiz_ids,
        finished_at__isnull=False
    ).values('quiz_id', 'student_id').annotate(
        first_started=Min('started_at')
    )

    # Build OR condition for all (quiz_id, student_id, started_at) tuples
    if first_attempts_data:
        conditions = Q()
        for fa in first_attempts_data:
            conditions |= Q(
                quiz_id=fa['quiz_id'],
                student_id=fa['student_id'],
                started_at=fa['first_started']
            )

        # Single query to get stats from all first attempts
        attempt_rows = QuizAttempt.objects.filter(
            quiz_id__in=quiz_ids,
            finished_at__isnull=False
        ).filter(conditions).values('quiz_id').annotate(
            attempts=Count('id'),
            avg_score=Avg('score')
        )
    else:
        attempt_rows = []

    question_rows = QuizQuestion.objects.filter(
        quiz_id__in=quiz_ids
    ).values('quiz_id').annotate(
        questions=Count('id')
    )

    attempt_map = {row['quiz_id']: row for row in attempt_rows}
    question_map = {row['quiz_id']: row['questions'] for row in question_rows}

    stats = {}
    for quiz_id in quiz_ids:
        attempt = attempt_map.get(quiz_id, {})
        avg = attempt.get('avg_score') or 0
        stats[quiz_id] = {
            'attempts': attempt.get('attempts', 0) or 0,
            'avg': round(avg, 1),
            'questions': question_map.get(quiz_id, 0) or 0
        }

    return stats


@sync_to_async
def get_quiz_top_students(quiz, limit=5):
    """Get top students based on first attempts only"""
    from django.db.models import Min, Q

    # Get first attempts for each student
    first_attempts_data = QuizAttempt.objects.filter(
        quiz=quiz,
        finished_at__isnull=False
    ).values('student_id').annotate(
        first_started=Min('started_at')
    )

    if not first_attempts_data:
        return []

    # Build OR condition for all (student_id, started_at) pairs
    conditions = Q()
    for fa in first_attempts_data:
        conditions |= Q(student_id=fa['student_id'], started_at=fa['first_started'])

    # Single query to get all first attempts
    first_attempts = QuizAttempt.objects.filter(
        quiz=quiz,
        finished_at__isnull=False
    ).filter(conditions).select_related('student').order_by('-score', 'finished_at')[:limit]

    return [(a.student, a.score, a.total) for a in first_attempts]


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


@sync_to_async
def delete_quiz_attempts(quiz):
    """Delete all attempts for a quiz (for restart)"""
    deleted_count = QuizAttempt.objects.filter(quiz=quiz).delete()[0]
    return deleted_count


@sync_to_async
def shuffle_quiz_questions(quiz):
    """Randomly shuffle the order of quiz questions"""
    import random
    questions = list(QuizQuestion.objects.filter(quiz=quiz))
    random.shuffle(questions)
    for i, question in enumerate(questions, 1):
        question.order = i
        question.save()
    return len(questions)


@sync_to_async
def get_global_leaderboard(mentor, limit=10):
    """
    Get global leaderboard for students based on RANKED quiz performance only.
    Returns list of (student, rating_score, avg_percentage, total_quizzes) ordered by rating.
    Only includes students who have completed at least one ranked quiz.

    Only counts attempts where:
    - quiz.quiz_type == 'ranked'
    - attempt.started_at < quiz.available_until

    Rating formula: avg_percentage × (1 + min(total_quizzes / 10, 1) × 0.5)
    This gives up to 50% bonus for activity (max at 10+ quizzes).
    """
    from django.db.models import F
    from collections import defaultdict

    # Get all valid ranked attempts in one query
    valid_attempts = QuizAttempt.objects.filter(
        quiz__mentor=mentor,
        quiz__quiz_type='ranked',
        finished_at__isnull=False,
        quiz__available_until__isnull=False
    ).filter(
        started_at__lt=F('quiz__available_until')
    ).select_related('student').values('student_id', 'quiz_id', 'score', 'total')

    # Group by student
    student_stats = defaultdict(lambda: {'quizzes': set(), 'total_score': 0, 'total_questions': 0})
    for attempt in valid_attempts:
        student_id = attempt['student_id']
        student_stats[student_id]['quizzes'].add(attempt['quiz_id'])
        student_stats[student_id]['total_score'] += attempt['score']
        student_stats[student_id]['total_questions'] += attempt['total']

    if not student_stats:
        return []

    # Get student objects
    student_ids = list(student_stats.keys())
    students_map = {s.id: s for s in Student.objects.filter(id__in=student_ids)}

    # Calculate ratings
    results = []
    for student_id, stats in student_stats.items():
        total_quizzes = len(stats['quizzes'])
        total_score = stats['total_score']
        total_questions = stats['total_questions']

        if total_questions == 0:
            continue

        avg_percentage = round((total_score / total_questions) * 100.0, 1)
        activity_bonus = min(total_quizzes / 10.0, 1.0) * 0.5
        rating_score = round(avg_percentage * (1 + activity_bonus), 1)

        student = students_map.get(student_id)
        if student:
            results.append((student, rating_score, avg_percentage, total_quizzes))

    # Sort by rating score descending
    results.sort(key=lambda x: (-x[1], -x[2], -x[3]))

    return results[:limit]


def is_exam_mode(quiz) -> bool:
    """Check if quiz is currently in exam mode (ranked + before deadline)"""
    if quiz.quiz_type != 'ranked':
        return False
    if not quiz.available_until:
        return False
    from django.utils import timezone
    return timezone.now() < quiz.available_until


def is_practice_mode(quiz) -> bool:
    """Check if quiz is in practice mode (practice OR expired ranked)"""
    if quiz.quiz_type == 'practice':
        return True
    if quiz.quiz_type == 'ranked' and quiz.available_until:
        from django.utils import timezone
        return timezone.now() >= quiz.available_until
    return False


@sync_to_async
def can_attempt_quiz(student, quiz) -> tuple[bool, str]:
    """
    Check if student can attempt quiz.
    Returns (can_attempt: bool, reason: str)
    reason is empty string if can attempt, otherwise contains error key for translation
    """
    from django.utils import timezone
    now = timezone.now()

    # Check if quiz is in exam mode
    if is_exam_mode(quiz):
        # Ranked quiz in exam mode
        # Check if available_from has passed
        if quiz.available_from and now < quiz.available_from:
            return False, "quiz_not_started"

        # Check if deadline hasn't passed
        if now >= quiz.available_until:
            return False, "quiz_expired"

        # Check attempt limit
        attempts_count = QuizAttempt.objects.filter(
            student=student,
            quiz=quiz,
            finished_at__isnull=False
        ).count()

        if attempts_count >= quiz.max_attempts:
            return False, "quiz_max_attempts"

        return True, ""

    # Practice mode - always allowed
    return True, ""


@sync_to_async
def get_student_rank(student, mentor):
    """
    Get student's rank in the global leaderboard based on RANKED quiz performance only.
    Returns (rank, rating_score, avg_percentage, total_quizzes) or None if student hasn't completed any ranked quiz.

    Only counts attempts where:
    - quiz.quiz_type == 'ranked'
    - attempt.started_at < quiz.available_until

    Rating formula: avg_percentage × (1 + min(total_quizzes / 10, 1) × 0.5)
    """
    from django.db.models import F
    from collections import defaultdict

    # Get all valid ranked attempts in one query
    valid_attempts = QuizAttempt.objects.filter(
        quiz__mentor=mentor,
        quiz__quiz_type='ranked',
        finished_at__isnull=False,
        quiz__available_until__isnull=False
    ).filter(
        started_at__lt=F('quiz__available_until')
    ).values('student_id', 'quiz_id', 'score', 'total')

    # Group by student
    student_stats = defaultdict(lambda: {'quizzes': set(), 'total_score': 0, 'total_questions': 0})
    for attempt in valid_attempts:
        student_id = attempt['student_id']
        student_stats[student_id]['quizzes'].add(attempt['quiz_id'])
        student_stats[student_id]['total_score'] += attempt['score']
        student_stats[student_id]['total_questions'] += attempt['total']

    # Calculate ratings
    student_data = []
    for student_id, stats in student_stats.items():
        total_quizzes = len(stats['quizzes'])
        total_score = stats['total_score']
        total_questions = stats['total_questions']

        if total_questions == 0:
            continue

        avg_percentage = round((total_score / total_questions) * 100.0, 1)
        activity_bonus = min(total_quizzes / 10.0, 1.0) * 0.5
        rating_score = round(avg_percentage * (1 + activity_bonus), 1)

        student_data.append({
            'id': student_id,
            'rating_score': rating_score,
            'avg_percentage': avg_percentage,
            'total_quizzes': total_quizzes
        })

    # Sort by rating score descending
    student_data.sort(key=lambda x: (-x['rating_score'], -x['avg_percentage'], -x['total_quizzes']))

    # Find student's position
    for rank, s_data in enumerate(student_data, 1):
        if s_data['id'] == student.id:
            return (rank, s_data['rating_score'], s_data['avg_percentage'], s_data['total_quizzes'])

    return None

# ==================== SEASONS ====================

@sync_to_async
def get_current_season(mentor):
    """Get or create current season for mentor"""
    return Season.get_or_create_current_season(mentor)


@sync_to_async
def get_season_leaderboard(season, limit=100):
    """
    Get leaderboard for a specific season.
    Returns list of (student, rating_score, avg_percentage, total_quizzes)
    """
    ratings = SeasonRating.objects.filter(
        season=season,
        rating_score__gt=0
    ).select_related('student').order_by('-rating_score')[:limit]

    return [
        (r.student, r.rating_score, r.avg_percentage, r.total_ranked_quizzes)
        for r in ratings
    ]


@sync_to_async
def update_season_rating(student, quiz_attempt):
    """
    Update student's rating in current season after quiz completion.
    Called after finish_quiz_attempt.
    """
    if quiz_attempt.quiz.quiz_type != 'ranked':
        return  # Only ranked quizzes affect season rating

    # Get current season
    mentor = quiz_attempt.quiz.mentor
    season = Season.get_or_create_current_season(mentor)

    # Get or create rating record
    rating = SeasonRating.get_or_create_for_student(student, season)

    # Recalculate rating
    rating.recalculate()


@sync_to_async
def get_student_season_rank(student, season):
    """
    Get student's rank in a specific season.
    Returns tuple: (rank, rating_score, avg_percentage, total_quizzes) or None
    """
    try:
        rating = SeasonRating.objects.get(season=season, student=student)
        
        # Count how many students have higher rating
        higher_count = SeasonRating.objects.filter(
            season=season,
            rating_score__gt=rating.rating_score
        ).count()
        
        rank = higher_count + 1
        return (rank, rating.rating_score, rating.avg_percentage, rating.total_ranked_quizzes)
    except SeasonRating.DoesNotExist:
        return None


@sync_to_async
def get_all_seasons(mentor):
    """Get all seasons for mentor, ordered by start date descending"""
    return list(Season.objects.filter(mentor=mentor).order_by('-start_date'))
