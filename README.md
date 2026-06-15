# Exam Parser

Парсер листов ЕГЭ по математике (PDF) в Excel с помощью Mistral API.
Из каждой задачи извлекаются текст условия (с формулами в LaTeX),
чертёж (вырезается в отдельный `.png`), а также генерируются решение
и краткий ответ.

## Запуск

```bash
python3 -m venv .venv
source .venv/bin/activate           # На Windows активация: `.venv\Scripts\activate`.
pip install -r requirements.txt
# ключ Mistral берётся из .env (MISTRAL_API_KEY=...)
python main.py                   # все файлы из input/
python main.py path/to/file.pdf  # один файл
python main.py path/to/dir/      # все файлы в папке
```

## Автор

GitHub: [Anastasiia Puzacheva](https://github.com/anastasiapuzaceva-source)