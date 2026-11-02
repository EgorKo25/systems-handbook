"""Pending integration: coordinator assigns the final volume number."""
CONFIG = dict(
    volume='XVIII',  # Provisional: integrator assigns final library number.
    title='Helm: типы, шаблоны, пакеты и жизненный цикл релиза',
    short='Helm',
    description='Проверенный клиент, Go templates, типы values, зависимости, доверие, установка, обновление и восстановление релиза.',
    sections=[
        ('Начало', ['00-route', '01-helm-install', '02-helm-path', '03-helm-chart']),
        ('Книга I · Данные и язык шаблонов', ['04-helm-values', '05-helm-template-model', '06-helm-scope', '07-helm-helpers', '08-helm-yaml']),
        ('Книга II · Состав и доставка пакета', ['09-helm-dependencies', '10-helm-distribution']),
        ('Книга III · Жизненный цикл релиза', ['11-helm-first-release', '12-helm-upgrade', '13-helm-hooks', '14-helm-recovery', '15-helm-workloads']),
        ('Эксплуатация и собственный практикум', ['16-helm-diagnostics', '17-helm-lab', '18-helm-migration', '19-helm-sources']),
        ('Справочник', ['99-glossary']),
    ],
    term_modules=['reference'],
    command_modules=['reference'],
    diagram_modules=['diagrams'],
    base_terms=[],
    revision='1 ноября 2026',
    blurb='Клиент и доверие → типы и Go templates → пакет и зависимости → история релиза → отказ, измерение и восстановление.',
)
