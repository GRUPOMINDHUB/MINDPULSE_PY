"""
Trainings Models - Treinamentos, Vídeos e Progresso
Sistema de treinamentos com gamificação e recompensas.
"""

from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.utils.text import slugify

from apps.core.models import CompanyBaseModel, TimeStampedModel


def training_cover_path(instance, filename):
    """Gera path para capa do treinamento."""
    return f'trainings/{instance.company.slug}/covers/{filename}'


def video_file_path(instance, filename):
    """Gera path para arquivo de vídeo no GCS."""
    return f'trainings/{instance.training.company.slug}/videos/{instance.training.id}/{filename}'


class Training(CompanyBaseModel):
    """
    Treinamento - Conjunto de vídeos para capacitação.
    """
    title = models.CharField('Título', max_length=255)
    slug = models.SlugField('Slug', max_length=100)
    description = models.TextField('Descrição', blank=True)
    objective = models.TextField(
        'Objetivo',
        blank=True,
        help_text='O que o colaborador aprenderá com este treinamento'
    )
    
    # Mídia
    cover_image = models.ImageField(
        'Imagem de Capa',
        upload_to=training_cover_path,
        blank=True,
        null=True
    )
    
    # Gamificação
    reward_points = models.PositiveIntegerField(
        'Pontos de Recompensa',
        default=100,
        help_text='Pontos ganhos ao completar o treinamento'
    )
    reward_badge = models.CharField(
        'Badge/Medalha',
        max_length=100,
        blank=True,
        help_text='Nome do badge conquistado'
    )
    
    # Controle
    is_active = models.BooleanField('Ativo', default=True)
    is_mandatory = models.BooleanField(
        'Obrigatório',
        default=False,
        help_text='Treinamento obrigatório para todos os colaboradores'
    )
    order = models.PositiveIntegerField('Ordem', default=0)
    
    # Atribuição individual
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='assigned_trainings',
        blank=True,
        verbose_name='Usuários Atribuídos',
        help_text='Selecione os colaboradores que devem ter acesso a este treinamento. Deixe vazio para tornar global (todos os colaboradores da empresa).'
    )
    
    # Datas
    available_from = models.DateField('Disponível a partir de', null=True, blank=True)
    available_until = models.DateField('Disponível até', null=True, blank=True)
    
    class Meta:
        verbose_name = 'Treinamento'
        verbose_name_plural = 'Treinamentos'
        ordering = ['order', 'title']
        unique_together = ['company', 'slug']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        """
        Gera slug automaticamente a partir do título.
        - Se slug não existe: gera automaticamente
        - Garante unicidade dentro da empresa
        """
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            
            # Garante unicidade dentro da empresa
            while Training.objects.filter(company=self.company, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = slug
        super().save(*args, **kwargs)
    
    @property
    def total_videos(self):
        return self.videos.count()
    
    @property
    def total_duration_seconds(self):
        """Duração total em segundos."""
        return self.videos.aggregate(
            total=models.Sum('duration_seconds')
        )['total'] or 0
    
    @property
    def total_duration_formatted(self):
        """Duração formatada em HH:MM:SS."""
        total = self.total_duration_seconds
        hours = total // 3600
        minutes = (total % 3600) // 60
        seconds = total % 60
        
        if hours > 0:
            return f'{hours:02d}:{minutes:02d}:{seconds:02d}'
        return f'{minutes:02d}:{seconds:02d}'
    
    def get_user_progress(self, user):
        """
        Retorna progresso do usuário neste treinamento.
        Considera vídeos assistidos E quizzes aprovados.
        """
        total_videos = self.videos.filter(is_active=True).count()
        total_quizzes = self.quizzes.filter(is_active=True).count()
        total_items = total_videos + total_quizzes
        
        if total_items == 0:
            return 0
        
        # Vídeos completados
        completed_videos = UserProgress.objects.filter(
            user=user,
            video__training=self,
            video__is_active=True,
            completed=True
        ).count()
        
        # Quizzes aprovados
        completed_quizzes = 0
        for quiz in self.quizzes.filter(is_active=True):
            if quiz.is_passed_by(user):
                completed_quizzes += 1
        
        completed_items = completed_videos + completed_quizzes
        
        return round((completed_items / total_items) * 100, 1)
    
    def is_completed_by(self, user):
        """
        Verifica se usuário completou o treinamento.
        Requer: todos os vídeos assistidos E todos os quizzes aprovados.
        """
        # Verifica vídeos
        total_videos = self.videos.filter(is_active=True).count()
        completed_videos = UserProgress.objects.filter(
            user=user,
            video__training=self,
            video__is_active=True,
            completed=True
        ).count()
        
        if total_videos > 0 and completed_videos < total_videos:
            return False
        
        # Verifica quizzes
        for quiz in self.quizzes.filter(is_active=True):
            if not quiz.is_passed_by(user):
                return False
        
        return True


class Video(TimeStampedModel):
    """
    Vídeo de treinamento - Armazenado no GCS.
    """
    training = models.ForeignKey(
        Training,
        on_delete=models.CASCADE,
        related_name='videos',
        verbose_name='Treinamento'
    )
    
    title = models.CharField('Título', max_length=255)
    description = models.TextField('Descrição', blank=True)
    
    # Arquivo de vídeo
    video_file = models.FileField(
        'Arquivo de Vídeo',
        upload_to=video_file_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['mp4', 'webm', 'mov']
            )
        ],
        help_text='Formatos aceitos: MP4, WebM, MOV'
    )
    
    # Thumbnail (opcional - pode ser gerado automaticamente)
    thumbnail = models.ImageField(
        'Thumbnail',
        upload_to='trainings/thumbnails/',
        blank=True,
        null=True
    )
    
    # Metadados
    duration_seconds = models.PositiveIntegerField(
        'Duração (segundos)',
        default=0,
        help_text='Duração do vídeo em segundos'
    )
    order = models.PositiveIntegerField('Ordem', default=0)
    
    # Controle
    is_active = models.BooleanField('Ativo', default=True)
    
    class Meta:
        verbose_name = 'Vídeo'
        verbose_name_plural = 'Vídeos'
        ordering = ['training', 'order']
    
    def __str__(self):
        return f'{self.training.title} - {self.title}'
    
    @property
    def duration_formatted(self):
        """Duração formatada em MM:SS."""
        minutes = self.duration_seconds // 60
        seconds = self.duration_seconds % 60
        return f'{minutes:02d}:{seconds:02d}'
    
    def is_watched_by(self, user):
        """Verifica se usuário assistiu o vídeo."""
        return UserProgress.objects.filter(
            user=user,
            video=self,
            completed=True
        ).exists()


