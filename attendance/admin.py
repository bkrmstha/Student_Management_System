# attendance/admin.py
from django.contrib import admin
from .models import AttendanceSession, AttendanceRecord

class AttendanceRecordInline(admin.TabularInline):
    model = AttendanceRecord
    extra = 0
    readonly_fields = ['recorded_by', 'created_at']
    fields = ['student', 'status', 'check_in_time', 'check_out_time', 'remarks']
    can_delete = True

@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'batch', 'course', 'subject', 'teacher', 'date', 'status', 'attendance_percentage']
    list_filter = ['status', 'batch', 'course', 'teacher', 'date']
    search_fields = ['session_id', 'batch__name', 'course__name', 'subject__name', 'teacher__email']
    readonly_fields = ['session_id', 'total_students', 'present_count', 'absent_count', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('session_id', 'batch', 'course', 'subject', 'teacher')
        }),
        ('Session Details', {
            'fields': ('date', 'start_time', 'end_time', 'semester', 'year')
        }),
        ('Status & Statistics', {
            'fields': ('status', 'total_students', 'present_count', 'absent_count', 'remarks')
        }),
        ('Timestamps', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    inlines = [AttendanceRecordInline]
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def attendance_percentage(self, obj):
        return f"{obj.attendance_percentage}%"
    attendance_percentage.short_description = 'Attendance %'

@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ['student', 'session', 'status', 'check_in_time', 'recorded_by', 'created_at']
    list_filter = ['status', 'session__batch', 'session__course', 'session__date']
    search_fields = ['student__user__email', 'student__student_id', 'session__session_id']
    readonly_fields = ['recorded_by', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('session', 'student', 'status')
        }),
        ('Time Details', {
            'fields': ('check_in_time', 'check_out_time')
        }),
        ('Additional Information', {
            'fields': ('remarks', 'recorded_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not obj.recorded_by:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)