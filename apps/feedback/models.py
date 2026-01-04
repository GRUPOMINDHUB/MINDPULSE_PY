"""
Feedback Models - Sistema de feedback com sentimentos gamificados.
"""

from django.db import models
from django.conf import settings

from apps.core.models import CompanyBaseModel, TimeStampedModel


class FeedbackTicket(CompanyBaseModel):
    """
    Ticket de feedback enviado por colaborador.
    Inclui sentimento gamificado e categorização.
    """
    SENTIMENT_CHOICES = [
        ('great', '😊 Ótimo'),
        ('good', '🙂 Bom'),
        ('neutral', '😐 Neutro'),
        ('bad', '😕 Ruim'),
        ('sad', '😢 Triste'),
    ]
    
    CATEGORY_CHOICES = [
        ('suggestion', 'Sugestão'),
        ('complaint', 'Reclamação'),
        ('question', 'Dúvida'),
        ('praise', 'Elogio'),
        ('other', 'Outro'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('in_progress', 'Em Andamento'),
        ('resolved', 'Resolvido'),
        ('closed', 'Fechado'),
    ]
    
    # Autor
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='feedback_tickets',
        verbose_name='Usuário'
    )
    
    # Conteúdo
    sentiment = models.CharField(
        'Sentimento',
        max_length=20,
        choices=SENTIMENT_CHOICES,
        default='neutral'
    )
    category = models.CharField(
        'Categoria',
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='other'
    )
    subject = models.CharField('Assunto', max_length=255)
    message = models.TextField('Mensagem')
    
    # Anexo opcional
    attachment = models.FileField(
        'Anexo',
        upload_to='feedback/attachments/',
        blank=True,
        null=True
    )
    
    # Status
    status = models.CharField(
        'Status',
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Resposta do gestor
    response = models.TextField('Resposta', blank=True)
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='feedback_responses',
        verbose_name='Respondido por'
    )
    responded_at = models.DateTimeField('Respondido em', null=True, blank=True)
    
    # Privacidade
    is_anonymous = models.BooleanField(
        'Anônimo',
        default=False,
        help_text='Se marcado, a identidade do autor não será revelada aos gestores'
    )
    
    class Meta:
        verbose_name = 'Ticket de Feedback'
        verbose_name_plural = 'Tickets de Feedback'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.get_sentiment_display()} - {self.subject}'
    
    @property
    def sentiment_emoji(self):
        """Retorna apenas o emoji do sentimento."""
        emojis = {
            'great': '😊',
            'good': '🙂',
            'neutral': '😐',
            'bad': '😕',
            'sad': '😢',
        }
        return emojis.get(self.sentiment, '😐')
    
    @property
    def is_resolved(self):
        return self.status in ['resolved', 'closed']
    
    def mark_resolved(self, user, response=''):
        """Marca o ticket como resolvido."""
        from django.utils import timezone
        
        self.status = 'resolved'
        self.response = response
        self.responded_by = user
        self.responded_at = timezone.now()
        self.save()


class FeedbackComment(TimeStampedModel):
    """
    Comentário em um ticket de feedback (thread de conversa).
    """
    ticket = models.ForeignKey(
        FeedbackTicket,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Ticket'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='feedback_comments',
        verbose_name='Usuário'
    )
    message = models.TextField('Mensagem')
    
    # Indica se é resposta do gestor
    is_staff_reply = models.BooleanField('Resposta da Equipe', default=False)
    
    class Meta:
        verbose_name = 'Comentário de Feedback'
        verbose_name_plural = 'Comentários de Feedback'
        ordering = ['created_at']
    
    def __str__(self):
        return f'Comentário de {self.user} em {self.ticket}'

