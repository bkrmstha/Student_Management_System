from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from accounts.decorators import admin_required
from collections import OrderedDict
from accounts.models import StudentProfile
from .models import Course, Subject
from .forms import CourseForm, SubjectForm

# ==================== COURSE VIEWS ====================

@login_required
@admin_required
def course_list(request):
    """Display list of all courses with filtering options."""
    courses = Course.objects.all().order_by('name')
    
    # Get filter parameters
    search = request.GET.get('search', '')
    course_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    
    # Apply filters
    if search:
        courses = courses.filter(
            Q(name__icontains=search) |
            Q(short_name__icontains=search)
        )
    
    if course_type:
        courses = courses.filter(course_type=course_type)
    
    if status == 'active':
        courses = courses.filter(is_active=True)
    elif status == 'inactive':
        courses = courses.filter(is_active=False)
    
    # Counts for stats
    active_count = Course.objects.filter(is_active=True).count()
    inactive_count = Course.objects.filter(is_active=False).count()
    total_count = Course.objects.count()
    
    # Pagination
    paginator = Paginator(courses, 10)  # Show 10 courses per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'courses': page_obj,
        'search_query': search,
        'type_filter': course_type,
        'status_filter': status,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'total_count': total_count,
        'page_obj': page_obj,
    }
    
    return render(request, 'admin/courses/course_list.html', context)


