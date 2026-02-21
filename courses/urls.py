from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # Course URLs
    path('', views.course_list, name='course_list'),
    path('add/', views.add_course, name='add_course'),
    path('<int:course_id>/', views.view_course, name='view_course'),
    path('<int:course_id>/edit/', views.edit_course, name='edit_course'),
    path('<int:course_id>/delete/', views.delete_course, name='delete_course'),
    path('<int:course_id>/toggle/', views.toggle_course_status, name='toggle_course_status'),
    
    # Subject URLs
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/add/', views.add_subject, name='add_subject'),
    path('course/<int:course_id>/subjects/', views.subject_list, name='course_subjects'),
    path('course/<int:course_id>/subjects/add/', views.add_subject, name='add_course_subject'),
    path('subjects/<int:subject_id>/edit/', views.edit_subject, name='edit_subject'),
    path('subjects/<int:subject_id>/delete/', views.delete_subject, name='delete_subject'),
    
    # Teacher URLs (for accessing assigned courses and subjects)
    path('my-courses/', views.teacher_courses, name='teacher_courses'),
    path('my-subjects/', views.teacher_subjects, name='teacher_subjects'),
    
    # Student URLs (for accessing enrolled courses)
    path('student-courses/', views.student_courses, name='student_courses'),
    path('student-subjects/', views.student_subjects, name='student_subjects'),
    
    # Guardian URLs (for accessing ward's courses and subjects)
    path('guardian-courses/<int:student_id>/', views.guardian_student_courses, name='guardian_student_courses'),
    path('guardian-courses/<int:student_id>/course/<int:course_id>/subjects/', views.guardian_course_subjects, name='guardian_course_subjects'),
]