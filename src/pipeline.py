'''Сквозная оркестрация пайплайна разбора экзаменов.'''

import re
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import fitz

from . import config, larin_answers
from .classifier import classify_task, load_categories
from .cropper import crop_figure, save_native_image
from .excel_writer import write_tasks
from .pdf_figures import assign_figures, extract_page_figures
from .paddle_parser import parse_page
from .pdf_render import render_pdf
from .solver import solve_task
from .textfmt import clean_html
from .vision_parser import parse_conditions

_SUBPART_RE = re.compile(r'^\s*(\d+)[\s.)]*[А-Яа-яA-Za-z][\s.)]*$')
_TASK_NUM_RE = re.compile(r'\d+')
_PDF_TASK_RE = re.compile(r'^\s*(\d{1,2})\s*[.)]\s*(.*)')
_PDF_WORD_RE = re.compile(r'[0-9A-Za-zА-Яа-яЁё]+')
_HTML_SPLIT_RE = re.compile(r'(<[^>]+>|\$[^$]*\$)')
_NOISE_RE = re.compile(
    r'(единый\s+государственный\s+экзамен|математика,?\s*\d+\s*класс|'
    r'тренировочный\s+вариант|alexlarin|ответом\s+к\s+заданиям|'
    r'инструкция\s+по\s+выполнению|часть\s+\d|бланк\s+ответов|'
    r'не\s+забудьте|запишите\s+число)',
    re.IGNORECASE,
)


def _task_int(task_num):
    '''Возвращает первое целое из номера задачи или ``None``.'''
    match = _TASK_NUM_RE.search(str(task_num or ''))
    return int(match.group(0)) if match else None


def _join_conditions(first, second):
    '''Склеивает условия подпунктов в один HTML-блок по порядку.'''
    first = (first or '').strip()
    second = (second or '').strip()
    if not first:
        return second
    if not second:
        return first
    return f'{first}\n{second}'


def _merge_subparts(tasks):
    '''Объединяет подпункты вида «13 А» и «13 Б» в одну задачу «13».'''
    merged = []
    index_by_base = {}
    for task in tasks:
        num = (task.get('task_num') or '').strip()
        match = _SUBPART_RE.match(num)
        if not match:
            merged.append(task)
            continue
        base = match.group(1)
        if base in index_by_base:
            target = merged[index_by_base[base]]
            target['condition'] = _join_conditions(
                target.get('condition', ''), task.get('condition', ''),
            )
            if not target.get('has_figure') and task.get('has_figure'):
                target['has_figure'] = True
                target['figure_box'] = task.get('figure_box')
        else:
            new_task = dict(task)
            new_task['task_num'] = base
            index_by_base[base] = len(merged)
            merged.append(new_task)
    return merged


def _site_answers(variant_stem):
    '''Ответы Ларина одним словарём: 1–12 из JS, 13+ из картинки.'''
    answers = dict(larin_answers.fetch_answers(variant_stem))
    answers.update(larin_answers.fetch_part2_answers(variant_stem))
    return answers


def _apply_site_answers(rows, site_answers):
    '''Перезаписывает столбец ``answer`` значениями с сайта Ларина.'''
    if not site_answers:
        return
    for row in rows:
        num = _task_int(row.get('task_num'))
        if num is not None and num in site_answers:
            row['answer'] = site_answers[num]


def _safe_name(task_num, counter):
    '''Формирует безопасное имя файла рисунка из номера задачи.'''
    slug = re.sub(r'[^0-9A-Za-zА-Яа-я]+', '_', task_num).strip('_')
    slug = slug or str(counter)
    return f'task_{slug}.webp'


