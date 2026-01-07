"""
Serviço de Relatórios - Extração de dados para relatórios consolidados.

Este módulo é responsável por extrair, agregar e sanitizar dados para os relatórios
individuais e coletivos da plataforma Mindpulse. Todas as funções implementam
proteção robusta contra NoneType e garantem que valores numéricos sejam sempre
retornados como int/float, nunca None.

Princípios aplicados:
- DRY: Funções utilitárias para sanitização reutilizáveis
- Fail-Safe: Sempre retorna valores padrão seguros (0, 0.0, '---')
- Type Safety: Type hints para melhor autocomplete e validação
- Performance: Uso de select_related e prefetch_related onde aplicável
"""

from typing import Dict, List, Optional, Any, Union
from django.db.models import Count, Q, Avg, Sum, Value, IntegerField, FloatField, QuerySet
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta, date

from apps.accounts.models import User, Warning
from apps.checklists.models import Checklist, TaskDone, ChecklistCompletion
from apps.trainings.models import Training, UserProgress, UserQuizAttempt, UserTrainingReward
from apps.core.models import Company
from apps.core.utils import (
    PeriodKeyHelper,
    safe_int,
    safe_float,
    safe_str,
    safe_date_format,
    safe_division,
)


def get_report_data(
    company: Company,
    start_date: Union[str, date],
    end_date: Union[str, date],
    user: Optional[User] = None
) -> Dict[str, Any]:
    """
    Extrai dados consolidados para relatório individual ou coletivo.
    
    Esta é a função principal de entrada para geração de relatórios. Ela
    orquestra a coleta de dados de diferentes módulos (checklists, trainings,
    quizzes, warnings) e retorna um dicionário estruturado.
    
    Args:
        company: Instância da Company para filtrar dados
        start_date: Data de início do período (str 'YYYY-MM-DD' ou date)
        end_date: Data de fim do período (str 'YYYY-MM-DD' ou date)
        user: Usuário específico. Se None, retorna dados agregados da empresa
    
    Returns:
        Dict contendo:
            - company: Instância da Company
            - start_date, end_date: Datas do período
            - generated_at: Timestamp de geração
            - Se user fornecido: profile, ranking, checklists, trainings, quizzes, warnings
            - Se user=None: users, summary
    
    Example:
        >>> report_data = get_report_data(company, '2026-01-01', '2026-01-31', user)
        >>> print(report_data['profile']['name'])
    """
    # Converter para datetime se necessário
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Converter para datetime para filtros
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
    
    data = {
        'company': company,
        'start_date': start_date,
        'end_date': end_date,
        'generated_at': timezone.now(),
    }
    
    # Se user específico foi fornecido, filtrar apenas esse usuário
    if user:
        data['user'] = user
        data['profile'] = _get_user_profile(user)
        data['ranking'] = _get_user_ranking(user, company)
        data['checklists'] = _get_user_checklists(user, company, start_datetime, end_datetime)
        data['trainings'] = _get_user_trainings(user, company, start_datetime, end_datetime)
        data['quizzes'] = _get_user_quizzes(user, company, start_datetime, end_datetime)
        data['warnings'] = _get_user_warnings(user, company, start_datetime, end_datetime)
    else:
        # Dados agregados da empresa
        data['users'] = _get_company_users(company)
        data['summary'] = _get_company_summary(company, start_datetime, end_datetime)
    
    return data


def _get_user_profile(user: User) -> Dict[str, Union[str, int]]:
    """
    Extrai e sanitiza dados do perfil do usuário.
    
    Calcula idade de forma segura e garante que todos os campos retornem
    valores válidos (nunca None) para uso em templates e PDFs.
    
    Args:
        user: Instância do User
    
    Returns:
        Dict com dados sanitizados do perfil:
            - name: Nome completo ou 'Não informado'
            - email: Email ou 'Não informado'
            - age: Idade calculada (int, sempre >= 0)
            - phone, city, neighborhood: Dados de contato ou 'Não informado'
            - birth_date: Data formatada ou 'Não informado'
    """
    # Calcular idade de forma segura
    age = 0
    if user.birth_date:
        try:
            today = date.today()
            age = today.year - user.birth_date.year - (
                (today.month, today.day) < (user.birth_date.month, user.birth_date.day)
            )
            age = max(0, age)  # Garantir que idade nunca seja negativa
        except (AttributeError, TypeError):
            age = 0
    
    return {
        'name': safe_str(user.get_full_name(), 'Não informado'),
        'email': safe_str(user.email, 'Não informado'),
        'age': safe_int(age, 0),
        'phone': safe_str(user.phone, 'Não informado'),
        'city': safe_str(user.city, 'Não informado'),
        'neighborhood': safe_str(user.neighborhood, 'Não informado'),
        'birth_date': safe_date_format(user.birth_date, '%d/%m/%Y', 'Não informado'),
    }


