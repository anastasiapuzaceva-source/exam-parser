'''Геометрия рисунков PDF: рамки-кандидаты и подбор по координатам.'''

import io

import fitz
from PIL import Image

_MAX_SPAN = 0.8
_RASTER_MIN = 0.05
_STROKE_2D = 0.02
_NOISE = 0.005
_CLUSTER_PAD = 0.02
_EXPAND_PAD = 0.02
_SEED_EXPAND = 0.04
_MIN_FIGURE = 0.06
_MAX_FIGURE = 0.6
_MATCH_GAP = 0.10
_MAX_WORDS = 6
_MIN_STROKES = 3


def _norm(rect, rotation, width, height):
    '''Поворачивает и нормирует прямоугольник в доли страницы.'''
    r = rect * rotation
    x0, x1 = sorted((r.x0, r.x1))
    y0, y1 = sorted((r.y0, r.y1))
    return [x0 / width, y0 / height, x1 / width, y1 / height]


def _clusters(rects):
    '''Сливает близкие рамки в связные группы и возвращает их.'''
    rects = [list(r) for r in rects]
    changed = True
    while changed:
        changed = False
        out = []
        while rects:
            a = rects.pop()
            i = 0
            while i < len(rects):
                b = rects[i]
                disjoint = (
                    a[2] + _CLUSTER_PAD < b[0]
                    or b[2] + _CLUSTER_PAD < a[0]
                    or a[3] + _CLUSTER_PAD < b[1]
                    or b[3] + _CLUSTER_PAD < a[1]
                )
                if not disjoint:
                    a = [min(a[0], b[0]), min(a[1], b[1]),
                         max(a[2], b[2]), max(a[3], b[3])]
                    rects.pop(i)
                    changed = True
                    i = 0
                else:
                    i += 1
            out.append(a)
        rects = out
    return out


def _native(document, xref, smask):
    '''Возвращает нативное изображение (с прозрачностью на белом) в PNG.'''
    try:
        pix = fitz.Pixmap(document, xref)
        if pix.n - pix.alpha >= 4:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        mode = 'RGBA' if pix.alpha else ('L' if pix.n == 1 else 'RGB')
        image = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
        alpha = image.getchannel('A') if mode == 'RGBA' else None
        image = image.convert('RGB')
        if smask:
            mask = fitz.Pixmap(document, smask)
            alpha = Image.frombytes(
                'L', (mask.width, mask.height), mask.samples)
            if alpha.size != image.size:
                alpha = alpha.resize(image.size)
        if alpha is not None:
            white = Image.new('RGB', image.size, (255, 255, 255))
            white.paste(image, (0, 0), alpha)
            image = white
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()
    except Exception:
        return None


def _page_candidates(page):
    '''Собирает растровые кандидаты рисунков с нативными пикселями.'''
    rotation = page.rotation_matrix
    width = page.rect.width
    height = page.rect.height
    document = page.parent
    candidates = []
    for image in page.get_images(full=True):
        for rect in page.get_image_rects(image[0]):
            box = _norm(rect, rotation, width, height)
            w = box[2] - box[0]
            h = box[3] - box[1]
            if _RASTER_MIN <= w <= _MAX_SPAN and _RASTER_MIN <= h <= _MAX_SPAN:
                candidates.append({
                    'box': box,
                    'image': _native(document, image[0], image[1]),
                })
    return candidates


def _page_strokes(page):
    '''Возвращает нормированные рамки векторных штрихов страницы.'''
    rotation = page.rotation_matrix
    width = page.rect.width
    height = page.rect.height
    strokes = []
    for drawing in page.get_drawings():
        box = _norm(drawing['rect'], rotation, width, height)
        w = box[2] - box[0]
        h = box[3] - box[1]
        if w > _MAX_SPAN or h > _MAX_SPAN:
            continue
        if w < _NOISE and h < _NOISE:
            continue
        strokes.append(box)
    return strokes


def _cluster_near(seed, strokes):
    '''Кластеризует штрихи у seed и возвращает рамку крупнейшего рисунка.'''
    left = seed[0] - _SEED_EXPAND
    top = seed[1] - _SEED_EXPAND
    right = seed[2] + _SEED_EXPAND
    bottom = seed[3] + _SEED_EXPAND
    inside = []
    for s in strokes:
        cx = (s[0] + s[2]) / 2
        cy = (s[1] + s[3]) / 2
        if left <= cx <= right and top <= cy <= bottom:
            inside.append(s)
    strokes_2d = [
        s for s in inside
        if s[2] - s[0] >= _STROKE_2D and s[3] - s[1] >= _STROKE_2D
    ]
    if not strokes_2d:
        return None
    best = max(
        _clusters(strokes_2d),
        key=lambda c: (c[2] - c[0]) * (c[3] - c[1]),
    )
    x0, y0, x1, y1 = best
    for s in inside:
        cx = (s[0] + s[2]) / 2
        cy = (s[1] + s[3]) / 2
        if x0 - _EXPAND_PAD <= cx <= x1 + _EXPAND_PAD and \
                y0 - _EXPAND_PAD <= cy <= y1 + _EXPAND_PAD:
            x0, y0, x1, y1 = min(x0, s[0]), min(y0, s[1]), \
                max(x1, s[2]), max(y1, s[3])
    w = x1 - x0
    h = y1 - y0
    if w < _MIN_FIGURE or h < _MIN_FIGURE:
        return None
    if w > _MAX_FIGURE or h > _MAX_FIGURE:
        return None
    return [x0, y0, x1, y1]


