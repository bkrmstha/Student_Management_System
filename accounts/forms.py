from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.validators import RegexValidator, EmailValidator
from django.core.exceptions import ValidationError
from .models import User, StudentProfile, TeacherProfile, GuardianProfile, Batch, BatchCourse
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

# Email validator
email_validator = EmailValidator(
    message='Please enter a valid email address (e.g., user@example.com).'
)

# ID validator for student, teacher, guardian IDs
id_validator = RegexValidator(
    regex=r'^[A-Za-z0-9\-_]+$',
    message='ID can only contain letters, numbers, hyphens, and underscores.'
)

# Custom function validator for no numbers in names
def validate_no_numbers(value):
    """Custom validator to ensure no numbers in name fields"""
    if value and any(char.isdigit() for char in value):
        raise ValidationError('Name cannot contain numbers.')
    return value

# Custom function validator for no letters in phone numbers
def validate_no_letters_in_phone(value):
    """Custom validator to ensure no letters in phone number"""
    if value and re.search(r'[A-Za-z]', value):
        raise ValidationError('Phone number cannot contain letters.')
    return value

# Custom function validator for email format
def validate_email_domain(value):
    """Custom validator for email domain"""
    if value and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
        raise ValidationError('Please enter a valid email address.')
    return value

# ==================== FORM CLASSES ====================

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'phone_number')
        
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Apply validators to fields
        self.fields['first_name'].validators.extend([name_validator, validate_no_numbers])
        self.fields['last_name'].validators.extend([name_validator, validate_no_numbers])
        self.fields['email'].validators.append(validate_email_domain)
        self.fields['phone_number'].validators.extend([phone_validator, validate_no_letters_in_phone])
        
        # Set password fields as not required initially
        self.fields['password1'].required = False
        self.fields['password2'].required = False
        
        # Admin can create any user type
        if self.request and self.request.user.is_admin:
            self.fields['role'].choices = User.ROLE_CHOICES
        else:
            self.fields['role'].choices = [('student', 'Student')]
        
        # Add HTML attributes for validation
        self.fields['first_name'].widget.attrs.update({
            'pattern': '[A-Za-z\\s\\-\\.\\\']+',
            'title': 'Only letters, spaces, hyphens, dots, and apostrophes allowed'
        })
        self.fields['last_name'].widget.attrs.update({
            'pattern': '[A-Za-z\\s\\-\\.\\\']+',
            'title': 'Only letters, spaces, hyphens, dots, and apostrophes allowed'
        })
        self.fields['email'].widget.attrs.update({
            'pattern': '[a-z0-9._%+-]+@[a-z0-9.-]+\\.[a-z]{2,}$',
            'title': 'Please enter a valid email address'
        })
        self.fields['phone_number'].widget.attrs.update({
            'pattern': '^\\+?[0-9]{9,15}$',
            'title': '9-15 digits with optional + at start'
        })
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        if not self.cleaned_data.get('password1'):
            import secrets
            password = secrets.token_urlsafe(12)
            user.set_password(password)
        
        if commit:
            user.save()
        return user

class DefaultPasswordMixin:
    """Mixin to add default password functionality to forms."""
    
    DEFAULT_PASSWORDS = {
        'teacher': 'Teacher@123',
        'student': 'Student@123',
        'guardian': 'Guardian@123',
    }
    
    def get_default_password(self, role):
        """Get default password for a role."""
        return self.DEFAULT_PASSWORDS.get(role, 'Password@123')
    
    def create_user_with_default_password(self, email, first_name, last_name, role, phone_number='', **extra_fields):
        """Create user with default password."""
        default_password = self.get_default_password(role)
        
        user = User.objects.create_user(
            email=email,
            password=default_password,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            role=role,
            **extra_fields
        )
        
        return user, default_password

