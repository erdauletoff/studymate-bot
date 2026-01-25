from django.contrib import admin
from .models import Mentor


@admin.register(Mentor)
class MentorAdmin(admin.ModelAdmin):
    list_display = ('name', 'telegram_id', 'group_chat_id', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'telegram_id')
