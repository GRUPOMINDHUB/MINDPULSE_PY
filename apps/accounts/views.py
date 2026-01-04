"""
Views de autenticação e gestão de usuários.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction

from .forms import LoginForm, UserProfileForm, CollaboratorForm, ChangePasswordForm
from .models import User, UserCompany


def login_view(request):
    """View de login."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            # Atualiza última atividade
            user.update_activity()
            
            # Define duração da sessão
            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0)  # Fecha ao fechar navegador
            
            messages.success(request, f'Bem-vindo(a), {user.get_short_name()}!')
            
            # Redireciona para página solicitada ou dashboard
            next_url = request.GET.get('next', 'core:dashboard')
            return redirect(next_url)
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """View de logout."""
    logout(request)
    messages.info(request, 'Você saiu do sistema.')
    return redirect('accounts:login')


@login_required
def profile_view(request):
    """View de perfil do usuário."""
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil atualizado com sucesso!')
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=request.user)
    
    # Busca vínculos do usuário
    user_companies = UserCompany.objects.filter(
        user=request.user
    ).select_related('company', 'role')
    
    context = {
        'form': form,
        'user_companies': user_companies,
    }
    
    return render(request, 'accounts/profile.html', context)


@login_required
def change_password(request):
    """Alterar senha do usuário."""
    if request.method == 'POST':
        form = ChangePasswordForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Senha alterada com sucesso!')
            return redirect('accounts:profile')
    else:
        form = ChangePasswordForm(request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form})


@login_required
def collaborators_list(request):
    """Lista de colaboradores (apenas gestores)."""
    if not request.is_gestor:
        messages.error(request, 'Acesso não autorizado.')
        return redirect('core:dashboard')
    
    company = request.current_company
    
    collaborators = UserCompany.objects.filter(
        company=company
    ).select_related('user', 'role').order_by('-is_active', 'user__first_name')
    
    context = {
        'collaborators': collaborators,
    }
    
    return render(request, 'accounts/collaborators_list.html', context)


@login_required
def collaborator_create(request):
    """Cadastro de novo colaborador (apenas gestores)."""
    if not request.is_gestor:
        messages.error(request, 'Acesso não autorizado.')
        return redirect('core:dashboard')
    
    company = request.current_company
    
    if request.method == 'POST':
        form = CollaboratorForm(company, request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user_company = form.save()
                messages.success(
                    request, 
                    f'Colaborador {user_company.user.get_full_name()} cadastrado com sucesso!'
                )
                return redirect('accounts:collaborators_list')
            except Exception as e:
                messages.error(request, f'Erro ao cadastrar colaborador: {str(e)}')
        else:
            # Exibe erros de validação
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = CollaboratorForm(company)
    
    return render(request, 'accounts/collaborator_form.html', {'form': form})


@login_required
@require_POST
def collaborator_toggle_status(request, pk):
    """Ativa/desativa colaborador (apenas gestores)."""
    if not request.is_gestor:
        return JsonResponse({'error': 'Não autorizado'}, status=403)
    
    user_company = get_object_or_404(
        UserCompany,
        pk=pk,
        company=request.current_company
    )
    
    user_company.is_active = not user_company.is_active
    user_company.save(update_fields=['is_active'])
    
    status_text = 'ativado' if user_company.is_active else 'desativado'
    
    return JsonResponse({
        'success': True,
        'is_active': user_company.is_active,
        'message': f'Colaborador {status_text} com sucesso!'
    })

