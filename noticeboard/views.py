# ============================================================================
# Noticeboard Views - School Management System
# ============================================================================
# Views for listing, creating, and managing notices. Handles audience targeting,
# attachments, comments, and read-tracking.
#
# Security note: write operations are restricted to authorized roles.
# ============================================================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from .models import Notice, NoticeAttachment, NoticeComment, NoticeView, NoticeReadStatus
from .forms import NoticeForm, NoticeAttachmentForm, NoticeCommentForm
from accounts.models import StudentProfile, TeacherProfile, GuardianProfile, Batch
from accounts.decorators import admin_required, teacher_required
from courses.models import Subject
from django.http import JsonResponse


def get_user_batch(user):
    """Get batch for student or teacher."""
    if user.role == 'student':
        try:
            return StudentProfile.objects.get(user=user).batch
        except StudentProfile.DoesNotExist:
            return None
    elif user.role == 'teacher':
        # Teachers don't have a direct `batch` attribute. Derive batches
        # from subjects they teach via Subject -> Course -> Batch relations.
        try:
            teacher_user = user
            teacher_subjects = Subject.objects.filter(teacher=teacher_user)
            if teacher_subjects.exists():
                teacher_courses = teacher_subjects.values_list('course', flat=True)
                teacher_batches = Batch.objects.filter(batch_courses__course__in=teacher_courses).distinct()
                return teacher_batches
            return None
        except TeacherProfile.DoesNotExist:
            return None
    return None


def get_accessible_notices(user):
    """Get notices accessible to the user based on their role."""
    notices = Notice.objects.filter(is_active=True).exclude(
        expires_at__lt=timezone.now()
    )
    
    if user.role == 'admin':
        # Admin can see all notices
        return notices
    
    elif user.role == 'teacher':
        # Teachers can see notices for:
        # - All users
        # - Batches that include courses they teach
        # - Courses they teach
        # - Teachers audience
        # Determine courses taught by this teacher (Subject.teacher is a User FK)
        teacher_user = user
        teacher_subjects = Subject.objects.filter(teacher=teacher_user)
        if teacher_subjects.exists():
            teacher_courses = teacher_subjects.values_list('course', flat=True)
            # Batches that include any of these courses
            teacher_batches = Batch.objects.filter(batch_courses__course__in=teacher_courses).distinct()
            return notices.filter(
                Q(audience_type='all') |
                Q(audience_type='teachers') |
                Q(audience_type='course', courses__in=teacher_courses) |
                Q(audience_type='batch', batches__in=teacher_batches)
            ).distinct()
        # If teacher has no assigned subjects, fall back to general teacher notices
        return notices.filter(Q(audience_type='all') | Q(audience_type='teachers'))
    
    elif user.role == 'student':
        # Students can see notices for:
        # - All users
        # - Their batch
        # - Courses they're enrolled in
        # - Students audience
        student = StudentProfile.objects.filter(user=user).first()
        if student:
            return notices.filter(
                Q(audience_type='all') |
                Q(audience_type='batch', batches=student.batch) |
                Q(audience_type='course', courses__in=student.enrolled_courses.all()) |
                Q(audience_type='students')
            ).distinct()
        return notices.filter(audience_type='all')
    
    elif user.role == 'guardian':
        # Guardians can see student audience notices
        return notices.filter(
            Q(audience_type='all') |
            Q(audience_type='guardians')
        )
    
    return notices.none()


@login_required
def notice_list(request):
    """View list of notices accessible to the user."""
    notices = get_accessible_notices(request.user)
    
    # Get unread notice IDs for current user
    unread_notice_ids = NoticeReadStatus.objects.filter(
        user=request.user,
        is_read=False
    ).values_list('notice_id', flat=True)
    
    unread_count = unread_notice_ids.count()
    
    # Mark notices as unread in context
    for notice in notices:
        notice.is_unread = notice.id in unread_notice_ids
    
    context = {
        'notices': notices,
        'unread_count': unread_count,
        'user_role': request.user.role
    }
    
    return render(request, 'noticeboard/notice_list.html', context)


