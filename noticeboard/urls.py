from django.urls import path
from . import views

app_name = 'noticeboard'

urlpatterns = [
    path('', views.notice_list, name='notice_list'),
    path('notice/<int:notice_id>/', views.notice_detail, name='notice_detail'),
    path('create/', views.create_notice, name='create_notice'),
    path('create-teacher/', views.teacher_create_notice, name='teacher_create_notice'),
    path('notice/<int:notice_id>/edit/', views.edit_notice, name='edit_notice'),
    path('notice/<int:notice_id>/delete/', views.delete_notice, name='delete_notice'),
    path('attachment/<int:attachment_id>/delete/', views.delete_attachment, name='delete_attachment'),
]
