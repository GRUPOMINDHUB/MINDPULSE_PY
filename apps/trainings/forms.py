"""
Forms para gestão de treinamentos.
"""

from django import forms
from django.forms import inlineformset_factory
from .models import Training, Video, Quiz, Question, Choice
from apps.core.models import Company
from apps.accounts.models import UserCompany
from django.contrib.auth import get_user_model

User = get_user_model()


# Widgets reutilizáveis para consistência
TRAINING_WIDGETS = {
    'title': forms.TextInput(attrs={'class': 'form-input'}),
    'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
    'objective': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
    'reward_points': forms.NumberInput(attrs={'class': 'form-input'}),
    'reward_badge': forms.TextInput(attrs={'class': 'form-input'}),
    'available_from': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
    'available_until': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
}

TRAINING_FIELDS = [
    'title', 'description', 'objective',
    'cover_image', 'reward_points', 'reward_badge',
    'is_active', 'is_mandatory',
    'available_from', 'available_until'
]


class TrainingForm(forms.ModelForm):
    """Form para criar/editar treinamentos (Gestor)."""
    
    class Meta:
        model = Training
        fields = TRAINING_FIELDS
        widgets = TRAINING_WIDGETS
    
    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self._setup_assigned_users_field()
    
    def _setup_assigned_users_field(self):
        """Configura o campo assigned_users com filtro por empresa."""
        if not hasattr(self.Meta.model, 'assigned_users'):
            return
        
        if 'assigned_users' not in self.fields:
            self.fields['assigned_users'] = forms.ModelMultipleChoiceField(
                queryset=User.objects.none(),
                required=False,
                widget=forms.SelectMultiple(attrs={
                    'class': 'form-select bg-[#1A1A1A] border border-[#333333] text-white rounded-lg',
                    'multiple': 'multiple',
                    'size': '6',
                    'id': 'id_assigned_users'
                }),
                label='Usuários Atribuídos',
                help_text='Selecione os colaboradores que devem ter acesso a este treinamento. Deixe vazio para tornar global.'
            )
        
        if self.instance and self.instance.pk and 'assigned_users' in self.fields:
            self.fields['assigned_users'].initial = self.instance.assigned_users.all()
        
        if self.company:
            company_user_ids = UserCompany.objects.filter(
                company=self.company,
                is_active=True
            ).values_list('user_id', flat=True)
            
            self.fields['assigned_users'].queryset = User.objects.filter(
                id__in=company_user_ids,
                is_active=True
            ).order_by('first_name', 'last_name')
        else:
            self.fields['assigned_users'].queryset = User.objects.none()


class VideoForm(forms.ModelForm):
    """Form para criar/editar vídeo."""
    
    class Meta:
        model = Video
        fields = ['title', 'description', 'video_file', 'order', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Título do vídeo'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 2,
                'placeholder': 'Descrição opcional'
            }),
            'video_file': forms.FileInput(attrs={
                'class': 'form-input file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-brand-500 file:text-white file:cursor-pointer',
                'accept': 'video/mp4,video/webm,video/quicktime'
            }),
            'order': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Torna video_file opcional na edição
        if self.instance and self.instance.pk:
            self.fields['video_file'].required = False


class VideoUploadForm(forms.Form):
    """Form simplificado para upload de vídeo (criação rápida)."""
    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Título do vídeo'
        })
    )
    video_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-input',
            'accept': 'video/mp4,video/webm,video/quicktime'
        })
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'rows': 2,
            'placeholder': 'Descrição opcional'
        })
    )


class QuizForm(forms.ModelForm):
    """Form para criar/editar quiz."""
    
    class Meta:
        model = Quiz
        fields = ['title', 'description', 'order', 'is_active', 'passing_score', 'allow_multiple_attempts']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'order': forms.NumberInput(attrs={'class': 'form-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'passing_score': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': 0,
                'max': 100,
                'value': 70
            }),
            'allow_multiple_attempts': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class QuestionForm(forms.ModelForm):
    """Form para criar/editar pergunta."""
    
    class Meta:
        model = Question
        fields = ['text', 'order']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 2,
                'placeholder': 'Digite a pergunta...'
            }),
            'order': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
        }


class ChoiceForm(forms.ModelForm):
    """Form para criar/editar opção de resposta."""
    
    class Meta:
        model = Choice
        fields = ['text', 'is_correct', 'order']
        widgets = {
            'text': forms.TextInput(attrs={
                'class': 'form-input w-full',
                'placeholder': 'Digite a opção de resposta...'
            }),
            'is_correct': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'order': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
        }


# Inline formsets para gerenciar perguntas e opções
QuestionFormSet = inlineformset_factory(
    Quiz,
    Question,
    form=QuestionForm,
    extra=0,  # JS cria perguntas dinamicamente
    can_delete=True,
    min_num=0,  # Validação será feita manualmente na view
    validate_min=False
)

ChoiceFormSet = inlineformset_factory(
    Question,
    Choice,
    form=ChoiceForm,
    extra=0,  # Não criar opções vazias por padrão
    can_delete=True,
    min_num=0,  # Validação será feita manualmente na view
    validate_min=False
)

