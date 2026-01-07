"""
Middleware para injetar a empresa atual no request e controle de assinaturas.
"""

from typing import Optional
from django.shortcuts import redirect
from django.urls import reverse
from django.core.cache import cache
from django.http import HttpResponse


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


class SubscriptionGateMiddleware:
    """
    Middleware que bloqueia acesso de empresas com assinatura suspensa.
    
    Funcionalidades:
    - Verifica status da assinatura antes de permitir acesso
    - Redireciona para página de suspensão se necessário
    - Usa cache para otimizar performance (evita queries repetitivas)
    - Lista branca de URLs que não devem ser bloqueadas
    """
    
    # URLs que nunca devem ser bloqueadas (lista branca)
    ALLOWED_PATHS = [
        '/accounts/logout/',
        '/admin/',
        '/assinatura/suspensa/',
        '/assinatura/pagamento/',
        '/suporte/',
        '/api/health/',  # Endpoint de health check
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Verificar se precisa bloquear acesso
        if self._should_check_subscription(request):
            if self._is_subscription_suspended(request):
                # Bloquear acesso - redirecionar para página de suspensão
                return redirect('core:subscription_suspended')
        
        response = self.get_response(request)
        return response
    
    def _should_check_subscription(self, request) -> bool:
        """
        Determina se deve verificar o status da assinatura.
        
        Não verifica se:
        - Usuário não está autenticado
        - É superuser (admin master sempre tem acesso)
        - URL está na lista branca
        
        Args:
            request: HttpRequest
        
        Returns:
            bool: True se deve verificar assinatura
        """
        # Não verifica se não está autenticado
        if not request.user.is_authenticated:
            return False
        
        # Superuser sempre tem acesso
        if request.user.is_superuser:
            return False
        
        # Verifica se o path está na lista branca
        path = request.path
        for allowed_path in self.ALLOWED_PATHS:
            if path.startswith(allowed_path):
                return False
        
        # Só verifica se tem empresa vinculada
        return hasattr(request, 'current_company') and request.current_company is not None
    
    def _is_subscription_suspended(self, request) -> bool:
        """
        Verifica se a assinatura da empresa está suspensa.
        
        Usa cache para otimizar performance (15 minutos de TTL).
        Evita consultas repetitivas ao banco em cada request.
        
        Args:
            request: HttpRequest com current_company
        
        Returns:
            bool: True se suspensa e deve bloquear acesso
        """
        company = request.current_company
        if not company:
            return False
        
        # Cache key única por empresa
        cache_key = f'company_subscription_status_{company.id}'
        
        # Tentar obter do cache primeiro
        cached_status = cache.get(cache_key)
        if cached_status is not None:
            return cached_status
        
        # Se não está em cache, verificar no banco
        # Verifica se deve ser suspensa (lógica do modelo)
        is_suspended = company.should_be_suspended() or company.subscription_status == 'suspended'
        
        # Salvar no cache por 15 minutos (900 segundos)
        # Isso reduz drasticamente queries ao banco
        cache.set(cache_key, is_suspended, 900)
        
        return is_suspended

