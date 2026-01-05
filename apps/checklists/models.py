"""
Checklists Models - Checklists com frequência configurável.
Sistema de tarefas recorrentes com period_key para controle de execução.
"""

from django.db import models
from django.conf import settings

from apps.core.models import CompanyBaseModel, TimeStampedModel
from apps.core.utils import PeriodKeyHelper


class Checklist(CompanyBaseModel):
    """
    Checklist - Lista de tarefas com frequência configurável.
    """
    FREQUENCY_CHOICES = [
        ('daily', 'Diário'),
        ('weekly', 'Semanal'),
        ('biweekly', 'Quinzenal'),
        ('monthly', 'Mensal'),
    ]
    
    title = models.CharField('Título', max_length=255)
    description = models.TextField('Descrição', blank=True)
    
    # Frequência
    frequency = models.CharField(
        'Frequência',
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='daily'
    )
    
    # Controle
    is_active = models.BooleanField('Ativo', default=True)
    order = models.PositiveIntegerField('Ordem', default=0)
    
    # Gamificação
    points_per_completion = models.PositiveIntegerField(
        'Pontos por Conclusão',
        default=10,
        help_text='Pontos ganhos ao completar todas as tarefas'
    )
    
    # Atribuição individual
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='assigned_checklists',
        blank=True,
        verbose_name='Usuários Atribuídos',
        help_text='Selecione os colaboradores que devem executar este checklist. Deixe vazio para tornar global (todos os colaboradores da empresa).'
    )
    
    class Meta:
        verbose_name = 'Checklist'
        verbose_name_plural = 'Checklists'
        ordering = ['order', 'title']
    
    def __str__(self):
        return f'{self.title} ({self.get_frequency_display()})'
    
    @property
    def total_tasks(self):
        return self.tasks.filter(is_active=True).count()
    
    def get_current_period_key(self):
        """
        Gera a period_key para o período atual baseado na frequência.
        Usa o helper centralizado PeriodKeyHelper.
        """
        return PeriodKeyHelper.get_period_key(self.frequency)
    
    def get_user_completion(self, user, period_key=None):
        """
        Retorna o progresso do usuário no checklist para o período.
        """
        if period_key is None:
            period_key = self.get_current_period_key()
        
        total = self.total_tasks
        if total == 0:
            return 100
        
        completed = TaskDone.objects.filter(
            task__checklist=self,
            user=user,
            period_key=period_key
        ).count()
        
        return round((completed / total) * 100, 1)
    
    def is_completed_by(self, user, period_key=None):
        """Verifica se usuário completou o checklist no período."""
        return self.get_user_completion(user, period_key) == 100
    
    def get_period_display(self):
        """
        Retorna descrição legível do período atual.
        Usa o helper centralizado PeriodKeyHelper.
        """
        return PeriodKeyHelper.get_period_display(self.frequency)
    
    def get_previous_period_key(self):
        """Retorna a period_key do período anterior."""
        return PeriodKeyHelper.get_previous_period_key(self.frequency)
    
    def get_previous_completion_status(self, user):
        """
        Verifica se o checklist foi concluído no período anterior.
        
        Returns:
            dict com 'completed' (bool) e 'period_key' (str)
        """
        prev_period_key = self.get_previous_period_key()
        
        completed = ChecklistCompletion.objects.filter(
            checklist=self,
            user=user,
            period_key=prev_period_key
        ).exists()
        
        return {
            'completed': completed,
            'period_key': prev_period_key,
        }
    
    def is_overdue_for_user(self, user):
        """
        Verifica se o checklist possui tarefas obrigatórias pendentes de períodos passados.
        
        IMPORTANTE: Um checklist nunca deve ser marcado como "Atrasado" se já foi finalizado.
        
        Returns:
            bool: True se há tarefas obrigatórias não concluídas no período anterior
        """
        # Se o checklist já foi completado no período atual, não está atrasado
        period_key = self.get_current_period_key()
        if self.is_completed_by(user, period_key):
            return False
        
        prev_period_key = self.get_previous_period_key()
        
        required_tasks = self.tasks.filter(is_active=True, is_required=True)
        if not required_tasks.exists():
            return False
        
        completed_required_tasks = TaskDone.objects.filter(
            task__in=required_tasks,
            user=user,
            period_key=prev_period_key
        ).values_list('task_id', flat=True)
        
        total_required = required_tasks.count()
        completed_count = len(completed_required_tasks)
        
        return completed_count < total_required