def _expand_box(box, strokes):
    '''Расширяет рамку ближайшими штрихами вокруг неё.'''
    x0, y0, x1, y1 = box
    for s in strokes:
        cx = (s[0] + s[2]) / 2
        cy = (s[1] + s[3]) / 2
        if x0 - _EXPAND_PAD <= cx <= x1 + _EXPAND_PAD and \
                y0 - _EXPAND_PAD <= cy <= y1 + _EXPAND_PAD:
            x0, y0, x1, y1 = min(x0, s[0]), min(y0, s[1]), \
                max(x1, s[2]), max(y1, s[3])
    return [x0, y0, x1, y1]


def _vector_candidates(strokes):
    '''Собирает рамки рисунков из кластеров и крупных одиночных штрихов.'''
    strokes_2d = [
        s for s in strokes
        if s[2] - s[0] >= _STROKE_2D and s[3] - s[1] >= _STROKE_2D
    ]
    boxes = []
    for cluster in _clusters(strokes_2d):
        boxes.append(_expand_box(cluster, strokes))
    for s in strokes_2d:
        if _MIN_FIGURE <= s[2] - s[0] <= _MAX_FIGURE and \
                _MIN_FIGURE <= s[3] - s[1] <= _MAX_FIGURE:
            boxes.append(_expand_box(list(s), strokes))
    result = []
    for box in sorted(boxes, key=lambda b: -(b[2] - b[0]) * (b[3] - b[1])):
        w = box[2] - box[0]
        h = box[3] - box[1]
        if (w < _MIN_FIGURE or h < _MIN_FIGURE
                or w > _MAX_FIGURE or h > _MAX_FIGURE):
            continue
        if any(_overlap(box, kept) > 0.5 for kept in result):
            continue
        result.append(box)
    return result


def _page_words(page):
    '''Возвращает нормированные рамки слов текста на странице.'''
    rotation = page.rotation_matrix
    width = page.rect.width
    height = page.rect.height
    words = []
    for word in page.get_text('words'):
        words.append(_norm(fitz.Rect(word[:4]), rotation, width, height))
    return words


def extract_page_figures(pdf_path):
    '''Возвращает по страницам рамки-кандидаты рисунков и слова текста.'''
    document = fitz.open(pdf_path)
    pages = []
    for page in document:
        pages.append({
            'candidates': _page_candidates(page),
            'strokes': _page_strokes(page),
            'words': _page_words(page),
        })
    document.close()
    return pages


def _gap(a, b):
    '''Возвращает зазор между двумя рамками (0 при пересечении).'''
    dx = max(0.0, a[0] - b[2], b[0] - a[2])
    dy = max(0.0, a[1] - b[3], b[1] - a[3])
    return (dx * dx + dy * dy) ** 0.5


def _overlap(a, b):
    '''Возвращает долю пересечения относительно меньшей рамки.'''
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    if inter <= 0:
        return 0.0
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return inter / smaller if smaller > 0 else 0.0


def _word_count(box, words):
    '''Считает слова текста, чьи центры попадают внутрь рамки.'''
    count = 0
    for word in words:
        cx = (word[0] + word[2]) / 2
        cy = (word[1] + word[3]) / 2
        if box[0] <= cx <= box[2] and box[1] <= cy <= box[3]:
            count += 1
    return count


def _stroke_hits(box, strokes):
    '''Считает 2D-штрихи, чьи центры попадают внутрь рамки.'''
    count = 0
    for s in strokes:
        if s[2] - s[0] < _STROKE_2D or s[3] - s[1] < _STROKE_2D:
            continue
        cx = (s[0] + s[2]) / 2
        cy = (s[1] + s[3]) / 2
        if box[0] <= cx <= box[2] and box[1] <= cy <= box[3]:
            count += 1
    return count


