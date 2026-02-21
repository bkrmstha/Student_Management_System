from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import AttendanceSession, AttendanceRecord
from accounts.models import Batch, User
from courses.models import Course, Subject
from django.db.models import Q

class AttendanceSessionForm(forms.ModelForm):
    """Form for creating and editing daily attendance sessions"""
    
    batch = forms.ModelChoiceField(
        queryset=Batch.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_batch',
        }),
        label="Academic Batch", # Changed from 'Batch' to avoid repetition
        required=True
    )
    
    course = forms.ModelChoiceField(
        queryset=Course.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_course',
        }),
        label="Course",
        required=True
    )
    
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_subject'
        }),
        label="Subject",
        required=True
    )
    
    teacher = forms.ModelChoiceField(
        queryset=User.objects.filter(role='teacher', is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_teacher'
        }),
        label="Assigned Teacher",
        required=True
    )
    
    date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-input',
            'type': 'date',
        }),
        initial=timezone.now().date,
        label="Attendance Date",
        required=True
    )

    class Meta:
        model = AttendanceSession
        fields = ['date', 'batch', 'course', 'subject', 'teacher', 'remarks']
        widgets = {
            'remarks': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 2,
                'placeholder': 'Session topics or notes...'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # 1. Handle Teacher Role Permissions
        if user and hasattr(user, 'role') and user.role == 'teacher':
            # Limit batches to only those this teacher has subjects in
            teacher_subjects = Subject.objects.filter(teacher=user)
            batch_ids = teacher_subjects.values_list('course__batch_courses__batch', flat=True).distinct()
            self.fields['batch'].queryset = Batch.objects.filter(id__in=batch_ids, is_active=True)
            
            # Set teacher field to current user and hide it from the form
            self.fields['teacher'].initial = user
            self.fields['teacher'].widget = forms.HiddenInput()
            self.fields['teacher'].required = False
        
        # 2. Format teacher names for the dropdown (Admins only)
        self.fields['teacher'].label_from_instance = self.format_teacher_name

        # 3. Dynamic Dropdown Logic: 
        # If it's a new form (GET), empty Course/Subject so AJAX can fill them.
        # If it's a POST or editing (instance), keep them populated for validation.
        if 'batch' not in self.data and not self.instance.pk:
            self.fields['course'].queryset = Course.objects.none()
            self.fields['subject'].queryset = Subject.objects.none()
        elif self.instance.pk:
            # When editing, filter based on existing instance
            self.fields['course'].queryset = Course.objects.filter(batch_courses__batch=self.instance.batch)
            self.fields['subject'].queryset = Subject.objects.filter(course=self.instance.course)

    def format_teacher_name(self, teacher):
        return teacher.get_full_name() or teacher.username

    def clean(self):
        cleaned_data = super().clean()
        batch = cleaned_data.get('batch')
        course = cleaned_data.get('course')
        subject = cleaned_data.get('subject')
        date = cleaned_data.get('date')
        
        # Cross-field Validation
        if batch and course:
            from accounts.models import BatchCourse
            if not BatchCourse.objects.filter(batch=batch, course=course).exists():
                raise ValidationError({'course': "This course is not linked to the selected batch."})

        if course and subject and subject.course != course:
            raise ValidationError({'subject': "This subject does not belong to the selected course."})

        # Prevent Duplicate Sessions for the same day
        if batch and subject and date:
            duplicate_query = AttendanceSession.objects.filter(
                batch=batch,
                subject=subject,
                date=date
            ).exclude(status='cancelled')
            
            if self.instance.pk:
                duplicate_query = duplicate_query.exclude(pk=self.instance.pk)
            
            if duplicate_query.exists():
                raise ValidationError("A session for this Batch, Subject, and Date already exists.")

        return cleaned_data

class AttendanceRecordForm(forms.ModelForm):
    class Meta:
        model = AttendanceRecord
        fields = ['status', 'remarks']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'remarks': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Notes...'})
        }