@login_required
def notice_detail(request, notice_id):
    """View notice details and add comments."""
    notice = get_object_or_404(Notice, id=notice_id)
    
    # Check if user has access to this notice
    accessible_notices = get_accessible_notices(request.user)
    if notice not in accessible_notices:
        messages.error(request, 'You do not have access to this notice.')
        return redirect('noticeboard:notice_list')
    
    # Track view
    NoticeView.objects.get_or_create(notice=notice, user=request.user)
    
    # Mark as read
    read_status, created = NoticeReadStatus.objects.get_or_create(
        notice=notice,
        user=request.user,
        defaults={'is_read': False}
    )
    if not read_status.is_read:
        read_status.is_read = True
        read_status.read_at = timezone.now()
        read_status.save()
    
    # Get comments
    comments = notice.comments.all()
    
    # Comment form
    if request.method == 'POST':
        form = NoticeCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.notice = notice
            comment.user = request.user
            comment.save()
            messages.success(request, 'Comment added successfully!')
            return redirect('noticeboard:notice_detail', notice_id=notice.id)
    else:
        form = NoticeCommentForm()
    
    # Get attachments
    attachments = notice.attachments.all()
    
    context = {
        'notice': notice,
        'comments': comments,
        'form': form,
        'attachments': attachments,
        'user_role': request.user.role
    }
    
    return render(request, 'noticeboard/notice_detail.html', context)


