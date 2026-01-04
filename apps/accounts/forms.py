"""
Forms para autenticação e gestão de usuários.
"""

from django import forms
from django.contrib.auth import authenticate

from .models import User, UserCompany, Warning
from apps.core.models import Company, Role


class LoginForm(forms.Form):
    """Form de login com email e senha."""
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'seu@email.com',
            'autocomplete': 'email',
        })
    )
    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': '••••••••',
            'autocomplete': 'current-password',
        })
    )
    remember_me = forms.BooleanField(
        label='Lembrar-me',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox',
        })
    )
    
    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)
    
    def clean(self):
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')
        
        if email and password:
            self.user_cache = authenticate(
                self.request,
                username=email,
                password=password
            )
            if self.user_cache is None:
                raise forms.ValidationError(
                    'Email ou senha incorretos.',
                    code='invalid_login',
                )
            elif not self.user_cache.is_active:
                raise forms.ValidationError(
                    'Esta conta está desativada.',
                    code='inactive',
                )
            
            # Verifica se usuário tem vínculo ativo com alguma empresa
            has_company = UserCompany.objects.filter(
                user=self.user_cache,
                is_active=True
            ).exists()
            
            if not has_company and not self.user_cache.is_superuser:
                raise forms.ValidationError(
                    'Você não está vinculado a nenhuma empresa ativa.',
                    code='no_company',
                )
        
        return self.cleaned_data
    
    def get_user(self):
        return self.user_cache


class UserProfileForm(forms.ModelForm):
    """Form para edição de perfil."""
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'neighborhood', 'city', 'bio', 'avatar', 'birth_date']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'phone': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '(00) 00000-0000'
            }),
            'neighborhood': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Bairro'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Cidade'
            }),
            'bio': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'birth_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-input'
            }),
        }


class CollaboratorForm(forms.ModelForm):
    """
    Form para gestores cadastrarem colaboradores ou outros gestores.
    Permite escolher entre roles de Gestor ou Colaborador da empresa.
    """
    # Dados básicos
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'colaborador@empresa.com'
        })
    )
    first_name = forms.CharField(
        label='Nome',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Nome'
        })
    )
    last_name = forms.CharField(
        label='Sobrenome',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Sobrenome'
        })
    )
    
    # Dados pessoais
    birth_date = forms.DateField(
        label='Data de Nascimento',
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-input'
        })
    )
    phone = forms.CharField(
        label='Telefone',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '(00) 00000-0000'
        })
    )
    
    # Dados de localização
    neighborhood = forms.CharField(
        label='Bairro',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Bairro'
        })
    )
    city = forms.CharField(
        label='Cidade',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Cidade'
        })
    )
    
    # Dados de empresa
    role = forms.ModelChoiceField(
        label='Cargo',
        queryset=Role.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Selecione o cargo do usuário na empresa'
    )
    
    class Meta:
        model = UserCompany
        fields = ['role']
    
    def __init__(self, company, *args, is_admin_master=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.is_admin_master = is_admin_master
        
        # Filtra roles da empresa do gestor logado (segurança multi-tenant)
        if company:
            # Admin Master pode criar qualquer nível
            # Gestor só pode criar Gestor ou Colaborador (não Admin)
            if is_admin_master:
                self.fields['role'].queryset = Role.objects.filter(
                    company=company
                ).order_by('name')
            else:
                # Gestor: exclui roles de nível admin_master
                self.fields['role'].queryset = Role.objects.filter(
                    company=company
                ).exclude(
                    level='admin_master'
                ).order_by('name')
    
    def clean_email(self):
        """Valida se o email já existe na empresa."""
        email = self.cleaned_data.get('email')
        if email:
            # Verifica se já existe vínculo ativo com esta empresa
            existing = UserCompany.objects.filter(
                user__email=email,
                company=self.company,
                is_active=True
            ).exists()
            if existing:
                raise forms.ValidationError('Este usuário já está vinculado a esta empresa.')
        return email
    
    def save(self, commit=True):
        email = self.cleaned_data['email']
        first_name = self.cleaned_data['first_name']
        last_name = self.cleaned_data['last_name']
        birth_date = self.cleaned_data.get('birth_date')
        phone = self.cleaned_data.get('phone', '')
        neighborhood = self.cleaned_data.get('neighborhood', '')
        city = self.cleaned_data.get('city', '')
        
        # Cria ou obtém o usuário
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'birth_date': birth_date,
                'phone': phone,
                'neighborhood': neighborhood,
                'city': city,
            }
        )
        
        # Atualiza dados se o usuário já existir
        if not created:
            update_fields = []
            if birth_date and not user.birth_date:
                user.birth_date = birth_date
                update_fields.append('birth_date')
            if phone and not user.phone:
                user.phone = phone
                update_fields.append('phone')
            if neighborhood and not user.neighborhood:
                user.neighborhood = neighborhood
                update_fields.append('neighborhood')
            if city and not user.city:
                user.city = city
                update_fields.append('city')
            if update_fields:
                user.save(update_fields=update_fields)
        
        if created:
            # Define uma senha temporária
            temp_password = User.objects.make_random_password()
            user.set_password(temp_password)
            user.save()
            # TODO: Enviar email com senha temporária
        
        # Gera matrícula automaticamente (EMPRESA-ANO-SEQUENCIAL)
        import datetime
        year = datetime.datetime.now().year
        company_prefix = self.company.slug[:3].upper() if self.company.slug else 'EMP'
        
        # Conta quantos usuários já existem na empresa para gerar sequencial
        count = UserCompany.objects.filter(company=self.company).count() + 1
        employee_id = f"{company_prefix}-{year}-{count:04d}"
        
        # Cria o vínculo com a empresa
        user_company, _ = UserCompany.objects.update_or_create(
            user=user,
            company=self.company,
            defaults={
                'role': self.cleaned_data['role'],
                'employee_id': employee_id,
                'is_active': True,
            }
        )
        
        return user_company


