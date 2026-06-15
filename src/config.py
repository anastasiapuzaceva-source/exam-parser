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

VISION_MODEL = 'mistral-medium-latest'
SOLVER_MODEL = 'mistral-large-latest'

RENDER_DPI = 200
REQUEST_TIMEOUT = 180
REQUEST_INTERVAL = 2.0
MAX_RETRIES = 6
