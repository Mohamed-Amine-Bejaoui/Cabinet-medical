from django import forms
from django.contrib.auth import get_user_model

from .models import CustomUser, Doctor, Patient

User = get_user_model()


class SignupForm(forms.Form):
    """User registration form."""
    
    ROLE_CHOICES = (
        (CustomUser.Role.PATIENT, 'Patient'),
        (CustomUser.Role.DOCTOR, 'Doctor'),
        (CustomUser.Role.SECRETARY, 'Secretary'),
    )

    username = forms.CharField(max_length=150, strip=True)
    full_name = forms.CharField(max_length=150, strip=True)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20, required=False, strip=True)
    address = forms.CharField(max_length=255, required=False, strip=True)
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    assigned_doctor = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(role=CustomUser.Role.DOCTOR),
        required=False,
        label='Assigned Doctor (secretaries only)',
        empty_label='Select a doctor...',
    )
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput, min_length=8)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)

    def clean_username(self):
        if User.objects.filter(username__iexact=self.cleaned_data['username']).exists():
            raise forms.ValidationError('Username already taken.')
        return self.cleaned_data['username']

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Email already in use.')
        return email

    def clean_full_name(self):
        full_name = self.cleaned_data['full_name'].strip()
        if len(full_name.split()) < 2:
            raise forms.ValidationError('Please enter your full name.')
        return full_name

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password1') != cleaned.get('password2'):
            self.add_error('password2', 'Passwords do not match.')
        
        if cleaned.get('role') == CustomUser.Role.SECRETARY and not cleaned.get('assigned_doctor'):
            self.add_error('assigned_doctor', 'Secretaries must have an assigned doctor.')
        
        return cleaned

    def save(self, commit=True):
        """Create user and associated profile."""
        full_name = self.cleaned_data['full_name'].strip()
        first, _, last = full_name.partition(' ')

        user = User(
            username=self.cleaned_data['username'],
            first_name=first,
            last_name=last,
            email=self.cleaned_data['email'].lower(),
            role=self.cleaned_data['role'],
        )

        # Doctors require approval, others auto-approved
        if user.role == CustomUser.Role.DOCTOR:
            user.status = CustomUser.Status.PENDING
        else:
            user.status = CustomUser.Status.APPROVED

        # Assign doctor to secretary
        if user.role == CustomUser.Role.SECRETARY:
            user.assigned_doctor = self.cleaned_data.get('assigned_doctor')

        user.set_password(self.cleaned_data['password1'])

        if commit:
            user.save()
            self._create_profile(user)

        return user

    def _create_profile(self, user):
        """Create user's profile."""
        phone = self.cleaned_data.get('phone', '')
        address = self.cleaned_data.get('address', '')
        full_name = self.cleaned_data['full_name']

        if user.role == CustomUser.Role.PATIENT:
            Patient.objects.create(
                user=user,
                name=full_name,
                email=user.email,
                phone=phone,
                address=address,
            )
        elif user.role == CustomUser.Role.DOCTOR:
            Doctor.objects.create(
                user=user,
                name=full_name,
                specialty='General Medicine',
                phone=phone,
                address=address,
            )


class PatientProfileForm(forms.ModelForm):
    """Form to edit patient profile."""
    
    class Meta:
        model = Patient
        fields = ('name', 'email', 'phone', 'address')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].disabled = True


class DoctorProfileForm(forms.ModelForm):
    """Form to edit doctor profile."""
    
    class Meta:
        model = Doctor
        fields = ('name', 'specialty', 'phone', 'address')


class UserProfileForm(forms.ModelForm):
    """Form to edit user account details."""
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].disabled = True

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Username already taken.')
        return username
