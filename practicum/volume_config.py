"""A persistent, personal end-to-end administration practicum."""
CONFIG = dict(
    volume='X', short='Практикум',
    title='Практикум: от своей сети до эксплуатации продукта',
    description='Рабочие заявки, ограничения доступа, диагностика, изменения, выпуск, измерение и восстановление в одном сохраняемом учебном мире.',
    sections=[
        ('Начало работы', ['00-route', 'pc-work-method']),
        ('Получить управление', ['P00-rescue-bootstrap', 'P01-management-ssh', 'P02-bastion-access']),
        ('Построить и исследовать сеть', ['P03-packet-path', 'P04-vlan-routing', 'P22-network-tool-migration', 'P05-dhcp-dns-tls']),
        ('Машина, программа и данные', ['P06-service-socket', 'P07-storage-recovery', 'P08-git-config', 'P09-go-service', 'P10-postgres-access', 'P11-database-recovery', 'P12-cache-effectiveness']),
        ('Измерять и выпускать', ['P13-observability', 'P21-capacity-budget', 'P14-manual-release', 'P15-jenkins-delivery', 'P20-gitlab-platform']),
        ('Воспроизводить и переживать отказы', ['P16-ansible', 'P17-terraform', 'P18-replica-failure', 'P19-kubernetes']),
        ('Справочник', ['99-glossary']),
    ],
    term_modules=['reference'], diagram_modules=['diagrams'], base_terms=[],
    blurb='Рабочая заявка → доступ и сеть → служба и данные → измерение → выпуск → автоматизация и отказы.',
)
