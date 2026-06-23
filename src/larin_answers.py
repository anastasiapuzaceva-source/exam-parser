'''Ответы с сайта Ларина: часть 1 (1–12) из JS, часть 2 из картинки.'''

import re
import tempfile
from pathlib import Path

import requests

from . import config
from .paddle_parser import recognize_answer_table
from .textfmt import clean_number

_ANSWERS_URL = 'https://alexlarin.net/ege/{year}/{stem}.js'
_IMAGE_URL = 'https://alexlarin.net/ege/{year}/{stem}.png'
_PAGE_URL = 'https://alexlarin.net/ege/{year}/{stem}.html'

_STEM_RE = re.compile(r'^trvar\d+$', re.IGNORECASE)
_PACKED_RE = re.compile(
    r"\}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\)", re.DOTALL
)
_ASSIGN_RE = re.compile(
    r'getElementById\(\s*["\']T(\d+)["\']\s*\)\.value\s*=\s*"([^"]*)"'
)
_DIGITS = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

_cache = {}
_image_cache = {}


def _base(number, radix):
    '''Представляет число в системе счисления ``radix`` (как ``toString``).'''
    if radix > len(_DIGITS):
        raise ValueError(f'unsupported packer radix {radix}')
    if number == 0:
        return '0'
    digits = ''
    while number > 0:
        digits = _DIGITS[number % radix] + digits
        number //= radix
    return digits


def _decode(raw):
    '''Декодирует байты скрипта (страницы Ларина — в windows-1251/utf-16).'''
    for encoding in ('utf-16', 'utf-16-le', 'windows-1251', 'utf-8'):
        try:
            text = raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
        if 'eval' in text and 'function' in text:
            return text
    return raw.decode('windows-1251', 'ignore')


def _unpack(source):
    '''Распаковывает Dean Edwards packer; иначе возвращает исходник.'''
    match = _PACKED_RE.search(source)
    if not match:
        return source
    payload = match.group(1)
    radix = int(match.group(2))
    count = int(match.group(3))
    words = match.group(4).split('|')
    code = payload
    for index in range(count - 1, -1, -1):
        if index < len(words) and words[index]:
            token = re.escape(_base(index, radix))
            word = words[index]
            code = re.sub(r'\b' + token + r'\b', lambda _m, w=word: w, code)
    return code


def fetch_answers(variant_stem):
    '''Возвращает ``{номер_задания: ответ}`` для части 1 варианта.'''
    stem = (variant_stem or '').strip()
    if not _STEM_RE.match(stem):
        return {}
    if stem in _cache:
        return _cache[stem]
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': _PAGE_URL.format(year=config.LARIN_YEAR, stem=stem),
    }
    try:
        response = requests.get(
            _ANSWERS_URL.format(year=config.LARIN_YEAR, stem=stem),
            headers=headers,
            timeout=config.REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        _cache[stem] = {}
        return {}
    if response.status_code != 200:
        _cache[stem] = {}
        return {}
    answers = {}
    try:
        code = _unpack(_decode(response.content))
        for num, value in _ASSIGN_RE.findall(code):
            cleaned = clean_number(value)
            if cleaned:
                answers[int(num)] = cleaned
    except Exception as error:
        print(f'[larin] unpack error for {stem}: {error}')
        answers = {}
    _cache[stem] = answers
    return answers


def fetch_part2_answers(variant_stem):
    '''Возвращает ``{номер_задания: ответ}`` части 2 из картинки варианта.'''
    stem = (variant_stem or '').strip()
    if not _STEM_RE.match(stem):
        return {}
    if stem in _image_cache:
        return _image_cache[stem]
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': _PAGE_URL.format(year=config.LARIN_YEAR, stem=stem),
    }
    try:
        response = requests.get(
            _IMAGE_URL.format(year=config.LARIN_YEAR, stem=stem),
            headers=headers,
            timeout=config.REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        _image_cache[stem] = {}
        return {}
    if response.status_code != 200:
        _image_cache[stem] = {}
        return {}
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as handle:
        handle.write(response.content)
        tmp_path = handle.name
    try:
        answers = recognize_answer_table(tmp_path)
    except Exception as error:
        print(f'[larin] part2 recognize error for {stem}: {error}')
        answers = {}
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    _image_cache[stem] = answers
    return answers
