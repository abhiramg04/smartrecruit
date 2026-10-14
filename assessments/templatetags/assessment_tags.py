from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        # Support string/int key lookup
        if key in dictionary:
            return dictionary.get(key)
        str_key = str(key)
        if str_key in dictionary:
            return dictionary.get(str_key)
    return None