def _get_user_ranking(user: User, company: Company) -> Dict[str, int]:
    """
    Calcula a posição do usuário no ranking da empresa.
    
    O ranking é baseado em: total_points, total_medalhas (training rewards),
    e total_videos completados. Todos os valores são sanitizados para evitar
    NoneType errors.
    
    Args:
        user: Instância do User para calcular ranking
        company: Instância da Company para filtrar ranking
    
    Returns:
        Dict com:
            - position: Posição no ranking (1-based, int sempre >= 1)
            - total_users: Total de usuários na empresa (int sempre >= 0)
            - total_points: Pontos totais do usuário (int sempre >= 0)
    """
    # Query otimizada: busca usuários ativos com agregações
    ranking_users: QuerySet[User] = User.objects.filter(
        user_companies__company=company,
        user_companies__is_active=True
    ).annotate(
        total_medalhas=Count(
            'training_rewards',
            filter=Q(training_rewards__training__company=company)
        ),
        total_videos=Count(
            'training_progress',
            filter=Q(
                training_progress__completed=True,
                training_progress__video__training__company=company
            )
        )
    ).order_by('-total_points', '-total_medalhas', '-total_videos')
    
    # Encontrar posição do usuário no ranking
    position = 1
    for rank_user in ranking_users:
        if rank_user.id == user.id:
            break
        position += 1
    
    total_users_count = ranking_users.count()
    
    return {
        'position': safe_int(position, 1),
        'total_users': safe_int(total_users_count, 0),
        'total_points': safe_int(getattr(user, 'total_points', None), 0),
    }