@login_required
@admin_required
def create_notice(request):
    """Create a new notice (Admin only)."""
    if request.method == 'POST':
        form = NoticeForm(request.POST)
        if form.is_valid():
            notice = form.save(commit=False)
            notice.created_by = request.user
            notice.save()
            form.save_m2m()

            # Handle attachments
            attachment_files = request.FILES.getlist('attachments')
            for file in attachment_files:
                NoticeAttachment.objects.create(notice=notice, file=file)

            messages.success(request, 'Notice created successfully!')
            return redirect('noticeboard:notice_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = NoticeForm()

    attachment_form = NoticeAttachmentForm()

    context = {
        'form': form,
        'attachment_form': attachment_form,
        'page_title': 'Create Notice'
    }

    return render(request, 'noticeboard/admin/create_notice.html', context)


@login_required
def teacher_create_notice(request):
    """Create a notice for a specific batch (Teacher only)."""
    # Check if user is a teacher
    teacher = TeacherProfile.objects.filter(user=request.user).first()
    if not teacher:
        messages.error(request, 'You must be a teacher to create notices.')
        return redirect('noticeboard:notice_list')

    if request.method == 'POST':
        # Determine teacher batches to inject into the POST data (template doesn't submit batches)
        teacher_subjects = Subject.objects.filter(teacher=request.user)
        teacher_batches = Batch.objects.none()
        if teacher_subjects.exists():
            teacher_courses = teacher_subjects.values_list('course', flat=True)
            teacher_batches = Batch.objects.filter(batch_courses__course__in=teacher_courses).distinct()

        if not teacher_batches.exists():
            messages.error(request, 'You are not associated with any batch to post a batch notice.')
            return redirect('noticeboard:notice_list')

        post_data = request.POST.copy()
        # Ensure audience_type is set to 'batch' since the template does not include this field
        post_data['audience_type'] = 'batch'
        post_data.setlist('batches', [str(b) for b in teacher_batches.values_list('id', flat=True)])
        form = NoticeForm(post_data)
        if form.is_valid():
            notice = form.save(commit=False)
            notice.created_by = request.user
            notice.audience_type = 'batch'
            notice.save()
            # Save selected batches (many-to-many)
            form.save_m2m()

            # Handle attachments
            attachment_files = request.FILES.getlist('attachments')
            for file in attachment_files:
                NoticeAttachment.objects.create(notice=notice, file=file)

            messages.success(request, 'Notice created successfully!')
            return redirect('noticeboard:notice_list')
        else:
            # If the only non-field error is missing batch selection (template omits batches),
            # create the notice directly and attach the teacher's batches.
            non_field = [str(x) for x in form.non_field_errors()]
            if any('batch' in nf.lower() for nf in non_field):
                # Create notice directly using POST values
                title = request.POST.get('title', '').strip()
                content = request.POST.get('content', '').strip()
                expires_at = request.POST.get('expires_at') or None

                notice = Notice(
                    title=title,
                    content=content,
                    created_by=request.user,
                    audience_type='batch'
                )
                # set expires_at if provided and valid will be handled by model validation on save
                if expires_at:
                    try:
                        from django.utils.dateparse import parse_datetime
                        parsed = parse_datetime(expires_at)
                        notice.expires_at = parsed
                    except Exception:
                        pass

                notice.save()
                # attach teacher batches we computed earlier
                if teacher_batches.exists():
                    notice.batches.add(*list(teacher_batches.values_list('id', flat=True)))

                # Handle attachments
                attachment_files = request.FILES.getlist('attachments')
                for file in attachment_files:
                    NoticeAttachment.objects.create(notice=notice, file=file)

                messages.success(request, 'Notice created successfully!')
                return redirect('noticeboard:notice_list')

            messages.error(request, 'Please correct the errors below.')
    else:
        form = NoticeForm(initial={'audience_type': 'batch'})
        # Limit batches to those related to courses the teacher teaches
        teacher_subjects = Subject.objects.filter(teacher=request.user)
        teacher_batches = Batch.objects.none()
        if teacher_subjects.exists():
            teacher_courses = teacher_subjects.values_list('course', flat=True)
            teacher_batches = Batch.objects.filter(batch_courses__course__in=teacher_courses).distinct()
        form.fields['batches'].queryset = teacher_batches

    attachment_form = NoticeAttachmentForm()

    context = {
        'form': form,
        'attachment_form': attachment_form,
        'page_title': 'Create Notice for Your Batch',
        'is_teacher_notice': True
    }

    return render(request, 'noticeboard/teacher/create_notice.html', context)


@login_required
def edit_notice(request, notice_id):
    """Edit a notice (Admin or creator can edit)."""
    notice = get_object_or_404(Notice, id=notice_id)
    
    # Check authorization: only admin or the creator can edit
    if not (request.user.is_admin or request.user == notice.created_by):
        messages.error(request, 'You do not have permission to edit this notice.')
        return redirect('noticeboard:notice_detail', notice_id=notice.id)
    
    if request.method == 'POST':
        form = NoticeForm(request.POST, request.FILES, instance=notice)
        if form.is_valid():
            notice = form.save()
            
            # Handle new attachments
            attachment_files = request.FILES.getlist('attachments')
            for file in attachment_files:
                NoticeAttachment.objects.create(notice=notice, file=file)
            
            messages.success(request, 'Notice updated successfully!')
            return redirect('noticeboard:notice_detail', notice_id=notice.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = NoticeForm(instance=notice)
    
    attachment_form = NoticeAttachmentForm()
    attachments = notice.attachments.all()
    
    context = {
        'form': form,
        'attachment_form': attachment_form,
        'notice': notice,
        'attachments': attachments,
        'page_title': 'Edit Notice'
    }
    
    return render(request, 'noticeboard/edit_notice.html', context)


@login_required
def delete_notice(request, notice_id):
    """Delete a notice (Admin or creator can delete)."""
    notice = get_object_or_404(Notice, id=notice_id)
    
    # Check authorization: only admin or the creator can delete
    if not (request.user.is_admin or request.user == notice.created_by):
        messages.error(request, 'You do not have permission to delete this notice.')
        return redirect('noticeboard:notice_detail', notice_id=notice.id)
    
    if request.method == 'POST':
        notice_title = notice.title
        notice.delete()
        messages.success(request, f'Notice "{notice_title}" deleted successfully!')
        return redirect('noticeboard:notice_list')
    
    context = {
        'notice': notice,
        'page_title': 'Delete Notice'
    }
    
    return render(request, 'noticeboard/delete_notice.html', context)


@login_required
def delete_attachment(request, attachment_id):
    """Delete an attachment from a notice (Admin or creator can delete)."""
    attachment = get_object_or_404(NoticeAttachment, id=attachment_id)
    notice = attachment.notice
    
    # Check authorization: only admin or the notice creator can delete attachments
    if not (request.user.is_admin or request.user == notice.created_by):
        messages.error(request, 'You do not have permission to delete this attachment.')
        return redirect('noticeboard:notice_detail', notice_id=notice.id)
    
    filename = attachment.file.name
    attachment.delete()
    messages.success(request, f'Attachment "{filename}" deleted successfully!')
    return redirect('noticeboard:edit_notice', notice_id=notice.id)
