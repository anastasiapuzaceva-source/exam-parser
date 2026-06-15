'''Разбор изображения страницы на структурированные задачи.'''

import json

from . import config
from .mistral_client import chat, encode_image
from .schema import PAGE_SCHEMA

PROMPT_HEAD = (
    'Ты парсер экзаменационных листов ЕГЭ по математике. '
    'На изображении страница с задачами. Извлеки КАЖДУЮ задачу '
    'в порядке нумерации. Ничего не придумывай и не решай — '
    'только переноси существующий текст.\n'
    'Для каждой задачи верни поля:\n'
    '- task_num: номер задачи строго как на листе (строка).\n'
    '- condition: полный текст условия. Все математические '
    'переменные, формулы и величины оберни в $...$ (LaTeX).\n'
    '- figure_index: индекс области с рисунком этой задачи.\n'
)

PROMPT_REGIONS = (
    'На странице автоматически найдены прямоугольные области с '
    'рисунками (нормализованные координаты [x0, y0, x1, y1], где '
    '(0, 0) — левый верхний угол страницы):\n{regions}\n'
    'Для каждой задачи укажи figure_index — индекс относящейся к '
    'ней области, или -1, если у задачи нет рисунка. Некоторые '
    'области могут быть декоративными (логотип, QR-код, пример '
    'бланка ответа) — их не назначай никакой задаче.'
)

PROMPT_NO_REGIONS = (
    'На этой странице рисунки не обнаружены, поэтому для всех '
    'задач figure_index равен -1.'
)


def _format_regions(candidates):
    '''Форматирует рамки-кандидаты в нумерованный список.'''
    if not candidates:
        return PROMPT_NO_REGIONS
    lines = []
    for index, box in enumerate(candidates):
        coords = ', '.join(f'{value:.2f}' for value in box)
        lines.append(f'{index}: [{coords}]')
    return PROMPT_REGIONS.format(regions='\n'.join(lines))


def parse_page(image_path, candidates):
    '''Возвращает список задач, разобранных с одной страницы.'''
    prompt = PROMPT_HEAD + _format_regions(candidates)
    messages = [
        {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': prompt},
                {
                    'type': 'image_url',
                    'image_url': encode_image(image_path),
                },
            ],
        }
    ]
    content = chat(
        messages,
        model=config.VISION_MODEL,
        response_format=PAGE_SCHEMA,
    )
    return json.loads(content)['tasks']
