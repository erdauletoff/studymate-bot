from django.contrib import admin
from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'telegram_id', 'mentor', 'joined_at', 'last_active')
    list_filter = ('mentor',)
    search_fields = ('username', 'first_name', 'last_name', 'telegram_id')
    readonly_fields = ('telegram_id', 'joined_at', 'last_active')
