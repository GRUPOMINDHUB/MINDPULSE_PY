"""
Views para treinamentos.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Max, Q, Count
import json

from .models import Training, Video, UserProgress, UserTrainingReward, Quiz, Question, Choice, UserQuizAttempt
from .forms import TrainingForm, VideoUploadForm, AdminTrainingForm, QuizForm, QuestionFormSet, ChoiceFormSet, VideoForm
from apps.core.models import Company
from apps.core.decorators import gestor_required, gestor_required_ajax


@login_required
def training_list(request):
    """
    Lista de treinamentos disponíveis.
    ACCESS: ADMIN MASTER | GESTOR | COLABORADOR
    - Admin Master: Vê todos os treinamentos de todas as empresas
    - Gestor/Colaborador: Vê apenas treinamentos da sua empresa
    Regra: Todos os usuários vinculados a uma empresa podem ver e executar todos os treinamentos ativos daquela unidade.
    """
    user = request.user
    company = request.current_company
    
    # Admin Master: se current_company for None, mostra todos os treinamentos (visão global)
    if user.is_superuser:
        if company:
            # Filtra por empresa selecionada (Admin Master vê todos, mesmo sem assigned_users)
            trainings = Training.objects.filter(
                company=company,
                is_active=True
            ).prefetch_related('videos', 'assigned_users')
        else:
            # Visão global: mostra todos os treinamentos de todas as empresas
            trainings = Training.objects.filter(
                is_active=True
            ).select_related('company').prefetch_related('videos', 'assigned_users')
    else:
        # Usuários normais: precisa ter empresa vinculada
        if not company:
            return render(request, 'core/no_company.html')
        
        # Gestor vê todos os treinamentos da empresa
        if request.is_gestor:
            trainings = Training.objects.filter(
                company=company,
                is_active=True
            ).prefetch_related('videos', 'assigned_users')
        else:
            # Colaborador: vê apenas treinamentos atribuídos a ele OU globais (sem assigned_users)
            from django.db.models import Count
            trainings = Training.objects.filter(
                company=company,
                is_active=True
            ).annotate(
                assigned_count=Count('assigned_users')
            ).filter(
                Q(assigned_users=user) | Q(assigned_count=0)
            ).distinct().prefetch_related('videos', 'assigned_users')
    
    # Adiciona progresso do usuário a cada treinamento
    training_data = []
    for training in trainings:
        progress = training.get_user_progress(user)
        is_completed = progress == 100
        
        # Verifica se tem recompensa
        has_reward = UserTrainingReward.objects.filter(
            user=user,
            training=training
        ).exists()
        
        training_data.append({
            'training': training,
            'progress': progress,
            'is_completed': is_completed,
            'has_reward': has_reward,
        })
    
    context = {
        'training_data': training_data,
    }
    
    return render(request, 'trainings/list.html', context)


@login_required
def training_detail(request, slug):
    """Detalhes do treinamento com lista de vídeos."""
    company = request.current_company
    user = request.user
    
    # Admin Master: se não tem empresa selecionada, busca em qualquer empresa
    if user.is_superuser and not company:
        training = get_object_or_404(
            Training,
            slug=slug,
            is_active=True
        )
    else:
        # Usuários normais ou Admin Master com empresa selecionada
        if not company:
            messages.error(request, 'Você precisa estar vinculado a uma empresa para acessar treinamentos.')
            return redirect('core:no_company')
        
        training = get_object_or_404(
            Training,
            company=company,
            slug=slug,
            is_active=True
        )
    
    # Verificação de permissão para usuários normais
    if not user.is_superuser:
        # Gestor tem acesso a todos os treinamentos da empresa
        if not request.is_gestor:
            # Colaborador: verifica se o treinamento está atribuído a ele ou é global
            training_check = Training.objects.filter(
                pk=training.pk
            ).annotate(
                assigned_count=Count('assigned_users')
            ).filter(
                Q(assigned_users=user) | Q(assigned_count=0)
            ).exists()
            
            if not training_check:
                messages.error(request, 'Você não tem acesso a este treinamento.')
                return redirect('trainings:list')
    
    # Força refresh do objeto training para pegar dados atualizados do banco
    training.refresh_from_db()
    
    # Busca todos os vídeos e quizzes ativos, forçando nova query e convertendo para lista
    videos = list(training.videos.filter(is_active=True).order_by('order'))
    quizzes = list(training.quizzes.filter(is_active=True).order_by('order'))
    
    # Busca progresso do usuário em cada vídeo
    if videos:
        video_ids = [v.id for v in videos]
        user_progress = UserProgress.objects.filter(
            user=request.user,
            video_id__in=video_ids
        ).values('video_id', 'completed', 'last_position')
        
        progress_map = {p['video_id']: p for p in user_progress}
    else:
        progress_map = {}
    
    # Busca tentativas de quiz do usuário (pega a última tentativa de cada quiz)
    quiz_passed_map = {}
    for quiz in quizzes:
        latest_attempt = UserQuizAttempt.objects.filter(
            user=request.user,
            quiz=quiz
        ).order_by('-completed_at').first()
        quiz_passed_map[quiz.id] = latest_attempt.is_passed if latest_attempt else False
    
    # Combina vídeos e quizzes em uma lista unificada ordenada
    content_items = []
    for video in videos:
        progress = progress_map.get(video.id, {'completed': False, 'last_position': 0})
        content_items.append({
            'type': 'video',
            'id': video.id,
            'object': video,
            'order': video.order,
            'completed': progress['completed'],
        })
    for quiz in quizzes:
        is_passed = quiz_passed_map.get(quiz.id, False)
        content_items.append({
            'type': 'quiz',
            'id': quiz.id,
            'object': quiz,
            'order': quiz.order,
            'completed': is_passed,
        })
    # Ordena por ordem
    content_items.sort(key=lambda x: x['order'])
    
    # Calcula progresso total
    total_progress = training.get_user_progress(request.user)
    
    context = {
        'training': training,
        'videos': [{'video': item['object'], 'completed': item['completed']} for item in content_items if item['type'] == 'video'],
        'content_items': content_items,
        'total_progress': total_progress,
    }
    
    return render(request, 'trainings/detail.html', context)


@login_required
def video_player(request, training_slug, video_id):
    """Player de vídeo com tracking de progresso."""
    return content_player(request, training_slug, 'video', video_id)


@login_required
def content_player(request, training_slug, content_type, content_id):
    """
    Player unificado para vídeos e quizzes.
    Aceita content_type: 'video' ou 'quiz'
    """
    company = request.current_company
    user = request.user
    
    # Admin Master: se não tem empresa selecionada, busca em qualquer empresa
    if user.is_superuser and not company:
        training = get_object_or_404(
            Training,
            slug=training_slug,
            is_active=True
        )
    else:
        # Usuários normais ou Admin Master com empresa selecionada
        if not company:
            messages.error(request, 'Você precisa estar vinculado a uma empresa para acessar treinamentos.')
            return redirect('core:no_company')
        
        training = get_object_or_404(
            Training,
            company=company,
            slug=training_slug,
            is_active=True
        )
    
    # Força refresh do training para pegar dados atualizados
    training.refresh_from_db()
    
    # Busca todos os conteúdos ordenados (força nova query)
    videos = list(training.videos.filter(is_active=True).order_by('order'))
    quizzes = list(training.quizzes.filter(is_active=True).order_by('order'))
    
    # Busca progresso do usuário
    user_progress = UserProgress.objects.filter(
        user=user,
        video__in=videos
    ).values('video_id', 'completed')
    progress_map = {p['video_id']: p['completed'] for p in user_progress}
    
    # Busca tentativas de quiz do usuário
    quiz_passed_map = {}
    for quiz in quizzes:
        latest_attempt = UserQuizAttempt.objects.filter(
            user=user,
            quiz=quiz
        ).order_by('-completed_at').first()
        quiz_passed_map[quiz.id] = latest_attempt.is_passed if latest_attempt else False
    
    # Combina em lista unificada
    all_content = []
    for video in videos:
        all_content.append({
            'type': 'video', 
            'id': video.id, 
            'order': video.order, 
            'object': video,
            'completed': progress_map.get(video.id, False)
        })
    for quiz in quizzes:
        all_content.append({
            'type': 'quiz', 
            'id': quiz.id, 
            'order': quiz.order, 
            'object': quiz,
            'completed': quiz_passed_map.get(quiz.id, False)
        })
    all_content.sort(key=lambda x: x['order'])
    
    # Busca o conteúdo atual
    current_content = None
    current_index = -1
    for idx, item in enumerate(all_content):
        if item['type'] == content_type and item['id'] == content_id:
            current_content = item
            current_index = idx
            break
    
    if not current_content:
        messages.error(request, 'Conteúdo não encontrado.')
        return redirect('trainings:detail', slug=training_slug)
    
    # Verifica se pode acessar (deve ter completado o anterior)
    if current_index > 0 and not user.is_superuser:
        prev_content = all_content[current_index - 1]
        can_access = False
        
        if prev_content['type'] == 'video':
            prev_progress = UserProgress.objects.filter(
                user=user,
                video_id=prev_content['id'],
                completed=True
            ).exists()
            can_access = prev_progress
        elif prev_content['type'] == 'quiz':
            prev_attempt = UserQuizAttempt.objects.filter(
                user=user,
                quiz_id=prev_content['id'],
                is_passed=True
            ).exists()
            can_access = prev_attempt
        
        if not can_access:
            prev_obj = prev_content['object']
            messages.warning(request, f'Você precisa completar o conteúdo anterior "{prev_obj.title}" antes de acessar este.')
            if prev_content['type'] == 'video':
                return redirect('trainings:content_player', training_slug=training.slug, content_type='video', content_id=prev_content['id'])
            else:
                return redirect('trainings:content_player', training_slug=training.slug, content_type='quiz', content_id=prev_content['id'])
    
    # Próximo e anterior
    next_content = all_content[current_index + 1] if current_index + 1 < len(all_content) else None
    prev_content = all_content[current_index - 1] if current_index > 0 else None
    
    context = {
        'training': training,
        'content_type': content_type,
        'all_content': all_content,
        'current_index': current_index,
        'next_content': next_content,
        'prev_content': prev_content,
    }
    
    # Adiciona dados específicos do tipo
    if content_type == 'video':
        video = current_content['object']
        progress, created = UserProgress.objects.get_or_create(user=user, video=video)
        context.update({
            'video': video,
            'progress': progress,
        })
    elif content_type == 'quiz':
        quiz = current_content['object']
        # Força refresh do quiz para pegar dados atualizados
        quiz.refresh_from_db()
        
        # Verifica se está mostrando resultado de uma tentativa
        attempt_id = request.GET.get('result')
        if attempt_id:
            try:
                attempt = UserQuizAttempt.objects.get(pk=attempt_id, user=user, quiz=quiz)
                
                # Verifica se completou o treinamento após aprovar o quiz
                training_completed = False
                if attempt.is_passed:
                    training_completed = training.is_completed_by(user)
                    if training_completed:
                        # Cria recompensa se ainda não existe
                        UserTrainingReward.objects.get_or_create(
                            user=user,
                            training=training,
                            defaults={
                                'points_earned': training.reward_points,
                                'badge_earned': training.reward_badge,
                            }
                        )
                        # Adiciona pontos ao usuário
                        user.add_points(training.reward_points)
                
                # Carrega perguntas com opções e respostas corretas
                normalized_attempt_answers = {}
                for key, value in attempt.answers.items():
                    clean_key = str(key).replace('question_', '')
                    normalized_attempt_answers[clean_key] = str(value).strip()
                
                result_questions = []
                for question in quiz.questions.all().prefetch_related('choices').order_by('order'):
                    question_id_str = str(question.id)
                    selected_choice_id_str = normalized_attempt_answers.get(question_id_str)
                    
                    selected_choice = None
                    if selected_choice_id_str:
                        try:
                            selected_choice_id = int(selected_choice_id_str)
                            selected_choice = Choice.objects.get(id=selected_choice_id, question=question)
                        except (ValueError, TypeError, Choice.DoesNotExist):
                            selected_choice = None
                    
                    is_correct = selected_choice.is_correct if selected_choice else False
                    
                    result_questions.append({
                        'question': question,
                        'selected_choice': selected_choice,
                        'is_correct': is_correct,
                    })
                
                # Calcula progresso atualizado
                total_progress = training.get_user_progress(user)
                
                context.update({
                    'quiz': quiz,
                    'attempt': attempt,
                    'result_questions': result_questions,
                    'show_result': True,
                    'training_completed': training_completed,
                    'total_progress': total_progress,
                })
            except UserQuizAttempt.DoesNotExist:
                # Se não encontrar a tentativa, mostra quiz normal
                pass
        
        # Se não está mostrando resultado, mostra quiz normal
        if 'show_result' not in context:
            # Busca todas as perguntas ordenadas (força nova query)
            questions = list(quiz.questions.all().prefetch_related('choices').order_by('order'))
            current_question_index = request.GET.get('question', 0)
            try:
                current_question_index = int(current_question_index)
            except:
                current_question_index = 0
            
            if current_question_index >= len(questions):
                current_question_index = 0
            
            current_question = questions[current_question_index] if questions else None
            context.update({
                'quiz': quiz,
                'questions': questions,
                'current_question': current_question,
                'current_question_index': current_question_index,
                'total_questions': len(questions),
            })
    
    return render(request, 'trainings/player.html', context)


@login_required
@require_POST
def update_progress(request, video_id):
    """API para atualizar progresso do vídeo via AJAX."""
    video = get_object_or_404(Video, id=video_id)
    company = request.current_company
    user = request.user
    
    # Verifica se usuário tem acesso
    # Admin Master sem empresa: pode acessar qualquer vídeo
    if not user.is_superuser or company:
        if video.training.company != company:
            return JsonResponse({'error': 'Não autorizado'}, status=403)
    
    progress, _ = UserProgress.objects.get_or_create(
        user=request.user,
        video=video
    )
    
    # Atualiza posição
    current_time = int(request.POST.get('current_time', 0))
    progress.last_position = current_time
    progress.watched_seconds = max(progress.watched_seconds, current_time)
    
    # Marca como completo se assistiu 90% ou mais
    if current_time >= video.duration_seconds * 0.9:
        if not progress.completed:
            progress.mark_completed()
            
            # Verifica se completou o treinamento
            training = video.training
            if training.is_completed_by(request.user):
                return JsonResponse({
                    'success': True,
                    'completed': True,
                    'training_completed': True,
                    'reward_points': training.reward_points,
                    'message': f'Parabéns! Você completou o treinamento "{training.title}" e ganhou {training.reward_points} pontos!'
                })
            
            return JsonResponse({
                'success': True,
                'completed': True,
                'training_completed': False,
                'message': 'Vídeo concluído!'
            })
    
    progress.save()
    
    return JsonResponse({
        'success': True,
        'completed': progress.completed,
        'progress_percentage': progress.progress_percentage
    })


# ============================================================================
# Views para Gestores
# ============================================================================

@login_required
@gestor_required
def training_manage_list(request):
    """Lista de treinamentos para gestão."""
    # Admin Master vê todos os treinamentos de todas as empresas
    if request.user.is_superuser:
        trainings = Training.objects.all().select_related('company').prefetch_related('videos')
        companies = Company.objects.filter(is_active=True)
    else:
        company = request.current_company
        trainings = Training.objects.filter(company=company).prefetch_related('videos')
        companies = None
    
    return render(request, 'trainings/manage/list.html', {
        'trainings': trainings,
        'companies': companies,
        'is_admin_master': request.user.is_superuser,
    })


@login_required
@gestor_required
def training_create(request):
    """
    Criar novo treinamento.
    ACCESS: ADMIN MASTER | GESTOR
    - Admin Master: Pode criar treinamento em qualquer empresa
    - Gestor: Pode criar treinamento apenas na sua empresa
    """
    
    # Admin Master pode escolher a empresa
    is_admin = request.user.is_superuser
    companies = Company.objects.filter(is_active=True) if is_admin else None
    
    # Validação crítica: Gestor precisa ter empresa vinculada
    if not is_admin and not request.current_company:
        messages.error(request, 'Você precisa estar vinculado a uma empresa para criar treinamentos.')
        return redirect('core:no_company')
    
    if request.method == 'POST':
        if is_admin:
            form = AdminTrainingForm(request.POST, request.FILES)
        else:
            form = TrainingForm(request.POST, request.FILES, company=request.current_company)
        
        if form.is_valid():
            training = form.save(commit=False)
            
            # Admin Master: company vem do form
            # Gestor: força company da sessão
            if not is_admin:
                if not request.current_company:
                    messages.error(request, 'Empresa não encontrada. Tente fazer login novamente.')
                    return redirect('core:no_company')
                training.company = request.current_company
            
            # Validação final: garantir que company foi atribuído
            if not training.company:
                messages.error(request, 'Erro: Empresa não foi atribuída. Tente novamente.')
                return render(request, 'trainings/manage/form.html', {
                    'form': form,
                    'title': 'Novo Treinamento',
                    'companies': companies,
                    'is_admin_master': is_admin,
                })
            
            # Atribui order automaticamente se não foi definido
            if not training.order or training.order == 0:
                max_order = Training.objects.filter(company=training.company).aggregate(
                    max_order=Max('order')
                )['max_order'] or 0
                training.order = max_order + 1
            
            training.save()
            
            # Salva ManyToMany (assigned_users)
            if 'assigned_users' in form.cleaned_data:
                training.assigned_users.set(form.cleaned_data['assigned_users'])
            
            messages.success(request, 'Treinamento criado com sucesso! Agora você pode adicionar vídeos.')
            return redirect('trainings:manage_detail', pk=training.pk)
    else:
        if is_admin:
            form = AdminTrainingForm()
        else:
            form = TrainingForm(company=request.current_company)
    
    return render(request, 'trainings/manage/form.html', {
        'form': form,
        'title': 'Novo Treinamento',
        'companies': companies,
        'is_admin_master': is_admin,
    })


@login_required
@gestor_required
def training_edit(request, pk):
    """Editar treinamento existente."""
    
    is_admin = request.user.is_superuser
    
    # Admin pode editar qualquer treinamento
    if is_admin:
        training = get_object_or_404(Training, pk=pk)
    else:
        training = get_object_or_404(Training, pk=pk, company=request.current_company)
    
    if request.method == 'POST':
        if is_admin:
            form = AdminTrainingForm(request.POST, request.FILES, instance=training)
        else:
            form = TrainingForm(request.POST, request.FILES, instance=training, company=request.current_company)
        
        if form.is_valid():
            training = form.save()
            
            # Salva ManyToMany (assigned_users)
            if 'assigned_users' in form.cleaned_data:
                training.assigned_users.set(form.cleaned_data['assigned_users'])
            
            messages.success(request, 'Treinamento atualizado!')
            return redirect('trainings:manage_detail', pk=training.pk)
    else:
        if is_admin:
            form = AdminTrainingForm(instance=training)
        else:
            form = TrainingForm(instance=training, company=request.current_company)
    
    companies = Company.objects.filter(is_active=True) if is_admin else None
    
    return render(request, 'trainings/manage/form.html', {
        'form': form,
        'training': training,
        'title': 'Editar Treinamento',
        'is_admin_master': is_admin,
        'companies': companies,
    })


@login_required
@gestor_required
def training_manage_detail(request, pk):
    """Detalhes do treinamento para gestão (adicionar vídeos)."""
    
    is_admin = request.user.is_superuser
    
    # Admin pode ver qualquer treinamento
    if is_admin:
        training = get_object_or_404(Training, pk=pk)
    else:
        training = get_object_or_404(Training, pk=pk, company=request.current_company)
    
    videos = training.videos.all().order_by('order')
    quizzes = training.quizzes.all().order_by('order')
    
    # Combina vídeos e quizzes em uma lista unificada ordenada
    content_items = []
    for video in videos:
        content_items.append({
            'type': 'video',
            'id': video.id,
            'object': video,
            'order': video.order,
        })
    for quiz in quizzes:
        content_items.append({
            'type': 'quiz',
            'id': quiz.id,
            'object': quiz,
            'order': quiz.order,
        })
    # Ordena por ordem
    content_items.sort(key=lambda x: x['order'])
    
    # Form para adicionar vídeo
    video_form = VideoUploadForm()
    quiz_form = QuizForm()
    
    if request.method == 'POST':
        # Verifica qual formulário foi submetido
        if 'add_video' in request.POST:
            video_form = VideoUploadForm(request.POST, request.FILES)
            if video_form.is_valid():
                video = Video.objects.create(
                    training=training,
                    title=video_form.cleaned_data['title'],
                    description=video_form.cleaned_data.get('description', ''),
                    video_file=video_form.cleaned_data['video_file'],
                    order=videos.count() + 1
                )
                messages.success(request, f'Vídeo "{video.title}" adicionado!')
                return redirect('trainings:manage_detail', pk=pk)
        
        elif 'add_quiz' in request.POST:
            quiz_form = QuizForm(request.POST)
            if quiz_form.is_valid():
                quiz = quiz_form.save(commit=False)
                quiz.training = training
                # Define ordem automaticamente se não foi informada
                if not quiz.order or quiz.order == 0:
                    # Pega a maior ordem entre vídeos e quizzes
                    max_video_order = videos.aggregate(Max('order'))['order__max'] or 0
                    max_quiz_order = quizzes.aggregate(Max('order'))['order__max'] or 0
                    quiz.order = max(max_video_order, max_quiz_order) + 1
                quiz.save()
                messages.success(request, f'Quiz "{quiz.title}" criado! Agora você pode adicionar perguntas editando-o.')
                return redirect('trainings:manage_detail', pk=pk)
    
    context = {
        'training': training,
        'videos': videos,
        'quizzes': quizzes,
        'content_items': content_items,
        'video_form': video_form,
        'quiz_form': quiz_form,
        'is_admin_master': is_admin,
    }
    
    return render(request, 'trainings/manage/detail.html', context)


@login_required
@gestor_required
@require_POST
def training_delete(request, pk):
    """Excluir treinamento."""
    
    is_admin = request.user.is_superuser
    
    if is_admin:
        training = get_object_or_404(Training, pk=pk)
    else:
        training = get_object_or_404(Training, pk=pk, company=request.current_company)
    
    training.delete()
    messages.success(request, 'Treinamento excluído!')
    
    return redirect('trainings:manage_list')


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
        form = VideoForm(request.POST, request.FILES, instance=video)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vídeo atualizado com sucesso!')
            return redirect('trainings:manage_detail', pk=training.pk)
    else:
        form = VideoForm(instance=video)
    
    context = {
        'training': training,
        'video': video,
        'form': form,
    }
    return render(request, 'trainings/manage/video_form.html', context)


@login_required
@gestor_required_ajax
@require_POST
def video_delete(request, video_id):
    """Excluir vídeo."""
    
    is_admin = request.user.is_superuser
    
    if is_admin:
        video = get_object_or_404(Video, id=video_id)
    else:
        video = get_object_or_404(Video, id=video_id, training__company=request.current_company)
    
    video.delete()
    
    return JsonResponse({'success': True, 'message': 'Vídeo excluído!'})


@login_required
@gestor_required_ajax
@require_POST
def video_reorder(request):
    """Reordenar vídeos via AJAX."""
    data = json.loads(request.body)
    
    is_admin = request.user.is_superuser
    
    for item in data.get('videos', []):
        if is_admin:
            Video.objects.filter(id=item['id']).update(order=item['order'])
        else:
            Video.objects.filter(
                id=item['id'],
                training__company=request.current_company
            ).update(order=item['order'])
    
    return JsonResponse({'success': True})


@login_required
@gestor_required_ajax
@require_POST
def content_reorder(request):
    """Reordenar conteúdo (vídeos e quizzes) via AJAX."""
    data = json.loads(request.body)
    
    is_admin = request.user.is_superuser
    
    for item in data.get('content', []):
        content_type = item.get('type')
        content_id = item.get('id')
        new_order = item.get('order')
        
        if content_type == 'video':
            if is_admin:
                Video.objects.filter(id=content_id).update(order=new_order)
            else:
                Video.objects.filter(
                    id=content_id,
                    training__company=request.current_company
                ).update(order=new_order)
        elif content_type == 'quiz':
            if is_admin:
                Quiz.objects.filter(id=content_id).update(order=new_order)
            else:
                Quiz.objects.filter(
                    id=content_id,
                    training__company=request.current_company
                ).update(order=new_order)
    
    return JsonResponse({'success': True})


@login_required
@gestor_required_ajax
def get_company_users(request):
    """
    API para buscar usuários de uma empresa (para atribuição de treinamentos).
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
def get_training_status(request, training_id):
    """
    API para obter status atualizado do treinamento (progresso, quizzes aprovados, etc).
    """
    training = get_object_or_404(Training, pk=training_id)
    user = request.user
    
    # Verifica acesso
    is_admin = user.is_superuser
    if not is_admin:
        company = request.current_company
        if not company or training.company != company:
            return JsonResponse({'error': 'Não autorizado'}, status=403)
    
    # Calcula progresso
    total_progress = training.get_user_progress(user)
    is_completed = training.is_completed_by(user)
    
    # Status de vídeos e quizzes
    content_status = []
    videos = training.videos.filter(is_active=True).order_by('order')
    quizzes = training.quizzes.filter(is_active=True).order_by('order')
    
    # Vídeos
    user_progress = UserProgress.objects.filter(
        user=user,
        video__in=videos
    ).values('video_id', 'completed')
    progress_map = {p['video_id']: p['completed'] for p in user_progress}
    
    for video in videos:
        content_status.append({
            'type': 'video',
            'id': video.id,
            'order': video.order,
            'completed': progress_map.get(video.id, False),
        })
    
    # Quizzes
    for quiz in quizzes:
        # Verifica se foi aprovado (pega a última tentativa)
        latest_attempt = UserQuizAttempt.objects.filter(
            user=user,
            quiz=quiz
        ).order_by('-completed_at').first()
        
        content_status.append({
            'type': 'quiz',
            'id': quiz.id,
            'order': quiz.order,
            'completed': latest_attempt.is_passed if latest_attempt else False,
        })
    
    # Ordena por ordem
    content_status.sort(key=lambda x: x['order'])
    
    return JsonResponse({
        'success': True,
        'training': {
            'id': training.id,
            'title': training.title,
            'total_progress': round(total_progress, 1),
            'is_completed': is_completed,
        },
        'content_status': content_status,
    })


