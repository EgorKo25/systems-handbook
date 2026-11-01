"""Original container volume: maintained sources, no host actions on import."""
CONFIG = dict(
    volume='XI', title='Docker: от образа до работающей и восстанавливаемой системы', short='Docker',
    description='Установка, OCI и слои, BuildKit, изоляция Linux, сеть, данные, Go, Compose, измерения и восстановление.',
    sections=[
        ('Маршрут', ['00-route']),
        ('Получить и понять инструмент', ['01-install-and-state', '02-client-daemon-runtime']),
        ('Книга I · Из чего получается контейнер', ['03-image-oci-layers', '04-buildkit-cache', '05-process-kernel']),
        ('Границы среды', ['06-network-path', '07-security-rootless', '08-volumes-consistency']),
        ('Книга II · Доставить Go-программу', ['09-go-image', '10-distribution-provenance', '11-compose-lifecycle']),
        ('Эксплуатация', ['12-observability', '13-resource-efficiency', '14-backup-recovery', '15-upgrade-diagnostics']),
        ('Продолжаемый стенд', ['16-integrated-lab']),
        ('Справочник', ['99-glossary']),
    ], term_modules=['reference'], diagram_modules=['diagrams'], command_modules=['reference'], base_terms=[],
    blurb='Официальная установка → образ и процесс → изоляция, сеть и данные → Go и Compose → измерение, резерв и обновление.',
    revision='1 ноября 2026',
)
