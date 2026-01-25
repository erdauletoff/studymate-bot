from django.contrib import admin
from .models import Download


@admin.register(Download)
class DownloadAdmin(admin.ModelAdmin):
    list_display = ('student', 'material', 'downloaded_at')
    list_filter = ('material__topic__mentor', 'downloaded_at')
    search_fields = ('student__username', 'material__title')
    readonly_fields = ('downloaded_at',)
