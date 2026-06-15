'''Точка входа командной строки для пайплайна разбора.'''

import sys
from pathlib import Path

from src.pipeline import process_file, run_all


def main():
    '''Обрабатывает все файлы из input/ либо указанный файл/папку.'''
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
