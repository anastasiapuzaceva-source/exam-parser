'''Рендеринг страниц PDF в PNG через PyMuPDF.'''

from pathlib import Path

import fitz

from . import config


def render_pdf(pdf_path, pages_dir, dpi=None):
    '''Рендерит каждую страницу PDF в PNG и возвращает их пути.'''
    dpi = dpi or config.RENDER_DPI
    pages_dir = Path(pages_dir)
    pages_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    document = fitz.open(pdf_path)
    for index, page in enumerate(document, start=1):
        pixmap = page.get_pixmap(matrix=matrix)
        out_path = pages_dir / f'page_{index}.png'
        pixmap.save(out_path)
        paths.append(out_path)
    document.close()
    return paths
