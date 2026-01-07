"""
Signals para Accounts App
Automation de onboarding e notificações
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

from .models import UserCompany, User
from .services import send_onboarding_email

logger = logging.getLogger(__name__)


@receiver(post_save, sender=UserCompany)
def send_onboarding_email_signal(sender, instance, created, **kwargs):
    """
    Signal que dispara e-mail de onboarding quando um novo UserCompany é criado.
    A senha temporária deve ser armazenada temporariamente durante a criação.
    """
    logger.debug(
        f'Signal post_save disparado para UserCompany ID {instance.id}: '
        f'created={created}, is_active={instance.is_active}'
    )
    
    if created and instance.is_active:
        try:
            user = instance.user
            company = instance.company
            
            # Verificar se o usuário foi recém-criado (criado há menos de 10 segundos)
            from django.utils import timezone
            from datetime import timedelta
            
            user_recently_created = (
                user.date_joined and 
                (timezone.now() - user.date_joined) < timedelta(seconds=10)
            )
            
            # Tenta obter a senha temporária do UserCompany primeiro, depois do User
            password = None
            if hasattr(instance, '_temp_password'):
                password = instance._temp_password
            elif hasattr(user, '_temp_password'):
                password = user._temp_password
            
            # Se não houver senha temporária E o usuário foi recém-criado, logar e não enviar
            if not password:
                if user_recently_created:
                    logger.warning(
                        f'Usuário {user.email} recém-criado vinculado a {company.name} '
                        f'sem senha temporária disponível. E-mail de onboarding não enviado.'
                    )
                else:
                    logger.info(
                        f'Usuário {user.email} vinculado a {company.name} sem senha temporária '
                        f'(usuário já existente). E-mail de onboarding não enviado.'
                    )
                return
            
            # Enviar e-mail de onboarding
            logger.info(f'Iniciando envio de e-mail de onboarding para {user.email}')
            try:
                import threading
                thread = threading.Thread(
                    target=send_onboarding_email,
                    args=(user, company, password),
                    daemon=True
                )
                thread.start()
                logger.info(f'E-mail de onboarding agendado (thread) para {user.email}')
            except Exception as e:
                logger.error(f'Erro ao agendar envio de e-mail: {str(e)}')
                # Tentar enviar de forma síncrona como fallback
                logger.info(f'Tentando envio síncrono de e-mail para {user.email}')
                result = send_onboarding_email(user, company, password)
                if result:
                    logger.info(f'E-mail enviado com sucesso (síncrono) para {user.email}')
                else:
                    logger.error(f'Falha no envio de e-mail (síncrono) para {user.email}')
                
        except Exception as e:
            import traceback
            logger.error(
                f'Erro no signal de onboarding para UserCompany {instance.id}: {str(e)}\n'
                f'Traceback: {traceback.format_exc()}'
            )

