"""Artifactory authorship inputs. XXIV is provisional; integrator assigns final number."""
CONFIG = dict(
    volume='XXIV', short='Artifactory',
    title='Artifactory: от поставки до прослеживаемого выпуска Go',
    description='Редакции, установка, checksum storage, Go и OCI, build-info, права, доставка, резерв и измерение.',
    revision='1 ноября 2026',
    sections=[
        ('Маршрут', ['00-route']),
        ('Книга I · Свой экземпляр', ['artifactory-01-install', 'artifactory-02-runtime', 'artifactory-03-addresses', 'artifactory-11-permissions']),
        ('Книга II · Как имя становится байтами', ['artifactory-04-storage', 'artifactory-05-resolution', 'artifactory-06-go-protocol', 'artifactory-07-go-client']),
        ('Книга III · Выпуск и его доказательства', ['artifactory-08-cli', 'artifactory-09-promotion', 'artifactory-10-oci', 'artifactory-12-ci']),
        ('Книга IV · Сохранность и стоимость', ['artifactory-13-maintenance', 'artifactory-14-recovery', 'artifactory-15-topology', 'artifactory-16-measurement', 'artifactory-17-lab']),
        ('Первоисточники и справочник', ['artifactory-98-sources', '99-glossary']),
    ],
    base_terms=[], term_modules=['reference'], command_modules=['reference'],
    diagram_modules=['diagrams'],
    blurb='Проверенная поставка → свой Router/Access/БД → байты и логические пути → clean Go client → build-info и promotion → независимый резерв.',
)
