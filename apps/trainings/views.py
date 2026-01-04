# -*- coding: utf-8 -*-
"""
Views do módulo de Treinamentos.
Gerencia listagem, detalhes, player de vídeos e área de gestão.
"""

import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Prefetch
from django.utils import timezone
from django.db import transaction

from apps.core.decorators import gestor_required
from .models import Training, Video, Quiz, Question, Choice, UserProgress, UserQuizAttempt
from .forms import TrainingForm, VideoUploadForm, QuizForm, QuestionFormSet, ChoiceFormSet

logger = logging.getLogger(__name__)


# =============================================================================
# VIEWS PÚBLICAS (COLABORADORES)
# =============================================================================

@login_required
def training_list(request):
    """
    Lista treinamentos disponíveis para o colaborador.
    ACCESS: TODOS (filtrado por empresa e atribuição)
    """
    user = request.user
    company = request.current_company
    
    if user.is_superuser:
        # Admin Master vê todos
        trainings = Training.objects.filter(is_active=True)
        if company:
            trainings = trainings.filter(company=company)
    elif hasattr(user, 'is_gestor') and user.is_gestor:
        # Gestor vê todos da empresa
        trainings = Training.objects.filter(
            company=company,
            is_active=True
        )
    else:
        # Colaborador vê apenas:
        # 1. Treinamentos atribuídos diretamente a ele
        # 2. Treinamentos globais (sem nenhum usuário atribuído)
        from django.db.models import Count
        
        # Treinamentos com assigned_users vazio (globais)
        global_trainings = Training.objects.filter(
            company=company,
            is_active=True
        ).annotate(
            num_assigned=Count('assigned_users')
        ).filter(num_assigned=0)
        
        # Treinamentos atribuídos ao usuário
        assigned_trainings = Training.objects.filter(
            company=company,
            is_active=True,
            assigned_users=user
        )
        
        # Combina ambos
        trainings = (global_trainings | assigned_trainings).distinct()
    
    # Calcula progresso para cada treinamento
    training_data = []
    for training in trainings:
        progress_data = get_user_progress(user, training)
        total_progress = progress_data.get('total_progress', 0) if isinstance(progress_data, dict) else progress_data
        is_completed = total_progress >= 100
        training_data.append({
            'training': training,
            'progress': total_progress,
            'is_completed': is_completed
        })
    
    context = {
        'training_data': training_data,
        'is_gestor': hasattr(user, 'is_gestor') and user.is_gestor,
    }
    return render(request, 'trainings/list.html', context)


@login_required
def training_detail(request, slug):
    """
    Detalhes do treinamento com lista de conteúdos.
    ACCESS: TODOS (filtrado por empresa e atribuição)
    """
    user = request.user
    company = request.current_company
    
    training = get_object_or_404(Training, slug=slug)
    
    # Força refresh para garantir dados atualizados
    training.refresh_from_db()
    
    # Verifica permissão
    if not user.is_superuser:
        if training.company != company:
            messages.error(request, 'Você não tem permissão para acessar este treinamento.')
            return redirect('trainings:list')
        
        # Verifica atribuição (se não for gestor)
        if not (hasattr(user, 'is_gestor') and user.is_gestor):
            if training.assigned_users.exists() and user not in training.assigned_users.all():
                messages.error(request, 'Você não está atribuído a este treinamento.')
                return redirect('trainings:list')
    
    # Busca vídeos e quizzes
    videos = list(training.videos.filter(is_active=True).order_by('order'))
    quizzes = list(training.quizzes.filter(is_active=True).order_by('order'))
    
    # Combina e ordena por ordem
    content_items = []
    for video in videos:
        # Verifica se o vídeo foi assistido
        watched = UserProgress.objects.filter(
            user=user,
            video=video,
            completed=True
        ).exists()
        content_items.append({
            'type': 'video',
            'item': video,
            'order': video.order,
            'completed': watched
        })
    
    for quiz in quizzes:
        # Verifica se o quiz foi aprovado
        passed = UserQuizAttempt.objects.filter(
            user=user,
            quiz=quiz,
            is_passed=True
        ).exists()
        content_items.append({
            'type': 'quiz',
            'item': quiz,
            'order': quiz.order,
            'completed': passed
        })
    
    # Ordena por ordem
    content_items.sort(key=lambda x: x['order'])
    
    # Calcula progresso
    progress_data = get_user_progress(user, training)
    progress = progress_data.get('total_progress', 0) if isinstance(progress_data, dict) else progress_data
    
    context = {
        'training': training,
        'content_items': content_items,
        'progress': progress,
    }
    return render(request, 'trainings/detail.html', context)


