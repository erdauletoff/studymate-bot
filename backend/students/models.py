from django.db import models
from backend.mentors.models import Mentor

# Import season models to ensure Django discovers them
from .season_models import Season, SeasonRating  # noqa: F401


class Student(models.Model):
    telegram_id = models.BigIntegerField(unique=True, verbose_name="Telegram ID")
    username = models.CharField(max_length=100, blank=True, null=True, verbose_name="Username")
    first_name = models.CharField(max_length=100, blank=True, verbose_name="First Name")
    last_name = models.CharField(max_length=100, blank=True, verbose_name="Last Name")
    full_name = models.CharField(max_length=200, blank=True, verbose_name="Full Name (Self-entered)")
    profile_completed = models.BooleanField(default=False, verbose_name="Profile Completed")
    mentor = models.ForeignKey(Mentor, on_delete=models.SET_NULL, null=True, related_name='students')
    language = models.CharField(max_length=5, default='ru', verbose_name="Language")
    joined_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)

    # Learning streak fields
    current_streak = models.IntegerField(default=0, verbose_name="Current Streak (days)")
    longest_streak = models.IntegerField(default=0, verbose_name="Longest Streak (days)")
    last_quiz_date = models.DateField(null=True, blank=True, verbose_name="Last Quiz Date")

    class Meta:
        verbose_name = "Student"
        verbose_name_plural = "Students"
        indexes = [
            models.Index(fields=['mentor', 'joined_at']),
        ]

    def __str__(self):
        if self.full_name:
            return self.full_name
        if self.username:
            return f"@{self.username}"
        return f"{self.first_name} {self.last_name}".strip() or str(self.telegram_id)

    def get_display_name(self):
        """Returns the best available name for display"""
        return self.full_name or f"{self.first_name} {self.last_name}".strip() or self.username or str(self.telegram_id)

    def get_quiz_stats(self):
        """
        Calculate student's quiz statistics.
        Returns dict with: total_quizzes, total_ranked, total_practice, avg_score, best_score
        """
        from django.db.models import Avg, Sum, Max

        # All finished attempts
        attempts = self.quiz_attempts.filter(finished_at__isnull=False)

        if not attempts.exists():
            return {
                'total_quizzes': 0,
                'total_ranked': 0,
                'total_practice': 0,
                'avg_score': 0,
                'avg_percentage': 0,
                'best_score': 0,
                'best_total': 0,
                'best_percentage': 0
            }

        # Count unique quizzes
        total_quizzes = attempts.values('quiz').distinct().count()

        # Count by type
        ranked_attempts = attempts.filter(quiz__quiz_type='ranked')
        practice_attempts = attempts.filter(quiz__quiz_type='practice')
        total_ranked = ranked_attempts.values('quiz').distinct().count()
        total_practice = practice_attempts.values('quiz').distinct().count()

        # Calculate average score (raw score)
        avg_score = attempts.aggregate(avg=Avg('score'))['avg'] or 0

        # Calculate average percentage using DB aggregation
        aggregates = attempts.aggregate(
            total_score=Sum('score'),
            total_possible=Sum('total')
        )
        total_score = aggregates['total_score'] or 0
        total_possible = aggregates['total_possible'] or 0
        avg_percentage = round((total_score / total_possible * 100), 1) if total_possible > 0 else 0

        # Get best result
        best_attempt = attempts.order_by('-score').first()
        best_score = best_attempt.score if best_attempt else 0
        best_total = best_attempt.total if best_attempt else 1
        best_percentage = round((best_score / best_total * 100), 1) if best_total > 0 else 0

        return {
            'total_quizzes': total_quizzes,
            'total_ranked': total_ranked,
            'total_practice': total_practice,
            'avg_score': round(avg_score, 1),
            'avg_percentage': avg_percentage,
            'best_score': best_score,
            'best_total': best_total,
            'best_percentage': best_percentage
        }
