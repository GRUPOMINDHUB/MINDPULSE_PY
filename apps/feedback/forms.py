"""
Forms para feedback.
"""

from django import forms
from .models import FeedbackTicket, FeedbackComment


class FeedbackForm(forms.ModelForm):
    """Form para enviar feedback."""
    
    class Meta:
        model = FeedbackTicket
        fields = ['sentiment', 'category', 'subject', 'message', 'attachment', 'is_anonymous']
        widgets = {
            'sentiment': forms.RadioSelect(attrs={'class': 'sentiment-radio'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Assunto do feedback'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 5,
                'placeholder': 'Descreva seu feedback em detalhes...'
            }),
            'attachment': forms.FileInput(attrs={'class': 'form-input'}),
            'is_anonymous': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class FeedbackResponseForm(forms.Form):
    """Form para responder feedback."""
    response = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'rows': 4,
            'placeholder': 'Escreva sua resposta...'
        })
    )
    status = forms.ChoiceField(
        choices=FeedbackTicket.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class FeedbackCommentForm(forms.ModelForm):
    """Form para adicionar comentário."""
    
    class Meta:
        model = FeedbackComment
        fields = ['message']
        widgets = {
            'message': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'Adicione um comentário...'
            })
        }

