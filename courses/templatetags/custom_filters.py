from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(mapping, key):
    """Return mapping[key] or None. Convert key to str for dicts with string keys."""
    try:
        # normalize key to string when dict uses string keys
        return mapping.get(str(key)) if hasattr(mapping, 'get') else None
    except Exception:
        return None

@register.filter(name='add_class')
def add_class(field, css_class):
    """Add CSS class to form field."""
    if hasattr(field, 'field'):
        # It's a bound field
        return field.as_widget(attrs={"class": css_class})
    else:
        # It's an unbound field
        return field.as_widget(attrs={"class": css_class})