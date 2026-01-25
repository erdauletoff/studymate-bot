from django.contrib import admin
from .models import Question


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('short_text', 'mentor', 'is_answered', 'created_at')
    list_filter = ('mentor', 'is_answered', 'created_at')
    search_fields = ('text',)
    readonly_fields = ('created_at',)
    actions = ['mark_as_answered']

    def short_text(self, obj):
        return obj.text[:80] + '...' if len(obj.text) > 80 else obj.text
    short_text.short_description = 'Question'

    @admin.action(description='Mark selected as answered')
    def mark_as_answered(self, request, queryset):
        queryset.update(is_answered=True)
