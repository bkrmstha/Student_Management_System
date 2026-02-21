# courses/admin.py
from django.contrib import admin
from .models import Course, Subject

class SubjectInline(admin.TabularInline):
    model = Subject
    extra = 1
    fields = ['code', 'name', 'teacher']
    ordering = ['code']

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['name', 'short_name', 'course_type', 'is_active']
    list_filter = ['course_type', 'is_active']
    search_fields = ['name', 'short_name']
    ordering = ['name']
    inlines = [SubjectInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'short_name', 'course_type')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'course', 'teacher', 'period_display']
    list_filter = ['course', 'course__course_type']
    search_fields = ['code', 'name', 'course__name', 'course__short_name', 'teacher__email', 'teacher__first_name', 'teacher__last_name']
    ordering = ['course', 'code']
    list_select_related = ['course', 'teacher']
    autocomplete_fields = ['teacher', 'course']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('course', 'code', 'name')
        }),
        ('Period Information', {
            'fields': ('semester', 'year'),
            'description': 'Note: Only semester or year should be set based on course type'
        }),
        ('Teacher Assignment', {
            'fields': ('teacher',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']
    
    def period_display(self, obj):
        """Display period (semester/year) in a user-friendly format."""
        if obj.course.course_type == 'semester' and obj.semester:
            return f"Semester {obj.semester}"
        elif obj.course.course_type == 'yearly' and obj.year:
            return f"Year {obj.year}"
        return "-"
    period_display.short_description = 'Period'