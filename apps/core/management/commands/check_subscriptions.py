"""
Management Command: Verificação Automática de Assinaturas

Este comando deve ser executado diariamente via Cron Job para:
- Enviar alertas preventivos (T+7 dias)
- Marcar assinaturas como vencidas (T+0)
- Suspender empresas inadimplentes (T-3 dias após vencimento)

Uso:
    python manage.py check_subscriptions
"""

from typing import List, Dict
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Q
from datetime import timedelta, date

from apps.core.models import Company
from apps.accounts.services import send_subscription_reminder_email, send_subscription_expired_email


class Command(BaseCommand):
    help = 'Verifica status de assinaturas e envia notificações'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa sem fazer alterações (apenas mostra o que faria)',
        )

    def handle(self, *args, **options):
        """Executa a verificação de assinaturas."""
        dry_run = options.get('dry_run', False)
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('🔍 Verificação de Assinaturas'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        
        today = date.today()
        seven_days_from_now = today + timedelta(days=7)
        three_days_ago = today - timedelta(days=3)
        
        # Buscar empresas ativas (não canceladas)
        companies = Company.objects.filter(
            ~Q(subscription_status='canceled'),
            is_active=True
        ).exclude(
            next_billing_date__isnull=True
        ).order_by('next_billing_date')
        
        stats = {
            'alerts_sent': 0,
            'expired_updated': 0,
            'suspended_updated': 0,
            'errors': 0,
        }
        
        for company in companies:
            try:
                if not company.next_billing_date:
                    continue
                
                days_until = company.days_until_expiration()
                
                # ============================================================
                # T+7: ALERTA PREVENTIVO (7 dias antes do vencimento)
                # ============================================================
                if days_until == 7 and company.subscription_status in ['trial', 'active']:
                    self.stdout.write(
                        self.style.WARNING(
                            f'📧 T+7: Enviando alerta preventivo para {company.name} '
                            f'(vence em {days_until} dias)'
                        )
                    )
                    
                    if not dry_run:
                        try:
                            send_subscription_reminder_email(company, days_until)
                            stats['alerts_sent'] += 1
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(
                                    f'  ❌ Erro ao enviar e-mail: {str(e)}'
                                )
                            )
                            stats['errors'] += 1
                    else:
                        self.stdout.write(f'  [DRY-RUN] Enviaria e-mail de alerta')
                
                # ============================================================
                # T+0: VENCIMENTO (marca como past_due)
                # ============================================================
                elif days_until == 0 and company.subscription_status in ['trial', 'active']:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠️ T+0: Assinatura de {company.name} venceu hoje!'
                        )
                    )
                    
                    if not dry_run:
                        company.subscription_status = 'past_due'
                        company.save()
                        
                        # Limpar cache de status
                        cache_key = f'company_subscription_status_{company.id}'
                        cache.delete(cache_key)
                        
                        # Enviar e-mail de vencimento
                        try:
                            send_subscription_expired_email(company)
                            stats['alerts_sent'] += 1
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(
                                    f'  ❌ Erro ao enviar e-mail: {str(e)}'
                                )
                            )
                            stats['errors'] += 1
                        
                        stats['expired_updated'] += 1
                    else:
                        self.stdout.write(f'  [DRY-RUN] Mudaria status para past_due')
                
                # ============================================================
                # T-3: SUSPENSÃO (3 dias após vencimento)
                # ============================================================
                elif days_until == -3 and company.subscription_status == 'past_due':
                    self.stdout.write(
                        self.style.ERROR(
                            f'🚫 T-3: Suspendo {company.name} (vencido há 3 dias)'
                        )
                    )
                    
                    if not dry_run:
                        company.subscription_status = 'suspended'
                        company.save()
                        
                        # Limpar cache de status
                        cache_key = f'company_subscription_status_{company.id}'
                        cache.delete(cache_key)
                        
                        stats['suspended_updated'] += 1
                        
                        # TODO: Implementar encerramento de sessões ativas
                        # Pode usar django-user-sessions ou similar
                    else:
                        self.stdout.write(f'  [DRY-RUN] Mudaria status para suspended')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ Erro ao processar {company.name}: {str(e)}'
                    )
                )
                stats['errors'] += 1
        
        # ============================================================
        # RESUMO FINAL
        # ============================================================
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('📊 RESUMO'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f'✅ Alertas enviados: {stats["alerts_sent"]}')
        self.stdout.write(f'⚠️ Assinaturas expiradas: {stats["expired_updated"]}')
        self.stdout.write(f'🚫 Empresas suspensas: {stats["suspended_updated"]}')
        self.stdout.write(f'❌ Erros: {stats["errors"]}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️ MODO DRY-RUN: Nenhuma alteração foi feita'))
        
        self.stdout.write(self.style.SUCCESS('=' * 80))

