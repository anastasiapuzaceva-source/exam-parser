'''Локальный парсер страницы на PaddleOCR (PP-StructureV3).'''

import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

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
_LEADING_NUM_RE = re.compile(r'^\s*\d{1,2}\s*[.)]?\s*')
_ANSWER_RE = re.compile(r'^\s*ответ\b', re.IGNORECASE)
_BULLET_RE = re.compile(r'^\s*(?:[–—•\-]|[а-яё]\)|\d+\))\s+')
_NOISE_RE = re.compile(
    r'(alexlarin|государственн\w*\s+экзамен|математика,?\s*\d+\s*класс|'
    r'не\s+забудьте|бланк\s+ответ|©|часть\s+\d)',
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
            formula_recognition_model_name=config.PADDLE_FORMULA_MODEL,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            use_seal_recognition=False,
            use_chart_recognition=False,
            device='gpu' if config.PADDLE_USE_GPU else 'cpu',
            enable_mkldnn=False,
        )
    return _engine


@contextmanager
def _inference_image(image_path):
    '''Изображение для инференса с длинной стороной не больше лимита.'''
    limit = config.PADDLE_MAX_SIDE
    with Image.open(image_path) as image:
        width, height = image.size
        if limit <= 0 or max(width, height) <= limit:
            yield str(image_path), width, height
            return
        scale = limit / max(width, height)
        new_size = (
            max(1, round(width * scale)),
            max(1, round(height * scale)),
        )
        resized = image.convert('RGB').resize(new_size, Image.LANCZOS)
    handle = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    handle.close()
    tmp_path = handle.name
    try:
        resized.save(tmp_path)
        yield tmp_path, new_size[0], new_size[1]
    finally:
        Path(tmp_path).unlink(missing_ok=True)


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
        content = _block_field(
            block, 'block_content', 'content', 'text', 'res')
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
    lines = [
        line.strip() for line in (text or '').splitlines() if line.strip()
    ]
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


def _task_region(items):
    '''Рамка [x0,y0,x1,y1] задачи по боксам её элементов.'''
    boxes = [item['box'] for item in items
             if item.get('box') and item['box'] != [0, 0, 0, 0]]
    if not boxes:
        return None
    return [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]


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


def _strip_leading_num(text):
    '''Срезает ведущий номер, даже искажённый (как «3Прямая» без точки).'''
    return _LEADING_NUM_RE.sub('', text or '', count=1)


_MAX_TASK = config.PADDLE_MAX_TASK


def _segment_tasks(items, start_num):
    '''Делит элементы на задачи по разделителю «Ответ:».'''
    tasks = []
    state = {'current': None, 'last': start_num, 'expect_new': False}

    def start_task(num, first_text, box):
        state['last'] = num
        current = {
            'task_num': str(num),
            'items': [{'kind': 'text', 'text': first_text, 'box': box}],
        }
        tasks.append(current)
        state['current'] = current
        state['expect_new'] = False

    def append(item):
        if state['current'] is not None:
            state['current']['items'].append(item)

    for item in items:
        if item['kind'] != 'text':
            append(item)
            continue
        text = item['text'] or ''
        if _ANSWER_RE.match(text):
            state['expect_new'] = True
            continue
        if _NOISE_RE.search(text):
            continue
        match = _TASK_NUM_RE.match(text)
        num = int(match.group(1)) if match else None
        if num is not None and state['last'] < num <= _MAX_TASK:
            start_task(num, _strip_task_number(text), item['box'])
        elif state['expect_new'] and state['last'] < _MAX_TASK:
            start_task(
                state['last'] + 1, _strip_leading_num(text), item['box'])
        else:
            append(item)
    return tasks


def parse_page(image_path, page=None, start_num=0):
    '''Возвращает список задач со страницы варианта.'''
    try:
        with _inference_image(image_path) as (infer_path, width, height):
            result = next(iter(_get_engine().predict(infer_path)), None)
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
            'region': _task_region(task['items']),
        })
    return tasks


_TR_RE = re.compile(r'<tr>(.*?)</tr>', re.S)
_TD_RE = re.compile(r'<td[^>]*>(.*?)</td>', re.S)

_SUBLABEL_RE = re.compile(r'\\left\(\s*\\mathrm\{[^{}]{1,3}\}\s*\\right\)')
_FRAC_RE = re.compile(r'\\frac\{([^{}]*)\}\{([^{}]*)\}')
_SQRT_RE = re.compile(r'\\sqrt\{([^{}]*)\}')
_RU_LABELS = ['А', 'Б', 'В', 'Г']
_LATEX_SYMBOLS = [
    (r'\\pm', '±'), (r'\\mp', '∓'), (r'\\cdot', '·'), (r'\\times', '×'),
    (r'\\infty', '∞'), (r'\\leqslant', '≤'), (r'\\geqslant', '≥'),
    (r'\\leq', '≤'), (r'\\geq', '≥'), (r'\\neq', '≠'), (r'\\notin', '∉'),
    (r'\\in', '∈'), (r'\\cup', '∪'), (r'\\cap', '∩'), (r'\\pi', 'π'),
    (r'\\circ', '°'), (r'\\ldots', '…'), (r'\\dots', '…'),
]


def _clean_answer(text):
    '''Делает ответ части 2 читаемым: LaTeX-шум → юникод/текст.'''
    text = text or ''
    seq = [0]

    def _label(_match):
        index = seq[0]
        seq[0] += 1
        return f'{_RU_LABELS[index]}) ' if index < len(_RU_LABELS) else ' '

    text = _SUBLABEL_RE.sub(_label, text)
    text = _SQRT_RE.sub(r'√\1', text)
    text = _FRAC_RE.sub(r'\1/\2', text)
    text = text.replace('\\left', '').replace('\\right', '')
    text = re.sub(r'\\mathrm\{([^{}]*)\}', r'\1', text)
    for pattern, char in _LATEX_SYMBOLS:
        text = re.sub(pattern, char, text)
    text = re.sub(r'(?<!\\)[{}]', '', text)
    text = text.replace('\\{', '{').replace('\\}', '}').replace('\\|', '|')
    text = re.sub(r'\\(?:quad|qquad|,|;|:|!| )', ' ', text)
    text = text.replace('$', '')
    return re.sub(r'\s+', ' ', text).strip()


def recognize_answer_table(image_path):
    '''Распознаёт таблицу ответов части 2 → {номер: html_ответ}.'''
    try:
        with _inference_image(image_path) as (infer_path, _w, _h):
            result = next(iter(_get_engine().predict(infer_path)), None)
        if result is None:
            return {}
        blocks = _result_blocks(result)
    except Exception as error:
        print(f'[paddle] answer table error: {error}')
        return {}
    answers = {}
    for block in blocks:
        label = (_block_field(block, 'block_label', 'label', 'type') or '')
        if str(label).lower() != 'table':
            continue
        html = _block_field(block, 'block_content', 'content', 'text') or ''
        for row in _TR_RE.findall(html):
            cells = _TD_RE.findall(row)
            if len(cells) < 2:
                continue
            num_match = re.search(r'\d+', cells[0])
            if not num_match:
                continue
            answer = _clean_answer(clean_html(cells[1]))
            if answer:
                answers[int(num_match.group(0))] = answer
    return answers


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
