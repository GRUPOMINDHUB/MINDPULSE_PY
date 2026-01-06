"""
Core Views - Dashboard e páginas principais
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings
from datetime import timedelta, datetime
import calendar

from apps.trainings.models import Training, UserProgress, UserTrainingReward
from apps.checklists.models import Checklist, Task, TaskDone, ChecklistCompletion, ChecklistAlert
from apps.feedback.models import FeedbackTicket
from apps.accounts.models import User, UserCompany, Warning
from .models import Company, Role
from .forms import CompanyForm, RoleForm
from .utils import PeriodKeyHelper
from .decorators import admin_master_required, gestor_required
from .reports import get_report_data, get_company_report_data


def home(request):
    """Página inicial - redireciona para dashboard ou login."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    return redirect('accounts:login')


@login_required
def switch_company(request):
    """
    Troca a empresa selecionada globalmente (apenas Admin Master).
    ACCESS: ADMIN MASTER
    Salva o company_id na sessão e redireciona para a página anterior.
    """
    if not request.user.is_superuser:
        messages.error(request, 'Acesso negado.')
        return redirect('core:dashboard')
    
    company_id = request.POST.get('company_id', '')
    
    if company_id:
        try:
            company = Company.objects.get(pk=company_id, is_active=True)
            request.session['current_company_id'] = int(company_id)
            messages.success(request, f'Empresa selecionada: {company.name}')
        except (Company.DoesNotExist, ValueError):
            messages.error(request, 'Empresa não encontrada.')
            request.session.pop('current_company_id', None)
    else:
        # company_id vazio = "Todas as Empresas" (visão global)
        request.session.pop('current_company_id', None)
        messages.success(request, 'Visão global ativada (Todas as Empresas)')
    
    # Redireciona para a página anterior ou dashboard
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('core:dashboard')


@login_required
def dashboard(request):
    """
    Dashboard principal - redireciona baseado no nível de acesso.
    ACCESS: ADMIN MASTER | GESTOR | COLABORADOR
    - Admin Master: Dashboard global com KPIs comparativos entre empresas
    - Gestor: Dashboard operacional da unidade (Ranking da equipe e status do dia)
    - Colaborador: Dashboard de performance individual ("O que eu fiz" vs "O que eu deveria fazer")
    """
    # Admin Master vai para dashboard global
    if request.user.is_superuser:
        return redirect('core:admin_dashboard')
    
    company = request.current_company
    
    if not company:
        return render(request, 'core/no_company.html')
    
    # Gestores vão para dashboard de gestão
    if request.is_gestor:
        return redirect('core:gestor_dashboard')
    
    # Colaboradores vão para dashboard individual
    return redirect('core:colaborador_dashboard')


@login_required
def colaborador_dashboard(request):
    """
    Dashboard do Colaborador - Visão Individual.
    ACCESS: COLABORADOR
    Contexto: "O que eu fiz" vs "O que eu deveria fazer"
    """
    company = request.current_company
    
    if not company:
        return render(request, 'core/no_company.html')
    
    user = request.user
    
    # ===========================================
    # TREINAMENTOS - Meu Progresso
    # ===========================================
    trainings = Training.objects.filter(
        company=company,
        is_active=True
    ).prefetch_related('videos')
    
    user_progress = UserProgress.objects.filter(
        user=user,
        video__training__company=company
    ).select_related('video', 'video__training')
    
    training_progress = []
    total_videos_all = 0
    completed_videos_all = 0
    
    for training in trainings:
        total_videos = training.videos.count()
        watched_videos = user_progress.filter(
            video__training=training,
            completed=True
        ).count()
        
        total_videos_all += total_videos
        completed_videos_all += watched_videos
        
        progress_pct = (watched_videos / total_videos * 100) if total_videos > 0 else 0
        
        training_progress.append({
            'training': training,
            'total_videos': total_videos,
            'watched_videos': watched_videos,
            'progress_pct': round(progress_pct, 1),
            'is_completed': progress_pct == 100,
        })
    
    overall_training_progress = (completed_videos_all / total_videos_all * 100) if total_videos_all > 0 else 0
    
    # ===========================================
    # CHECKLISTS - O que fazer vs O que fiz
    # ===========================================
    checklists = Checklist.objects.filter(
        company=company,
        is_active=True
    ).prefetch_related('tasks', 'assigned_users')
    
    user_checklists = []
    for checklist in checklists:
        if not checklist.assigned_users.exists() or user in checklist.assigned_users.all():
            user_checklists.append(checklist)
    
    checklist_data = []
    total_tasks_today = 0
    completed_tasks_today = 0
    overdue_count = 0
    
    for checklist in user_checklists:
        period_key = checklist.get_current_period_key()
        tasks = checklist.tasks.filter(is_active=True)
        
        done_tasks = TaskDone.objects.filter(
            task__in=tasks,
            user=user,
            period_key=period_key
        ).values_list('task_id', flat=True)
        
        total = tasks.count()
        done = len(done_tasks)
        
        total_tasks_today += total
        completed_tasks_today += done
        
        is_overdue = checklist.is_overdue_for_user(user)
        if is_overdue:
            overdue_count += 1
        
        checklist_data.append({
            'checklist': checklist,
            'total_tasks': total,
            'done_tasks': done,
            'progress': (done / total * 100) if total > 0 else 0,
            'period_display': checklist.get_period_display(),
            'is_overdue': is_overdue,
        })
    
    # ===========================================
    # MINHAS RECOMPENSAS/MEDALHAS
    # ===========================================
    rewards = UserTrainingReward.objects.filter(
        user=user,
        training__company=company
    ).select_related('training').order_by('-earned_at')[:5]
    
    # Total de pontos
    total_points = user.total_points
    
    context = {
        'training_progress': training_progress,
        'overall_training_progress': round(overall_training_progress, 1),
        'checklist_data': checklist_data,
        'total_tasks_today': total_tasks_today,
        'completed_tasks_today': completed_tasks_today,
        'tasks_completion_rate': round((completed_tasks_today / total_tasks_today * 100) if total_tasks_today > 0 else 0, 1),
        'overdue_count': overdue_count,
        'rewards': rewards,
        'total_rewards': rewards.count(),
        'total_points': total_points,
    }
    
    return render(request, 'core/colaborador_dashboard.html', context)


