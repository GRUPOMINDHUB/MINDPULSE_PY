"""
Utilitários Core - Funções auxiliares e helpers
"""
from typing import Optional, Union, Any
from datetime import date, datetime
from django.utils import timezone
from django.db.models import QuerySet


class PeriodKeyHelper:
    """
    Helper para geração e manipulação de chaves de período.
    
    Usado para identificar períodos únicos de checklists baseado em frequência
    (diário, semanal, mensal) e data de referência.
    """
    
    @classmethod
    def get_current_period_key(cls, frequency: str, date_ref: Optional[date] = None) -> str:
        """
        Gera chave de período atual baseado na frequência.
        
        Args:
            frequency: Frequência do checklist ('daily', 'weekly', 'monthly')
            date_ref: Data de referência (default: hoje)
        
        Returns:
            String no formato 'YYYY-MM-DD' representando o início do período
        """
        if date_ref is None:
            date_ref = date.today()
        
        if frequency == 'daily':
            return date_ref.strftime('%Y-%m-%d')
        elif frequency == 'weekly':
            # Segunda-feira da semana
            days_until_monday = date_ref.weekday()
            monday = date_ref - timezone.timedelta(days=days_until_monday)
            return monday.strftime('%Y-%m-%d')
        elif frequency == 'monthly':
            # Primeiro dia do mês
            return date_ref.replace(day=1).strftime('%Y-%m-%d')
        else:
            return date_ref.strftime('%Y-%m-%d')
    
    @classmethod
    def get_previous_period_key(cls, frequency: str, date_ref: Optional[date] = None) -> str:
        """
        Gera chave do período anterior.
        
        Args:
            frequency: Frequência do checklist
            date_ref: Data de referência (default: hoje)
        
        Returns:
            String no formato 'YYYY-MM-DD' do período anterior
        """
        if date_ref is None:
            date_ref = date.today()
        
        if frequency == 'daily':
            previous_date = date_ref - timezone.timedelta(days=1)
        elif frequency == 'weekly':
            days_until_monday = date_ref.weekday()
            monday = date_ref - timezone.timedelta(days=days_until_monday)
            previous_date = monday - timezone.timedelta(days=7)
        elif frequency == 'monthly':
            # Primeiro dia do mês anterior
            first_day_current = date_ref.replace(day=1)
            previous_date = (first_day_current - timezone.timedelta(days=1)).replace(day=1)
        else:
            previous_date = date_ref - timezone.timedelta(days=1)
        
        return previous_date.strftime('%Y-%m-%d')


def safe_int(value: Optional[Any], default: int = 0) -> int:
    """
    Converte valor para int de forma segura, tratando None e tipos inválidos.
    
    Args:
        value: Valor a ser convertido
        default: Valor padrão se conversão falhar (default: 0)
    
    Returns:
        int: Valor convertido ou default
    """
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Optional[Any], default: float = 0.0) -> float:
    """
    Converte valor para float de forma segura, tratando None e tipos inválidos.
    
    Args:
        value: Valor a ser convertido
        default: Valor padrão se conversão falhar (default: 0.0)
    
    Returns:
        float: Valor convertido ou default
    """
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_str(value: Optional[Any], default: str = '---') -> str:
    """
    Converte valor para string de forma segura, tratando None.
    
    Args:
        value: Valor a ser convertido
        default: Valor padrão se None (default: '---')
    
    Returns:
        str: Valor convertido ou default
    """
    if value is None:
        return default
    try:
        return str(value)
    except (TypeError, ValueError):
        return default


def safe_date_format(date_obj: Optional[date], format_str: str = '%d/%m/%Y', default: str = '---') -> str:
    """
    Formata data de forma segura, tratando None.
    
    Args:
        date_obj: Objeto date a ser formatado
        format_str: String de formatação (default: '%d/%m/%Y')
        default: Valor padrão se None (default: '---')
    
    Returns:
        str: Data formatada ou default
    """
    if date_obj is None:
        return default
    try:
        return date_obj.strftime(format_str)
    except (AttributeError, ValueError):
        return default


def safe_division(numerator: Union[int, float], denominator: Union[int, float], default: float = 0.0) -> float:
    """
    Realiza divisão de forma segura, evitando divisão por zero.
    
    Args:
        numerator: Numerador
        denominator: Denominador
        default: Valor padrão se divisão inválida (default: 0.0)
    
    Returns:
        float: Resultado da divisão ou default
    """
    try:
        numerator = safe_float(numerator, 0.0)
        denominator = safe_float(denominator, 0.0)
        
        if denominator == 0:
            return default
        
        return float(numerator / denominator)
    except (TypeError, ZeroDivisionError):
        return default


def get_company_filter(request: Any, queryset: QuerySet, allow_all_for_admin: bool = True) -> QuerySet:
    """
    Aplica filtro de empresa ao queryset baseado no usuário logado.
    
    Função utilitária para garantir segurança multi-tenant, aplicando
    filtro automático de empresa em todas as consultas.
    
    Args:
        request: HttpRequest com atributo current_company
        queryset: QuerySet a ser filtrado
        allow_all_for_admin: Se True, Admin Master vê todos os registros
    
    Returns:
        QuerySet filtrado pela empresa do usuário ou vazio se sem empresa
    """
    if allow_all_for_admin and request.user.is_superuser:
        return queryset
    
    company = getattr(request, 'current_company', None)
    if company:
        return queryset.filter(company=company)
    
    return queryset.none()
