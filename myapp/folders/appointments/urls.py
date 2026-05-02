from django.urls import path

from . import views

app_name = 'appointments'

urlpatterns = [
    path('doctors/', views.DoctorListView.as_view(), name='doctor_list'),
    path('doctors/<int:pk>/', views.DoctorDetailView.as_view(), name='doctor_detail'),
    path('request/', views.request_appointment, name='request_appointment'),
    path('cancel/<int:appointment_id>/', views.cancel_appointment, name='cancel_appointment'),
    path('patient/dashboard/', views.PatientAppointmentsView.as_view(), name='patient_dashboard'),
    path('doctor/agenda/', views.DoctorAgendaView.as_view(), name='doctor_agenda'),
    path('doctor/working-hours/', views.doctor_working_hours, name='doctor_working_hours'),
    path('doctor/working-hours/<int:hour_id>/delete/', views.delete_working_hour, name='delete_working_hour'),
    path('doctor/block-time-slot/', views.block_time_slot, name='block_time_slot'),
    path('doctor/appointment/<int:appointment_id>/update/', views.doctor_update_appointment, name='doctor_update_appointment'),
    path('secretary/dashboard/', views.secretary_dashboard, name='secretary_dashboard'),
    path('secretary/appointment/<int:appointment_id>/manage/', views.secretary_manage_appointment, name='secretary_manage_appointment'),
    path('secretary/appointment/<int:appointment_id>/<str:action>/', views.secretary_quick_action, name='secretary_quick_action'),
    path('secretary/create-patient/', views.secretary_create_patient, name='secretary_create_patient'),
    path('secretary/working-hours/', views.secretary_set_working_hours, name='secretary_working_hours'),
    path('secretary/holidays/', views.secretary_add_holiday, name='secretary_holidays'),
]
