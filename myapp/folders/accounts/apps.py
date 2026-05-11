from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp.folders.accounts'
    label = 'accounts'

    def ready(self):
        import myapp.folders.accounts.signals  # noqa: F401 — register signal handlers
