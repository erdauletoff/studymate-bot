from django.db import models
from backend.students.models import Student
from backend.materials.models import Material


class Download(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='downloads')
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='downloads')
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Download"
        verbose_name_plural = "Downloads"
        indexes = [
            models.Index(fields=['material', 'downloaded_at']),
            models.Index(fields=['downloaded_at']),
        ]

    def __str__(self):
        return f"{self.student} - {self.material.title}"
