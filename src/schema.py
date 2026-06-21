'''JSON-схемы структурированных ответов вызовов Mistral.'''

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
                        'required': [
                            'task_num',
                            'condition',
                            'has_figure',
                            'figure_box',
                        ],
                        'properties': {
                            'task_num': {'type': 'string'},
                            'condition': {
                                'type': 'string',
                                'description': (
                                    'Условие задачи строго в HTML-тегах '
                                    '(<p>, <br>, <b>, <ul>, <li>) без '
                                    'Markdown; перечисления — списком '
                                    '<ul><li>; формулы только в одинарных '
                                    '$...$, без $$...$$.'
                                ),
                            },
                            'has_figure': {
                                'type': 'boolean',
                                'description': (
                                    'Есть ли у задачи рисунок, график '
                                    'или чертёж на странице.'
                                ),
                            },
                            'figure_box': {
                                'type': 'array',
                                'items': {'type': 'number'},
                                'description': (
                                    'Рамка рисунка [x0, y0, x1, y1] в '
                                    'долях ширины и высоты страницы '
                                    '(0..1, начало в левом верхнем углу). '
                                    '[0, 0, 0, 0], если рисунка нет.'
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
                        'Пошаговое решение строго в HTML-тегах '
                        '(<p>, <br>, <b>, <ul>, <li>) без Markdown; '
                        'формулы только в одинарных $...$, без $$...$$.'
                    ),
                },
                'answer': {
                    'type': 'string',
                    'description': (
                        'Только число (целое или конечная десятичная '
                        'дробь) без слов и единиц измерения.'
                    ),
                },
            },
        },
    },
}