@login_required
@gestor_required
def quiz_create(request, training_id):
    """
    Criar novo quiz para um treinamento.
    ACCESS: ADMIN MASTER | GESTOR
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
        
        if quiz_form.is_valid() and question_formset.is_valid():
            quiz = quiz_form.save(commit=False)
            quiz.training = training
            quiz.save()
            
            # Salva perguntas
            questions = question_formset.save(commit=False)
            for question in questions:
                question.quiz = quiz
                question.save()
            
            # Validação: Para cada pergunta, verifica opções
            validation_errors = []
            for idx, form in enumerate(question_formset.forms):
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    question = form.instance
                    question_text = form.cleaned_data.get('text', '').strip()
                    
                    if not question_text:
                        continue
                    
                    # PRIORIDADE: Se a pergunta já existe, processa via formset primeiro
                    if question.pk:
                        choice_prefix = f'choices_{question.id}'
                        choice_formset = ChoiceFormSet(
                            request.POST,
                            instance=question,
                            prefix=choice_prefix
                        )
                        
                        if choice_formset.is_valid():
                            valid_choices = []
                            has_correct = False
                            
                            for choice_form in choice_formset.forms:
                                if choice_form.cleaned_data and not choice_form.cleaned_data.get('DELETE', False):
                                    choice_text = choice_form.cleaned_data.get('text', '').strip()
                                    if not choice_text:
                                        validation_errors.append(f'Pergunta "{question_text[:50]}": Todas as opções devem ter texto preenchido.')
                                        break
                                    if choice_form.cleaned_data.get('is_correct', False):
                                        has_correct = True
                                    valid_choices.append(choice_form)
                            
                            if not has_correct and valid_choices:
                                validation_errors.append(f'Pergunta "{question_text[:50]}": Deve ter pelo menos uma resposta correta marcada.')
                            
                            if not validation_errors:
                                for choice_form in valid_choices:
                                    choice = choice_form.save(commit=False)
                                    choice.question = question
                                    choice.save()
                            
                            # Deleta opções marcadas
                            for del_form in choice_formset.deleted_forms:
                                if del_form.instance.pk:
                                    del_form.instance.delete()
                    else:
                        # Pergunta nova sem opções
                        validation_errors.append(f'Pergunta "{question_text[:50]}": Adicione pelo menos 2 opções de resposta.')
            
            if validation_errors:
                for error in validation_errors:
                    messages.error(request, error)
                # Recarrega o formulário com erros
                quiz_form = QuizForm(request.POST)
                question_formset = QuestionFormSet(request.POST, prefix='questions')
                context = {
                    'training': training,
                    'quiz_form': quiz_form,
                    'question_formset': question_formset,
                }
                return render(request, 'trainings/manage/quiz_form.html', context)
            
            messages.success(request, 'Quiz criado com sucesso!')
            return redirect('trainings:manage_detail', pk=training.pk)
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
        
        if quiz_form.is_valid() and question_formset.is_valid():
            quiz_form.save()
            
            # Salva perguntas
            questions = question_formset.save(commit=False)
            for question in questions:
                question.quiz = quiz
                question.save()
            
            # Deleta perguntas marcadas
            for form in question_formset.deleted_forms:
                if form.instance.pk:
                    form.instance.delete()
            
            # Processa opções de cada pergunta
            validation_errors = []
            for idx, form in enumerate(question_formset.forms):
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    question = form.instance
                    question_text = form.cleaned_data.get('text', '').strip()
                    
                    if not question_text:
                        continue
                    
                    # Processa opções dinâmicas do JavaScript (formato: choice_{questionIndex}_{choiceCount}_text)
                    dynamic_choices = []
                    choice_index = 0
                    while True:
                        choice_text_key = f'choice_{idx}_{choice_index}_text'
                        choice_correct_key = f'choice_{idx}_{choice_index}_is_correct'
                        
                        if choice_text_key not in request.POST:
                            break
                        
                        choice_text = request.POST.get(choice_text_key, '').strip()
                        if choice_text:  # Só adiciona se tiver texto
                            # Checkbox marcado envia 'on', não marcado não envia nada
                            is_correct = choice_correct_key in request.POST and request.POST.get(choice_correct_key) == 'on'
                            dynamic_choices.append({
                                'text': choice_text,
                                'is_correct': is_correct
                            })
                        choice_index += 1
                    
                    # Se tem opções dinâmicas, valida e salva
                    if dynamic_choices:
                        if len(dynamic_choices) < 2:
                            validation_errors.append(f'Pergunta "{question_text[:50]}": Adicione pelo menos 2 opções de resposta.')
                            continue
                        
                        has_correct = any(c['is_correct'] for c in dynamic_choices)
                        if not has_correct:
                            validation_errors.append(f'Pergunta "{question_text[:50]}": Marque pelo menos uma opção como correta.')
                            continue
                        
                        # Remove opções antigas e cria novas
                        question.choices.all().delete()
                        for order, choice_data in enumerate(dynamic_choices):
                            choice = Choice.objects.create(
                                question=question,
                                text=choice_data['text'],
                                is_correct=choice_data['is_correct'],
                                order=order
                            )
                            # DEBUG: Log para verificar se está salvando corretamente
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.info(f'✅ Escolha criada: ID={choice.id}, Texto="{choice.text}", is_correct={choice.is_correct}')
                    
                    # Processa opções via formset (para perguntas existentes)
                    elif question.pk:
                        choice_prefix = f'choices_{question.id}'
                        choice_formset = ChoiceFormSet(
                            request.POST,
                            instance=question,
                            prefix=choice_prefix
                        )
                        
                        if choice_formset.is_valid():
                            choices = choice_formset.save(commit=False)
                            valid_choices = []
                            has_correct = False
                            
                            for choice_form in choice_formset.forms:
                                if choice_form.cleaned_data and not choice_form.cleaned_data.get('DELETE', False):
                                    choice_text = choice_form.cleaned_data.get('text', '').strip()
                                    if not choice_text:
                                        validation_errors.append(f'Pergunta "{question_text[:50]}": Todas as opções devem ter texto preenchido.')
                                        break
                                    if choice_form.cleaned_data.get('is_correct', False):
                                        has_correct = True
                                    valid_choices.append(choice_form)
                            
                            if not has_correct and valid_choices:
                                validation_errors.append(f'Pergunta "{question_text[:50]}": Deve ter pelo menos uma resposta correta marcada.')
                            
                            if not validation_errors:
                                for choice_form in valid_choices:
                                    choice = choice_form.save(commit=False)
                                    choice.question = question
                                    choice.save()
                            
                            # Deleta opções marcadas
                            for del_form in choice_formset.deleted_forms:
                                if del_form.instance.pk:
                                    del_form.instance.delete()
                    else:
                        # PERGUNTA NOVA: Processa opções dinâmicas do JavaScript
                        logger.info(f'Pergunta nova - Processando opções dinâmicas')
                        dynamic_choices = []
                        choice_index = 0
                        while True:
                            choice_text_key = f'choice_{idx}_{choice_index}_text'
                            choice_correct_key = f'choice_{idx}_{choice_index}_is_correct'
                            
                            if choice_text_key not in request.POST:
                                break
                            
                            choice_text = request.POST.get(choice_text_key, '').strip()
                            if choice_text:
                                is_correct = choice_correct_key in request.POST and request.POST.get(choice_correct_key) == 'on'
                                logger.info(f'  Opção dinâmica {choice_index}: Texto="{choice_text[:30]}", is_correct={is_correct}')
                                dynamic_choices.append({
                                    'text': choice_text,
                                    'is_correct': is_correct
                                })
                            choice_index += 1
                        
                        if dynamic_choices:
                            if len(dynamic_choices) < 2:
                                validation_errors.append(f'Pergunta "{question_text[:50]}": Adicione pelo menos 2 opções de resposta.')
                                continue
                            
                            has_correct = any(c['is_correct'] for c in dynamic_choices)
                            if not has_correct:
                                validation_errors.append(f'Pergunta "{question_text[:50]}": Marque pelo menos uma opção como correta.')
                                continue
                            
                            Choice.objects.filter(question=question).delete()
                            for order, choice_data in enumerate(dynamic_choices):
                                choice = Choice.objects.create(
                                    question=question,
                                    text=choice_data['text'],
                                    is_correct=choice_data['is_correct'],
                                    order=order
                                )
                                logger.info(f'  ✅ Opção criada: ID={choice.id}, is_correct={choice.is_correct}')
                        else:
                            validation_errors.append(f'Pergunta "{question_text[:50]}": Adicione pelo menos 2 opções de resposta.')
            
            if validation_errors:
                for error in validation_errors:
                    messages.error(request, error)
                # Recarrega o formulário com erros
                quiz_form = QuizForm(request.POST, instance=quiz)
                question_formset = QuestionFormSet(request.POST, instance=quiz, prefix='questions')
                choice_formsets = {}
                for question in quiz.questions.all():
                    choice_formsets[question.id] = ChoiceFormSet(
                        instance=question,
                        prefix=f'choices_{question.id}'
                    )
                # Força refresh antes de renderizar
                quiz.refresh_from_db()
                context = {
                    'training': training,
                    'quiz': quiz,
                    'quiz_form': quiz_form,
                    'question_formset': question_formset,
                    'choice_formsets': choice_formsets,
                }
                return render(request, 'trainings/manage/quiz_form.html', context)
            
            # Força refresh do quiz após salvar
            quiz.refresh_from_db()
            messages.success(request, 'Quiz atualizado com sucesso!')
            return redirect('trainings:manage_detail', pk=training.pk)
    else:
        quiz_form = QuizForm(instance=quiz)
        question_formset = QuestionFormSet(instance=quiz, prefix='questions')
    
    # Prepara formsets de opções para cada pergunta existente
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
        quiz.delete()
        messages.success(request, 'Quiz deletado com sucesso!')
        return redirect('trainings:manage_detail', pk=training.pk)
    
    return redirect('trainings:manage_detail', pk=training.pk)


@login_required
def quiz_take(request, training_slug, quiz_id):
    """
    Colaborador responde o quiz (processa todas as respostas e finaliza).
    ACCESS: ADMIN MASTER | GESTOR | COLABORADOR (se atribuído)
    """
    training = get_object_or_404(Training, slug=training_slug, is_active=True)
    quiz = get_object_or_404(Quiz, pk=quiz_id, training=training, is_active=True)
    user = request.user
    company = request.current_company
    
    # Verifica acesso ao treinamento
    if not user.is_superuser:
        if not company or training.company != company:
            messages.error(request, 'Você não tem acesso a este treinamento.')
            return redirect('trainings:list')
        
        # Gestor vê tudo, colaborador só se atribuído ou global
        if not request.is_gestor:
            from django.db.models import Count
            has_access = Training.objects.filter(
                pk=training.pk
            ).annotate(
                assigned_count=Count('assigned_users')
            ).filter(
                Q(assigned_users=user) | Q(assigned_count=0)
            ).exists()
            
            if not has_access:
                messages.error(request, 'Você não tem acesso a este treinamento.')
                return redirect('trainings:list')
    
    # Permite acesso perpétuo ao quiz, mesmo após aprovação
    # O status de "Aprovado" será mantido, mas o usuário pode refazer quantas vezes quiser
    
    if request.method == 'POST':
        # Força refresh do quiz para pegar dados atualizados
        quiz.refresh_from_db()
        
        # Processa respostas (pode vir do localStorage via JavaScript ou do form)
        answers = {}
        
        import json
        
        # PRIORIDADE 1: Tenta pegar do POST (respostas diretas do form)
        for key, value in request.POST.items():
            # Ignora campos do sistema
            if key in ['csrfmiddlewaretoken', 'question_index', 'answers_json']:
                continue
            if key.startswith('question_'):
                question_id = key.replace('question_', '')
                # Garante que o valor seja string para consistência
                answers[str(question_id)] = str(value).strip()
        
        # PRIORIDADE 2: SEMPRE tenta pegar do answers_json (localStorage) e MERGE com POST
        # Isso garante que todas as respostas sejam capturadas, mesmo que algumas venham do POST
        answers_str = request.POST.get('answers_json', '{}')
        try:
            json_answers = json.loads(answers_str)
            # Normaliza: remove 'question_' do início das chaves e converte para string
            for k, v in json_answers.items():
                # Remove 'question_' se existir
                question_id = str(k).replace('question_', '')
                clean_value = str(v).strip()
                if clean_value:  # Só adiciona se não estiver vazio
                    # MERGE: Se já existe no answers (do POST), mantém; senão, adiciona do JSON
                    if question_id not in answers:
                        answers[question_id] = clean_value
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f'Erro ao processar answers_json: {e}')
            # Se der erro, continua com answers do POST
        
        # PRIORIDADE 3: Se ainda não tem, tenta pegar do body JSON (se vier via AJAX)
        if not answers:
            try:
                body_data = json.loads(request.body)
                answers = body_data.get('answers', {})
                # Normaliza para string
                normalized_answers = {}
                for k, v in answers.items():
                    question_id = str(k).replace('question_', '')
                    normalized_answers[question_id] = str(v)
                answers = normalized_answers
            except:
                answers = {}
        
        # Valida se tem respostas antes de criar tentativa
        if not answers:
            messages.error(request, 'Nenhuma resposta foi enviada. Por favor, responda todas as perguntas.')
            return redirect('trainings:content_player', training_slug=training.slug, content_type='quiz', content_id=quiz_id)
        
        # DEBUG: Log das respostas recebidas ANTES de criar tentativa
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f'=== QUIZ {quiz.id} - PROCESSANDO RESPOSTAS ===')
        logger.info(f'POST completo: {dict(request.POST)}')
        logger.info(f'answers_json recebido: {request.POST.get("answers_json", "NÃO ENVIADO")}')
        logger.info(f'Respostas finais processadas: {answers}')
        
        # Valida se todas as perguntas têm resposta
        quiz.refresh_from_db()
        all_questions = list(quiz.questions.all().prefetch_related('choices').order_by('order'))
        total_questions = len(all_questions)
        logger.info(f'Total de perguntas no quiz: {total_questions}')
        
        # DEBUG: Mostra todas as perguntas e suas escolhas corretas
        for q in all_questions:
            choices_info = [(c.id, c.text[:30], c.is_correct) for c in q.choices.all()]
            correct_choices = [c.id for c in q.choices.all() if c.is_correct]
            logger.info(f'Pergunta {q.id} ({q.text[:50]}): Escolhas {choices_info}')
            logger.info(f'  -> Escolhas CORRETAS: {correct_choices}')
            if str(q.id) in answers:
                logger.info(f'  -> Resposta selecionada pelo usuário: {answers[str(q.id)]}')
            else:
                logger.warning(f'  -> ⚠️ NENHUMA RESPOSTA para pergunta {q.id}')
        
        if len(answers) < total_questions:
            logger.warning(f'Quiz {quiz.id} - Apenas {len(answers)} de {total_questions} perguntas foram respondidas')
        
        # Cria tentativa com as respostas normalizadas
        attempt = UserQuizAttempt.objects.create(
            user=user,
            quiz=quiz,
            answers=answers
        )
        
        # Calcula nota (já faz refresh interno)
        score = attempt.calculate_score()
        
        # DEBUG: Log do resultado
        logger.info(f'=== RESULTADO ===')
        logger.info(f'Pontuação: {score}%')
        logger.info(f'Corretas: {attempt.correct_answers}/{attempt.total_questions}')
        logger.info(f'Aprovado: {attempt.is_passed}')
        
        # Redireciona para content_player com resultado
        from django.urls import reverse
        result_url = reverse('trainings:content_player', kwargs={
            'training_slug': training.slug,
            'content_type': 'quiz',
            'content_id': quiz_id
        }) + f'?result={attempt.id}'
        return redirect(result_url)
    
    # Se GET, redireciona para content_player
    return redirect('trainings:content_player', training_slug=training.slug, content_type='quiz', content_id=quiz_id)


@login_required
def quiz_result(request, training_slug, attempt_id):
    """
    Mostra resultado da tentativa do quiz.
    """
    training = get_object_or_404(Training, slug=training_slug, is_active=True)
    attempt = get_object_or_404(UserQuizAttempt, pk=attempt_id, user=request.user)
    quiz = attempt.quiz
    
    # Verifica se completou o treinamento após aprovar o quiz
    training_completed = False
    if attempt.is_passed:
        training_completed = training.is_completed_by(request.user)
        if training_completed:
            # Cria recompensa se ainda não existe
            UserTrainingReward.objects.get_or_create(
                user=request.user,
                training=training,
                defaults={
                    'points_earned': training.reward_points,
                    'badge_earned': training.reward_badge,
                }
            )
            # Adiciona pontos ao usuário
            request.user.add_points(training.reward_points)
    
    # Carrega perguntas com opções e respostas corretas
    # Normaliza as respostas do attempt para garantir tipos consistentes
    normalized_attempt_answers = {}
    for key, value in attempt.answers.items():
        clean_key = str(key).replace('question_', '')
        normalized_attempt_answers[clean_key] = str(value).strip()
    
    questions = []
    for question in quiz.questions.all().prefetch_related('choices').order_by('order'):
        question_id_str = str(question.id)
        
        # Busca resposta normalizada (chave sempre string)
        selected_choice_id_str = normalized_attempt_answers.get(question_id_str)
        
        selected_choice = None
        if selected_choice_id_str:
            try:
                # Converte para int para buscar no banco
                selected_choice_id = int(selected_choice_id_str)
                selected_choice = Choice.objects.get(id=selected_choice_id, question=question)
            except (ValueError, TypeError, Choice.DoesNotExist):
                selected_choice = None
        
        # Verifica se está correto (comparação robusta)
        is_correct = False
        if selected_choice:
            is_correct = selected_choice.is_correct
        
        questions.append({
            'question': question,
            'selected_choice': selected_choice,
            'is_correct': is_correct,
        })
    
    # Calcula progresso atualizado
    total_progress = training.get_user_progress(request.user)
    
    context = {
        'training': training,
        'quiz': quiz,
        'attempt': attempt,
        'questions': questions,
        'training_completed': training_completed,
        'total_progress': total_progress,
    }
    return render(request, 'trainings/quiz_result.html', context)

