# accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator, EmailValidator, MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
import re

# ==================== CUSTOM VALIDATORS ====================

# Name validator: Allows only letters, spaces, hyphens, dots, and apostrophes
name_validator = RegexValidator(
    regex=r'^[A-Za-z\s\-\.\']+$',
    message='Name can only contain letters, spaces, hyphens, dots, and apostrophes. No numbers allowed.'
)

# Phone number validator: Only digits with optional + at start
phone_validator = RegexValidator(
    regex=r'^\+?[0-9]{9,15}$',
    message="Phone number must contain 9-15 digits with optional '+' at the start. No letters allowed."
)

# Email validator using Django's built-in with custom message
email_validator = EmailValidator(
    message='Please enter a valid email address (e.g., user@example.com).'
)

# Student ID, Teacher ID, Guardian ID validator
id_validator = RegexValidator(
    regex=r'^[A-Za-z0-9\-_]+$',
    message='ID can only contain letters, numbers, hyphens, and underscores.'
)

# Custom function validator for no numbers in names
def validate_no_numbers(value):
    """Custom validator to ensure no numbers in name fields"""
    if any(char.isdigit() for char in value):
        raise ValidationError('Name cannot contain numbers.')
    return value

# Custom function validator for no letters in phone numbers
def validate_no_letters_in_phone(value):
    """Custom validator to ensure no letters in phone number"""
    if value and re.search(r'[A-Za-z]', value):
        raise ValidationError('Phone number cannot contain letters.')
    return value

# ==================== CUSTOM USER MANAGER ====================

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'admin')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)

# ==================== USER MODEL ====================

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
        ('guardian', 'Guardian'),
    )
    
    # Remove username field, use email instead
    username = None
    
    # Email field with validation
    email = models.EmailField(
        unique=True,
        validators=[email_validator],
        verbose_name="Email ID",
        help_text="Enter a valid email address"
    )
    
    # Role field
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='student',
        verbose_name="User Role"
    )
    
    # Verification and tracking fields
    is_verified = models.BooleanField(default=False, verbose_name="Email Verified")
    created_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_users',
        verbose_name="Created By"
    )
    date_created = models.DateTimeField(auto_now_add=True, verbose_name="Account Created")
    
    # Name fields with validation
    first_name = models.CharField(
        max_length=30,
        validators=[name_validator, validate_no_numbers],
        verbose_name="First Name",
        help_text="Enter first name without numbers"
    )
    
    last_name = models.CharField(
        max_length=30,
        validators=[name_validator, validate_no_numbers],
        verbose_name="Last Name",
        help_text="Enter last name without numbers"
    )
    
    # Phone number with validation
    phone_number = models.CharField(
        validators=[phone_validator, validate_no_letters_in_phone], 
        max_length=17, 
        blank=True,
        verbose_name="Phone Number",
        help_text="Enter phone number (9-15 digits, optional +)"
    )
    
    # Authentication fields
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    objects = CustomUserManager()
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ['-date_created']
    
    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"
    
    @property
    def full_name(self):
        """Return the full name of the user"""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_admin(self):
        return self.role == 'admin' or self.is_superuser
    
    @property
    def is_teacher(self):
        return self.role == 'teacher'
    
    @property
    def is_student(self):
        return self.role == 'student'
    
    @property
    def is_guardian(self):
        return self.role == 'guardian'
    
    def clean(self):
        """Model-level validation"""
        super().clean()
        
        # Additional email validation
        if self.email:
            # Check for valid email format
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', self.email):
                raise ValidationError({'email': 'Please enter a valid email address.'})
        
        # Additional phone validation
        if self.phone_number:
            # Remove any spaces from phone number
            self.phone_number = self.phone_number.replace(' ', '')
            
            # Ensure it starts with + or digits only
            if not re.match(r'^\+?[0-9]+$', self.phone_number):
                raise ValidationError({'phone_number': 'Phone number can only contain digits and optional +.'})
    
    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.full_clean()
        super().save(*args, **kwargs)


# ==================== BATCH MODEL ====================

