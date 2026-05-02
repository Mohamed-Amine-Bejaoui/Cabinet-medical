from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from myapp.folders.utils import is_admin
from .forms import DoctorProfileForm, PatientProfileForm, SignupForm, UserProfileForm
from .models import CustomUser, Doctor, Patient

User = get_user_model()


def logout_view(request):
    auth_logout(request)
    messages.success(request, 'Logged out successfully.')
    return redirect('home')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, 'Enter username and password.')
            return render(request, 'accounts/login.html')

        user = authenticate(request, username=username, password=password)
        if not user:
            messages.error(request, 'Invalid username or password.')
            return render(request, 'accounts/login.html')

        # Admins bypass approval checks entirely
        if is_admin(user):
            auth_login(request, user)
            messages.success(request, f'Welcome {user.username}!')
            return redirect('accounts:admin_panel')

        # Regular users must be approved
        if user.status != CustomUser.Status.APPROVED:
            status_msg = {
                CustomUser.Status.PENDING: 'Account pending approval.',
                CustomUser.Status.BLOCKED: 'Account is blocked.',
            }
            messages.error(request, status_msg.get(user.status, 'Account inactive.'))
            return render(request, 'accounts/login.html')

        auth_login(request, user)
        messages.success(request, f'Welcome {user.username}!')
        return redirect('dashboard')

    return render(request, 'accounts/login.html')


@login_required
def admin_panel(request):
    if not is_admin(request.user):
        messages.error(request, 'Admin access only.')
        return redirect('dashboard')

    pending_doctors = CustomUser.objects.filter(
        role=CustomUser.Role.DOCTOR,
        status=CustomUser.Status.PENDING
    ).select_related('doctor_profile')

    approved_doctors = CustomUser.objects.filter(
        role=CustomUser.Role.DOCTOR,
        status=CustomUser.Status.APPROVED
    ).select_related('doctor_profile')

    blocked_doctors = CustomUser.objects.filter(
        role=CustomUser.Role.DOCTOR,
        status=CustomUser.Status.BLOCKED
    ).select_related('doctor_profile')

    return render(request, 'accounts/admin_panel.html', {
        'pending_doctors': pending_doctors,
        'approved_doctors': approved_doctors,
        'blocked_doctors': blocked_doctors,
    })


@login_required
def edit_profile(request):
    user = request.user

    # Admin/staff edit their basic user info
    if user.is_superuser or user.is_staff:
        if request.method == 'POST':
            form = UserProfileForm(request.POST, instance=user)
            if form.is_valid():
                form.save()
                messages.success(request, 'Profile updated successfully.')
                return redirect('accounts:admin_panel')
        else:
            form = UserProfileForm(instance=user)
        return render(request, 'accounts/edit_profile.html', {'form': form, 'role': 'admin'})

    if user.status != CustomUser.Status.APPROVED:
        messages.error(request, 'Your account is pending approval.')
        return redirect('dashboard')

    if user.is_doctor:
        try:
            doctor = user.doctor_profile
        except Doctor.DoesNotExist:
            doctor = Doctor.objects.create(
                user=user,
                name=user.get_full_name() or user.username,
                specialty='General Medicine'
            )
        if request.method == 'POST':
            form = DoctorProfileForm(request.POST, instance=doctor)
            if form.is_valid():
                form.save()
                messages.success(request, 'Profile updated successfully.')
                return redirect('appointments:doctor_agenda')
        else:
            form = DoctorProfileForm(instance=doctor)
        return render(request, 'accounts/edit_profile.html', {'form': form, 'role': 'doctor'})

    elif user.is_patient:
        patient = get_object_or_404(Patient, user=user)
        if request.method == 'POST':
            form = PatientProfileForm(request.POST, instance=patient)
            if form.is_valid():
                form.save()
                messages.success(request, 'Profile updated successfully.')
                return redirect('appointments:patient_dashboard')
        else:
            form = PatientProfileForm(instance=patient)
        return render(request, 'accounts/edit_profile.html', {'form': form, 'role': 'patient'})

    messages.error(request, 'Only patients and doctors can edit their profile.')
    return redirect('dashboard')


@login_required
def check_status(request):
    user = request.user

    # Admins and approved users don't need this page
    if is_admin(user) or user.status == CustomUser.Status.APPROVED:
        return redirect('dashboard')

    return render(request, 'accounts/check_status.html', {
        'username': user.username,
        'email': user.email,
        'role': user.get_role_display(),
        'status': user.get_status_display(),
        'is_approved': user.status == CustomUser.Status.APPROVED,
    })


@login_required
def approve_doctor(request, doctor_id):
    if not is_admin(request.user):
        messages.error(request, 'Admin access only.')
        return redirect('dashboard')

    doctor_user = get_object_or_404(CustomUser, id=doctor_id, role=CustomUser.Role.DOCTOR)
    doctor_user.status = CustomUser.Status.APPROVED
    doctor_user.save()
    messages.success(request, f'Doctor {doctor_user.username} has been approved.')
    return redirect('accounts:admin_panel')


@login_required
def block_doctor(request, doctor_id):
    if not is_admin(request.user):
        messages.error(request, 'Admin access only.')
        return redirect('dashboard')

    doctor_user = get_object_or_404(CustomUser, id=doctor_id, role=CustomUser.Role.DOCTOR)
    doctor_user.status = CustomUser.Status.BLOCKED
    doctor_user.save()
    messages.success(request, f'Doctor {doctor_user.username} has been blocked.')
    return redirect('accounts:admin_panel')


@login_required
def delete_doctor(request, doctor_id):
    if not is_admin(request.user):
        messages.error(request, 'Admin access only.')
        return redirect('dashboard')

    doctor_user = get_object_or_404(CustomUser, id=doctor_id, role=CustomUser.Role.DOCTOR)
    username = doctor_user.username

    for secretary in doctor_user.assigned_secretaries.all():
        if secretary.assigned_doctors.count() == 1:
            secretary.delete()

    doctor_user.delete()
    messages.success(request, f'Doctor {username} and their exclusive secretaries have been deleted.')
    return redirect('accounts:admin_panel')


def signup(request):
    if request.user.is_authenticated:
        messages.info(request, 'You are already signed in.')
        return redirect('home')

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            if user.role == CustomUser.Role.DOCTOR:
                messages.success(request, 'Doctor account created. Please wait for admin approval.')
            else:
                messages.success(request, 'Account created successfully. You can now log in.')
            return redirect('accounts:login')
    else:
        form = SignupForm()
    return render(request, 'accounts/signup.html', {'form': form})


@login_required
def auto_approve_patient(request):
    user = request.user

    if user.role != CustomUser.Role.PATIENT:
        messages.error(request, 'Only patients can use this action.')
        return redirect('dashboard')

    if user.status == CustomUser.Status.APPROVED:
        messages.info(request, 'Your account is already approved!')
    else:
        user.status = CustomUser.Status.APPROVED
        user.save()
        messages.success(request, 'Your account has been approved!')

    return redirect('appointments:doctor_list')


def csrf_failure_view(request, reason=""):
    return render(request, 'csrf_error.html', {
        'reason': reason,
        'debug': True
    }, status=403)