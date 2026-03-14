# ============================================================================
# Attendance Views - School Management System
# ============================================================================
# Views for managing attendance sessions, recording student attendance, and
# generating reports. Includes separate admin and teacher interfaces.
#
# Security note: Only authorized users may access/modify attendance records.
# ============================================================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.utils import timezone
from accounts.decorators import admin_required
from .models import AttendanceSession, AttendanceRecord
from .forms import AttendanceSessionForm
from accounts.models import Batch, StudentProfile, BatchCourse
from courses.models import Course, Subject

# --- 1. DASHBOARD & LIST VIEWS ---

@login_required
def attendance_session_list(request):
    """Admin/Staff view of all sessions"""
    if not request.user.is_staff:
        return redirect('attendance:teacher_attendance')

    sessions = AttendanceSession.objects.all().select_related(
        'batch', 'course', 'subject', 'teacher'
    ).order_by('-date', '-created_at')
    
    search = request.GET.get('search', '')
    if search:
        sessions = sessions.filter(
            Q(session_id__icontains=search) | Q(batch__name__icontains=search) |
            Q(subject__name__icontains=search)
        )
    
    paginator = Paginator(sessions, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'sessions': page_obj,
        'batches': Batch.objects.filter(is_active=True),
        'ongoing_count': AttendanceSession.objects.filter(status='ongoing').count(),
        'total_sessions': AttendanceSession.objects.count(),
    }
    return render(request, 'attendance/admin/attendance_session_list.html', context)

@login_required
def teacher_attendance_list(request):
    """Teacher dashboard for their specific sessions"""
    sessions = AttendanceSession.objects.filter(teacher=request.user).select_related(
        'batch', 'course', 'subject'
    ).order_by('-date', '-created_at')
    
    context = {
        'sessions': sessions,
        'total_sessions': sessions.count(),
        'today_sessions': sessions.filter(date=timezone.now().date()).count(),
    }
    return render(request, 'attendance/teacher/attendance_list.html', context)

# --- 2. RECORD VIEW ---

@login_required
def view_attendance_session(request, session_id):
    """View the results of a specific session"""
    session = get_object_or_404(AttendanceSession, id=session_id)
    
    if not request.user.is_staff and session.teacher != request.user:
        return HttpResponseForbidden("Access Denied")

    records = session.attendance_records.select_related('student__user').order_by('student__student_id')

    total_students = records.count()
    present_count = records.filter(status='present').count()
    absent_count = total_students - present_count
    excused_count = records.filter(status='excused').count()
    half_day_count = records.filter(status='half_day').count()

    context = {
        'session': session,
        'records': records,
        'total_students': total_students,
        'present_count': present_count,
        'absent_count': absent_count,
        'excused_count': excused_count,
        'half_day_count': half_day_count,
    }
    template = 'attendance/admin/view_attendance_session.html' if request.user.is_staff else 'attendance/teacher/view_attendance_records.html'
    return render(request, template, context)

# --- 3. CRUD OPERATIONS ---

@login_required
@admin_required
def add_attendance_session(request):
    """Create a new daily attendance session (admin only)."""
    if request.method == 'POST':
        form = AttendanceSessionForm(request.POST, user=request.user)
        if form.is_valid():
            s = form.save(commit=False)
            s.created_by = request.user
            s.save()
            messages.success(request, "Session created successfully.")
            return redirect('attendance:attendance_session_list')
    else:
        form = AttendanceSessionForm(user=request.user)
    return render(request, 'attendance/admin/add_attendance_session.html', {'form': form})

