"""Independent Nexus source volume. Provisional volume number: integrator must assign."""
CONFIG = dict(
    volume='XIX',  # TEMPORARY ONLY: integration assigns the final library number.
    title='Nexus Repository: артефакты, Go-модули и сохранение состояния',
    short='Nexus Repository', revision='1 ноября 2026',
    description='Установка CE 3.97.3, metadata и blobs, Go proxy/hosted/group, доверие, выпуски, измерения и восстановление.',
    sections=[
        ('Начало', ['00-route']),
        ('Книга I · Собственный экземпляр', ['01-nexus-install','02-nexus-addresses','03-nexus-state']),
        ('Книга II · Протоколы и артефакты', ['04-nexus-cache','05-nexus-go-protocol','06-nexus-go-client','07-nexus-go-publish','08-nexus-raw','09-nexus-registry']),
        ('Книга III · Доверие и выпуск', ['10-nexus-access','11-nexus-promotion']),
        ('Книга IV · Эксплуатация', ['12-nexus-cleanup','13-nexus-measurement','14-nexus-recovery','15-nexus-upgrade']),
        ('Собственный практикум', ['16-nexus-lab']),
        ('Источники и справочник', ['98-nexus-sources','99-glossary']),
    ],
    term_modules=['reference'], command_modules=['reference'], diagram_modules=['diagrams'], base_terms=[],
    blurb='Проверенная поставка → metadata и байты → Go module proxy → неизменяемый выпуск → доступ, измерения и восстановление.',
)
