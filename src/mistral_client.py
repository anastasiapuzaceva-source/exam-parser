'''Тонкий клиент над REST API чат-комплишенов Mistral.'''

import base64
import time
from pathlib import Path

import requests

from . import config


class MistralError(RuntimeError):
    '''Исключение при ошибочном ответе от Mistral API.'''

_last_request = [0.0]


def _throttle():
    '''Пауза, чтобы запросы не превышали лимит частоты API.'''
    elapsed = time.monotonic() - _last_request[0]
    if elapsed < config.REQUEST_INTERVAL:
        time.sleep(config.REQUEST_INTERVAL - elapsed)
    _last_request[0] = time.monotonic()


def _headers():
    '''Возвращает заголовки авторизации для запроса к API.'''
    return {
        'Authorization': f'Bearer {config.MISTRAL_API_KEY}',
        'Content-Type': 'application/json',
    }


def encode_image(path):
    '''Возвращает data URI (base64 PNG) для изображения по пути.'''
    data = Path(path).read_bytes()
    b64 = base64.b64encode(data).decode('ascii')
    return f'data:image/png;base64,{b64}'


def chat(messages, model, response_format=None, temperature=0,
         max_retries=None):
    '''Вызывает чат-комплишен и возвращает текст ответа модели.'''
    max_retries = max_retries or config.MAX_RETRIES
    payload = {
        'model': model,
        'messages': messages,
        'temperature': temperature,
    }
    if response_format is not None:
        payload['response_format'] = response_format
    url = f'{config.MISTRAL_BASE_URL}/chat/completions'
    last_error = None
    for attempt in range(max_retries):
        _throttle()
        try:
            response = requests.post(
                url,
                headers=_headers(),
                json=payload,
                timeout=config.REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as error:
            last_error = str(error)
            time.sleep(min(60, 4 * 2 ** attempt))
            continue
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        last_error = f'{response.status_code}: {response.text[:300]}'
        if response.status_code in (429, 500, 502, 503):
            time.sleep(min(60, 4 * 2 ** attempt))
            continue
        break
    raise MistralError(last_error)
