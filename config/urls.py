from django.contrib import admin
from django.urls import include, path

from myapp import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('accounts/', include('myapp.folders.accounts.urls')),
    path('appointments/', include('myapp.folders.appointments.urls')),
    path('auth/', include('django.contrib.auth.urls')),
]