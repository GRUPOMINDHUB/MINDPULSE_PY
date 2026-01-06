"""
Utilitários e helpers centralizados para o Mindpulse.
"""

from django.utils import timezone
from datetime import timedelta


class PeriodKeyHelper:
    """
    Helper centralizado para geração de period_key.
    Usado para checklists com diferentes frequências.
    
    Formatos:
    - Daily: YYYY-MM-DD (ex: 2024-01-15)
    - Weekly: YYYY-Www (ex: 2024-W03)
    - Biweekly: YYYY-Bww (ex: 2024-B02)
    - Monthly: YYYY-MM (ex: 2024-01)
    """
    
    FREQUENCY_DAILY = 'daily'
    FREQUENCY_WEEKLY = 'weekly'
    FREQUENCY_BIWEEKLY = 'biweekly'
    FREQUENCY_MONTHLY = 'monthly'
    
    @classmethod
    def get_period_key(cls, frequency, date=None):
        """
        Gera a period_key para uma data e frequência específicas.
        
        Args:
            frequency: Tipo de frequência (daily, weekly, biweekly, monthly)
            date: Data de referência (default: hoje)
        
        Returns:
            String com a period_key formatada
        """
        if date is None:
            date = timezone.now().date()
        
        if frequency == cls.FREQUENCY_DAILY:
            return date.strftime('%Y-%m-%d')
        
        elif frequency == cls.FREQUENCY_WEEKLY:
            return date.strftime('%Y-W%W')
        
        elif frequency == cls.FREQUENCY_BIWEEKLY:
            week_num = date.isocalendar()[1]
            biweek = (week_num - 1) // 2 + 1
            return f'{date.year}-B{biweek:02d}'
        
        elif frequency == cls.FREQUENCY_MONTHLY:
            return date.strftime('%Y-%m')
        
        # Fallback para diário
        return date.strftime('%Y-%m-%d')
    
    @classmethod
    def get_period_display(cls, frequency, date=None):
        """
        Retorna descrição legível do período.
        
        Args:
            frequency: Tipo de frequência
            date: Data de referência (default: hoje)
        
        Returns:
            String com descrição do período
        """
        if date is None:
            date = timezone.now().date()
        
        if frequency == cls.FREQUENCY_DAILY:
            return date.strftime('%d/%m/%Y')
        
        elif frequency == cls.FREQUENCY_WEEKLY:
            start = date - timedelta(days=date.weekday())
            end = start + timedelta(days=6)
            return f'{start.strftime("%d/%m")} - {end.strftime("%d/%m")}'
        
        elif frequency == cls.FREQUENCY_BIWEEKLY:
            week_num = date.isocalendar()[1]
            if week_num % 2 == 1:
                start = date - timedelta(days=date.weekday())
            else:
                start = date - timedelta(days=date.weekday() + 7)
            end = start + timedelta(days=13)
            return f'{start.strftime("%d/%m")} - {end.strftime("%d/%m")}'
        
        elif frequency == cls.FREQUENCY_MONTHLY:
            return date.strftime('%B/%Y')
        
        return date.strftime('%d/%m/%Y')
    
    @classmethod
    def get_previous_period_key(cls, frequency, date=None):
        """
        Gera a period_key para o período anterior.
        
        Args:
            frequency: Tipo de frequência (daily, weekly, biweekly, monthly)
            date: Data de referência (default: hoje)
        
        Returns:
            String com a period_key do período anterior
        """
        if date is None:
            date = timezone.now().date()
        
        if frequency == cls.FREQUENCY_DAILY:
            previous_date = date - timedelta(days=1)
            return previous_date.strftime('%Y-%m-%d')
        
        elif frequency == cls.FREQUENCY_WEEKLY:
            previous_date = date - timedelta(weeks=1)
            return previous_date.strftime('%Y-W%W')
        
        elif frequency == cls.FREQUENCY_BIWEEKLY:
            previous_date = date - timedelta(weeks=2)
            week_num = previous_date.isocalendar()[1]
            biweek = (week_num - 1) // 2 + 1
            return f'{previous_date.year}-B{biweek:02d}'
        
        elif frequency == cls.FREQUENCY_MONTHLY:
            if date.month == 1:
                previous_date = date.replace(year=date.year - 1, month=12, day=1)
            else:
                previous_date = date.replace(month=date.month - 1, day=1)
            return previous_date.strftime('%Y-%m')
        
        previous_date = date - timedelta(days=1)
        return previous_date.strftime('%Y-%m-%d')


def get_company_filter(request, queryset, allow_all_for_admin=True):
    """
    Aplica filtro de empresa ao queryset baseado no usuário.
    
    Args:
        request: HttpRequest
        queryset: QuerySet a ser filtrado
        allow_all_for_admin: Se True, Admin Master vê todos os registros
    
    Returns:
        QuerySet filtrado
    """
    if allow_all_for_admin and request.user.is_superuser:
        return queryset
    
    company = getattr(request, 'current_company', None)
    if company:
        return queryset.filter(company=company)
    
    return queryset.none()

