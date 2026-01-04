"""
Accounts Models - User & Authentication
Sistema customizado de usuários com vínculo obrigatório a empresa.
"""

from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone

from apps.core.models import TimeStampedModel, Company, Role


class UserManager(BaseUserManager):
    """Manager customizado para User model."""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('O email é obrigatório')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser precisa ter is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser precisa ter is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Usuário customizado com email como identificador principal.
    """
    username = None  # Remove username field
    email = models.EmailField('Email', unique=True)
    
    # Campos de perfil
    avatar = models.ImageField(
        'Avatar',
        upload_to='avatars/',
        blank=True,
        null=True
    )
    bio = models.TextField('Biografia', blank=True)
    
    # Dados pessoais
    birth_date = models.DateField('Data de Nascimento', null=True, blank=True)
    phone = models.CharField(
        'Telefone',
        max_length=20,
        blank=True,
        help_text='Formato: (00) 00000-0000'
    )
    
    # Dados de localização
    neighborhood = models.CharField('Bairro', max_length=100, blank=True)
    city = models.CharField('Cidade', max_length=100, blank=True)
    
    # Gamificação
    total_points = models.PositiveIntegerField('Pontos Totais', default=0)
    
    # Controle
    email_verified = models.BooleanField('Email Verificado', default=False)
    last_activity = models.DateTimeField('Última Atividade', null=True, blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    objects = UserManager()
    
    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
        ordering = ['first_name', 'last_name']
    
    def __str__(self):
        return self.get_full_name() or self.email
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self):
        return self.first_name
    
    def get_avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return '/static/images/default-avatar.png'
    
    def update_activity(self):
        """Atualiza timestamp de última atividade."""
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])
    
    def add_points(self, points):
        """Adiciona pontos de gamificação."""
        self.total_points += points
        self.save(update_fields=['total_points'])
    
    @property
    def is_birthday_today(self):
        """Verifica se hoje é o aniversário do usuário."""
        if not self.birth_date:
            return False
        today = timezone.now().date()
        return self.birth_date.month == today.month and self.birth_date.day == today.day
    
    @property
    def is_admin_master(self):
        """
        Verifica se o usuário é Admin Master (superuser).
        ACCESS: ADMIN MASTER
        """
        return self.is_superuser
    
    @property
    def is_gestor(self):
        """
        Verifica se o usuário é Gestor (via UserCompany role).
        ACCESS: GESTOR | ADMIN MASTER
        """
        if self.is_superuser:
            return True
        # Verifica se tem algum vínculo ativo com role de gestor
        return self.user_companies.filter(
            is_active=True,
            role__level__in=['gestor', 'admin_master']
        ).exists()
    
    @property
    def is_colaborador(self):
        """
        Verifica se o usuário é apenas Colaborador (sem permissões de gestão).
        ACCESS: COLABORADOR
        """
        if self.is_superuser:
            return False
        # Se não é gestor, é colaborador
        return not self.is_gestor
    
    def get_current_company_role(self):
        """
        Retorna o role do usuário na empresa atual (via middleware).
        Retorna None se não houver empresa atual.
        """
        user_company = self.user_companies.filter(is_active=True).first()
        if user_company and user_company.role:
            return user_company.role.level
        return 'colaborador'


class UserCompany(TimeStampedModel):
    """
    Vínculo Many-to-Many entre Usuário e Empresa.
    Um usuário pode pertencer a múltiplas empresas.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_companies',
        verbose_name='Usuário'
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='user_companies',
        verbose_name='Empresa'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_companies',
        verbose_name='Cargo'
    )
    
    # Controle
    is_active = models.BooleanField('Ativo', default=True)
    joined_at = models.DateTimeField('Data de Entrada', auto_now_add=True)
    deactivated_at = models.DateTimeField('Data de Desativação', null=True, blank=True)
    
    # Identificador interno na empresa
    employee_id = models.CharField(
        'Matrícula',
        max_length=50,
        blank=True,
        help_text='Identificador interno do colaborador'
    )
    
    class Meta:
        verbose_name = 'Vínculo Usuário-Empresa'
        verbose_name_plural = 'Vínculos Usuário-Empresa'
        unique_together = ['user', 'company']
        ordering = ['-is_active', 'user__first_name']
    
    def __str__(self):
        return f"{self.user.get_full_name()} @ {self.company.name}"
    
    def deactivate(self):
        """Desativa o vínculo do usuário com a empresa."""
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.save(update_fields=['is_active', 'deactivated_at'])
    
    @property
    def access_level(self):
        """Retorna o nível de acesso do usuário."""
        if self.role:
            return self.role.level
        return 'colaborador'
    
    @property
    def is_gestor(self):
        return self.access_level in ['admin_master', 'gestor']
    
    @property
    def is_admin_master(self):
        return self.access_level == 'admin_master'


class Warning(TimeStampedModel):
    """
    Advertência disciplinar aplicada a um colaborador.
    ACCESS: ADMIN MASTER | GESTOR
    """
    WARNING_TYPE_CHOICES = [
        ('oral', 'Advertência Oral'),
        ('escrita', 'Advertência Escrita'),
        ('suspensao', 'Suspensão'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='warnings_received',
        verbose_name='Colaborador'
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='warnings',
        verbose_name='Empresa'
    )
    issuer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='warnings_issued',
        verbose_name='Aplicado por'
    )
    warning_type = models.CharField(
        'Tipo de Advertência',
        max_length=20,
        choices=WARNING_TYPE_CHOICES,
        default='oral'
    )
    reason = models.TextField('Motivo', help_text='Descrição detalhada do motivo da advertência')
    
    class Meta:
        verbose_name = 'Advertência'
        verbose_name_plural = 'Advertências'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_warning_type_display()} - {self.user.get_full_name()} ({self.created_at.strftime('%d/%m/%Y')})"
    
    def get_warning_type_display_class(self):
        """Retorna classe CSS baseada no tipo de advertência."""
        classes = {
            'oral': 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50',
            'escrita': 'bg-orange-500/20 text-orange-400 border-orange-500/50',
            'suspensao': 'bg-red-500/20 text-red-400 border-red-500/50',
        }
        return classes.get(self.warning_type, 'bg-gray-500/20 text-gray-400 border-gray-500/50')