@login_required
def content_player(request, slug, content_type, content_id):
    """
    Player unificado para vídeos e quizzes.
    ACCESS: TODOS (filtrado por empresa e atribuição)
    """
    user = request.user
    company = request.current_company
    
    training = get_object_or_404(Training, slug=slug)
    
    # Verifica permissão
    if not user.is_superuser:
        if training.company != company:
            messages.error(request, 'Você não tem permissão para acessar este conteúdo.')
            return redirect('trainings:list')
    
    # Busca o conteúdo
    if content_type == 'video':
        content = get_object_or_404(Video, pk=content_id, training=training)
        questions = None
        attempt = None
        show_result = False
        current_question = None
        current_question_index = 0
        total_questions = 0
        
        # Busca progresso do vídeo
        progress, _ = UserProgress.objects.get_or_create(
            user=user,
            video=content,
            defaults={'completed': False, 'last_position': 0}
        )
    elif content_type == 'quiz':
        content = get_object_or_404(Quiz, pk=content_id, training=training)
        questions = list(content.questions.all().order_by('order').prefetch_related('choices'))
        total_questions = len(questions)
        
        # Pega o índice da pergunta atual (via query param)
        question_index = request.GET.get('question', '0')
        try:
            current_question_index = int(question_index)
        except (ValueError, TypeError):
            current_question_index = 0
        
        # Garante que o índice está dentro dos limites
        if current_question_index < 0:
            current_question_index = 0
        if current_question_index >= total_questions:
            current_question_index = max(0, total_questions - 1)
        
        # Pega a pergunta atual
        current_question = questions[current_question_index] if questions else None
        
        # Verifica se está mostrando resultado
        result_id = request.GET.get('result')
        if result_id:
            attempt = get_object_or_404(UserQuizAttempt, pk=result_id, user=user, quiz=content)
            show_result = True
        else:
            attempt = None
            show_result = False
        
        progress = None  # Quiz não tem progresso de vídeo
    else:
        messages.error(request, 'Tipo de conteúdo inválido.')
        return redirect('trainings:detail', slug=slug)
    
    # Busca próximo e anterior
    videos = list(training.videos.filter(is_active=True).order_by('order'))
    quizzes = list(training.quizzes.filter(is_active=True).order_by('order'))
    
    all_content = []
    for v in videos:
        watched = UserProgress.objects.filter(user=user, video=v, completed=True).exists()
        all_content.append({'type': 'video', 'item': v, 'order': v.order, 'completed': watched})
    for q in quizzes:
        passed = UserQuizAttempt.objects.filter(user=user, quiz=q, is_passed=True).exists()
        all_content.append({'type': 'quiz', 'item': q, 'order': q.order, 'completed': passed})
    all_content.sort(key=lambda x: x['order'])
    
    current_index = None
    for i, c in enumerate(all_content):
        if c['type'] == content_type and c['item'].id == content.id:
            current_index = i
            break
    
    prev_content = all_content[current_index - 1] if current_index and current_index > 0 else None
    next_content = all_content[current_index + 1] if current_index is not None and current_index < len(all_content) - 1 else None
    
    context = {
        'training': training,
        'content': content,
        'content_type': content_type,
        'questions': questions,
        'attempt': attempt,
        'show_result': show_result,
        'prev_content': prev_content,
        'next_content': next_content,
        'all_content': all_content,
        'current_index': current_index,
        'current_question': current_question,
        'current_question_index': current_question_index,
        'total_questions': total_questions,
        'progress': progress,
    }
    
    # Adiciona variáveis específicas para facilitar acesso no template
    if content_type == 'quiz':
        context['quiz'] = content
    elif content_type == 'video':
        context['video'] = content
    
    return render(request, 'trainings/player.html', context)


@login_required
def video_complete(request, video_id):
    """
    Marca um vídeo como completo.
    ACCESS: TODOS
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    video = get_object_or_404(Video, pk=video_id)
    
    progress, created = UserProgress.objects.get_or_create(
        user=request.user,
        video=video,
        defaults={'completed': True, 'completed_at': timezone.now()}
    )
    
    if not progress.completed:
        progress.completed = True
        progress.completed_at = timezone.now()
        progress.save()
    
    return JsonResponse({'success': True, 'completed': True})


@login_required
def quiz_take(request, slug, quiz_id):
    """
    Processa submissão do quiz.
    ACCESS: TODOS
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    training = quiz.training
    
    # Verifica se o slug corresponde ao treinamento
    if training.slug != slug:
        messages.error(request, 'Quiz não encontrado neste treinamento.')
        return redirect('trainings:list')
    
    if request.method != 'POST':
        return redirect('trainings:content_player', slug=training.slug, content_type='quiz', content_id=quiz.id)
    
    # Processa respostas
    import json
    
    # Tenta pegar do body (JSON) ou do POST
    answers = {}
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            answers = data.get('answers', {})
        except json.JSONDecodeError:
            pass
    else:
        # Pega do POST
        answers_json = request.POST.get('answers_json', '{}')
        try:
            answers = json.loads(answers_json)
        except json.JSONDecodeError:
            # Fallback: monta das chaves do POST
            for key, value in request.POST.items():
                if key.startswith('question_'):
                    q_id = key.replace('question_', '')
                    answers[q_id] = value
    
    # Normaliza as chaves (remove prefixos, converte para string)
    normalized_answers = {}
    for key, value in answers.items():
        clean_key = str(key).replace('question_', '').strip()
        clean_value = str(value).strip() if value else ''
        if clean_key and clean_value:
            normalized_answers[clean_key] = clean_value
    
    logger.info(f'Quiz {quiz.id} - Respostas recebidas: {answers}')
    logger.info(f'Quiz {quiz.id} - Respostas normalizadas: {normalized_answers}')
    
    # Cria tentativa
    attempt = UserQuizAttempt.objects.create(
        user=request.user,
        quiz=quiz,
        answers=normalized_answers
    )
    
    # Calcula score
    attempt.calculate_score()
    
    logger.info(f'Quiz {quiz.id} - Tentativa {attempt.id}: Score={attempt.score}, Passed={attempt.is_passed}')
    
    # Redireciona para resultado usando reverse
    from django.urls import reverse
    result_url = reverse('trainings:content_player', kwargs={
        'slug': training.slug,
        'content_type': 'quiz',
        'content_id': quiz.id
    })
    return redirect(f"{result_url}?result={attempt.id}")


