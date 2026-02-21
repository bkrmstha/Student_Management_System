from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

class Course(models.Model):
    COURSE_TYPES = (
        ('semester', 'Semester-based'),
        ('yearly', 'Yearly-based'),
    )
    
    name = models.CharField(
        max_length=200,
        unique=True,
        verbose_name="Course Name",
        help_text="Full name of the course"
    )
    
    short_name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Short Name",
        help_text="Abbreviated name (must be unique)"
    )
    
    course_type = models.CharField(
        max_length=20,
        choices=COURSE_TYPES,
        default='semester',
        verbose_name="Course Type"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Course"
        verbose_name_plural = "Courses"
    
    def __str__(self):
        return f"{self.short_name} - {self.name}"
    
    def clean(self):
        super().clean()
        if self.short_name:
            self.short_name = self.short_name.upper().strip()
        
        if self.name.lower().strip() == self.short_name.lower().strip():
            raise ValidationError({
                'short_name': 'Short name cannot be the same as the full course name.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Subject(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='subjects',
        verbose_name="Course"
    )
    
    code = models.CharField(
        max_length=20,
        verbose_name="Subject Code",
        help_text="e.g., CS101-T, CS101-P"
    )
    
    name = models.CharField(
        max_length=200,
        verbose_name="Subject Name"
    )
    
    # Semester field (1-8)
    semester = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(8)],
        verbose_name="Semester",
        help_text="Choose 1-8 for semester-based courses"
    )
    
    # Year field (1-4)
    year = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        verbose_name="Year",
        help_text="Choose 1-4 for yearly-based courses"
    )
    
    teacher = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'teacher', 'is_active': True},
        related_name='subjects_taught',
        verbose_name="Subject Teacher"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['course', 'semester', 'year', 'code']
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"
        unique_together = ['course', 'code']
    
    def __str__(self):
        period_info = ""
        if self.course.course_type == 'semester' and self.semester:
            period_info = f" - Sem {self.semester}"
        elif self.course.course_type == 'yearly' and self.year:
            period_info = f" - Year {self.year}"
        
        return f"{self.code} - {self.name} ({self.course.short_name}{period_info})"
    
    def clean(self):
        """Strict validation for Semester vs Year based on Course Type."""
        super().clean()
        
        if self.course:
            if self.course.course_type == 'semester':
                if not self.semester:
                    raise ValidationError({'semester': 'This course requires a Semester (1-8).'})
                if self.year:
                    raise ValidationError({'year': 'Year should not be set for a semester-based course.'})
            
            elif self.course.course_type == 'yearly':
                if not self.year:
                    raise ValidationError({'year': 'This course requires a Year (1-4).'})
                if self.semester:
                    raise ValidationError({'semester': 'Semester should not be set for a yearly-based course.'})
    
    @property
    def period(self):
        """Returns a string representing the current period."""
        if self.course.course_type == 'semester':
            return f"Semester {self.semester}" if self.semester else "N/A"
        return f"Year {self.year}" if self.year else "N/A"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)