class Batch(models.Model):
    """Model for academic batches/years"""
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Batch Name",
        help_text="e.g., Batch 2080, Class of 2024"
    )
    
    description = models.TextField(
        blank=True,
        verbose_name="Description",
        help_text="Optional description about the batch"
    )
    
    year = models.IntegerField(
        verbose_name="Batch Year",
        help_text="Year when batch started (e.g., 2080)",
        validators=[MinValueValidator(2000), MaxValueValidator(2100)]
    )
    
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Start Date"
    )
    
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Expected End Date"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active Batch"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_batches',
        verbose_name="Created By"
    )
    
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Batch"
        verbose_name_plural = "Batches"
        ordering = ['-year', '-date_created']
    
    def __str__(self):
        return self.name
    
    def clean(self):
        """Validate batch dates"""
        super().clean()
        
        # Validate dates if both are provided
        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                raise ValidationError({
                    'end_date': 'End date must be after start date.'
                })
    
    @property
    def total_students(self):
        """Get total students in this batch"""
        return self.students.count()
    
    @property
    def total_courses(self):
        """Get total courses in this batch"""
        return self.batch_courses.count()
    
    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.full_clean()
        super().save(*args, **kwargs)

    def import_all_courses(self, added_by_user=None):
        """
        Automatically import all ACTIVE courses into this batch.
        Returns the number of courses imported.
        """
        from courses.models import Course
        
        # Get all active courses that are properly formatted
        active_courses = Course.objects.filter(
            is_active=True,
            name__isnull=False,
            short_name__isnull=False
        ).exclude(
            name='',
            short_name=''
        )
        
        imported_count = 0
        for course in active_courses:
            # Check if course already exists in batch
            if not BatchCourse.objects.filter(batch=self, course=course).exists():
                try:
                    BatchCourse.objects.create(
                        batch=self,
                        course=course,
                        added_by=added_by_user,
                        is_active=True
                    )
                    imported_count += 1
                except Exception as e:
                    print(f"Error importing course {course.short_name}: {e}")
        
        return imported_count
    
    def save(self, *args, **kwargs):
        """Override save to auto-import courses for new batches."""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Auto-import courses for new batches
        if is_new and not self.batch_courses.exists():
            imported = self.import_all_courses(added_by_user=self.created_by)
            print(f"Auto-imported {imported} courses to batch {self.name}")


# ==================== BATCH-COURSE RELATIONSHIP MODEL ====================

class BatchCourse(models.Model):
    """Model linking batches to courses"""
    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name='batch_courses',
        verbose_name="Batch"
    )
    
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='batch_courses',
        verbose_name="Course"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active in Batch"
    )
    
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='added_batch_courses',
        verbose_name="Added By"
    )
    
    date_added = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Batch Course"
        verbose_name_plural = "Batch Courses"
        unique_together = ['batch', 'course']
        ordering = ['course__name']
    
    def __str__(self):
        return f"{self.batch.name} - {self.course.name}"


# ==================== TEACHER PROFILE MODEL ====================

class TeacherProfile(models.Model):
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='teacher_profile',
        verbose_name="User Account"
    )
    
    teacher_id = models.CharField(
        max_length=20, 
        unique=True, 
        verbose_name="Teacher ID",
        null=True,
        blank=True,
        validators=[id_validator],
        help_text="Leave blank to auto-generate"
    )
    
    middle_name = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name="Middle Name",
        validators=[name_validator, validate_no_numbers],
        help_text="Enter middle name without numbers"
    )
    
    designation = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="Designation",
        help_text="Enter designation/title"
    )
    
    department = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="Department",
        help_text="Enter department name"
    )
    
    joining_date = models.DateField(
        null=True, 
        blank=True, 
        verbose_name="Joining Date",
        help_text="Select joining date"
    )
    
    subjects = models.TextField(
        blank=True, 
        help_text="Comma separated list of subjects", 
        verbose_name="Subjects Taught"
    )
    
    photo = models.ImageField(
        upload_to='teachers/photos/', 
        null=True, 
        blank=True, 
        verbose_name="Profile Photo",
        help_text="Upload a professional photo"
    )
    
    class Meta:
        verbose_name = "Teacher Profile"
        verbose_name_plural = "Teacher Profiles"
    
    def __str__(self):
        return f"Teacher: {self.user.full_name} ({self.teacher_id})"
    
    @property
    def full_name(self):
        """Return full name including middle name if available"""
        if self.middle_name:
            return f"{self.user.first_name} {self.middle_name} {self.user.last_name}"
        return f"{self.user.first_name} {self.user.last_name}"
    
    def clean(self):
        """Model-level validation"""
        super().clean()
        
        # Validate middle name if provided
        if self.middle_name and not re.match(r'^[A-Za-z\s\-\.\']+$', self.middle_name):
            raise ValidationError({
                'middle_name': 'Middle name can only contain letters, spaces, hyphens, dots, and apostrophes.'
            })
        
        # Validate teacher_id format if provided
        if self.teacher_id and not re.match(r'^[A-Za-z0-9\-_]+$', self.teacher_id):
            raise ValidationError({
                'teacher_id': 'Teacher ID can only contain letters, numbers, hyphens, and underscores.'
            })
    
    def save(self, *args, **kwargs):
        """Override save to auto-generate teacher_id and run validation"""
        
        # Auto-generate teacher_id if not provided
        if not self.teacher_id and self.user:
            if self.user.id:
                self.teacher_id = f"T{self.user.id:04d}"
        
        # Run validation
        self.full_clean()
        super().save(*args, **kwargs)


