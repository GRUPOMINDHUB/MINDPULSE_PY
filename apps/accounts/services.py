"""
Serviços de E-mail - Onboarding e Recuperação de Senha
"""
import logging
from django.conf import settings
from django.core.mail import send_mail, mail_admins
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.urls import reverse

logger = logging.getLogger(__name__)


def send_onboarding_email(user, company, password):
    """
    Envia e-mail de boas-vindas ao novo colaborador com suas credenciais.
    
    Args:
        user: Instância do User
        company: Instância da Company
        password: Senha temporária gerada
    """
    try:
        # URL base da aplicação
        login_url = settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'http://localhost:8000'
        if not login_url.endswith('/'):
            login_url += '/'
        
        # Contexto para o template
        context = {
            'user': user,
            'company': company,
            'password': password,
            'login_url': login_url + 'accounts/login/',
            'user_full_name': user.get_full_name() or user.email,
        }
        
        # Renderizar HTML
        html_message = render_to_string('accounts/emails/onboarding.html', context)
        plain_message = strip_tags(html_message)
        
        # Assunto
        subject = f'Bem-vindo(a) à {company.name} - Mindpulse'
        
        # Em modo de desenvolvimento, se não houver configuração SMTP, usar console
        if settings.DEBUG and not hasattr(settings, 'EMAIL_HOST_USER') or not settings.EMAIL_HOST_USER:
            logger.warning(
                f'[MODO DESENVOLVIMENTO] E-mail de onboarding NÃO ENVIADO (SMTP não configurado)\n'
                f'Para: {user.email}\n'
                f'Assunto: {subject}\n'
                f'Credenciais:\n'
                f'  Email: {user.email}\n'
                f'  Senha: {password}\n'
                f'  Empresa: {company.name}\n'
                f'  Login: {login_url}accounts/login/\n'
            )
            # Em desenvolvimento, também printar no console
            print('\n' + '='*80)
            print('📧 E-MAIL DE ONBOARDING (MODO DESENVOLVIMENTO)')
            print('='*80)
            print(f'Para: {user.email}')
            print(f'Assunto: {subject}')
            print(f'\nCredenciais de Acesso:')
            print(f'  📧 Email: {user.email}')
            print(f'  🔑 Senha: {password}')
            print(f'  🏢 Empresa: {company.name}')
            print(f'  🔗 Login: {login_url}accounts/login/')
            print('='*80 + '\n')
            return True
        
        # Log das configurações SMTP (sem mostrar senha)
        logger.info(
            f'Tentando enviar e-mail de onboarding:\n'
            f'  SMTP Host: {settings.EMAIL_HOST}\n'
            f'  SMTP Port: {settings.EMAIL_PORT}\n'
            f'  Use TLS: {getattr(settings, "EMAIL_USE_TLS", False)}\n'
            f'  Use SSL: {getattr(settings, "EMAIL_USE_SSL", False)}\n'
            f'  From: {settings.DEFAULT_FROM_EMAIL}\n'
            f'  To: {user.email}\n'
            f'  Subject: {subject}'
        )
        
        # Enviar e-mail com tratamento de erros detalhado
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,  # Importante: False para ver erros
            )
            
            logger.info(f'✅ E-mail de onboarding enviado com sucesso para {user.email}')
            return True
            
        except Exception as smtp_error:
            # Captura erros específicos do SMTP
            error_type = type(smtp_error).__name__
            error_message = str(smtp_error)
            
            logger.error(
                f'❌ Erro SMTP ao enviar e-mail de onboarding:\n'
                f'  Tipo: {error_type}\n'
                f'  Mensagem: {error_message}\n'
                f'  Para: {user.email}'
            )
            
            # Dicas específicas baseadas no tipo de erro
            if 'authentication' in error_message.lower() or 'auth' in error_message.lower():
                logger.error(
                    '💡 DICA: Erro de autenticação. Verifique:\n'
                    '  1. EMAIL_HOST_USER e EMAIL_HOST_PASSWORD estão corretos\n'
                    '  2. Se usar Gmail, gere uma "Senha de App" (não use a senha normal)\n'
                    '  3. Verifique se 2FA está ativado no Gmail\n'
                    '  4. DEFAULT_FROM_EMAIL deve usar o mesmo domínio do EMAIL_HOST_USER'
                )
            elif 'connection' in error_message.lower() or 'timeout' in error_message.lower():
                logger.error(
                    '💡 DICA: Erro de conexão. Verifique:\n'
                    '  1. EMAIL_HOST e EMAIL_PORT estão corretos\n'
                    '  2. Firewall/proxy não está bloqueando a conexão\n'
                    '  3. Porta 587 (TLS) ou 465 (SSL) está acessível'
                )
            
            raise  # Re-raise para manter o erro visível
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(
            f'❌ Erro ao enviar e-mail de onboarding para {user.email}:\n'
            f'Erro: {str(e)}\n'
            f'Traceback: {error_details}'
        )
        
        # Em desenvolvimento, mostrar erro no console também
        if settings.DEBUG:
            print('\n' + '='*80)
            print('❌ ERRO AO ENVIAR E-MAIL DE ONBOARDING')
            print('='*80)
            print(f'Para: {user.email}')
            print(f'Erro: {str(e)}')
            print(f'\nCredenciais (para acesso manual):')
            print(f'  Email: {user.email}')
            print(f'  Senha: {password}')
            print('='*80 + '\n')
        
        return False


