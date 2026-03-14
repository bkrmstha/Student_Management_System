# ============================================================================
# User Management Views - School Management System
# ============================================================================
# This file contains all views related to user authentication, dashboard,
# profile management, and user administration (teachers, students, guardians).
# ============================================================================

from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.db.models import Q
from .forms import (
    CustomAuthenticationForm, StudentCreationForm, 
    TeacherCreationForm, GuardianCreationForm
)
from .models import User, StudentProfile, TeacherProfile, GuardianProfile, GuardianStudentRelationship, Batch, StudentCourseEnrollment
from django.db.models import Prefetch
from courses.models import Course
import secrets
import uuid

# ============================================================================
# DECORATORS
# ============================================================================

def admin_required(view_func):
    """
    Custom decorator to restrict access to admin users only.
    
    Usage:
        @login_required
        @admin_required
        def my_view(request):
            ...
    
    Returns:
        Decorated view function that checks if user is authenticated and is_admin
    """
    actual_decorator = user_passes_test(
        lambda u: u.is_authenticated and u.is_admin,
        login_url='login'
    )
    return actual_decorator(view_func)


# ============================================================================
# AUTHENTICATION VIEWS
# ============================================================================

def login_view(request):
    """
    Handle user login.
    
    - If user is already authenticated, redirect to appropriate dashboard
    - Process login form submission
    - Authenticate user using email and password
    - Display error messages for invalid credentials
    
    GET: Display login form
    POST: Process login attempt
    """
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=email, password=password)
            
            if user is not None:
                login(request, user)
                return redirect('dashboard_redirect')
            else:
                messages.error(request, 'Invalid email or password.')
        else:
            messages.error(request, 'Invalid email or password.')
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'auth/login.html', {'form': form})


def logout_view(request):
    """
    Log out the current user and redirect to login page.
    """
    logout(request)
    return redirect('login')


@login_required
def dashboard_redirect(request):
    """
    Redirect users to their role-specific dashboard.
    
    Based on user role:
    - Admin → admin_dashboard
    - Teacher → teacher_dashboard
    - Student → student_dashboard
    - Guardian → guardian_dashboard
    - Unknown role → login page
    """
    if request.user.is_admin:
        return redirect('admin_dashboard')
    elif request.user.is_teacher:
        return redirect('teacher_dashboard')
    elif request.user.is_student:
        return redirect('student_dashboard')
    elif request.user.is_guardian:
        return redirect('guardian_dashboard')
    else:
        return redirect('login')


# ============================================================================
# ADMIN DASHBOARD VIEWS
# ============================================================================

@login_required
@admin_required
def admin_dashboard(request):
    """
    Admin dashboard showing overview of the system.
    
    Displays:
    - Count statistics (teachers, students, batches, courses)
    - Latest notice
    - Today's absent students grouped by batch and course
    """
    from courses.models import Course
    from attendance.models import AttendanceRecord, AttendanceSession
    from noticeboard.models import Notice
    from django.utils import timezone
    from django.db.models import Prefetch
    
    # Statistics cards data
    teachers_count = User.objects.filter(role='teacher').count()
    students_count = User.objects.filter(role='student').count()
    batches_count = Batch.objects.count()
    courses_count = Course.objects.count()
    
    # Get latest notice
    latest_notice = Notice.objects.all().order_by('-created_at').first()
    
    # Get today's absent records
    today = timezone.now().date()
    absent_records = AttendanceRecord.objects.filter(
        status='absent',
        date=today
    ).select_related(
        'student__user',
        'student__batch',
        'session__course',
        'session__batch'
    ).order_by('session__batch', 'session__course', 'student__user__last_name')
    
    # Group absent students by batch and course for organized display
    absent_by_batch_course = {}
    for record in absent_records:
        batch = record.session.batch
        course = record.session.course
        batch_key = f"{batch.id}"
        
        if batch_key not in absent_by_batch_course:
            absent_by_batch_course[batch_key] = {
                'batch': batch,
                'courses': {}
            }
        
        course_key = f"{course.id}" if course else "no_course"
        if course_key not in absent_by_batch_course[batch_key]['courses']:
            absent_by_batch_course[batch_key]['courses'][course_key] = {
                'course': course,
                'students': []
            }
        
        absent_by_batch_course[batch_key]['courses'][course_key]['students'].append(record.student)
    
    context = {
        'teachers_count': teachers_count,
        'students_count': students_count,
        'batches_count': batches_count,
        'courses_count': courses_count,
        'latest_notice': latest_notice,
        'absent_by_batch_course': absent_by_batch_course,
        'absent_count': absent_records.count(),
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
@admin_required
def user_list(request):
    """
    General user list for admin. Returns users grouped by role.

    Optional GET params:
    - `role`: filter to a single role (teacher/student/guardian)
    - `search`: search by name or email
    
    Groups users into:
    - Teachers
    - Students
    - Guardians (with prefetched student relationships)
    - Other roles
    """
    role = request.GET.get('role', '')
    search = request.GET.get('search', '')

    base_q = User.objects.all().order_by('-date_created')
    if search:
        base_q = base_q.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )

    # Prepare grouped querysets
    teachers = base_q.filter(role='teacher')
    students = base_q.filter(role='student')
    # prefetch guardian-student relationships to avoid N+1 queries
    guardians = base_q.filter(role='guardian').prefetch_related(
        Prefetch('students', queryset=GuardianStudentRelationship.objects.select_related('student'))
    )
    others = base_q.exclude(role__in=['teacher', 'student', 'guardian'])

    # If a specific role filter is provided, only show that group
    if role == 'teacher':
        teachers = teachers
        students = students.none()
        guardians = guardians.none()
        others = others.none()
    elif role == 'student':
        students = students
        teachers = teachers.none()
        guardians = guardians.none()
        others = others.none()
    elif role == 'guardian':
        guardians = guardians
        teachers = teachers.none()
        students = students.none()
        others = others.none()

    context = {
        'teachers': teachers,
        'students': students,
        'guardians': guardians,
        'others': others,
        'filter_role': role,
        'search_query': search,
    }
    return render(request, 'admin/users/user_list.html', context)


# ============================================================================
# TEACHER DASHBOARD AND MANAGEMENT VIEWS
# ============================================================================

@login_required
def teacher_dashboard(request):
    """
    Teacher dashboard showing relevant information.
    
    Displays:
    - Teacher profile information
    - Statistics (subjects, courses, students)
    - Today's absent students count
    - Latest relevant notices
    """
    if not request.user.is_teacher:
        return redirect('login')
    
    teacher_profile = None
    if hasattr(request.user, 'teacher_profile'):
        teacher_profile = request.user.teacher_profile
    # Stats for teacher
    subjects_count = request.user.subjects_taught.count() if request.user else 0
    # number of distinct courses the teacher teaches (via Subject.course)
    courses_count = Course.objects.filter(subjects__teacher=request.user).distinct().count()
    # number of distinct students across those courses
    students_count = StudentCourseEnrollment.objects.filter(course__subjects__teacher=request.user).values('student').distinct().count()

    # Get today's absent count for teacher's students
    from attendance.models import AttendanceRecord
    from django.utils import timezone
    today = timezone.now().date()
    absent_count = AttendanceRecord.objects.filter(
        status='absent',
        date=today,
        session__teacher=request.user
    ).values('student').distinct().count()

    context = {
        'teacher_profile': teacher_profile,
        'subjects_count': subjects_count,
        'courses_count': courses_count,
        'students_count': students_count,
        'absent_count': absent_count,
    }
    # Latest notice relevant to the teacher
    from noticeboard.models import Notice
    from django.utils import timezone as dj_tz
    now = dj_tz.now()
    notices_qs = Notice.objects.filter(is_active=True).filter(
        Q(expires_at__gt=now) | Q(expires_at__isnull=True)
    )
    # teacher-relevant: all, teachers, or notices targeting courses they teach
    course_ids = Course.objects.filter(subjects__teacher=request.user).values_list('id', flat=True)
    notices_qs = notices_qs.filter(
        Q(audience_type='all') | Q(audience_type='teachers') | Q(courses__in=course_ids)
    ).distinct().order_by('-created_at')
    context['latest_notice'] = notices_qs.first()
    # If no audience-specific notice found, fall back to any active notice
    if not context['latest_notice']:
        fallback = Notice.objects.filter(is_active=True).filter(
            Q(expires_at__gt=now) | Q(expires_at__isnull=True)
        ).order_by('-created_at').first()
        context['latest_notice'] = fallback
    return render(request, 'dashboard/teacher_dashboard.html', context)