def _pdf_task_texts(pdf_path):
    '''Извлекает сырой текст задач из текстового слоя PDF для ремонта OCR.'''
    tasks = {}
    current = None
    document = fitz.open(pdf_path)
    try:
        for page in document:
            for raw_line in page.get_text('text').splitlines():
                line = re.sub(r'\s+', ' ', raw_line.replace('\xa0', ' '))
                line = line.strip()
                if not line:
                    continue
                match = _PDF_TASK_RE.match(line)
                if match:
                    num = int(match.group(1))
                    if 1 <= num <= config.PADDLE_MAX_TASK:
                        current = num
                        tail = match.group(2).strip()
                        tasks.setdefault(current, [])
                        if tail:
                            tasks[current].append(tail)
                    continue
                if current is None:
                    continue
                if line.lower().startswith('ответ:'):
                    continue
                if _NOISE_RE.search(line):
                    continue
                tasks[current].append(line)
    finally:
        document.close()
    return {num: ' '.join(lines) for num, lines in tasks.items()}


_HOMOGLYPH_MAP = str.maketrans({
    'a': 'а', 'e': 'е', 'o': 'о', 'p': 'р', 'c': 'с', 'x': 'х', 'y': 'у',
})


def _normalize_script(text):
    '''Сводит латинские омоглифы к кириллице, чтобы OCR не путал буквы.'''
    return text.translate(_HOMOGLYPH_MAP)


def _segment_token(token, pdf_words):
    '''Разбивает склеенный токен на цепочку соседних слов из PDF.'''
    lower = _normalize_script(token.lower())
    count = len(pdf_words)
    for start in range(count):
        word0 = _normalize_script(pdf_words[start].lower())
        if not lower.startswith(word0):
            continue
        pos = len(word0)
        stop = start + 1
        while pos < len(lower) and stop < count:
            word = _normalize_script(pdf_words[stop].lower())
            if not lower.startswith(word, pos):
                break
            pos += len(word)
            stop += 1
        if pos != len(lower) or stop - start < 2:
            continue
        return ' '.join(pdf_words[start:stop])
    return token


def _repair_plain_text_spacing(text, pdf_text):
    '''Вставляет пробелы там, где PDF содержит несколько соседних слов.'''
    if not text or not pdf_text:
        return text
    pdf_words = [word for word in _PDF_WORD_RE.findall(pdf_text) if word]
    if not pdf_words:
        return text
    text = _PDF_WORD_RE.sub(
        lambda m: _segment_token(m.group(0), pdf_words), text,
    )
    text = re.sub(r'(?<!\d)([.,;:!?])(?=[^\s\d])', r'\1 ', text)
    text = re.sub(r'(?<=[а-яёa-z])(?=[А-ЯЁA-Z])', ' ', text)
    return re.sub(r'[ \t]{2,}', ' ', text)


def _repair_condition_spacing(condition, pdf_text):
    '''Чинит склейки слов в HTML, не заходя внутрь тегов и формул.'''
    if not pdf_text:
        return condition
    parts = _HTML_SPLIT_RE.split(condition or '')
    for index, part in enumerate(parts):
        if not part or part.startswith('<') or (
            part.startswith('$') and part.endswith('$')
        ):
            continue
        parts[index] = _repair_plain_text_spacing(part, pdf_text)
    return ''.join(parts)


def _save_figure(match, page_path, image_name, images_dir):
    '''Сохраняет рисунок: нативное изображение или вырезку со страницы.'''
    data = match.get('image')
    if data:
        try:
            return save_native_image(data, image_name, images_dir)
        except (OSError, ValueError):
            pass
    return crop_figure(page_path, match['box'], image_name, images_dir)


def _parse_all_pages(page_paths, page_figures, images_dir, pdf_texts=None):
    '''Парсинг страниц и вырезка рисунков (последовательно, без LLM).'''
    pdf_texts = pdf_texts or {}
    records = []
    counter = 0
    last_num = 0
    total = len(page_paths)
    for page_index, page_path in enumerate(page_paths, start=1):
        print(f'[parse] page {page_index}/{total}')
        if page_index - 1 < len(page_figures):
            page = page_figures[page_index - 1]
        else:
            page = None
        tasks = _merge_subparts(parse_page(page_path, page, last_num))
        for task in tasks:
            num = _task_int(task.get('task_num'))
            if num is not None:
                last_num = max(last_num, num)
        vlm_conditions = parse_conditions(page_path)
        seeds = [
            task.get('figure_box') if task.get('has_figure') else None
            for task in tasks
        ]
        regions = [task.get('region') for task in tasks]
        matches = assign_figures(seeds, page, regions)
        for task, match in zip(tasks, matches):
            counter += 1
            num = task.get('task_num', str(counter))
            task_int = _task_int(num)
            vlm_condition = vlm_conditions.get(task_int, '')
            if vlm_condition:
                condition = clean_html(vlm_condition)
            else:
                condition = clean_html(task.get('condition', ''))
                condition = _repair_condition_spacing(
                    condition, pdf_texts.get(task_int, ''),
                )
            image_name = ''
            if match is not None:
                name = _safe_name(num, counter)
                saved = _save_figure(match, page_path, name, images_dir)
                if saved is not None:
                    image_name = name
            records.append({
                'task_num': num,
                'condition': condition,
                'image_name': image_name,
            })
    return records