class UserProgress(TimeStampedModel):
    """
    Progresso do usuário em vídeos de treinamento.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='training_progress',
        verbose_name='Usuário'
    )
    video = models.ForeignKey(
        Video,
        on_delete=models.CASCADE,
        related_name='user_progress',
        verbose_name='Vídeo'
    )
    
    # Progresso
    watched_seconds = models.PositiveIntegerField(
        'Segundos Assistidos',
        default=0
    )
    completed = models.BooleanField('Concluído', default=False)
    completed_at = models.DateTimeField('Concluído em', null=True, blank=True)
    
    # Controle de visualização
    last_position = models.PositiveIntegerField(
        'Última Posição',
        default=0,
        help_text='Posição em segundos onde o usuário parou'
    )
    watch_count = models.PositiveIntegerField(
        'Vezes Assistido',
        default=0
    )
    
    class Meta:
        verbose_name = 'Progresso de Usuário'
        verbose_name_plural = 'Progressos de Usuários'
        unique_together = ['user', 'video']
    
    def __str__(self):
        status = '✓' if self.completed else f'{self.progress_percentage}%'
        return f'{self.user} - {self.video.title} ({status})'
    
    @property
    def progress_percentage(self):
        """Porcentagem de progresso no vídeo."""
        if self.video.duration_seconds == 0:
            return 0
        return min(100, round((self.watched_seconds / self.video.duration_seconds) * 100, 1))
    
    def mark_completed(self):
        """Marca o vídeo como concluído."""
        from django.utils import timezone
        
        if not self.completed:
            self.completed = True
            self.completed_at = timezone.now()
            self.watched_seconds = self.video.duration_seconds
            self.watch_count += 1
            self.save()
            
            # Verifica se completou o treinamento
            self._check_training_completion()
    
    def _check_training_completion(self):
        """Verifica e registra conclusão do treinamento."""
        training = self.video.training
        
        if training.is_completed_by(self.user):
            # Cria recompensa se ainda não existe
            UserTrainingReward.objects.get_or_create(
                user=self.user,
                training=training,
                defaults={
                    'points_earned': training.reward_points,
                    'badge_earned': training.reward_badge,
                }
            )
            
            # Adiciona pontos ao usuário
            self.user.add_points(training.reward_points)


class UserTrainingReward(TimeStampedModel):
    """
    Recompensa conquistada ao completar um treinamento.
    Sistema de gamificação.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='training_rewards',
        verbose_name='Usuário'
    )
    training = models.ForeignKey(
        Training,
        on_delete=models.CASCADE,
        related_name='user_rewards',
        verbose_name='Treinamento'
    )
    
    # Recompensa
    points_earned = models.PositiveIntegerField('Pontos Ganhos', default=0)
    badge_earned = models.CharField('Badge Conquistado', max_length=100, blank=True)
    
    # Data
    earned_at = models.DateTimeField('Conquistado em', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Recompensa de Treinamento'
        verbose_name_plural = 'Recompensas de Treinamentos'
        unique_together = ['user', 'training']
    
    def __str__(self):
        return f'{self.user} - {self.training.title} ({self.points_earned} pts)'


class Quiz(TimeStampedModel):
    """
    Quiz de treinamento - Avaliação com perguntas de múltipla escolha.
    """
    training = models.ForeignKey(
        Training,
        on_delete=models.CASCADE,
        related_name='quizzes',
        verbose_name='Treinamento'
    )
    
    title = models.CharField('Título', max_length=255)
    description = models.TextField('Descrição', blank=True)
    order = models.PositiveIntegerField('Ordem', default=0)
    is_active = models.BooleanField('Ativo', default=True)
    
    # Configurações
    passing_score = models.PositiveIntegerField(
        'Nota Mínima para Aprovação',
        default=70,
        help_text='Nota mínima (0-100) para aprovação no quiz'
    )
    allow_multiple_attempts = models.BooleanField(
        'Permitir Múltiplas Tentativas',
        default=True,
        help_text='Permite que o colaborador refaça o quiz caso não seja aprovado'
    )
    
    class Meta:
        verbose_name = 'Quiz'
        verbose_name_plural = 'Quizzes'
        ordering = ['training', 'order']
    
    def __str__(self):
        return f'{self.training.title} - {self.title}'
    
    @property
    def total_questions(self):
        """Retorna o total de perguntas do quiz."""
        return self.questions.count()
    
    def is_passed_by(self, user):
        """Verifica se o usuário foi aprovado no quiz."""
        best_attempt = UserQuizAttempt.objects.filter(
            user=user,
            quiz=self
        ).order_by('-score').first()
        
        if not best_attempt:
            return False
        
        return best_attempt.score >= self.passing_score
    
    def get_best_score(self, user):
        """Retorna a melhor nota do usuário neste quiz."""
        best_attempt = UserQuizAttempt.objects.filter(
            user=user,
            quiz=self
        ).order_by('-score').first()
        
        return best_attempt.score if best_attempt else None


class Question(TimeStampedModel):
    """
    Pergunta do quiz.
    """
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='Quiz'
    )
    
    text = models.TextField('Texto da Pergunta')
    order = models.PositiveIntegerField('Ordem', default=0)
    
    class Meta:
        verbose_name = 'Pergunta'
        verbose_name_plural = 'Perguntas'
        ordering = ['quiz', 'order']
    
    def __str__(self):
        return f'{self.quiz.title} - {self.text[:50]}...'
    
    @property
    def correct_choice(self):
        """Retorna a escolha correta desta pergunta."""
        return self.choices.filter(is_correct=True).first()
    
    @property
    def total_choices(self):
        """Retorna o total de opções desta pergunta."""
        return self.choices.count()


