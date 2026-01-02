"""
Views para treinamentos.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Max

from .models import Training, Video, UserProgress, UserTrainingReward
from .forms import TrainingForm, VideoUploadForm, AdminTrainingForm
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
        
        # Filtra treinamentos: assigned_users contém o usuário OU assigned_users está vazio (global)
        from django.db.models import Q
        trainings = Training.objects.filter(
            company=company,
            is_active=True
        ).filter(
            Q(assigned_users=user) | Q(assigned_users__isnull=True)
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
    
    training = get_object_or_404(
        Training,
        company=company,
        slug=slug,
        is_active=True
    )
    
    videos = training.videos.filter(is_active=True).order_by('order')
    
    # Busca progresso do usuário em cada vídeo
    user_progress = UserProgress.objects.filter(
        user=request.user,
        video__in=videos
    ).values('video_id', 'completed', 'last_position')
    
    progress_map = {p['video_id']: p for p in user_progress}
    
    videos_with_progress = []
    for video in videos:
        progress = progress_map.get(video.id, {'completed': False, 'last_position': 0})
        videos_with_progress.append({
            'video': video,
            'completed': progress['completed'],
            'last_position': progress['last_position'],
        })
    
    # Calcula progresso total
    total_progress = training.get_user_progress(request.user)
    
    context = {
        'training': training,
        'videos': videos_with_progress,
        'total_progress': total_progress,
    }
    
    return render(request, 'trainings/detail.html', context)


@login_required
def video_player(request, training_slug, video_id):
    """Player de vídeo com tracking de progresso."""
    company = request.current_company
    
    training = get_object_or_404(
        Training,
        company=company,
        slug=training_slug,
        is_active=True
    )
    
    video = get_object_or_404(
        Video,
        id=video_id,
        training=training,
        is_active=True
    )
    
    # Busca ou cria progresso do usuário
    progress, created = UserProgress.objects.get_or_create(
        user=request.user,
        video=video
    )
    
    # Próximo vídeo
    next_video = Video.objects.filter(
        training=training,
        is_active=True,
        order__gt=video.order
    ).order_by('order').first()
    
    # Vídeo anterior
    prev_video = Video.objects.filter(
        training=training,
        is_active=True,
        order__lt=video.order
    ).order_by('-order').first()
    
    context = {
        'training': training,
        'video': video,
        'progress': progress,
        'next_video': next_video,
        'prev_video': prev_video,
    }
    
    return render(request, 'trainings/player.html', context)


@login_required
@require_POST
def update_progress(request, video_id):
    """API para atualizar progresso do vídeo via AJAX."""
    video = get_object_or_404(Video, id=video_id)
    
    # Verifica se usuário tem acesso
    if video.training.company != request.current_company:
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
    
    return render(request, 'trainings/manage/form.html', {
        'form': form,
        'training': training,
        'title': 'Editar Treinamento',
        'is_admin_master': is_admin,
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
    
    # Form para adicionar vídeo
    if request.method == 'POST':
        form = VideoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            video = Video.objects.create(
                training=training,
                title=form.cleaned_data['title'],
                description=form.cleaned_data.get('description', ''),
                video_file=form.cleaned_data['video_file'],
                order=videos.count() + 1
            )
            messages.success(request, f'Vídeo "{video.title}" adicionado!')
            return redirect('trainings:manage_detail', pk=pk)
    else:
        form = VideoUploadForm()
    
    context = {
        'training': training,
        'videos': videos,
        'form': form,
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
    import json
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

