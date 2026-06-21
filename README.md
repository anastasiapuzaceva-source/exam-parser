# Exam Parser

Парсер листов ЕГЭ по математике (PDF) в Excel.
Из каждой задачи извлекаются текст условия в HTML-разметке (формулы в LaTeX
`$...$`, перечисления списком `<ul><li>`), чертёж (вырезается в отдельный файл),
а также генерируются решение и краткий ответ. Ответы части 1 (задания 1–12)
подтягиваются с сайта Ларина, остальные считает решатель.

Распознавание страниц можно вести двумя движками (тумблер `PARSER_BACKEND`):
- `mistral` (по умолчанию) — облачный `pixtral` через Mistral API;
- `paddle` — локальный PaddleOCR (PP-StructureV3), без стороннего API.

Решение и ответ задач всегда считает Mistral-решатель.

## Запуск (бэкенд Mistral)

```bash
python3 -m venv .venv
source .venv/bin/activate           # На Windows активация: `.venv\Scripts\activate`.
pip install -r requirements.txt
# ключ Mistral берётся из .env (MISTRAL_API_KEY=...)
python main.py                   # все файлы из input/
python main.py path/to/file.pdf  # один файл
python main.py path/to/dir/      # все файлы в папке
```

## Локальный парсинг (бэкенд PaddleOCR)

PaddleOCR требует Python 3.10–3.12 и ставится в **отдельное** окружение
(основной `.venv` может быть на 3.14, где PaddleOCR не поддерживается):

```bash
python3.12 -m venv .venv-paddle
.venv-paddle/bin/pip install -r requirements-paddle.txt
# распознавание — локально PaddleOCR, решение задач — по-прежнему Mistral:
PARSER_BACKEND=paddle .venv-paddle/bin/python main.py input/trvar506.pdf
# PADDLE_USE_GPU=1 — считать на GPU (если хватает VRAM); по умолчанию CPU.
```

## Настройки (переменные окружения)

Кладутся в `.env` или передаются перед командой. Все, кроме ключа, опциональны.

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `MISTRAL_API_KEY` | — | Ключ Mistral API (обязателен). |
| `PARSER_BACKEND` | `mistral` | Движок распознавания: `mistral` или `paddle`. |
| `PADDLE_USE_GPU` | `0` | `1` — считать PaddleOCR на GPU, иначе CPU. |
| `PADDLE_MAX_TASK` | `19` | Число заданий в варианте (профиль — 19, база — 21). |
| `LARIN_YEAR` | `2026` | Год сборника Ларина в URL ответов части 1. |

## Автор

GitHub: [Anastasiia Puzacheva](https://github.com/anastasiapuzaceva-source)