@login_required
def get_training_status(request, training_id):
    """
    API para obter status atualizado do treinamento.
    ACCESS: TODOS
    """
    training = get_object_or_404(Training, pk=training_id)
    user = request.user
    
    # Calcula progresso
    progress = get_user_progress(user, training)
    
    # Status de cada conteúdo
    content_status = []
    
    for video in training.videos.filter(is_active=True):
        watched = UserProgress.objects.filter(
            user=user,
            video=video,
            completed=True
        ).exists()
        content_status.append({
            'type': 'video',
            'id': video.id,
            'completed': watched
        })
    
    for quiz in training.quizzes.filter(is_active=True):
        passed = UserQuizAttempt.objects.filter(
            user=user,
            quiz=quiz,
            is_passed=True
        ).exists()
        content_status.append({
            'type': 'quiz',
            'id': quiz.id,
            'completed': passed
        })
    
    total_progress = progress.get('total_progress', 0) if isinstance(progress, dict) else progress
    
    return JsonResponse({
        'success': True,
        'training': {
            'total_progress': total_progress,
            'is_completed': total_progress >= 100
        },
        'content_status': content_status,
        'is_complete': total_progress >= 100
    })


@login_required
@gestor_required
def get_company_users(request):
    """
    API para obter usuários de uma empresa.
    ACCESS: ADMIN MASTER | GESTOR
    """
    from apps.accounts.models import User, UserCompany
    from apps.core.models import Company
    
    company_id = request.GET.get('company_id')
    
    if not company_id:
        # Se não especificou empresa, usa a empresa atual
        company = request.current_company
    else:
        try:
            company = Company.objects.get(pk=company_id)
            # Verifica permissão
            if not request.user.is_superuser and company != request.current_company:
                return JsonResponse({'success': False, 'error': 'Sem permissão'}, status=403)
        except Company.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Empresa não encontrada'}, status=404)
    
    if not company:
        return JsonResponse({'success': False, 'error': 'Nenhuma empresa selecionada'}, status=400)
    
    # Busca usuários ativos da empresa via UserCompany
    user_ids = UserCompany.objects.filter(
        company=company,
        is_active=True
    ).values_list('user_id', flat=True)
    
    users = User.objects.filter(
        id__in=user_ids,
        is_active=True
    ).exclude(
        is_superuser=True  # Exclui admin master
    ).order_by('first_name', 'last_name', 'email')
    
    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'email': user.email,
            'full_name': user.get_full_name() or user.email,
            'is_gestor': getattr(user, 'is_gestor', False)
        })
    
    return JsonResponse({
        'success': True,
        'users': users_data,
        'company_id': company.id,
        'company_name': company.name
    })


def get_user_progress(user, training):
    """
    Calcula o progresso do usuário em um treinamento.
    Considera vídeos assistidos e quizzes aprovados.
    """
    videos = training.videos.filter(is_active=True)
    quizzes = training.quizzes.filter(is_active=True)
    
    total_items = videos.count() + quizzes.count()
    if total_items == 0:
        return {
            'videos_watched': 0,
            'videos_total': 0,
            'quizzes_passed': 0,
            'quizzes_total': 0,
            'total_progress': 0
        }
    
    videos_watched = UserProgress.objects.filter(
        user=user,
        video__in=videos,
        completed=True
    ).count()
    
    quizzes_passed = UserQuizAttempt.objects.filter(
        user=user,
        quiz__in=quizzes,
        is_passed=True
    ).values('quiz').distinct().count()
    
    completed_items = videos_watched + quizzes_passed
    progress_percent = int((completed_items / total_items) * 100)
    
    return {
        'videos_watched': videos_watched,
        'videos_total': videos.count(),
        'quizzes_passed': quizzes_passed,
        'quizzes_total': quizzes.count(),
        'total_progress': progress_percent
    }


