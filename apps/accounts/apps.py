import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = 'Contas de Usuário'
    
    def ready(self):
        """Registra os signals quando o app está pronto."""
        try:
            import apps.accounts.signals  # noqa
            logger.info('✅ Signals do app accounts carregados com sucesso')
        except Exception as e:
            logger.error(f'❌ Erro ao carregar signals do app accounts: {str(e)}')
            raise

