'''Сквозная оркестрация пайплайна разбора экзаменов.'''

import re
import shutil
import tempfile
from pathlib import Path

from . import config
from .cropper import crop_figure
from .excel_writer import write_tasks
from .pdf_figures import extract_figure_boxes
from .pdf_render import render_pdf
from .solver import solve_task
from .vision_parser import parse_page


def _safe_name(task_num, counter):
    '''Формирует безопасное имя файла рисунка из номера задачи.'''
    slug = re.sub(r'[^0-9A-Za-zА-Яа-я]+', '_', task_num).strip('_')
    slug = slug or str(counter)
    return f'task_{slug}.png'


def _process_pages(page_paths, figure_boxes, images_dir):
    '''Разбирает, вырезает и решает задачи на всех страницах.'''
    rows = []
    counter = 0
    total = len(page_paths)
    for page_index, page_path in enumerate(page_paths, start=1):
        print(f'[parse] page {page_index}/{total}')
        if page_index - 1 < len(figure_boxes):
            candidates = figure_boxes[page_index - 1]
        else:
            candidates = []
        tasks = parse_page(page_path, candidates)
        for task in tasks:
            counter += 1
            num = task.get('task_num', str(counter))
            image_name = ''
            index = task.get('figure_index', -1)
            if 0 <= index < len(candidates):
                name = _safe_name(num, counter)
                saved = crop_figure(
                    page_path, candidates[index], name, images_dir,
                )
                if saved is not None:
                    image_name = name
            print(f'[solve] task {num}')
            solved = solve_task(num, task.get('condition', ''))
            rows.append({
                'task_num': num,
                'condition': task.get('condition', ''),
                'image_name': image_name,
                'solution': solved.get('solution', ''),
                'answer': solved.get('answer', ''),
            })
    return rows


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
    if suffix == '.pdf':
        figure_boxes = extract_figure_boxes(path)
        with tempfile.TemporaryDirectory() as tmp:
            page_paths = render_pdf(path, tmp)
            rows = _process_pages(page_paths, figure_boxes, images_dir)
    elif suffix in config.IMAGE_EXTENSIONS:
        rows = _process_pages([path], [[]], images_dir)
    else:
        print(f'[skip] {path.name}: unsupported file type')
        return None
    write_tasks(rows, excel_path)
    print(f'[done] {path.name} -> {excel_path} ({len(rows)} task(s))')
    return excel_path


def run_all(input_dir=None):
    '''Обрабатывает по очереди все подходящие файлы из папки.'''
    input_dir = Path(input_dir or config.INPUT_DIR)
    files = sorted(p for p in input_dir.iterdir() if p.is_file())
    if not files:
        print(f'[warn] no input files in {input_dir}')
        return []
    results = []
    for path in files:
        results.append(process_file(path))
    return results
