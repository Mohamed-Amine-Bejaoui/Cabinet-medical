from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """Custom user model with role-based access control."""
    
    class Role(models.TextChoices):
        PATIENT = 'patient', 'Patient'
        DOCTOR = 'doctor', 'Doctor'
        SECRETARY = 'secretary', 'Secretary'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        BLOCKED = 'blocked', 'Blocked'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PATIENT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    assigned_doctor = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_secretaries',
        limit_choices_to={'role': Role.DOCTOR},
    )

    def clean(self):
        """Ensure secretaries have an assigned doctor."""
        if self.role != self.Role.SECRETARY:
            self.assigned_doctor = None

    @property
    def is_patient(self):
        return self.role == self.Role.PATIENT

    @property
    def is_doctor(self):
        return self.role == self.Role.DOCTOR

    @property
    def is_secretary(self):
        return self.role == self.Role.SECRETARY

    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED

    def __str__(self):
        return self.username


class Doctor(models.Model):
    """Doctor profile linked to CustomUser."""
    
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='doctor_profile',
        limit_choices_to={'role': CustomUser.Role.DOCTOR},
    )
    name = models.CharField(max_length=150)
    specialty = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Dr. {self.name}"


class Patient(models.Model):
    """Patient profile linked to CustomUser."""
    
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='patient_profile',
        limit_choices_to={'role': CustomUser.Role.PATIENT},
    )
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


