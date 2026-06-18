'''Решение разобранных задач: получение решения и ответа.'''

import json
import re

from . import config
from .mistral_client import MistralError, chat
from .schema import SOLUTION_SCHEMA

_BOLD_RE = re.compile(r'\*\*(.+?)\*\*')
_HEADING_RE = re.compile(r'(?m)^\s{0,3}#{1,6}\s*')
_NUMBER_RE = re.compile(r'-?\d+(?:[.,]\d+)?')

PROMPT = (
    'Ты эксперт по математике, решающий задачи ЕГЭ профильного '
    'уровня. Реши предложенную задачу и верни поля solution и answer.\n'
    '\n'
    'Поле solution — пошаговое развёрнутое решение, размеченное строго '
    'HTML-тегами. Категорически запрещено использовать Markdown: никаких '
    '**, ##, ###, а также списков через * или -. Используй только теги: '
    'абзацы оборачивай в <p>, переносы строк — <br>, выделения — <b>, '
    'списки — <ul> и <li>.\n'
    '\n'
    'Все формулы и переменные оборачивай строго в одинарные знаки доллара '
    '$...$ (LaTeX). Использовать двойные знаки $$...$$ категорически '
    'запрещено.\n'
    '\n'
    'Поле answer — только число (целое или конечная десятичная дробь) без '
    'каких-либо слов и единиц измерения (без «рублей», «градусов», '
    '«кв. ед» и тому подобного).'
)


def _clean_solution(text):
    '''Подчищает решение: HTML вместо Markdown и одинарные $...$.'''
    text = text or ''
    text = text.replace('$$', '$')
    text = _BOLD_RE.sub(r'<b>\1</b>', text)
    text = _HEADING_RE.sub('', text)
    return text.strip()


def _clean_answer(text):
    '''Оставляет в ответе только число без слов и единиц.'''
    text = (text or '').replace('$', '').strip()
    match = _NUMBER_RE.search(text)
    if match is None:
        return text
    return match.group(0).replace(',', '.')


def solve_task(task_num, condition):
    '''Возвращает словарь с ``solution`` и ``answer`` для задачи.'''
    user = f'Задача {task_num}.\n{condition}'
    messages = [
        {'role': 'system', 'content': PROMPT},
        {'role': 'user', 'content': user},
    ]
    try:
        content = chat(
            messages,
            model=config.SOLVER_MODEL,
            response_format=SOLUTION_SCHEMA,
        )
        data = json.loads(content)
    except (MistralError, json.JSONDecodeError, TypeError):
        return {
            'solution': '<p>Не удалось получить решение от модели.</p>',
            'answer': '',
        }
    return {
        'solution': _clean_solution(data.get('solution', '')),
        'answer': _clean_answer(data.get('answer', '')),
    }