class AdminUserCreateForm(forms.ModelForm):
    """
    Form para Admin Master criar usuários e vincular à empresa.
    Inclui todos os campos cadastrais e permite definir senha.
    """
    # Dados básicos
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'usuario@empresa.com'
        })
    )
    first_name = forms.CharField(
        label='Nome',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Nome'
        })
    )
    last_name = forms.CharField(
        label='Sobrenome',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Sobrenome'
        })
    )
    
    # Dados pessoais
    birth_date = forms.DateField(
        label='Data de Nascimento',
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-input'
        })
    )
    phone = forms.CharField(
        label='Telefone',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '(00) 00000-0000'
        })
    )
    
    # Dados de localização
    neighborhood = forms.CharField(
        label='Bairro',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Bairro'
        })
    )
    city = forms.CharField(
        label='Cidade',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Cidade'
        })
    )
    
    # Segurança
    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': '••••••••',
            'id': 'id_password'
        }),
        help_text='A senha será definida pelo Admin Master. O usuário poderá alterá-la após o primeiro acesso.'
    )
    
    # Dados de empresa
    role = forms.ModelChoiceField(
        label='Cargo',
        queryset=Role.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Selecione o cargo do usuário na empresa'
    )
    employee_id = forms.CharField(
        label='Matrícula',
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'ID interno (opcional)'
        })
    )
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']
    
    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        # Filtra roles da empresa selecionada (segurança multi-tenant)
        if company:
            self.fields['role'].queryset = Role.objects.filter(company=company).order_by('name')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError('Este email já está cadastrado.')
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        # Salva campos adicionais
        user.birth_date = self.cleaned_data.get('birth_date')
        user.phone = self.cleaned_data.get('phone', '')
        user.neighborhood = self.cleaned_data.get('neighborhood', '')
        user.city = self.cleaned_data.get('city', '')
        if commit:
            user.save()
        return user


class ChangePasswordForm(forms.Form):
    """Form para alteração de senha."""
    old_password = forms.CharField(
        label='Senha Atual',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': '••••••••',
            'id': 'id_old_password'
        })
    )
    new_password1 = forms.CharField(
        label='Nova Senha',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': '••••••••',
            'id': 'id_new_password1'
        }),
        min_length=8,
        help_text='Mínimo de 8 caracteres'
    )
    new_password2 = forms.CharField(
        label='Confirmar Nova Senha',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': '••••••••',
            'id': 'id_new_password2'
        })
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise forms.ValidationError('Senha atual incorreta.')
        return old_password
    
    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('As senhas não coincidem.')
        return password2
    
    def save(self, commit=True):
        password = self.cleaned_data['new_password1']
        self.user.set_password(password)
        if commit:
            self.user.save()
        return self.user


class WarningForm(forms.ModelForm):
    """Form para lançamento de advertência disciplinar."""
    
    class Meta:
        model = Warning
        fields = ['user', 'warning_type', 'reason']
        widgets = {
            'user': forms.Select(attrs={
                'class': 'form-select',
            }),
            'warning_type': forms.Select(attrs={
                'class': 'form-select',
            }),
            'reason': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 5,
                'placeholder': 'Descreva detalhadamente o motivo da advertência...'
            }),
        }
        labels = {
            'user': 'Colaborador',
            'warning_type': 'Tipo de Advertência',
            'reason': 'Motivo',
        }
    
    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        
        if company:
            # Filtra apenas colaboradores ativos da empresa
            from apps.accounts.models import UserCompany
            company_user_ids = UserCompany.objects.filter(
                company=company,
                is_active=True
            ).values_list('user_id', flat=True)
            
            self.fields['user'].queryset = User.objects.filter(
                id__in=company_user_ids,
                is_active=True
            ).order_by('first_name', 'last_name')

