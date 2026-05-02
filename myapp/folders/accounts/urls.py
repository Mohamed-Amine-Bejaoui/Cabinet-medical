from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('status/', views.check_status, name='check_status'),
    path('approve-me/', views.auto_approve_patient, name='auto_approve_patient'),
    path('admin/panel/', views.admin_panel, name='admin_panel'),
    path('admin/approve/<int:doctor_id>/', views.approve_doctor, name='approve_doctor'),
    path('admin/block/<int:doctor_id>/', views.block_doctor, name='block_doctor'),
    path('admin/delete/<int:doctor_id>/', views.delete_doctor, name='delete_doctor'),
]