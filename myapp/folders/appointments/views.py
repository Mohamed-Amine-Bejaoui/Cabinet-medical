from datetime import datetime, timedelta
from calendar import monthcalendar
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, ListView

from myapp.folders.accounts.models import CustomUser, Doctor, Patient

from .forms import (
    AppointmentActionForm,
    AppointmentRequestForm,
    BulkDoctorWorkingHourForm,
    DoctorHolidayForm,
    DoctorNoteForm,
    DoctorWorkingHourForm,
    SecretaryCreatePatientForm,
)
from .models import Appointment, DoctorWorkingHour, DoctorHoliday
from .services import get_available_slots, notify_appointment_event


def _user_is_approved(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.status == CustomUser.Status.APPROVED


def _ensure_role(user, role):
    return _user_is_approved(user) and user.role == role


@method_decorator(login_required, name='dispatch')
class DoctorListView(ListView):
    model = Doctor
    template_name = 'doctor_list.html'
    context_object_name = 'doctors'

    def dispatch(self, request, *args, **kwargs):
        # Only approved patients can browse doctors
        if request.user.role != CustomUser.Role.PATIENT or request.user.status != CustomUser.Status.APPROVED:
            messages.error(request, 'Only approved patients can browse doctors.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Doctor.objects.select_related('user').all().order_by('name')
        # Simple search by name or specialty
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(name__icontains=search) | queryset.filter(specialty__icontains=search) | queryset.filter(address__icontains=search)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


@method_decorator(login_required, name='dispatch')
class DoctorDetailView(DetailView):
    model = Doctor
    template_name = 'doctor_detail.html'
    context_object_name = 'doctor'

    def dispatch(self, request, *args, **kwargs):
        # Only approved patients can view doctor details
        if request.user.role != CustomUser.Role.PATIENT or request.user.status != CustomUser.Status.APPROVED:
            messages.error(request, 'Only approved patients can view doctor details.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date_str = self.request.GET.get('date')
        selected_date = timezone.localdate()
        if date_str:
            try:
                selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        context['selected_date'] = selected_date
        context['available_slots'] = get_available_slots(self.object, selected_date)
        return context


@login_required
def request_appointment(request):
    """Only approved patients can request appointments."""
    if request.user.role != CustomUser.Role.PATIENT or request.user.status != CustomUser.Status.APPROVED:
        messages.error(request, 'Only approved patients can request appointments.')
        return redirect('dashboard')

    patient = get_object_or_404(Patient, user=request.user)
    initial = {}
    doctor_id = request.GET.get('doctor_id')
    date_time = request.GET.get('date_time')
    if doctor_id:
        initial['doctor'] = doctor_id
    if date_time:
        initial['date_time'] = date_time

    if request.method == 'POST':
        form = AppointmentRequestForm(request.POST, patient=patient)
        if form.is_valid():
            # Extract cleaned data
            is_recurring = form.cleaned_data.get('is_recurring', False)
            
            # Get the appointment instance from the form (patient is set in _post_clean)
            appointment = form.instance
            appointment.patient = patient
            appointment.created_by = request.user
            appointment.status = Appointment.Status.REQUESTED
            appointment.is_recurring = is_recurring
            appointment.recurrence_frequency_months = int(form.cleaned_data.get('recurrence_frequency_months', 3))
            appointment.recurrence_end_date = form.cleaned_data.get('recurrence_end_date')
            
            # Save the appointment
            appointment.save()
            
            # Create recurring instances if needed
            if is_recurring:
                try:
                    form._create_recurring_appointments(appointment)
                    messages.success(request, 'Recurring appointment series created successfully!')
                except Exception as e:
                    messages.warning(request, f'Initial appointment created, but recurring instances failed: {str(e)}')
            else:
                messages.success(request, 'Appointment request submitted.')
            
            notify_appointment_event(appointment, 'created')
            return redirect('appointments:patient_dashboard')
    else:
        form = AppointmentRequestForm(initial=initial, patient=patient)
    return render(request, 'appointment_request.html', {'form': form})


@login_required
def cancel_appointment(request, appointment_id):
    if not _user_is_approved(request.user):
        messages.error(request, 'Your account must be approved to perform this action.')
        return redirect('dashboard')

    appointment = get_object_or_404(Appointment, id=appointment_id)
    user = request.user

    is_patient_owner = (user.role == CustomUser.Role.PATIENT and 
                       appointment.patient.user_id == user.id)
    is_doctor_owner = (user.role == CustomUser.Role.DOCTOR and 
                      user.status == CustomUser.Status.APPROVED and 
                      appointment.doctor.user_id == user.id)
    is_secretary_owner = (user.role == CustomUser.Role.SECRETARY and 
                         user.status == CustomUser.Status.APPROVED and 
                         user.assigned_doctor_id == appointment.doctor.user_id)
    if not (is_patient_owner or is_doctor_owner or is_secretary_owner):
        messages.error(request, 'You do not have permission to cancel this appointment.')
        return redirect('dashboard')

    if not appointment.can_cancel():
        messages.error(request, 'Cancellation is rejected within 24 hours of appointment time.')
        return redirect('dashboard')

    appointment.status = Appointment.Status.CANCELLED
    appointment.save(update_fields=['status', 'updated_at'])
    notify_appointment_event(appointment, 'cancelled')
    messages.success(request, 'Appointment cancelled.')
    return redirect('dashboard')


@method_decorator(login_required, name='dispatch')
class PatientAppointmentsView(ListView):
    model = Appointment
    template_name = 'patient_dashboard.html'
    context_object_name = 'appointments'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != CustomUser.Role.PATIENT or request.user.status != CustomUser.Status.APPROVED:
            messages.error(request, 'Only approved patients can access this page.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        patient = get_object_or_404(Patient, user=self.request.user)
        return Appointment.objects.filter(patient=patient).select_related('doctor').order_by('-date_time')


@method_decorator(login_required, name='dispatch')
class DoctorAgendaView(ListView):
    model = Appointment
    template_name = 'doctor_calendar.html'
    context_object_name = 'appointments'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != CustomUser.Role.DOCTOR or request.user.status != CustomUser.Status.APPROVED:
            messages.error(request, 'Only approved doctors can access this page.')
            return redirect('dashboard')
        
        # Ensure doctor has a profile (auto-create if missing)
        try:
            request.user.doctor_profile
        except Doctor.DoesNotExist:
            Doctor.objects.create(
                user=request.user,
                name=request.user.get_full_name() or request.user.username,
                specialty='General Medicine'
            )
        
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        doctor = self.request.user.doctor_profile
        # Only show CONFIRMED appointments for doctors
        return Appointment.objects.filter(
            doctor=doctor,
            status=Appointment.Status.CONFIRMED
        ).select_related('patient').order_by('date_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doctor = self.request.user.doctor_profile
        
        from datetime import date
        
        # Only CONFIRMED appointments for doctors
        today = timezone.now().date()
        
        # Handle month navigation from GET parameters
        month = self.request.GET.get('month')
        year = self.request.GET.get('year')
        
        if month and year:
            try:
                current_month = date(int(year), int(month), 1)
            except (ValueError, TypeError):
                current_month = today.replace(day=1)
        else:
            current_month = today.replace(day=1)
        
        # Calculate next and previous months
        if current_month.month == 12:
            next_month = current_month.replace(year=current_month.year + 1, month=1)
        else:
            next_month = current_month.replace(month=current_month.month + 1)
        
        if current_month.month == 1:
            prev_month = current_month.replace(year=current_month.year - 1, month=12)
        else:
            prev_month = current_month.replace(month=current_month.month - 1)
        
        # Get all confirmed appointments for current month
        month_end = next_month
        all_confirmed = Appointment.objects.filter(
            doctor=doctor,
            status=Appointment.Status.CONFIRMED,
            date_time__date__gte=current_month,
            date_time__date__lt=month_end
        ).select_related('patient').order_by('date_time')
        
        # Get today's appointments (only if viewing current month)
        if current_month.year == today.year and current_month.month == today.month:
            today_appts = [appt for appt in all_confirmed if appt.date_time.date() == today]
        else:
            today_appts = []
        
        # Build calendar grid with appointments
        appointments_by_date = defaultdict(list)
        for appt in all_confirmed:
            date_key = appt.date_time.date()
            appointments_by_date[date_key].append(appt)
        
        # Create calendar structure
        month_calendar = monthcalendar(current_month.year, current_month.month)
        calendar_weeks = []
        for week in month_calendar:
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append(None)
                else:
                    date_obj = current_month.replace(day=day)
                    appts_count = len(appointments_by_date.get(date_obj, []))
                    week_data.append({
                        'day': day,
                        'date': date_obj,
                        'appointments': appointments_by_date.get(date_obj, []),
                        'is_today': date_obj == today,
                        'is_past': date_obj < today,
                        'appt_count': appts_count
                    })
            calendar_weeks.append(week_data)
        
        context['today_appointments'] = today_appts
        context['appointments_by_date'] = dict(appointments_by_date)
        context['today'] = today
        context['current_month'] = current_month
        context['calendar_weeks'] = calendar_weeks
        context['month_name'] = current_month.strftime('%B %Y')
        context['weekday_names'] = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        context['prev_month'] = prev_month
        context['next_month'] = next_month
        
        # Generate date range for month selector (12 months: 6 before + 6 after)
        date_range = []
        start_month = current_month.replace(day=1)
        for i in range(-6, 7):  # 6 months before to 6 months after
            if i == 0:
                month_date = start_month
            elif i > 0:
                # Add months forward
                new_month = start_month.month + i
                new_year = start_month.year
                while new_month > 12:
                    new_month -= 12
                    new_year += 1
                month_date = start_month.replace(year=new_year, month=new_month)
            else:
                # Add months backward
                new_month = start_month.month + i
                new_year = start_month.year
                while new_month < 1:
                    new_month += 12
                    new_year -= 1
                month_date = start_month.replace(year=new_year, month=new_month)
            date_range.append(month_date)
        
        context['date_range'] = date_range
        
        return context


@login_required
def doctor_update_appointment(request, appointment_id):
    """Only the doctor who owns the appointment can update it."""
    if not _ensure_role(request.user, CustomUser.Role.DOCTOR):
        messages.error(request, 'Only approved doctors can update appointments.')
        return redirect('dashboard')
    
    doctor = request.user.doctor_profile
    appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)
    # Verify ownership

    appointment = get_object_or_404(Appointment, id=appointment_id, doctor__user=request.user)
    if request.method == 'POST':
        form = DoctorNoteForm(request.POST, instance=appointment)
        if form.is_valid():
            # Check if it's a status change to CANCELLED
            new_status = request.POST.get('status')
            if new_status == Appointment.Status.CANCELLED:
                # Delete the appointment instead of updating it
                old_status = appointment.status
                patient_name = appointment.patient.user.get_full_name() or appointment.patient.user.username
                appointment.delete()
                
                # Notify patient about cancellation
                if old_status == Appointment.Status.REQUESTED:
                    notify_appointment_event(None, 'cancelled', appointment_id=appointment_id)
                
                messages.success(request, f'✕ Appointment with {patient_name} has been deleted.')
            else:
                appointment = form.save(commit=False)
                old_status = appointment.status
                
                if new_status:
                    appointment.status = new_status
                
                appointment.save()
                
                # Notify based on status change
                if old_status == Appointment.Status.REQUESTED:
                    if new_status == Appointment.Status.CONFIRMED:
                        notify_appointment_event(appointment, 'confirmed')
                        messages.success(request, '✓ Appointment approved and confirmed.')
                    elif new_status == Appointment.Status.CANCELLED:
                        notify_appointment_event(appointment, 'cancelled')
                        messages.success(request, '✕ Appointment request rejected.')
                elif new_status == Appointment.Status.COMPLETED:
                    messages.success(request, '✓ Appointment marked as completed.')
                else:
                    messages.success(request, 'Appointment updated.')
            
            return redirect('appointments:doctor_agenda')
    else:
        form = DoctorNoteForm(instance=appointment)

    return render(request, 'doctor_update_appointment.html', {'form': form, 'appointment': appointment})


@login_required
def secretary_dashboard(request):
    """Secretary dashboard - only accessible by approved secretaries."""
    if request.user.role != CustomUser.Role.SECRETARY or request.user.status != CustomUser.Status.APPROVED:
        messages.error(request, 'Only approved secretaries can access this page.')
        return redirect('dashboard')
    if not request.user.assigned_doctor_id:
        messages.error(request, 'No doctor assigned to your account yet.')
        return redirect('dashboard')

    doctor = get_object_or_404(Doctor, user_id=request.user.assigned_doctor_id)
    
    # Pending requests that need approval
    pending_requests = Appointment.objects.filter(
        doctor=doctor,
        status=Appointment.Status.REQUESTED
    ).select_related('patient').order_by('date_time')
    
    # All appointments
    appointments = Appointment.objects.filter(doctor=doctor).select_related('patient').order_by('date_time')
    
    return render(
        request,
        'secretary_dashboard.html',
        {
            'doctor': doctor,
            'appointments': appointments,
            'pending_requests': pending_requests,
        },
    )


@login_required
def secretary_manage_appointment(request, appointment_id):
    """Secretary can only manage appointments for their assigned doctor."""
    if request.user.role != CustomUser.Role.SECRETARY or request.user.status != CustomUser.Status.APPROVED:
        messages.error(request, 'Only approved secretaries can perform this action.')
        return redirect('dashboard')

    appointment = get_object_or_404(
        Appointment,
        id=appointment_id,
        doctor__user_id=request.user.assigned_doctor_id,
    )
    if request.method == 'POST':
        form = AppointmentActionForm(request.POST, instance=appointment)
        if form.is_valid():
            updated = form.save(commit=False)
            try:
                if updated.status == Appointment.Status.CANCELLED and not appointment.can_cancel():
                    form.add_error(None, 'Cancellation is rejected within 24 hours of appointment time.')
                    return render(request, 'secretary_manage_appointment.html', {'form': form, 'appointment': appointment})
                updated.full_clean()
                updated.save()
                if updated.status == Appointment.Status.CONFIRMED:
                    notify_appointment_event(updated, 'confirmed')
                elif updated.status == Appointment.Status.CANCELLED:
                    notify_appointment_event(updated, 'cancelled')
                messages.success(request, 'Appointment updated.')
                return redirect('appointments:secretary_dashboard')
            except ValidationError as exc:
                form.add_error(None, exc)
    else:
        form = AppointmentActionForm(instance=appointment)

    return render(request, 'secretary_manage_appointment.html', {'form': form, 'appointment': appointment})


@login_required
def secretary_quick_action(request, appointment_id, action):
    """Quick approve/reject action from dashboard - secretary only."""
    if request.user.role != CustomUser.Role.SECRETARY or request.user.status != CustomUser.Status.APPROVED:
        messages.error(request, 'Only approved secretaries can perform this action.')
        return redirect('dashboard')

    appointment = get_object_or_404(
        Appointment,
        id=appointment_id,
        doctor__user_id=request.user.assigned_doctor_id,
        status=Appointment.Status.REQUESTED,
    )

    if action == 'approve':
        appointment.status = Appointment.Status.CONFIRMED
        appointment.save()
        notify_appointment_event(appointment, 'confirmed')
        messages.success(request, f'Appointment with {appointment.patient.name} confirmed!')
    elif action == 'reject':
        appointment.status = Appointment.Status.CANCELLED
        appointment.save()
        notify_appointment_event(appointment, 'cancelled')
        messages.success(request, f'Appointment with {appointment.patient.name} rejected.')
    else:
        messages.error(request, 'Invalid action.')

    return redirect('appointments:secretary_dashboard')


@login_required
def secretary_create_patient(request):
    """Only secretaries can create patient accounts."""
    if request.user.role != CustomUser.Role.SECRETARY or request.user.status != CustomUser.Status.APPROVED:
        messages.error(request, 'Only approved secretaries can create patient accounts.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = SecretaryCreatePatientForm(request.POST)
        if form.is_valid():
            patient = form.save()
            messages.success(request, f'Patient {patient.name} created successfully.')
            return redirect('appointments:secretary_dashboard')
    else:
        form = SecretaryCreatePatientForm()

    return render(request, 'secretary_create_patient.html', {'form': form})


@login_required
def secretary_set_working_hours(request):
    """Only secretaries can set working hours for their doctor."""
    if request.user.role != CustomUser.Role.SECRETARY or request.user.status != CustomUser.Status.APPROVED:
        messages.error(request, 'Only approved secretaries can set working hours.')
        return redirect('dashboard')

    doctor = get_object_or_404(Doctor, user_id=request.user.assigned_doctor_id)
    
    bulk_form = None
    individual_form = None
    
    if request.method == 'POST':
        # Check which form was submitted
        if 'bulk_submit' in request.POST:
            bulk_form = BulkDoctorWorkingHourForm(request.POST)
            individual_form = DoctorWorkingHourForm()
            if bulk_form.is_valid():
                count = bulk_form.save(doctor)
                messages.success(request, f'Working hours added for {count} day(s).')
                return redirect('appointments:secretary_working_hours')
        else:
            individual_form = DoctorWorkingHourForm(request.POST)
            bulk_form = BulkDoctorWorkingHourForm()
            if individual_form.is_valid():
                block = individual_form.save(commit=False)
                block.doctor = doctor
                block.full_clean()
                block.save()
                messages.success(request, 'Working hour added.')
                return redirect('appointments:secretary_working_hours')
    else:
        bulk_form = BulkDoctorWorkingHourForm()
        individual_form = DoctorWorkingHourForm()

    existing_hours = doctor.working_hours.all().order_by('weekday', 'start_time')
    return render(request, 'secretary_working_hours.html', {
        'bulk_form': bulk_form,
        'individual_form': individual_form,
        'doctor': doctor,
        'existing_hours': existing_hours,
    })


@login_required
def secretary_add_holiday(request):
    """Only secretaries can add holidays for their doctor."""
    if request.user.role != CustomUser.Role.SECRETARY or request.user.status != CustomUser.Status.APPROVED:
        messages.error(request, 'Only approved secretaries can manage holidays.')
        return redirect('dashboard')

    doctor = get_object_or_404(Doctor, user_id=request.user.assigned_doctor_id)
    if request.method == 'POST':
        form = DoctorHolidayForm(request.POST)
        if form.is_valid():
            holiday = form.save(commit=False)
            holiday.doctor = doctor
            holiday.full_clean()
            holiday.save()
            messages.success(request, 'Holiday saved.')
            return redirect('appointments:secretary_dashboard')
    else:
        form = DoctorHolidayForm()

    return render(request, 'secretary_holidays.html', {'form': form, 'doctor': doctor})


@login_required
def secretary_monthly_report(request):
    if not _ensure_role(request.user, CustomUser.Role.SECRETARY):
        messages.error(request, 'Only approved secretaries can download reports.')
        return redirect('dashboard')

    doctor = get_object_or_404(Doctor, user_id=request.user.assigned_doctor_id)
    month = int(request.GET.get('month', timezone.localdate().month))
    year = int(request.GET.get('year', timezone.localdate().year))
    last_day = monthrange(year, month)[1]

    start = timezone.make_aware(datetime(year, month, 1, 0, 0), timezone.get_current_timezone())
    end = timezone.make_aware(datetime(year, month, last_day, 23, 59), timezone.get_current_timezone())

    appointments = Appointment.objects.filter(doctor=doctor, date_time__range=(start, end)).select_related('patient')
    patients = Patient.objects.filter(appointments__in=appointments).distinct()

    lines = [
        f'Monthly report for Dr. {doctor.name}',
        f'Period: {year}-{month:02d}',
        f'Appointments: {appointments.count()}',
        f'Patients seen: {patients.count()}',
        '--- Appointments ---',
    ]
    for appt in appointments:
        lines.append(f'{appt.date_time:%Y-%m-%d %H:%M} - {appt.patient.name} - {appt.status}')

    response = HttpResponse(_simple_pdf(lines), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="report_{year}_{month:02d}.pdf"'
    return response


@login_required
def doctor_working_hours(request):
    """Only approved doctors can manage their working hours."""
    if request.user.role != CustomUser.Role.DOCTOR or request.user.status != CustomUser.Status.APPROVED:
        messages.error(request, 'Only approved doctors can manage working hours.')
        return redirect('dashboard')

    doctor = request.user.doctor_profile
    
    bulk_form = None
    individual_form = None
    
    if request.method == 'POST':
        # Check which form was submitted
        if 'bulk_submit' in request.POST:
            bulk_form = BulkDoctorWorkingHourForm(request.POST)
            individual_form = DoctorWorkingHourForm()
            if bulk_form.is_valid():
                count = bulk_form.save(doctor)
                messages.success(request, f'Working hours added for {count} day(s).')
                return redirect('appointments:doctor_working_hours')
        else:
            individual_form = DoctorWorkingHourForm(request.POST)
            bulk_form = BulkDoctorWorkingHourForm()
            if individual_form.is_valid():
                block = individual_form.save(commit=False)
                block.doctor = doctor
                block.full_clean()
                block.save()
                messages.success(request, 'Working hour added.')
                return redirect('appointments:doctor_working_hours')
    else:
        bulk_form = BulkDoctorWorkingHourForm()
        individual_form = DoctorWorkingHourForm()

    existing_hours = doctor.working_hours.all().order_by('weekday', 'start_time')
    return render(request, 'secretary_working_hours.html', {
        'bulk_form': bulk_form,
        'individual_form': individual_form,
        'doctor': doctor,
        'existing_hours': existing_hours,
    })


@login_required
def delete_working_hour(request, hour_id):
    """Delete a working hour entry - only doctor or secretary of that doctor."""
    working_hour = get_object_or_404(DoctorWorkingHour, id=hour_id)
    doctor = working_hour.doctor

    # Verify user is authorized (secretary of the doctor or the doctor themselves)
    user = request.user
    is_secretary = (user.role == CustomUser.Role.SECRETARY and 
                   user.status == CustomUser.Status.APPROVED and 
                   user.assigned_doctor_id == doctor.user_id)
    is_doctor = (user.role == CustomUser.Role.DOCTOR and 
                user.status == CustomUser.Status.APPROVED and 
                user.doctor_profile_id == doctor.id)

    if not (is_secretary or is_doctor):
        messages.error(request, 'You do not have permission to delete this working hour.')
        return redirect('dashboard')

    working_hour.delete()
    messages.success(request, 'Working hour deleted.')

    # Redirect back to the working hours page
    if is_secretary:
        return redirect('appointments:secretary_working_hours')
    else:
        return redirect('appointments:doctor_working_hours')


@login_required
def block_time_slot(request):
    """Only approved doctors can block time slots."""
    if request.user.role != CustomUser.Role.DOCTOR or request.user.status != CustomUser.Status.APPROVED:
        messages.error(request, 'Only approved doctors can block time slots.')
        return redirect('dashboard')

    doctor = request.user.doctor_profile
    if request.method == 'POST':
        form = DoctorHolidayForm(request.POST)
        if form.is_valid():
            holiday = form.save(commit=False)
            holiday.doctor = doctor
            holiday.full_clean()
            holiday.save()
            messages.success(request, 'Time slot blocked.')
            return redirect('appointments:doctor_agenda')
    else:
        form = DoctorHolidayForm()

    return render(request, 'secretary_holidays.html', {'form': form, 'doctor': doctor})