@login_required
def gestor_dashboard(request):
    """
    Dashboard do Gestor - Visão Operacional.
    ACCESS: GESTOR
    Contexto: Ranking da equipe e status do dia
    """
    company = request.current_company
    
    if not company:
        return render(request, 'core/no_company.html')
    
    if not request.is_gestor and not request.user.is_superuser:
        return redirect('core:colaborador_dashboard')
    
    # ===========================================
    # KPIs PRINCIPAIS
    # ===========================================
    total_users = company.user_companies.filter(is_active=True).count()
    
    trainings = Training.objects.filter(company=company, is_active=True)
    total_trainings = trainings.count()
    
    checklists = Checklist.objects.filter(company=company, is_active=True)
    total_checklists = checklists.count()
    
    # ===========================================
    # RANKING DE COLABORADORES (por pontos e medalhas)
    # ===========================================
    ranking_users = User.objects.filter(
        user_companies__company=company,
        user_companies__is_active=True
    ).annotate(
        total_medalhas=Count('training_rewards', filter=Q(training_rewards__training__company=company)),
        total_videos=Count('training_progress', filter=Q(training_progress__completed=True, training_progress__video__training__company=company))
    ).order_by('-total_points', '-total_medalhas', '-total_videos')[:10]
    
    # ===========================================
    # STATUS DOS CHECKLISTS DE HOJE
    # ===========================================
    today_key = PeriodKeyHelper.get_period_key(PeriodKeyHelper.FREQUENCY_DAILY)
    
    # Total de tarefas ativas únicas da empresa (para referência)
    total_tasks_active = Task.objects.filter(
        checklist__company=company,
        checklist__is_active=True,
        is_active=True
    ).count()
    
    # Calcular total esperado de tarefas hoje (considerando colaboradores atribuídos)
    checklists_active = Checklist.objects.filter(
        company=company,
        is_active=True
    ).prefetch_related('tasks', 'assigned_users')
    
    total_expected_tasks = 0
    for checklist in checklists_active:
        # Contar tarefas ativas deste checklist
        tasks_count = checklist.tasks.filter(is_active=True).count()
        
        # Contar quantos colaboradores devem fazer este checklist
        if checklist.assigned_users.exists():
            # Checklist atribuído a usuários específicos
            assigned_count = checklist.assigned_users.filter(
                user_companies__company=company,
                user_companies__is_active=True
            ).distinct().count()
        else:
            # Checklist global (todos os colaboradores)
            assigned_count = total_users
        
        # Total esperado = tarefas * colaboradores
        total_expected_tasks += tasks_count * assigned_count
    
    # Tarefas concluídas hoje (por todos os colaboradores)
    tasks_done_today = TaskDone.objects.filter(
        task__checklist__company=company,
        period_key=today_key
    ).count()
    
    # Performance: (Total de TaskDone hoje / Total esperado) * 100, limitado a 100%
    if total_expected_tasks > 0:
        completion_rate = (tasks_done_today / total_expected_tasks * 100)
        checklist_completion_rate = round(min(completion_rate, 100.0), 1)
    else:
        checklist_completion_rate = 0
    
    # ===========================================
    # PROGRESSO MÉDIO DA EQUIPE EM TREINAMENTOS
    # ===========================================
    total_videos_all = sum(t.total_videos for t in trainings)
    
    if total_videos_all > 0 and total_users > 0:
        completed_videos = UserProgress.objects.filter(
            video__training__company=company,
            completed=True
        ).count()
        avg_training_progress = round((completed_videos / (total_videos_all * total_users)) * 100, 1)
    else:
        avg_training_progress = 0
    
    # ===========================================
    # ALERTAS DE EQUIPE (Checklists Atrasados)
    # ===========================================
    team_alerts = []
    company_users = User.objects.filter(
        user_companies__company=company,
        user_companies__is_active=True
    ).distinct()
    
    for user in company_users:
        user_checklists = Checklist.objects.filter(
            company=company,
            is_active=True
        ).filter(
            Q(assigned_users=user) | Q(assigned_users__isnull=True)
        ).distinct()
        
        overdue_count = 0
        overdue_checklists = []
        
        for checklist in user_checklists:
            if checklist.is_overdue_for_user(user):
                overdue_count += 1
                overdue_checklists.append(checklist.title)
        
        if overdue_count > 0:
            team_alerts.append({
                'user': user,
                'overdue_count': overdue_count,
                'overdue_checklists': overdue_checklists[:3],
            })
    
    team_alerts.sort(key=lambda x: x['overdue_count'], reverse=True)
    team_alerts = team_alerts[:5]
    
    # ===========================================
    # ANIVERSARIANTES DO MÊS
    # ===========================================
    current_month = timezone.now().month
    current_month_name = calendar.month_name[current_month]
    birthdays_month = User.objects.filter(
        user_companies__company=company,
        user_companies__is_active=True,
        birth_date__isnull=False
    ).filter(
        birth_date__month=current_month
    ).order_by('birth_date__day', 'first_name', 'last_name').distinct()
    
    # ===========================================
    # FEEDBACKS PENDENTES
    # ===========================================
    pending_feedback = FeedbackTicket.objects.filter(
        company=company,
        status='pending'
    ).count()
    
    # Sentimento médio (últimos 30 dias)
    month_ago = timezone.now() - timedelta(days=30)
    sentiment_stats = FeedbackTicket.objects.filter(
        company=company,
        created_at__gte=month_ago
    ).values('sentiment').annotate(count=Count('id'))
    
    # Converte para formato amigável para gráficos
    sentiment_data = {
        'great': 0, 'good': 0, 'neutral': 0, 'bad': 0, 'sad': 0
    }
    for stat in sentiment_stats:
        sentiment_data[stat['sentiment']] = stat['count']
    
    # ===========================================
    # DADOS PARA GRÁFICOS (Chart.js)
    # ===========================================
    # Progresso por treinamento
    training_chart_data = []
    for training in trainings[:5]:  # Top 5 treinamentos
        total_videos = training.total_videos
        if total_videos > 0:
            completed = UserProgress.objects.filter(
                video__training=training,
                completed=True
            ).count()
            avg_progress = round((completed / (total_videos * total_users)) * 100, 1) if total_users > 0 else 0
        else:
            avg_progress = 0
        training_chart_data.append({
            'name': training.title[:20],
            'progress': avg_progress
        })
    
    # ===========================================
    # ALERTAS DE CHECKLISTS (Tarefas Pendentes)
    # ===========================================
    today = timezone.now().date()
    checklist_alerts = ChecklistAlert.objects.filter(
        company=company,
        is_resolved=False,
        created_at__date=today
    ).select_related('user', 'checklist', 'task').order_by('-created_at')[:5]
    
    checklist_alerts_count = ChecklistAlert.objects.filter(
        company=company,
        is_resolved=False,
        created_at__date=today
    ).count()
    
    context = {
        'total_users': total_users,
        'total_trainings': total_trainings,
        'total_checklists': total_checklists,
        'ranking_users': ranking_users,
        'total_tasks_active': total_tasks_active,
        'tasks_done_today': tasks_done_today,
        'checklist_completion_rate': checklist_completion_rate,
        'avg_training_progress': avg_training_progress,
        'pending_feedback': pending_feedback,
        'sentiment_data': sentiment_data,
        'training_chart_data': training_chart_data,
        'team_alerts': team_alerts,
        'birthdays_month': birthdays_month,
        'current_month': current_month,
        'current_month_name': current_month_name,
        'checklist_alerts': checklist_alerts,
        'checklist_alerts_count': checklist_alerts_count,
    }
    
    return render(request, 'core/gestor_dashboard.html', context)


