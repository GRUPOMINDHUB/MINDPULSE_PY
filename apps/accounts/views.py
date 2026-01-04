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

from .forms import LoginForm, UserProfileForm, CollaboratorForm, ChangePasswordForm, WarningForm
from .models import User, UserCompany, Warning
from django.http import HttpResponseForbidden


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
    
    # Busca histórico de advertências do usuário
    warnings = Warning.objects.filter(
        user=request.user
    ).select_related('company', 'issuer').order_by('-created_at')
    
    context = {
        'form': form,
        'user_companies': user_companies,
        'warnings': warnings,
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


@login_required
def warning_list(request):
    """
    Lista de advertências disciplinares.
    ACCESS: ADMIN MASTER | GESTOR
    - Admin Master: Vê todas as advertências (ou da empresa selecionada)
    - Gestor: Vê apenas advertências da sua empresa
    """
    # Verificação de segurança: apenas Admin Master e Gestores
    if not (request.is_gestor or request.user.is_superuser):
        return HttpResponseForbidden(
            '<h1>403 - Acesso Negado</h1>'
            '<p>Você não tem permissão para acessar esta página.</p>'
        )
    
    user = request.user
    company = request.current_company
    
    # Admin Master: se current_company for None, mostra todas (visão global)
    if user.is_superuser:
        if company:
            warnings = Warning.objects.filter(
                company=company
            ).select_related('user', 'company', 'issuer').order_by('-created_at')
        else:
            warnings = Warning.objects.all().select_related('user', 'company', 'issuer').order_by('-created_at')
    else:
        # Gestor: precisa ter empresa vinculada
        if not company:
            return render(request, 'core/no_company.html')
        
        warnings = Warning.objects.filter(
            company=company
        ).select_related('user', 'company', 'issuer').order_by('-created_at')
    
    context = {
        'warnings': warnings,
        'is_admin_master': user.is_superuser,
    }
    
    return render(request, 'accounts/warning_list.html', context)


@login_required
def warning_create(request):
    """
    Criar nova advertência disciplinar.
    ACCESS: ADMIN MASTER | GESTOR
    Usa a empresa selecionada no sidemenu (request.current_company)
    """
    # Verificação de segurança: apenas Admin Master e Gestores
    if not (request.is_gestor or request.user.is_superuser):
        return HttpResponseForbidden(
            '<h1>403 - Acesso Negado</h1>'
            '<p>Você não tem permissão para acessar esta página.</p>'
        )
    
    company = request.current_company
    
    # Verifica se há empresa selecionada
    if not company:
        messages.error(request, 'Selecione uma empresa no menu lateral antes de criar uma advertência.')
        return redirect('accounts:warning_list')
    
    if request.method == 'POST':
        form = WarningForm(request.POST, company=company)
        if form.is_valid():
            warning = form.save(commit=False)
            warning.issuer = request.user
            warning.company = company
            warning.save()
            
            messages.success(
                request,
                f'Advertência aplicada a {warning.user.get_full_name()} com sucesso!'
            )
            return redirect('accounts:warning_list')
        else:
            # Exibe erros de validação
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = WarningForm(company=company)
    
    context = {
        'form': form,
    }
    
    return render(request, 'accounts/warning_form.html', context)

