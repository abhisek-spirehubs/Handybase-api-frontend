# frontend/apps/core/templatetags/ui_tags.py
from django import template

register = template.Library()

@register.filter(name='clean_feature')
def clean_feature(value):
    """
    Replaces underscores with spaces and capitalizes the string.
    Usage: {{ feature_key|clean_feature }}
    """
    if not value:
        return ""
    # Replace underscores and capitalize each word
    return str(value).replace('_', ' ').title()