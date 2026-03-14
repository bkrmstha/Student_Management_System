from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from .models import Batch, BatchCourse
from .forms import BatchForm, BatchCourseForm
from courses.models import Course


@login_required
def batch_list(request):
    """List all batches"""
    if not request.user.is_admin:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('dashboard_redirect')

    batches = Batch.objects.all().order_by('-year', '-date_created')
    return render(request, 'admin/batches/batch_list.html', {
        'batches': batches,
        'title': 'Batch Management'
    })


@login_required
def add_batch(request):
    """Add a new batch"""
    if not request.user.is_admin:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = BatchForm(request.POST)
        if form.is_valid():
            batch = form.save(commit=False)
            batch.created_by = request.user
            batch.save()
            messages.success(request, f'Batch "{batch.name}" has been created successfully.')
            return redirect('batch_list')
    else:
        form = BatchForm()

    return render(request, 'admin/batches/add_batch.html', {
        'form': form,
        'title': 'Add New Batch'
    })


@login_required
def view_batch(request, batch_id):
    """View batch details"""
    if not request.user.is_admin:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('dashboard_redirect')

    batch = get_object_or_404(Batch, id=batch_id)
    batch_courses = BatchCourse.objects.filter(batch=batch).select_related('course')
    
    # Handle course sync
    if request.GET.get('sync_courses') == 'true':
        imported_count = batch.import_all_courses(added_by_user=request.user)
        if imported_count > 0:
            messages.success(request, f'Successfully imported {imported_count} courses into batch "{batch.name}".')
        else:
            messages.info(request, 'No new courses to import. All active courses are already in this batch.')
        return redirect('view_batch', batch_id=batch.id)
    
    # Get statistics for the template
    total_active_courses = Course.objects.filter(is_active=True).count()
    courses_in_batch = batch_courses.count()
    needs_sync = courses_in_batch < total_active_courses

    return render(request, 'admin/batches/view_batch.html', {
        'batch': batch,
        'batch_courses': batch_courses,
        'total_active_courses': total_active_courses,
        'courses_in_batch': courses_in_batch,
        'needs_sync': needs_sync,
        'title': f'Batch: {batch.name}'
    })


@login_required
def edit_batch(request, batch_id):
    """Edit an existing batch"""
    if not request.user.is_admin:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('dashboard_redirect')

    batch = get_object_or_404(Batch, id=batch_id)

    if request.method == 'POST':
        form = BatchForm(request.POST, instance=batch)
        if form.is_valid():
            form.save()
            messages.success(request, f'Batch "{batch.name}" has been updated successfully.')
            return redirect('view_batch', batch_id=batch.id)
    else:
        form = BatchForm(instance=batch)

    return render(request, 'admin/batches/edit_batch.html', {
        'form': form,
        'batch': batch,
        'title': f'Edit Batch: {batch.name}'
    })


@login_required
def delete_batch(request, batch_id):
    """Delete a batch"""
    if not request.user.is_admin:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('dashboard_redirect')

    batch = get_object_or_404(Batch, id=batch_id)

    if request.method == 'POST':
        batch_name = batch.name
        batch.delete()
        messages.success(request, f'Batch "{batch_name}" has been deleted successfully.')
        return redirect('batch_list')

    return render(request, 'admin/batches/delete_batch.html', {
        'batch': batch,
        'title': f'Delete Batch: {batch.name}'
    })


@login_required
def add_course_to_batch(request, batch_id):
    """Add a course to a batch"""
    if not request.user.is_admin:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('dashboard_redirect')

    batch = get_object_or_404(Batch, id=batch_id)

    if request.method == 'POST':
        course_id = request.POST.get('course')
        if course_id:
            try:
                course = Course.objects.get(id=course_id)
                # Check if course is already in batch
                if not BatchCourse.objects.filter(batch=batch, course=course).exists():
                    BatchCourse.objects.create(
                        batch=batch,
                        course=course,
                        added_by=request.user
                    )
                    messages.success(request, f'Course "{course.name}" has been added to batch "{batch.name}".')
                else:
                    messages.warning(request, f'Course "{course.name}" is already in batch "{batch.name}".')
            except Course.DoesNotExist:
                messages.error(request, 'Selected course does not exist.')

    return redirect('view_batch', batch_id=batch.id)


@login_required
def remove_course_from_batch(request, batch_id, course_id):
    """Remove a course from a batch"""
    if not request.user.is_admin:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('dashboard_redirect')

    batch = get_object_or_404(Batch, id=batch_id)
    course = get_object_or_404(Course, id=course_id)

    batch_course = get_object_or_404(BatchCourse, batch=batch, course=course)
    batch_course.delete()

    messages.success(request, f'Course "{course.name}" has been removed from batch "{batch.name}".')
    return redirect('view_batch', batch_id=batch.id)


@login_required
def toggle_batch_status(request, batch_id):
    """Toggle active status of a batch"""
    if not request.user.is_admin:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('dashboard_redirect')

    if request.method != 'POST':
        return redirect('batch_list')

    batch = get_object_or_404(Batch, id=batch_id)
    
    # Toggle the active status
    batch.is_active = not batch.is_active
    batch.save()
    
    status_text = "activated" if batch.is_active else "deactivated"
    messages.success(request, f'Batch "{batch.name}" has been {status_text}.')
    
    return redirect('batch_list')


@login_required
def toggle_batch_course(request, batch_id, batch_course_id):
    """Toggle active status of a course in a batch"""
    if not request.user.is_admin:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('dashboard_redirect')

    if request.method != 'POST':
        return redirect('view_batch', batch_id=batch_id)

    batch = get_object_or_404(Batch, id=batch_id)
    batch_course = get_object_or_404(BatchCourse, id=batch_course_id, batch=batch)
    
    # Toggle the active status
    batch_course.is_active = not batch_course.is_active
    batch_course.save()
    
    status_text = "activated" if batch_course.is_active else "deactivated"
    messages.success(request, f'Course "{batch_course.course.name}" has been {status_text} in batch "{batch.name}".')
    
    return redirect('view_batch', batch_id=batch.id)