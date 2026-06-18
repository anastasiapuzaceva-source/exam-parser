'''Классификация задач по категориям из CSV-справочника.'''

import csv
import json
from pathlib import Path

from . import config
from .mistral_client import MistralError, chat

_NAME_COLUMNS = ('category', 'категория', 'тема', 'topic', 'name', 'название')
_DESC_COLUMNS = ('description', 'описание', 'desc', 'keywords', 'комментарий')


def _pick(fields, options):
    '''Находит подходящую колонку среди заголовков CSV.'''
    lower = {field.lower(): field for field in fields}
    for option in options:
        if option in lower:
            return lower[option]
    return None


def load_categories(csv_path=None):
    '''Читает CSV-справочник и возвращает список категорий с описанием.'''
    path = Path(csv_path or config.CATEGORIES_CSV)
    if not config.ENABLE_CLASSIFY or not path.exists():
        return []
    categories = []
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        name_key = _pick(fields, _NAME_COLUMNS)
        desc_key = _pick(fields, _DESC_COLUMNS)
        if name_key is None:
            return []
        for row in reader:
            name = (row.get(name_key) or '').strip()
            if not name:
                continue
            description = (row.get(desc_key) or '').strip() if desc_key else ''
            categories.append({'category': name, 'description': description})
    return categories


def _schema(names):
    '''Строит схему ответа с фиксированным списком категорий.'''
    return {
        'type': 'json_schema',
        'json_schema': {
            'name': 'task_category',
            'strict': True,
            'schema': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['category'],
                'properties': {
                    'category': {'type': 'string', 'enum': names},
                },
            },
        },
    }


def classify_task(task_num, condition, categories):
    '''Возвращает категорию задачи из справочника или пустую строку.'''
    if not categories:
        return ''
    names = [item['category'] for item in categories]
    listing = '\n'.join(
        f'- {item["category"]}'
        + (f': {item["description"]}' if item['description'] else '')
        for item in categories
    )
    prompt = (
        'Ты классификатор задач ЕГЭ по математике. Отнеси задачу строго '
        'к одной из категорий ниже и верни поле category с её названием '
        'без изменений.\n' + listing
    )
    messages = [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': f'Задача {task_num}.\n{condition}'},
    ]
    try:
        content = chat(
            messages,
            model=config.CLASSIFIER_MODEL,
            response_format=_schema(names),
        )
        category = json.loads(content).get('category', '')
    except (MistralError, json.JSONDecodeError, TypeError):
        return ''
    return category if category in names else ''
