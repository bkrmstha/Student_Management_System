from django import forms
from django.core.exceptions import ValidationError
from .models import Notice, NoticeAttachment, NoticeComment
from accounts.models import Batch, StudentProfile
from courses.models import Course


class NoticeForm(forms.ModelForm):
    """Form for creating and editing notices."""
    
    class Meta:
        model = Notice
        fields = [
            'title', 'content', 'audience_type', 'batches', 'courses',
            'expires_at'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Notice Title',
                'required': True
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Notice Content',
                'required': True
            }),
            'audience_type': forms.Select(attrs={
                'class': 'form-control',
                'id': 'audienceType',
                'required': True
            }),
            'batches': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input',
                'id': 'batchSelect'
            }),
            'courses': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input',
                'id': 'courseSelect'
            }),
            'expires_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            })
        }
    
    def clean(self):
        cleaned_data = super().clean()
        audience_type = cleaned_data.get('audience_type')
        batches = cleaned_data.get('batches')
        courses = cleaned_data.get('courses')
        
        # Validate audience type selections
        if audience_type == 'batch' and not batches:
            raise ValidationError('Please select at least one batch for batch-specific notices.')
        
        if audience_type == 'course' and not courses:
            raise ValidationError('Please select at least one course for course-specific notices.')
        
        return cleaned_data


class NoticeAttachmentForm(forms.ModelForm):
    """Form for notice attachments."""
    
    class Meta:
        model = NoticeAttachment
        fields = ['file']
        widgets = {
            'file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png,.gif,.webp,.txt'
            })
        }
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        
        if file:
            # Check file size (max 10MB)
            max_size = 10 * 1024 * 1024  # 10MB
            if file.size > max_size:
                raise ValidationError(f'File size must be under {max_size // (1024*1024)}MB.')
            
            # Check file type based on extension
            import os
            ext = os.path.splitext(file.name)[1].lower()
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf', '.doc', '.docx', '.txt']
            
            if ext not in allowed_extensions:
                raise ValidationError('File type not allowed. Please upload images, PDFs, or documents.')
        
        return file


class NoticeCommentForm(forms.ModelForm):
    """Form for commenting on notices."""
    
    class Meta:
        model = NoticeComment
        fields = ['comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Add your comment here...',
                'required': True
            })
        }