@login_required
def admin_dashboard(request):
    """
    Dashboard do Admin Master - Visão Global.
    ACCESS: ADMIN MASTER
    Contexto: KPIs comparativos entre empresas, NPS global
    """
    if not request.user.is_superuser:
        return redirect('core:dashboard')
    
    # ===========================================
    # KPIs GLOBAIS
    # ===========================================
    total_empresas = Company.objects.filter(is_active=True).count()
    total_usuarios = User.objects.filter(is_active=True).count()
    total_trainings = Training.objects.filter(is_active=True).count()
    total_checklists = Checklist.objects.filter(is_active=True).count()
    
    # ===========================================
    # DADOS DAS EMPRESAS PARA O SELETOR
    # ===========================================
    companies_qs = Company.objects.filter(is_active=True)
    
    companies_data = []
    sentiment_scores = {'great': 5, 'good': 4, 'neutral': 3, 'bad': 2, 'sad': 1}
    
    for company in companies_qs:
        # Total de colaboradores
        total_users = company.user_companies.filter(is_active=True).count()
        
        # Checklists: total aplicados vs concluídos
        company_checklists = Checklist.objects.filter(company=company, is_active=True).count()
        checklists_done = ChecklistCompletion.objects.filter(
            checklist__company=company
        ).count()
        
        # Performance de Checklists (%)
        checklist_performance = round((checklists_done / company_checklists * 100) if company_checklists > 0 else 0, 1)
        
        # Treinamentos: total aplicados vs concluídos
        company_trainings = Training.objects.filter(company=company, is_active=True).count()
        trainings_done = UserTrainingReward.objects.filter(
            training__company=company
        ).count()
        
        # Feedbacks: total recebidos vs resolvidos
        total_feedbacks = FeedbackTicket.objects.filter(company=company).count()
        feedbacks_resolved = FeedbackTicket.objects.filter(
            company=company,
            status__in=['resolved', 'closed']
        ).count()
        
        # NPS: Média aritmética dos sentimentos
        feedbacks = FeedbackTicket.objects.filter(company=company)
        if feedbacks.exists():
            total_score = sum(sentiment_scores.get(f.sentiment, 3) for f in feedbacks)
            nps_score = round(total_score / feedbacks.count(), 2)
        else:
            nps_score = 0
        
        companies_data.append({
            'id': company.id,
            'name': company.name,
            'total_users': total_users,
            'total_checklists': company_checklists,
            'checklists_done': checklists_done,
            'checklist_performance': checklist_performance,
            'total_trainings': company_trainings,
            'trainings_done': trainings_done,
            'total_feedbacks': total_feedbacks,
            'feedbacks_resolved': feedbacks_resolved,
            'nps_score': nps_score,
        })
    
    # Ordena por performance de checklists (ranking)
    companies_data.sort(key=lambda x: x['checklist_performance'], reverse=True)
    
    # NPS Global (média de todas as empresas)
    all_feedbacks = FeedbackTicket.objects.all()
    if all_feedbacks.exists():
        global_nps = round(
            sum(sentiment_scores.get(f.sentiment, 3) for f in all_feedbacks) / all_feedbacks.count(),
            2
        )
    else:
        global_nps = 0
    
    context = {
        'total_empresas': total_empresas,
        'total_usuarios': total_usuarios,
        'total_trainings': total_trainings,
        'total_checklists': total_checklists,
        'companies': companies_data,
        'global_nps': global_nps,
    }
    
    return render(request, 'core/admin_dashboard.html', context)


