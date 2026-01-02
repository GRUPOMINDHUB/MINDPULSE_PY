"""
Forms para autenticação e gestão de usuários.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import authenticate

from .models import User, UserCompany
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


class UserRegistrationForm(UserCreationForm):
    """Form para registro de novos colaboradores."""
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'password1', 'password2']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'seu@email.com',
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Nome',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Sobrenome',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': '••••••••',
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': '••••••••',
        })


class UserProfileForm(forms.ModelForm):
    """Form para edição de perfil."""
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'bio', 'avatar', 'birth_date']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'phone': forms.TextInput(attrs={'class': 'form-input'}),
            'bio': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'birth_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-input'
            }),
        }


class CollaboratorForm(forms.ModelForm):
    """Form para gestores cadastrarem colaboradores."""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-input'})
    )
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )
    birth_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-input'
        })
    )
    role = forms.ModelChoiceField(
        queryset=Role.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    employee_id = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )
    
    class Meta:
        model = UserCompany
        fields = ['role', 'employee_id']
    
    def __init__(self, company, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.fields['role'].queryset = Role.objects.filter(company=company)
    
    def save(self, commit=True):
        email = self.cleaned_data['email']
        first_name = self.cleaned_data['first_name']
        last_name = self.cleaned_data['last_name']
        birth_date = self.cleaned_data.get('birth_date')
        
        # Cria ou obtém o usuário
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'birth_date': birth_date,
            }
        )
        
        # Atualiza birth_date se o usuário já existir
        if not created and birth_date:
            user.birth_date = birth_date
            user.save(update_fields=['birth_date'])
        
        if created:
            # Define uma senha temporária
            temp_password = User.objects.make_random_password()
            user.set_password(temp_password)
            user.save()
            # TODO: Enviar email com senha temporária
        
        # Cria o vínculo com a empresa
        user_company, _ = UserCompany.objects.update_or_create(
            user=user,
            company=self.company,
            defaults={
                'role': self.cleaned_data['role'],
                'employee_id': self.cleaned_data.get('employee_id', ''),
                'is_active': True,
            }
        )
        
        return user_company


class AdminUserCreateForm(forms.ModelForm):
    """Form para Admin Master criar usuários e vincular à empresa."""
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
    birth_date = forms.DateField(
        label='Data de Nascimento',
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-input'
        })
    )
    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': '••••••••',
            'id': 'id_password'
        }),
        help_text='A senha será definida pelo Admin Master. O usuário poderá alterá-la após o primeiro acesso.'
    )
    role = forms.ModelChoiceField(
        label='Cargo',
        queryset=Role.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Selecione o cargo do usuário na empresa'
    )
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']
    
    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        if company:
            self.fields['role'].queryset = Role.objects.filter(company=company)
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError('Este email já está cadastrado.')
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
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

