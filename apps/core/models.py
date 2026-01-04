"""
Core Models - Company & Role Management (Multi-tenant Base)
"""

from django.db import models
from django.utils import timezone


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
    """
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
    max_users = models.PositiveIntegerField(
        'Limite de Usuários',
        default=50,
        help_text='Número máximo de colaboradores'
    )
    
    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def active_users_count(self):
        return self.user_companies.filter(is_active=True).count()


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

