from django.contrib import admin
from .models import Question


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('short_text', 'student_info', 'mentor', 'has_reply', 'is_answered', 'created_at')
    list_filter = ('mentor', 'is_answered', 'created_at')
    search_fields = ('text', 'reply_text', 'student__first_name', 'student__last_name', 'student__username')
    readonly_fields = ('created_at', 'replied_at', 'student')
    actions = ['mark_as_answered']
    fieldsets = (
        ('Question', {
            'fields': ('mentor', 'student', 'text', 'created_at')
        }),
        ('Reply', {
            'fields': ('reply_text', 'replied_at', 'is_answered')
        }),
    )

    def short_text(self, obj):
        return obj.text[:80] + '...' if len(obj.text) > 80 else obj.text
    short_text.short_description = 'Question'

    def student_info(self, obj):
        if obj.student:
            name = f"{obj.student.first_name} {obj.student.last_name}".strip()
            username = f"@{obj.student.username}" if obj.student.username else ""
            return f"{name} {username}".strip() or f"ID: {obj.student.telegram_id}"
        return "Unknown"
    student_info.short_description = 'Student'

    def has_reply(self, obj):
        return bool(obj.reply_text)
    has_reply.short_description = 'Replied'
    has_reply.boolean = True

    @admin.action(description='Mark selected as answered')
    def mark_as_answered(self, request, queryset):
        queryset.update(is_answered=True)
