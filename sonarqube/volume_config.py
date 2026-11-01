"""Independent SonarQube volume; source registration is performed by the library."""
CONFIG = dict(
    volume='XII', short='SonarQube',
    title='SonarQube: от установки до доказуемой проверки изменений',
    description='Сервер, сканер, Go-отчёты, политика качества, интеграция CI, наблюдение и восстановление.',
    revision='1 ноября 2026',
    sections=[
        ('Начало', ['00-route']),
        ('Экземпляр и доступ', ['01-model-and-limits', '02-install-and-accept', '03-addresses-security', '04-projects-access']),
        ('Книга I · Как получается результат анализа', ['05-scanner-contract', '06-go-analysis', '07-quality-policy']),
        ('Результат в процессе разработки', ['08-ci-integration', '09-issues-security', '10-plugins-and-ide']),
        ('Эксплуатация и собственный опыт', ['11-performance-diagnostics', '12-backup-upgrade', '13-lab']),
        ('Справочник', ['99-glossary']),
    ],
    base_terms=[], term_modules=['reference'], command_modules=['reference'],
    diagram_modules=['diagrams'],
    blurb='Официальная поставка → собственный экземпляр → область Go-анализа → отчёты и правила → асинхронный допуск → эксплуатация.',
)