# =============================================================================
# VIEWS DE GESTÃO (ADMIN/GESTOR)
# =============================================================================

@login_required
@gestor_required
def manage_list(request):
    """
    Lista treinamentos para gestão.
    ACCESS: ADMIN MASTER | GESTOR
    """
    user = request.user
    company = request.current_company
    
    if user.is_superuser:
        trainings = Training.objects.all()
        if company:
            trainings = trainings.filter(company=company)
    else:
        trainings = Training.objects.filter(company=company)
    
    trainings = trainings.order_by('-created_at')
    
    context = {
        'trainings': trainings,
    }
    return render(request, 'trainings/manage/list.html', context)


@login_required
@gestor_required
def manage_create(request):
    """
    Criar novo treinamento.
    ACCESS: ADMIN MASTER | GESTOR
    Usa a empresa selecionada no sidemenu (request.current_company)
    """
    # Verifica se há empresa selecionada
    if not request.current_company:
        messages.error(request, 'Selecione uma empresa no menu lateral antes de criar um treinamento.')
        return redirect('trainings:manage_list')
    
    if request.method == 'POST':
        form = TrainingForm(request.POST, request.FILES, company=request.current_company)
        
        if form.is_valid():
            training = form.save(commit=False)
            training.company = request.current_company
            training.created_by = request.user
            training.save()
            form.save_m2m()  # Salva relações many-to-many
            messages.success(request, f'Treinamento "{training.title}" criado com sucesso!')
            return redirect('trainings:manage_detail', pk=training.pk)
    else:
        form = TrainingForm(company=request.current_company)
    
    context = {
        'form': form,
        'title': 'Criar Treinamento',
        'is_edit': False,
    }
    return render(request, 'trainings/manage/form.html', context)


@login_required
@gestor_required
def manage_edit(request, pk):
    """
    Editar treinamento existente.
    ACCESS: ADMIN MASTER | GESTOR
    Usa a empresa do treinamento
    """
    training = get_object_or_404(Training, pk=pk)
    
    # Verifica permissão - Admin pode editar qualquer, Gestor só da sua empresa
    if not request.user.is_superuser and training.company != request.current_company:
        messages.error(request, 'Você não tem permissão para editar este treinamento.')
        return redirect('trainings:manage_list')
    
    if request.method == 'POST':
        form = TrainingForm(request.POST, request.FILES, instance=training, company=training.company)
        
        if form.is_valid():
            form.save()
            messages.success(request, f'Treinamento "{training.title}" atualizado com sucesso!')
            return redirect('trainings:manage_detail', pk=training.pk)
    else:
        form = TrainingForm(instance=training, company=training.company)
    
    context = {
        'form': form,
        'training': training,
        'title': f'Editar: {training.title}',
        'is_edit': True,
    }
    return render(request, 'trainings/manage/form.html', context)


@login_required
@gestor_required
def manage_delete(request, pk):
    """
    Deletar treinamento.
    ACCESS: ADMIN MASTER | GESTOR
    """
    training = get_object_or_404(Training, pk=pk)
    
    # Verifica permissão
    is_admin = request.user.is_superuser
    if not is_admin and training.company != request.current_company:
        messages.error(request, 'Você não tem permissão para deletar este treinamento.')
        return redirect('trainings:manage_list')
    
    if request.method == 'POST':
        title = training.title
        training.delete()
        messages.success(request, f'Treinamento "{title}" deletado com sucesso!')
        return redirect('trainings:manage_list')
    
    context = {
        'training': training,
    }
    return render(request, 'trainings/manage/delete.html', context)


@login_required
@gestor_required
def manage_detail(request, pk):
    """
    Detalhes do treinamento para gestão.
    ACCESS: ADMIN MASTER | GESTOR
    """
    training = get_object_or_404(Training, pk=pk)
    
    # Verifica permissão
    is_admin = request.user.is_superuser
    if not is_admin and training.company != request.current_company:
        messages.error(request, 'Você não tem permissão para acessar este treinamento.')
        return redirect('trainings:manage_list')
    
    # Força refresh
    training.refresh_from_db()
    
    # Busca vídeos e quizzes
    videos = list(training.videos.all().order_by('order'))
    quizzes = list(training.quizzes.all().order_by('order'))
    
    # Combina conteúdos
    content_items = []
    for video in videos:
        content_items.append({
            'type': 'video',
            'item': video,
            'order': video.order
        })
    for quiz in quizzes:
        content_items.append({
            'type': 'quiz',
            'item': quiz,
            'order': quiz.order
        })
    content_items.sort(key=lambda x: x['order'])
    
    context = {
        'training': training,
        'content_items': content_items,
        'videos': videos,
        'quizzes': quizzes,
    }
    return render(request, 'trainings/manage/detail.html', context)


# =============================================================================
# VIEWS DE VÍDEO
# =============================================================================

