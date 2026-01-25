from django.db import models
from backend.mentors.models import Mentor


class Topic(models.Model):
    mentor = models.ForeignKey(Mentor, on_delete=models.CASCADE, related_name='topics')
    name = models.CharField(max_length=100, verbose_name="Topic Name")
    order = models.PositiveIntegerField(default=0, verbose_name="Order")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Topic"
        verbose_name_plural = "Topics"
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.mentor.name} - {self.name}"


class Material(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='materials')
    title = models.CharField(max_length=200, verbose_name="Title")
    file_id = models.CharField(max_length=200, verbose_name="Telegram File ID")
    file_name = models.CharField(max_length=200, verbose_name="File Name", blank=True)
    order = models.PositiveIntegerField(default=0, verbose_name="Order")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "Materials"
        ordering = ['order', 'created_at']

    def __str__(self):
        return self.title
