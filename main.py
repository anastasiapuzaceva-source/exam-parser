'''Точка входа командной строки для пайплайна разбора.'''

import importlib.util
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PADDLE_PYTHON = BASE_DIR / '.venv-paddle' / 'bin' / 'python'


def _ensure_paddle_interpreter():
    '''Перезапускает скрипт интерпретатором .venv-paddle, если paddle нет.'''
    if importlib.util.find_spec('paddleocr') is not None:
        return
    current = Path(sys.executable).resolve()
    if current == PADDLE_PYTHON.resolve():
        sys.exit('paddleocr не установлен в .venv-paddle. '
                 'Установите его: .venv-paddle/bin/pip install paddleocr')
    if not PADDLE_PYTHON.exists():
        sys.exit('Не найден интерпретатор .venv-paddle/bin/python. '
                 'Создайте venv с Python 3.12 и установите paddleocr.')
    os.execv(str(PADDLE_PYTHON), [str(PADDLE_PYTHON), *sys.argv])


def main():
    '''Обрабатывает все файлы из input/ либо указанный файл/папку.'''
    _ensure_paddle_interpreter()
    from src.pipeline import process_file, run_all
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        if target.is_dir():
            run_all(target)
        else:
            process_file(target)
    else:
        run_all()


if __name__ == '__main__':
    main()
