'''Тонкий клиент над OpenAI-совместимым API чат-комплишенов (Mistral).'''

import random
import threading
import time

import requests

from . import config


class LLMError(RuntimeError):
    '''Исключение при ошибочном ответе от LLM API.'''

_last_request = [0.0]
_throttle_lock = threading.Lock()
_rate_lock = threading.Lock()
_consecutive_429 = [0]


def _circuit_open():
    '''Открыт ли предохранитель (слишком много 429-провалов подряд).'''
    with _rate_lock:
        return _consecutive_429[0] >= config.RATE_LIMIT_CIRCUIT


def _note_429():
    with _rate_lock:
        _consecutive_429[0] += 1


def _note_success():
    with _rate_lock:
        _consecutive_429[0] = 0


def _retry_delay(attempt, response=None):
    '''Пауза перед повтором: Retry-After либо экспонента с джиттером.'''
    if response is not None:
        retry_after = response.headers.get('Retry-After')
        if retry_after:
            try:
                return min(60.0, float(retry_after))
            except ValueError:
                pass
    return min(60.0, 4 * 2 ** attempt) + random.uniform(0, 1.0)


def _throttle():
    '''Глобальный лимитер: старты запросов разнесены на REQUEST_INTERVAL.'''
    if config.REQUEST_INTERVAL <= 0:
        return
    with _throttle_lock:
        elapsed = time.monotonic() - _last_request[0]
        wait = config.REQUEST_INTERVAL - elapsed
        if wait > 0:
            time.sleep(wait)
        _last_request[0] = time.monotonic()


def _headers(api_key):
    '''Возвращает заголовки авторизации для запроса к API.'''
    return {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }


def chat(messages, model, response_format=None, temperature=0,
         max_retries=None, base_url=None, api_key=None, max_tokens=None):
    '''Вызывает чат-комплишен и возвращает текст ответа.'''
    max_retries = max_retries or config.MAX_RETRIES
    base_url = base_url or config.MISTRAL_BASE_URL
    api_key = api_key or config.MISTRAL_API_KEY
    payload = {
        'model': model,
        'messages': messages,
        'temperature': temperature,
    }
    if max_tokens:
        payload['max_tokens'] = max_tokens
    if response_format is not None:
        payload['response_format'] = response_format
    url = f'{base_url}/chat/completions'
    last_error = None
    saw_429 = False
    for attempt in range(max_retries):
        if _circuit_open():
            raise LLMError('429: rate limit (предохранитель открыт, пропуск)')
        _throttle()
        try:
            response = requests.post(
                url,
                headers=_headers(api_key),
                json=payload,
                timeout=config.REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as error:
            last_error = str(error)
            time.sleep(_retry_delay(attempt))
            continue
        if response.status_code == 200:
            _note_success()
            return response.json()['choices'][0]['message']['content']
        last_error = f'{response.status_code}: {response.text[:300]}'
        if response.status_code == 429:
            saw_429 = True
            time.sleep(_retry_delay(attempt, response))
            continue
        if response.status_code in (500, 502, 503):
            time.sleep(_retry_delay(attempt, response))
            continue
        break
    if saw_429:
        _note_429()
    raise LLMError(last_error)