@login_required
@admin_required
def create_teacher(request):
    """
    Create a new teacher account with detailed information.
    
    Process:
    1. Display teacher creation form (GET)
    2. Process form submission (POST)
    3. Create teacher user and profile
    4. Send credentials email to the teacher
    5. Display success message with default password
    
    The form includes fields for:
    - Personal information (name, email, phone, photo)
    - Professional information (teacher ID, department, designation, subjects, qualification)
    """
    if request.method == 'POST':
        form = TeacherCreationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                user, password = form.save(created_by=request.user)
                email_sent = send_credentials_email(user, password)
                
                # Show success message with default password
                email_status = '✅ Email sent with credentials' if email_sent else '⚠️ Email could not be sent (check console)'
                messages.success(request, 
                    f'✅ Teacher account created successfully!<br>'
                    f'<strong>Email:</strong> {user.email}<br>'
                    f'<strong>Default Password:</strong> <code>{password}</code><br>'
                    f'{email_status}'
                )
                
                return redirect('teacher_list')  # Changed from user_list to teacher_list
            except Exception as e:
                messages.error(request, f'❌ Error creating teacher account: {str(e)}')
    else:
        form = TeacherCreationForm()
    
    context = {
        'form': form,
    }
    return render(request, 'admin/teachers/create_teacher.html', context)


@login_required
@admin_required
def teacher_list(request):
    """
    Display list of all teachers with filtering options.
    
    Filter options:
    - Search by name, email, department, or subjects
    - Filter by department
    - Filter by status (active/inactive)
    
    Also displays statistics:
    - Active/Inactive teacher counts
    - Unique departments count
    - Unique designations count
    """
    teachers = User.objects.filter(role='teacher').order_by('teacher_profile__teacher_id')
    
    # Get filter parameters
    search = request.GET.get('search', '')
    department_filter = request.GET.get('department', '')
    status_filter = request.GET.get('status', '')
    
    # Apply filters
    if search:
        teachers = teachers.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(teacher_profile__department__icontains=search) |
            Q(teacher_profile__subjects__icontains=search)
        )
    
    if department_filter:
        teachers = teachers.filter(teacher_profile__department=department_filter)
    
    if status_filter == 'active':
        teachers = teachers.filter(is_active=True)
    elif status_filter == 'inactive':
        teachers = teachers.filter(is_active=False)
    
    # Get counts for stats (removed from template but kept for context if needed)
    active_count = User.objects.filter(role='teacher', is_active=True).count()
    inactive_count = User.objects.filter(role='teacher', is_active=False).count()
    
    # Get unique departments
    departments = TeacherProfile.objects.exclude(department='').values_list('department', flat=True).distinct()
    departments_count = departments.count()
    
    # Get unique designations count
    designations_count = TeacherProfile.objects.exclude(designation='').values_list('designation', flat=True).distinct().count()
    
    context = {
        'teachers': teachers,
        'search_query': search,
        'department_filter': department_filter,
        'status_filter': status_filter,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'departments': departments,
        'departments_count': departments_count,
        'designations_count': designations_count,
    }
    
    return render(request, 'admin/teachers/teacher_list.html', context)


@login_required
@admin_required
def view_teacher(request, teacher_id):
    """
    Display detailed view of a single teacher.
    
    Shows:
    - Teacher personal information
    - Professional details (ID, department, designation)
    - Assigned subjects/courses
    """
    teacher = get_object_or_404(User, id=teacher_id, role='teacher')
    teacher_profile = get_object_or_404(TeacherProfile, user=teacher)
    assigned_subjects = teacher.subjects_taught.all().order_by('course__name', 'code')
    
    context = {
        'teacher': teacher,
        'profile': teacher_profile,
        'assigned_subjects': assigned_subjects,
    }
    return render(request, 'admin/teachers/view_teacher.html', context)


@login_required
@admin_required
def edit_teacher(request, teacher_id):
    """
    Edit teacher account and profile information.
    
    Allows updating:
    - User information (name, email, phone)
    - Profile information (teacher ID, department, designation, subjects, qualification, DOB)
    - Photo upload
    """
    teacher = get_object_or_404(User, id=teacher_id, role='teacher')
    teacher_profile = get_object_or_404(TeacherProfile, user=teacher)
    
    if request.method == 'POST':
        teacher.first_name = request.POST.get('first_name')
        teacher.last_name = request.POST.get('last_name')
        teacher.email = request.POST.get('email')
        teacher.phone_number = request.POST.get('phone_number')
        teacher.save()
        
        teacher_profile.middle_name = request.POST.get('middle_name', '')
        teacher_profile.teacher_id = request.POST.get('teacher_id')
        teacher_profile.department = request.POST.get('department', '')
        teacher_profile.designation = request.POST.get('designation', '')
        teacher_profile.subjects = request.POST.get('subjects', '')
        teacher_profile.qualification = request.POST.get('qualification', '')
        teacher_profile.date_of_birth = request.POST.get('date_of_birth') or None
        
        if 'photo' in request.FILES:
            teacher_profile.photo = request.FILES['photo']
        
        teacher_profile.save()
        
        messages.success(request, 'Teacher account updated successfully!')
        return redirect('teacher_list')
    
    context = {
        'teacher': teacher,
        'profile': teacher_profile,
    }
    return render(request, 'admin/teachers/edit_teacher.html', context)


# ============================================================================
# STUDENT DASHBOARD AND MANAGEMENT VIEWS
# ============================================================================

@login_required
def student_dashboard(request):
    """
    Student dashboard showing relevant information.
    
    Displays:
    - Student profile information
    - Number of enrolled courses
    - Latest relevant notices (targeting all, students, their batch, or their courses)
    """
    if not request.user.is_student:
        return redirect('login')
    
    student_profile = None
    if hasattr(request.user, 'student_profile'):
        student_profile = request.user.student_profile
    # Student stats
    courses_count = 0
    if student_profile:
        courses_count = StudentCourseEnrollment.objects.filter(student=student_profile).count()

    context = {
        'student_profile': student_profile,
        'courses_count': courses_count,
    }
    # Latest notice relevant to the student
    from noticeboard.models import Notice
    from django.utils import timezone as dj_tz
    now = dj_tz.now()
    notices_qs = Notice.objects.filter(is_active=True).filter(
        Q(expires_at__gt=now) | Q(expires_at__isnull=True)
    )
    if student_profile and student_profile.batch:
        notices_qs = notices_qs.filter(
            Q(audience_type='all') | Q(audience_type='students') | Q(batches=student_profile.batch) | Q(courses__in=student_profile.enrolled_courses.all())
        ).distinct().order_by('-created_at')
    else:
        notices_qs = notices_qs.filter(Q(audience_type='all') | Q(audience_type='students')).order_by('-created_at')
    context['latest_notice'] = notices_qs.first()
    if not context['latest_notice']:
        fallback = Notice.objects.filter(is_active=True).filter(
            Q(expires_at__gt=now) | Q(expires_at__isnull=True)
        ).order_by('-created_at').first()
        context['latest_notice'] = fallback
    return render(request, 'dashboard/student_dashboard.html', context)


