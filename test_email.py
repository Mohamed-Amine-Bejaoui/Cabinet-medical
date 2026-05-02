#!/usr/bin/env python
"""Quick test script to verify email notifications work."""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(__file__))

django.setup()

from django.core.mail import send_mail
from django.conf import settings

print("=" * 60)
print("EMAIL NOTIFICATION TEST")
print("=" * 60)
print(f"Backend: {settings.EMAIL_BACKEND}")
print(f"Host: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
print(f"From: {settings.DEFAULT_FROM_EMAIL}")
print("=" * 60)

# Test sending email
try:
    result = send_mail(
        'Test from Medical Cabinet',
        'Email notifications are working!',
        settings.DEFAULT_FROM_EMAIL,
        ['forviait@gmail.com'],
    )
    
    if result == 1:
        print("✅ SUCCESS: Test email sent to forviait@gmail.com")
        print("\nYour email system is ready!")
        print("\nYou can now:")
        print("1. Approve a doctor in admin - email sent to doctor & secretary")
        print("2. Confirm an appointment - email sent to patient & doctor")
        print("3. Cancel an appointment - email sent to all parties")
    else:
        print("❌ Failed: Email was not sent")
        
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nTroubleshooting:")
    print("- Check Gmail credentials in .env")
    print("- Ensure 2-factor auth is disabled or use App Password")
    print("- Check firewall/proxy settings")

print("=" * 60)
