from datetime import timedelta, time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from myapp.folders.accounts.models import Doctor, Patient


class DoctorWorkingHour(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, 'Monday'
        TUESDAY = 1, 'Tuesday'
        WEDNESDAY = 2, 'Wednesday'
        THURSDAY = 3, 'Thursday'
        FRIDAY = 4, 'Friday'
        SATURDAY = 5, 'Saturday'
        SUNDAY = 6, 'Sunday'

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='working_hours')
    weekday = models.IntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ('weekday', 'start_time')
        constraints = [
            models.UniqueConstraint(fields=('doctor', 'weekday', 'start_time', 'end_time'), name='uniq_doctor_hours_block'),
        ]

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError({'end_time': 'End time must be after start time.'})

    def __str__(self):
        return f'{self.doctor.name} - {self.get_weekday_display()} {self.start_time}-{self.end_time}'


class DoctorHoliday(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='holidays')
    date = models.DateField()
    label = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ('date',)
        constraints = [
            models.UniqueConstraint(fields=('doctor', 'date'), name='uniq_doctor_holiday'),
        ]

    def __str__(self):
        return f'{self.doctor.name} holiday {self.date}'


class Appointment(models.Model):
    SLOT_MINUTES = 30
    LUNCH_START = time(12, 0)
    LUNCH_END = time(13, 30)

    class Status(models.TextChoices):
        REQUESTED = 'requested', 'Requested'
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'

    class Attendance(models.TextChoices):
        UNKNOWN = 'unknown', 'Unknown'
        PRESENT = 'present', 'Present'
        ABSENT = 'absent', 'Absent'

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    date_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    attendance = models.CharField(max_length=10, choices=Attendance.choices, default=Attendance.UNKNOWN)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_appointments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Recurrence fields for chronic disease management
    is_recurring = models.BooleanField(default=False)
    recurrence_frequency_months = models.PositiveIntegerField(
        default=3,
        help_text='Number of months between recurring appointments (e.g., 3 for quarterly, 6 for semi-annual, 12 for annual)'
    )
    recurrence_end_date = models.DateField(null=True, blank=True, help_text='When to stop creating recurring appointments')
    is_recurring_instance = models.BooleanField(default=False, help_text='True if this is part of a recurring series')

    class Meta:
        ordering = ('date_time',)

    @property
    def end_time(self):
        return self.date_time + timedelta(minutes=self.SLOT_MINUTES)

    def can_cancel(self):
        return timezone.now() <= self.date_time - timedelta(hours=24)

    def clean(self):
        errors = {}
        now = timezone.now()
        earliest = now + timedelta(hours=1)
        latest = now + timedelta(days=90)

        if self.date_time < earliest:
            errors['date_time'] = 'Booking must be at least 1 hour ahead.'
        if self.date_time > latest:
            errors['date_time'] = 'Booking cannot be more than 3 months ahead.'

        appt_start = self.date_time.time()
        appt_end = self.end_time.time()
        if appt_start < self.LUNCH_END and appt_end > self.LUNCH_START:
            errors['date_time'] = 'Lunch break (12:00 to 13:30) is blocked.'

        if DoctorHoliday.objects.filter(doctor=self.doctor, date=self.date_time.date()).exists():
            errors['date_time'] = 'Doctor is on holiday for this date.'

        weekday = self.date_time.weekday()
        has_working_window = DoctorWorkingHour.objects.filter(
            doctor=self.doctor,
            weekday=weekday,
            start_time__lte=appt_start,
            end_time__gte=appt_end,
        ).exists()
        if not has_working_window:
            errors['date_time'] = 'Outside doctor working hours.'

        overlap_exists = Appointment.objects.filter(
            doctor=self.doctor,
            status__in=[self.Status.REQUESTED, self.Status.CONFIRMED, self.Status.COMPLETED],
            date_time__lt=self.end_time,
            date_time__gt=self.date_time - timedelta(minutes=self.SLOT_MINUTES),
        ).exclude(pk=self.pk).exists()
        if overlap_exists:
            errors['date_time'] = 'This slot is already occupied.'

        daily_count = Appointment.objects.filter(
            patient=self.patient,
            date_time__date=self.date_time.date(),
            status__in=[self.Status.REQUESTED, self.Status.CONFIRMED, self.Status.COMPLETED],
        ).exclude(pk=self.pk).count()
        if daily_count >= 2:
            errors['patient'] = 'Patient cannot have more than 2 appointments in one day.'

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.patient.name} with {self.doctor.name} at {self.date_time:%Y-%m-%d %H:%M}'