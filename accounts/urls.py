from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import batch_views

urlpatterns = [
    # Authentication URLs
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard URLs
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('guardian/dashboard/', views.guardian_dashboard, name='guardian_dashboard'),
    
    # General User Management (supports optional role filter)
    path('admin/users/', views.user_list, name='user_list'),
    
    # Teacher Management URLs
    path('admin/teachers/', views.teacher_list, name='teacher_list'),
    path('admin/teachers/create/', views.create_teacher, name='create_teacher'),
    path('admin/teachers/<int:teacher_id>/', views.view_teacher, name='view_teacher'),
    path('admin/teachers/<int:teacher_id>/edit/', views.edit_teacher, name='edit_teacher'),
    
    # Student Management URLs
    path('admin/students/', views.student_list, name='student_list'),
    path('admin/students/absent/', views.absent_list, name='absent_list'),
    
    # User Management URLs
    path('admin/users/create/student/', views.create_student, name='create_student'),
    path('admin/users/create/guardian/', views.create_guardian, name='create_guardian'),
    
    # User Detail and Edit URLs
    path('admin/users/<int:user_id>/edit/student/', views.edit_student, name='edit_student'),
    path('admin/users/<int:user_id>/edit/guardian/', views.edit_guardian, name='edit_guardian'),
    
    # User Actions URLs (for all user types)
    path('admin/users/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path('admin/users/<int:user_id>/toggle/', views.toggle_user_status, name='toggle_user_status'),
    path('admin/users/<int:user_id>/reset-password/', views.reset_user_password, name='reset_user_password'),
    path('admin/users/bulk-actions/', views.bulk_user_actions, name='bulk_user_actions'),
    
    # Profile and Settings URLs
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('change-password/', views.change_password, name='change_password'),
    
    # Password Reset URLs (Django built-in)
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='auth/password_reset.html'
         ), 
         name='password_reset'),
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='auth/password_reset_done.html'
         ), 
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='auth/password_reset_confirm.html'
         ), 
         name='password_reset_confirm'),
    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='auth/password_reset_complete.html'
         ), 
         name='password_reset_complete'),

    # Batch Management URLs
    path('admin/batches/', batch_views.batch_list, name='batch_list'),
    path('admin/batches/add/', batch_views.add_batch, name='add_batch'),
    path('admin/batches/<int:batch_id>/', batch_views.view_batch, name='view_batch'),
    path('admin/batches/<int:batch_id>/edit/', batch_views.edit_batch, name='edit_batch'),
    path('admin/batches/<int:batch_id>/toggle-course/<int:batch_course_id>/', batch_views.toggle_batch_course, name='toggle_batch_course'),
    path('admin/batches/<int:batch_id>/delete/', batch_views.delete_batch, name='delete_batch'),
    path('admin/batches/<int:batch_id>/add-course/', batch_views.add_course_to_batch, name='add_course_to_batch'),
    path('admin/batches/<int:batch_id>/remove-course/<int:course_id>/', batch_views.remove_course_from_batch, name='remove_course_from_batch'),
    path('admin/batches/<int:batch_id>/courses/<int:course_id>/students/', views.course_student_list, name='course_student_list'),

    # Student Management URLs for Courses
    path('admin/batches/<int:batch_id>/courses/<int:course_id>/students/', views.course_student_list, name='course_student_list'),
    path('admin/batches/<int:batch_id>/courses/<int:course_id>/students/add/', views.add_student_to_course, name='add_student_to_course'),

    # Student Detail URLs
    path('admin/students/<int:student_id>/', views.view_student, name='view_student'),
    path('admin/students/<int:student_id>/edit/', views.edit_student, name='edit_student'),
    path('admin/students/<int:student_id>/delete/', views.delete_student, name='delete_student'),
]