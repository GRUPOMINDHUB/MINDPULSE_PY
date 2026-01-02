"""
Forms para gestão de treinamentos.
"""

from django import forms
from .models import Training, Video
from apps.core.models import Company


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


class AdminTrainingForm(TrainingForm):
    """Form para Admin Master - inclui seletor de empresa."""
    
    company = forms.ModelChoiceField(
        queryset=Company.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Empresa'
    )
    
    class Meta(TrainingForm.Meta):
        fields = ['company'] + TRAINING_FIELDS


class VideoUploadForm(forms.Form):
    """Form simplificado para upload de vídeo."""
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

