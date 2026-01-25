from django.contrib import admin
from .models import Topic, Material


class MaterialInline(admin.TabularInline):
    model = Material
    extra = 0
    fields = ('title', 'file_name', 'order')
    readonly_fields = ('file_name',)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'mentor', 'order', 'materials_count', 'created_at')
    list_filter = ('mentor',)
    search_fields = ('name',)
    inlines = [MaterialInline]

    def materials_count(self, obj):
        return obj.materials.count()
    materials_count.short_description = 'Materials'


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'topic', 'file_name', 'order', 'created_at')
    list_filter = ('topic__mentor', 'topic')
    search_fields = ('title',)
