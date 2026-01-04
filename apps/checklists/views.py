"""
Views para checklists.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.db.models import Max, Q
from django.urls import reverse

from .models import Checklist, Task, TaskDone, ChecklistCompletion
from .forms import ChecklistForm, TaskForm
from apps.core.models import Company
from apps.core.decorators import gestor_required, gestor_required_ajax
from apps.core.utils import PeriodKeyHelper


@login_required
def checklist_list(request):
    """
    Lista de checklists disponíveis.
    ACCESS: ADMIN MASTER | GESTOR | COLABORADOR
    - Admin Master: Vê todos os checklists de todas as empresas
    - Gestor: Vê todos os checklists da sua empresa
    - Colaborador: Vê apenas checklists atribuídos a ele ou globais
    """
    user = request.user
    company = request.current_company
    
    if user.is_superuser:
        if company:
            checklists = Checklist.objects.filter(
                company=company,
                is_active=True
            ).prefetch_related('tasks', 'assigned_users')
        else:
            checklists = Checklist.objects.filter(
                is_active=True
            ).select_related('company').prefetch_related('tasks', 'assigned_users')
    else:
        if not company:
            return render(request, 'core/no_company.html')
        
        if request.is_gestor:
            checklists = Checklist.objects.filter(
                company=company,
                is_active=True
            ).prefetch_related('tasks', 'assigned_users')
        else:
            try:
                checklists = Checklist.objects.filter(
                    company=company,
                    is_active=True
                ).filter(
                    Q(assigned_users=user) | Q(assigned_users__isnull=True) | Q(assigned_users__exact=None)
                ).distinct().prefetch_related('tasks', 'assigned_users')
            except Exception:
                checklists = Checklist.objects.filter(
                    company=company,
                    is_active=True
                ).prefetch_related('tasks', 'assigned_users')
    
    sort_by = request.GET.get('sort', 'title')
    
    if sort_by == 'frequency':
        checklists = checklists.order_by('frequency', 'title')
    elif sort_by == 'responsible':
        checklists_list = list(checklists)
        checklists_list.sort(key=lambda c: (
            c.assigned_users.first().first_name if c.assigned_users.exists() and c.assigned_users.first() else 'ZZZ',
            c.title
        ))
        checklists = checklists_list
    elif sort_by == 'title':
        checklists = checklists.order_by('title')
    elif sort_by == 'order':
        checklists = checklists.order_by('order', 'title')
    else:
        checklists = checklists.order_by('title')
    
    requested_period = request.GET.get('period')
    if requested_period:
        period_key = requested_period
    else:
        period_key = None
    
    checklist_data = []
    for checklist in checklists:
        if period_key is None:
            current_period_key = checklist.get_current_period_key()
        else:
            current_period_key = period_key
        
        progress = checklist.get_user_completion(user, current_period_key)
        is_overdue = checklist.is_overdue_for_user(user) if not requested_period else False
        
        checklist_data.append({
            'checklist': checklist,
            'period_key': current_period_key,
            'period_display': PeriodKeyHelper.get_period_display(checklist.frequency) if not requested_period else requested_period,
            'progress': progress,
            'is_completed': progress == 100,
            'is_overdue': is_overdue,
        })
    
    context = {
        'checklist_data': checklist_data,
        'sort_by': sort_by,
    }
    
    return render(request, 'checklists/list.html', context)


@login_required
def checklist_detail(request, pk):
    """
    Detalhes do checklist com tarefas.
    ACCESS: ADMIN MASTER | GESTOR | COLABORADOR (com restrição)
    """
    if request.user.is_superuser:
        checklist = get_object_or_404(
            Checklist.objects.prefetch_related('tasks'),
            pk=pk,
            is_active=True
        )
    else:
        company = request.current_company
        if not company:
            return render(request, 'core/no_company.html')
        
        checklist = get_object_or_404(
            Checklist.objects.prefetch_related('tasks'),
            pk=pk,
            company=company,
            is_active=True
        )
    
    # Verificação de segurança: colaborador só pode acessar checklists atribuídos a ele ou globais
    # REGRA DE OURO: Não permitir que colaborador veja checklists não atribuídos
    # ACCESS CONTROL: Bloqueia acesso não autorizado com 403
    if not (request.is_gestor or request.user.is_superuser):
        try:
            # Verifica se o campo assigned_users existe
            if hasattr(checklist, 'assigned_users'):
                assigned_count = checklist.assigned_users.count()
                # Se há usuários atribuídos, verifica se o usuário atual está na lista
                if assigned_count > 0:
                    if request.user not in checklist.assigned_users.all():
                        return HttpResponseForbidden(
                            f'<div style="padding: 2rem; text-align: center; color: white; background: #1A1A1A; min-height: 100vh; display: flex; align-items: center; justify-content: center; flex-direction: column;">'
                            f'<h1 style="color: #F83531; font-size: 2rem; margin-bottom: 1rem;">403 - Acesso Negado</h1>'
                            f'<p style="font-size: 1.1rem; margin-bottom: 0.5rem;">Você não tem permissão para acessar este checklist.</p>'
                            f'<p style="color: #999; margin-bottom: 2rem;">Este checklist foi atribuído apenas a usuários específicos.</p>'
                            f'<a href="{reverse("checklists:list")}" style="color: #F83531; text-decoration: underline;">← Voltar para lista de checklists</a>'
                            f'</div>'
                        )
        except Exception:
            return HttpResponseForbidden(
                '<h1>403 - Acesso Negado</h1>'
                '<p>Erro ao verificar permissões. Contate o administrador.</p>'
            )
    
    period_key = checklist.get_current_period_key()
    tasks = checklist.tasks.filter(is_active=True).order_by('order')
    
    done_tasks = TaskDone.objects.filter(
        task__checklist=checklist,
        user=request.user,
        period_key=period_key
    ).values_list('task_id', flat=True)
    
    tasks_with_status = []
    for task in tasks:
        tasks_with_status.append({
            'task': task,
            'is_done': task.id in done_tasks,
        })
    
    progress = checklist.get_user_completion(request.user, period_key)
    can_manage_tasks = request.is_gestor or request.user.is_superuser

    assigned_user = None
    try:
        if hasattr(checklist, 'assigned_users'):
            assigned_user = checklist.assigned_users.first()
    except Exception:
        pass
    
    context = {
        'checklist': checklist,
        'tasks': tasks_with_status,
        'period_key': period_key,
        'period_display': checklist.get_period_display(),
        'progress': progress,
        'is_completed': progress == 100,
        'can_manage_tasks': can_manage_tasks,
        'assigned_user': assigned_user,
    }
    
    return render(request, 'checklists/detail.html', context)


@login_required
@require_POST
def toggle_task(request, task_id):
    """Alterna estado de conclusão da tarefa (marca/desmarca)."""
    task = get_object_or_404(Task, pk=task_id)
    
    if not request.user.is_superuser:
        if not request.current_company or task.checklist.company != request.current_company:
            return JsonResponse({'error': 'Não autorizado'}, status=403)
    
    period_key = task.checklist.get_current_period_key()
    task_done = TaskDone.objects.filter(
        task=task,
        user=request.user,
        period_key=period_key
    ).first()
    
    if task_done:
        task_done.delete()
        is_done = False
        message = 'Tarefa desmarcada'
    else:
        TaskDone.objects.create(
            task=task,
            user=request.user,
            period_key=period_key,
            notes=request.POST.get('notes', '')
        )
        is_done = True
        message = 'Tarefa concluída!'
    
    checklist = task.checklist
    progress = checklist.get_user_completion(request.user, period_key)
    is_checklist_completed = progress == 100
    
    response_data = {
        'success': True,
        'is_done': is_done,
        'message': message,
        'progress': progress,
        'is_checklist_completed': is_checklist_completed,
    }
    
    if is_checklist_completed and is_done:
        response_data['reward_message'] = f'Parabéns! Você completou o checklist e ganhou {checklist.points_per_completion} pontos!'
    
    return JsonResponse(response_data)


# ============================================================================
# Views para Gestores
# ============================================================================

@login_required
@gestor_required
def checklist_manage_list(request):
    """
    Lista de checklists para gestão.
    ACCESS: ADMIN MASTER | GESTOR
    """
    if not (request.is_gestor or request.user.is_superuser):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Apenas gestores e administradores podem acessar esta página.")
    
    if request.user.is_superuser:
        company = request.current_company
        if company:
            checklists = Checklist.objects.filter(company=company).select_related('company').prefetch_related('tasks', 'assigned_users')
        else:
            checklists = Checklist.objects.all().select_related('company').prefetch_related('tasks', 'assigned_users')
        companies = Company.objects.filter(is_active=True)
    else:
        company = request.current_company
        if not company:
            return render(request, 'core/no_company.html')
        checklists = Checklist.objects.filter(company=company).prefetch_related('tasks', 'assigned_users')
        companies = None
    
    sort_by = request.GET.get('sort', 'title')
    
    if sort_by == 'frequency':
        checklists = checklists.order_by('frequency', 'title')
    elif sort_by == 'responsible':
        checklists_list = list(checklists)
        checklists_list.sort(key=lambda c: (
            c.assigned_users.first().first_name if c.assigned_users.exists() and c.assigned_users.first() else 'ZZZ',
            c.title
        ))
        checklists = checklists_list
    elif sort_by == 'title':
        checklists = checklists.order_by('title')
    elif sort_by == 'order':
        checklists = checklists.order_by('order', 'title')
    else:
        checklists = checklists.order_by('title')
    
    checklists_data = []
    for checklist in checklists:
        checklists_data.append({
            'checklist': checklist,
        })
    
    return render(request, 'checklists/manage/list.html', {
        'checklists_data': checklists_data,
        'companies': companies,
        'is_admin_master': request.user.is_superuser,
        'sort_by': sort_by,
    })


@login_required
@gestor_required
def checklist_create(request):
    """
    Criar novo checklist.
    ACCESS: ADMIN MASTER | GESTOR
    Usa a empresa selecionada no sidemenu (request.current_company)
    """
    if not (request.is_gestor or request.user.is_superuser):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Apenas gestores e administradores podem criar checklists.")
    
    # Verifica se há empresa selecionada
    if not request.current_company:
        messages.error(request, 'Selecione uma empresa no menu lateral antes de criar um checklist.')
        return redirect('checklists:manage_list')
    
    if request.method == 'POST':
        form = ChecklistForm(request.POST, company=request.current_company)
        
        if form.is_valid():
            checklist = form.save(commit=False)
            checklist.company = request.current_company
            
            if not checklist.order or checklist.order == 0:
                max_order = Checklist.objects.filter(company=checklist.company).aggregate(
                    max_order=Max('order')
                )['max_order'] or 0
                checklist.order = max_order + 1
            
            checklist.save()
            
            if 'assigned_users' in form.cleaned_data:
                checklist.assigned_users.set(form.cleaned_data['assigned_users'])
            else:
                checklist.assigned_users.clear()
            
            messages.success(request, 'Checklist criado com sucesso!')
            return redirect('checklists:manage_list')
    else:
        form = ChecklistForm(company=request.current_company)
    
    return render(request, 'checklists/manage/form.html', {
        'form': form,
        'title': 'Novo Checklist',
    })


@login_required
@gestor_required
def checklist_edit(request, pk):
    """
    Editar checklist existente.
    ACCESS: ADMIN MASTER | GESTOR
    Usa a empresa do checklist
    """
    if not (request.is_gestor or request.user.is_superuser):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Apenas gestores e administradores podem editar checklists.")
    
    # Admin pode editar qualquer, Gestor só da sua empresa
    if request.user.is_superuser:
        checklist = get_object_or_404(Checklist, pk=pk)
    else:
        checklist = get_object_or_404(Checklist, pk=pk, company=request.current_company)
    
    if request.method == 'POST':
        form = ChecklistForm(request.POST, instance=checklist, company=checklist.company)
        
        if form.is_valid():
            checklist = form.save()
            
            if 'assigned_users' in form.cleaned_data:
                checklist.assigned_users.set(form.cleaned_data['assigned_users'])
            else:
                checklist.assigned_users.clear()
            
            messages.success(request, 'Checklist atualizado!')
            return redirect('checklists:manage_list')
    else:
        form = ChecklistForm(instance=checklist, company=checklist.company)
    
    return render(request, 'checklists/manage/form.html', {
        'form': form,
        'checklist': checklist,
        'title': 'Editar Checklist',
    })


@login_required
@gestor_required
def checklist_manage_detail(request, pk):
    """
    Detalhes do checklist para gestão (adicionar tarefas).
    ACCESS: ADMIN MASTER | GESTOR
    - Admin Master: Pode gerenciar checklist de qualquer empresa
    - Gestor: Pode gerenciar apenas checklists da sua empresa
    REGRA DE OURO: Colaboradores recebem 403 se tentarem acessar manualmente
    """
    # Validação adicional de segurança
    if not (request.is_gestor or request.user.is_superuser):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Apenas gestores e administradores podem gerenciar checklists.")
    
    is_admin = request.user.is_superuser
    
    # Admin pode ver qualquer checklist
    if is_admin:
        checklist = get_object_or_404(Checklist, pk=pk)
    else:
        checklist = get_object_or_404(Checklist, pk=pk, company=request.current_company)
    
    tasks = checklist.tasks.all().order_by('order')
    
    # Form para adicionar tarefa
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.checklist = checklist
            # Calcula ordem automaticamente (última posição + 1)
            max_order = tasks.aggregate(Max('order'))['order__max'] or 0
            task.order = max_order + 1
            task.save()
            messages.success(request, f'Tarefa "{task.title}" adicionada!')
            return redirect('checklists:manage_detail', pk=pk)
        else:
            # Exibe erros de validação
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = TaskForm()
    
    context = {
        'checklist': checklist,
        'tasks': tasks,
        'form': form,
        'is_admin_master': is_admin,
    }
    
    return render(request, 'checklists/manage/detail.html', context)


@login_required
@gestor_required
@require_POST
def checklist_delete(request, pk):
    """
    Excluir checklist.
    ACCESS: ADMIN MASTER | GESTOR
    - Admin Master: Pode excluir checklist de qualquer empresa
    - Gestor: Pode excluir apenas checklists da sua empresa
    REGRA DE OURO: Colaboradores recebem 403 se tentarem acessar manualmente
    """
    # Validação adicional de segurança
    if not (request.is_gestor or request.user.is_superuser):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Apenas gestores e administradores podem excluir checklists.")
    
    is_admin = request.user.is_superuser
    
    if is_admin:
        checklist = get_object_or_404(Checklist, pk=pk)
    else:
        checklist = get_object_or_404(Checklist, pk=pk, company=request.current_company)
    
    checklist.delete()
    messages.success(request, 'Checklist excluído!')
    
    return redirect('checklists:manage_list')


@login_required
@gestor_required_ajax
@require_POST
def task_delete(request, task_id):
    """Excluir tarefa."""
    
    is_admin = request.user.is_superuser
    
    if is_admin:
        task = get_object_or_404(Task, pk=task_id)
    else:
        task = get_object_or_404(Task, pk=task_id, checklist__company=request.current_company)
    
    task_title = task.title
    task.delete()
    
    return JsonResponse({'success': True, 'message': f'Tarefa "{task_title}" excluída!'})


@login_required
@gestor_required_ajax
def task_edit(request, task_id):
    """
    Editar tarefa via AJAX.
    ACCESS: ADMIN MASTER | GESTOR
    """
    is_admin = request.user.is_superuser
    
    if is_admin:
        task = get_object_or_404(Task, pk=task_id)
    else:
        task = get_object_or_404(Task, pk=task_id, checklist__company=request.current_company)
    
    if request.method == 'POST':
        # Prepara dados do formulário (trata checkboxes)
        post_data = request.POST.copy()
        post_data['is_required'] = post_data.get('is_required', 'off') == 'on'
        post_data['is_active'] = post_data.get('is_active', 'off') == 'on'
        
        form = TaskForm(post_data, instance=task)
        if form.is_valid():
            form.save()
            return JsonResponse({
                'success': True,
                'message': 'Tarefa atualizada!',
                'task': {
                    'id': task.id,
                    'title': task.title,
                    'description': task.description,
                    'is_required': task.is_required,
                    'is_active': task.is_active,
                }
            })
        else:
            # Retorna erros formatados
            errors_dict = {}
            for field, errors in form.errors.items():
                errors_dict[field] = [str(error) for error in errors]
            
            return JsonResponse({
                'success': False,
                'errors': errors_dict,
                'message': 'Por favor, corrija os erros no formulário.'
            }, status=400)
    else:
        # GET: retorna dados da tarefa para edição
        return JsonResponse({
            'success': True,
            'task': {
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'is_required': task.is_required,
                'is_active': task.is_active,
            }
        })


@login_required
@gestor_required_ajax
def get_company_users(request):
    """
    API para buscar usuários de uma empresa (para filtragem dinâmica).
    ACCESS: ADMIN MASTER | GESTOR
    """
    from apps.accounts.models import UserCompany
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    company_id = request.GET.get('company_id')
    
    if not company_id:
        return JsonResponse({
            'success': False,
            'message': 'company_id é obrigatório'
        }, status=400)
    
    try:
        company_id = int(company_id)
        company = Company.objects.get(id=company_id, is_active=True)
    except (ValueError, Company.DoesNotExist):
        return JsonResponse({
            'success': False,
            'message': 'Empresa não encontrada'
        }, status=404)
    
    # Verifica permissão: Admin Master pode ver qualquer empresa, Gestor só a sua
    if not request.user.is_superuser:
        if request.current_company != company:
            return JsonResponse({
                'success': False,
                'message': 'Não autorizado'
            }, status=403)
    
    # Busca usuários vinculados à empresa
    company_user_ids = UserCompany.objects.filter(
        company=company,
        is_active=True
    ).values_list('user_id', flat=True)
    
    users = User.objects.filter(
        id__in=company_user_ids,
        is_active=True
    ).order_by('first_name', 'last_name')
    
    users_data = [{
        'id': user.id,
        'full_name': user.get_full_name() or user.email,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
    } for user in users]
    
    return JsonResponse({
        'success': True,
        'users': users_data,
        'count': len(users_data)
    })


@login_required
@gestor_required_ajax
@require_POST
def task_create_ajax(request, checklist_id):
    """
    Criar tarefa via AJAX na página de detalhes.
    ACCESS: ADMIN MASTER | GESTOR
    """
    is_admin = request.user.is_superuser
    
    if is_admin:
        checklist = get_object_or_404(Checklist, pk=checklist_id)
    else:
        checklist = get_object_or_404(Checklist, pk=checklist_id, company=request.current_company)
    
    # Prepara dados do formulário (trata checkboxes)
    post_data = request.POST.copy()
    post_data['is_required'] = post_data.get('is_required', 'off') == 'on'
    post_data['is_active'] = post_data.get('is_active', 'off') == 'on'
    
    form = TaskForm(post_data)
    if form.is_valid():
        task = form.save(commit=False)
        task.checklist = checklist
        # Calcula ordem automaticamente
        max_order = checklist.tasks.aggregate(Max('order'))['order__max'] or 0
        task.order = max_order + 1
        task.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Tarefa "{task.title}" criada!',
            'task': {
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'is_required': task.is_required,
                'is_active': task.is_active,
            }
        })
    else:
        # Retorna erros formatados
        errors_dict = {}
        for field, errors in form.errors.items():
            errors_dict[field] = [str(error) for error in errors]
        
        return JsonResponse({
            'success': False,
            'errors': errors_dict,
            'message': 'Por favor, corrija os erros no formulário.'
        }, status=400)