@login_required
@admin_required
def student_list(request):
    """
    Display list of all students with filtering options.
    
    Filter options:
    - Search by name, email, or student ID
    - Filter by batch
    - Filter by course
    
    Also displays:
    - Active/Inactive student counts
    - Today's absent students grouped by batch and course
    """
    from attendance.models import AttendanceRecord
    from django.utils import timezone
    
    students = StudentProfile.objects.filter(user__role='student').select_related('user', 'batch').order_by('student_id')
    
    # Get filter parameters
    search = request.GET.get('search', '')
    batch_filter = request.GET.get('batch', '')
    course_filter = request.GET.get('course', '')
    
    # Apply filters
    if search:
        students = students.filter(
            Q(user__email__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(student_id__icontains=search)
        )
    
    if batch_filter:
        students = students.filter(batch_id=batch_filter)
    
    if course_filter:
        students = students.filter(enrolled_courses__id=course_filter)
    
    students = students.distinct()
    
    # Get counts for stats
    active_count = User.objects.filter(role='student', is_active=True).count()
    inactive_count = User.objects.filter(role='student', is_active=False).count()
    
    # Get unique batches
    batches = Batch.objects.all().order_by('year', 'name')
    
    # Get all courses
    courses = Course.objects.all().order_by('name')
    
    # Get today's absent records
    today = timezone.now().date()
    absent_records = AttendanceRecord.objects.filter(
        status='absent',
        date=today
    ).select_related(
        'student__user',
        'student__batch',
        'session__course',
        'session__batch'
    ).order_by('session__batch', 'session__course', 'student__user__last_name')
    
    # Group absent students by batch and course
    absent_by_batch_course = {}
    for record in absent_records:
        batch = record.session.batch
        course = record.session.course
        batch_key = f"{batch.id}"
        
        if batch_key not in absent_by_batch_course:
            absent_by_batch_course[batch_key] = {
                'batch': batch,
                'courses': {}
            }
        
        course_key = f"{course.id}" if course else "no_course"
        if course_key not in absent_by_batch_course[batch_key]['courses']:
            absent_by_batch_course[batch_key]['courses'][course_key] = {
                'course': course,
                'students': []
            }
        
        absent_by_batch_course[batch_key]['courses'][course_key]['students'].append(record.student)
    
    context = {
        'students': students,
        'search_query': search,
        'batch_filter': batch_filter,
        'course_filter': course_filter,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'batches': batches,
        'courses': courses,
        'absent_by_batch_course': absent_by_batch_course,
        'absent_count': absent_records.count(),
    }
    
    return render(request, 'admin/students/all_student_list.html', context)


@login_required
def absent_list(request):
    """
    Display today's absent students organized by batch and course.
    - Admins see all absent students
    - Teachers see only their own students' absences
    
    Returns:
        Forbidden response if user is neither admin nor teacher
    """
    from courses.models import Course
    from attendance.models import AttendanceRecord
    from django.utils import timezone
    
    today = timezone.now().date()
    
    # Build queryset based on user role
    if request.user.is_staff or request.user.is_superuser:
        # Admins see all absent students
        absent_records = AttendanceRecord.objects.filter(
            status='absent',
            date=today
        )
    elif request.user.role == 'teacher':
        # Teachers see only their own students' absences
        absent_records = AttendanceRecord.objects.filter(
            status='absent',
            date=today,
            session__teacher=request.user
        )
    else:
        # Other users don't have access
        return HttpResponseForbidden("Access Denied")
    
    absent_records = absent_records.select_related(
        'student__user',
        'student__batch',
        'session__course',
        'session__batch'
    ).order_by('session__batch', 'session__course', 'student__user__last_name')
    
    # Group absent students by batch and course
    absent_by_batch_course = {}
    for record in absent_records:
        batch = record.session.batch
        course = record.session.course
        batch_key = f"{batch.id}"
        
        if batch_key not in absent_by_batch_course:
            absent_by_batch_course[batch_key] = {
                'batch': batch,
                'courses': {}
            }
        
        course_key = f"{course.id}" if course else "no_course"
        if course_key not in absent_by_batch_course[batch_key]['courses']:
            absent_by_batch_course[batch_key]['courses'][course_key] = {
                'course': course,
                'students': []
            }
        
        absent_by_batch_course[batch_key]['courses'][course_key]['students'].append(record.student)
    
    context = {
        'absent_by_batch_course': absent_by_batch_course,
        'absent_count': absent_records.count(),
        'today': today,
    }
    
    return render(request, 'admin/students/absent_list.html', context)


@login_required
@admin_required
def create_student(request):
    """
    Create a new student account.
    
    Process:
    1. Display student creation form (GET)
    2. Process form submission (POST)
    3. Generate student ID based on batch year and course short name
    4. Create student user and profile
    5. Enroll student in selected course
    6. Create guardian users (father/mother) if provided
    7. Send credentials emails to student and guardians
    8. Support both AJAX and regular form submissions
    
    Student ID format: {batch_year}{course_short_name}{sequential_number:04d}
    Example: 2023BCA0001
    """
    if request.method == 'POST':
        form = StudentCreationForm(request.POST, request.FILES)
        if not getattr(form.instance, 'student_id', None):
            form.instance.student_id = f"TMP-{uuid.uuid4().hex[:12].upper()}"

        if form.is_valid():
            try:
                # Get batch and course info for student ID generation
                batch_id = request.POST.get('batch')
                course_id = request.POST.get('course')
                batch_obj = None
                course_obj = None
                student_id = None

                if batch_id and course_id:
                    try:
                        batch_obj = Batch.objects.get(pk=batch_id)
                        from courses.models import Course as CourseModel
                        course_obj = CourseModel.objects.get(pk=course_id)

                        # Generate student ID like add_student_to_course does
                        last_student = StudentProfile.objects.filter(
                            batch=batch_obj,
                            enrolled_courses=course_obj
                        ).order_by('-student_id').first()

                        if last_student and last_student.student_id:
                            import re
                            match = re.search(r'(\d{4})$', last_student.student_id)
                            if match:
                                number = int(match.group(1)) + 1
                            else:
                                number = 1
                        else:
                            number = 1

                        student_id = f"{batch_obj.year}{course_obj.short_name}{number:04d}"
                    except Exception:
                        pass

                # Create user with form (commit=False so view can set profile fields)
                user, password = form.save(created_by=request.user, commit=False)
                # Ensure user is saved
                user.save()

                # Ensure a StudentProfile exists and is saved before using M2M relations
                student_profile, created = StudentProfile.objects.get_or_create(user=user)

                # Set student_id - either from generated one or create a default
                if student_id:
                    student_profile.student_id = student_id
                elif not student_profile.student_id:
                    student_profile.student_id = f"STD-{uuid.uuid4().hex[:12].upper()}"

                # Assign batch
                if batch_obj:
                    student_profile.batch = batch_obj

                # Save profile before adding many-to-many relations
                student_profile.save()

                # Enroll in course (requires saved profile)
                if course_obj:
                    student_profile.enrolled_courses.add(course_obj)

                # Create guardian users and relationships if guardian data provided
                try:
                    father_name = request.POST.get('father_name', '').strip()
                    father_email = request.POST.get('father_email', '').strip()
                    father_phone = request.POST.get('father_phone', '').strip()

                    mother_name = request.POST.get('mother_name', '').strip()
                    mother_email = request.POST.get('mother_email', '').strip()
                    mother_phone = request.POST.get('mother_phone', '').strip()

                    def _create_or_get_guardian(name, email, phone, relation_label):
                        """
                        Helper function to create or get a guardian user and establish relationship.
                        
                        Args:
                            name: Full name of guardian
                            email: Email address
                            phone: Phone number
                            relation_label: 'Father' or 'Mother'
                        
                        Returns:
                            Guardian User object or None
                        """
                        if not name:
                            return None

                        parts = name.split()
                        first = parts[0]
                        last = ' '.join(parts[1:]) if len(parts) > 1 else ''

                        guardian_user = None
                        guardian_password = 'Guardian@123'
                        created = False
                        
                        if email:
                            guardian_user = User.objects.filter(email__iexact=email).first()
                            if guardian_user and guardian_user.role != 'guardian':
                                guardian_user.role = 'guardian'
                                guardian_user.save()

                        if not guardian_user:
                            if not email:
                                email = f"guardian-{uuid.uuid4().hex[:8]}@example.com"

                            guardian_user = User(
                                email=email,
                                first_name=first,
                                last_name=last or 'Guardian',
                                phone_number=phone or '',
                                role='guardian'
                            )
                            guardian_user.set_password(guardian_password)
                            guardian_user.save()
                            created = True
                            # Send credentials email to newly created guardian
                            send_credentials_email(guardian_user, guardian_password)

                        try:
                            gp = getattr(guardian_user, 'guardian_profile', None)
                            if not gp:
                                from .models import GuardianProfile
                                gid = f"GN{uuid.uuid4().hex[:8]}"
                                gp = GuardianProfile.objects.create(
                                    user=guardian_user,
                                    guardian_id=gid,
                                    relation_to_student=relation_label
                                )
                            else:
                                if not gp.relation_to_student and relation_label:
                                    gp.relation_to_student = relation_label
                                    gp.save()
                        except Exception:
                            pass

                        try:
                            GuardianStudentRelationship.objects.get_or_create(
                                guardian=guardian_user,
                                student=user,
                                defaults={'is_primary': True if relation_label.lower() == 'father' else False}
                            )
                        except Exception:
                            pass

                        return guardian_user

                    _create_or_get_guardian(father_name, father_email, father_phone, 'Father')
                    _create_or_get_guardian(mother_name, mother_email, mother_phone, 'Mother')
                except Exception:
                    pass

                email_sent = send_credentials_email(user, password)
                email_status = 'Credentials have been sent via email.' if email_sent else '(Email could not be sent - check console)'
                
                is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                if is_ajax:
                    from django.http import JsonResponse
                    return JsonResponse({
                        'success': True,
                        'message': f'Student {user.get_full_name()} created successfully.'
                    })
                else:
                    messages.success(request, f'Student account created successfully! {email_status}')
                    return redirect('student_list')
            except Exception as e:
                is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                if is_ajax:
                    from django.http import JsonResponse
                    return JsonResponse({
                        'success': False,
                        'errors': {'general': [str(e)]}
                    }, status=400)
                else:
                    messages.error(request, f'Error creating student account: {str(e)}')
        else:
            # Form validation failed
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            if is_ajax:
                from django.http import JsonResponse
                # Convert form errors to a dictionary
                errors = {}
                for field, error_list in form.errors.items():
                    errors[field] = [str(e) for e in error_list]
                return JsonResponse({
                    'success': False,
                    'errors': errors
                }, status=400)
            else:
                messages.error(request, 'Please correct the errors below.')
    else:
        form = StudentCreationForm()
    
    # Provide batches and courses for dropdowns
    from courses.models import Course as CourseModel
    batches = Batch.objects.all().order_by('year', 'name')
    courses = CourseModel.objects.all().order_by('name')

    context = {
        'form': form,
        'batches': batches,
        'courses': courses,
    }
    return render(request, 'admin/students/create_student.html', context)


@login_required
@admin_required
def view_student(request, student_id):
    """
    View detailed student information.
    
    Shows:
    - Student personal information
    - Student ID and batch
    - Guardian information (father and mother with contact details)
    """
    student = get_object_or_404(StudentProfile, id=student_id)
    
    # Get guardian information through relationships
    father_info = {}
    mother_info = {}
    
    # Get guardian relationships for this student
    relationships = GuardianStudentRelationship.objects.filter(student=student.user).select_related('guardian', 'guardian__guardian_profile')
    
    for relationship in relationships:
        guardian_profile = relationship.guardian.guardian_profile
        if guardian_profile.relation_to_student.lower() == 'father':
            father_info = {
                'name': relationship.guardian.get_full_name(),
                'email': relationship.guardian.email,
                'phone': relationship.guardian.phone_number,
            }
        elif guardian_profile.relation_to_student.lower() == 'mother':
            mother_info = {
                'name': relationship.guardian.get_full_name(),
                'email': relationship.guardian.email,
                'phone': relationship.guardian.phone_number,
            }
    
    context = {
        'student': student,
        'father_name': father_info.get('name'),
        'father_email': father_info.get('email'),
        'father_phone': father_info.get('phone'),
        'mother_name': mother_info.get('name'),
        'mother_email': mother_info.get('email'),
        'mother_phone': mother_info.get('phone'),
    }
    
    return render(request, 'admin/students/view_student.html', context)


@login_required
@admin_required
def edit_student(request, student_id):
    """
    Edit student information.
    
    Allows updating:
    - Student user information (name, email, phone)
    - Student profile (ID, DOB, address, etc.)
    - Guardian information (father and mother details)
    
    If guardian emails are provided but users don't exist, they are created.
    If guardians exist but have different roles, shows error.
    """
    student = get_object_or_404(StudentProfile, id=student_id)
    
    if request.method == 'POST':
        try:
            # Update user information
            student.user.first_name = request.POST.get('first_name')
            student.user.last_name = request.POST.get('last_name')
            student.user.email = request.POST.get('email')
            student.user.phone_number = request.POST.get('phone_number', '')
            student.user.save()
            
            # Update student profile
            student.student_id = request.POST.get('student_id', student.student_id)
            student.middle_name = request.POST.get('middle_name', '')
            student.address = request.POST.get('address', '')
            student.date_of_birth = request.POST.get('date_of_birth') or None
            student.gender = request.POST.get('gender', '')
            student.nationality = request.POST.get('nationality', 'Nepali')
            student.emergency_contact = request.POST.get('emergency_contact', '')
            
            if 'photo' in request.FILES:
                student.photo = request.FILES['photo']
            
            student.save()
            
            # Handle father information
            father_email = request.POST.get('father_email', '').strip()
            if father_email:
                father_name = request.POST.get('father_name', '').strip()
                father_phone = request.POST.get('father_phone', '').strip()
                
                if father_name:
                    name_parts = father_name.split()
                    father_first_name = name_parts[0] if name_parts else ''
                    father_last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                    
                    father_user = User.objects.filter(email=father_email).first()
                    guardian_password = 'Guardian@123'
                    created = False
                    if not father_user:
                        father_user = User.objects.create_user(
                            email=father_email,
                            password=guardian_password,
                            first_name=father_first_name,
                            last_name=father_last_name,
                            phone_number=father_phone,
                            role='guardian'
                        )
                        created = True
                        # Send credentials email to newly created father guardian
                        send_credentials_email(father_user, guardian_password)
                    
                    # If the user existed but does not have guardian role, abort with a clear message
                    if not created and father_user.role != 'guardian':
                        messages.error(request, (
                            f"Email {father_email} belongs to an existing '{father_user.role}' account. "
                            "Use a different email or convert that account to a guardian before linking."
                        ))
                        return redirect('edit_student', student_id=student.id)

                    # Ensure GuardianProfile exists even if user already existed
                    GuardianProfile.objects.get_or_create(
                        user=father_user,
                        defaults={
                            'guardian_id': f"G{father_user.id:04d}",
                            'relation_to_student': 'Father'
                        }
                    )
                    
                    # Create or update relationship
                    relationship, created = GuardianStudentRelationship.objects.get_or_create(
                        guardian=father_user,
                        student=student.user,
                        defaults={'is_primary': True}
                    )
                    
                    # Update father user info if not created
                    if not created:
                        father_user.first_name = father_first_name
                        father_user.last_name = father_last_name
                        father_user.phone_number = father_phone
                        father_user.save()
            
            # Handle mother information
            mother_email = request.POST.get('mother_email', '').strip()
            if mother_email:
                mother_name = request.POST.get('mother_name', '').strip()
                mother_phone = request.POST.get('mother_phone', '').strip()
                
                if mother_name:
                    name_parts = mother_name.split()
                    mother_first_name = name_parts[0] if name_parts else ''
                    mother_last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                    
                    mother_user = User.objects.filter(email=mother_email).first()
                    guardian_password = 'Guardian@123'
                    created = False
                    if not mother_user:
                        mother_user = User.objects.create_user(
                            email=mother_email,
                            password=guardian_password,
                            first_name=mother_first_name,
                            last_name=mother_last_name,
                            phone_number=mother_phone,
                            role='guardian'
                        )
                        created = True
                        # Send credentials email to newly created mother guardian
                        send_credentials_email(mother_user, guardian_password)
                    
                    # If the user existed but does not have guardian role, abort with a clear message
                    if not created and mother_user.role != 'guardian':
                        messages.error(request, (
                            f"Email {mother_email} belongs to an existing '{mother_user.role}' account. "
                            "Use a different email or convert that account to a guardian before linking."
                        ))
                        return redirect('edit_student', student_id=student.id)

                    # Ensure GuardianProfile exists even if user already existed
                    GuardianProfile.objects.get_or_create(
                        user=mother_user,
                        defaults={
                            'guardian_id': f"G{mother_user.id:04d}",
                            'relation_to_student': 'Mother'
                        }
                    )
                    
                    # Create or update relationship
                    relationship, created = GuardianStudentRelationship.objects.get_or_create(
                        guardian=mother_user,
                        student=student.user,
                        defaults={'is_primary': False}
                    )
                    
                    # Update mother user info if not created
                    if not created:
                        mother_user.first_name = mother_first_name
                        mother_user.last_name = mother_last_name
                        mother_user.phone_number = mother_phone
                        mother_user.save()
            
            messages.success(request, 'Student information updated successfully!')
            return redirect('view_student', student_id=student.id)
            
        except Exception as e:
            messages.error(request, f'Error updating student: {str(e)}')
    
    # Get existing guardian information for form
    father_info = {}
    mother_info = {}
    
    relationships = GuardianStudentRelationship.objects.filter(student=student.user).select_related('guardian', 'guardian__guardian_profile')
    
    for relationship in relationships:
        guardian_profile = relationship.guardian.guardian_profile
        if guardian_profile.relation_to_student.lower() == 'father':
            father_info = {
                'name': relationship.guardian.get_full_name(),
                'email': relationship.guardian.email,
                'phone': relationship.guardian.phone_number,
            }
        elif guardian_profile.relation_to_student.lower() == 'mother':
            mother_info = {
                'name': relationship.guardian.get_full_name(),
                'email': relationship.guardian.email,
                'phone': relationship.guardian.phone_number,
            }
    
    context = {
        'student': student,
        'father_name': father_info.get('name'),
        'father_email': father_info.get('email'),
        'father_phone': father_info.get('phone'),
        'mother_name': mother_info.get('name'),
        'mother_email': mother_info.get('email'),
        'mother_phone': mother_info.get('phone'),
    }
    
    return render(request, 'admin/students/edit_student.html', context)


@login_required
@admin_required
def delete_student(request, student_id):
    """
    Delete a student.
    
    Process:
    1. Show confirmation page (GET)
    2. Delete student profile and user account (POST)
    
    The student profile is deleted first, then the user account.
    """
    student = get_object_or_404(StudentProfile, id=student_id)
    
    if request.method == 'POST':
        try:
            user_email = student.user.email
            user = student.user
            
            # Delete student profile first
            student.delete()
            
            # Delete user account
            user.delete()
            
            messages.success(request, f'Student {user_email} has been deleted successfully.')
            
            # Redirect to student list
            return redirect('student_list')
                
        except Exception as e:
            messages.error(request, f'Error deleting student: {str(e)}')
            return redirect('view_student', student_id=student_id)
    
    context = {
        'student': student,
    }
    
    return render(request, 'admin/students/delete_student.html', context)


@login_required
@admin_required
def add_student_to_course(request, batch_id, course_id):
    """
    Add a new student to a course in a batch.
    
    This is a specialized view for adding students directly to a specific
    batch and course combination. It handles:
    - Student ID generation based on batch year and course short name
    - User and profile creation
    - Course enrollment
    - Guardian creation (father/mother)
    - Email notifications
    
    Student ID format: {batch_year}{course_short_name}{sequential_number:04d}
    Example: 2023BCA0001
    """
    batch = get_object_or_404(Batch, id=batch_id)
    course = get_object_or_404(Course, id=course_id)
    
    if request.method == 'POST':
        try:
            # Generate student ID
            last_student = StudentProfile.objects.filter(
                batch=batch,
                enrolled_courses=course
            ).order_by('-student_id').first()
            
            if last_student and last_student.student_id:
                # Extract number from student ID and increment
                import re
                match = re.search(r'(\d{4})$', last_student.student_id)
                if match:
                    number = int(match.group(1)) + 1
                else:
                    number = 1
            else:
                number = 1
            
            student_id = f"{batch.year}{course.short_name}{number:04d}"
            
            # Create user
            student_password = 'Student@123'  # Default password
            user = User.objects.create_user(
                email=request.POST.get('email'),
                password=student_password,
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                phone_number=request.POST.get('phone_number', ''),
                role='student'
            )
            
            # Send credentials email to student
            send_credentials_email(user, student_password)
            
            # Create student profile
            student_profile = StudentProfile.objects.create(
                user=user,
                student_id=student_id,
                batch=batch,
                middle_name=request.POST.get('middle_name', ''),
                address=request.POST.get('address', ''),
                date_of_birth=request.POST.get('date_of_birth') or None,
                gender=request.POST.get('gender', ''),
                nationality=request.POST.get('nationality', 'Nepali'),
                emergency_contact=request.POST.get('emergency_contact', '')
            )
            
            # Handle photo upload
            if 'photo' in request.FILES:
                student_profile.photo = request.FILES['photo']
                student_profile.save()
            
            # Enroll in course
            student_profile.enrolled_courses.add(course)
            
            # Handle guardian information (father and mother separately)
            guardian_password = 'Guardian@123'  # Default password for guardians
            
            # Handle father information
            father_email = request.POST.get('father_email', '').strip()
            if father_email:
                father_name = request.POST.get('father_name', '').strip()
                father_phone = request.POST.get('father_phone', '').strip()
                
                if father_name:
                    name_parts = father_name.split()
                    father_first_name = name_parts[0] if name_parts else ''
                    father_last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                    
                    father_user = User.objects.filter(email=father_email).first()
                    created = False
                    if not father_user:
                        father_user = User.objects.create_user(
                            email=father_email,
                            password=guardian_password,
                            first_name=father_first_name,
                            last_name=father_last_name,
                            phone_number=father_phone,
                            role='guardian'
                        )
                        created = True
                        # Send credentials email to father guardian
                        send_credentials_email(father_user, guardian_password)
                    
                    # If the user existed but does not have guardian role, abort with a clear message
                    if not created and father_user.role != 'guardian':
                        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                        if is_ajax:
                            from django.http import JsonResponse
                            return JsonResponse({
                                'success': False,
                                'errors': {
                                    'father_email': [f"Email {father_email} belongs to an existing '{father_user.role}' account. Use a different email."]
                                }
                            }, status=400)
                        else:
                            messages.error(request, (
                                f"Email {father_email} belongs to an existing '{father_user.role}' account. "
                                "Use a different email or convert that account to a guardian before linking."
                            ))
                            return redirect('add_student_to_course', batch_id=batch_id, course_id=course_id)

                    # Create GuardianProfile if it doesn't exist
                    GuardianProfile.objects.get_or_create(
                        user=father_user,
                        defaults={
                            'guardian_id': f"G{father_user.id:04d}",
                            'relation_to_student': 'Father'
                        }
                    )
                    
                    # Create relationship
                    GuardianStudentRelationship.objects.get_or_create(
                        guardian=father_user,
                        student=user,
                        defaults={'is_primary': True}
                    )
            
            # Handle mother information
            mother_email = request.POST.get('mother_email', '').strip()
            if mother_email:
                mother_name = request.POST.get('mother_name', '').strip()
                mother_phone = request.POST.get('mother_phone', '').strip()
                
                if mother_name:
                    name_parts = mother_name.split()
                    mother_first_name = name_parts[0] if name_parts else ''
                    mother_last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                    
                    mother_user = User.objects.filter(email=mother_email).first()
                    created = False
                    if not mother_user:
                        mother_user = User.objects.create_user(
                            email=mother_email,
                            password=guardian_password,
                            first_name=mother_first_name,
                            last_name=mother_last_name,
                            phone_number=mother_phone,
                            role='guardian'
                        )
                        created = True
                        # Send credentials email to mother guardian
                        send_credentials_email(mother_user, guardian_password)
                    
                    # If the user existed but does not have guardian role, abort with a clear message
                    if not created and mother_user.role != 'guardian':
                        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                        if is_ajax:
                            from django.http import JsonResponse
                            return JsonResponse({
                                'success': False,
                                'errors': {
                                    'mother_email': [f"Email {mother_email} belongs to an existing '{mother_user.role}' account. Use a different email."]
                                }
                            }, status=400)
                        else:
                            messages.error(request, (
                                f"Email {mother_email} belongs to an existing '{mother_user.role}' account. "
                                "Use a different email or convert that account to a guardian before linking."
                            ))
                            return redirect('add_student_to_course', batch_id=batch_id, course_id=course_id)

                    # Create GuardianProfile if it doesn't exist
                    GuardianProfile.objects.get_or_create(
                        user=mother_user,
                        defaults={
                            'guardian_id': f"G{mother_user.id:04d}",
                            'relation_to_student': 'Mother'
                        }
                    )
                    
                    # Create relationship
                    GuardianStudentRelationship.objects.get_or_create(
                        guardian=mother_user,
                        student=user,
                        defaults={'is_primary': False}
                    )
            
            # Check if it's an AJAX request
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            if is_ajax:
                from django.http import JsonResponse
                return JsonResponse({
                    'success': True,
                    'message': f'Student {user.get_full_name()} added successfully! Credentials sent via email.'
                })
            else:
                messages.success(request, f'Student {user.get_full_name()} added successfully! Credentials sent via email.')
                return redirect('student_list')
            
        except Exception as e:
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            if is_ajax:
                from django.http import JsonResponse
                return JsonResponse({
                    'success': False,
                    'errors': {
                        'general': [f'Error adding student: {str(e)}']
                    }
                }, status=400)
            else:
                messages.error(request, f'Error adding student: {str(e)}')
    
    context = {
        'batch': batch,
        'course': course,
    }
    
    return render(request, 'admin/students/add_student.html', context)


# ============================================================================
# GUARDIAN DASHBOARD AND MANAGEMENT VIEWS
# ============================================================================

@login_required
def guardian_dashboard(request):
    """
    Guardian dashboard showing information about their wards.
    
    Displays:
    - Guardian profile
    - Number of wards
    - List of wards with details
    - Statistics (total courses across wards, total attendance records)
    - Latest relevant notices
    """
    if not request.user.is_guardian:
        return redirect('login')
    
    guardian_profile = None
    if hasattr(request.user, 'guardian_profile'):
        guardian_profile = request.user.guardian_profile
    
    # Guardian stats
    wards_count = GuardianStudentRelationship.objects.filter(guardian=request.user).count()
    
    # Get all wards for this guardian
    ward_users = GuardianStudentRelationship.objects.filter(
        guardian=request.user
    ).values_list('student', flat=True)
    wards = StudentProfile.objects.filter(user__in=ward_users).distinct().order_by('user__first_name')

    # additional aggregated stats for the cards
    from attendance.models import AttendanceRecord
    # count unique courses across all wards
    courses_count = StudentCourseEnrollment.objects.filter(student__in=wards).values('course').distinct().count() if wards.exists() else 0
    # total attendance records for all wards
    attendance_count = AttendanceRecord.objects.filter(student__in=wards).count() if wards.exists() else 0
    # first ward (for showing an ID if single-ward case)
    first_ward = wards.first() if wards.exists() else None

    context = {
        'guardian_profile': guardian_profile,
        'wards_count': wards_count,
        'wards': wards,
        'courses_count': courses_count,
        'total_attendance': attendance_count,
        'first_ward': first_ward,
    }
    # Latest notice relevant to the guardian
    from noticeboard.models import Notice
    from django.utils import timezone as dj_tz
    now = dj_tz.now()
    notices_qs = Notice.objects.filter(is_active=True).filter(
        Q(expires_at__gt=now) | Q(expires_at__isnull=True)
    )
    # guardians or all
    notices_qs = notices_qs.filter(Q(audience_type='all') | Q(audience_type='guardians')).order_by('-created_at')
    context['latest_notice'] = notices_qs.first()
    if not context['latest_notice']:
        fallback = Notice.objects.filter(is_active=True).filter(
            Q(expires_at__gt=now) | Q(expires_at__isnull=True)
        ).order_by('-created_at').first()
        context['latest_notice'] = fallback
    return render(request, 'dashboard/guardian_dashboard.html', context)


@login_required
@admin_required
def create_guardian(request):
    """
    Create a new guardian account.
    
    Process:
    1. Display guardian creation form (GET)
    2. Process form submission (POST)
    3. Create guardian user and profile
    4. Send credentials email
    """
    if request.method == 'POST':
        form = GuardianCreationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                user, password = form.save(created_by=request.user)
                email_sent = send_credentials_email(user, password)
                email_status = 'Credentials have been sent via email.' if email_sent else '(Email could not be sent - check console)'
                messages.success(request, f'Guardian account created successfully! {email_status}')
                return redirect('student_list')
            except Exception as e:
                messages.error(request, f'Error creating guardian account: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = GuardianCreationForm()
    
    context = {
        'form': form,
    }
    return render(request, 'admin/guardians/create_guardian.html', context)


@login_required
@admin_required
def edit_guardian(request, user_id):
    """
    Edit guardian account.
    
    Allows updating:
    - User information (name, email, phone)
    - Profile information (guardian ID, relation to student, occupation, address)
    - Photo upload
    """
    user = get_object_or_404(User, id=user_id, role='guardian')
    guardian_profile = get_object_or_404(GuardianProfile, user=user)
    
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.email = request.POST.get('email')
        user.phone_number = request.POST.get('phone_number')
        user.save()
        
        guardian_profile.middle_name = request.POST.get('middle_name', '')
        guardian_profile.guardian_id = request.POST.get('guardian_id')
        guardian_profile.relation_to_student = request.POST.get('relation_to_student', '')
        guardian_profile.occupation = request.POST.get('occupation', '')
        guardian_profile.address = request.POST.get('address', '')
        
        if 'photo' in request.FILES:
            guardian_profile.photo = request.FILES['photo']
        
        guardian_profile.save()
        
        messages.success(request, 'Guardian account updated successfully!')
        return redirect('student_list')
    
    context = {
        'user': user,
        'profile': guardian_profile,
    }
    return render(request, 'admin/guardians/edit_guardian.html', context)


# ============================================================================
# COMMON USER OPERATIONS
# ============================================================================

@login_required
@admin_required
def delete_user(request, user_id):
    """
    Delete a user account.
    
    Prevents self-deletion.
    Redirects based on user role (teacher or student).
    """
    user = get_object_or_404(User, id=user_id)
    
    # Prevent deleting yourself
    if user == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('teacher_list' if user.role == 'teacher' else 'student_list')
    
    # Determine redirect based on user role
    redirect_to = 'teacher_list' if user.role == 'teacher' else 'student_list'
    
    if request.method == 'POST':
        email = user.email
        user.delete()
        messages.success(request, f'User {email} has been deleted successfully.')
        return redirect(redirect_to)
    
    # If GET request, show confirmation
    context = {
        'user': user,
    }
    return render(request, 'admin/delete_user.html', context)


@login_required
@admin_required
def toggle_user_status(request, user_id):
    """
    Activate or deactivate a user account.
    
    Toggles the is_active flag.
    Prevents self-deactivation.
    Redirects based on user role (teacher or student).
    """
    user = get_object_or_404(User, id=user_id)
    
    # Check if it's a teacher for teacher-specific redirect
    is_teacher = user.role == 'teacher'
    
    if user == request.user:
        messages.error(request, 'You cannot change your own status.')
    else:
        user.is_active = not user.is_active
        user.save()
        
        new_status = 'activated' if user.is_active else 'deactivated'
        messages.success(request, f'User {user.email} has been {new_status}.')
    
    # Redirect to teacher_list if it's a teacher, otherwise student_list
    if is_teacher:
        return redirect('teacher_list')
    else:
        return redirect('student_list')


@login_required
@admin_required
def reset_user_password(request, user_id):
    """
    Reset user password and send email.
    
    Generates a random secure password, sets it for the user,
    and sends it via email.
    If email fails, displays the password in a warning message.
    """
    user = get_object_or_404(User, id=user_id)
    
    # Check if it's a teacher for teacher-specific redirect
    is_teacher = user.role == 'teacher'
    
    new_password = secrets.token_urlsafe(12)
    user.set_password(new_password)
    user.save()
    
    # Send email with new password
    subject = 'Password Reset - School Management System'
    message = f'''
    Hello {user.first_name},
    
    Your password has been reset by the administrator.
    
    New Login Details:
    Email: {user.email}
    Password: {new_password}
    
    Please login and change your password immediately for security.
    
    Best regards,
    School Administration
    '''
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        messages.success(request, f'Password reset for {user.email}. New password has been sent via email.')
    except Exception as e:
        messages.warning(request, f'Password reset for {user.email} but email could not be sent. New password: {new_password}')
    
    # Redirect to teacher_list if it's a teacher, otherwise student_list
    if is_teacher:
        return redirect('teacher_list')
    else:
        return redirect('student_list')


# ============================================================================
# PROFILE AND PASSWORD MANAGEMENT
# ============================================================================

@login_required
def profile_view(request):
    """
    Display user's own profile.
    
    Shows role-specific profile information:
    - Teachers: teacher profile with professional details
    - Students: student profile with guardian information
    - Guardians: guardian profile with relation info
    """
    user = request.user
    profile = None
    father_guardian = None
    mother_guardian = None
    
    if user.is_teacher and hasattr(user, 'teacher_profile'):
        profile = user.teacher_profile
        template = 'dashboard/profile_teacher.html'
    elif user.is_student and hasattr(user, 'student_profile'):
        profile = user.student_profile
        template = 'dashboard/profile_student.html'
        
        # Fetch father and mother guardians for the student
        try:
            father_rel = GuardianStudentRelationship.objects.filter(
                student=user,
                guardian__guardian_profile__relation_to_student__iexact='father'
            ).select_related('guardian', 'guardian__guardian_profile').first()
            if father_rel:
                father_guardian = father_rel.guardian
            
            mother_rel = GuardianStudentRelationship.objects.filter(
                student=user,
                guardian__guardian_profile__relation_to_student__iexact='mother'
            ).select_related('guardian', 'guardian__guardian_profile').first()
            if mother_rel:
                mother_guardian = mother_rel.guardian
        except Exception:
            pass
    elif user.is_guardian and hasattr(user, 'guardian_profile'):
        profile = user.guardian_profile
        template = 'dashboard/profile_guardian.html'
    else:
        template = 'dashboard/profile.html'
    
    context = {
        'user': user,
        'profile': profile,
        'father_guardian': father_guardian,
        'mother_guardian': mother_guardian,
    }
    
    return render(request, template, context)


@login_required
def change_password(request):
    """
    Allow users to change their password.
    
    Uses Django's built-in PasswordChangeForm.
    Updates session auth hash to prevent logout after password change.
    """
    if request.method == 'POST':
        form = DjangoPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Your password was successfully updated!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = DjangoPasswordChangeForm(request.user)
    
    return render(request, 'auth/change_password.html', {'form': form})


@login_required
def edit_profile(request):
    """
    Allow any logged-in user to edit their own profile (teacher/student/guardian).
    
    Handles role-specific profile fields:
    - Teachers: department, designation, subjects, qualification
    - Students: student ID, grade, section, emergency contact
    - Guardians: guardian ID, relation, occupation, address
    """
    user = request.user
    profile = None
    role = None

    if user.is_teacher and hasattr(user, 'teacher_profile'):
        profile = user.teacher_profile
        role = 'teacher'
    elif user.is_student and hasattr(user, 'student_profile'):
        profile = user.student_profile
        role = 'student'
    elif user.is_guardian and hasattr(user, 'guardian_profile'):
        profile = user.guardian_profile
        role = 'guardian'

    if request.method == 'POST':
        # Common user fields
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.phone_number = request.POST.get('phone_number', user.phone_number)
        user.save()

        # Role-specific profile updates
        if role == 'teacher' and profile is not None:
            profile.middle_name = request.POST.get('middle_name', profile.middle_name or '')
            profile.teacher_id = request.POST.get('teacher_id', profile.teacher_id)
            profile.department = request.POST.get('department', profile.department or '')
            profile.designation = request.POST.get('designation', profile.designation or '')
            profile.subjects = request.POST.get('subjects', profile.subjects or '')
            # Only set qualification if the field exists on the model
            if hasattr(profile, 'qualification'):
                profile.qualification = request.POST.get('qualification', getattr(profile, 'qualification', '') or '')
            profile.date_of_birth = request.POST.get('date_of_birth') or None
            if 'photo' in request.FILES:
                profile.photo = request.FILES['photo']
            profile.save()

        if role == 'student' and profile is not None:
            profile.middle_name = request.POST.get('middle_name', profile.middle_name or '')
            profile.student_id = request.POST.get('student_id', profile.student_id)
            profile.date_of_birth = request.POST.get('date_of_birth') or None
            profile.grade = request.POST.get('grade', profile.grade or '')
            profile.section = request.POST.get('section', profile.section or '')
            profile.emergency_contact = request.POST.get('emergency_contact', profile.emergency_contact or '')
            if 'photo' in request.FILES:
                profile.photo = request.FILES['photo']
            profile.save()

        if role == 'guardian' and profile is not None:
            profile.middle_name = request.POST.get('middle_name', profile.middle_name or '')
            profile.guardian_id = request.POST.get('guardian_id', profile.guardian_id)
            profile.relation_to_student = request.POST.get('relation_to_student', profile.relation_to_student or '')
            profile.occupation = request.POST.get('occupation', profile.occupation or '')
            profile.address = request.POST.get('address', profile.address or '')
            if 'photo' in request.FILES:
                profile.photo = request.FILES['photo']
            profile.save()

        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')

    context = {
        'user': user,
        'profile': profile,
        'role': role,
    }
    return render(request, 'dashboard/edit_profile.html', context)


# ============================================================================
# BULK OPERATIONS
# ============================================================================

@login_required
@admin_required
def bulk_user_actions(request):
    """
    Handle bulk actions for users.
    
    Actions:
    - activate: Set multiple users as active
    - deactivate: Set multiple users as inactive
    - delete: Delete multiple users
    
    Users can be selected via checkboxes in the user list.
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        user_ids = request.POST.getlist('user_ids')
        
        if not user_ids:
            messages.error(request, 'No users selected.')
            return redirect('student_list')
        
        users = User.objects.filter(id__in=user_ids).exclude(id=request.user.id)
        
        # Determine redirect destination based on user role
        redirect_to = 'student_list'
        if users.exists() and users.first().role == 'teacher':
            redirect_to = 'teacher_list'
        
        if action == 'activate':
            count = users.update(is_active=True)
            messages.success(request, f'{count} user(s) activated.')
        elif action == 'deactivate':
            count = users.update(is_active=False)
            messages.success(request, f'{count} user(s) deactivated.')
        elif action == 'delete':
            count = users.count()
            users.delete()
            messages.success(request, f'{count} user(s) deleted.')
        else:
            messages.error(request, 'Invalid action.')
    
    return redirect(redirect_to)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def send_credentials_email(user, password):
    """
    Send welcome email with credentials to new user.
    
    Args:
        user: User object
        password: Plain text password to include in email
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    subject = 'Your School Management System Account'
    
    if user.is_teacher and hasattr(user, 'teacher_profile'):
        full_name = user.teacher_profile.full_name
    else:
        full_name = f"{user.first_name} {user.last_name}"
    
    message = f'''
    Dear {full_name},
    
    Your account has been successfully created in the School Management System.
    
    Account Details:
    - Email: {user.email}
    - Default Password: {password}
    - Role: {user.get_role_display()}
    
    Please login at: {settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'http://localhost:8000/login/'}
    
    Important: 
    1. This is your default password. 
    2. Please change your password immediately after first login for security.
    
    Best regards,
    School Administration Team
    '''
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


# ============================================================================
# BATCH MANAGEMENT VIEWS
# ============================================================================

from .models import Batch, BatchCourse
from courses.models import Course

@login_required
@admin_required
def batch_list(request):
    """
    Display list of all batches with filtering.
    
    Filter options:
    - Search by name or description
    - Filter by status (active/inactive)
    - Filter by year
    
    Also displays statistics:
    - Active/Inactive/Total batch counts
    """
    batches = Batch.objects.all().order_by('-year', '-date_created')
    
    # Get filter parameters
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    year_filter = request.GET.get('year', '')
    
    # Apply filters
    if search:
        batches = batches.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search)
        )
    
    if status_filter == 'active':
        batches = batches.filter(is_active=True)
    elif status_filter == 'inactive':
        batches = batches.filter(is_active=False)
    
    if year_filter:
        batches = batches.filter(year=year_filter)
    
    # Get unique years for filter dropdown
    years = Batch.objects.values_list('year', flat=True).distinct().order_by('-year')
    
    # Counts for stats
    active_count = Batch.objects.filter(is_active=True).count()
    inactive_count = Batch.objects.filter(is_active=False).count()
    total_count = Batch.objects.count()
    
    context = {
        'batches': batches,
        'search_query': search,
        'status_filter': status_filter,
        'year_filter': year_filter,
        'years': years,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'total_count': total_count,
    }
    
    return render(request, 'admin/batches/batch_list.html', context)