# =============================================================================
# Views para Admin Master - Gestão de Empresas
# =============================================================================

@login_required
def company_list(request):
    """
    Lista de empresas.
    ACCESS: ADMIN MASTER
    - Apenas Admin Master pode gerenciar empresas
    """
    if not request.user.is_superuser:
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('core:dashboard')
    
    # Parâmetro de ordenação
    sort_param = request.GET.get('sort', '-created_at')
    
    # Validação de ordenação permitida
    allowed_sorts = ['name', '-name', 'created_at', '-created_at', 'is_active', '-is_active']
    if sort_param not in allowed_sorts:
        sort_param = '-created_at'
    
    companies = Company.objects.all().select_related().order_by(sort_param)
    
    # Blindagem: garantir que todos os valores numéricos sejam seguros
    for company in companies:
        # Garantir que max_users e active_users_count nunca sejam None
        if company.max_users is None:
            company.max_users = 50
        if not hasattr(company, '_active_users_count_cached'):
            try:
                count = company.active_users_count
                company._active_users_count_cached = int(count) if count is not None else 0
            except Exception:
                company._active_users_count_cached = 0
    
    return render(request, 'core/companies/list.html', {
        'companies': companies,
        'current_sort': sort_param,
    })


@login_required
def company_create(request):
    """Criar nova empresa."""
    if not request.user.is_superuser:
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = CompanyForm(request.POST, request.FILES)
        if form.is_valid():
            company = form.save(commit=False)
            if not company.slug:
                company.slug = slugify(company.name)
            # Blindagem: garantir que max_users seja sempre um inteiro válido
            max_users = form.cleaned_data.get('max_users')
            company.max_users = int(max_users) if max_users is not None else 50
            company.save()
            
            # Criar cargos padrão
            default_roles = [
                {'name': 'Administrador', 'level': 'admin_master', 'description': 'Acesso total ao sistema'},
                {'name': 'Gestor', 'level': 'gestor', 'description': 'Gerencia equipes e conteúdos'},
                {'name': 'Colaborador', 'level': 'colaborador', 'description': 'Acesso básico'},
            ]
            for role_data in default_roles:
                Role.objects.create(company=company, **role_data)
            
            messages.success(request, f'Empresa "{company.name}" criada com sucesso!')
            return redirect('core:company_list')
    else:
        form = CompanyForm()
    
    return render(request, 'core/companies/form.html', {
        'form': form,
        'title': 'Nova Empresa'
    })


