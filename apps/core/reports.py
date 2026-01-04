"""
Serviço de Relatórios - Extração de dados para relatórios consolidados.
"""

from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import datetime, timedelta

from apps.accounts.models import User, Warning
from apps.checklists.models import Checklist, TaskDone, ChecklistCompletion
from apps.trainings.models import Training, UserProgress, UserQuizAttempt
from apps.core.utils import PeriodKeyHelper


def get_report_data(company, start_date, end_date, user=None):
    """
    Extrai dados consolidados para relatório.
    
    Args:
        company: Empresa para filtrar dados
        start_date: Data de início do período
        end_date: Data de fim do período
        user: Usuário específico (opcional). Se None, retorna dados da empresa inteira
    
    Returns:
        dict: Dicionário com dados do relatório
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


def _get_user_profile(user):
    """Extrai perfil do usuário."""
    return {
        'name': user.get_full_name(),
        'email': user.email,
        'age': user.age,
        'phone': user.phone or 'Não informado',
        'city': user.city or 'Não informado',
        'neighborhood': user.neighborhood or 'Não informado',
        'birth_date': user.birth_date.strftime('%d/%m/%Y') if user.birth_date else 'Não informado',
    }


def _get_user_ranking(user, company):
    """Calcula a posição do usuário no ranking da empresa."""
    # Buscar todos os usuários ativos da empresa ordenados por pontos
    ranking_users = User.objects.filter(
        user_companies__company=company,
        user_companies__is_active=True
    ).annotate(
        total_medalhas=Count('training_rewards', filter=Q(training_rewards__training__company=company)),
        total_videos=Count('training_progress', filter=Q(training_progress__completed=True, training_progress__video__training__company=company))
    ).order_by('-total_points', '-total_medalhas', '-total_videos')
    
    # Encontrar posição do usuário
    position = 1
    for rank_user in ranking_users:
        if rank_user.id == user.id:
            break
        position += 1
    
    total_users = ranking_users.count()
    
    return {
        'position': position,
        'total_users': total_users,
        'total_points': user.total_points,
    }


def _get_user_checklists(user, company, start_datetime, end_datetime):
    """Extrai dados de checklists do usuário no período."""
    # ChecklistCompletions no período
    completions = ChecklistCompletion.objects.filter(
        user=user,
        checklist__company=company,
        completed_at__gte=start_datetime,
        completed_at__lte=end_datetime
    ).select_related('checklist')
    
    total_completed = completions.count()
    
    # TaskDones no período (tarefas individuais)
    task_dones = TaskDone.objects.filter(
        user=user,
        task__checklist__company=company,
        completed_at__gte=start_datetime,
        completed_at__lte=end_datetime
    ).select_related('task', 'task__checklist')
    
    total_tasks_completed = task_dones.count()
    
    # Contador de atrasos (verificar checklists que estavam atrasados no período)
    overdue_count = 0
    user_checklists = Checklist.objects.filter(
        company=company,
        is_active=True
    ).filter(
        Q(assigned_users=user) | Q(assigned_users__isnull=True)
    ).distinct()
    
    # Para cada checklist, verificar se estava atrasado em algum ponto do período
    for checklist in user_checklists:
        if checklist.is_overdue_for_user(user):
            overdue_count += 1
    
    return {
        'total_completed': total_completed,
        'total_tasks_completed': total_tasks_completed,
        'overdue_count': overdue_count,
        'completions': [
            {
                'checklist': comp.checklist.title,
                'date': comp.completed_at.strftime('%d/%m/%Y'),
                'points': comp.points_earned,
            }
            for comp in completions[:20]  # Limitar a 20 mais recentes
        ],
    }


def _get_user_trainings(user, company, start_datetime, end_datetime):
    """
    Extrai dados de treinamentos do usuário.
    Mostra TODOS os treinamentos atribuídos ao usuário, com progresso atual.
    """
    # Treinamentos atribuídos ao usuário ou globais
    trainings = Training.objects.filter(
        company=company,
        is_active=True
    ).filter(
        Q(assigned_users=user) | Q(assigned_users__isnull=True)
    ).distinct()
    
    training_list = []
    total_progress = 0
    
    for training in trainings:
        # Progresso do usuário no treinamento (TODOS os vídeos, não apenas do período)
        total_videos = training.videos.filter(is_active=True).count()
        completed_videos = UserProgress.objects.filter(
            user=user,
            video__training=training,
            video__is_active=True,
            completed=True
        ).count()
        
        # Verificar quizzes (TODOS os quizzes)
        quizzes = training.quizzes.filter(is_active=True)
        total_quizzes = quizzes.count()
        
        # Quizzes aprovados (verificar se o usuário passou em pelo menos uma tentativa de cada quiz)
        passed_quizzes = 0
        for quiz in quizzes:
            if UserQuizAttempt.objects.filter(
                user=user,
                quiz=quiz,
                is_passed=True
            ).exists():
                passed_quizzes += 1
        
        # Progresso geral (vídeos + quizzes)
        if total_videos + total_quizzes > 0:
            progress = int(((completed_videos + passed_quizzes) / (total_videos + total_quizzes)) * 100)
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
            'title': training.title,
            'progress': progress,
            'is_completed': is_completed,
            'is_started': is_started,
            'total_videos': total_videos,
            'completed_videos': completed_videos,
            'total_quizzes': total_quizzes,
            'passed_quizzes': passed_quizzes,
        })
    
    avg_progress = int(total_progress / len(training_list)) if training_list else 0
    
    return {
        'trainings': training_list,
        'total_trainings': len(training_list),
        'avg_progress': avg_progress,
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
    avg_score_all = attempts_all.aggregate(avg=Avg('score'))['avg'] or 0
    total_passed_all = attempts_all.filter(is_passed=True).count()
    
    # Estatísticas do período
    if attempts_period.exists():
        avg_score_period = attempts_period.aggregate(avg=Avg('score'))['avg'] or 0
        total_passed_period = attempts_period.filter(is_passed=True).count()
    else:
        avg_score_period = 0
        total_passed_period = 0
    
    attempts_list = []
    for attempt in attempts_period[:20]:  # Limitar a 20 mais recentes do período
        attempts_list.append({
            'quiz_title': attempt.quiz.title,
            'training_title': attempt.quiz.training.title,
            'score': attempt.score,
            'is_passed': attempt.is_passed,
            'date': attempt.completed_at.strftime('%d/%m/%Y %H:%M'),
            'total_questions': attempt.total_questions,
            'correct_answers': attempt.correct_answers,
        })
    
    return {
        'avg_score': round(avg_score_all, 1),  # Média geral
        'avg_score_period': round(avg_score_period, 1),  # Média do período
        'total_attempts': attempts_all.count(),  # Total geral
        'total_attempts_period': attempts_period.count(),  # Total do período
        'total_passed': total_passed_all,  # Aprovados geral
        'total_passed_period': total_passed_period,  # Aprovados no período
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
            'date': warning.created_at.strftime('%d/%m/%Y'),
            'type': warning.get_warning_type_display(),
            'reason': warning.reason,
            'issuer': warning.issuer.get_full_name() if warning.issuer else 'Sistema',
        })
    
    return {
        'total': warnings.count(),
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

