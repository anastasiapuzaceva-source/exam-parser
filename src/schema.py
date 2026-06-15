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
                            'figure_index',
                        ],
                        'properties': {
                            'task_num': {'type': 'string'},
                            'condition': {'type': 'string'},
                            'figure_index': {'type': 'integer'},
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
                'solution': {'type': 'string'},
                'answer': {'type': 'string'},
            },
        },
    },
}
