from datetime import datetime, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Appointment, DoctorHoliday, DoctorWorkingHour


def notify_appointment_event(appointment, event):
    patient_email = appointment.patient.email
    if not patient_email:
        return

    subject = f'Appointment {event}: {appointment.date_time:%Y-%m-%d %H:%M}'
    message = (
        f'Doctor: {appointment.doctor.name}\n'
        f'Patient: {appointment.patient.name}\n'
        f'Status: {appointment.status}\n'
        f'Event: {event}\n'
    )
    send_mail(
        subject,
        message,
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'clinic@example.com'),
        [patient_email],
        fail_silently=True,
    )


def get_available_slots(doctor, day):
    if DoctorHoliday.objects.filter(doctor=doctor, date=day).exists():
        return []

    weekday = day.weekday()
    hours = DoctorWorkingHour.objects.filter(doctor=doctor, weekday=weekday).order_by('start_time')
    if not hours.exists():
        return []

    slots = []
    now = timezone.now()
    for window in hours:
        cursor = timezone.make_aware(datetime.combine(day, window.start_time), timezone.get_current_timezone())
        window_end = timezone.make_aware(datetime.combine(day, window.end_time), timezone.get_current_timezone())

        while cursor + timedelta(minutes=30) <= window_end:
            end_time = cursor + timedelta(minutes=30)
            if not (cursor.time() < Appointment.LUNCH_END and end_time.time() > Appointment.LUNCH_START):
                occupied = Appointment.objects.filter(
                    doctor=doctor,
                    status__in=[Appointment.Status.REQUESTED, Appointment.Status.CONFIRMED, Appointment.Status.COMPLETED],
                    date_time__lt=end_time,
                    date_time__gt=cursor - timedelta(minutes=30),
                ).exists()
                if cursor >= now + timedelta(hours=1) and cursor <= now + timedelta(days=90) and not occupied:
                    slots.append(cursor)
            cursor += timedelta(minutes=30)

    return slots