# ==================== STUDENT PROFILE MODEL ====================

class StudentProfile(models.Model):
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='student_profile',
        verbose_name="User Account"
    )
    
    student_id = models.CharField(
        max_length=20, 
        unique=True, 
        verbose_name="Student ID",
        validators=[id_validator],
        help_text="Enter student ID"
    )
    
    middle_name = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name="Middle Name",
        validators=[name_validator, validate_no_numbers],
        help_text="Enter middle name without numbers"
    )
    
    date_of_birth = models.DateField(
        null=True, 
        blank=True, 
        verbose_name="Date of Birth",
        help_text="Select date of birth"
    )
    
    gender = models.CharField(
        max_length=10,
        choices=[
            ('Male', 'Male'),
            ('Female', 'Female'),
            ('Other', 'Other'),
        ],
        blank=True,
        verbose_name="Gender",
        help_text="Select gender"
    )
    
    nationality = models.CharField(
        max_length=50,
        blank=True,
        default='Nepali',
        verbose_name="Nationality",
        help_text="Enter nationality"
    )
    
    grade = models.CharField(
        max_length=10, 
        blank=True, 
        verbose_name="Grade",
        help_text="Enter grade/class"
    )
    
    section = models.CharField(
        max_length=10, 
        blank=True, 
        verbose_name="Section",
        help_text="Enter section"
    )
    
    emergency_contact = models.CharField(
        max_length=20, 
        blank=True, 
        verbose_name="Emergency Contact",
        validators=[phone_validator, validate_no_letters_in_phone],
        help_text="Enter emergency contact number"
    )
    
    address = models.TextField(
        blank=True,
        verbose_name="Address",
        help_text="Enter student's address"
    )
    
    photo = models.ImageField(
        upload_to='students/photos/', 
        null=True, 
        blank=True, 
        verbose_name="Student Photo",
        help_text="Upload student photo"
    )
    
    # Batch field added
    batch = models.ForeignKey(
        Batch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
        verbose_name="Batch"
    )
    
    enrolled_courses = models.ManyToManyField(
        'courses.Course',
        through='StudentCourseEnrollment',
        related_name='enrolled_students',
        blank=True,
        verbose_name="Enrolled Courses"
    )
    
    class Meta:
        verbose_name = "Student Profile"
        verbose_name_plural = "Student Profiles"
    
    def __str__(self):
        return f"Student: {self.user.full_name} ({self.student_id})"
    
    @property
    def full_name(self):
        """Return full name including middle name if available"""
        if self.middle_name:
            return f"{self.user.first_name} {self.middle_name} {self.user.last_name}"
        return f"{self.user.first_name} {self.user.last_name}"
    
    def clean(self):
        """Model-level validation"""
        super().clean()
        
        # Validate middle name if provided
        if self.middle_name and not re.match(r'^[A-Za-z\s\-\.\']+$', self.middle_name):
            raise ValidationError({
                'middle_name': 'Middle name can only contain letters, spaces, hyphens, dots, and apostrophes.'
            })
        
        # Validate student_id format
        if not re.match(r'^[A-Za-z0-9\-_]+$', self.student_id):
            raise ValidationError({
                'student_id': 'Student ID can only contain letters, numbers, hyphens, and underscores.'
            })
        
        # Validate emergency contact if provided
        if self.emergency_contact:
            # Remove spaces
            self.emergency_contact = self.emergency_contact.replace(' ', '')
            if not re.match(r'^\+?[0-9]+$', self.emergency_contact):
                raise ValidationError({
                    'emergency_contact': 'Emergency contact can only contain digits and optional +.'
                })
    
    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.full_clean()
        super().save(*args, **kwargs)