@login_required
@admin_required
def edit_attendance_session(request, session_id):
    session = get_object_or_404(AttendanceSession, id=session_id)
    if request.method == 'POST':
        form = AttendanceSessionForm(request.POST, instance=session, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Session updated.")
            return redirect('attendance:attendance_session_list')
    else:
        form = AttendanceSessionForm(instance=session, user=request.user)
    return render(request, 'attendance/admin/edit_attendance_session.html', {'form': form, 'session': session})

@login_required
@require_POST
@admin_required
def cancel_attendance_session(request, session_id):
    """Admin-only deactivation: mark session as cancelled instead of deleting."""
    session = get_object_or_404(AttendanceSession, id=session_id)
    session.status = 'cancelled'
    session.save()
    messages.warning(request, "Session deactivated.")
    return redirect('attendance:attendance_session_list')

@login_required
@admin_required
def delete_attendance_session(request, session_id):
    session = get_object_or_404(AttendanceSession, id=session_id)
    session.delete()
    messages.success(request, "Session deleted permanently.")
    return redirect('attendance:attendance_session_list')

# --- 4. ATTENDANCE TAKING & ACTIONS ---

@login_required
@require_POST
@admin_required
def activate_attendance_session(request, session_id):
    """Admin-only reactivation: revert a cancelled session back to scheduled."""
    session = get_object_or_404(AttendanceSession, id=session_id)
    session.status = 'scheduled'
    session.save()
    messages.success(request, "Session activated.")
    return redirect('attendance:attendance_session_list')


@login_required
def take_attendance(request, session_id):
    from datetime import datetime
    
    session = get_object_or_404(AttendanceSession, id=session_id)
    
    # FIX: Use user__is_active because is_active is on the User model, not StudentProfile
    # Only include students who are in the session's batch and
    # who are enrolled in the session.course (if course specified).
    student_qs = StudentProfile.objects.filter(
        batch=session.batch,
        user__is_active=True
    )

    if session.course:
        student_qs = student_qs.filter(enrolled_courses=session.course)

    students = student_qs.select_related('user').order_by('student_id')

    # Only the assigned teacher may take attendance for a session.
    if session.teacher != request.user:
        return HttpResponseForbidden("Only the assigned teacher may take attendance for this session.")

    # If admin has deactivated/cancelled the session, disallow taking/updating attendance
    if session.status == 'cancelled':
        return HttpResponseForbidden("This session has been deactivated by the administrator.")

    if request.method == 'POST':
        # Get the attendance date from the form
        attendance_date_str = request.POST.get('date', timezone.now().date())
        if isinstance(attendance_date_str, str):
            try:
                attendance_date = datetime.strptime(attendance_date_str, '%Y-%m-%d').date()
            except ValueError:
                attendance_date = timezone.now().date()
        else:
            attendance_date = attendance_date_str

        # Prevent taking attendance for future dates
        today_date = timezone.now().date()
        if attendance_date > today_date:
            messages.error(request, "Cannot take attendance for a future date.")
            return redirect('attendance:start_attendance_session', session.id)

        # Get present students - form sends status_<student_id> for each select
        for student in students:
            status_field = f'status_{student.id}'
            status = request.POST.get(status_field, 'absent')
            
            # Update or create records for each student with the selected date
            # This allows daily attendance updates for different dates
            record, created = AttendanceRecord.objects.update_or_create(
                session=session,
                student=student,
                date=attendance_date,
                defaults={'status': status, 'recorded_by': request.user}
            )

        # Keep session as ongoing while teacher is allowed to update; admin will mark completed.
        session.status = 'ongoing'
        session.save()

        messages.success(request, f"Attendance for {session.subject.name} on {attendance_date.strftime('%Y-%m-%d')} saved successfully.")
        return redirect('attendance:teacher_attendance')

    # Use the teacher-specific template that exists in templates/attendance/teacher/
    today = timezone.now().date()
    return render(request, 'attendance/teacher/take_attendance.html', {
        'session': session,
        'students': students,
        'today': today,
    })


@login_required
def student_attendance_records(request):
    """Allow a student to view their own attendance across subjects."""
    # Ensure the user has a StudentProfile
    try:
        student = StudentProfile.objects.select_related('user', 'batch').get(user=request.user)
    except StudentProfile.DoesNotExist:
        return HttpResponseForbidden("Access Denied")

    # Subjects the student has records for (or that belong to their batch)
    subjects = Subject.objects.filter(course__batch_courses__batch=student.batch).distinct()

    reports = []
    total_sessions = 0
    total_present = total_absent = 0

    for subj in subjects:
        # Count total recorded attendance entries for this student & subject
        # so the denominator equals the number of recorded class entries.
        subj_total = AttendanceRecord.objects.filter(student=student, session__subject=subj).count()
        
        # Skip subjects with no recorded attendance
        if subj_total == 0:
            continue
        
        present_count = AttendanceRecord.objects.filter(student=student, session__subject=subj, status='present').count()
        absent_count = AttendanceRecord.objects.filter(student=student, session__subject=subj, status='absent').count()
        # 'late' and 'leave' statuses are not used anymore
        attendance_percentage = (present_count / subj_total * 100) if subj_total > 0 else 0

        reports.append({
            'subject': subj,
            'batch': student.batch,
            'total_sessions': subj_total,
            'present_count': present_count,
            'absent_count': absent_count,
            'attendance_percentage': round(attendance_percentage, 2),
        })

        total_sessions += subj_total
        total_present += present_count
        total_absent += absent_count
        # late/leave totals intentionally omitted

    overall_percentage = (total_present / total_sessions * 100) if total_sessions > 0 else 0

    context = {
        'student': student,
        'reports': reports,
        'total_sessions': total_sessions,
        'total_present': total_present,
        'total_absent': total_absent,
        'overall_percentage': round(overall_percentage, 2),
    }

    return render(request, 'attendance/student/attendance_report.html', context)


@login_required
def student_subject_attendance_detail(request, subject_id):
    """View detailed attendance records for a specific subject."""
    try:
        student = StudentProfile.objects.select_related('user', 'batch').get(user=request.user)
    except StudentProfile.DoesNotExist:
        return HttpResponseForbidden("Access Denied")

    # Get the subject
    subject = get_object_or_404(Subject, id=subject_id)

    # Verify student has access to this subject (belongs to their batch)
    if not Subject.objects.filter(id=subject_id, course__batch_courses__batch=student.batch).exists():
        return HttpResponseForbidden("Access Denied")

    # Get attendance records for this student in this subject
    records = AttendanceRecord.objects.filter(
        student=student,
        session__subject=subject
    ).select_related('session', 'session__teacher').order_by('-date')

    # Calculate totals
    total_sessions = records.count()
    present_count = records.filter(status='present').count()
    absent_count = records.filter(status='absent').count()
    excused_count = records.filter(status='excused').count()
    half_day_count = records.filter(status='half_day').count()

    percentage = (present_count / total_sessions * 100) if total_sessions > 0 else 0

    context = {
        'student': student,
        'subject': subject,
        'records': records,
        'total_sessions': total_sessions,
        'present_count': present_count,
        'absent_count': absent_count,
        'excused_count': excused_count,
        'half_day_count': half_day_count,
        'percentage': round(percentage, 2),
    }

    return render(request, 'attendance/student/subject_attendance_detail.html', context)


@login_required
def guardian_students_attendance(request):
    """Guardian view to select and see attendance of their students."""
    from accounts.models import GuardianStudentRelationship
    
    try:
        guardian_user = request.user
    except:
        return HttpResponseForbidden("Access Denied")

    # Get all students linked to this guardian
    relationships = GuardianStudentRelationship.objects.filter(
        guardian=guardian_user
    ).select_related('student', 'student__student_profile__batch')

    students_with_data = []
    for rel in relationships:
        try:
            student = rel.student.student_profile
            # Count total attendance records for this student
            total_records = AttendanceRecord.objects.filter(student=student).count()
            students_with_data.append({
                'student': student,
                'relationship': rel,
                'total_records': total_records
            })
        except Exception as e:
            continue

    context = {
        'students': students_with_data,
    }
    return render(request, 'attendance/guardian/students_list.html', context)


@login_required
def guardian_student_attendance(request, student_id):
    """Guardian view of a specific student's attendance across subjects."""
    from accounts.models import GuardianStudentRelationship
    
    guardian_user = request.user
    
    # Verify guardian has access to this student
    student = get_object_or_404(StudentProfile, id=student_id)
    if not GuardianStudentRelationship.objects.filter(guardian=guardian_user, student=student.user).exists():
        return HttpResponseForbidden("Access Denied")

    # Get subjects for this student's batch
    subjects = Subject.objects.filter(course__batch_courses__batch=student.batch).distinct()

    reports = []
    total_sessions = 0
    total_present = total_absent = 0

    for subj in subjects:
        # Count total recorded attendance entries for this student & subject
        subj_total = AttendanceRecord.objects.filter(student=student, session__subject=subj).count()
        
        # Skip subjects with no recorded attendance
        if subj_total == 0:
            continue
        
        present_count = AttendanceRecord.objects.filter(student=student, session__subject=subj, status='present').count()
        absent_count = AttendanceRecord.objects.filter(student=student, session__subject=subj, status='absent').count()
        attendance_percentage = (present_count / subj_total * 100) if subj_total > 0 else 0

        reports.append({
            'subject': subj,
            'batch': student.batch,
            'total_sessions': subj_total,
            'present_count': present_count,
            'absent_count': absent_count,
            'attendance_percentage': round(attendance_percentage, 2),
        })

        total_sessions += subj_total
        total_present += present_count
        total_absent += absent_count

    overall_percentage = (total_present / total_sessions * 100) if total_sessions > 0 else 0

    context = {
        'student': student,
        'reports': reports,
        'total_sessions': total_sessions,
        'total_present': total_present,
        'total_absent': total_absent,
        'overall_percentage': round(overall_percentage, 2),
    }

    return render(request, 'attendance/guardian/attendance_report.html', context)


@login_required
def guardian_subject_attendance_detail(request, student_id, subject_id):
    """Guardian view of detailed attendance for a specific student-subject."""
    from accounts.models import GuardianStudentRelationship
    
    guardian_user = request.user
    
    # Verify guardian has access to this student
    student = get_object_or_404(StudentProfile, id=student_id)
    if not GuardianStudentRelationship.objects.filter(guardian=guardian_user, student=student.user).exists():
        return HttpResponseForbidden("Access Denied")

    # Get the subject
    subject = get_object_or_404(Subject, id=subject_id)

    # Verify student has access to this subject (belongs to their batch)
    if not Subject.objects.filter(id=subject_id, course__batch_courses__batch=student.batch).exists():
        return HttpResponseForbidden("Access Denied")

    # Get attendance records for this student in this subject
    records = AttendanceRecord.objects.filter(
        student=student,
        session__subject=subject
    ).select_related('session', 'session__teacher').order_by('-date')

    # Calculate totals
    total_sessions = records.count()
    present_count = records.filter(status='present').count()
    absent_count = records.filter(status='absent').count()
    excused_count = records.filter(status='excused').count()
    half_day_count = records.filter(status='half_day').count()

    percentage = (present_count / total_sessions * 100) if total_sessions > 0 else 0

    context = {
        'student': student,
        'subject': subject,
        'records': records,
        'total_sessions': total_sessions,
        'present_count': present_count,
        'absent_count': absent_count,
        'excused_count': excused_count,
        'half_day_count': half_day_count,
        'percentage': round(percentage, 2),
    }

    return render(request, 'attendance/guardian/subject_attendance_detail.html', context)


@login_required
def delete_attendance_session(request, session_id):
    if request.method == 'POST':
        session = get_object_or_404(AttendanceSession, id=session_id)
        subject_name = session.subject.name
        session.delete()
        messages.success(request, f"Session for {subject_name} deleted successfully.")
    return redirect('attendance:attendance_session_list')

@login_required
def subject_attendance_report(request, subject_id):
    # This generates the "Full Subject Report" you requested earlier
    from courses.models import Subject
    from django.db.models import Q
    
    subject = get_object_or_404(Subject, id=subject_id)
    
    # Get all students enrolled in the course containing this subject
    students = StudentProfile.objects.filter(
        enrolled_courses=subject.course,
        user__is_active=True
    ).select_related('user', 'batch').distinct()
    
    total_sessions = AttendanceSession.objects.filter(subject=subject, status='completed').count()
    
    report_data = []
    for student in students:
        present_count = AttendanceRecord.objects.filter(
            student=student, 
            session__subject=subject, 
            status='present'
        ).count()
        
        percent = (present_count / total_sessions * 100) if total_sessions > 0 else 0
        
        report_data.append({
            'student': student,
            'present': present_count,
            'total': total_sessions,
            'percent': round(percent, 2)
        })

    return render(request, 'attendance/admin/subject_report.html', {
        'subject': subject,
        'report_data': report_data,
        'total_sessions': total_sessions
    })

@login_required
@require_POST
def bulk_update_attendance(request, session_id):
    session = get_object_or_404(AttendanceSession, id=session_id)
    for key, value in request.POST.items():
        if key.startswith('student_'):
            std_id = key.replace('student_', '')
            AttendanceRecord.objects.filter(session=session, student_id=std_id).update(
                status=value, recorded_by=request.user, updated_at=timezone.now()
            )
    
    recs = session.attendance_records.all()
    session.status = 'ongoing'
    session.total_students = recs.count()
    session.present_count = recs.filter(status='present').count()
    session.absent_count = recs.exclude(status='present').count()
    session.save()
    
    messages.success(request, "Attendance updated.")
    return redirect('attendance:view_attendance_session', session_id=session.id)

@login_required
@require_POST
def complete_attendance_session(request, session_id):
    session = get_object_or_404(AttendanceSession, id=session_id)
    session.status = 'completed'
    session.save()
    messages.success(request, "Session marked as completed.")
    return redirect('attendance:view_attendance_session', session_id=session.id)

# --- 5. DATEWISE ATTENDANCE REPORTS ---

@login_required
def datewise_attendance_report(request, session_id):
    """Generate attendance report organized by date with matrix view"""
    session = get_object_or_404(AttendanceSession, id=session_id)
    
    # Only teacher, admin, or staff can view this
    if not (request.user.is_staff or session.teacher == request.user):
        return HttpResponseForbidden("Access Denied")
    
    # Get all attendance records for this session
    records = AttendanceRecord.objects.filter(
        session=session
    ).select_related('student__user').order_by('date', 'student__student_id')
    
    # Get all unique dates sorted
    all_dates = sorted(set(r.date for r in records))
    
    # Get all students in the batch
    # If session has a specific course, filter by enrolled_courses
    all_students = StudentProfile.objects.filter(
        batch=session.batch,
        user__is_active=True
    ).select_related('user')
    
    if session.course:
        all_students = all_students.filter(enrolled_courses=session.course)
    
    all_students = all_students.order_by('student_id')
    
    # Build attendance matrix: for each student, track attendance for each date
    attendance_matrix = []
    daily_present_counts = {date: 0 for date in all_dates}
    daily_absent_counts = {date: 0 for date in all_dates}
    
    # Create a lookup dict for quick access: {date: {student_id: record}}
    records_lookup = {}
    for record in records:
        if record.date not in records_lookup:
            records_lookup[record.date] = {}
        records_lookup[record.date][record.student_id] = record
    
    # Build matrix for each student
    for student in all_students:
        attendance_status = []
        present_count = 0
        absent_count = 0
        
        for date in all_dates:
            if date in records_lookup and student.id in records_lookup[date]:
                record = records_lookup[date][student.id]
                status = record.status
                attendance_status.append(status)
                
                if status == 'present':
                    present_count += 1
                    daily_present_counts[date] += 1
                else:
                    absent_count += 1
                    daily_absent_counts[date] += 1
            else:
                attendance_status.append(None)
        
        attendance_matrix.append({
            'student': student,
            'attendance_status': attendance_status,
            'present_count': present_count,
            'absent_count': absent_count
        })
    
    # Convert daily counts to ordered list
    daily_present_list = [daily_present_counts[date] for date in all_dates]
    daily_absent_list = [daily_absent_counts[date] for date in all_dates]
    
    context = {
        'session': session,
        'attendance_matrix': attendance_matrix,
        'dates': all_dates,
        'daily_present_counts': daily_present_list,
        'daily_absent_counts': daily_absent_list,
    }
    
    return render(request, 'attendance/admin/datewise_attendance_report.html', context)

@login_required
def teacher_datewise_report(request):
    """Teacher view to see datewise attendance for all their sessions"""
    if request.user.role != 'teacher':
        return HttpResponseForbidden("Only teachers can access this view.")
    
    sessions = AttendanceSession.objects.filter(
        teacher=request.user
    ).select_related('batch', 'subject').order_by('-date')
    
    # Filter by subject if provided
    subject_id = request.GET.get('subject_id')
    if subject_id:
        sessions = sessions.filter(subject_id=subject_id)
    
    # Get datewise summary across all sessions
    records = AttendanceRecord.objects.filter(
        session__teacher=request.user
    ).select_related('session', 'student__user').order_by('-date')
    
    # Group by date and subject
    from collections import defaultdict
    date_subject_summary = defaultdict(lambda: defaultdict(lambda: {'present': 0, 'absent': 0, 'total': 0}))
    
    for record in records:
        date_key = record.date
        subject_key = record.session.subject.name if record.session.subject else 'N/A'
        
        date_subject_summary[date_key][subject_key]['total'] += 1
        if record.status == 'present':
            date_subject_summary[date_key][subject_key]['present'] += 1
        else:
            date_subject_summary[date_key][subject_key]['absent'] += 1
    
    # Convert to sorted list for template
    report_data = []
    for date_key in sorted(date_subject_summary.keys(), reverse=True):
        subjects = []
        for subject_name, stats in date_subject_summary[date_key].items():
            pct = round((stats['present'] / stats['total'] * 100), 2) if stats['total'] > 0 else 0
            subjects.append({
                'name': subject_name,
                'present': stats['present'],
                'absent': stats['absent'],
                'total': stats['total'],
                'percentage': pct
            })
        report_data.append({
            'date': date_key,
            'subjects': subjects
        })
    
    context = {
        'sessions': sessions,
        'report_data': report_data,
        'subjects': AttendanceSession.objects.filter(teacher=request.user).values_list('subject__id', 'subject__name').distinct()
    }
    
    return render(request, 'attendance/teacher/datewise_report.html', context)

# --- 6. AJAX & REPORTS ---

@login_required
def get_courses_for_batch(request):
    batch_id = request.GET.get('batch_id')
    batch_courses = BatchCourse.objects.filter(batch_id=batch_id, is_active=True)
    courses = [{'id': bc.course.id, 'name': bc.course.name} for bc in batch_courses]
    return JsonResponse({'courses': courses, 'success': True})

@login_required
def get_subjects_for_course(request):
    course_id = request.GET.get('course_id')
    subjects = Subject.objects.filter(course_id=course_id).values('id', 'name', 'code')
    return JsonResponse({'subjects': list(subjects), 'success': True})

@login_required
@require_POST
def update_attendance_record(request, record_id):
    status = request.POST.get('status')
    record = get_object_or_404(AttendanceRecord, id=record_id)
    record.status = status
    record.save()
    return JsonResponse({'success': True})

# --- 6. PLACEHOLDER ---

def placeholder_view(request):
    """Fallback view for missing templates or future modules"""
    return HttpResponse("Module Under Construction")