@login_required
@gestor_required
def video_create(request, training_id):
    """
    Criar novo vídeo para um treinamento.
    ACCESS: ADMIN MASTER | GESTOR
    """
    training = get_object_or_404(Training, pk=training_id)
    
    # Verifica permissão
    is_admin = request.user.is_superuser
    if not is_admin and training.company != request.current_company:
        messages.error(request, 'Você não tem permissão para adicionar vídeo neste treinamento.')
        return redirect('trainings:manage_list')
    
    if request.method == 'POST':
        form = VideoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            video = form.save(commit=False)
            video.training = training
            # Define ordem como próximo disponível
            max_order = training.videos.count() + training.quizzes.count()
            video.order = max_order + 1
            video.save()
            messages.success(request, f'Vídeo "{video.title}" adicionado com sucesso!')
            return redirect('trainings:manage_detail', pk=training.pk)
    else:
        form = VideoUploadForm()
    
    context = {
        'form': form,
        'training': training,
    }
    return render(request, 'trainings/manage/video_form.html', context)


@login_required
@gestor_required
def video_edit(request, video_id):
    """
    Editar vídeo existente.
    ACCESS: ADMIN MASTER | GESTOR
    """
    video = get_object_or_404(Video, pk=video_id)
    training = video.training
    
    # Verifica permissão
    is_admin = request.user.is_superuser
    if not is_admin and training.company != request.current_company:
        messages.error(request, 'Você não tem permissão para editar este vídeo.')
        return redirect('trainings:manage_list')
    
    if request.method == 'POST':
        form = VideoUploadForm(request.POST, request.FILES, instance=video)
        if form.is_valid():
            form.save()
            messages.success(request, f'Vídeo "{video.title}" atualizado com sucesso!')
            return redirect('trainings:manage_detail', pk=training.pk)
    else:
        form = VideoUploadForm(instance=video)
    
    context = {
        'form': form,
        'video': video,
        'training': training,
    }
    return render(request, 'trainings/manage/video_form.html', context)


@login_required
@gestor_required
def video_delete(request, video_id):
    """
    Deletar vídeo.
    ACCESS: ADMIN MASTER | GESTOR
    """
    video = get_object_or_404(Video, pk=video_id)
    training = video.training
    
    # Verifica permissão
    is_admin = request.user.is_superuser
    if not is_admin and training.company != request.current_company:
        messages.error(request, 'Você não tem permissão para deletar este vídeo.')
        return redirect('trainings:manage_list')
    
    if request.method == 'POST':
        title = video.title
        video.delete()
        messages.success(request, f'Vídeo "{title}" deletado com sucesso!')
        return redirect('trainings:manage_detail', pk=training.pk)
    
    return redirect('trainings:manage_detail', pk=training.pk)


# =============================================================================
# VIEWS DE QUIZ - REFATORADAS COMPLETAMENTE
# =============================================================================

def _collect_dynamic_choices_from_post(request, question_identifier):
    """
    Coleta TODAS as opções dinâmicas do POST para uma pergunta.
    
    IMPORTANTE: Busca por TODAS as chaves que começam com choice_{identifier}_
    em vez de assumir índices sequenciais (0, 1, 2...).
    
    Args:
        request: HttpRequest
        question_identifier: ID da pergunta (int) ou índice do formset (int)
    
    Returns:
        list: Lista de dicts com {text, is_correct, order}
    """
    choices = []
    prefix = f'choice_{question_identifier}_'
    
    # Encontra todos os índices únicos de opções para este identificador
    choice_indices = set()
    for key in request.POST.keys():
        if key.startswith(prefix) and key.endswith('_text'):
            # Extrai o índice: choice_5_2_text -> 2
            try:
                parts = key.replace(prefix, '').replace('_text', '')
                idx = int(parts)
                choice_indices.add(idx)
            except (ValueError, IndexError):
                continue
    
    logger.info(f'Índices de opções encontrados para {prefix}: {sorted(choice_indices)}')
    
    # Coleta dados de cada opção encontrada
    for idx in sorted(choice_indices):
        text_key = f'{prefix}{idx}_text'
        correct_key = f'{prefix}{idx}_is_correct'
        
        text = request.POST.get(text_key, '').strip()
        is_correct = correct_key in request.POST and request.POST.get(correct_key) == 'on'
        
        if text:  # Só adiciona se tiver texto
            choices.append({
                'text': text,
                'is_correct': is_correct,
                'order': idx
            })
            logger.info(f'  Opção dinâmica coletada: idx={idx}, text="{text[:30]}", is_correct={is_correct}')
    
    return choices


