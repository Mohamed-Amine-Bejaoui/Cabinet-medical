from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

def home(request):
    return render(request, 'home.html')

@login_required
def dashboard(request):
    role = request.user.role
    if role == 'doctor':
        return redirect('appointments:doctor_agenda')
    elif role == 'secretary':
        return redirect('appointments:secretary_dashboard')
    else:
        return redirect('appointments:patient_dashboard')