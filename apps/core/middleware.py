"""
Middleware para injetar a empresa atual no request.
"""

from django.shortcuts import redirect
from django.urls import reverse


class CompanyMiddleware:
    """
    Middleware que adiciona a empresa atual ao request.
    Baseado no UserCompany do usuário logado.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Inicializa company como None
        request.current_company = None
        request.user_role = None
        
        # Se usuário está autenticado, busca a empresa ativa
        if request.user.is_authenticated:
            # Admin Master: usa sessão para seleção global de empresa
            if request.user.is_superuser:
                company_id = request.session.get('current_company_id')
                if company_id:
                    try:
                        from .models import Company
                        request.current_company = Company.objects.get(pk=company_id, is_active=True)
                    except Company.DoesNotExist:
                        request.current_company = None
                # Se company_id for None ou vazio, request.current_company permanece None (visão global)
                request.is_gestor = True  # Admin Master sempre é gestor
                request.is_admin_master = True
            else:
                # Usuários normais: busca o vínculo ativo com empresa
                user_company = request.user.user_companies.filter(
                    is_active=True
                ).select_related('company', 'role').first()
                
                if user_company:
                    request.current_company = user_company.company
                    request.user_role = user_company.role
                    request.is_gestor = user_company.role and user_company.role.level in ['admin_master', 'gestor']
                    request.is_admin_master = user_company.role and user_company.role.level == 'admin_master'
                else:
                    request.is_gestor = False
                    request.is_admin_master = False
        
        response = self.get_response(request)
        return response

