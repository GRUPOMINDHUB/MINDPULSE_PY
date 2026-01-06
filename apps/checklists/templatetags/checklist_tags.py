"""
Template tags customizados para checklists.
"""
from django import template

register = template.Library()


@register.filter
def has_attr(obj, attr_name):
    """
    Verifica se um objeto tem um atributo específico.
    Uso: {% if checklist|has_attr:"assigned_users" %}
    """
    try:
        return hasattr(obj, attr_name)
    except Exception:
        return False


@register.simple_tag(takes_context=True)
def try_get_attr(context, obj, attr_name, default=''):
    """
    Tenta acessar um atributo de forma segura.
    Uso: {% try_get_attr checklist "assigned_users" as assigned_users %}
    """
    try:
        return getattr(obj, attr_name, default)
    except Exception:
        return default

