"""Author-owned Flyway sources. Registration is an editor's explicit step."""
CONFIG = dict(
    volume='XX', short='Flyway',
    title='Flyway: управляемое изменение живой базы данных',
    description='От официального CLI и собственного PostgreSQL до истории миграций, блокировок, совместимых выпусков Go и проверенного восстановления.',
    revision='2 ноября 2026',
    sections=[
        ('Начало', ['00-route']),
        ('Книга I · Инструмент и принятый экземпляр', ['flyway-01-model', 'flyway-02-distribution', 'flyway-03-state', 'flyway-04-first-release']),
        ('Книга II · От файла до зафиксированной истории', ['flyway-05-discovery', 'flyway-06-request-path', 'flyway-07-history', 'flyway-08-configuration', 'flyway-09-validation']),
        ('Книга III · Выпуск при живых данных', ['flyway-10-transactions', 'flyway-11-expand-contract', 'flyway-12-backfill-index', 'flyway-13-concurrency-failure']),
        ('Книга IV · Принятие чужой истории и эксплуатация', ['flyway-14-baseline-repair', 'flyway-15-restore', 'flyway-16-measurement', 'flyway-17-delivery-offline', 'flyway-18-lab']),
        ('Справочник', ['99-glossary']),
    ],
    base_terms=[], term_modules=['reference'], command_modules=['reference'],
    diagram_modules=['diagrams'],
    blurb='Поставка → личный PostgreSQL → SQL и история → блокировки и отказы → совместимый Go-выпуск → восстановление.',
)