def _get_user_checklists(
    user: User,
    company: Company,
    start_datetime: datetime,
    end_datetime: datetime
) -> Dict[str, Any]:
    """
    Extrai e sanitiza dados de checklists do usuário.
    
    Calcula completions no período e totais, conta tarefas completadas,
    e identifica checklists atrasados (apenas se não foram completados
    no período atual - lógica anti-false-positive).
    
    Args:
        user: Instância do User
        company: Instância da Company
        start_datetime: Início do período (timezone-aware)
        end_datetime: Fim do período (timezone-aware)
    
    Returns:
        Dict com dados sanitizados de checklists:
            - total_completed_period: Checklists completados no período (int)
            - total_tasks_completed_period: Tarefas completadas no período (int)
            - total_completed_all: Checklists completados (total histórico) (int)
            - total_tasks_completed_all: Tarefas completadas (total histórico) (int)
            - overdue_count: Checklists atrasados não completados (int)
            - total_overdue_days: Dias de atraso acumulados (int)
            - completions: Lista de últimos 20 completions com detalhes
    """
    # Completions no período
    completions_period = ChecklistCompletion.objects.filter(
        user=user,
        checklist__company=company,
        completed_at__gte=start_datetime,
        completed_at__lte=end_datetime
    ).select_related('checklist')

    # Completions totais (para estatísticas gerais)
    completions_all = ChecklistCompletion.objects.filter(
        user=user,
        checklist__company=company,
    ).select_related('checklist')
    
    total_completed_period = safe_int(completions_period.count(), 0)
    total_completed_all = safe_int(completions_all.count(), 0)
    
    # TaskDones no período
    task_dones_period = TaskDone.objects.filter(
        user=user,
        task__checklist__company=company,
        completed_at__gte=start_datetime,
        completed_at__lte=end_datetime
    ).select_related('task', 'task__checklist')

    # TaskDones totais
    task_dones_all = TaskDone.objects.filter(
        user=user,
        task__checklist__company=company,
    ).select_related('task', 'task__checklist')
    
    total_tasks_completed_period = safe_int(task_dones_period.count(), 0)
    total_tasks_completed_all = safe_int(task_dones_all.count(), 0)
    
    # Contador de atrasos e dias de atraso (apenas checklists não finalizados)
    overdue_count = 0
    total_overdue_days = 0
    user_checklists = Checklist.objects.filter(
        company=company,
        is_active=True
    ).filter(
        Q(assigned_users=user) | Q(assigned_users__isnull=True)
    ).distinct().prefetch_related('tasks')
    
    # Para cada checklist, verificar se está atrasado E não foi finalizado no período atual
    for checklist in user_checklists:
        current_period = checklist.get_current_period_key()
        is_completed_current = checklist.is_completed_by(user, current_period)
        
        # Só conta como atrasado se NÃO foi completado no período atual
        if not is_completed_current and checklist.is_overdue_for_user(user):
            overdue_count += 1
            # Calcular dias de atraso: dias desde o fim do período anterior até hoje
            # Simplificado: considerar 1 dia por checklist atrasado no período
            # (pode ser refinado no futuro para cálculo mais preciso)
            total_overdue_days += 1
    
    completions_list: List[Dict[str, Union[str, int]]] = []
    for comp in completions_period[:20]:  # Limitar a 20 mais recentes do período
        completions_list.append({
            'checklist': safe_str(comp.checklist.title if comp.checklist else None, '---'),
            'date': safe_date_format(comp.completed_at, '%d/%m/%Y', '---'),
            'points': safe_int(comp.points_earned, 0),
        })
    
    return {
        'total_completed_period': safe_int(total_completed_period, 0),
        'total_tasks_completed_period': safe_int(total_tasks_completed_period, 0),
        'total_completed_all': safe_int(total_completed_all, 0),
        'total_tasks_completed_all': safe_int(total_tasks_completed_all, 0),
        'overdue_count': safe_int(overdue_count, 0),
        'total_overdue_days': safe_int(total_overdue_days, 0),
        'completions': completions_list,
    }


def _get_user_trainings(
    user: User,
    company: Company,
    start_datetime: datetime,
    end_datetime: datetime
) -> Dict[str, Any]:
    """
    Extrai dados de treinamentos do usuário com progresso atual.
    
    Mostra TODOS os treinamentos atribuídos ao usuário (não apenas do período),
    incluindo progresso em vídeos e quizzes. Todos os valores são sanitizados.
    
    Args:
        user: Instância do User
        company: Instância da Company
        start_datetime: Início do período (timezone-aware) - não usado atualmente
        end_datetime: Fim do período (timezone-aware) - não usado atualmente
    
    Returns:
        Dict com:
            - trainings: Lista de treinamentos com progresso
            - total_trainings: Total de treinamentos (int)
            - avg_progress: Progresso médio em % (int, 0-100)
    """
    # Treinamentos atribuídos ao usuário ou globais (query otimizada)
    trainings: QuerySet[Training] = Training.objects.filter(
        company=company,
        is_active=True
    ).filter(
        Q(assigned_users=user) | Q(assigned_users__isnull=True)
    ).distinct().prefetch_related('videos', 'quizzes', 'assigned_users')
    
    training_list = []
    total_progress = 0
    
    for training in trainings:
        # Progresso do usuário no treinamento (TODOS os vídeos, não apenas do período)
        # Query otimizada: usar prefetch_related já carregado
        total_videos = safe_int(training.videos.filter(is_active=True).count(), 0)
        completed_videos = safe_int(
            UserProgress.objects.filter(
                user=user,
                video__training=training,
                completed=True
            ).count(),
            0
        )
        
        # Verificar quizzes (TODOS os quizzes)
        quizzes = training.quizzes.filter(is_active=True)
        total_quizzes = safe_int(quizzes.count(), 0)
        
        # Quizzes aprovados (verificar se o usuário passou em pelo menos uma tentativa de cada quiz)
        passed_quizzes = 0
        for quiz in quizzes:
            if UserQuizAttempt.objects.filter(
                user=user,
                quiz=quiz,
                is_passed=True
            ).exists():
                passed_quizzes += 1
        passed_quizzes = safe_int(passed_quizzes, 0)
        
        # Progresso geral (vídeos + quizzes) - divisão segura
        total_content = total_videos + total_quizzes
        if total_content > 0:
            progress = safe_division(
                completed_videos + passed_quizzes,
                total_content,
                0.0
            ) * 100.0
            progress = safe_int(round(progress), 0)
        else:
            progress = 0
        total_progress += progress
        
        # Verificar se foi iniciado
        first_access = UserProgress.objects.filter(
            user=user,
            video__training=training
        ).order_by('created_at').first()
        
        is_started = first_access is not None
        is_completed = progress >= 100
        
        training_list.append({
            'title': safe_str(training.title, '---'),
            'progress': safe_int(progress, 0),
            'is_completed': bool(is_completed),
            'is_started': bool(is_started),
            'total_videos': safe_int(total_videos, 0),
            'completed_videos': safe_int(completed_videos, 0),
            'total_quizzes': safe_int(total_quizzes, 0),
            'passed_quizzes': safe_int(passed_quizzes, 0),
        })
    
    # Calcular média de progresso (divisão segura)
    avg_progress = safe_division(total_progress, len(training_list), 0.0) if training_list else 0.0
    avg_progress = safe_int(round(avg_progress), 0)
    
    return {
        'trainings': training_list,
        'total_trainings': safe_int(len(training_list), 0),
        'avg_progress': safe_int(avg_progress, 0),
    }


