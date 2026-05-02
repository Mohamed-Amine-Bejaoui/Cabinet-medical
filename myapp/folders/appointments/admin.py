from django.contrib import admin

from .models import Appointment, DoctorHoliday, DoctorWorkingHour


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'patient', 'date_time', 'status', 'attendance')
    list_filter = ('status', 'attendance', 'doctor')
    search_fields = ('doctor__name', 'patient__name', 'patient__email')


@admin.register(DoctorWorkingHour)
class DoctorWorkingHourAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'weekday', 'start_time', 'end_time')
    list_filter = ('doctor', 'weekday')


@admin.register(DoctorHoliday)
class DoctorHolidayAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'date', 'label')
    list_filter = ('doctor',)
