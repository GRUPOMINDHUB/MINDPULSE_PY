"""
Views para feedback.
"""

from typing import Dict, Any, Optional
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta

from .models import FeedbackTicket, FeedbackComment
from .forms import FeedbackForm, FeedbackResponseForm, FeedbackCommentForm
from apps.core.models import Company
from apps.core.decorators import gestor_required, gestor_required_ajax
from apps.core.utils import safe_int


@login_required
def feedback_list(request):
    """
    Lista de feedbacks.
    ACCESS: ADMIN MASTER | GESTOR | COLABORADOR
    - Admin Master: Vê todos os feedbacks de todas as empresas
    - Gestor: Vê feedbacks da sua empresa
    - Colaborador: Vê apenas seus próprios feedbacks
    """
    user = request.user
    company = request.current_company
    
    # Admin Master: se current_company for None, mostra todos os feedbacks (visão global)
    if user.is_superuser:
        if company:
            # Filtra por empresa selecionada
            feedbacks = FeedbackTicket.objects.filter(
                company=company
            ).select_related('user', 'company').order_by('-created_at')
        else:
            # Visão global: mostra todos os feedbacks de todas as empresas
            feedbacks = FeedbackTicket.objects.all().select_related('user', 'company').order_by('-created_at')
    else:
        # Usuários normais: precisa ter empresa vinculada
        if not company:
            return render(request, 'core/no_company.html')
        
        # Colaborador vê apenas seus próprios feedbacks
        feedbacks = FeedbackTicket.objects.filter(
            company=company,
            user=user
        ).select_related('user', 'company', 'responded_by').order_by('-created_at')
    
    context = {
        'feedbacks': feedbacks,
    }
    
    return render(request, 'feedback/list.html', context)


@login_required
def feedback_create(request):
    """
    Criar novo feedback.
    ACCESS: ADMIN MASTER | GESTOR | COLABORADOR
    Usa a empresa selecionada no sidemenu (request.current_company)
    """
    user = request.user
    
    # Verifica se há empresa selecionada
    if not request.current_company:
        messages.error(request, 'Selecione uma empresa no menu lateral antes de enviar um feedback.')
        return redirect('feedback:list')
    
    if request.method == 'POST':
        form = FeedbackForm(request.POST, request.FILES)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.company = request.current_company
            feedback.user = user
            feedback.save()
            
            messages.success(request, 'Feedback enviado com sucesso!')
            return redirect('feedback:list')
    else:
        form = FeedbackForm()
    
    return render(request, 'feedback/form.html', {
        'form': form,
    })


@login_required
@require_POST
def feedback_delete(request, pk):
    """Excluir feedback (apenas o próprio usuário)."""
    company = request.current_company
    
    if not company:
        return JsonResponse({'success': False, 'error': 'Empresa não selecionada.'}, status=403)
    
    # Colaborador só pode excluir seus próprios feedbacks
    feedback = get_object_or_404(FeedbackTicket, pk=pk, company=company, user=request.user)
    
    feedback.delete()
    
    return JsonResponse({
        'success': True,
        'message': 'Feedback excluído com sucesso!'
    })


@login_required
def feedback_detail(request, pk):
    """
    Visualizar detalhes do feedback com histórico completo de mensagens.
    Interface estilo chat para diálogo contínuo.
    ACCESS: ADMIN MASTER | GESTOR | COLABORADOR (apenas seus próprios feedbacks)
    """
    user = request.user
    company = request.current_company
    
    if not company and not user.is_superuser:
        return render(request, 'core/no_company.html')
    
    # Permissões de acesso
    if user.is_superuser:
        feedback = get_object_or_404(FeedbackTicket, pk=pk)
    elif request.is_gestor:
        feedback = get_object_or_404(FeedbackTicket, pk=pk, company=company)
    else:
        # Colaborador só vê seus próprios feedbacks
        feedback = get_object_or_404(FeedbackTicket, pk=pk, company=company, user=user)
    
    # Carrega histórico de mensagens (query otimizada)
    comments = feedback.comments.all().select_related('user', 'ticket').order_by('created_at')
    
    # Conta mensagens de forma segura
    total_comments = safe_int(comments.count(), 0)
    
    context = {
        'feedback': feedback,
        'comments': comments,
        'total_comments': total_comments,
    }
    
    return render(request, 'feedback/detail.html', context)