def _validate_and_save_choices(question, formset_choices, dynamic_choices, validation_errors, question_text):
    """
    Valida e salva as opções de uma pergunta.
    
    REGRAS:
    - Mínimo 2 opções, máximo 5 opções
    - EXATAMENTE 1 resposta correta
    - Se existem opções dinâmicas, elas SUBSTITUEM as do formset
    
    Returns:
        bool: True se salvou com sucesso, False se houve erro
    """
    # Se tem opções dinâmicas, usa apenas elas (substitui formset)
    if dynamic_choices:
        all_choices = dynamic_choices
        logger.info(f'Usando {len(dynamic_choices)} opções dinâmicas (substituindo formset)')
    else:
        # Usa opções do formset
        all_choices = []
        for choice_form in formset_choices:
            if choice_form.cleaned_data and not choice_form.cleaned_data.get('DELETE', False):
                all_choices.append({
                    'text': choice_form.cleaned_data.get('text', '').strip(),
                    'is_correct': choice_form.cleaned_data.get('is_correct', False),
                    'order': choice_form.cleaned_data.get('order', 0),
                    '_form': choice_form  # Referência ao form para salvar
                })
        logger.info(f'Usando {len(all_choices)} opções do formset')
    
    # Validação: mínimo 2 opções
    if len(all_choices) < 2:
        validation_errors.append(f'Pergunta "{question_text[:50]}": Adicione pelo menos 2 opções de resposta.')
        return False
    
    # Validação: máximo 5 opções
    if len(all_choices) > 5:
        validation_errors.append(f'Pergunta "{question_text[:50]}": Máximo de 5 opções permitido.')
        return False
    
    # Validação: EXATAMENTE 1 resposta correta
    correct_count = sum(1 for c in all_choices if c['is_correct'])
    if correct_count == 0:
        validation_errors.append(f'Pergunta "{question_text[:50]}": Selecione uma opção como correta.')
        return False
    if correct_count > 1:
        validation_errors.append(f'Pergunta "{question_text[:50]}": Apenas UMA opção pode ser marcada como correta.')
        return False
    
    # Validação: todas com texto
    for c in all_choices:
        if not c['text']:
            validation_errors.append(f'Pergunta "{question_text[:50]}": Todas as opções devem ter texto preenchido.')
            return False
    
    # Se tem opções dinâmicas, deleta as existentes e cria novas
    if dynamic_choices:
        # Deleta todas as opções existentes
        deleted_count = question.choices.all().delete()[0]
        logger.info(f'Deletadas {deleted_count} opções existentes da pergunta {question.id}')
        
        # Cria novas opções
        for order, choice_data in enumerate(all_choices):
            choice = Choice.objects.create(
                question=question,
                text=choice_data['text'],
                is_correct=choice_data['is_correct'],
                order=order
            )
            logger.info(f'  ✅ Opção criada: ID={choice.id}, text="{choice.text[:30]}", is_correct={choice.is_correct}')
    else:
        # Salva opções do formset normalmente
        for choice_data in all_choices:
            if '_form' in choice_data:
                choice = choice_data['_form'].save(commit=False)
                choice.question = question
                choice.save()
                logger.info(f'  ✅ Opção formset salva: ID={choice.id}, is_correct={choice.is_correct}')
    
    return True


