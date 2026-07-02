'''Общая нормализация HTML-текста для условий и решений.'''

import re

_BOLD_RE = re.compile(r'\*\*(.+?)\*\*')
_HEADING_RE = re.compile(r'(?m)^\s{0,3}#{1,6}\s*')
_NUMBER_RE = re.compile(r'-?\d+(?:[.,]\d+)?')

_LATEX_COMMANDS = sorted((
    'frac', 'tfrac', 'dfrac', 'cfrac', 'left', 'right', 'begin', 'end',
    'big', 'Big', 'bigg', 'Bigg', 'binom', 'neq', 'ne', 'nabla', 'notin',
    'not', 'nu', 'times', 'text', 'tanh', 'tan', 'theta', 'tau', 'to',
    'triangle', 'geqslant', 'geq', 'ge', 'leqslant', 'leq', 'le', 'lt',
    'gt', 'cdots', 'cdot', 'sqrt', 'sum', 'prod', 'int', 'lim', 'log',
    'ln', 'lg', 'sin', 'cos', 'tg', 'ctg', 'cot', 'sec', 'csc', 'arcsin',
    'arccos', 'arctan', 'pi', 'alpha', 'beta', 'gamma', 'delta', 'epsilon',
    'varepsilon', 'zeta', 'eta', 'iota', 'kappa', 'lambda', 'mu', 'xi',
    'rho', 'sigma', 'phi', 'varphi', 'chi', 'psi', 'omega', 'Gamma',
    'Delta', 'Theta', 'Lambda', 'Xi', 'Pi', 'Sigma', 'Phi', 'Psi', 'Omega',
    'vec', 'overline', 'underline', 'underbrace', 'infty', 'in', 'cup',
    'cap', 'subseteq', 'subset', 'supset', 'emptyset', 'varnothing',
    'angle', 'degree', 'circ', 'pm', 'mp', 'approx', 'equiv', 'simeq',
    'sim', 'forall', 'exists', 'mathbb', 'mathrm', 'mathsf', 'mathbf',
    'mathit', 'mathcal', 'cases', 'matrix', 'pmatrix', 'bmatrix',
    'vmatrix', 'quad', 'qquad', 'dots', 'ldots', 'hat', 'bar', 'prime',
    'partial', 'perp', 'parallel', 'rightarrow', 'leftarrow', 'Rightarrow',
    'Leftrightarrow', 'leftrightarrow', 'longrightarrow', 'mid', 'div',
), key=len, reverse=True)
_BACKSLASH_RUN_RE = re.compile(r'\\\\|\\([a-zA-Z]+)')
_HEX_DIGITS = set('0123456789abcdefABCDEF')


def _fix_backslash(match):
    '''Решает судьбу одиночного слэша: LaTeX — удвоить, JSON — оставить.'''
    tail = match.group(1)
    if tail is None:
        return match.group(0)
    if tail[0] == 'u':
        rest = match.string[match.start() + 2:match.start() + 6]
        if len(rest) == 4 and set(rest) <= _HEX_DIGITS:
            return match.group(0)
    for command in _LATEX_COMMANDS:
        if tail.startswith(command):
            return '\\\\' + tail
    if tail[0] in 'nt':
        return match.group(0)
    return '\\\\' + tail


def escape_latex_in_json(raw):
    '''Удваивает слэши LaTeX-команд в сыром JSON-ответе модели.'''
    return _BACKSLASH_RUN_RE.sub(_fix_backslash, raw or '')


_CTRL_REPAIRS = [
    (chr({'b': 8, 'f': 12, 'n': 10, 'r': 13, 't': 9}[cmd[0]]) + cmd[1:],
     '\\' + cmd)
    for cmd in _LATEX_COMMANDS
    if cmd[0] in 'bfnrt' and len(cmd) >= 3
]


def restore_control_latex(text):
    '''Возвращает LaTeX-команды, съеденные JSON-escape при разборе.'''
    for broken, fixed in _CTRL_REPAIRS:
        if broken in text:
            text = text.replace(broken, fixed)
    return text


def clean_html(text):
    '''Подчищает разметку: HTML вместо Markdown и одинарные $...$.'''
    text = text or ''
    text = text.replace('$$', '$')
    text = _BOLD_RE.sub(r'<b>\1</b>', text)
    text = _HEADING_RE.sub('', text)
    return text.strip()


def clean_number(text):
    '''Оставляет в строке только число (запятая → точка), иначе исходник.'''
    text = (text or '').replace('$', '').strip()
    match = _NUMBER_RE.search(text)
    if match is None:
        return text
    return match.group(0).replace(',', '.')
