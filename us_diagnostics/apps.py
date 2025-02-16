from django.apps import AppConfig


class UsDiagnosticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'us_diagnostics'

    def ready(self):
        import us_diagnostics.tasks
