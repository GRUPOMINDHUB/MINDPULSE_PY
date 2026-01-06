"""
Forms para gestão de empresas.
"""

from django import forms
from django.utils.text import slugify
from .models import Company, Role


class CompanyForm(forms.ModelForm):
    """Form para criar/editar empresas."""
    
    class Meta:
        model = Company
        fields = ['name', 'logo', 'primary_color', 'is_active', 'max_users']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Nome da empresa'
            }),
            'primary_color': forms.TextInput(attrs={
                'class': 'form-input',
                'type': 'color',
            }),
            'max_users': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': 1
            }),
        }


class RoleForm(forms.ModelForm):
    """Form para criar/editar cargos."""
    
    class Meta:
        model = Role
        fields = ['name', 'level', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Nome do cargo'
            }),
            'level': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 2,
                'placeholder': 'Descrição do cargo'
            }),
        }