@login_required
def company_detail(request, pk):
    """Detalhes da empresa."""
    if not request.user.is_superuser:
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('core:dashboard')
    
    company = get_object_or_404(Company, pk=pk)
    roles = company.roles.all()
    users = company.user_companies.select_related('user', 'role').order_by('-is_active', 'user__first_name')
    
    # Form para adicionar cargo
    if request.method == 'POST' and 'add_role' in request.POST:
        role_form = RoleForm(request.POST)
        if role_form.is_valid():
            role = role_form.save(commit=False)
            role.company = company
            role.save()
            messages.success(request, f'Cargo "{role.name}" criado!')
            return redirect('core:company_detail', pk=pk)
    else:
        role_form = RoleForm()
    
    context = {
        'company': company,
        'roles': roles,
        'users': users,
        'role_form': role_form,
    }
    
    return render(request, 'core/companies/detail.html', context)


@login_required
def company_edit(request, pk):
    """Editar empresa."""
    if not request.user.is_superuser:
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('core:dashboard')
    
    company = get_object_or_404(Company, pk=pk)
    
    if request.method == 'POST':
        form = CompanyForm(request.POST, request.FILES, instance=company)
        if form.is_valid():
            # Blindagem: garantir que max_users seja sempre um inteiro válido
            company_instance = form.save(commit=False)
            max_users = form.cleaned_data.get('max_users')
            company_instance.max_users = int(max_users) if max_users is not None else 50
            company_instance.save()
            messages.success(request, 'Empresa atualizada!')
            return redirect('core:company_detail', pk=pk)
    else:
        form = CompanyForm(instance=company)
    
    return render(request, 'core/companies/form.html', {
        'form': form,
        'company': company,
        'title': 'Editar Empresa'
    })


@login_required
def company_users(request, pk):
    """Gestão de usuários da empresa."""
    if not request.user.is_superuser:
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('core:dashboard')
    
    from apps.accounts.models import User, UserCompany
    from apps.accounts.forms import AdminUserCreateForm
    
    company = get_object_or_404(Company, pk=pk)
    users = company.user_companies.select_related('user', 'role').order_by('-is_active', 'user__first_name')
    roles = company.roles.all()
    
    return render(request, 'core/companies/users.html', {
        'company': company,
        'users': users,
        'roles': roles,
    })


@login_required
def company_add_user(request, pk):
    """Criar novo usuário e vincular à empresa."""
    if not request.user.is_superuser:
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('core:dashboard')
    
    from apps.accounts.models import User, UserCompany
    from apps.accounts.forms import AdminUserCreateForm
    
    company = get_object_or_404(Company, pk=pk)
    
    if request.method == 'POST':
        form = AdminUserCreateForm(data=request.POST, company=company)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Cria o usuário
                    user = form.save(commit=False)
                    password = form.cleaned_data['password']
                    
                    # Salva campos adicionais (phone, neighborhood, city, birth_date)
                    user.phone = form.cleaned_data.get('phone', '')
                    user.neighborhood = form.cleaned_data.get('neighborhood', '')
                    user.city = form.cleaned_data.get('city', '')
                    user.birth_date = form.cleaned_data.get('birth_date')
                    
                    user.set_password(password)
                    user.save()
                    
                    # Vincula à empresa com o cargo selecionado
                    role = form.cleaned_data.get('role')
                    
                    # Gera matrícula automaticamente (EMPRESA-ANO-SEQUENCIAL)
                    import datetime
                    year = datetime.datetime.now().year
                    company_prefix = company.slug[:3].upper() if company.slug else 'EMP'
                    
                    # Busca última matrícula do ano
                    last_employee = UserCompany.objects.filter(
                        company=company,
                        employee_id__startswith=f'{company_prefix}-{year}-'
                    ).order_by('-employee_id').first()
                    
                    if last_employee and last_employee.employee_id:
                        try:
                            last_seq = int(last_employee.employee_id.split('-')[-1])
                            new_seq = last_seq + 1
                        except (ValueError, IndexError):
                            new_seq = 1
                    else:
                        new_seq = 1
                    
                    employee_id = f'{company_prefix}-{year}-{new_seq:04d}'
                    
                    UserCompany.objects.create(
                        user=user,
                        company=company,
                        role=role,
                        employee_id=employee_id,
                        is_active=True
                    )
                
                messages.success(request, f'Usuário "{user.get_full_name()}" criado e vinculado à empresa!')
                return redirect('core:company_users', pk=pk)
            except Exception as e:
                messages.error(request, f'Erro ao criar usuário: {str(e)}')
        else:
            # Exibe erros de validação
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = AdminUserCreateForm(company=company)
    
    return render(request, 'core/companies/user_form.html', {
        'form': form,
        'company': company,
        'title': 'Novo Usuário'
    })


