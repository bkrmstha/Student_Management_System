from django.db import models
from django.contrib.auth import get_user_model
from accounts.models import Batch, StudentProfile, TeacherProfile
from courses.models import Course

User = get_user_model()


class Notice(models.Model):
    """Model for notices posted to various user groups."""
    
    AUDIENCE_CHOICES = [
        ('all', 'All Users'),
        ('batch', 'Specific Batch'),
        ('course', 'Specific Course'),
        ('role', 'Specific Role'),
        ('students', 'All Students'),
        ('teachers', 'All Teachers'),
        ('guardians', 'All Guardians'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    title = models.CharField(max_length=255)
    content = models.TextField()
    audience_type = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default='all')
    
    # For filtering audience
    batches = models.ManyToManyField(Batch, blank=True, related_name='notices')
    courses = models.ManyToManyField(Course, blank=True, related_name='notices')
    
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    is_important = models.BooleanField(default=False)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_notices')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at', 'is_active']),
            models.Index(fields=['audience_type', 'created_by']),
            models.Index(fields=['priority', 'is_important']),
        ]
        verbose_name_plural = 'Notices'
    
    def __str__(self):
        return self.title
    
    def get_viewer_count(self):
        """Return number of unique viewers."""
        return self.views.values('user').distinct().count()
    
    def is_expired(self):
        """Check if notice has expired."""
        from django.utils import timezone
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class NoticeAttachment(models.Model):
    """Model for attachments to notices."""
    
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='noticeboard/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.notice.title} - {self.file.name}"


class NoticeComment(models.Model):
    """Model for comments on notices."""
    
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notice_comments')
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['notice', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"Comment by {self.user} on {self.notice.title}"


class NoticeView(models.Model):
    """Model to track who has viewed a notice."""
    
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='viewed_notices')
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('notice', 'user')
        indexes = [
            models.Index(fields=['notice', 'viewed_at']),
            models.Index(fields=['user', 'viewed_at']),
        ]
    
    def __str__(self):
        return f"{self.user} viewed {self.notice.title}"


class NoticeReadStatus(models.Model):
    """Model to track read/unread status of notices for users."""
    
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name='read_statuses')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notice_read_statuses')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('notice', 'user')
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['notice', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.notice.title} ({'Read' if self.is_read else 'Unread'})"
