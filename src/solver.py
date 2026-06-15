'''Решение разобранных задач: получение решения и ответа.'''

import json

from . import config
from .mistral_client import chat
from .schema import SOLUTION_SCHEMA

PROMPT = (
    'Ты эксперт по математике, решающий задачи ЕГЭ профильного '
    'уровня. Реши предложенную задачу и верни поля:\n'
    '- solution: пошаговое развёрнутое решение, все формулы '
    'оберни в $...$ (LaTeX).\n'
    '- answer: краткий финальный численный или текстовый ответ '
    'для быстрой проверки.'
)


def solve_task(task_num, condition):
    '''Возвращает словарь с ``solution`` и ``answer`` для задачи.'''
    user = f'Задача {task_num}.\n{condition}'
    messages = [
        {'role': 'system', 'content': PROMPT},
        {'role': 'user', 'content': user},
    ]
    content = chat(
        messages,
        model=config.SOLVER_MODEL,
        response_format=SOLUTION_SCHEMA,
    )
    return json.loads(content)
