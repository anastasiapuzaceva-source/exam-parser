'''Решение разобранных задач: получение решения и ответа.'''

import json

from . import config
from .mistral_client import MistralError, chat
from .schema import SOLUTION_SCHEMA
from .textfmt import clean_html, clean_number

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
        'solution': clean_html(data.get('solution', '')),
        'answer': clean_number(data.get('answer', '')),
    }
