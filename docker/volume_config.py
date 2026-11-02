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
    ], term_modules=['reference'], diagram_modules=['diagrams', 'diagrams_network', 'diagrams_security'], command_modules=['reference'], base_terms=[],
    illustration_links=[{'id': 'docker-durable-counter', 'title': 'Запись счётчика: файл, имя и подтверждение', 'label': 'write · fsync · rename'}, {'id': 'docker-storage-mount-cutaway', 'title': 'Как mount меняет видимые файлы', 'label': '5 состояний'}, {'id': 'goimage09-elf', 'title': 'Исполняемый файл Go внутри образа', 'label': 'разрез ELF64'}, {'id': 'oci10-byte-cutaway', 'title': 'OCI: манифесты, хеши и байты слоёв', 'label': 'разрез объектов'}, {'id': 'docker-recovery-separate-target', 'title': 'Копия и восстановленная ветвь истории', 'label': 'временная шкала'}],
    blurb='Официальная установка → образ и процесс → изоляция, сеть и данные → Go и Compose → измерение, резерв и обновление.',
    revision='1 ноября 2026',
)
