"""
Context processors para disponibilizar dados globais nos templates.
"""

from django.conf import settings


def company_context(request):
    """
    Adiciona informações da empresa e usuário ao contexto.
    Para Admin Master, inclui lista de empresas e empresa selecionada na sessão.
    """
    context = {
        'current_company': getattr(request, 'current_company', None),
        'user_role': getattr(request, 'user_role', None),
        'is_gestor': getattr(request, 'is_gestor', False),
        'is_admin_master': getattr(request, 'is_admin_master', False),
        'brand_color': settings.MINDPULSE_SETTINGS.get('BRAND_COLOR', '#F83531'),
        'bg_color': settings.MINDPULSE_SETTINGS.get('BACKGROUND_COLOR', '#1A1A1A'),
        'text_color': settings.MINDPULSE_SETTINGS.get('TEXT_COLOR', '#FFFFFF'),
    }
    
    # Para Admin Master, adiciona lista de empresas e empresa selecionada
    if request.user.is_authenticated and request.user.is_superuser:
        from .models import Company
        context['companies'] = Company.objects.filter(is_active=True).order_by('name')
        # Garante que selected_company_id seja int ou None
        company_id = request.session.get('current_company_id')
        context['selected_company_id'] = int(company_id) if company_id else None
    
    return context

