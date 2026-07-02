# Exam Parser

Парсер листов ЕГЭ по математике (PDF) в Excel.
Из каждой задачи извлекаются текст условия в HTML-разметке (формулы в LaTeX
`$...$`, перечисления списком `<ul><li>`), чертёж (вырезается в отдельный файл),
а также генерируется развёрнутое решение. Ответы берутся с сайта Ларина:
1–12 — из упакованного `trvarNNN.js`, 13–19 — распознаются из картинки
`trvarNNN.png`. Решение задач генерирует решатель.

## Запуск

PaddleOCR требует Python 3.10–3.12 и ставится в **отдельное** окружение
`.venv-paddle` (основной `.venv` может быть на 3.14, где PaddleOCR не
поддерживается):

```bash
python3.12 -m venv .venv-paddle
.venv-paddle/bin/pip install -r requirements-paddle.txt
```

Дальше запускать можно **обычным `python main.py`** — скрипт сам подхватит
интерпретатор `.venv-paddle` с PaddleOCR:

```bash
# ключ решателя в .env (MISTRAL_API_KEY=...); парсинг — локально:
python main.py input/trvar506.pdf     # один вариант
python main.py input/                 # вся папка
python main.py                        # папка input/ по умолчанию
# PADDLE_USE_GPU=1 — считать на GPU (если хватает VRAM); по умолчанию CPU.
```

## Настройки (переменные окружения)

Кладутся в `.env` или передаются перед командой. Все, кроме ключа, опциональны.

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `MISTRAL_API_KEY` | — | Ключ Mistral для решателя и классификатора (обязателен). |
| `SOLVER_BASE_URL` | адрес Mistral | Базовый URL OpenAI-совместимого API для решателя — чтобы подставить другого провайдера вместо Mistral. |
| `SOLVER_API_KEY` | `MISTRAL_API_KEY` | Ключ для `SOLVER_BASE_URL`, если он отличается от Mistral. |
| `CLASSIFIER_BASE_URL` | адрес Mistral | Базовый URL OpenAI-совместимого API для классификатора. |
| `CLASSIFIER_API_KEY` | `MISTRAL_API_KEY` | Ключ для `CLASSIFIER_BASE_URL`, если он отличается от Mistral. |
| `VISION_MODEL` | — (пусто) | VLM для транскрипции условий со страницы (например `meta-llama/llama-4-scout-17b-16e-instruct` на Groq). Пусто — VLM выключен, парсинг полностью локальный (PaddleOCR); при сбое VLM тоже откат на PaddleOCR. |
| `VISION_BASE_URL` | адрес Mistral | Базовый URL OpenAI-совместимого API для VLM. |
| `VISION_API_KEY` | `MISTRAL_API_KEY` | Ключ для `VISION_BASE_URL`. |
| `SOLVER_MODEL` | `mistral-large-latest` | Модель решателя. |
| `CLASSIFIER_MODEL` | `mistral-large-latest` | Модель классификатора задач. |
| `SOLVER_ATTEMPTS` | `3` | Сколько раз перерешивать при несовпадении ответа с эталоном Ларина (1-я попытка вслепую, далее — с подсказкой). |
| `SOLVER_WORKERS` | `3` | Сколько задач решать параллельно. Снизьте при рейт-лимите (429), повысьте для скорости. |
| `RATE_LIMIT_CIRCUIT` | `6` | Сколько 429 подряд считать исчерпанным лимитом: после этого решатель быстро отдаёт заглушки (прогон не виснет, ответы с сайта всё равно пишутся). |
| `PADDLE_USE_GPU` | `0` | `1` — считать PaddleOCR на GPU, иначе CPU. |
| `PADDLE_MAX_SIDE` | `1100` | Лимит длинной стороны страницы для инференса PaddleOCR (защита от нехватки памяти). Меньше — меньше RAM: при нехватке памяти ставьте `900`. |
| `PADDLE_MAX_TASK` | `19` | Число заданий в варианте (профиль — 19, база — 21). |
| `LARIN_YEAR` | `2026` | Год сборника Ларина в URL ответов части 1. |

## Автор

GitHub: [Anastasiia Puzacheva](https://github.com/anastasiapuzaceva-source)
