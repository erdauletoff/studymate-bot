from django.db import models
from backend.mentors.models import Mentor


class Question(models.Model):
    mentor = models.ForeignKey(Mentor, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField(verbose_name="Question Text")
    is_answered = models.BooleanField(default=False, verbose_name="Answered")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Anonymous Question"
        verbose_name_plural = "Anonymous Questions"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.text[:50]}..."
