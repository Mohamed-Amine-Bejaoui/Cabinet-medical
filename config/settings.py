from pathlib import Path
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # loads the .env file

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') or 'django-insecure-dev-key-change-in-production'
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# ─── Security ────────────────────────────────────────────────────────────────

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']


# ─── Apps ─────────────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'myapp.folders.accounts',
    'myapp.folders.appointments',
]


# ─── Custom user model (MUST be set before first migration) ───────────────────

AUTH_USER_MODEL = 'accounts.CustomUser'


# ─── Auth redirects ───────────────────────────────────────────────────────────

LOGIN_URL          = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'


# ─── Middleware ───────────────────────────────────────────────────────────────

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ─── URLs ─────────────────────────────────────────────────────────────────────

ROOT_URLCONF = 'config.urls'


# ─── Templates ────────────────────────────────────────────────────────────────

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'myapp' / 'folders' / 'templates'],
        'APP_DIRS': True,   # also finds app-level templates/ folders
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.csrf',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# ─── WSGI ─────────────────────────────────────────────────────────────────────

WSGI_APPLICATION = 'config.wsgi.application'


# ─── Database ─────────────────────────────────────────────────────────────────

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'medical_cabinet.sqlite3',
    }
}


# ─── Password validation ──────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    # Intentionally left permissive: no password strength validation.
]


# ─── Internationalisation ─────────────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Africa/Tunis'  # your local timezone — avoids naive datetime bugs
USE_I18N      = True
USE_TZ        = True


# ─── Static files ─────────────────────────────────────────────────────────────

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'myapp' / 'folders' / 'static']

# ─── Email Configuration ──────────────────────────────────────────────────────

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_USER', 'forviait@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_PASS', 'qsxdghywcorrrwkl')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


# ─── Default primary key ──────────────────────────────────────────────────────

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ─── CSRF Configuration ───────────────────────────────────────────────────────

CSRF_COOKIE_SECURE = False  # Set to True only in production with HTTPS
CSRF_COOKIE_HTTPONLY = False  # Must be False so template tag can access it
CSRF_COOKIE_SAMESITE = 'Lax'  # Allows forms to work on localhost
CSRF_TRUSTED_ORIGINS = ['http://127.0.0.1:8000', 'http://localhost:8000']
CSRF_FAILURE_VIEW = 'myapp.folders.accounts.views.csrf_failure_view'  # Custom error page for debugging


# ─── Session Configuration ────────────────────────────────────────────────────

SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 86400 * 7  # 7 days
SESSION_EXPIRE_AT_BROWSER_CLOSE = False