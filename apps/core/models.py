"""
Core Models - Company & Role Management (Multi-tenant Base)
"""

from typing import Optional
from django.db import models
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta, date


class TimeStampedModel(models.Model):
    """Abstract base model with created/updated timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class Company(TimeStampedModel):
    """
    Empresa/Organização - Base do sistema multi-tenant.
    Todos os dados são filtrados por company_id.
    
    Sistema de Assinatura:
    - Gerencia ciclo de vida da assinatura (trial, active, past_due, suspended, canceled)
    - Controla datas de vencimento e períodos de carência
    - Define limites de uso baseado no plano contratado
    """
    # Informações Básicas
    name = models.CharField('Nome da Empresa', max_length=255)
    slug = models.SlugField('Slug', max_length=100, unique=True)
    logo = models.ImageField(
        'Logo',
        upload_to='companies/logos/',
        blank=True,
        null=True
    )
    primary_color = models.CharField(
        'Cor Primária',
        max_length=7,
        default='#ff6a00',
        help_text='Cor em formato hexadecimal'
    )
    is_active = models.BooleanField('Ativa', default=True)
    
    # Gestão de Assinatura
    SUBSCRIPTION_STATUS_CHOICES = [
        ('trial', 'Período de Teste'),
        ('active', 'Ativa'),
        ('past_due', 'Pagamento Atrasado'),
        ('suspended', 'Suspensa'),
        ('canceled', 'Cancelada'),
    ]
    
    PLAN_TYPE_CHOICES = [
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('diamond', 'Diamond'),
    ]
    
    subscription_status = models.CharField(
        'Status da Assinatura',
        max_length=20,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        default='trial',
        help_text='Status atual da assinatura da empresa'
    )
    
    plan_type = models.CharField(
        'Tipo de Plano',
        max_length=20,
        choices=PLAN_TYPE_CHOICES,
        default='bronze',
        help_text='Plano contratado (Bronze, Silver, Gold, Diamond)'
    )
    
    # Controle de Datas
    trial_ends_at = models.DateField(
        'Fim do Período de Teste',
        null=True,
        blank=True,
        help_text='Data de término do período de teste (se aplicável)'
    )
    
    next_billing_date = models.DateField(
        'Próxima Data de Cobrança',
        null=True,
        blank=True,
        help_text='Data prevista para a próxima cobrança'
    )
    
    last_payment_date = models.DateField(
        'Última Data de Pagamento',
        null=True,
        blank=True,
        help_text='Data do último pagamento confirmado'
    )
    
    # Limites do Plano
    max_users_limit = models.PositiveIntegerField(
        'Limite Máximo de Usuários',
        default=10,
        help_text='Número máximo de colaboradores permitidos no plano'
    )
    
    # Legacy field (mantido para compatibilidade)
    max_users = models.PositiveIntegerField(
        'Limite de Usuários',
        default=50,
        help_text='[DEPRECATED] Use max_users_limit. Mantido para compatibilidade.'
    )
    
    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'
        ordering = ['name']
        indexes = [
            models.Index(fields=['subscription_status']),
            models.Index(fields=['next_billing_date']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def active_users_count(self) -> int:
        """Retorna o número de usuários ativos da empresa."""
        return self.user_companies.filter(is_active=True).count()
    
    def days_until_expiration(self) -> Optional[int]:
        """
        Calcula quantos dias faltam até o vencimento da assinatura.
        
        Returns:
            int: Dias até o vencimento (positivo = ainda não venceu, negativo = já venceu)
            None: Se não houver data de vencimento definida
        """
        if not self.next_billing_date:
            return None
        
        today = date.today()
        delta = self.next_billing_date - today
        return delta.days
    
    def is_within_grace_period(self) -> bool:
        """
        Verifica se a empresa está no período de carência (3 dias após vencimento).
        
        O período de carência permite que a empresa continue usando o sistema
        por até 3 dias após o vencimento antes do bloqueio.
        
        Returns:
            bool: True se estiver em carência (vencido há menos de 3 dias)
        """
        if not self.next_billing_date:
            # Se não tem data, considera como não vencido
            return False
        
        if self.subscription_status == 'suspended':
            return False
        
        days_until = self.days_until_expiration()
        if days_until is None:
            return False
        
        # Está em carência se venceu há 3 dias ou menos
        return -3 <= days_until < 0
    
    def should_be_suspended(self) -> bool:
        """
        Determina se a empresa deve ser suspensa.
        
        Critérios de suspensão:
        - Status é 'past_due'
        - Vencimento há mais de 3 dias (fora do período de carência)
        - Não é superuser/admin
        
        Returns:
            bool: True se deve ser suspensa
        """
        if self.subscription_status == 'canceled':
            return True
        
        if self.subscription_status == 'suspended':
            return True
        
        if self.subscription_status != 'past_due':
            return False
        
        days_until = self.days_until_expiration()
        if days_until is None:
            # Sem data de vencimento, não suspende
            return False
        
        # Suspende se venceu há mais de 3 dias
        return days_until < -3
    
    def is_subscription_active(self) -> bool:
        """
        Verifica se a assinatura está ativa e permite acesso.
        
        Returns:
            bool: True se a assinatura está ativa ou em período válido
        """
        # Status ativos
        if self.subscription_status in ['trial', 'active']:
            return True
        
        # Em carência ainda permite acesso
        if self.is_within_grace_period():
            return True
        
        # Demais status bloqueiam
        return False
    
    def get_subscription_display_info(self) -> dict:
        """
        Retorna informações formatadas sobre a assinatura para exibição.
        
        Returns:
            dict: Dicionário com informações da assinatura formatadas
        """
        days_until = self.days_until_expiration()
        
        return {
            'status': self.get_subscription_status_display(),
            'status_code': self.subscription_status,
            'plan': self.get_plan_type_display(),
            'days_until_expiration': days_until,
            'next_billing_date': self.next_billing_date.strftime('%d/%m/%Y') if self.next_billing_date else 'Não definida',
            'is_active': self.is_subscription_active(),
            'is_in_grace_period': self.is_within_grace_period(),
            'should_be_suspended': self.should_be_suspended(),
        }
    
    def save(self, *args, **kwargs):
        """Override save para manter max_users sincronizado com max_users_limit."""
        # Sincroniza max_users (legacy) com max_users_limit
        if self.max_users_limit and self.max_users != self.max_users_limit:
            self.max_users = self.max_users_limit
        
        super().save(*args, **kwargs)
        
        # Limpa cache de status da assinatura ao salvar
        cache_key = f'company_subscription_status_{self.id}'
        cache.delete(cache_key)


class Role(TimeStampedModel):
    """
    Papel/Função dentro de uma empresa.
    Ex: Vendedor, Supervisor, Atendente
    """
    LEVEL_CHOICES = [
        ('admin_master', 'Admin Master'),
        ('gestor', 'Gestor'),
        ('colaborador', 'Colaborador'),
    ]
    
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='roles',
        verbose_name='Empresa'
    )
    name = models.CharField('Nome do Cargo', max_length=100)
    level = models.CharField(
        'Nível de Acesso',
        max_length=20,
        choices=LEVEL_CHOICES,
        default='colaborador'
    )
    description = models.TextField('Descrição', blank=True)
    
    class Meta:
        verbose_name = 'Cargo'
        verbose_name_plural = 'Cargos'
        ordering = ['company', 'name']
        unique_together = ['company', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.company.name})"


class CompanyQuerySet(models.QuerySet):
    """QuerySet customizado para filtragem por empresa."""
    
    def for_company(self, company):
        """Filtra registros pela empresa."""
        return self.filter(company=company)


class CompanyManager(models.Manager):
    """Manager customizado para models multi-tenant."""
    
    def get_queryset(self):
        return CompanyQuerySet(self.model, using=self._db)
    
    def for_company(self, company):
        return self.get_queryset().for_company(company)


class CompanyBaseModel(TimeStampedModel):
    """
    Abstract base model para todos os models que pertencem a uma empresa.
    Implementa a filtragem multi-tenant via company_id.
    """
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='%(class)ss',
        verbose_name='Empresa'
    )
    
    objects = CompanyManager()
    
    class Meta:
        abstract = True