# =============================================================================
# Views de Relatórios
# =============================================================================

from django.http import HttpResponse, Http404
from io import BytesIO
from django.template.loader import get_template


@login_required
@gestor_required
def report_management(request):
    """
    Interface de gerenciamento de relatórios.
    ACCESS: GESTOR | ADMIN MASTER
    """
    company = request.current_company
    
    if not company:
        messages.error(request, 'É necessário selecionar uma empresa.')
        return render(request, 'core/no_company.html')
    
    # Buscar usuários da empresa
    company_user_ids = UserCompany.objects.filter(
        company=company,
        is_active=True
    ).values_list('user_id', flat=True)
    
    users = User.objects.filter(
        id__in=company_user_ids,
        is_active=True
    ).order_by('first_name', 'last_name')
    
    # Valores padrão (mês atual)
    today = timezone.now().date()
    start_date = today.replace(day=1)  # Primeiro dia do mês
    end_date = today
    
    # Verificar se há parâmetros GET (se não houver, mostrar formulário)
    has_params = bool(request.GET.get('action') or request.GET.get('start_date') or request.GET.get('period'))
    
    if not has_params:
        # GET sem parâmetros: mostrar formulário
        return render(request, 'core/reports/management.html', {
            'users': users,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
        })
    
    # Processar formulário quando há parâmetros
    # Atalhos de período
    period = request.GET.get('period', '')
    if period == 'week':
        # Semana atual
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif period == 'month':
        # Mês atual
        start_date = today.replace(day=1)
        end_date = today
    elif period == 'quarter':
        # Últimos 3 meses
        end_date = today
        start_date = (end_date - timedelta(days=90)).replace(day=1)
    else:
        # Datas customizadas
        start_str = request.GET.get('start_date', '')
        end_str = request.GET.get('end_date', '')
        if start_str:
            try:
                start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if end_str:
            try:
                end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            except ValueError:
                pass
    
    # Usuário selecionado
    user_id = request.GET.get('user', '')
    user = None
    if user_id:
        try:
            user = get_object_or_404(User, pk=user_id)
            # Verificar segurança multi-tenant
            if not UserCompany.objects.filter(
                user=user,
                company=company,
                is_active=True
            ).exists():
                messages.error(request, 'Usuário não pertence à empresa selecionada.')
                user = None
        except (ValueError, Http404):
            messages.error(request, 'Usuário inválido.')
            user = None
    
    # Ação: Visualizar ou Baixar
    action = request.GET.get('action', 'view')
    
    if action == 'download':
        # Gerar PDF
        if user:
            return _generate_pdf(request, company, start_date, end_date, user)
        else:
            return _generate_collective_pdf(request, company, start_date, end_date)
    else:
        # Visualizar na tela
        if user:
            # Relatório Individual
            report_data = get_report_data(company, start_date, end_date, user)
            return render(request, 'core/reports/view.html', {
                'report_data': report_data,
                'users': users,
                'selected_user_id': user_id if user else '',
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'selected_period': period,
            })
        else:
            # Relatório Coletivo
            report_data = get_company_report_data(company, start_date, end_date)
            return render(request, 'core/reports/view_collective.html', {
                'report_data': report_data,
                'users': users,
                'selected_user_id': '',
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'selected_period': period,
            })


