# Data migration: populate earliest_attempt_at for existing SeasonRating records

from django.db import migrations, models


def populate_earliest_attempt_at(apps, schema_editor):
    """Recalculate earliest_attempt_at for all existing SeasonRating records."""
    SeasonRating = apps.get_model('students', 'SeasonRating')
    QuizAttempt = apps.get_model('quizzes', 'QuizAttempt')
    Season = apps.get_model('students', 'Season')
    from datetime import datetime, time, timedelta

    for rating in SeasonRating.objects.filter(rating_score__gt=0):
        season = rating.season
        # Build season datetime boundaries
        try:
            from django.utils import timezone as tz
            season_start = tz.make_aware(datetime.combine(season.start_date, time.min))
            season_end = tz.make_aware(datetime.combine(season.end_date, time.max))
        except Exception:
            continue

        earliest = QuizAttempt.objects.filter(
            student_id=rating.student_id,
            quiz__mentor_id=season.mentor_id,
            quiz__quiz_type='ranked',
            finished_at__isnull=False,
            started_at__gte=season_start,
            started_at__lte=season_end,
            quiz__available_until__isnull=False,
        ).filter(
            started_at__lt=models.F('quiz__available_until')
        ).order_by('finished_at').values_list('finished_at', flat=True).first()

        if earliest:
            rating.earliest_attempt_at = earliest
            rating.save(update_fields=['earliest_attempt_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0007_add_earliest_attempt_at'),
        ('quizzes', '__latest__'),
    ]

    operations = [
        migrations.RunPython(populate_earliest_attempt_at, migrations.RunPython.noop),
    ]