class Choice(TimeStampedModel):
    """
    Opção de resposta de uma pergunta.
    """
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='choices',
        verbose_name='Pergunta'
    )
    
    text = models.CharField('Texto da Opção', max_length=500)
    is_correct = models.BooleanField('Resposta Correta', default=False)
    order = models.PositiveIntegerField('Ordem', default=0)
    
    class Meta:
        verbose_name = 'Opção'
        verbose_name_plural = 'Opções'
        ordering = ['question', 'order']
    
    def __str__(self):
        status = '✓' if self.is_correct else '○'
        return f'{status} {self.text[:50]}...'


class UserQuizAttempt(TimeStampedModel):
    """
    Tentativa do usuário em um quiz.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
        verbose_name='Usuário'
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts',
        verbose_name='Quiz'
    )
    
    # Resultado
    score = models.PositiveIntegerField(
        'Nota',
        default=0,
        help_text='Nota de 0 a 100'
    )
    total_questions = models.PositiveIntegerField('Total de Perguntas', default=0)
    correct_answers = models.PositiveIntegerField('Respostas Corretas', default=0)
    
    # Respostas selecionadas (JSON)
    answers = models.JSONField(
        'Respostas',
        default=dict,
        help_text='Dicionário com question_id: choice_id das respostas'
    )
    
    # Controle
    completed_at = models.DateTimeField('Concluído em', auto_now_add=True)
    is_passed = models.BooleanField('Aprovado', default=False)
    
    class Meta:
        verbose_name = 'Tentativa de Quiz'
        verbose_name_plural = 'Tentativas de Quizzes'
        ordering = ['-completed_at']
    
    def __str__(self):
        status = 'Aprovado' if self.is_passed else 'Reprovado'
        return f'{self.user} - {self.quiz.title} ({self.score}% - {status})'
    
    def calculate_score(self):
        """Calcula a nota baseada nas respostas."""
        # Força refresh do quiz para pegar dados atualizados
        self.quiz.refresh_from_db()
        
        # Busca todas as perguntas do quiz (força nova query)
        questions = list(self.quiz.questions.all().prefetch_related('choices'))
        total = len(questions)
        
        if total == 0:
            self.correct_answers = 0
            self.total_questions = 0
            self.score = 0
            self.is_passed = False
            self.save()
            return 0
        
        correct = 0
        for question in questions:
            # Tenta pegar a resposta como string ou int
            selected_choice_id = self.answers.get(str(question.id)) or self.answers.get(question.id)
            
            if selected_choice_id:
                # Converte para int se necessário
                try:
                    selected_choice_id = int(selected_choice_id)
                except (ValueError, TypeError):
                    pass
                
                # Busca a escolha correta
                try:
                    choice = Choice.objects.get(id=selected_choice_id, question=question)
                    if choice.is_correct:
                        correct += 1
                except Choice.DoesNotExist:
                    # Se a escolha não existe, pode ter sido deletada ou alterada
                    pass
        
        self.correct_answers = correct
        self.total_questions = total
        self.score = round((correct / total) * 100) if total > 0 else 0
        self.is_passed = self.score >= self.quiz.passing_score
        self.save()
        
        return self.score
