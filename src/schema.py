'''JSON-схемы структурированных ответов LLM.'''

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
                        'только в одинарных $...$, без $$...$$.'
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
