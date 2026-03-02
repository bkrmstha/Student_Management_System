from django.apps import AppConfig


class CoursesConfig(AppConfig):
    name = 'courses'

    def ready(self):
        # Import signals to ensure post-save handlers are connected
        try:
            import courses.signals  # noqa: F401
        except Exception:
            # If signals fail to import, don't crash the app startup
            pass
