"""
Decorators para controle de acesso e permissões.
Centraliza a lógica de verificação de permissões para evitar repetição.
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse


def gestor_required(view_func):
    """
    Decorator que verifica se o usuário é Gestor ou Admin Master.
    Redireciona para o dashboard se não tiver permissão.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not (request.user.is_superuser or getattr(request, 'is_gestor', False)):
            messages.error(request, 'Acesso não autorizado.')
            return redirect('core:dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def gestor_required_ajax(view_func):
    """
    Decorator para views AJAX que requerem permissão de Gestor.
    Retorna JSON com erro se não tiver permissão.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Não autenticado'}, status=401)
        
        if not (request.user.is_superuser or getattr(request, 'is_gestor', False)):
            return JsonResponse({'error': 'Não autorizado'}, status=403)
        
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_master_required(view_func):
    """
    Decorator que verifica se o usuário é Admin Master (superuser).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not request.user.is_superuser:
            messages.error(request, 'Acesso restrito ao Admin Master.')
            return redirect('core:dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def company_required(view_func):
    """
    Decorator que verifica se o usuário está vinculado a uma empresa.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not getattr(request, 'current_company', None) and not request.user.is_superuser:
            return redirect('core:no_company')
        
        return view_func(request, *args, **kwargs)
    return wrapper

