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


class AdminChecklistForm(ChecklistForm):
    """Form para Admin Master - inclui seletor de empresa."""
    
    company = forms.ModelChoiceField(
        queryset=Company.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Empresa'
    )
    
    class Meta(ChecklistForm.Meta):
        fields = ['company'] + CHECKLIST_FIELDS
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = self._get_company_from_form()
        if company:
            self.company = company
            self._setup_assigned_users_field()
    
    def _get_company_from_form(self):
        """Extrai a empresa do formulário (instância, POST ou initial)."""
        if self.instance and self.instance.pk:
            return self.instance.company
        
        if 'company' in self.data:
            try:
                return Company.objects.get(id=int(self.data.get('company')), is_active=True)
            except (ValueError, Company.DoesNotExist):
                return None
        
        if 'company' in self.initial:
            try:
                company_id = self.initial.get('company')
                return Company.objects.get(id=company_id, is_active=True) if company_id else None
            except (ValueError, Company.DoesNotExist, TypeError):
                return None
        
        return None


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

