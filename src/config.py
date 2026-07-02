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
SOLVER_BASE_URL = os.getenv('SOLVER_BASE_URL', MISTRAL_BASE_URL)
SOLVER_API_KEY = os.getenv('SOLVER_API_KEY', MISTRAL_API_KEY)
CLASSIFIER_BASE_URL = os.getenv('CLASSIFIER_BASE_URL', MISTRAL_BASE_URL)
CLASSIFIER_API_KEY = os.getenv('CLASSIFIER_API_KEY', MISTRAL_API_KEY)
VISION_BASE_URL = os.getenv('VISION_BASE_URL', MISTRAL_BASE_URL)
VISION_API_KEY = os.getenv('VISION_API_KEY', MISTRAL_API_KEY)
VISION_MODEL = os.getenv('VISION_MODEL', '')  # пусто — VLM выключен
SOLVER_MODEL = os.getenv('SOLVER_MODEL', 'mistral-large-latest')
CLASSIFIER_MODEL = os.getenv('CLASSIFIER_MODEL', 'mistral-large-latest')
SOLVER_TEMPERATURE = float(os.getenv('SOLVER_TEMPERATURE', '0.3'))
SOLVER_MAX_TOKENS = int(os.getenv('SOLVER_MAX_TOKENS', '8192'))
SOLVER_WORKERS = int(os.getenv('SOLVER_WORKERS', '3'))
SOLVER_ATTEMPTS = int(os.getenv('SOLVER_ATTEMPTS', '3'))

PADDLE_LANG = 'ru'
PADDLE_USE_GPU = os.getenv('PADDLE_USE_GPU', '0') == '1'
PADDLE_FORMULA_MODEL = os.getenv('PADDLE_FORMULA_MODEL', 'PP-FormulaNet_plus-L')
PADDLE_MAX_TASK = int(os.getenv('PADDLE_MAX_TASK', '19'))
PADDLE_MAX_SIDE = int(os.getenv('PADDLE_MAX_SIDE', '1100'))
LARIN_YEAR = os.getenv('LARIN_YEAR', '2026')
LARIN_YEAR_MIN = int(os.getenv('LARIN_YEAR_MIN', '2015'))

RENDER_DPI = 300
REQUEST_TIMEOUT = 180
REQUEST_INTERVAL = float(os.getenv('REQUEST_INTERVAL', '1.2'))
MAX_RETRIES = 8
RATE_LIMIT_CIRCUIT = int(os.getenv('RATE_LIMIT_CIRCUIT', '6'))

CATEGORIES_CSV = BASE_DIR / 'data' / 'categories.csv'
ENABLE_CLASSIFY = True
