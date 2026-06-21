'''Локальный парсер страницы на PaddleOCR (PP-StructureV3).'''

import re

from PIL import Image

from . import config
from .textfmt import clean_html

_engine = None

_TEXT_LABELS = {'text', 'paragraph', 'paragraph_title', 'title', 'abstract'}
_FORMULA_LABELS = {'formula', 'formula_number', 'equation', 'inline_formula'}
_LIST_LABELS = {'list', 'list_item'}
_FIGURE_LABELS = {'image', 'figure', 'chart', 'figure_title'}
_SKIP_LABELS = {'table', 'table_title', 'header', 'footer', 'page_number',
                'seal', 'aside_text', 'reference'}

_TASK_NUM_RE = re.compile(r'^\s*(\d{1,2})\s*([А-Яа-яA-Za-z])?\s*[.)](?!\d)\s*')
_BULLET_RE = re.compile(r'^\s*(?:[–—•\-]|[а-яё]\)|\d+\))\s+')
_NOISE_RE = re.compile(
    r'(alexlarin|единый\s+государственный|ответ\s*[:\-]|©|часть\s+\d)',
    re.IGNORECASE,
)


def _get_engine():
    '''Создаёт и кеширует пайплайн PP-StructureV3.'''
    global _engine
    if _engine is None:
        from paddleocr import PPStructureV3
        _engine = PPStructureV3(
            lang=config.PADDLE_LANG,
            use_formula_recognition=True,
            device='gpu' if config.PADDLE_USE_GPU else 'cpu',
        )
    return _engine


def _result_blocks(result):
    '''Достаёт список блоков в порядке чтения из результата PP-StructureV3.'''
    data = getattr(result, 'json', None)
    if isinstance(data, dict):
        data = data.get('res', data)
    else:
        data = {}
    for key in ('parsing_res_list', 'parsing_result', 'layout_parsing_result'):
        blocks = data.get(key)
        if blocks:
            return blocks
    return []


def _block_field(block, *names):
    '''Возвращает первое непустое поле блока по списку возможных имён.'''
    for name in names:
        value = block.get(name) if isinstance(block, dict) else None
        if value:
            return value
    return None


def _normalize_box(box, width, height):
    '''Переводит пиксельную рамку [x0,y0,x1,y1] в доли страницы (0..1).'''
    if not box or len(box) < 4 or width <= 0 or height <= 0:
        return [0, 0, 0, 0]
    x0, y0, x1, y1 = box[0], box[1], box[2], box[3]
    return [
        max(0.0, min(1.0, x0 / width)),
        max(0.0, min(1.0, y0 / height)),
        max(0.0, min(1.0, x1 / width)),
        max(0.0, min(1.0, y1 / height)),
    ]


def _to_items(blocks, width, height):
    '''Преобразует блоки в плоский список типизированных элементов.'''
    items = []
    for block in blocks:
        label = (_block_field(block, 'block_label', 'label', 'type') or '')
        label = str(label).lower()
        content = _block_field(block, 'block_content', 'content', 'text', 'res')
        box = _block_field(block, 'block_bbox', 'bbox', 'box')
        if label in _FORMULA_LABELS:
            kind = 'formula'
        elif label in _LIST_LABELS:
            kind = 'list'
        elif label in _FIGURE_LABELS:
            kind = 'figure'
        elif label in _SKIP_LABELS:
            continue
        else:
            kind = 'text'
        items.append({
            'kind': kind,
            'text': content if isinstance(content, str) else '',
            'box': _normalize_box(box, width, height),
        })
    return items


def _clean_formula(latex):
    '''Нормализует LaTeX формулы к одинарному $...$.'''
    latex = (latex or '').strip()
    for wrap in ('$$', '$', r'\[', r'\]', r'\(', r'\)'):
        latex = latex.replace(wrap, '')
    latex = re.sub(r'\\begin\{.*?\}|\\end\{.*?\}', '', latex)
    latex = latex.strip()
    return f'${latex}$' if latex else ''


