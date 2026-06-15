'''Вырезание рисунков задач со страниц по нормализованным рамкам.'''

from pathlib import Path

from PIL import Image


def crop_figure(page_path, box, image_name, images_dir, padding=0.012):
    '''
    Вырезает нормализованную рамку со страницы и сохраняет в PNG.
    '''
    if not box or len(box) != 4:
        return None
    images_dir = Path(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(page_path) as page:
        width, height = page.size
        x0, y0, x1, y1 = box
        left = max(0, int((x0 - padding) * width))
        top = max(0, int((y0 - padding) * height))
        right = min(width, int((x1 + padding) * width))
        bottom = min(height, int((y1 + padding) * height))
        if right <= left or bottom <= top:
            return None
        crop = page.crop((left, top, right, bottom))
        out_path = images_dir / image_name
        crop.save(out_path)
    return out_path
