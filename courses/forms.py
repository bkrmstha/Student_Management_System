# courses/forms.py
from django import forms
from django.core.exceptions import ValidationError
from accounts.models import User
from .models import Course, Subject
import re

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'short_name', 'course_type', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Enter full course name',
                'maxlength': '200'
            }),
            'short_name': forms.TextInput(attrs={
                'placeholder': 'e.g., BCS, BCA, BBA',
                'maxlength': '50'
            }),
            'course_type': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if len(name) < 3:
            raise ValidationError('Course name must be at least 3 characters long.')
        return name
    
    def clean_short_name(self):
        short_name = self.cleaned_data['short_name'].strip().upper()
        
        # Check if it's alphanumeric
        if not short_name.isalnum():
            raise ValidationError('Short name can only contain letters and numbers. No spaces or special characters allowed.')
        
        if len(short_name) < 2:
            raise ValidationError('Short name must be at least 2 characters long.')
        
        if len(short_name) > 10:
            raise ValidationError('Short name must be 10 characters or less.')
        
        return short_name
    
    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name', '').strip().lower()
        short_name = cleaned_data.get('short_name', '').strip().lower()
        
        # Check if name and short_name are the same
        if name and short_name and name == short_name:
            raise ValidationError({
                'short_name': 'Short name cannot be the same as the full course name.'
            })
        
        return cleaned_data


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['course', 'code', 'name', 'semester', 'year', 'teacher']
        widgets = {
            'course': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_course'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., CS101-T, CS101-P',
                'id': 'id_code',
                'autocomplete': 'off'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter subject name',
                'id': 'id_name'
            }),
            'semester': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_semester'
            }, choices=[
                ('', 'Select Semester'),
                (1, 'Semester 1'), (2, 'Semester 2'), (3, 'Semester 3'), (4, 'Semester 4'),
                (5, 'Semester 5'), (6, 'Semester 6'), (7, 'Semester 7'), (8, 'Semester 8')
            ]),
            'year': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_year'
            }, choices=[
                ('', 'Select Year'),
                (1, 'Year 1'), (2, 'Year 2'), (3, 'Year 3'), (4, 'Year 4')
            ]),
            'teacher': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_teacher'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.course = kwargs.pop('course', None)
        self.initial_period = kwargs.pop('initial_period', {})
        super().__init__(*args, **kwargs)
        
        # Set teacher queryset to active teachers
        self.fields['teacher'].queryset = User.objects.filter(
            role='teacher', 
            is_active=True
        ).order_by('first_name', 'last_name')
        
        # Set empty label for teacher dropdown
        self.fields['teacher'].empty_label = "Select a teacher (Optional)"
        
        # Format teacher display in dropdown - Show only name
        self.fields['teacher'].label_from_instance = self.format_teacher_name
        
        if self.course:
            self.fields['course'].initial = self.course
            self.fields['course'].widget = forms.HiddenInput()
            
            # Set initial semester/year from initial_period
            if 'semester' in self.initial_period:
                self.fields['semester'].initial = self.initial_period['semester']
            if 'year' in self.initial_period:
                self.fields['year'].initial = self.initial_period['year']
            
            # Customize semester/year fields based on course type
            if self.course.course_type == 'semester':
                self.fields['semester'].required = True
                self.fields['year'].required = False
                self.fields['year'].widget = forms.HiddenInput()
            else:
                self.fields['year'].required = True
                self.fields['semester'].required = False
                self.fields['semester'].widget = forms.HiddenInput()
    
    def format_teacher_name(self, teacher):
        """Format teacher name for dropdown display - Show full name with middle name if available."""
        try:
            # Try to get teacher profile for middle name
            if hasattr(teacher, 'teacher_profile') and teacher.teacher_profile:
                profile = teacher.teacher_profile
                if profile.middle_name:
                    return f"{teacher.first_name} {profile.middle_name} {teacher.last_name}"
        except:
            pass
    
        # Fallback to basic full name
        return teacher.get_full_name()
    
    def clean_code(self):
        code = self.cleaned_data['code'].upper().strip()
        
        # Validate code format (alphanumeric with optional hyphens)
        if not re.match(r'^[A-Z0-9][A-Z0-9\-\s]*[A-Z0-9]$', code):
            raise ValidationError('Subject code can only contain letters, numbers, spaces, and hyphens.')
        
        return code
    
    def clean(self):
        cleaned_data = super().clean()
        course = cleaned_data.get('course') or self.course
        
        if course:
            # Check for unique code within course
            code = cleaned_data.get('code')
            if code:
                existing = Subject.objects.filter(
                    course=course, 
                    code__iexact=code
                )
                if self.instance and self.instance.id:
                    existing = existing.exclude(id=self.instance.id)
                if existing.exists():
                    raise ValidationError({
                        'code': f'Subject code "{code}" already exists in course "{course.name}".'
                    })
        
        return cleaned_data