'''Сквозная оркестрация пайплайна разбора экзаменов.'''

import re
import shutil
import tempfile
from pathlib import Path

from . import config
from .classifier import classify_task, load_categories
from .cropper import crop_figure, save_native_image
from .excel_writer import write_tasks
from .pdf_figures import assign_figures, extract_page_figures
from .pdf_render import render_pdf
from .solver import solve_task
from .vision_parser import parse_page


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


def _process_pages(page_paths, page_figures, categories, images_dir):
    '''Разбирает, вырезает, улучшает и решает задачи на всех страницах.'''
    rows = []
    counter = 0
    total = len(page_paths)
    for page_index, page_path in enumerate(page_paths, start=1):
        print(f'[parse] page {page_index}/{total}')
        tasks = parse_page(page_path)
        if page_index - 1 < len(page_figures):
            page = page_figures[page_index - 1]
        else:
            page = None
        seeds = [
            task.get('figure_box') if task.get('has_figure') else None
            for task in tasks
        ]
        matches = assign_figures(seeds, page)
        for task, match in zip(tasks, matches):
            counter += 1
            num = task.get('task_num', str(counter))
            condition = task.get('condition', '')
            image_name = ''
            if match is not None:
                name = _safe_name(num, counter)
                saved = _save_figure(match, page_path, name, images_dir)
                if saved is not None:
                    image_name = name
            print(f'[solve] task {num}')
            solved = solve_task(num, condition)
            category = classify_task(num, condition, categories)
            rows.append({
                'task_num': num,
                'condition': condition,
                'image_name': image_name,
                'solution': solved.get('solution', ''),
                'answer': solved.get('answer', ''),
                'category': category,
            })
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
    '''
    Обрабатывает один входной файл в одноимённую папку результата.
    '''
    path = Path(path)
    suffix = path.suffix.lower()
    result_dir = config.OUTPUT_DIR / path.stem
    excel_path = result_dir / f'{path.stem}.xlsx'
    images_dir = result_dir
    if result_dir.exists():
        shutil.rmtree(result_dir)
    print(f'[file] {path.name}')
    categories = load_categories()
    if suffix == '.pdf':
        page_figures = extract_page_figures(path)
        with tempfile.TemporaryDirectory() as tmp:
            page_paths = render_pdf(path, tmp)
            rows = _process_pages(
                page_paths, page_figures, categories, images_dir,
            )
    elif suffix in config.IMAGE_EXTENSIONS:
        rows = _process_pages([path], [None], categories, images_dir)
    else:
        print(f'[skip] {path.name}: unsupported file type')
        return None
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