@login_required
@gestor_required
def quiz_create(request, training_id):
    """
    Criar novo quiz para um treinamento.
    ACCESS: ADMIN MASTER | GESTOR
    
    FLUXO:
    1. Valida formulário do quiz e formset de perguntas
    2. Para cada pergunta, coleta opções dinâmicas do JavaScript
    3. Valida: mínimo 2 opções, pelo menos 1 correta, todas com texto
    4. Salva tudo em transação atômica
    """
    training = get_object_or_404(Training, pk=training_id)
    
    # Verifica permissão
    is_admin = request.user.is_superuser
    if not is_admin and training.company != request.current_company:
        messages.error(request, 'Você não tem permissão para criar quiz neste treinamento.')
        return redirect('trainings:manage_list')
    
    if request.method == 'POST':
        quiz_form = QuizForm(request.POST)
        question_formset = QuestionFormSet(request.POST, prefix='questions')
        
        logger.info('=== QUIZ_CREATE: Iniciando processamento ===')
        logger.info(f'POST keys: {list(request.POST.keys())}')
        
        if quiz_form.is_valid() and question_formset.is_valid():
            validation_errors = []
            
            try:
                with transaction.atomic():
                    # Salva o quiz
                    quiz = quiz_form.save(commit=False)
                    quiz.training = training
                    # Define ordem como próximo disponível
                    max_order = training.videos.count() + training.quizzes.count()
                    quiz.order = max_order + 1
                    quiz.save()
                    
                    logger.info(f'Quiz criado: ID={quiz.id}, title="{quiz.title}"')
                    
                    # Processa cada pergunta
                    questions_saved = 0
                    choices_saved = 0
                    
                    for idx, form in enumerate(question_formset.forms):
                        if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                            question_text = form.cleaned_data.get('text', '').strip()
                            
                            if not question_text:
                                continue
                            
                            logger.info(f'=== Processando pergunta {idx}: "{question_text[:50]}" ===')
                            
                            # Salva a pergunta
                            question = form.save(commit=False)
                            question.quiz = quiz
                            question.order = idx + 1
                            question.save()
                            
                            logger.info(f'Pergunta salva: ID={question.id}')
                            
                            # Coleta opções dinâmicas do JavaScript
                            # Para perguntas novas, JS usa o índice do formset
                            dynamic_choices = _collect_dynamic_choices_from_post(request, idx)
                            
                            logger.info(f'Opções dinâmicas encontradas: {len(dynamic_choices)}')
                            
                            # Valida e salva opções
                            if not _validate_and_save_choices(question, [], dynamic_choices, validation_errors, question_text):
                                raise ValueError('Erro de validação')
                            
                            questions_saved += 1
                            choices_saved += len(dynamic_choices)
                    
                    # Verifica se salvou pelo menos uma pergunta
                    if questions_saved == 0:
                        validation_errors.append('Adicione pelo menos uma pergunta ao quiz.')
                        raise ValueError('Nenhuma pergunta')
                    
                    if validation_errors:
                        raise ValueError('Erros de validação')
                    
                    messages.success(request, f'Quiz "{quiz.title}" criado com sucesso! ({questions_saved} perguntas, {choices_saved} opções)')
                    return redirect('trainings:manage_detail', pk=training.pk)
                    
            except ValueError:
                # Rollback automático pela transação
                for error in validation_errors:
                    messages.error(request, error)
        else:
            # Erros de validação do form/formset - mostra detalhes
            logger.error(f'Quiz form errors: {quiz_form.errors}')
            logger.error(f'Question formset errors: {question_formset.errors}')
            logger.error(f'Question formset non_form_errors: {question_formset.non_form_errors()}')
            
            if not quiz_form.is_valid():
                for field, errors in quiz_form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
            if not question_formset.is_valid():
                # Mostra erros específicos de cada pergunta
                for i, form_errors in enumerate(question_formset.errors):
                    if form_errors:
                        for field, errors in form_errors.items():
                            for error in errors:
                                messages.error(request, f'Pergunta {i+1} - {field}: {error}')
                # Mostra erros gerais do formset
                for error in question_formset.non_form_errors():
                    messages.error(request, error)
    else:
        quiz_form = QuizForm()
        question_formset = QuestionFormSet(prefix='questions')
    
    context = {
        'training': training,
        'quiz_form': quiz_form,
        'question_formset': question_formset,
    }
    return render(request, 'trainings/manage/quiz_form.html', context)