@login_required
@admin_required
def add_batch(request):
    """
    Add a new batch with auto-import of courses.
    
    Process:
    1. Create batch with provided details
    2. Auto-import all active courses into the batch
    3. Redirect to batch detail view
    
    Auto-import creates BatchCourse records for all active courses.
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        year = request.POST.get('year')
        start_date = request.POST.get('start_date') or None
        end_date = request.POST.get('end_date') or None
        
        if not name or not year:
            messages.error(request, 'Batch name and year are required.')
            return redirect('add_batch')
        
        try:
            batch = Batch.objects.create(
                name=name,
                description=description,
                year=int(year),
                start_date=start_date,
                end_date=end_date,
                created_by=request.user
            )
            
            # Auto-import all active courses
            imported_count = batch.import_all_courses(added_by_user=request.user)
            
            messages.success(request, 
                f'Batch "{batch.name}" created successfully! '
                f'Auto-imported {imported_count} active courses.'
            )
            return redirect('view_batch', batch_id=batch.id)
        except Exception as e:
            messages.error(request, f'Error creating batch: {str(e)}')
    
    # Get next suggested batch year
    import datetime
    current_year = datetime.datetime.now().year
    suggested_year = current_year + 1
    
    context = {
        'suggested_year': suggested_year,
    }
    return render(request, 'admin/batches/add_batch.html', context)


@login_required
@admin_required
def view_batch(request, batch_id):
    """
    View batch details with auto-imported courses.
    
    Shows:
    - Batch information
    - Associated courses with active status
    - Students in the batch
    - Statistics (students, courses)
    - Sync status with global courses
    
    Supports course synchronization via ?sync_courses=true parameter.
    """
    batch = get_object_or_404(Batch, id=batch_id)
    
    # Auto-sync courses if requested
    if request.GET.get('sync_courses') == 'true':
        added, deactivated = batch.update_courses_from_all_active(added_by_user=request.user)
        if added > 0 or deactivated > 0:
            messages.success(request, 
                f'Synced courses: Added {added} new courses, Deactivated {deactivated} courses.'
            )
        else:
            messages.info(request, 'All courses are already up to date.')
        return redirect('view_batch', batch_id=batch_id)
    
    # Get batch courses with course details
    batch_courses = batch.batch_courses.select_related('course').all()
    
    # Get students in this batch
    students = batch.students.select_related('user').all()
    
    # Get stats about course synchronization
    from courses.models import Course
    total_active_courses = Course.objects.filter(is_active=True).count()
    courses_in_batch = batch_courses.filter(is_active=True).count()
    needs_sync = total_active_courses != courses_in_batch
    
    context = {
        'batch': batch,
        'batch_courses': batch_courses,
        'students': students,
        'total_students': batch.total_students,
        'total_courses': batch.total_courses,
        'total_active_courses': total_active_courses,
        'courses_in_batch': courses_in_batch,
        'needs_sync': needs_sync,
    }
    
    return render(request, 'admin/batches/view_batch.html', context)


@login_required
@admin_required
def toggle_batch_course(request, batch_id, batch_course_id):
    """
    Toggle active status of a course in batch.
    
    This allows enabling/disabling a course for a specific batch
    without removing it completely.
    """
    batch = get_object_or_404(Batch, id=batch_id)
    batch_course = get_object_or_404(BatchCourse, id=batch_course_id, batch=batch)
    
    if request.method == 'POST':
        batch_course.is_active = not batch_course.is_active
        batch_course.save()
        
        status = "activated" if batch_course.is_active else "deactivated"
        messages.success(request, f'Course "{batch_course.course.name}" has been {status} in batch.')
    
    return redirect('view_batch', batch_id=batch.id)


@login_required
@admin_required
def edit_batch(request, batch_id):
    """
    Edit an existing batch.
    
    Allows updating:
    - Name, description, year
    - Start and end dates
    - Active status
    """
    batch = get_object_or_404(Batch, id=batch_id)
    
    if request.method == 'POST':
        batch.name = request.POST.get('name')
        batch.description = request.POST.get('description', '')
        batch.year = request.POST.get('year')
        batch.start_date = request.POST.get('start_date') or None
        batch.end_date = request.POST.get('end_date') or None
        batch.is_active = 'is_active' in request.POST
        
        try:
            batch.save()
            messages.success(request, f'Batch "{batch.name}" updated successfully!')
            return redirect('batch_list')
        except Exception as e:
            messages.error(request, f'Error updating batch: {str(e)}')
    
    context = {
        'batch': batch,
    }
    return render(request, 'admin/batches/edit_batch.html', context)


@login_required
@admin_required
def delete_batch(request, batch_id):
    """
    Delete a batch.
    
    Process:
    1. Show confirmation page (GET)
    2. Delete batch (POST)
    """
    batch = get_object_or_404(Batch, id=batch_id)
    
    if request.method == 'POST':
        batch_name = batch.name
        batch.delete()
        messages.success(request, f'Batch "{batch_name}" deleted successfully!')
        return redirect('batch_list')
    
    context = {
        'batch': batch,
    }
    return render(request, 'admin/batches/delete_batch.html', context)


@login_required
@admin_required
def add_course_to_batch(request, batch_id):
    """
    Add a course to batch.
    
    Checks if the course already exists in the batch before adding.
    """
    batch = get_object_or_404(Batch, id=batch_id)
    
    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        
        if not course_id:
            messages.error(request, 'Please select a course.')
            return redirect('view_batch', batch_id=batch_id)
        
        try:
            course = Course.objects.get(id=course_id)
            
            # Check if course already exists in batch
            if BatchCourse.objects.filter(batch=batch, course=course).exists():
                messages.warning(request, f'Course "{course.name}" is already in this batch.')
            else:
                BatchCourse.objects.create(
                    batch=batch,
                    course=course,
                    added_by=request.user
                )
                messages.success(request, f'Course "{course.name}" added to batch successfully!')
        except Course.DoesNotExist:
            messages.error(request, 'Selected course does not exist.')
        except Exception as e:
            messages.error(request, f'Error adding course: {str(e)}')
    
    return redirect('view_batch', batch_id=batch_id)


@login_required
@admin_required
def remove_course_from_batch(request, batch_id, course_id):
    """
    Remove a course from batch.
    
    Deletes the BatchCourse record completely.
    """
    batch = get_object_or_404(Batch, id=batch_id)
    
    if request.method == 'POST':
        try:
            batch_course = BatchCourse.objects.get(batch=batch, id=course_id)
            course_name = batch_course.course.name
            batch_course.delete()
            messages.success(request, f'Course "{course_name}" removed from batch successfully!')
        except BatchCourse.DoesNotExist:
            messages.error(request, 'Course not found in this batch.')
        except Exception as e:
            messages.error(request, f'Error removing course: {str(e)}')
    
    return redirect('view_batch', batch_id=batch_id)


# ============================================================================
# COURSE-STUDENT MANAGEMENT
# ============================================================================

@login_required
@admin_required
def course_student_list(request, batch_id, course_id):
    """
    View students enrolled in a specific course within a batch.
    
    Shows students who are:
    - In the specified batch
    - Enrolled in the specified course
    
    Supports search by name, email, or student ID.
    """
    batch = get_object_or_404(Batch, id=batch_id)
    course = get_object_or_404(Course, id=course_id)
    
    # Get students enrolled in this course and batch
    students = StudentProfile.objects.filter(
        batch=batch,
        enrolled_courses=course
    ).select_related('user')
    
    # Apply search filter if provided
    search = request.GET.get('search', '')
    if search:
        students = students.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(student_id__icontains=search)
        )
    
    context = {
        'batch': batch,
        'course': course,
        'students': students,
    }
    
    return render(request, 'admin/students/student_list.html', context)