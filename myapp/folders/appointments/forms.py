from datetime import datetime, timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from myapp.folders.accounts.models import Doctor, Patient

from .models import Appointment, DoctorHoliday, DoctorWorkingHour

User = get_user_model()


class AppointmentRequestForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ('doctor', 'date_time')
        widgets = {
            'date_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    # Recurrence fields
    is_recurring = forms.BooleanField(
        required=False,
        label='This is a recurring appointment (chronic disease management)',
        help_text='Check if this appointment needs to be repeated regularly'
    )
    recurrence_frequency_months = forms.ChoiceField(
        choices=[
            (1, 'Monthly'),
            (3, 'Quarterly (Every 3 months)'),
            (6, 'Semi-annual (Every 6 months)'),
            (12, 'Annually (Every 12 months)'),
        ],
        required=False,
        initial=3,
        label='How often should this appointment repeat?'
    )
    recurrence_end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False,
        label='Stop recurring appointments after (leave blank for indefinite)'
    )

    def __init__(self, *args, **kwargs):
        self.patient = kwargs.pop('patient', None)
        super().__init__(*args, **kwargs)

    def clean_date_time(self):
        value = self.cleaned_data['date_time']
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        return value

    def clean(self):
        cleaned = super().clean()
        is_recurring = cleaned.get('is_recurring')
        recurrence_end_date = cleaned.get('recurrence_end_date')
        
        if is_recurring and recurrence_end_date:
            if recurrence_end_date <= cleaned['date_time'].date():
                raise forms.ValidationError('Recurrence end date must be after the first appointment date.')
        
        return cleaned
    
    def _post_clean(self):
        """Set patient before calling parent's _post_clean to avoid validation errors."""
        if self.patient and not self.instance.patient_id:
            self.instance.patient = self.patient
        super()._post_clean()
    
    def _create_recurring_appointments(self, first_appointment):
        """Create recurring appointment instances."""
        frequency_months = int(self.cleaned_data.get('recurrence_frequency_months', 3))
        end_date = self.cleaned_data.get('recurrence_end_date')
        
        current_date = first_appointment.date_time
        
        # Create recurring instances
        while True:
            # Add frequency to create next appointment
            month = current_date.month + frequency_months
            year = current_date.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1
            
            next_date = current_date.replace(year=year, month=month)
            
            # Stop if we've exceeded the end date or gone too far into the future
            if end_date and next_date.date() > end_date:
                break
            if next_date > timezone.now() + timedelta(days=365):  # Don't create more than 1 year in advance
                break
            
            # Create the recurring instance
            Appointment.objects.create(
                patient=first_appointment.patient,
                doctor=first_appointment.doctor,
                date_time=next_date,
                status=Appointment.Status.REQUESTED,
                notes=f'Recurring: {first_appointment.notes}' if first_appointment.notes else '',
                created_by=first_appointment.created_by,
                is_recurring=False,
                is_recurring_instance=True,
                recurrence_frequency_months=frequency_months,
                recurrence_end_date=end_date,
            )
            
            current_date = next_date


class AppointmentActionForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ('date_time', 'status')
        widgets = {
            'date_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class DoctorNoteForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ('notes', 'attendance', 'status')
    
    def _post_clean(self):
        """Skip full_clean validation since we're only updating simple fields."""
        # Don't call super()._post_clean() to avoid validation errors
        # on fields not included in this form (date_time, patient, doctor, etc.)
        pass


class DoctorWorkingHourForm(forms.ModelForm):
    class Meta:
        model = DoctorWorkingHour
        fields = ('weekday', 'start_time', 'end_time')
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }


class BulkDoctorWorkingHourForm(forms.Form):
    """Form to set working hours for multiple weekdays at once."""
    
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), label='Start Time (All Days)')
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), label='End Time (All Days)')
    
    # Checkboxes for each weekday
    monday = forms.BooleanField(required=False, label='Monday')
    tuesday = forms.BooleanField(required=False, label='Tuesday')
    wednesday = forms.BooleanField(required=False, label='Wednesday')
    thursday = forms.BooleanField(required=False, label='Thursday')
    friday = forms.BooleanField(required=False, label='Friday')
    saturday = forms.BooleanField(required=False, label='Saturday')
    sunday = forms.BooleanField(required=False, label='Sunday')
    
    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('end_time') and cleaned_data.get('start_time'):
            if cleaned_data['end_time'] <= cleaned_data['start_time']:
                raise forms.ValidationError('End time must be after start time.')
        
        weekdays = [
            cleaned_data.get('monday'),
            cleaned_data.get('tuesday'),
            cleaned_data.get('wednesday'),
            cleaned_data.get('thursday'),
            cleaned_data.get('friday'),
            cleaned_data.get('saturday'),
            cleaned_data.get('sunday'),
        ]
        if not any(weekdays):
            raise forms.ValidationError('Please select at least one weekday.')
        
        return cleaned_data
    
    def save(self, doctor):
        """Create working hour entries for selected weekdays."""
        start_time = self.cleaned_data['start_time']
        end_time = self.cleaned_data['end_time']
        
        weekday_map = {
            'monday': 0,
            'tuesday': 1,
            'wednesday': 2,
            'thursday': 3,
            'friday': 4,
            'saturday': 5,
            'sunday': 6,
        }
        
        created_count = 0
        for day_name, day_num in weekday_map.items():
            if self.cleaned_data.get(day_name):
                # Only create if it doesn't already exist
                DoctorWorkingHour.objects.get_or_create(
                    doctor=doctor,
                    weekday=day_num,
                    defaults={'start_time': start_time, 'end_time': end_time}
                )
                created_count += 1
        
        return created_count


class DoctorHolidayForm(forms.ModelForm):
    class Meta:
        model = DoctorHoliday
        fields = ('date', 'label')
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }


class SecretaryCreatePatientForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    full_name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=20, required=False)
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('This username already exists.')
        return username

    def save(self):
        full_name = self.cleaned_data['full_name'].strip()
        first, _, last = full_name.partition(' ')
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            first_name=first,
            last_name=last,
            role=User.Role.PATIENT,
            status=User.Status.APPROVED,
        )
        return Patient.objects.create(
            user=user,
            name=full_name,
            email=user.email,
            phone=self.cleaned_data.get('phone', ''),
        )