@login_required
@require_POST
def add_comment(request, pk):
    """
    Adicionar mensagem à thread de conversa do feedback.
    Atualiza status automaticamente baseado em quem está respondendo.
    """
    company = request.current_company
    
    if not company and not request.user.is_superuser:
        return JsonResponse({'error': 'Empresa não selecionada.'}, status=403)
    
    # Permissões de acesso
    if request.user.is_superuser:
        feedback = get_object_or_404(FeedbackTicket, pk=pk)
    elif request.is_gestor:
        feedback = get_object_or_404(FeedbackTicket, pk=pk, company=company)
    else:
        # Colaborador só pode comentar em seus próprios feedbacks
        feedback = get_object_or_404(FeedbackTicket, pk=pk, company=company, user=request.user)
    
    form = FeedbackCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.ticket = feedback
        comment.user = request.user
        comment.is_staff_reply = request.is_gestor
        comment.save()
        
        # Lógica de atualização de status
        # Se gestor respondeu: status vira "Respondido" ou "Em Diálogo" se já tinha mensagens
        # Se colaborador respondeu: status vira "Pendente" (aguardando resposta do gestor)
        if request.is_gestor:
            # Gestor respondeu
            if feedback.status == 'pending':
                feedback.status = 'in_progress'
            elif feedback.status not in ['resolved', 'closed']:
                # Se já estava em andamento ou em diálogo, continua em diálogo
                feedback.status = 'in_dialogue'
            feedback.save(update_fields=['status', 'updated_at'])
        else:
            # Colaborador respondeu - precisa de atenção do gestor
            if feedback.status not in ['pending', 'in_dialogue']:
                feedback.status = 'pending'
            else:
                feedback.status = 'in_dialogue'
            feedback.save(update_fields=['status', 'updated_at'])
        
        # Retorna dados do comentário
        return JsonResponse({
            'success': True,
            'message': 'Mensagem enviada!',
            'comment': {
                'id': comment.pk,
                'user_name': comment.user.get_full_name() or comment.user.email,
                'message': comment.message,
                'created_at': comment.created_at.strftime('%d/%m/%Y %H:%M'),
                'is_staff_reply': comment.is_staff_reply,
                'is_anonymous': feedback.is_anonymous and not request.is_gestor,
            },
            'new_status': feedback.status,
            'new_status_display': feedback.get_status_display(),
        })
    
    return JsonResponse({'error': 'Erro ao adicionar mensagem'}, status=400)


# ============================================================================
# Views para Gestores
# ============================================================================

@login_required
@gestor_required
def feedback_manage_list(request):
    """Lista de todos os feedbacks para gestores."""
    
    company = request.current_company
    
    if not company and not request.user.is_superuser:
        return render(request, 'core/no_company.html')
    
    status_filter = request.GET.get('status', '')
    sentiment_filter = request.GET.get('sentiment', '')
    category_filter = request.GET.get('category', '')
    
    if request.user.is_superuser:
        if company:
            feedbacks = FeedbackTicket.objects.filter(company=company)
            stats_base = FeedbackTicket.objects.filter(company=company)
        else:
            feedbacks = FeedbackTicket.objects.all()
            stats_base = FeedbackTicket.objects.all()
    else:
        feedbacks = FeedbackTicket.objects.filter(company=company)
        stats_base = FeedbackTicket.objects.filter(company=company)
    
    if status_filter:
        feedbacks = feedbacks.filter(status=status_filter)
    if sentiment_filter:
        feedbacks = feedbacks.filter(sentiment=sentiment_filter)
    if category_filter:
        feedbacks = feedbacks.filter(category=category_filter)
    
    # Query otimizada: select_related para evitar N+1 queries
    feedbacks = feedbacks.select_related('user', 'company', 'responded_by').prefetch_related('comments').order_by('-created_at')
    
    # Marca feedbacks pendentes há mais de 24h como urgentes
    urgent_threshold = timezone.now() - timedelta(hours=24)
    for feedback in feedbacks:
        feedback.is_urgent = (feedback.status == 'pending' and feedback.created_at < urgent_threshold)
    
    # Stats otimizado: usar agregações no banco
    from django.db.models import Count
    stats = {
        'total': safe_int(stats_base.count(), 0),
        'pending': safe_int(stats_base.filter(status='pending').count(), 0),
        'in_progress': safe_int(stats_base.filter(status='in_progress').count(), 0),
        'resolved': safe_int(stats_base.filter(status='resolved').count(), 0),
    }
    
    context = {
        'feedbacks': feedbacks,
        'stats': stats,
        'status_filter': status_filter,
        'sentiment_filter': sentiment_filter,
        'category_filter': category_filter,
    }
    
    return render(request, 'feedback/manage/list.html', context)


@login_required
@gestor_required
def feedback_respond(request, pk):
    """Responder feedback (gestor)."""
    
    if request.user.is_superuser:
        feedback = get_object_or_404(FeedbackTicket, pk=pk)
    else:
        feedback = get_object_or_404(
            FeedbackTicket,
            pk=pk,
            company=request.current_company
        )
    
    if request.method == 'POST':
        form = FeedbackResponseForm(request.POST)
        if form.is_valid():
            feedback.response = form.cleaned_data['response']
            feedback.status = form.cleaned_data['status']
            feedback.responded_by = request.user
            feedback.responded_at = timezone.now()
            feedback.save()
            
            messages.success(request, 'Resposta enviada!')
            return redirect('feedback:manage_list')
    else:
        form = FeedbackResponseForm(initial={
            'response': feedback.response,
            'status': feedback.status,
        })
    
    comments = feedback.comments.all().select_related('user')
    
    context = {
        'feedback': feedback,
        'form': form,
        'comments': comments,
    }
    
    return render(request, 'feedback/manage/respond.html', context)


@login_required
@gestor_required_ajax
@require_POST
def feedback_update_status(request, pk):
    """Atualizar status do feedback via AJAX."""
    
    if request.user.is_superuser:
        feedback = get_object_or_404(FeedbackTicket, pk=pk)
    else:
        feedback = get_object_or_404(
            FeedbackTicket,
            pk=pk,
            company=request.current_company
        )
    
    new_status = request.POST.get('status')
    if new_status in dict(FeedbackTicket.STATUS_CHOICES):
        feedback.status = new_status
        feedback.save(update_fields=['status', 'updated_at'])
        
        return JsonResponse({
            'success': True,
            'status': new_status,
            'status_display': feedback.get_status_display()
        })
    
    return JsonResponse({'error': 'Status inválido'}, status=400)