def _solve_record(record, categories, site_answers):
    '''Решает и классифицирует одну задачу; собирает строку результата.'''
    num = record['task_num']
    condition = record['condition']
    print(f'[solve] task {num}')
    hint = site_answers.get(_task_int(num))
    solved = solve_task(num, condition, answer_hint=hint)
    category = classify_task(num, condition, categories)
    return {
        'task_num': num,
        'condition': condition,
        'image_name': record['image_name'],
        'solution': solved.get('solution', ''),
        'answer': solved.get('answer', ''),
        'category': category,
    }


def _process_pages(page_paths, page_figures, categories, images_dir,
                   site_answers=None, pdf_texts=None):
    '''Парсит последовательно, решает параллельно (SOLVER_WORKERS потоков).'''
    site_answers = site_answers or {}
    records = _parse_all_pages(page_paths, page_figures, images_dir, pdf_texts)
    rows = [None] * len(records)
    workers = max(1, config.SOLVER_WORKERS)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _solve_record, record, categories, site_answers): index
            for index, record in enumerate(records)
        }
        for future in as_completed(futures):
            rows[futures[future]] = future.result()
    return rows


def _archive_result(result_dir):
    '''Пакует папку результата в .zip рядом и удаляет саму папку.'''
    zip_path = result_dir.parent / f'{result_dir.name}.zip'
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(result_dir), 'zip', root_dir=result_dir)
    shutil.rmtree(result_dir)
    return zip_path


def process_file(path):
    '''Обрабатывает один входной файл в одноимённую папку результата.'''
    path = Path(path)
    suffix = path.suffix.lower()
    result_dir = config.OUTPUT_DIR / path.stem
    excel_path = result_dir / f'{path.stem}.xlsx'
    images_dir = result_dir
    if result_dir.exists():
        shutil.rmtree(result_dir)
    print(f'[file] {path.name}')
    categories = load_categories()
    site_answers = _site_answers(path.stem)
    if not site_answers:
        print(f'[warn] нет ответов с сайта Ларина для {path.stem} '
              '(ожидается trvarNNN)')
    if suffix == '.pdf':
        page_figures = extract_page_figures(path)
        pdf_texts = _pdf_task_texts(path)
        with tempfile.TemporaryDirectory() as tmp:
            page_paths = render_pdf(path, tmp)
            rows = _process_pages(
                page_paths, page_figures, categories, images_dir,
                site_answers, pdf_texts,
            )
    elif suffix in config.IMAGE_EXTENSIONS:
        rows = _process_pages(
            [path], [None], categories, images_dir, site_answers,
        )
    else:
        print(f'[skip] {path.name}: unsupported file type')
        return None
    _apply_site_answers(rows, site_answers)
    write_tasks(rows, excel_path)
    zip_path = _archive_result(result_dir)
    print(f'[done] {path.name} -> {zip_path} ({len(rows)} task(s))')
    return zip_path


def run_all(input_dir=None):
    '''Обрабатывает по очереди все подходящие файлы из папки.'''
    input_dir = Path(input_dir or config.INPUT_DIR)
    files = sorted(p for p in input_dir.iterdir() if p.is_file())
    if not files:
        print(f'[warn] no input files in {input_dir}')
        return []
    results = []
    for path in files:
        try:
            results.append(process_file(path))
        except Exception as error:
            print(f'[error] {path.name}: {error}')
            results.append(None)
    return results
