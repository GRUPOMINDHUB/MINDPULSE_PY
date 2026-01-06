"""
Views de Relatórios - Geração de relatórios consolidados e exportação PDF.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, Http404
from django.utils import timezone
from datetime import datetime, timedelta
from io import BytesIO
from django.template.loader import get_template

from apps.accounts.models import User, UserCompany
from apps.core.decorators import gestor_required
from apps.core.reports import get_report_data


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
        from django.shortcuts import render as render_view
        return render_view(request, 'core/no_company.html')
    
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
    
    # Processar formulário
    if request.method == 'GET':
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
            return _generate_pdf(request, company, start_date, end_date, user)
        else:
            # Visualizar na tela
            report_data = get_report_data(company, start_date, end_date, user)
            return render(request, 'core/reports/view.html', {
                'report_data': report_data,
                'users': users,
                'selected_user_id': user_id if user else '',
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'selected_period': period,
            })
    
    # GET sem parâmetros: mostrar formulário
    return render(request, 'core/reports/management.html', {
        'users': users,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
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
    
    # Extrair dados do relatório
    report_data = get_report_data(company, start_date, end_date, user)
    
    # Renderizar template HTML
    template = get_template('core/reports/pdf_template.html')
    html = template.render({'report_data': report_data, 'request': request})
    
    # Gerar PDF
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    
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