def _is_figure_candidate(candidate, strokes, words):
    '''Отличает рисунок/график от обведённого рамкой текста.'''
    if candidate.get('image'):
        return True
    box = candidate['box']
    hits = _stroke_hits(box, strokes)
    if hits >= _MIN_STROKES:
        return True
    return hits >= 1 and _word_count(box, words) == 0


def _center_distance(a, b):
    '''Возвращает расстояние между центрами двух рамок.'''
    ax, ay = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
    bx, by = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _hungarian(cost):
    '''Решает задачу о назначениях (минимум суммы) для квадратной матрицы.'''
    n = len(cost)
    inf = float('inf')
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [inf] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = inf
            j1 = -1
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    assignment = [-1] * n
    for j in range(1, n + 1):
        if p[j] > 0:
            assignment[p[j] - 1] = j - 1
    return assignment


def _candidate_pool(page):
    '''Объединяет растровые и векторные кандидаты без дублей одной фигуры.'''
    raster = [
        {'box': c['box'], 'image': c.get('image')}
        for c in (page.get('candidates') or [])
    ]
    pool = list(raster)
    for box in _vector_candidates(page.get('strokes') or []):
        if any(_overlap(box, r['box']) > 0.5 for r in raster):
            continue
        pool.append({'box': box, 'image': None})
    return pool


def _same_column(box, region):
    '''Лежат ли кандидат и задача в одной колонке (по стороне от 0.5).'''
    cx = (box[0] + box[2]) / 2
    rcx = (region[0] + region[2]) / 2
    return (cx < 0.5) == (rcx < 0.5)


def _vertical_overlap(box, region):
    '''Доля вертикального перекрытия рамки-кандидата с задачей (0..1).'''
    inter = max(0.0, min(box[3], region[3]) - max(box[1], region[1]))
    height = box[3] - box[1]
    return inter / height if height > 0 else 0.0


def _assign_by_region(result, regions, pool):
    '''Привязывает кандидаты к задачам по вертикали в той же колонке.'''
    if not regions or not pool:
        return
    used = [item['box'] for item in result if item]
    def _area(candidate):
        box = candidate['box']
        return (box[2] - box[0]) * (box[3] - box[1])

    ordered = sorted(pool, key=_area, reverse=True)
    for candidate in ordered:
        box = candidate['box']
        if box[2] - box[0] < _MIN_FIGURE or box[3] - box[1] < _MIN_FIGURE:
            continue
        if any(_overlap(box, taken) > 0.3 for taken in used):
            continue
        best_index = None
        best_overlap = 0.0
        for index, region in enumerate(regions):
            if index >= len(result) or result[index] is not None or not region:
                continue
            if not _same_column(box, region):
                continue
            overlap = _vertical_overlap(box, region)
            if overlap > best_overlap:
                best_overlap = overlap
                best_index = index
        if best_index is not None and best_overlap > 0:
            result[best_index] = {
                'box': list(box),
                'image': candidate.get('image'),
            }
            used.append(box)


def assign_figures(seeds, page, regions=None):
    '''Распределяет рамки рисунков по задачам без повторного использования.'''
    result = [None] * len(seeds)
    normalized = []
    for index, seed in enumerate(seeds):
        if seed and len(seed) == 4:
            x0, x1 = sorted((seed[0], seed[2]))
            y0, y1 = sorted((seed[1], seed[3]))
            normalized.append((index, [x0, y0, x1, y1]))
    if not page:
        for index, seed in normalized:
            result[index] = {'box': seed, 'image': None}
        return result
    words = page.get('words') or []
    strokes = page.get('strokes') or []
    pool = [
        candidate for candidate in _candidate_pool(page)
        if _word_count(candidate['box'], words) <= _MAX_WORDS
        and _is_figure_candidate(candidate, strokes, words)
    ]
    if normalized and pool:
        big = 100.0
        size = max(len(normalized), len(pool))
        cost = [[big] * size for _ in range(size)]
        for row, (index, seed) in enumerate(normalized):
            for ci, candidate in enumerate(pool):
                if _gap(seed, candidate['box']) <= _MATCH_GAP:
                    cost[row][ci] = _center_distance(seed, candidate['box'])
        assignment = _hungarian(cost)
        for row, (index, seed) in enumerate(normalized):
            ci = assignment[row]
            if ci < len(pool) and cost[row][ci] < big:
                candidate = pool[ci]
                result[index] = {
                    'box': list(candidate['box']),
                    'image': candidate.get('image'),
                }
    for index, seed in normalized:
        if result[index] is not None:
            continue
        box = _cluster_near(seed, strokes)
        if box is None or _word_count(box, words) > _MAX_WORDS:
            continue
        if any(other is not None and _overlap(box, other['box']) > 0.5
               for other in result):
            continue
        result[index] = {'box': box, 'image': None}
    _assign_by_region(result, regions, pool)
    return result