class TeacherCreationForm(DefaultPasswordMixin, forms.ModelForm):
    email = forms.EmailField(
        label="Email ID",
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter email address',
            'pattern': '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$',
            'title': 'Please enter a valid email address'
        }),
        validators=[email_validator, validate_email_domain],
        error_messages={
            'required': 'Email ID is required.',
            'invalid': 'Please enter a valid email address.'
        }
    )
    
    first_name = forms.CharField(
        max_length=30,
        label="First Name",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter first name',
            'pattern': '[A-Za-z\\s\\-\\.\\\']+',
            'title': 'Only letters, spaces, hyphens, dots, and apostrophes allowed'
        }),
        validators=[name_validator, validate_no_numbers],
        error_messages={
            'required': 'First name is required.',
            'invalid': 'Invalid characters in first name.'
        }
    )
    
    middle_name = forms.CharField(
        max_length=50,
        required=False,
        label="Middle Name",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter middle name',
            'pattern': '[A-Za-z\\s\\-\\.\\\']*',
            'title': 'Only letters, spaces, hyphens, dots, and apostrophes allowed'
        }),
        validators=[name_validator, validate_no_numbers],
        error_messages={
            'invalid': 'Invalid characters in middle name.'
        }
    )
    
    last_name = forms.CharField(
        max_length=30,
        label="Last Name",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter last name',
            'pattern': '[A-Za-z\\s\\-\\.\\\']+',
            'title': 'Only letters, spaces, hyphens, dots, and apostrophes allowed'
        }),
        validators=[name_validator, validate_no_numbers],
        error_messages={
            'required': 'Last name is required.',
            'invalid': 'Invalid characters in last name.'
        }
    )
    
    phone_number = forms.CharField(
        max_length=17,
        required=False,
        label="Phone Number",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g., +1234567890 or 1234567890',
            'pattern': '^\\+?[0-9]{9,15}$',
            'title': '9-15 digits with optional + at start'
        }),
        validators=[phone_validator, validate_no_letters_in_phone],
        error_messages={
            'invalid': 'Invalid phone number format.'
        }
    )
    
    class Meta:
        model = TeacherProfile
        fields = ['teacher_id', 'designation', 'department', 'joining_date', 'subjects', 'photo']
        widgets = {
            'teacher_id': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Leave blank to auto-generate',
                'pattern': '[A-Za-z0-9\\-_]*',
                'title': 'Only letters, numbers, hyphens, and underscores allowed'
            }),
            'designation': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter designation (e.g., Professor, Lecturer)'
            }),
            'department': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter department name'
            }),
            'joining_date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
            'subjects': forms.Textarea(attrs={
                'class': 'form-textarea',
                'placeholder': 'Enter subjects separated by commas',
                'rows': 3
            }),
            'photo': forms.FileInput(attrs={
                'class': 'form-input',
                'accept': 'image/*'
            }),
        }
        labels = {
            'teacher_id': 'Teacher ID (Optional)',
            'designation': 'Designation',
            'department': 'Department',
            'joining_date': 'Joining Date',
            'subjects': 'Subjects',
            'photo': 'Profile Photo',
        }
        error_messages = {
            'teacher_id': {
                'unique': 'This Teacher ID already exists.',
                'invalid': 'Invalid characters in Teacher ID.'
            }
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add ID validator to teacher_id field
        self.fields['teacher_id'].validators.append(id_validator)
    
    def clean(self):
        """Form-level validation"""
        cleaned_data = super().clean()
        
        # Additional email validation
        email = cleaned_data.get('email')
        if email:
            # Check if email already exists
            if User.objects.filter(email=email).exists():
                self.add_error('email', 'This email is already registered.')
        
        # Additional phone validation
        phone_number = cleaned_data.get('phone_number')
        if phone_number:
            # Remove spaces and validate
            phone_number = phone_number.replace(' ', '')
            if not re.match(r'^\+?[0-9]+$', phone_number):
                self.add_error('phone_number', 'Phone number can only contain digits and optional +.')
            
            # Check length
            digits = phone_number[1:] if phone_number.startswith('+') else phone_number
            if len(digits) < 9 or len(digits) > 15:
                self.add_error('phone_number', 'Phone number must be 9-15 digits long.')
        
        # Validate names for numbers (additional check)
        for field_name in ['first_name', 'middle_name', 'last_name']:
            field_value = cleaned_data.get(field_name)
            if field_value and any(char.isdigit() for char in field_value):
                self.add_error(field_name, f'{field_name.replace("_", " ").title()} cannot contain numbers.')
        
        return cleaned_data
    
    def save(self, commit=True, created_by=None):
        user_data = {
            'email': self.cleaned_data['email'],
            'first_name': self.cleaned_data['first_name'],
            'last_name': self.cleaned_data['last_name'],
            'phone_number': self.cleaned_data.get('phone_number', ''),
            'role': 'teacher',
        }
        
        # Use mixin method to create user with default password
        user, default_password = self.create_user_with_default_password(**user_data)
        
        if created_by:
            user.created_by = created_by
        
        user.save()
        
        # Create teacher profile
        teacher_profile = super().save(commit=False)
        teacher_profile.user = user
        teacher_profile.middle_name = self.cleaned_data.get('middle_name', '')
        
        # Clean phone number before saving
        if teacher_profile.user.phone_number:
            teacher_profile.user.phone_number = teacher_profile.user.phone_number.replace(' ', '')
        
        if commit:
            teacher_profile.save()
        
        return user, default_password

class StudentCreationForm(DefaultPasswordMixin, forms.ModelForm):
    # Expose a hidden student_id field so model validation has a value
    student_id = forms.CharField(required=False, widget=forms.HiddenInput())

    email = forms.EmailField(
        label="Email ID",
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter email address',
            'pattern': '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'
        }),
        validators=[email_validator, validate_email_domain]
    )
    
    first_name = forms.CharField(
        max_length=30,
        label="First Name",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter first name',
            'pattern': '[A-Za-z\\s\\-\\.\\\']+'
        }),
        validators=[name_validator, validate_no_numbers]
    )
    
    middle_name = forms.CharField(
        max_length=50,
        required=False,
        label="Middle Name",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter middle name',
            'pattern': '[A-Za-z\\s\\-\\.\\\']*'
        }),
        validators=[name_validator, validate_no_numbers]
    )
    
    last_name = forms.CharField(
        max_length=30,
        label="Last Name",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter last name',
            'pattern': '[A-Za-z\\s\\-\\.\\\']+'
        }),
        validators=[name_validator, validate_no_numbers]
    )
    
    phone_number = forms.CharField(
        max_length=17,
        required=False,
        label="Phone Number",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g., +1234567890 or 1234567890',
            'pattern': '^\\+?[0-9]{9,15}$'
        }),
        validators=[phone_validator, validate_no_letters_in_phone]
    )
    
    class Meta:
        model = StudentProfile
        # include student_id as a hidden field so validation can run without errors
        fields = ['student_id', 'date_of_birth', 'gender', 'nationality', 'address', 'photo']
        widgets = {
            'student_id': forms.TextInput(attrs={'type': 'hidden'}),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
            'gender': forms.Select(attrs={
                'class': 'form-select'
            }),
            'nationality': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter nationality',
                'value': 'Nepali'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Enter address',
                'rows': 2
            }),
            'photo': forms.FileInput(attrs={
                'class': 'form-input',
                'accept': 'image/*'
            }),
        }
        labels = {
            'date_of_birth': 'Date of Birth',
            'gender': 'Gender',
            'nationality': 'Nationality',
            'address': 'Address',
            'photo': 'Student Photo',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def clean(self):
        """Form-level validation"""
        cleaned_data = super().clean()
        
        # Email validation
        email = cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            self.add_error('email', 'This email is already registered.')
        
        # Emergency contact validation
        emergency_contact = cleaned_data.get('emergency_contact')
        if emergency_contact:
            emergency_contact = emergency_contact.replace(' ', '')
            if not re.match(r'^\+?[0-9]+$', emergency_contact):
                self.add_error('emergency_contact', 'Invalid emergency contact number.')
        
        return cleaned_data
    
    def save(self, commit=True, created_by=None):
        user_data = {
            'email': self.cleaned_data['email'],
            'first_name': self.cleaned_data['first_name'],
            'last_name': self.cleaned_data['last_name'],
            'phone_number': self.cleaned_data.get('phone_number', ''),
            'role': 'student',
        }
        
        # Use mixin method to create user with default password
        user, password = self.create_user_with_default_password(**user_data)
        
        if created_by:
            user.created_by = created_by
        
        user.save()
        
        # Create student profile (ModelForm save without commit)
        student_profile = super().save(commit=False)
        student_profile.user = user
        student_profile.middle_name = self.cleaned_data.get('middle_name', '')
        
        # Clean phone numbers before saving
        if student_profile.user.phone_number:
            student_profile.user.phone_number = student_profile.user.phone_number.replace(' ', '')
        
        # Don't save yet - let view set student_id first
        if commit:
            student_profile.save()
        
        return user, password

class GuardianCreationForm(DefaultPasswordMixin, forms.ModelForm):
    email = forms.EmailField(
        label="Email ID",
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter email address',
            'pattern': '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'
        }),
        validators=[email_validator, validate_email_domain]
    )
    
    first_name = forms.CharField(
        max_length=30,
        label="First Name",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter first name',
            'pattern': '[A-Za-z\\s\\-\\.\\\']+'
        }),
        validators=[name_validator, validate_no_numbers]
    )
    
    middle_name = forms.CharField(
        max_length=50,
        required=False,
        label="Middle Name",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter middle name',
            'pattern': '[A-Za-z\\s\\-\\.\\\']*'
        }),
        validators=[name_validator, validate_no_numbers]
    )
    
    last_name = forms.CharField(
        max_length=30,
        label="Last Name",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter last name',
            'pattern': '[A-Za-z\\s\\-\\.\\\']+'
        }),
        validators=[name_validator, validate_no_numbers]
    )
    
    phone_number = forms.CharField(
        max_length=17,
        required=False,
        label="Phone Number",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g., +1234567890 or 1234567890',
            'pattern': '^\\+?[0-9]{9,15}$'
        }),
        validators=[phone_validator, validate_no_letters_in_phone]
    )
    
    class Meta:
        model = GuardianProfile
        fields = ['guardian_id', 'relation_to_student', 'occupation', 'address', 'photo']
        widgets = {
            'guardian_id': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter guardian ID',
                'pattern': '[A-Za-z0-9\\-_]+'
            }),
            'relation_to_student': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Father, Mother, Guardian'
            }),
            'occupation': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter occupation'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-textarea',
                'placeholder': 'Enter complete address',
                'rows': 3
            }),
            'photo': forms.FileInput(attrs={
                'class': 'form-input',
                'accept': 'image/*'
            }),
        }
        labels = {
            'guardian_id': 'Guardian ID',
            'relation_to_student': 'Relation to Student',
            'occupation': 'Occupation',
            'address': 'Address',
            'photo': 'Guardian Photo',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add ID validator to guardian_id field
        self.fields['guardian_id'].validators.append(id_validator)
    
    def clean(self):
        """Form-level validation"""
        cleaned_data = super().clean()
        
        # Email validation
        email = cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            self.add_error('email', 'This email is already registered.')
        
        # Guardian ID validation
        guardian_id = cleaned_data.get('guardian_id')
        if guardian_id and GuardianProfile.objects.filter(guardian_id=guardian_id).exists():
            self.add_error('guardian_id', 'This Guardian ID already exists.')
        
        return cleaned_data
    
    def save(self, commit=True, created_by=None):
        user_data = {
            'email': self.cleaned_data['email'],
            'first_name': self.cleaned_data['first_name'],
            'last_name': self.cleaned_data['last_name'],
            'phone_number': self.cleaned_data.get('phone_number', ''),
            'role': 'guardian',
        }
        
        # Use mixin method to create user with default password
        user, password = self.create_user_with_default_password(**user_data)
        
        if created_by:
            user.created_by = created_by
        
        user.save()
        
        guardian_profile = super().save(commit=False)
        guardian_profile.user = user
        guardian_profile.middle_name = self.cleaned_data.get('middle_name', '')
        
        # Clean phone number before saving
        if guardian_profile.user.phone_number:
            guardian_profile.user.phone_number = guardian_profile.user.phone_number.replace(' ', '')
        
        if commit:
            guardian_profile.save()
        
        return user, password

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your email',
            'pattern': '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$',
            'title': 'Please enter a valid email address'
        }),
        validators=[validate_email_domain],
        error_messages={
            'required': 'Email is required.',
            'invalid': 'Please enter a valid email address.'
        }
    )
    
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your password'
        }),
        error_messages={
            'required': 'Password is required.'
        }
    )
    
    def clean(self):
        """Custom authentication form validation"""
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        
        # Additional email validation
        if username and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', username):
            self.add_error('username', 'Please enter a valid email address.')
        
        return cleaned_data


# ==================== BATCH FORMS ====================

class BatchForm(forms.ModelForm):
    """Form for creating and editing batches"""
    class Meta:
        model = Batch
        fields = ['name', 'description', 'year', 'start_date', 'end_date', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Batch 2080, Class of 2024'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'placeholder': 'Optional description about the batch',
                'rows': 3
            }),
            'year': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., 2080',
                'min': 2000,
                'max': 2100,
                'maxlength': '4',
                'oninput': 'if(this.value.length>4) this.value=this.value.slice(0,4);'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            })
        }


    def clean_year(self):
        yr = self.cleaned_data.get('year')
        if yr is not None:
            s = str(yr)
            if len(s) != 4:
                raise forms.ValidationError('Year must be exactly 4 digits.')
            if not s.isdigit():
                raise forms.ValidationError('Year must contain only numbers.')
        return yr

class BatchCourseForm(forms.ModelForm):
    """Form for adding courses to batches"""
    class Meta:
        model = BatchCourse
        fields = ['course', 'is_active']
        widgets = {
            'course': forms.Select(attrs={
                'class': 'form-select'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            })
        }