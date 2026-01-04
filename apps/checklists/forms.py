"""
Forms para gestão de checklists.
"""

from django import forms
from .models import Checklist, Task
from apps.core.models import Company
from apps.accounts.models import UserCompany
from django.contrib.auth import get_user_model

User = get_user_model()

CHECKLIST_WIDGETS = {
    'title': forms.TextInput(attrs={'class': 'form-input'}),
    'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
    'frequency': forms.Select(attrs={'class': 'form-select'}),
    'points_per_completion': forms.NumberInput(attrs={'class': 'form-input'}),
}

CHECKLIST_FIELDS = ['title', 'description', 'frequency', 'points_per_completion', 'is_active']


class ChecklistForm(forms.ModelForm):
    """Form para criar/editar checklists (Gestor)."""
    
    class Meta:
        model = Checklist
        fields = CHECKLIST_FIELDS
        widgets = CHECKLIST_WIDGETS
    
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
                    'size': '6'
                }),
                label='Responsáveis por este Checklist',
                help_text='Selecione os colaboradores. Deixe vazio para tornar global.'
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


class TaskForm(forms.ModelForm):
    """Form para criar/editar tarefas."""
    
    class Meta:
        model = Task
        fields = ['title', 'description', 'is_required', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Título da tarefa'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 2,
                'placeholder': 'Descrição opcional'
            }),
        }

