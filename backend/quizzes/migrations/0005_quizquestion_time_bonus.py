from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quizzes', '0004_quiz_quizzes_qui_mentor__27d7d8_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='quizquestion',
            name='time_bonus',
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]

