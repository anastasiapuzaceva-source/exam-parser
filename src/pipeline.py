'''Сквозная оркестрация пайплайна разбора экзаменов.'''

import re
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import config, larin_answers
from .classifier import classify_task, load_categories
from .cropper import crop_figure, save_native_image
from .excel_writer import write_tasks
from .pdf_figures import assign_figures, extract_page_figures
from .paddle_parser import parse_page
from .pdf_render import render_pdf
from .solver import solve_task
from .textfmt import clean_html

_SUBPART_RE = re.compile(r'^\s*(\d+)[\s.)]*[А-Яа-яA-Za-z][\s.)]*$')
_TASK_NUM_RE = re.compile(r'\d+')


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


def _save_figure(match, page_path, image_name, images_dir):
    '''Сохраняет рисунок: нативное изображение или вырезку со страницы.'''
    data = match.get('image')
    if data:
        try:
            return save_native_image(data, image_name, images_dir)
        except (OSError, ValueError):
            pass
    return crop_figure(page_path, match['box'], image_name, images_dir)


def _parse_all_pages(page_paths, page_figures, images_dir):
    '''Парсинг страниц и вырезка рисунков (последовательно, без LLM).'''
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
        seeds = [
            task.get('figure_box') if task.get('has_figure') else None
            for task in tasks
        ]
        regions = [task.get('region') for task in tasks]
        matches = assign_figures(seeds, page, regions)
        for task, match in zip(tasks, matches):
            counter += 1
            num = task.get('task_num', str(counter))
            condition = clean_html(task.get('condition', ''))
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
                   site_answers=None):
    '''Парсит последовательно, решает параллельно (SOLVER_WORKERS потоков).'''
    site_answers = site_answers or {}
    records = _parse_all_pages(page_paths, page_figures, images_dir)
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
        with tempfile.TemporaryDirectory() as tmp:
            page_paths = render_pdf(path, tmp)
            rows = _process_pages(
                page_paths, page_figures, categories, images_dir,
                site_answers,
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
