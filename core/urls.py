# core/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('signup/',    views.signup_view,    name='signup'),
    path('login/',     views.login_view,     name='login'),
    path('logout/',    views.logout_view,    name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('landing/', views.landing_view, name='landing'),

    # Job Description
    path('jobs/',                 views.job_list_view,   name='job_list'),
    path('jobs/create/',          views.job_create_view, name='job_create'),
    path('jobs/<int:pk>/',        views.job_detail_view, name='job_detail'),
    path('jobs/<int:pk>/edit/',   views.job_edit_view,   name='job_edit'),
    path('jobs/<int:pk>/delete/', views.job_delete_view, name='job_delete'),

    # Resumes
    path('resumes/',                  views.resume_list_view,    name='resume_list'),
    path('resumes/upload/',           views.resume_upload_view,  name='resume_upload'),
    path('resumes/<int:pk>/process/', views.process_resume_view, name='process_resume'),
    path('resumes/<int:pk>/results/', views.resume_result_view,  name='resume_result'),
    path('resumes/<int:pk>/delete/',  views.resume_delete_view,  name='resume_delete'),

    # Matching Engine
    path('resumes/<int:pk>/match/',   views.run_matching_view,   name='run_matching'),
    path('jobs/<int:pk>/ranking/',    views.job_ranking_view,    name='job_ranking'),

    # Skill Gap Analysis
    path('match/<int:pk>/gap/',       views.skill_gap_view,      name='skill_gap'),



    # Super Admin Panel
    path('admin-panel/',                    views.admin_dashboard_view,    name='admin_dashboard'),
    path('admin-panel/users/',              views.admin_user_list_view,    name='admin_user_list'),
    path('admin-panel/users/create/',       views.admin_create_hr_view,    name='admin_create_hr'),
    path('admin-panel/users/<int:pk>/',     views.admin_user_detail_view,  name='admin_user_detail'),
    path('admin-panel/users/<int:pk>/toggle/', views.admin_user_toggle_view, name='admin_user_toggle'),
    path('admin-panel/users/<int:pk>/delete/', views.admin_user_delete_view, name='admin_user_delete'),


    # Notifications
    path('notifications/',              views.notifications_view,   name='notifications'),
    path('notifications/<int:pk>/read/', views.mark_read_view,      name='mark_read'),
    path('notifications/read-all/',     views.mark_all_read_view,   name='mark_all_read'),
    path('notifications/count/',        views.unread_count_view,    name='unread_count'),

    path('jobs/<int:pk>/send-selection/', views.send_selection_email_view, name='send_selection_email'),

    path('jobs/<int:pk>/send-rejection/', views.send_rejection_email_view, name='send_rejection_email'),

    path('analytics/', views.analytics_view, name='analytics'),

    path('jobs/<int:pk>/export-pdf/', views.export_pdf_report_view, name='export_pdf_report'),

    # Skill Library
    path('skills/',                  views.skill_library_view, name='skill_library'),
    path('skills/add/',              views.skill_add_view,     name='skill_add'),
    path('skills/<int:pk>/edit/',    views.skill_edit_view,    name='skill_edit'),
    path('skills/<int:pk>/delete/',  views.skill_delete_view,  name='skill_delete'),

    path('resumes/process-all/', views.process_all_resumes_view, name='process_all_resumes'),

]


