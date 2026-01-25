from django.db import models
from backend.mentors.models import Mentor


class Student(models.Model):
    telegram_id = models.BigIntegerField(unique=True, verbose_name="Telegram ID")
    username = models.CharField(max_length=100, blank=True, null=True, verbose_name="Username")
    first_name = models.CharField(max_length=100, blank=True, verbose_name="First Name")
    last_name = models.CharField(max_length=100, blank=True, verbose_name="Last Name")
    mentor = models.ForeignKey(Mentor, on_delete=models.SET_NULL, null=True, related_name='students')
    language = models.CharField(max_length=5, default='ru', verbose_name="Language")
    joined_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Student"
        verbose_name_plural = "Students"

    def __str__(self):
        if self.username:
            return f"@{self.username}"
        return f"{self.first_name} {self.last_name}".strip() or str(self.telegram_id)
