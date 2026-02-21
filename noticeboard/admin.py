from django.contrib import admin
from .models import Notice, NoticeAttachment, NoticeComment, NoticeView, NoticeReadStatus


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'audience_type', 'priority', 'is_important', 'created_by', 'created_at')
    list_filter = ('audience_type', 'priority', 'is_important', 'is_active', 'created_at')
    search_fields = ('title', 'content')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'content')
        }),
        ('Audience', {
            'fields': ('audience_type', 'batches', 'courses')
        }),
        ('Priority', {
            'fields': ('priority', 'is_important', 'is_active')
        }),
        ('Expiration', {
            'fields': ('expires_at',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(NoticeAttachment)
class NoticeAttachmentAdmin(admin.ModelAdmin):
    list_display = ('notice', 'file', 'uploaded_at')
    list_filter = ('uploaded_at', 'notice')
    search_fields = ('notice__title', 'file')
    readonly_fields = ('uploaded_at',)


@admin.register(NoticeComment)
class NoticeCommentAdmin(admin.ModelAdmin):
    list_display = ('notice', 'user', 'created_at')
    list_filter = ('created_at', 'notice')
    search_fields = ('notice__title', 'user__email', 'comment')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(NoticeView)
class NoticeViewAdmin(admin.ModelAdmin):
    list_display = ('notice', 'user', 'viewed_at')
    list_filter = ('viewed_at', 'notice')
    search_fields = ('notice__title', 'user__email')
    readonly_fields = ('viewed_at',)


@admin.register(NoticeReadStatus)
class NoticeReadStatusAdmin(admin.ModelAdmin):
    list_display = ('notice', 'user', 'is_read', 'read_at')
    list_filter = ('is_read', 'read_at')
    search_fields = ('notice__title', 'user__email')
    readonly_fields = ('read_at',)