def _generate_pdf(request, company, start_date, end_date, user=None):
    """
    Gera PDF do relatório usando xhtml2pdf.
    """
    try:
        from xhtml2pdf import pisa
    except ImportError:
        messages.error(request, 'Biblioteca xhtml2pdf não está instalada.')
        return redirect('core:report_management')
    
    # Segurança multi-tenant
    if user:
        if not UserCompany.objects.filter(
            user=user,
            company=company,
            is_active=True
        ).exists():
            messages.error(request, 'Usuário não pertence à empresa selecionada.')
            return redirect('core:report_management')
        
        # Relatório Individual
        try:
            report_data = get_report_data(company, start_date, end_date, user)
            
            # Sanitizar todos os dados antes de enviar ao template
            if 'profile' in report_data:
                profile = report_data['profile']
                profile['name'] = str(profile.get('name', '---') or '---')
                profile['email'] = str(profile.get('email', '---') or '---')
                profile['phone'] = str(profile.get('phone', '---') or '---')
                profile['city'] = str(profile.get('city', '---') or '---')
                profile['neighborhood'] = str(profile.get('neighborhood', '---') or '---')
                profile['age'] = int(profile.get('age', 0) or 0)
                profile['birth_date'] = str(profile.get('birth_date', '---') or '---')
            
            if 'ranking' in report_data:
                ranking = report_data['ranking']
                ranking['position'] = int(ranking.get('position', 0) or 0)
                ranking['total_users'] = int(ranking.get('total_users', 0) or 0)
                ranking['total_points'] = int(ranking.get('total_points', 0) or 0)
            
            if 'checklists' in report_data:
                checklists = report_data['checklists']
                checklists['total_completed_period'] = int(checklists.get('total_completed_period', 0) or 0)
                checklists['total_tasks_completed_period'] = int(checklists.get('total_tasks_completed_period', 0) or 0)
                checklists['total_completed_all'] = int(checklists.get('total_completed_all', 0) or 0)
                checklists['total_tasks_completed_all'] = int(checklists.get('total_tasks_completed_all', 0) or 0)
                checklists['overdue_count'] = int(checklists.get('overdue_count', 0) or 0)
                checklists['total_overdue_days'] = int(checklists.get('total_overdue_days', 0) or 0)
                if 'completions' in checklists:
                    for comp in checklists['completions']:
                        comp['checklist'] = str(comp.get('checklist', '---') or '---')
                        comp['date'] = str(comp.get('date', '---') or '---')
                        comp['points'] = int(comp.get('points', 0) or 0)
            
            if 'trainings' in report_data:
                trainings = report_data['trainings']
                trainings['total_trainings'] = int(trainings.get('total_trainings', 0) or 0)
                trainings['avg_progress'] = int(trainings.get('avg_progress', 0) or 0)
                if 'trainings' in trainings:
                    for training in trainings['trainings']:
                        training['title'] = str(training.get('title', '---') or '---')
                        training['progress'] = int(training.get('progress', 0) or 0)
                        training['total_videos'] = int(training.get('total_videos', 0) or 0)
                        training['completed_videos'] = int(training.get('completed_videos', 0) or 0)
                        training['total_quizzes'] = int(training.get('total_quizzes', 0) or 0)
                        training['passed_quizzes'] = int(training.get('passed_quizzes', 0) or 0)
            
            if 'quizzes' in report_data:
                quizzes = report_data['quizzes']
                quizzes['avg_score'] = float(quizzes.get('avg_score', 0) or 0.0)
                quizzes['avg_score_period'] = float(quizzes.get('avg_score_period', 0) or 0.0)
                quizzes['total_attempts'] = int(quizzes.get('total_attempts', 0) or 0)
                quizzes['total_attempts_period'] = int(quizzes.get('total_attempts_period', 0) or 0)
                quizzes['total_passed'] = int(quizzes.get('total_passed', 0) or 0)
                quizzes['total_passed_period'] = int(quizzes.get('total_passed_period', 0) or 0)
                if 'attempts' in quizzes:
                    for attempt in quizzes['attempts']:
                        attempt['quiz_title'] = str(attempt.get('quiz_title', '---') or '---')
                        attempt['training_title'] = str(attempt.get('training_title', '---') or '---')
                        attempt['score'] = float(attempt.get('score', 0) or 0.0)
                        attempt['total_questions'] = int(attempt.get('total_questions', 0) or 0)
                        attempt['correct_answers'] = int(attempt.get('correct_answers', 0) or 0)
                        attempt['date'] = str(attempt.get('date', '---') or '---')
            
            if 'warnings' in report_data:
                warnings = report_data['warnings']
                warnings['total'] = int(warnings.get('total', 0) or 0)
                if 'warnings' in warnings:
                    for warning in warnings['warnings']:
                        warning['date'] = str(warning.get('date', '---') or '---')
                        warning['type'] = str(warning.get('type', '---') or '---')
                        warning['reason'] = str(warning.get('reason', '---') or '---')
                        warning['issuer'] = str(warning.get('issuer', 'Sistema') or 'Sistema')
        
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            messages.error(request, f'Erro ao extrair dados do relatório individual: {str(e)}')
            if settings.DEBUG:
                messages.error(request, f'Detalhes: {error_details}')
            return redirect('core:report_management')
        
        template_name = 'core/reports/pdf_template.html'
    else:
        # Relatório Coletivo
        report_data = get_company_report_data(company, start_date, end_date)
        template_name = 'core/reports/pdf_collective.html'
    
    # Renderizar template HTML
    template = get_template(template_name)
    html = template.render({'report_data': report_data, 'request': request})
    
    # Gerar PDF
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode('UTF-8')), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        filename = f'relatorio_{company.slug}'
        if user:
            filename += f'_{user.get_full_name().replace(" ", "_")}'
        filename += f'_{start_date}_{end_date}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    else:
        messages.error(request, 'Erro ao gerar PDF. Tente novamente.')
        return redirect('core:report_management')


