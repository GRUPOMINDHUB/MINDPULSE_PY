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
from apps.core.reports import get_report_data, get_company_report_data


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
    report_data = get_company_report_data(company, start_date, end_date)
    
    # Renderizar template HTML CORRETO para coletivo
    template = get_template('core/reports/pdf_collective.html')
    html = template.render({'report_data': report_data, 'request': request})
    
    # Gerar PDF
    result = BytesIO()
    
    # Configurar pisaDocument com encoding correto
    pdf = pisa.pisaDocument(
        BytesIO(html.encode('UTF-8')),
        result,
        encoding='UTF-8'
    )
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        # Nome do arquivo formatado
        filename = f'relatorio_coletivo_{company.slug}_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    else:
        messages.error(request, f'Erro ao gerar PDF coletivo: {pdf.err}')
        return redirect('core:report_management')


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
            if user:
                # Relatório Individual
                return _generate_pdf(request, company, start_date, end_date, user)
            else:
                # Relatório Coletivo
                return _generate_collective_pdf(request, company, start_date, end_date)
        else:
            # Visualizar na tela
            if user:
                # Relatório Individual
                report_data = get_report_data(company, start_date, end_date, user)
                template_name = 'core/reports/view.html'
            else:
                # Relatório Coletivo
                report_data = get_company_report_data(company, start_date, end_date)
                template_name = 'core/reports/view_collective.html'
            
            return render(request, template_name, {
                'report_data': report_data,
                'users': users,
                'selected_user_id': user_id if user else '',
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'selected_period': period,
                'company': company,  # Para navegação
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
    Segurança multi-tenant: garante que apenas colaboradores da empresa possam ter relatórios gerados.
    """
    try:
        from xhtml2pdf import pisa
    except ImportError:
        messages.error(request, 'Biblioteca xhtml2pdf não está instalada.')
        return redirect('core:report_management')
    
    # Segurança multi-tenant: verificar se user pertence à company
    if user:
        if not UserCompany.objects.filter(
            user=user,
            company=company,
            is_active=True
        ).exists():
            messages.error(request, 'Usuário não pertence à empresa selecionada.')
            return redirect('core:report_management')
        
        # Extrair dados do relatório individual
        report_data = get_report_data(company, start_date, end_date, user)
    else:
        # Relatório coletivo da empresa
        report_data = get_company_report_data(company, start_date, end_date)
    
    # Renderizar template HTML
    template = get_template('core/reports/pdf_template.html')
    html = template.render({'report_data': report_data, 'request': request})
    
    # Gerar PDF
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        
        # Nome do arquivo: relatorio_[colaborador]_[periodo].pdf
        filename = f'relatorio_{company.slug}'
        if user:
            # Remove caracteres especiais do nome
            user_name = user.get_full_name().replace(" ", "_").replace("/", "-").replace("\\", "-")
            filename += f'_{user_name}'
        filename += f'_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.pdf'
        
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    else:
        messages.error(request, 'Erro ao gerar PDF. Tente novamente.')
        return redirect('core:report_management')

