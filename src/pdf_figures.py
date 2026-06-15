'''Извлечение точных рамок рисунков из встроенных изображений PDF.'''

import fitz


def extract_figure_boxes(pdf_path):
    '''
    Возвращает нормализованные рамки рисунков по страницам.
    '''
    document = fitz.open(pdf_path)
    pages = []
    for page in document:
        width = page.rect.width
        height = page.rect.height
        boxes = []
        for image in page.get_images(full=True):
            for rect in page.get_image_rects(image[0]):
                boxes.append([
                    rect.x0 / width,
                    rect.y0 / height,
                    rect.x1 / width,
                    rect.y1 / height,
                ])
        pages.append(boxes)
    document.close()
    return pages
