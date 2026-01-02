from django.apps import AppConfig


class TrainingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.trainings'
    verbose_name = 'Treinamentos'
    
    def ready(self):
        import apps.trainings.signals  # noqa

