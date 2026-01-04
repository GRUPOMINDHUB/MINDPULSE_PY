"""
Views para feedback.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import FeedbackTicket, FeedbackComment
from .forms import FeedbackForm, FeedbackResponseForm, FeedbackCommentForm
from apps.core.models import Company
from apps.core.decorators import gestor_required, gestor_required_ajax


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
        ).order_by('-created_at')
    
    context = {
        'feedbacks': feedbacks,
    }
    
    return render(request, 'feedback/list.html', context)


@login_required
def feedback_create(request):
    """
    Criar novo feedback.
    ACCESS: ADMIN MASTER | GESTOR | COLABORADOR
    - Todos os usuários podem criar feedback
    """
    user = request.user
    
    # Admin Master pode criar feedback para qualquer empresa
    if user.is_superuser:
        companies = Company.objects.filter(is_active=True)
        company = None  # Será selecionada no form
    else:
        company = request.current_company
        companies = None
        
        if not company:
            return render(request, 'core/no_company.html')
    
    if request.method == 'POST':
        form = FeedbackForm(request.POST, request.FILES)
        if form.is_valid():
            feedback = form.save(commit=False)
            
            # Admin Master seleciona a empresa
            if user.is_superuser:
                company_id = request.POST.get('company')
                if company_id:
                    feedback.company = Company.objects.get(id=company_id)
                else:
                    messages.error(request, 'Selecione uma empresa.')
                    return render(request, 'feedback/form.html', {'form': form, 'companies': companies})
            else:
                feedback.company = company
            
            feedback.user = user
            feedback.save()
            
            messages.success(request, 'Feedback enviado com sucesso!')
            return redirect('feedback:list')
    else:
        form = FeedbackForm()
    
    return render(request, 'feedback/form.html', {
        'form': form,
        'companies': companies,
    })


@login_required
def feedback_detail(request, pk):
    """Detalhes do feedback."""
    company = request.current_company
    
    # Colaborador vê apenas seus feedbacks, gestor vê todos da empresa
    if request.is_gestor:
        feedback = get_object_or_404(FeedbackTicket, pk=pk, company=company)
    else:
        feedback = get_object_or_404(FeedbackTicket, pk=pk, company=company, user=request.user)
    
    comments = feedback.comments.all().select_related('user')
    
    # Form para comentário
    comment_form = FeedbackCommentForm()
    
    context = {
        'feedback': feedback,
        'comments': comments,
        'comment_form': comment_form,
    }
    
    return render(request, 'feedback/detail.html', context)


@login_required
@require_POST
def add_comment(request, pk):
    """Adicionar comentário ao feedback."""
    company = request.current_company
    
    if request.is_gestor:
        feedback = get_object_or_404(FeedbackTicket, pk=pk, company=company)
    else:
        feedback = get_object_or_404(FeedbackTicket, pk=pk, company=company, user=request.user)
    
    form = FeedbackCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.ticket = feedback
        comment.user = request.user
        comment.is_staff_reply = request.is_gestor
        comment.save()
        
        # Se gestor comentou, atualiza status para em andamento
        if request.is_gestor and feedback.status == 'pending':
            feedback.status = 'in_progress'
            feedback.save(update_fields=['status'])
        
        return JsonResponse({
            'success': True,
            'message': 'Comentário adicionado!',
            'comment': {
                'user': comment.user.get_full_name(),
                'message': comment.message,
                'created_at': comment.created_at.strftime('%d/%m/%Y %H:%M'),
                'is_staff_reply': comment.is_staff_reply,
            }
        })
    
    return JsonResponse({'error': 'Erro ao adicionar comentário'}, status=400)


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
    
    feedbacks = feedbacks.select_related('user', 'company').order_by('-created_at')
    
    stats = {
        'total': stats_base.count(),
        'pending': stats_base.filter(status='pending').count(),
        'in_progress': stats_base.filter(status='in_progress').count(),
        'resolved': stats_base.filter(status='resolved').count(),
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

