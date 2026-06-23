'''Решение разобранных задач: Mistral + сверка ответа с эталоном Ларина.'''

import json
import re

from . import config
from .llm_client import LLMError, chat
from .schema import SOLUTION_SCHEMA
from .textfmt import clean_html, clean_number

_NUM_RE = re.compile(r'^-?\d+(?:[.,]\d+)?$')

PROMPT = (
    'Ты эксперт по математике, решающий задачи ЕГЭ профильного уровня. '
    'Реши задачу и верни поля solution и answer.\n'
    '\n'
    'Поле solution — пошаговое развёрнутое решение, размеченное строго '
    'HTML-тегами. Категорически запрещено использовать Markdown: никаких '
    '**, ##, ###, а также списков через * или -. Используй только теги: '
    'абзацы — <p>, переносы строк — <br>, выделения — <b>, списки — <ul> '
    'и <li>.\n'
    '\n'
    'Все формулы и переменные оборачивай строго в одинарные знаки доллара '
    '$...$ (LaTeX). Двойные $$...$$ запрещены.\n'
    '\n'
    'Поле answer — только итоговый ответ: число (целое или конечная '
    'десятичная дробь) без слов и единиц измерения.'
)

_FALLBACK = '<p>Не удалось получить решение от модели.</p>'

_SOL_FIELD_RE = re.compile(r'"solution"\s*:\s*"((?:[^"\\]|\\.)*)', re.S)
_ANS_FIELD_RE = re.compile(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*?)"', re.S)


def _json_unescape(fragment):
    '''Снимает JSON-экранирование с фрагмента строки (терпит обрыв в конце).'''
    fragment = fragment.rstrip('\\')
    try:
        return json.loads(f'"{fragment}"')
    except json.JSONDecodeError:
        return (
            fragment.replace('\\"', '"').replace('\\n', '\n')
            .replace('\\t', '\t').replace('\\/', '/').replace('\\\\', '\\')
        )


def _parse_solution(content):
    '''Парсит ответ в (solution, answer), спасая оборванный по лимиту JSON.'''
    try:
        data = json.loads(content)
        return data.get('solution', ''), data.get('answer', '')
    except (json.JSONDecodeError, TypeError):
        pass
    sol_match = _SOL_FIELD_RE.search(content or '')
    ans_match = _ANS_FIELD_RE.search(content or '')
    solution = _json_unescape(sol_match.group(1)) if sol_match else ''
    answer = _json_unescape(ans_match.group(1)) if ans_match else ''
    if not solution.strip():
        raise json.JSONDecodeError('решение не спасти', content or '', 0)
    return solution, answer


def _hint_message(answer):
    '''Подсказка решателю: построить решение к известному ответу.'''
    return (
        f'\n\nИзвестен правильный ответ: {answer}. Построй строгое пошаговое '
        'решение, приводящее именно к этому ответу.'
    )


def _solve_once(task_num, condition, hint=None):
    '''Один вызов решателя → (solution_html, model_answer).'''
    user = f'Задача {task_num}.\n{condition}'
    if hint:
        user += _hint_message(hint)
    messages = [
        {'role': 'system', 'content': PROMPT},
        {'role': 'user', 'content': user},
    ]
    content = chat(
        messages,
        model=config.SOLVER_MODEL,
        response_format=SOLUTION_SCHEMA,
        temperature=config.SOLVER_TEMPERATURE,
        max_tokens=config.SOLVER_MAX_TOKENS,
    )
    solution, answer = _parse_solution(content)
    return clean_html(solution), clean_number(answer)


def _answers_match(left, right):
    '''Сравнивает два ответа как числа (иначе как строки).'''
    left = (left or '').strip()
    right = (right or '').strip()
    if not left or not right:
        return False
    try:
        return abs(float(left.replace(',', '.'))
                   - float(right.replace(',', '.'))) < 1e-9
    except ValueError:
        return left == right


def solve_task(task_num, condition, answer_hint=None):
    '''Решает задачу, сверяя ответ с эталоном Ларина и перерешивая при сбое.'''
    hint_str = (answer_hint or '').strip()
    numeric_ref = bool(_NUM_RE.match(hint_str))
    reference = clean_number(hint_str) if numeric_ref else ''

    if not numeric_ref:
        try:
            solution, model_answer = _solve_once(
                task_num, condition, hint=answer_hint)
        except (LLMError, json.JSONDecodeError, TypeError):
            return {'solution': _FALLBACK, 'answer': answer_hint or ''}
        return {'solution': solution, 'answer': answer_hint or model_answer}

    last_solution = None
    attempts = max(1, config.SOLVER_ATTEMPTS)
    for attempt in range(attempts):
        hint = reference if attempt > 0 else None
        try:
            solution, model_answer = _solve_once(
                task_num, condition, hint=hint)
        except (LLMError, json.JSONDecodeError, TypeError):
            return {
                'solution': last_solution or _FALLBACK,
                'answer': reference,
            }
        last_solution = solution
        if _answers_match(model_answer, reference):
            return {'solution': solution, 'answer': reference}
    return {'solution': last_solution or _FALLBACK, 'answer': reference}
