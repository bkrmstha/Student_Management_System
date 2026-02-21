from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from accounts.models import User, StudentProfile

class AttendanceSession(models.Model):
    """Model for attendance sessions"""
    
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    session_id = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Session ID",
        help_text="Auto-generated session ID"
    )
    
    batch = models.ForeignKey(
        'accounts.Batch',
        on_delete=models.CASCADE,
        related_name='attendance_sessions',
        verbose_name="Batch"
    )
    
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='attendance_sessions',
        verbose_name="Course",
        null=True,
        blank=True
    )
    
    subject = models.ForeignKey(
        'courses.Subject',
        on_delete=models.CASCADE,
        related_name='attendance_sessions',
        verbose_name="Subject",
        null=True,
        blank=True
    )
    
    teacher = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'teacher'},
        related_name='attendance_sessions',
        verbose_name="Teacher"
    )
    
    date = models.DateField(
        verbose_name="Date",
        default=timezone.now
    )
    
    start_time = models.TimeField(
        verbose_name="Start Time",
        default=timezone.now
    )
    
    end_time = models.TimeField(
        verbose_name="End Time",
        null=True,
        blank=True
    )
    
    semester = models.IntegerField(
        verbose_name="Semester",
        validators=[MinValueValidator(1), MaxValueValidator(8)],
        null=True,
        blank=True
    )
    
    year = models.IntegerField(
        verbose_name="Year",
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        null=True,
        blank=True
    )
    
    total_students = models.IntegerField(
        verbose_name="Total Students",
        default=0,
        editable=False
    )
    
    present_count = models.IntegerField(
        verbose_name="Present Count",
        default=0,
        editable=False
    )
    
    absent_count = models.IntegerField(
        verbose_name="Absent Count",
        default=0,
        editable=False
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled',
        verbose_name="Status"
    )
    
    remarks = models.TextField(
        verbose_name="Remarks",
        blank=True,
        null=True
    )
    
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_attendance_sessions',
        verbose_name="Created By"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Attendance Session"
        verbose_name_plural = "Attendance Sessions"
        ordering = ['-date', '-start_time']
    
    def __str__(self):
        if self.course and self.subject:
            return f"{self.session_id} - {self.batch.name} - {self.subject.code}"
        return f"{self.session_id} - {self.batch.name}"
    
    def clean(self):
        super().clean()
        # Ensure subject belongs to the selected course if both are selected
        if self.course and self.subject and self.subject.course != self.course:
            raise ValidationError({'subject': 'Selected subject must belong to the selected course.'})
        
        # Time validation
        if self.end_time and self.start_time >= self.end_time:
            raise ValidationError({'end_time': 'End time must be after start time.'})
    
    def update_stats(self):
        """Method to recalculate session statistics"""
        records = self.attendance_records.all()
        self.total_students = records.count()
        self.present_count = records.filter(status='present').count()
        self.absent_count = self.total_students - self.present_count
        # Save without calling the full save method to avoid recursion
        AttendanceSession.objects.filter(pk=self.pk).update(
            total_students=self.total_students,
            present_count=self.present_count,
            absent_count=self.absent_count
        )

    def save(self, *args, **kwargs):
        # 1. Generate unique session ID if not exists
        if not self.session_id:
            date_str = self.date.strftime('%d%m%y')
            batch_code = self.batch.name.replace(' ', '').upper()[:4]
            base_id = f"{batch_code}-{date_str}"
            existing = AttendanceSession.objects.filter(session_id__startswith=base_id).count()
            self.session_id = f"{base_id}-{existing + 1:02d}"
        
        super().save(*args, **kwargs)

    @property
    def attendance_percentage(self):
        if self.total_students > 0:
            return round((self.present_count / self.total_students) * 100, 2)
        return 0


class AttendanceRecord(models.Model):
    """Model for individual student attendance records"""
    
    STATUS_CHOICES = (
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('excused', 'Excused'),
        ('half_day', 'Half Day'),
    )
    
    session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name='attendance_records',
        verbose_name="Attendance Session"
    )
    
    student = models.ForeignKey(
        'accounts.StudentProfile',
        on_delete=models.CASCADE,
        related_name='attendance_records',
        verbose_name="Student"
    )
    
    date = models.DateField(
        verbose_name="Attendance Date",
        default=timezone.now,
        help_text="Date on which attendance was recorded"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='absent',
        verbose_name="Status"
    )
    
    check_in_time = models.TimeField(null=True, blank=True)
    remarks = models.CharField(max_length=255, blank=True, null=True)
    
    recorded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_attendances'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"
        unique_together = ['session', 'student', 'date']
        ordering = ['-date', 'student__student_id']
        indexes = [
            models.Index(fields=['date', 'student']),
            models.Index(fields=['date', 'session']),
        ]

    def __str__(self):
        return f"{self.student.student_id} - {self.status}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update the parent session stats every time a record is saved
        self.session.update_stats()
    
    def delete(self, *args, **kwargs):
        session = self.session
        super().delete(*args, **kwargs)
        # Update stats after a record is removed
        session.update_stats()