"""Original independent Ansible volume; no side effects on import."""
CONFIG = dict(
    volume='XIII',
    title='Ansible: от SSH и одной задачи до управляемого выпуска Go',
    short='Ansible',
    description='Установка, модель исполнения, YAML и Jinja, переменные, роли, безопасность, выпуск, измерения и восстановление.',
    revision='1 ноября 2026',
    sections=[
        ('Начало', ['00-route']),
        ('Книга I · Инструмент и управляемая машина', ['an-01-install', 'an-02-config-inventory', 'an-03-ssh-become', 'an-04-task-engine']),
        ('Книга II · Данные и язык исполнения', ['an-05-yaml', 'an-06-jinja', 'an-07-variables', 'an-08-facts-results', 'an-09-task-control', 'an-10-handlers']),
        ('Книга III · Большая конфигурация', ['an-11-import-include', 'an-12-roles-collections', 'an-13-orchestration', 'an-14-check-diff']),
        ('Книга IV · Доверие, расширение и выпуск', ['an-15-secrets', 'an-16-custom-module', 'an-17-go-release', 'an-18-testing']),
        ('Книга V · Эксплуатация', ['an-19-performance', 'an-20-recovery', 'an-21-lab', 'an-22-sources']),
        ('Справочник', ['99-glossary']),
    ],
    term_modules=['reference'], command_modules=['reference'],
    diagram_modules=['diagrams'], base_terms=[],
    blurb='Версия и SSH → задача и данные → переменные и роли → последовательный выпуск → измерения, отказ и восстановление.',
)
