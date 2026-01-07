"""
Comando Django para testar envio de e-mail
Uso: python manage.py test_email
"""
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
import sys


class Command(BaseCommand):
    help = 'Testa a configuração SMTP enviando um e-mail de teste'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            type=str,
            help='E-mail de destino (opcional, será solicitado se não fornecido)',
        )

    def handle(self, *args, **options):
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('🧪 TESTE DE CONFIGURAÇÃO SMTP'))
        self.stdout.write('='*80)
        
        # Verificar configurações
        self.stdout.write('\n📋 Configurações SMTP:')
        self.stdout.write(f'  EMAIL_BACKEND: {settings.EMAIL_BACKEND}')
        self.stdout.write(f'  EMAIL_HOST: {settings.EMAIL_HOST}')
        self.stdout.write(f'  EMAIL_PORT: {settings.EMAIL_PORT}')
        self.stdout.write(f'  EMAIL_USE_TLS: {getattr(settings, "EMAIL_USE_TLS", "N/A")}')
        self.stdout.write(f'  EMAIL_USE_SSL: {getattr(settings, "EMAIL_USE_SSL", "N/A")}')
        self.stdout.write(f'  EMAIL_HOST_USER: {settings.EMAIL_HOST_USER or "(não configurado)"}')
        password_display = "*" * len(settings.EMAIL_HOST_PASSWORD) if settings.EMAIL_HOST_PASSWORD else "(não configurado)"
        self.stdout.write(f'  EMAIL_HOST_PASSWORD: {password_display}')
        self.stdout.write(f'  DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}')
        
        # Verificar se está configurado
        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            self.stdout.write(self.style.WARNING(
                '\n⚠️  AVISO: EMAIL_HOST_USER ou EMAIL_HOST_PASSWORD não configurados!'
            ))
            self.stdout.write('   Configure essas variáveis no arquivo .env ou no ambiente.')
            return
        
        # Obter e-mail de destino
        recipient = options.get('to')
        if not recipient:
            recipient = input('\n📧 Digite o e-mail de destino para o teste: ').strip()
        
        if not recipient:
            self.stdout.write(self.style.ERROR('❌ E-mail não fornecido. Teste cancelado.'))
            return
        
        self.stdout.write(f'\n🚀 Tentando enviar e-mail de teste para: {recipient}')
        self.stdout.write('   Aguarde...\n')
        
        try:
            # Tentar enviar e-mail
            send_mail(
                subject='Teste de E-mail - Mindpulse',
                message='Este é um e-mail de teste do sistema Mindpulse. Se você recebeu isso, o SMTP está funcionando!',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                html_message='<p>Este é um <strong>e-mail de teste</strong> do sistema Mindpulse.</p><p>Se você recebeu isso, o SMTP está funcionando! 🎉</p>',
                fail_silently=False,
            )
            
            self.stdout.write(self.style.SUCCESS('\n' + '='*80))
            self.stdout.write(self.style.SUCCESS('✅ SUCESSO! E-mail enviado com sucesso!'))
            self.stdout.write(self.style.SUCCESS('='*80))
            self.stdout.write(f'\n📬 Verifique a caixa de entrada (e spam) de: {recipient}')
            
        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)
            
            self.stdout.write(self.style.ERROR('\n' + '='*80))
            self.stdout.write(self.style.ERROR('❌ ERRO AO ENVIAR E-MAIL'))
            self.stdout.write(self.style.ERROR('='*80))
            self.stdout.write(f'\nTipo de Erro: {error_type}')
            self.stdout.write(self.style.ERROR(f'Mensagem: {error_message}'))
            
            # Dicas específicas
            if 'authentication' in error_message.lower() or 'auth' in error_message.lower():
                self.stdout.write(self.style.WARNING('\n💡 ERRO DE AUTENTICAÇÃO:'))
                self.stdout.write('   1. Verifique se EMAIL_HOST_USER está correto')
                self.stdout.write('   2. Verifique se EMAIL_HOST_PASSWORD está correto')
                self.stdout.write('   3. Se usar Gmail:')
                self.stdout.write('      → Ative 2FA na sua conta Google')
                self.stdout.write('      → Gere uma "Senha de App" em: https://myaccount.google.com/apppasswords')
                self.stdout.write('      → Use essa senha (não a senha normal)')
                self.stdout.write('   4. Verifique se DEFAULT_FROM_EMAIL usa o mesmo domínio do EMAIL_HOST_USER')
                
            elif 'connection' in error_message.lower() or 'timeout' in error_message.lower():
                self.stdout.write(self.style.WARNING('\n💡 ERRO DE CONEXÃO:'))
                self.stdout.write('   1. Verifique se EMAIL_HOST está correto')
                self.stdout.write('   2. Verifique se EMAIL_PORT está correto (587 para TLS, 465 para SSL)')
                self.stdout.write('   3. Verifique se EMAIL_USE_TLS ou EMAIL_USE_SSL está correto')
                
            self.stdout.write('\n' + '='*80)