class Task(TimeStampedModel):
    """
    Tarefa individual dentro de um checklist.
    """
    checklist = models.ForeignKey(
        Checklist,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name='Checklist'
    )
    
    title = models.CharField('Título', max_length=255)
    description = models.TextField('Descrição', blank=True)
    
    # Controle
    is_active = models.BooleanField('Ativo', default=True)
    order = models.PositiveIntegerField('Ordem', default=0)
    is_required = models.BooleanField(
        'Obrigatório',
        default=True,
        help_text='Tarefa obrigatória para conclusão do checklist'
    )
    
    class Meta:
        verbose_name = 'Tarefa'
        verbose_name_plural = 'Tarefas'
        ordering = ['checklist', 'order']
    
    def __str__(self):
        return self.title
    
    def is_done_by(self, user, period_key=None):
        """Verifica se a tarefa foi concluída pelo usuário no período."""
        if period_key is None:
            period_key = self.checklist.get_current_period_key()
        
        return TaskDone.objects.filter(
            task=self,
            user=user,
            period_key=period_key
        ).exists()


class TaskDone(TimeStampedModel):
    """
    Registro de tarefa concluída.
    Usa period_key para identificar o período de execução.
    """
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='completions',
        verbose_name='Tarefa'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='task_completions',
        verbose_name='Usuário'
    )
    
    # Chave do período (formato depende da frequência do checklist)
    period_key = models.CharField(
        'Chave do Período',
        max_length=20,
        help_text='Identificador único do período (YYYY-MM-DD, YYYY-Www, YYYY-MM)'
    )
    
    # Observação opcional
    notes = models.TextField('Observações', blank=True)
    
    # Data/hora real de conclusão
    completed_at = models.DateTimeField('Concluído em', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Tarefa Concluída'
        verbose_name_plural = 'Tarefas Concluídas'
        unique_together = ['task', 'user', 'period_key']
        ordering = ['-completed_at']
    
    def __str__(self):
        return f'{self.user} - {self.task.title} ({self.period_key})'
    
    def save(self, *args, **kwargs):
        # Garante que period_key está definido
        if not self.period_key:
            self.period_key = self.task.checklist.get_current_period_key()
        
        super().save(*args, **kwargs)
        
        # Verifica se completou o checklist
        self._check_checklist_completion()
    
    def _check_checklist_completion(self):
        """Verifica e registra conclusão do checklist."""
        checklist = self.task.checklist
        
        if checklist.is_completed_by(self.user, self.period_key):
            # Registra conclusão do checklist
            ChecklistCompletion.objects.get_or_create(
                checklist=checklist,
                user=self.user,
                period_key=self.period_key,
                defaults={'points_earned': checklist.points_per_completion}
            )
            
            # Adiciona pontos ao usuário
            self.user.add_points(checklist.points_per_completion)


class ChecklistCompletion(TimeStampedModel):
    """
    Registro de checklist completamente concluído em um período.
    """
    checklist = models.ForeignKey(
        Checklist,
        on_delete=models.CASCADE,
        related_name='completions',
        verbose_name='Checklist'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='checklist_completions',
        verbose_name='Usuário'
    )
    period_key = models.CharField('Chave do Período', max_length=20)
    
    points_earned = models.PositiveIntegerField('Pontos Ganhos', default=0)
    completed_at = models.DateTimeField('Concluído em', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Checklist Concluído'
        verbose_name_plural = 'Checklists Concluídos'
        unique_together = ['checklist', 'user', 'period_key']
    
    def __str__(self):
        return f'{self.user} - {self.checklist.title} ({self.period_key})'


class ChecklistAlert(CompanyBaseModel):
    """
    Alerta de checklist com tarefa pendente.
    Cada tarefa pendente gera um alerta separado.
    Criado quando colaborador finaliza checklist com tarefas obrigatórias em falta.
    """
    checklist = models.ForeignKey(
        Checklist,
        on_delete=models.CASCADE,
        related_name='alerts',
        verbose_name='Checklist'
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='alerts',
        verbose_name='Tarefa Pendente',
        help_text='Tarefa obrigatória que não foi concluída'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='checklist_alerts',
        verbose_name='Usuário'
    )
    
    period_key = models.CharField(
        'Chave do Período',
        max_length=20,
        help_text='Período em que o alerta foi criado'
    )
    
    is_resolved = models.BooleanField(
        'Resolvido',
        default=False,
        help_text='Marcado como resolvido pelo gestor'
    )
    
    resolved_at = models.DateTimeField(
        'Resolvido em',
        null=True,
        blank=True
    )
    
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_alerts',
        verbose_name='Resolvido por'
    )
    
    class Meta:
        verbose_name = 'Alerta de Checklist'
        verbose_name_plural = 'Alertas de Checklists'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'is_resolved', '-created_at']),
        ]
        unique_together = ['checklist', 'task', 'user', 'period_key', 'is_resolved']
    
    def __str__(self):
        status = 'Resolvido' if self.is_resolved else 'Pendente'
        return f'{self.user.get_full_name()} - {self.checklist.title} ({status})'