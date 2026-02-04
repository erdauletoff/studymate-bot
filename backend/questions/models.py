from django.db import models
from backend.mentors.models import Mentor
from backend.students.models import Student


class Question(models.Model):
    mentor = models.ForeignKey(Mentor, on_delete=models.CASCADE, related_name='questions')
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name='questions', verbose_name="Student (Anonymous)")
    text = models.TextField(verbose_name="Question Text")
    reply_text = models.TextField(verbose_name="Reply Text", blank=True, default='')
    is_answered = models.BooleanField(default=False, verbose_name="Answered")
    created_at = models.DateTimeField(auto_now_add=True)
    replied_at = models.DateTimeField(null=True, blank=True, verbose_name="Last Reply Time")
    message_id = models.BigIntegerField(null=True, blank=True, verbose_name="Student's Message ID")

    class Meta:
        verbose_name = "Anonymous Question"
        verbose_name_plural = "Anonymous Questions"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['mentor', 'is_answered']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.text[:50]}..."