def _get_user_quizzes(user, company, start_datetime, end_datetime):
    """
    Extrai dados de quizzes do usuário.
    Mostra tentativas do período, mas também estatísticas gerais.
    """
    # Tentativas no período
    attempts_period = UserQuizAttempt.objects.filter(
        user=user,
        quiz__training__company=company,
        completed_at__gte=start_datetime,
        completed_at__lte=end_datetime
    ).select_related('quiz', 'quiz__training').order_by('-completed_at')
    
    # TODAS as tentativas (para estatísticas gerais)
    attempts_all = UserQuizAttempt.objects.filter(
        user=user,
        quiz__training__company=company
    ).select_related('quiz', 'quiz__training')
    
    if not attempts_all.exists():
        return {
            'avg_score': 0,
            'avg_score_period': 0,
            'total_attempts': 0,
            'total_attempts_period': 0,
            'total_passed': 0,
            'total_passed_period': 0,
            'attempts': [],
        }
    
    # Estatísticas gerais (todas as tentativas)
    avg_score_all_result = attempts_all.aggregate(avg=Coalesce(Avg('score'), Value(0.0), output_field=FloatField()))
    avg_score_all = float(avg_score_all_result['avg'] or 0.0)
    total_passed_all = int(attempts_all.filter(is_passed=True).count() or 0)
    
    # Estatísticas do período
    if attempts_period.exists():
        avg_score_period_result = attempts_period.aggregate(avg=Coalesce(Avg('score'), Value(0.0), output_field=FloatField()))
        avg_score_period = float(avg_score_period_result['avg'] or 0.0)
        total_passed_period = int(attempts_period.filter(is_passed=True).count() or 0)
    else:
        avg_score_period = 0.0
        total_passed_period = 0
    
    attempts_list = []
    for attempt in attempts_period[:20]:  # Limitar a 20 mais recentes do período
        attempts_list.append({
            'quiz_title': str(attempt.quiz.title) if attempt.quiz.title else '---',
            'training_title': str(attempt.quiz.training.title) if attempt.quiz.training.title else '---',
            'score': float(attempt.score) if attempt.score is not None else 0.0,
            'is_passed': bool(attempt.is_passed) if attempt.is_passed is not None else False,
            'date': attempt.completed_at.strftime('%d/%m/%Y %H:%M') if attempt.completed_at else '---',
            'total_questions': int(attempt.total_questions) if attempt.total_questions is not None else 0,
            'correct_answers': int(attempt.correct_answers) if attempt.correct_answers is not None else 0,
        })
    
    return {
        'avg_score': float(round(avg_score_all, 1) or 0.0),  # Média geral
        'avg_score_period': float(round(avg_score_period, 1) or 0.0),  # Média do período
        'total_attempts': int(attempts_all.count() or 0),  # Total geral
        'total_attempts_period': int(attempts_period.count() or 0),  # Total do período
        'total_passed': int(total_passed_all or 0),  # Aprovados geral
        'total_passed_period': int(total_passed_period or 0),  # Aprovados no período
        'attempts': attempts_list,
    }