@login_required
@admin_required
def add_course(request):
    """Add a new course."""
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save()
            messages.success(request, f'Course "{course.name}" created successfully!')
            return redirect('courses:course_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CourseForm()
    
    return render(request, 'admin/courses/add_course.html', {'form': form})


# courses/views.py - Update view_course function

@login_required
@admin_required
def view_course(request, course_id):
    """View course details."""
    course = get_object_or_404(Course, id=course_id)
    
    # Get subjects with teacher prefetched
    all_subjects = course.subjects.select_related('teacher').all()
    
    # Initialize dictionaries for organizing subjects
    subjects_by_semester = {}
    subjects_by_year = {}
    
    # Prepare ranges for template
    if course.course_type == 'semester':
        semester_range = range(1, 9)  # Semesters 1-8
        for i in semester_range:
            subjects_by_semester[str(i)] = []
    else:
        year_range = range(1, 5)  # Years 1-4
        for i in year_range:
            subjects_by_year[str(i)] = []
    
    # Organize subjects by period
    for subject in all_subjects:
        if course.course_type == 'semester' and subject.semester:
            subjects_by_semester[str(subject.semester)].append(subject)
        elif course.course_type == 'yearly' and subject.year:
            subjects_by_year[str(subject.year)].append(subject)
    
    # Count total subjects
    total_subjects = all_subjects.count()
    
    context = {
        'course': course,
        'subjects_by_semester': subjects_by_semester,
        'subjects_by_year': subjects_by_year,
        'subjects': all_subjects,
        'total_subjects': total_subjects,
        'semester_range': range(1, 9) if course.course_type == 'semester' else [],
        'year_range': range(1, 5) if course.course_type == 'yearly' else [],
    }
    
    return render(request, 'admin/courses/view_course.html', context)


@login_required
@admin_required
def edit_course(request, course_id):
    """Edit an existing course."""
    course = get_object_or_404(Course, id=course_id)
    
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, f'Course "{course.name}" updated successfully!')
            return redirect('courses:course_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CourseForm(instance=course)
    
    return render(request, 'admin/courses/edit_course.html', {'form': form, 'course': course})


@login_required
@admin_required
def delete_course(request, course_id):
    """Delete a course."""
    course = get_object_or_404(Course, id=course_id)
    
    if request.method == 'POST':
        course_name = course.name
        course.delete()
        messages.success(request, f'Course "{course_name}" deleted successfully!')
        return redirect('courses:course_list')
    
    return render(request, 'admin/courses/delete_course.html', {'course': course})


@login_required
@admin_required
def toggle_course_status(request, course_id):
    """Toggle the active status of a course."""
    course = get_object_or_404(Course, id=course_id)
    
    if request.method == 'POST':
        course.is_active = not course.is_active
        course.save()
        status_text = "activated" if course.is_active else "deactivated"
        messages.success(request, f'Course "{course.name}" has been {status_text}.')
    
    return redirect('courses:course_list')


# ==================== SUBJECT VIEWS ====================

@login_required
@admin_required
def subject_list(request, course_id=None):
    """Display list of subjects. Can be filtered by course."""
    if course_id:
        course = get_object_or_404(Course, id=course_id)
        subjects = Subject.objects.filter(course=course).order_by('code')
        course_filter = course
    else:
        course = None
        subjects = Subject.objects.all().order_by('course', 'code')
        course_filter = None
    
    # Get filter parameters
    search = request.GET.get('search', '')
    
    # Apply filters
    if search:
        subjects = subjects.filter(
            Q(code__icontains=search) |
            Q(name__icontains=search) |
            Q(course__name__icontains=search)
        )
    
    # Get all courses for filter dropdown
    courses = Course.objects.all()
    
    # Counts for stats
    total_count = Subject.objects.count()
    
    context = {
        'subjects': subjects,
        'course': course,
        'course_filter': course_filter,
        'search_query': search,
        'courses': courses,
        'total_count': total_count,
    }
    
    return render(request, 'admin/courses/subject_list.html', context)


# courses/views.py - Update add_subject function
@login_required
@admin_required
def add_subject(request, course_id=None):
    """Add a new subject. Can be associated with a specific course."""
    if course_id:
        course = get_object_or_404(Course, id=course_id)
    else:
        course = None
    
    # Get period from URL parameters
    initial_period = {}
    if request.GET.get('semester'):
        initial_period['semester'] = int(request.GET.get('semester'))
    if request.GET.get('year'):
        initial_period['year'] = int(request.GET.get('year'))
    
    if request.method == 'POST':
        form = SubjectForm(request.POST, course=course, initial_period=initial_period)
        if form.is_valid():
            subject = form.save()
            messages.success(request, f'Subject "{subject.name}" created successfully!')
            
            if course:
                return redirect('courses:view_course', course_id=course.id)
            else:
                return redirect('courses:subject_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SubjectForm(course=course, initial_period=initial_period)
    
    # Get all courses for the dropdown (if not specific course)
    if not course:
        courses = Course.objects.filter(is_active=True).order_by('name')
    else:
        courses = None
    
    context = {
        'form': form, 
        'course': course,
        'courses': courses,
        'initial_period': initial_period
    }
    
    return render(request, 'admin/courses/subjects/add_subject.html', context)


@login_required
@admin_required
def edit_subject(request, subject_id):
    """Edit an existing subject."""
    subject = get_object_or_404(Subject, id=subject_id)
    
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            messages.success(request, f'Subject "{subject.name}" updated successfully!')
            return redirect('courses:view_course', course_id=subject.course.id)
        else:
            # Show detailed form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    
    else:
        form = SubjectForm(instance=subject)
    
    return render(request, 'admin/courses/subjects/edit_subject.html', {
        'form': form, 
        'subject': subject
    })


@login_required
@admin_required
def delete_subject(request, subject_id):
    """Delete a subject."""
    subject = get_object_or_404(Subject, id=subject_id)
    course_id = subject.course.id
    
    if request.method == 'POST':
        subject_name = subject.name
        subject.delete()
        messages.success(request, f'Subject "{subject_name}" deleted successfully!')
        return redirect('courses:view_course', course_id=course_id)
    
    return render(request, 'admin/courses/subjects/delete_subject.html', {
        'subject': subject
    })


# ==================== TEACHER VIEWS ====================

@login_required
def teacher_courses(request):
    """Display courses assigned to the current teacher."""
    if not request.user.is_teacher:
        return redirect('login')
    
    # Get distinct courses where this teacher teaches subjects
    courses = Course.objects.filter(subjects__teacher=request.user).distinct().order_by('name')
    
    # Get filter parameters
    search = request.GET.get('search', '')
    course_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    
    # Apply filters
    if search:
        courses = courses.filter(
            Q(name__icontains=search) |
            Q(short_name__icontains=search)
        )
    
    if course_type:
        courses = courses.filter(course_type=course_type)
    
    if status == 'active':
        courses = courses.filter(is_active=True)
    elif status == 'inactive':
        courses = courses.filter(is_active=False)
    
    # Counts for stats
    active_count = courses.filter(is_active=True).count()
    inactive_count = courses.filter(is_active=False).count()
    total_count = courses.count()
    
    context = {
        'courses': courses,
        'search_query': search,
        'type_filter': course_type,
        'status_filter': status,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'total_count': total_count,
        'is_teacher_view': True,
    }
    
    return render(request, 'courses/teacher_courses.html', context)


@login_required
def teacher_subjects(request):
    """Display subjects assigned to the current teacher."""
    if not request.user.is_teacher:
        return redirect('login')
    
    # Get subjects taught by this teacher
    subjects = Subject.objects.filter(teacher=request.user).order_by('course', 'code')
    
    # Get filter parameters
    search = request.GET.get('search', '')
    course_id = request.GET.get('course', '')
    
    # Apply filters
    if search:
        subjects = subjects.filter(
            Q(code__icontains=search) |
            Q(name__icontains=search)
        )
    
    if course_id:
        subjects = subjects.filter(course_id=course_id)
    
    # Get all courses taught by teacher for filter dropdown
    courses = Course.objects.filter(subjects__teacher=request.user).distinct()
    
    # Counts for stats
    total_count = Subject.objects.filter(teacher=request.user).count()
    
    context = {
        'subjects': subjects,
        'courses': courses,
        'search_query': search,
        'course_filter': course_id,
        'total_count': total_count,
        'is_teacher_view': True,
    }
    
    return render(request, 'courses/teacher_subjects.html', context)


@login_required
def student_courses(request):
    """Display courses enrolled by the current student."""
    if not request.user.is_student:
        return redirect('login')
    
    # Get the student profile
    try:
        student_profile = request.user.student_profile
    except:
        return redirect('login')
    
    # Get enrolled courses for this student
    courses = Course.objects.filter(
        student_enrollments__student=student_profile,
        student_enrollments__is_active=True
    ).distinct().order_by('name')
    
    # Get filter parameters
    search = request.GET.get('search', '')
    course_type = request.GET.get('type', '')
    
    # Apply filters
    if search:
        courses = courses.filter(
            Q(name__icontains=search) |
            Q(short_name__icontains=search)
        )
    
    if course_type:
        courses = courses.filter(course_type=course_type)
    
    # Counts for stats
    total_count = courses.count()
    semester_count = courses.filter(course_type='semester').count()
    yearly_count = courses.filter(course_type='yearly').count()
    
    context = {
        'courses': courses,
        'search_query': search,
        'type_filter': course_type,
        'total_count': total_count,
        'semester_count': semester_count,
        'yearly_count': yearly_count,
        'is_student_view': True,
    }
    
    return render(request, 'courses/student_courses.html', context)


@login_required
def student_subjects(request):
    """Display all subjects the student is enrolled in across all courses."""
    if not request.user.is_student:
        return redirect('login')
    
    # Get the student profile
    try:
        student_profile = request.user.student_profile
    except:
        return redirect('login')
    
    # Get all subjects from courses the student is enrolled in
    subjects = Subject.objects.filter(
        course__student_enrollments__student=student_profile,
        course__student_enrollments__is_active=True
    ).distinct().order_by('course__name', 'code')
    
    # Get filter parameters
    search = request.GET.get('search', '')
    course_id = request.GET.get('course', '')
    
    # Apply filters
    if search:
        subjects = subjects.filter(
            Q(code__icontains=search) |
            Q(name__icontains=search)
        )
    
    if course_id:
        subjects = subjects.filter(course_id=course_id)
    
    # Get all courses for filter dropdown
    courses = Course.objects.filter(
        student_enrollments__student=student_profile,
        student_enrollments__is_active=True
    ).distinct().order_by('name')
    
    # Organize subjects by course and within each course group by semester/year
    subjects_by_course = OrderedDict()
    # Ensure consistent ordering
    subjects = subjects.order_by('course__name', 'code')

    for subject in subjects:
        course = subject.course
        if course not in subjects_by_course:
            subjects_by_course[course] = OrderedDict()

        if subject.semester:
            label = f"Semester {subject.semester}"
        elif subject.year:
            label = f"Year {subject.year}"
        else:
            label = 'Other'

        subjects_by_course[course].setdefault(label, []).append({
            'subject': subject,
            'teacher_name': subject.teacher.get_full_name() if subject.teacher else 'Unassigned'
        })

    context = {
        'subjects_by_course': subjects_by_course,
        'courses': courses,
        'search_query': search,
        'course_filter': course_id,
        'total_count': Subject.objects.filter(
            course__student_enrollments__student=student_profile,
            course__student_enrollments__is_active=True
        ).distinct().count(),
        'is_student_view': True,
    }

    return render(request, 'courses/student_subjects.html', context)



@login_required
def guardian_student_courses(request, student_id):
    """Display courses for a ward that the guardian is responsible for."""
    if not request.user.is_guardian:
        return redirect('login')
    
    # Get the guardian profile
    try:
        guardian_profile = request.user.guardian_profile
    except:
        return redirect('login')
    
    # Get the student
    student = get_object_or_404(StudentProfile, id=student_id)
    
    # Verify guardian is responsible for this student
    is_guardian = student.guardian_relationships.filter(
        guardian=guardian_profile
    ).exists()
    
    if not is_guardian:
        messages.error(request, 'You do not have access to this ward\'s information.')
        return redirect('guardian_dashboard')
    
    # Get enrolled courses for this student
    courses = Course.objects.filter(
        student_enrollments__student=student,
        student_enrollments__is_active=True
    ).distinct().order_by('name')
    
    # Get filter parameters
    search = request.GET.get('search', '')
    course_type = request.GET.get('type', '')
    
    # Apply filters
    if search:
        courses = courses.filter(
            Q(name__icontains=search) |
            Q(short_name__icontains=search)
        )
    
    if course_type:
        courses = courses.filter(course_type=course_type)
    
    # Counts for stats
    total_count = courses.count()
    semester_count = courses.filter(course_type='semester').count()
    yearly_count = courses.filter(course_type='yearly').count()
    
    context = {
        'student': student,
        'courses': courses,
        'search_query': search,
        'type_filter': course_type,
        'total_count': total_count,
        'semester_count': semester_count,
        'yearly_count': yearly_count,
        'is_guardian_view': True,
    }
    
    return render(request, 'courses/guardian_student_courses.html', context)


@login_required
def guardian_course_subjects(request, student_id, course_id):
    """Display subjects for a course that a guardian's ward is enrolled in."""
    if not request.user.is_guardian:
        return redirect('login')
    
    # Get the guardian profile
    try:
        guardian_profile = request.user.guardian_profile
    except:
        return redirect('login')
    
    # Get the student
    student = get_object_or_404(StudentProfile, id=student_id)
    
    # Verify guardian is responsible for this student
    is_guardian = student.guardian_relationships.filter(
        guardian=guardian_profile
    ).exists()
    
    if not is_guardian:
        messages.error(request, 'You do not have access to this ward\'s information.')
        return redirect('guardian_dashboard')
    
    # Get the course
    course = get_object_or_404(Course, id=course_id)
    
    # Verify student is enrolled in this course
    is_enrolled = student.course_enrollments.filter(
        course=course,
        is_active=True
    ).exists()
    
    if not is_enrolled:
        messages.error(request, 'This ward is not enrolled in this course.')
        return redirect('courses:guardian_student_courses', student_id=student.id)
    
    # Get subjects for this course
    subjects = Subject.objects.filter(course=course).order_by('code')
    
    # Get filter parameters
    search = request.GET.get('search', '')
    
    # Apply filters
    if search:
        subjects = subjects.filter(
            Q(code__icontains=search) |
            Q(name__icontains=search)
        )
    
    # Group subjects by semester/year
    subject_list = list(subjects)

    def _sort_key(s):
        if s.semester:
            return (0, s.semester, s.code)
        if s.year:
            return (1, s.year, s.code)
        return (2, 0, s.code)

    subject_list.sort(key=_sort_key)

    grouped = OrderedDict()
    for s in subject_list:
        if s.semester:
            label = f"Semester {s.semester}"
        elif s.year:
            label = f"Year {s.year}"
        else:
            label = 'Other'

        grouped.setdefault(label, []).append({
            'subject': s,
            'teacher_name': s.teacher.get_full_name() if s.teacher else 'Unassigned'
        })

    context = {
        'student': student,
        'course': course,
        'grouped_subjects': grouped,
        'total_count': Subject.objects.filter(course=course).count(),
        'search_query': search,
        'is_guardian_view': True,
    }

    return render(request, 'courses/guardian_course_subjects.html', context)

