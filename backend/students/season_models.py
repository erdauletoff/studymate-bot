"""
Season and SeasonRating models for leaderboard management.
"""
from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta


class Season(models.Model):
    """
    Represents a rating season (e.g., monthly period).

    Features:
    - Automatic monthly seasons
    - Manual season creation by mentor
    - One active season per mentor at a time
    """
    mentor = models.ForeignKey(
        'mentors.Mentor',
        on_delete=models.CASCADE,
        related_name='seasons',
        verbose_name="Mentor"
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Season Name",
        help_text="e.g., 'Январь 2026', 'Семестр 1'"
    )
    start_date = models.DateField(verbose_name="Start Date")
    end_date = models.DateField(verbose_name="End Date")
    is_active = models.BooleanField(
        default=True,
        verbose_name="Is Active",
        help_text="Only one season can be active at a time per mentor"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Season"
        verbose_name_plural = "Seasons"
        ordering = ['-start_date']
        constraints = [
            # Only one active season per mentor
            models.UniqueConstraint(
                fields=['mentor', 'is_active'],
                condition=models.Q(is_active=True),
                name='one_active_season_per_mentor'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.mentor.name})"

    def is_current(self):
        """Check if this season is currently running"""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date

    def save(self, *args, **kwargs):
        """Ensure only one active season per mentor"""
        if self.is_active:
            # Deactivate other active seasons for this mentor
            Season.objects.filter(
                mentor=self.mentor,
                is_active=True
            ).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create_current_season(cls, mentor):
        """
        Get or create the current month's season for a mentor.
        Auto-creates monthly seasons.
        """
        today = timezone.now().date()

        # Try to find active season
        active_season = cls.objects.filter(
            mentor=mentor,
            is_active=True,
            start_date__lte=today,
            end_date__gte=today
        ).first()

        if active_season:
            return active_season

        # Create new season for current month
        start_of_month = today.replace(day=1)

        # Calculate last day of month
        if today.month == 12:
            end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

        # Generate season name
        month_names_ru = [
            'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
        ]
        season_name = f"{month_names_ru[today.month - 1]} {today.year}"

        # Create season
        season = cls.objects.create(
            mentor=mentor,
            name=season_name,
            start_date=start_of_month,
            end_date=end_of_month,
            is_active=True
        )

        return season

    @classmethod
    def get_or_create_season_for_date(cls, mentor, target_date):
        """
        Get or create season for a specific date (not necessarily today).
        Used when recording quiz attempts to ensure they go to the correct season.

        Args:
            mentor: Mentor object
            target_date: date or datetime object for which to find/create season

        Returns:
            Season object covering the target_date
        """
        # Convert datetime to date if needed
        if hasattr(target_date, 'date'):
            target_date = target_date.date()

        # Try to find existing season covering this date
        existing_season = cls.objects.filter(
            mentor=mentor,
            start_date__lte=target_date,
            end_date__gte=target_date
        ).first()

        if existing_season:
            return existing_season

        # Create new season for target month
        start_of_month = target_date.replace(day=1)

        # Calculate last day of month
        if target_date.month == 12:
            end_of_month = target_date.replace(year=target_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = target_date.replace(month=target_date.month + 1, day=1) - timedelta(days=1)

        # Generate season name
        month_names_ru = [
            'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
        ]
        season_name = f"{month_names_ru[target_date.month - 1]} {target_date.year}"

        # Check if this should be the active season (only if it covers today)
        today = timezone.now().date()
        is_active = (start_of_month <= today <= end_of_month)

        # Create season
        season = cls.objects.create(
            mentor=mentor,
            name=season_name,
            start_date=start_of_month,
            end_date=end_of_month,
            is_active=is_active
        )

        return season


class SeasonRating(models.Model):
    """
    Student's rating within a specific season.

    This is a cached/denormalized table for performance.
    Updated when quiz attempts are completed.
    """
    season = models.ForeignKey(
        Season,
        on_delete=models.CASCADE,
        related_name='ratings',
        verbose_name="Season"
    )
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='season_ratings',
        verbose_name="Student"
    )

    # Rating metrics (same formula as global leaderboard)
    total_ranked_quizzes = models.IntegerField(
        default=0,
        verbose_name="Total Ranked Quizzes"
    )
    total_score = models.IntegerField(
        default=0,
        verbose_name="Total Score"
    )
    total_possible = models.IntegerField(
        default=0,
        verbose_name="Total Possible Score"
    )
    avg_percentage = models.FloatField(
        default=0.0,
        verbose_name="Average Percentage"
    )
    rating_score = models.FloatField(
        default=0.0,
        verbose_name="Rating Score",
        help_text="Calculated: avg_percentage × (1 + min(total_quizzes/10, 1) × 0.5)"
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Season Rating"
        verbose_name_plural = "Season Ratings"
        ordering = ['-rating_score']
        unique_together = ['season', 'student']

    def __str__(self):
        return f"{self.student} - {self.season.name}: {self.rating_score:.1f}"

    def recalculate(self):
        """
        Recalculate rating based on quiz attempts in this season.
        Uses the same formula as global leaderboard.
        """
        from backend.quizzes.models import QuizAttempt
        from django.db.models import F
        from datetime import datetime, time

        # Convert season dates to datetime with timezone for proper comparison
        season_start = timezone.make_aware(
            datetime.combine(self.season.start_date, time.min)
        )
        season_end = timezone.make_aware(
            datetime.combine(self.season.end_date, time.max)
        )

        # Get valid ranked attempts in this season
        # Only count attempts that:
        # 1. Are for ranked quizzes
        # 2. Were completed (finished_at is not null)
        # 3. Started within the season period
        # 4. Started before the quiz expired (if available_until is set)
        valid_attempts = QuizAttempt.objects.filter(
            student=self.student,
            quiz__mentor=self.season.mentor,
            quiz__quiz_type='ranked',
            finished_at__isnull=False,
            started_at__gte=season_start,
            started_at__lte=season_end,
            quiz__available_until__isnull=False  # Only quizzes with available_until set
        ).filter(
            started_at__lt=F('quiz__available_until')
        )

        if not valid_attempts.exists():
            self.total_ranked_quizzes = 0
            self.total_score = 0
            self.total_possible = 0
            self.avg_percentage = 0.0
            self.rating_score = 0.0
            self.save()
            return

        # Calculate metrics
        from django.db.models import Sum

        self.total_ranked_quizzes = valid_attempts.values('quiz').distinct().count()

        aggregates = valid_attempts.aggregate(
            total_score=Sum('score'),
            total_possible=Sum('total')
        )
        self.total_score = aggregates['total_score'] or 0
        self.total_possible = aggregates['total_possible'] or 0

        # Average percentage
        self.avg_percentage = round((self.total_score / self.total_possible * 100), 1) if self.total_possible > 0 else 0

        # Rating formula: avg_percentage × (1 + min(total_quizzes/10, 1) × 0.5)
        activity_bonus = min(self.total_ranked_quizzes / 10, 1) * 0.5
        self.rating_score = round(self.avg_percentage * (1 + activity_bonus), 1)

        self.save()

    @classmethod
    def get_or_create_for_student(cls, student, season):
        """Get or create rating record for student in season"""
        rating, created = cls.objects.get_or_create(
            season=season,
            student=student,
            defaults={
                'total_ranked_quizzes': 0,
                'total_score': 0,
                'total_possible': 0,
                'avg_percentage': 0.0,
                'rating_score': 0.0
            }
        )
        return rating