def _get_user_warnings(user, company, start_datetime, end_datetime):
    """
    Extrai advertências do usuário.
    IMPORTANTE: Mostra TODAS as advertências do usuário, não apenas do período,
    pois advertências são históricas e devem aparecer sempre no relatório.
    """
    # Buscar TODAS as advertências do usuário na empresa (sem filtro de período)
    warnings = Warning.objects.filter(
        user=user,
        company=company
    ).select_related('issuer').order_by('-created_at')
    
    warnings_list = []
    for warning in warnings:
        warnings_list.append({
            'date': warning.created_at.strftime('%d/%m/%Y') if warning.created_at else '---',
            'type': str(warning.get_warning_type_display()) if warning.warning_type else '---',
            'reason': str(warning.reason) if warning.reason else '---',
            'issuer': str(warning.issuer.get_full_name()) if warning.issuer and warning.issuer.get_full_name() else 'Sistema',
        })
    
    return {
        'total': int(warnings.count() or 0),
        'warnings': warnings_list,
    }


def _get_company_users(company):
    """Retorna lista de usuários da empresa."""
    users = User.objects.filter(
        user_companies__company=company,
        user_companies__is_active=True
    ).distinct().order_by('first_name', 'last_name')
    
    return [
        {
            'id': user.id,
            'name': user.get_full_name(),
            'email': user.email,
        }
        for user in users
    ]


def _get_company_summary(company, start_datetime, end_datetime):
    """Retorna resumo agregado da empresa."""
    # Este método pode ser expandido no futuro
    return {
        'total_users': User.objects.filter(
            user_companies__company=company,
            user_companies__is_active=True
        ).count(),
        'total_checklists': Checklist.objects.filter(
            company=company,
            is_active=True
        ).count(),
        'total_trainings': Training.objects.filter(
            company=company,
            is_active=True
        ).count(),
    }


