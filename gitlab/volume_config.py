"""Maintained metadata for the independent GitLab volume."""
CONFIG = dict(
    volume='IX',
    title='GitLab: платформа, исполнение CI и эксплуатация',
    short='GitLab',
    description='Установка, состояние GitLab, права, граф CI, Runner, Go-конвейер, хранение и восстановление.',
    sections=[
        ('Начало', ['00-route']),
        ('Платформа и доверие', ['01-platform-and-state', '02-install-and-addresses', '03-identity-and-projects', '04-import-and-review']),
        ('Книга I · Как исполняется CI', ['05-pipeline-compilation', '06-rules-and-events', '07-runners-and-executors', '08-job-process', '09-variables-and-trust', '10-caches-and-artifacts']),
        ('От Go-кода к выпуску', ['11-go-pipeline', '12-reports-and-quality', '13-release-and-environments']),
        ('Эксплуатация', ['14-performance-and-diagnostics', '15-backup-and-upgrade']),
        ('Собственный практикум', ['16-lab']),
        ('Справочник', ['99-glossary']),
    ],
    term_modules=['reference'],
    command_modules=['reference'],
    diagram_modules=['diagrams'],
    base_terms=[],
    blurb='Установка и данные → права → граф CI → Runner и процессы → Go-артефакт → выпуск, измерения и восстановление.',
)