def _generate_collective_pdf(request, company, start_date, end_date):
    """
    Gera PDF do relatório coletivo usando xhtml2pdf.
    """
    try:
        from xhtml2pdf import pisa
    except ImportError:
        messages.error(request, 'Biblioteca xhtml2pdf não está instalada.')
        return redirect('core:report_management')
    
    # Extrair dados do relatório coletivo
    try:
        report_data = get_company_report_data(company, start_date, end_date)
        
        # BLINDAGEM TOTAL: Garantir que TODOS os valores sejam seguros
        # Valores principais
        report_data['checklist_average'] = float(report_data.get('checklist_average', 0) or 0.0)
        report_data['training_average'] = float(report_data.get('training_average', 0) or 0.0)
        report_data['quiz_average_all'] = float(report_data.get('quiz_average_all', 0) or 0.0)
        report_data['total_warnings'] = int(report_data.get('total_warnings', 0) or 0)
        report_data['total_completions'] = int(report_data.get('total_completions', 0) or 0)
        report_data['total_tasks_completed'] = int(report_data.get('total_tasks_completed', 0) or 0)
        report_data['total_users'] = int(report_data.get('total_users', 0) or 0)
        
        # Warnings by type
        if 'warnings_by_type' in report_data:
            wbt = report_data['warnings_by_type']
            report_data['warnings_by_type'] = {
                'oral': int(wbt.get('oral', 0) or 0),
                'escrita': int(wbt.get('escrita', 0) or 0),
                'suspensao': int(wbt.get('suspensao', 0) or 0),
            }
        
        # Performance data - sanitizar TODOS os itens
        if 'performance_data' in report_data:
            for item in report_data['performance_data']:
                item['name'] = str(item.get('name', '-') or '-')
                item['email'] = str(item.get('email', '-') or '-')
                item['checklist_percentage'] = float(item.get('checklist_percentage', 0) or 0.0)
                item['training_percentage'] = float(item.get('training_percentage', 0) or 0.0)
                item['quiz_average'] = float(item.get('quiz_average', 0) or 0.0)
                item['points_earned'] = int(item.get('points_earned', 0) or 0)
                item['warnings_count'] = int(item.get('warnings_count', 0) or 0)
                item['checklist_overdue'] = int(item.get('checklist_overdue', 0) or 0)
                item['attention_score'] = int(item.get('attention_score', 0) or 0)
        
        # Top 3 - sanitizar TODOS os itens
        if 'top_3' in report_data:
            for item in report_data['top_3']:
                item['name'] = str(item.get('name', '-') or '-')
                item['points_earned'] = int(item.get('points_earned', 0) or 0)
                item['checklist_percentage'] = float(item.get('checklist_percentage', 0) or 0.0)
                item['training_percentage'] = float(item.get('training_percentage', 0) or 0.0)
                item['quiz_average'] = float(item.get('quiz_average', 0) or 0.0)
        
        # Attention list - sanitizar TODOS os itens
        if 'attention_list' in report_data:
            for item in report_data['attention_list']:
                item['name'] = str(item.get('name', '-') or '-')
                item['attention_score'] = int(item.get('attention_score', 0) or 0)
                item['checklist_overdue'] = int(item.get('checklist_overdue', 0) or 0)
                item['warnings_count'] = int(item.get('warnings_count', 0) or 0)
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        messages.error(request, f'Erro ao extrair dados do relatório: {str(e)}')
        if settings.DEBUG:
            messages.error(request, f'Detalhes: {error_details}')
        return redirect('core:report_management')
    
    # Renderizar template HTML
    template = get_template('core/reports/pdf_collective.html')
    html = template.render({'report_data': report_data, 'request': request})
    
    # Gerar PDF
    result = BytesIO()
    
    try:
        # Configurar pisaDocument com encoding e opções para garantir landscape
        pdf = pisa.pisaDocument(
            BytesIO(html.encode('UTF-8')),
            result,
            encoding='UTF-8',
            link_callback=None
        )
        
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            # Nome do arquivo formatado
            filename = f'relatorio_coletivo_{company.slug}_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.pdf'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        else:
            error_msg = str(pdf.err) if pdf.err else 'Erro desconhecido'
            messages.error(request, f'Erro ao gerar PDF coletivo: {error_msg}')
            return redirect('core:report_management')
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        messages.error(request, f'Erro ao gerar PDF: {str(e)}')
        # Em desenvolvimento, podemos logar o erro completo
        if settings.DEBUG:
            print(f"Erro detalhado no PDF: {error_details}")
        return redirect('core:report_management')

