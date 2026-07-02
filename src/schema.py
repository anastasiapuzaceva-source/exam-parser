'''JSON-схемы структурированных ответов LLM.'''

PAGE_SCHEMA = {
    'type': 'json_schema',
    'json_schema': {
        'name': 'exam_page',
        'strict': True,
        'schema': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['tasks'],
            'properties': {
                'tasks': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'required': ['task_num', 'condition'],
                        'properties': {
                            'task_num': {'type': 'string'},
                            'condition': {
                                'type': 'string',
                                'description': (
                                    'Условие задачи строго в HTML-тегах '
                                    '(<p>, <br>, <b>, <ul>, <li>) без '
                                    'Markdown; формулы только в одинарных '
                                    '$...$, без $$...$$. Обратные слэши '
                                    'LaTeX-команд удваивай по правилам '
                                    'JSON: \\\\frac, \\\\vec.'
                                ),
                            },
                        },
                    },
                },
            },
        },
    },
}

SOLUTION_SCHEMA = {
    'type': 'json_schema',
    'json_schema': {
        'name': 'task_solution',
        'strict': True,
        'schema': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['solution', 'answer'],
            'properties': {
                'solution': {
                    'type': 'string',
                    'description': (
                        'Пошаговое развёрнутое решение строго в HTML-тегах '
                        '(<p>, <br>, <b>, <ul>, <li>) без Markdown; формулы '
                        'только в одинарных $...$, без $$...$$. Обратные '
                        'слэши LaTeX-команд удваивай по правилам JSON: '
                        '\\\\frac, \\\\left.'
                    ),
                },
                'answer': {
                    'type': 'string',
                    'description': (
                        'Только итоговый ответ — число (целое или конечная '
                        'десятичная дробь) без слов и единиц измерения.'
                    ),
                },
            },
        },
    },
}
