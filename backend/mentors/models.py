from django.db import models


class Mentor(models.Model):
    telegram_id = models.BigIntegerField(unique=True, verbose_name="Telegram ID")
    name = models.CharField(max_length=100, verbose_name="Name")
    group_chat_id = models.BigIntegerField(verbose_name="Group Chat ID")
    language = models.CharField(max_length=5, default='ru', verbose_name="Language")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mentor"
        verbose_name_plural = "Mentors"

    def __str__(self):
        return self.name
