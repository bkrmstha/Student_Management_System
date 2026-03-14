from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    # Admin & General session URLs
    path('sessions/', views.attendance_session_list, name='attendance_session_list'),
    path('sessions/add/', views.add_attendance_session, name='add_attendance_session'),
    path('sessions/<int:session_id>/', views.view_attendance_session, name='view_attendance_session'),
    path('sessions/<int:session_id>/edit/', views.edit_attendance_session, name='edit_attendance_session'),
    path('sessions/<int:session_id>/delete/', views.delete_attendance_session, name='delete_attendance_session'),
    
    # Logic URLs
    # We point both 'start' and 'take' to the same view since they do the same work
    path('sessions/<int:session_id>/start/', views.take_attendance, name='start_attendance_session'),
    path('sessions/<int:session_id>/take/', views.take_attendance, name='take_attendance'),
    path('sessions/<int:session_id>/complete/', views.complete_attendance_session, name='complete_attendance_session'),
    path('sessions/<int:session_id>/bulk-update/', views.bulk_update_attendance, name='bulk_update_attendance'),
    path('sessions/<int:session_id>/cancel/', views.cancel_attendance_session, name='cancel_attendance_session'),
    path('sessions/<int:session_id>/activate/', views.activate_attendance_session, name='activate_attendance_session'),

    # AJAX endpoints
    path('ajax/get-courses/', views.get_courses_for_batch, name='get_courses_for_batch'),
    path('ajax/get-subjects/', views.get_subjects_for_course, name='get_subjects_for_course'),
    path('ajax/update-record/<int:record_id>/', views.update_attendance_record, name='update_attendance_record'),

    # Teacher specific
    path('my-attendance/', views.teacher_attendance_list, name='teacher_attendance'),
    path('my-records/', views.student_attendance_records, name='student_attendance_records'),
    path('my-records/<int:subject_id>/', views.student_subject_attendance_detail, name='student_subject_attendance_detail'),
    path('my-datewise-report/', views.teacher_datewise_report, name='teacher_datewise_report'),
    
    # Guardian specific
    path('guardian/students/', views.guardian_students_attendance, name='guardian_students_attendance'),
    path('guardian/student/<int:student_id>/', views.guardian_student_attendance, name='guardian_student_attendance'),
    path('guardian/student/<int:student_id>/subject/<int:subject_id>/', views.guardian_subject_attendance_detail, name='guardian_subject_attendance_detail'),
    
    # Reports
    path('report/subject/<int:subject_id>/', views.subject_attendance_report, name='subject_attendance_report'),
    path('report/datewise/<int:session_id>/', views.datewise_attendance_report, name='datewise_attendance_report'),

    # Placeholders
    path('my-courses/', views.placeholder_view, name='teacher_courses'),
    path('my-batches/', views.placeholder_view, name='teacher_batches'),
    path('my-exams/', views.placeholder_view, name='teacher_exams'),
    path('my-assignments/', views.placeholder_view, name='teacher_assignments'),
    path('my-announcements/', views.placeholder_view, name='teacher_announcements'),
]