def get_company_report_data(company, start_date, end_date):
    """
    Extrai dados consolidados para relatório coletivo da loja.
    
    Args:
        company: Empresa para filtrar dados
        start_date: Data de início do período
        end_date: Data de fim do período
    
    Returns:
        dict: Dicionário com dados agregados da loja
    """
    # Converter para datetime se necessário
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Converter para datetime para filtros
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
    
    # Buscar todos os colaboradores ativos da empresa
    company_users = User.objects.filter(
        user_companies__company=company,
        user_companies__is_active=True
    ).distinct().prefetch_related('user_companies')
    
    # ===========================================
    # KPIs CONSOLIDADOS DA LOJA
    # ===========================================
    
    # 1. MÉDIA DE CHECKLIST: % total de tarefas concluídas vs. esperadas
    total_checklists = Checklist.objects.filter(
        company=company,
        is_active=True
    ).prefetch_related('tasks', 'assigned_users')
    
    total_tasks_expected = 0
    total_tasks_completed = 0
    total_completions = 0
    
    for checklist in total_checklists:
        tasks = checklist.tasks.filter(is_active=True)
        task_count = int(tasks.count() or 0)
        user_count = int(company_users.count() or 0)
        total_tasks_expected += task_count * user_count
        
        # Contar tarefas concluídas no período
        task_dones = int(TaskDone.objects.filter(
            task__in=tasks,
            completed_at__gte=start_datetime,
            completed_at__lte=end_datetime
        ).count() or 0)
        total_tasks_completed += task_dones
        
        # Contar checklist completions no período
        completions = int(ChecklistCompletion.objects.filter(
            checklist=checklist,
            completed_at__gte=start_datetime,
            completed_at__lte=end_datetime
        ).count() or 0)
        total_completions += completions
    
    checklist_average = round((float(total_tasks_completed) / float(total_tasks_expected) * 100) if total_tasks_expected > 0 else 0.0, 1)
    checklist_average = float(checklist_average) if checklist_average is not None else 0.0
    
    # 2. MÉDIA DE TREINAMENTO: % médio de conclusão de vídeos e quizzes
    trainings = Training.objects.filter(
        company=company,
        is_active=True
    ).prefetch_related('videos', 'quizzes', 'assigned_users')
    
    total_progress_sum = 0
    total_users_with_trainings = 0
    
    for training in trainings:
        total_videos = int(training.videos.filter(is_active=True).count() or 0)
        total_quizzes = int(training.quizzes.filter(is_active=True).count() or 0)
        total_content = total_videos + total_quizzes
        
        if total_content == 0:
            continue
        
        # Para cada usuário, calcular progresso no treinamento
        for user in company_users:
            completed_videos = int(UserProgress.objects.filter(
                user=user,
                video__training=training,
                completed=True
            ).count() or 0)
            
            passed_quizzes = 0
            for quiz in training.quizzes.filter(is_active=True):
                if UserQuizAttempt.objects.filter(
                    user=user,
                    quiz=quiz,
                    is_passed=True
                ).exists():
                    passed_quizzes += 1
            passed_quizzes = int(passed_quizzes)
            
            if total_content > 0:
                progress = ((float(completed_videos) + float(passed_quizzes)) / float(total_content)) * 100.0
                progress = float(progress) if progress is not None else 0.0
                total_progress_sum += progress
                total_users_with_trainings += 1
    
    training_average = round((float(total_progress_sum) / float(total_users_with_trainings)) if total_users_with_trainings > 0 else 0.0, 1)
    training_average = float(training_average) if training_average is not None else 0.0
    
    # 3. TOTAL DE ADVERTÊNCIAS: Contagem por tipo no período
    warnings_period = Warning.objects.filter(
        company=company,
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).select_related('user', 'issuer')
    
    # Garantir que todas as contagens sejam inteiros seguros
    oral_count = warnings_period.filter(warning_type='oral').count()
    escrita_count = warnings_period.filter(warning_type='escrita').count()
    suspensao_count = warnings_period.filter(warning_type='suspensao').count()
    
    warnings_by_type = {
        'oral': int(oral_count or 0) if oral_count is not None else 0,
        'escrita': int(escrita_count or 0) if escrita_count is not None else 0,
        'suspensao': int(suspensao_count or 0) if suspensao_count is not None else 0,
    }
    total_warnings = int(sum(warnings_by_type.values()) or 0)
    
    # ===========================================
    # TABELA DE PERFORMANCE POR COLABORADOR
    # ===========================================
    performance_data = []
    
    for user in company_users:
        # Checklists: % Concluído e dias de atraso
        user_checklists = Checklist.objects.filter(
            company=company,
            is_active=True
        ).filter(
            Q(assigned_users=user) | Q(assigned_users__isnull=True)
        ).distinct()
        
        user_tasks_expected = 0
        user_tasks_completed = 0
        user_overdue_count = 0
        
        for checklist in user_checklists:
            tasks = checklist.tasks.filter(is_active=True)
            user_tasks_expected += int(tasks.count() or 0)
            
            task_dones = int(TaskDone.objects.filter(
                task__in=tasks,
                user=user,
                completed_at__gte=start_datetime,
                completed_at__lte=end_datetime
            ).count() or 0)
            user_tasks_completed += task_dones
            
            # Incoerência Lógica: Só conta como atrasado se NÃO foi completado no período atual
            current_period = checklist.get_current_period_key()
            is_completed_current = checklist.is_completed_by(user, current_period)
            
            if not is_completed_current and checklist.is_overdue_for_user(user):
                user_overdue_count += 1
        
        checklist_percentage = round((float(user_tasks_completed) / float(user_tasks_expected) * 100) if user_tasks_expected > 0 else 0.0, 1)
        checklist_percentage = float(checklist_percentage) if checklist_percentage is not None else 0.0
        
        # Treinamentos: % Progresso e Quizzes (média de notas)
        user_trainings = Training.objects.filter(
            company=company,
            is_active=True
        ).filter(
            Q(assigned_users=user) | Q(assigned_users__isnull=True)
        ).distinct()
        
        user_training_progress_sum = 0
        user_training_count = 0
        user_quiz_scores = []
        
        for training in user_trainings:
            total_videos = int(training.videos.filter(is_active=True).count() or 0)
            total_quizzes = int(training.quizzes.filter(is_active=True).count() or 0)
            total_content = total_videos + total_quizzes
            
            if total_content == 0:
                continue
            
            completed_videos = int(UserProgress.objects.filter(
                user=user,
                video__training=training,
                completed=True
            ).count() or 0)
            
            passed_quizzes = 0
            for quiz in training.quizzes.filter(is_active=True):
                attempts = UserQuizAttempt.objects.filter(
                    user=user,
                    quiz=quiz,
                    completed_at__gte=start_datetime,
                    completed_at__lte=end_datetime
                )
                if attempts.exists():
                    avg_score_result = attempts.aggregate(avg=Coalesce(Avg('score'), Value(0.0), output_field=FloatField()))
                    avg_score = float(avg_score_result.get('avg') or 0.0)
                    user_quiz_scores.append(avg_score)
                
                if attempts.filter(is_passed=True).exists():
                    passed_quizzes += 1
            passed_quizzes = int(passed_quizzes)
            
            if total_content > 0:
                progress = ((float(completed_videos) + float(passed_quizzes)) / float(total_content)) * 100.0
                progress = float(progress) if progress is not None else 0.0
                user_training_progress_sum += progress
                user_training_count += 1
        
        training_percentage = round((float(user_training_progress_sum) / float(user_training_count)) if user_training_count > 0 else 0.0, 1)
        training_percentage = float(training_percentage) if training_percentage is not None else 0.0
        
        quiz_average = round((sum(user_quiz_scores) / len(user_quiz_scores)) if user_quiz_scores else 0.0, 1)
        quiz_average = float(quiz_average) if quiz_average is not None else 0.0
        
        # Advertências: Quantidade no período
        user_warnings_query = warnings_period.filter(user=user)
        user_warnings_count_result = user_warnings_query.count()
        user_warnings_count = int(user_warnings_count_result or 0) if user_warnings_count_result is not None else 0
        
        # Pontos: Saldo de pontos ganhos no intervalo
        # Calcular pontos ganhos no período (checklist completions + training rewards)
        points_from_checklists_result = ChecklistCompletion.objects.filter(
            user=user,
            checklist__company=company,
            completed_at__gte=start_datetime,
            completed_at__lte=end_datetime
        ).aggregate(total=Coalesce(Sum('points_earned'), Value(0), output_field=IntegerField()))
        points_from_checklists = int(points_from_checklists_result['total'] or 0)
        
        points_from_trainings_result = UserTrainingReward.objects.filter(
            user=user,
            training__company=company,
            earned_at__gte=start_datetime,
            earned_at__lte=end_datetime
        ).aggregate(total=Coalesce(Sum('points_earned'), Value(0), output_field=IntegerField()))
        points_from_trainings = int(points_from_trainings_result['total'] or 0)
        
        points_earned = int((points_from_checklists or 0) + (points_from_trainings or 0))
        
        performance_data.append({
            'user': user,
            'name': str(user.get_full_name() or '-'),
            'email': str(user.email or '-'),
            'checklist_percentage': float(checklist_percentage or 0.0),
            'checklist_overdue': int(user_overdue_count or 0),
            'training_percentage': float(training_percentage or 0.0),
            'quiz_average': float(quiz_average or 0.0),
            'warnings_count': int(user_warnings_count or 0),
            'points_earned': int(points_earned or 0),
            'attention_score': int((user_overdue_count or 0) * 10 + (user_warnings_count or 0) * 5),  # Score para índice de atenção
        })
    
    # Ordenar por pontos ganhos no período (maior primeiro)
    performance_data.sort(key=lambda x: int(x.get('points_earned', 0) or 0), reverse=True)
    
    # Top 3 (Pódio) - sempre garantir 3 elementos com valores seguros
    top_3 = performance_data[:3] if len(performance_data) >= 3 else performance_data
    while len(top_3) < 3:
        top_3.append({
            'name': str('-'),
            'points_earned': int(0),
            'checklist_percentage': float(0.0),
            'training_percentage': float(0.0),
            'quiz_average': float(0.0),
        })
    
    # Sanitizar top_3
    for item in top_3:
        item['name'] = str(item.get('name', '-') or '-')
        item['points_earned'] = int(item.get('points_earned', 0) or 0)
        item['checklist_percentage'] = float(item.get('checklist_percentage', 0) or 0.0)
        item['training_percentage'] = float(item.get('training_percentage', 0) or 0.0)
        item['quiz_average'] = float(item.get('quiz_average', 0) or 0.0)
    
    # Índice de Atenção: Top 3 com mais problemas (atrasos + advertências)
    attention_list = sorted(
        performance_data,
        key=lambda x: int(x.get('attention_score', 0) or 0),
        reverse=True
    )[:3]
    # Garantir sempre 3 elementos com valores seguros
    while len(attention_list) < 3:
        attention_list.append({
            'name': str('-'),
            'attention_score': int(0),
            'checklist_overdue': int(0),
            'warnings_count': int(0),
        })
    
    # Sanitizar attention_list
    for item in attention_list:
        item['name'] = str(item.get('name', '-') or '-')
        item['attention_score'] = int(item.get('attention_score', 0) or 0)
        item['checklist_overdue'] = int(item.get('checklist_overdue', 0) or 0)
        item['warnings_count'] = int(item.get('warnings_count', 0) or 0)
    
    # Garantir que performance_data sempre tenha pelo menos uma linha vazia se estiver vazio
    if not performance_data:
        performance_data = [{
            'user': None,
            'name': str('Nenhum colaborador'),
            'email': str('-'),
            'checklist_percentage': float(0.0),
            'checklist_overdue': int(0),
            'training_percentage': float(0.0),
            'quiz_average': float(0.0),
            'warnings_count': int(0),
            'points_earned': int(0),
            'attention_score': int(0),
        }]
    
    # Sanitizar TODOS os itens de performance_data
    for item in performance_data:
        item['name'] = str(item.get('name', '-') or '-')
        item['email'] = str(item.get('email', '-') or '-')
        item['checklist_percentage'] = float(item.get('checklist_percentage', 0) or 0.0)
        item['checklist_overdue'] = int(item.get('checklist_overdue', 0) or 0)
        item['training_percentage'] = float(item.get('training_percentage', 0) or 0.0)
        item['quiz_average'] = float(item.get('quiz_average', 0) or 0.0)
        item['warnings_count'] = int(item.get('warnings_count', 0) or 0)
        item['points_earned'] = int(item.get('points_earned', 0) or 0)
        item['attention_score'] = int(item.get('attention_score', 0) or 0)
    
    # Calcular média geral de quizzes
    quiz_average_all = 0.0
    try:
        if performance_data:
            quiz_scores = []
            for item in performance_data:
                quiz_avg = item.get('quiz_average')
                if quiz_avg is not None:
                    try:
                        quiz_scores.append(float(quiz_avg or 0.0))
                    except (TypeError, ValueError):
                        pass
            
            if quiz_scores and len(quiz_scores) > 0:
                quiz_average_all = round(float(sum(quiz_scores)) / float(len(quiz_scores)), 1)
            quiz_average_all = float(quiz_average_all) if quiz_average_all is not None else 0.0
    except Exception:
        quiz_average_all = 0.0
    
    # Garantir que warnings_by_type sempre tenha valores inteiros
    safe_warnings_by_type = {
        'oral': int(warnings_by_type.get('oral', 0) or 0),
        'escrita': int(warnings_by_type.get('escrita', 0) or 0),
        'suspensao': int(warnings_by_type.get('suspensao', 0) or 0),
    }
    
    # Garantir conversão final de todos os valores
    total_users_count = int(company_users.count() or 0)
    
    return {
        'company': company,
        'start_date': start_date,
        'end_date': end_date,
        'generated_at': timezone.now(),
        'checklist_average': float(checklist_average or 0.0),
        'training_average': float(training_average or 0.0),
        'quiz_average_all': float(quiz_average_all or 0.0),
        'total_warnings': int(total_warnings or 0),
        'warnings_by_type': safe_warnings_by_type,
        'total_completions': int(total_completions or 0),
        'total_tasks_completed': int(total_tasks_completed or 0),
        'performance_data': performance_data,
        'top_3': top_3,
        'attention_list': attention_list,
        'total_users': int(total_users_count),
    }