def _join_inline(run):
    '''Склеивает строчные элементы (текст + формулы) в одно предложение.'''
    out = ''
    for kind, value in run:
        piece = _clean_formula(value) if kind == 'formula' else value.strip()
        if not piece:
            continue
        if out and not out.endswith((' ', '(')) and not piece.startswith(
            (' ', ',', '.', ';', ':', ')', '?', '!')
        ):
            out += ' '
        out += piece
    return out.strip()


def _list_html(text):
    '''Собирает <ul><li>…</li></ul> из многострочного текста списка.'''
    lines = [line.strip() for line in (text or '').splitlines() if line.strip()]
    items = [_BULLET_RE.sub('', line) for line in lines] or [text.strip()]
    body = ''.join(f'<li>{item}</li>' for item in items if item)
    return f'<ul>{body}</ul>' if body else ''


def _looks_like_list(text):
    '''Похож ли текстовый блок на перечисление (несколько строк-пунктов).'''
    lines = [line for line in (text or '').splitlines() if line.strip()]
    bullets = sum(1 for line in lines if _BULLET_RE.match(line))
    return len(lines) >= 2 and bullets >= max(2, len(lines) - 1)


def _build_condition_html(items):
    '''Собирает HTML-условие из элементов одной задачи.'''
    parts = []
    run = []

    def flush():
        if run:
            sentence = _join_inline(run)
            if sentence:
                parts.append(f'<p>{sentence}</p>')
            run.clear()

    for item in items:
        kind = item['kind']
        text = item['text']
        if kind == 'formula':
            run.append(('formula', text))
        elif kind == 'list' or (kind == 'text' and _looks_like_list(text)):
            flush()
            html = _list_html(text)
            if html:
                parts.append(html)
        elif kind == 'text':
            run.append(('text', text))
    flush()
    return clean_html('\n'.join(parts))


def _figure_box(items):
    '''Возвращает (has_figure, figure_box) по элементам-рисункам задачи.'''
    for item in items:
        if item['kind'] == 'figure':
            box = item['box']
            if box and box != [0, 0, 0, 0]:
                return True, box
    return False, [0, 0, 0, 0]


def _strip_task_number(text):
    '''Убирает ведущий «N.»/«N)» из первого текстового блока задачи.'''
    return _TASK_NUM_RE.sub('', text or '', count=1)


_MAX_TASK = config.PADDLE_MAX_TASK


def _segment_tasks(items, start_num):
    '''Делит элементы на задачи по номерам.'''
    tasks = []
    current = None
    last = start_num
    for item in items:
        text = item['text']
        if item['kind'] == 'text' and _NOISE_RE.search(text or ''):
            continue
        match = _TASK_NUM_RE.match(text or '') if item['kind'] == 'text' else None
        if match and last < int(match.group(1)) <= _MAX_TASK:
            last = int(match.group(1))
            stripped = dict(item, text=_strip_task_number(text))
            current = {'task_num': str(last), 'items': [stripped]}
            tasks.append(current)
        elif current is not None:
            current['items'].append(item)
    return tasks


def parse_page(image_path, page=None, start_num=0):
    '''Возвращает список задач со страницы (контракт vision_parser.parse_page).'''
    try:
        with Image.open(image_path) as image:
            width, height = image.size
        result = next(iter(_get_engine().predict(str(image_path))), None)
        if result is None:
            return []
        items = _to_items(_result_blocks(result), width, height)
        segmented = _segment_tasks(items, start_num)
    except Exception as error:
        print(f'[paddle] parse error: {error}')
        return []
    tasks = []
    for task in segmented:
        condition = _build_condition_html(task['items'])
        has_figure, box = _figure_box(task['items'])
        _qa_flag(task['task_num'], condition)
        tasks.append({
            'task_num': task['task_num'],
            'condition': condition,
            'has_figure': has_figure,
            'figure_box': box,
        })
    return tasks


def _qa_flag(task_num, condition):
    '''Помечает подозрительные разборы для ручной проверки.'''
    reasons = []
    if not condition.strip():
        reasons.append('пустое условие')
    if condition.count('$') % 2 != 0:
        reasons.append('непарный $')
    if condition.count('{') != condition.count('}'):
        reasons.append('непарная {}')
    if reasons:
        print(f'[paddle][qa] задача {task_num}: {", ".join(reasons)}')
    return '; '.join(reasons)