# ==================== STUDENT COURSE ENROLLMENT MODEL ====================

class StudentCourseEnrollment(models.Model):
    """Model for student course enrollment"""
    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name='course_enrollments',
        verbose_name="Student"
    )
    
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='student_enrollments',
        verbose_name="Course"
    )
    
    enrollment_date = models.DateField(
        auto_now_add=True,
        verbose_name="Enrollment Date"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active Enrollment"
    )
    
    enrolled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='enrolled_students',
        verbose_name="Enrolled By"
    )
    
    class Meta:
        verbose_name = "Student Course Enrollment"
        verbose_name_plural = "Student Course Enrollments"
        unique_together = ['student', 'course']
        ordering = ['-enrollment_date']
    
    def __str__(self):
        return f"{self.student.user.email} - {self.course.name}"


# ==================== GUARDIAN PROFILE MODEL ====================

class GuardianProfile(models.Model):
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='guardian_profile',
        verbose_name="User Account"
    )
    
    guardian_id = models.CharField(
        max_length=20, 
        unique=True, 
        verbose_name="Guardian ID",
        validators=[id_validator],
        help_text="Enter guardian ID"
    )
    
    middle_name = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name="Middle Name",
        validators=[name_validator, validate_no_numbers],
        help_text="Enter middle name without numbers"
    )
    
    relation_to_student = models.CharField(
        max_length=50,
        verbose_name="Relation to Student",
        help_text="e.g., Father, Mother, Guardian"
    )
    
    occupation = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="Occupation",
        help_text="Enter occupation/profession"
    )
    
    address = models.TextField(
        blank=True,
        verbose_name="Address",
        help_text="Enter complete address"
    )
    
    photo = models.ImageField(
        upload_to='guardians/photos/', 
        null=True, 
        blank=True, 
        verbose_name="Guardian Photo",
        help_text="Upload guardian photo"
    )
    
    class Meta:
        verbose_name = "Guardian Profile"
        verbose_name_plural = "Guardian Profiles"
    
    def __str__(self):
        return f"Guardian: {self.user.full_name} ({self.guardian_id})"
    
    @property
    def full_name(self):
        """Return full name including middle name if available"""
        if self.middle_name:
            return f"{self.user.first_name} {self.middle_name} {self.user.last_name}"
        return f"{self.user.first_name} {self.user.last_name}"
    
    def clean(self):
        """Model-level validation"""
        super().clean()
        
        # Validate middle name if provided
        if self.middle_name and not re.match(r'^[A-Za-z\s\-\.\']+$', self.middle_name):
            raise ValidationError({
                'middle_name': 'Middle name can only contain letters, spaces, hyphens, dots, and apostrophes.'
            })
        
        # Validate guardian_id format
        if not re.match(r'^[A-Za-z0-9\-_]+$', self.guardian_id):
            raise ValidationError({
                'guardian_id': 'Guardian ID can only contain letters, numbers, hyphens, and underscores.'
            })
    
    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.full_clean()
        super().save(*args, **kwargs)


# ==================== GUARDIAN-STUDENT RELATIONSHIP MODEL ====================

class GuardianStudentRelationship(models.Model):
    guardian = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='students',
        limit_choices_to={'role': 'guardian'},
        verbose_name="Guardian"
    )
    
    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='guardians',
        limit_choices_to={'role': 'student'},
        verbose_name="Student"
    )
    
    is_primary = models.BooleanField(
        default=False,
        verbose_name="Primary Guardian",
        help_text="Check if this is the primary guardian"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Relationship Created"
    )
    
    class Meta:
        verbose_name = "Guardian-Student Relationship"
        verbose_name_plural = "Guardian-Student Relationships"
        unique_together = ['guardian', 'student']
    
    def __str__(self):
        return f"{self.guardian.email} → {self.student.email} (Primary: {self.is_primary})"
    
    def clean(self):
        """Model-level validation"""
        super().clean()
        
        # Ensure guardian is actually a guardian
        if not self.guardian.is_guardian:
            raise ValidationError({
                'guardian': 'Selected user must have the guardian role.'
            })
        
        # Ensure student is actually a student
        if not self.student.is_student:
            raise ValidationError({
                'student': 'Selected user must have the student role.'
            })
    
    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.full_clean()
        super().save(*args, **kwargs)