@login_required
@gestor_required
def quiz_edit(request, quiz_id):
    """
    Editar quiz existente.
    ACCESS: ADMIN MASTER | GESTOR
    
    FLUXO:
    1. Carrega quiz e perguntas existentes
    2. Processa formset de perguntas (existentes) e opções dinâmicas (novas do JS)
    3. Para perguntas existentes: usa ID da pergunta para buscar opções dinâmicas
    4. Para perguntas novas: usa índice do formset
    5. Se há opções dinâmicas, elas SUBSTITUEM as existentes
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    training = quiz.training
    
    # Verifica permissão
    is_admin = request.user.is_superuser
    if not is_admin and training.company != request.current_company:
        messages.error(request, 'Você não tem permissão para editar este quiz.')
        return redirect('trainings:manage_list')
    
    if request.method == 'POST':
        quiz_form = QuizForm(request.POST, instance=quiz)
        question_formset = QuestionFormSet(request.POST, instance=quiz, prefix='questions')
        
        logger.info('=== QUIZ_EDIT: Iniciando processamento ===')
        logger.info(f'Quiz ID: {quiz.id}')
        logger.info(f'POST keys com "choice_": {[k for k in request.POST.keys() if "choice_" in k or "choices_" in k]}')
        
        if quiz_form.is_valid() and question_formset.is_valid():
            validation_errors = []
            
            try:
                with transaction.atomic():
                    # Salva o quiz
                    quiz_form.save()
                    
                    # Processa perguntas
                    questions_saved = 0
                    choices_saved = 0
                    
                    # Salva perguntas do formset
                    questions = question_formset.save(commit=False)
                    for question in questions:
                        question.quiz = quiz
                        question.save()
                    
                    # Deleta perguntas marcadas
                    for form in question_formset.deleted_forms:
                        if form.instance.pk:
                            form.instance.delete()
                            logger.info(f'Pergunta deletada: ID={form.instance.pk}')
                    
                    # Processa opções de cada pergunta
                    for idx, form in enumerate(question_formset.forms):
                        if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                            question = form.instance
                            question_text = form.cleaned_data.get('text', '').strip()
                            
                            if not question_text:
                                continue
                            
                            logger.info(f'=== Processando pergunta {idx} (ID: {question.pk}) ===')
                            logger.info(f'Texto: "{question_text[:50]}"')
                            
                            # Determina identificador para buscar opções dinâmicas
                            # Perguntas existentes: usa ID
                            # Perguntas novas: usa índice do formset
                            if question.pk:
                                # Tenta primeiro com ID da pergunta
                                dynamic_choices = _collect_dynamic_choices_from_post(request, question.id)
                                
                                # Se não encontrou, tenta com índice (fallback)
                                if not dynamic_choices:
                                    dynamic_choices = _collect_dynamic_choices_from_post(request, idx)
                                
                                # Carrega formset de opções existentes
                                choice_prefix = f'choices_{question.id}'
                                choice_formset = ChoiceFormSet(
                                    request.POST,
                                    instance=question,
                                    prefix=choice_prefix
                                )
                                
                                formset_choices = []
                                if choice_formset.is_valid():
                                    formset_choices = list(choice_formset.forms)
                                else:
                                    logger.warning(f'Formset de opções inválido: {choice_formset.errors}')
                            else:
                                # Pergunta nova
                                dynamic_choices = _collect_dynamic_choices_from_post(request, idx)
                                formset_choices = []
                            
                            logger.info(f'Opções dinâmicas: {len(dynamic_choices)}, Formset: {len(formset_choices)}')
                            
                            # Valida e salva opções
                            if not _validate_and_save_choices(question, formset_choices, dynamic_choices, validation_errors, question_text):
                                raise ValueError('Erro de validação')
                            
                            questions_saved += 1
                            choices_saved += len(dynamic_choices) if dynamic_choices else len([f for f in formset_choices if f.cleaned_data and not f.cleaned_data.get('DELETE')])
                    
                    if validation_errors:
                        raise ValueError('Erros de validação')
                    
                    # Força refresh
                    quiz.refresh_from_db()
                    
                    messages.success(request, f'Quiz "{quiz.title}" atualizado com sucesso! ({questions_saved} perguntas)')
                    return redirect('trainings:manage_detail', pk=training.pk)
                    
            except ValueError:
                # Rollback automático pela transação
                for error in validation_errors:
                    messages.error(request, error)
                
                # Recarrega formsets para manter dados
                quiz_form = QuizForm(request.POST, instance=quiz)
                question_formset = QuestionFormSet(request.POST, instance=quiz, prefix='questions')
        else:
            # Erros de validação - mostra detalhes
            logger.error(f'Quiz form errors: {quiz_form.errors}')
            logger.error(f'Question formset errors: {question_formset.errors}')
            logger.error(f'Question formset non_form_errors: {question_formset.non_form_errors()}')
            
            if not quiz_form.is_valid():
                for field, errors in quiz_form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
            if not question_formset.is_valid():
                # Mostra erros específicos de cada pergunta
                for i, form_errors in enumerate(question_formset.errors):
                    if form_errors:
                        for field, errors in form_errors.items():
                            for error in errors:
                                messages.error(request, f'Pergunta {i+1} - {field}: {error}')
                # Mostra erros gerais do formset
                for error in question_formset.non_form_errors():
                    messages.error(request, error)
    else:
        quiz_form = QuizForm(instance=quiz)
        question_formset = QuestionFormSet(instance=quiz, prefix='questions')
    
    # Carrega formsets de opções para cada pergunta
    choice_formsets = {}
    for question in quiz.questions.all():
        choice_formsets[question.id] = ChoiceFormSet(
            instance=question,
            prefix=f'choices_{question.id}'
        )
    
    context = {
        'training': training,
        'quiz': quiz,
        'quiz_form': quiz_form,
        'question_formset': question_formset,
        'choice_formsets': choice_formsets,
    }
    return render(request, 'trainings/manage/quiz_form.html', context)


@login_required
@gestor_required
def quiz_delete(request, quiz_id):
    """
    Deletar quiz.
    ACCESS: ADMIN MASTER | GESTOR
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    training = quiz.training
    
    # Verifica permissão
    is_admin = request.user.is_superuser
    if not is_admin and training.company != request.current_company:
        messages.error(request, 'Você não tem permissão para deletar este quiz.')
        return redirect('trainings:manage_list')
    
    if request.method == 'POST':
        title = quiz.title
        quiz.delete()
        messages.success(request, f'Quiz "{title}" deletado com sucesso!')
        return redirect('trainings:manage_detail', pk=training.pk)
    
    return redirect('trainings:manage_detail', pk=training.pk)


@login_required
@gestor_required
def update_content_order(request, training_id):
    """
    Atualiza a ordem dos conteúdos via AJAX.
    ACCESS: ADMIN MASTER | GESTOR
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    training = get_object_or_404(Training, pk=training_id)
    
    # Verifica permissão
    is_admin = request.user.is_superuser
    if not is_admin and training.company != request.current_company:
        return JsonResponse({'error': 'Sem permissão'}, status=403)
    
    import json
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        
        for item in items:
            content_type = item.get('type')
            content_id = item.get('id')
            order = item.get('order')
            
            if content_type == 'video':
                Video.objects.filter(pk=content_id, training=training).update(order=order)
            elif content_type == 'quiz':
                Quiz.objects.filter(pk=content_id, training=training).update(order=order)
        
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f'Erro ao atualizar ordem: {e}')
        return JsonResponse({'error': str(e)}, status=400)