def send_password_reset_email(user, reset_url, token):
    """
    Envia e-mail de recuperação de senha.
    
    Args:
        user: Instância do User
        reset_url: URL completa para reset de senha
        token: Token de segurança (não usado diretamente, mas disponível se necessário)
    """
    try:
        # Contexto para o template
        context = {
            'user': user,
            'reset_url': reset_url,
            'user_full_name': user.get_full_name() or user.email,
        }
        
        # Renderizar HTML
        html_message = render_to_string('accounts/emails/password_reset.html', context)
        plain_message = strip_tags(html_message)
        
        # Assunto
        subject = 'Recuperação de Senha - Mindpulse'
        
        # Em modo de desenvolvimento, se não houver configuração SMTP, usar console
        if settings.DEBUG and (not hasattr(settings, 'EMAIL_HOST_USER') or not settings.EMAIL_HOST_USER):
            logger.warning(
                f'[MODO DESENVOLVIMENTO] E-mail de recuperação NÃO ENVIADO (SMTP não configurado)\n'
                f'Para: {user.email}\n'
                f'Assunto: {subject}\n'
                f'Link de Reset: {reset_url}\n'
            )
            print('\n' + '='*80)
            print('📧 E-MAIL DE RECUPERAÇÃO DE SENHA (MODO DESENVOLVIMENTO)')
            print('='*80)
            print(f'Para: {user.email}')
            print(f'Assunto: {subject}')
            print(f'\n🔗 Link de Reset:')
            print(f'   {reset_url}')
            print('='*80 + '\n')
            return True
        
        # Log das configurações SMTP (sem mostrar senha)
        logger.info(
            f'Tentando enviar e-mail de recuperação:\n'
            f'  SMTP Host: {settings.EMAIL_HOST}\n'
            f'  SMTP Port: {settings.EMAIL_PORT}\n'
            f'  Use TLS: {getattr(settings, "EMAIL_USE_TLS", False)}\n'
            f'  Use SSL: {getattr(settings, "EMAIL_USE_SSL", False)}\n'
            f'  From: {settings.DEFAULT_FROM_EMAIL}\n'
            f'  To: {user.email}'
        )
        
        # Enviar e-mail com tratamento de erros detalhado
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,  # Importante: False para ver erros
            )
            
            logger.info(f'✅ E-mail de recuperação de senha enviado com sucesso para {user.email}')
            return True
            
        except Exception as smtp_error:
            # Captura erros específicos do SMTP
            error_type = type(smtp_error).__name__
            error_message = str(smtp_error)
            
            logger.error(
                f'❌ Erro SMTP ao enviar e-mail de recuperação:\n'
                f'  Tipo: {error_type}\n'
                f'  Mensagem: {error_message}\n'
                f'  Para: {user.email}'
            )
            
            # Dicas específicas baseadas no tipo de erro
            if 'authentication' in error_message.lower() or 'auth' in error_message.lower():
                logger.error(
                    '💡 DICA: Erro de autenticação. Verifique:\n'
                    '  1. EMAIL_HOST_USER e EMAIL_HOST_PASSWORD estão corretos\n'
                    '  2. Se usar Gmail, gere uma "Senha de App" (não use a senha normal)\n'
                    '  3. Verifique se 2FA está ativado no Gmail\n'
                    '  4. DEFAULT_FROM_EMAIL deve usar o mesmo domínio do EMAIL_HOST_USER'
                )
            elif 'connection' in error_message.lower() or 'timeout' in error_message.lower():
                logger.error(
                    '💡 DICA: Erro de conexão. Verifique:\n'
                    '  1. EMAIL_HOST e EMAIL_PORT estão corretos\n'
                    '  2. Firewall/proxy não está bloqueando a conexão\n'
                    '  3. Porta 587 (TLS) ou 465 (SSL) está acessível'
                )
            
            raise  # Re-raise para manter o erro visível
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(
            f'❌ Erro ao enviar e-mail de recuperação para {user.email}:\n'
            f'Erro: {str(e)}\n'
            f'Traceback: {error_details}'
        )
        
        # Em desenvolvimento, mostrar erro no console também
        if settings.DEBUG:
            print('\n' + '='*80)
            print('❌ ERRO AO ENVIAR E-MAIL DE RECUPERAÇÃO')
            print('='*80)
            print(f'Para: {user.email}')
            print(f'Erro: {str(e)}')
            print(f'\nLink de Reset (para acesso manual):')
            print(f'  {reset_url}')
            print('='*80 + '\n')
        
        return False

