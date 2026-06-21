'''Общая нормализация HTML-текста для условий и решений.'''

import re

_BOLD_RE = re.compile(r'\*\*(.+?)\*\*')
_HEADING_RE = re.compile(r'(?m)^\s{0,3}#{1,6}\s*')
_NUMBER_RE = re.compile(r'-?\d+(?:[.,]\d+)?')


def clean_html(text):
    '''Подчищает разметку: HTML вместо Markdown и одинарные $...$.'''
    text = text or ''
    text = text.replace('$$', '$')
    text = _BOLD_RE.sub(r'<b>\1</b>', text)
    text = _HEADING_RE.sub('', text)
    return text.strip()


def clean_number(text):
    '''Оставляет в строке только число (запятая → точка), иначе исходник.'''
    text = (text or '').replace('$', '').strip()
    match = _NUMBER_RE.search(text)
    if match is None:
        return text
    return match.group(0).replace(',', '.')
