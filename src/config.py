'''Настройки и общие пути пайплайна разбора экзаменов.'''

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / 'input'
OUTPUT_DIR = BASE_DIR / 'output'

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}

MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY', '')
MISTRAL_BASE_URL = 'https://api.mistral.ai/v1'

VISION_MODEL = 'pixtral-large-latest'
SOLVER_MODEL = 'mistral-large-latest'

PARSER_BACKEND = os.getenv('PARSER_BACKEND', 'mistral')
PADDLE_LANG = 'ru'
PADDLE_USE_GPU = os.getenv('PADDLE_USE_GPU', '0') == '1'
PADDLE_FORMULA_MODEL = 'PP-FormulaNet_plus-M'
PADDLE_MAX_TASK = int(os.getenv('PADDLE_MAX_TASK', '19'))
LARIN_YEAR = os.getenv('LARIN_YEAR', '2026')

RENDER_DPI = 300
REQUEST_TIMEOUT = 180
REQUEST_INTERVAL = 2.0
MAX_RETRIES = 6

CATEGORIES_CSV = BASE_DIR / 'data' / 'categories.csv'
CLASSIFIER_MODEL = 'mistral-large-latest'
ENABLE_CLASSIFY = True
