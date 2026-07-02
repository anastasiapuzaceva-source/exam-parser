'''Транскрипция условий задач со страницы через VLM (гибрид с PaddleOCR).'''

import base64
import io
import json
import re

from PIL import Image

from . import config
from .llm_client import LLMError, chat
from .schema import PAGE_SCHEMA
from .textfmt import escape_latex_in_json, restore_control_latex

_TASK_NUM_RE = re.compile(r'\d+')

PROMPT = (
    'Ты парсер экзаменационных листов ЕГЭ по математике. '
    'На изображении страница с задачами. Извлеки КАЖДУЮ задачу '
    'в порядке нумерации. Ничего не придумывай и не решай — '
    'только переноси существующий текст.\n'
    'Для каждой задачи верни поля:\n'
    '- task_num: номер задачи строго как на листе (строка). Подпункты '
    'одной задачи (а, б, в) объединяй в одну задачу под общим номером.\n'
    '- condition: полный текст условия, размеченный HTML-тегами для '
    'рендеринга в MathJax. Абзацы оборачивай в <p>, переносы строк — '
    '<br>, выделения — <b>. Перечисления и наборы условий (например, '
    'в задачах про кредиты и вклады) оформляй маркированным списком '
    '<ul><li>...</li></ul>, по одному пункту на <li>. Markdown '
    'категорически запрещён (никаких **, ##, * или - для списков). '
    'Все математические переменные, формулы и величины оборачивай '
    'строго в одинарные $...$ (LaTeX), без $$...$$. Системы уравнений '
    'и неравенств записывай одной формулой '
    '$\\\\begin{cases}...\\\\end{cases}$ (она даёт фигурную скобку, '
    'как на листе), а не списком. Внутри JSON-строки '
    'каждый обратный слэш LaTeX-команды удваивай: пиши \\\\frac, '
    '\\\\vec, \\\\sqrt.\n'
    'Не включай в condition строку «Ответ: …», поля для ответа, '
    'колонтитулы, инструкции по заполнению бланков и справочные '
    'материалы. Русский текст оставляй русским текстом, не превращай '
    'слова в математические символы.'
)


def encode_image(path, max_side=1600):
    '''Возвращает data URI (base64 PNG), ужав картинку до max_side.'''
    image = Image.open(path)
    if max(image.size) > max_side:
        scale = max_side / max(image.size)
        new_size = (round(image.width * scale), round(image.height * scale))
        image = image.resize(new_size, Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    b64 = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f'data:image/png;base64,{b64}'


def _task_int(task_num):
    '''Первое целое из номера задачи или ``None``.'''
    match = _TASK_NUM_RE.search(str(task_num or ''))
    return int(match.group(0)) if match else None


def parse_conditions(image_path):
    '''Возвращает {номер задачи: HTML-условие} или {} при сбое VLM.'''
    if not config.VISION_MODEL:
        return {}
    messages = [{
        'role': 'user',
        'content': [
            {'type': 'text', 'text': PROMPT},
            {'type': 'image_url',
             'image_url': {'url': encode_image(image_path)}},
        ],
    }]
    try:
        content = chat(
            messages,
            model=config.VISION_MODEL,
            response_format=PAGE_SCHEMA,
            max_tokens=8192,
            base_url=config.VISION_BASE_URL,
            api_key=config.VISION_API_KEY,
        )
        tasks = json.loads(escape_latex_in_json(content))['tasks']
    except (LLMError, json.JSONDecodeError, TypeError, KeyError) as error:
        print(f'[vision] откат на PaddleOCR: {error}')
        return {}
    conditions = {}
    for task in tasks:
        num = _task_int(task.get('task_num'))
        condition = restore_control_latex((task.get('condition') or '').strip())
        if num is None or not condition:
            continue
        if num in conditions:
            conditions[num] = f'{conditions[num]}\n{condition}'
        else:
            conditions[num] = condition
    return conditions
