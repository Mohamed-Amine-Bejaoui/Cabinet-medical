from datetime import datetime, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Appointment, DoctorHoliday, DoctorWorkingHour


def notify_appointment_event(appointment, event, appointment_id=None):
    """
    Send email notifications for appointment events.
    - 'confirmed': emails BOTH the patient AND the doctor
    - 'created', 'cancelled': emails the patient only
    """
    if appointment is None:
        return

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'clinic@example.com')
    patient_email = appointment.patient.email
    date_str = appointment.date_time.strftime('%Y-%m-%d %H:%M')
    doctor_name = appointment.doctor.name
    patient_name = appointment.patient.name

    # ── Always notify the patient ─────────────────────────────────────────
    if patient_email:
        if event == 'confirmed':
            patient_subject = f'Appointment Confirmed — {date_str}'
            patient_body = (
                f'Dear {patient_name},\n\n'
                f'Your appointment with Dr. {doctor_name} has been confirmed.\n\n'
                f'  Date & Time: {date_str}\n\n'
                f'Please arrive 10 minutes early. If you need to cancel, '
                f'do so at least 24 hours in advance.\n\n'
                f'Best regards,\n'
                f'The Medical Cabinet Team'
            )
        elif event == 'cancelled':
            patient_subject = f'Appointment Cancelled — {date_str}'
            patient_body = (
                f'Dear {patient_name},\n\n'
                f'Your appointment with Dr. {doctor_name} on {date_str} '
                f'has been cancelled.\n\n'
                f'If this was unexpected, please contact the clinic to reschedule.\n\n'
                f'Best regards,\n'
                f'The Medical Cabinet Team'
            )
        else:  # 'created' or any other event
            patient_subject = f'Appointment {event.title()} — {date_str}'
            patient_body = (
                f'Dear {patient_name},\n\n'
                f'Your appointment request with Dr. {doctor_name} on {date_str} '
                f'has been received. You will be notified once it is confirmed.\n\n'
                f'Best regards,\n'
                f'The Medical Cabinet Team'
            )

        send_mail(patient_subject, patient_body, from_email, [patient_email], fail_silently=True)

    # ── Notify the doctor when an appointment is confirmed ────────────────
    if event == 'confirmed':
        doctor_email = getattr(appointment.doctor, 'user', None)
        if doctor_email:
            doctor_email = doctor_email.email
        if doctor_email:
            doctor_subject = f'New Confirmed Appointment — {patient_name} on {date_str}'
            doctor_body = (
                f'Dear Dr. {doctor_name},\n\n'
                f'A new appointment has been confirmed in your schedule.\n\n'
                f'  Patient: {patient_name}\n'
                f'  Date & Time: {date_str}\n\n'
                f'Please review your agenda for details.\n\n'
                f'Best regards,\n'
                f'The Medical Cabinet Team'
            )
            send_mail(doctor_subject, doctor_body, from_email, [doctor_email], fail_silently=True)


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
