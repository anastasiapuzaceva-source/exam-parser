'''Классификация задач по категориям из CSV-справочника.'''

import csv
from pathlib import Path

from . import config
from .llm_client import LLMError, chat

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
        'к одной из категорий ниже и верни ТОЛЬКО название категории без '
        'изменений, без пояснений и кавычек.\n' + listing
    )
    messages = [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': f'Задача {task_num}.\n{condition}'},
    ]
    try:
        content = chat(
            messages,
            model=config.CLASSIFIER_MODEL,
            max_tokens=64,
        )
    except (LLMError, TypeError):
        return ''
    text = (content or '').strip().strip('"\'')
    if text in names:
        return text
    for name in names:
        if name in text:
            return name
    return ''
