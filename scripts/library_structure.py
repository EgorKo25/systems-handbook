"""Original learning map with publication numbers following its reading order.

Availability is a property of the built reading copy, not of this work queue.
No private course URLs, lesson text, progress or deployment settings belong here.
"""
from html import escape
from pathlib import Path
import json
import re
from scripts.publication import PUBLISHED


SCHEMA = 1
BASE_SLUGS = frozenset(row['slug'] for row in PUBLISHED if row['build'] != 'managed')

GROUPS = (
    dict(id='foundations', title='Машина, оболочка и сеть',
         description='Сначала разберитесь, как исполняется программа, где живут её данные и каким путём она общается с другими машинами.',
         volumes=('computer-architecture', 'operating-systems', 'linux', 'bash', 'networks')),
    dict(id='software', title='Код и исполняемая программа',
         description='Сохраните историю изменения, получите проверяемый бинарный файл и поймите границы контейнерного окружения.',
         volumes=('git', 'go', 'docker')),
    dict(id='data', title='Данные и хранение',
         description='От транзакции и изменения схемы — к кэшу, документам и распределённому хранению. Выбирайте ветку под свою задачу.',
         volumes=('postgres', 'flyway', 'cache', 'mongodb', 's3', 'minio', 'ceph')),
    dict(id='delivery', title='Качество, артефакты и поставка',
         description='Отделите проверку исходников, хранение результата и исполнение конвейера. Jenkins и GitLab можно изучать как два самостоятельных пути.',
         volumes=('sonarqube', 'nexus', 'artifactory', 'jenkins', 'gitlab')),
    dict(id='infrastructure', title='Инфраструктура и секреты',
         description='Опишите ресурсы, настройте уже созданные машины и управляйте доступом без секретов в исходном коде.',
         volumes=('terraform', 'ansible', 'vault')),
    dict(id='observability', title='Наблюдение и измерение',
         description='Получите измерения до масштабирования: от сбора временных рядов и запросов к ним до объяснимых панелей.',
         volumes=('prometheus', 'grafana')),
    dict(id='orchestration', title='Оркестрация и управление выпуском',
         description='Переходите сюда после устройства Linux, сети и контейнеров: управляйте жизненным циклом приложения и проверяйте согласование состояния.',
         volumes=('kubernetes', 'helm', 'argocd')),
    dict(id='practice', title='Сквозной практикум',
         description='Открывайте параллельно основным книгам после первых глав Linux и Bash. Один учебный мир сохраняет настройки, данные и последствия ваших решений.',
         volumes=('practicum',)),
)


def _book(title, status, prerequisites, scope, blurb=None):
    return dict(title=title, status=status, prerequisites=tuple(prerequisites),
                scope=scope, **({'blurb': blurb} if blurb else {}))


BOOKS = {
    'computer-architecture': _book('Архитектура компьютера', 'released', (),
        'Биты, инструкции, процессор, память, устройства и аппаратная защита.',
        'Сигнал и байт → инструкция → процессор и память → устройства → загрузка машины.'),
    'operating-systems': _book('Операционные системы', 'released', ('computer-architecture',),
        'Ядро, исполнение программ, управление памятью, согласование и ввод-вывод.',
        'Аппаратные возможности → процесс и системный вызов → память и файлы → согласование и защита.'),
    'linux': _book('Устройство Linux', 'released', ('operating-systems',),
        'Процессор, ядро, процессы, память, файлы, устройства и службы.',
        'Команда процессора → системный вызов → процесс и память → файлы и устройства → работающая служба.'),
    'bash': _book('Bash', 'released', ('linux',),
        'Разбор команд, аргументы, потоки, процессы и надёжные сценарии.',
        'Исходный текст → разбор оболочкой → аргументы и дескрипторы → процессы → воспроизводимый сценарий.'),
    'networks': _book('Сети', 'released', (),
        'Сигнал, кадр, пакет, транспорт, приложения и измерение пути.',
        'Байты и заголовки → тракт отправки и приёма → протоколы → топология → измерения.'),
    'git': _book('Git', 'released', ('bash',),
        'Объекты, история, совместная работа, доверие и восстановление.'),
    'go': _book('Go', 'released', ('linux', 'bash', 'git'),
        'Модули, компилятор, линковка, исполнение и измерение программы.'),
    'docker': _book('Docker', 'authoring', ('linux', 'bash', 'networks'),
        'Получение и установка, runtime, образы, сборка, сеть, данные и эксплуатация.'),
    'postgres': _book('PostgreSQL', 'released', ('linux', 'bash', 'networks'),
        'Установка, SQL, устройство СУБД, доступ, устойчивость и эксплуатация.',
        'SQL и протокол → каталоги и план → страницы и MVCC → WAL и устойчивость → восстановление.'),
    'flyway': _book('Flyway', 'planned', ('postgres', 'git'),
        'Установка, история миграций, изменение схемы, совместимость и восстановление.'),
    'cache': _book('Кэш и базы в памяти', 'released', ('postgres',),
        'Польза кэша, согласованность, Redis, Memcached, память и отказы.',
        'Причины внедрения → расчёт пользы → свежесть и память → Redis и Memcached → измерения и отказы.'),
    'mongodb': _book('MongoDB', 'planned', ('linux', 'bash', 'networks'),
        'Установка, модель документов, индексы, транзакции, репликация и обслуживание.'),
    's3': _book('S3 и объектное хранение', 'planned', ('networks',),
        'Модель объектов и API S3, адресация, подпись запроса, доступ и семантика операций.'),
    'minio': _book('MinIO', 'planned', ('linux', 'bash', 's3'),
        'Установка сервера, диски, политики, отказ, проверка восстановления и обновление.'),
    'ceph': _book('Ceph', 'planned', ('linux', 'bash', 'networks'),
        'RADOS, размещение и восстановление; отдельные пути блоков, файлов и объектов.'),
    'sonarqube': _book('SonarQube', 'authoring', ('git', 'go', 'linux', 'networks'),
        'Установка, анализаторы, правила, результаты анализа, пороги качества и обслуживание.'),
    'nexus': _book('Nexus Repository', 'authoring', ('linux', 'bash', 'networks'),
        'Установка репозитория артефактов, форматы, прокси, права, обслуживание и восстановление.'),
    'artifactory': _book('JFrog Artifactory', 'planned', ('linux', 'bash', 'networks'),
        'Установка, хранение артефактов, метаданные, продвижение выпуска и эксплуатация.'),
    'jenkins': _book('Jenkins', 'released', ('git', 'go', 'linux', 'bash', 'networks'),
        'Установка, плагины, агенты, Pipeline, доверие, очереди и восстановление.'),
    'gitlab': _book('GitLab', 'released', ('git', 'go', 'linux', 'bash', 'networks'),
        'Сервер совместной работы, Runner, граф CI, выпуск и эксплуатация платформы.'),
    'terraform': _book('Terraform', 'authoring', ('git', 'linux', 'bash', 'networks'),
        'Установка, провайдеры, план, state, блокировки, дрейф и жизненный цикл ресурсов.'),
    'ansible': _book('Ansible', 'authoring', ('git', 'linux', 'bash', 'networks'),
        'Установка, SSH, inventory, модули, роли, повторное применение и секреты.'),
    'vault': _book('Vault', 'planned', ('linux', 'bash', 'networks'),
        'Установка, инициализация, политики, аутентификация, аренды, PKI и восстановление.'),
    'prometheus': _book('Prometheus', 'authoring', ('linux', 'bash', 'networks'),
        'Установка, сбор, метки, хранение, PromQL, правила и стоимость наблюдения.'),
    'grafana': _book('Grafana', 'planned', ('prometheus',),
        'Установка, источники, запросы, панели, доступ и воспроизводимое управление.'),
    'kubernetes': _book('Kubernetes', 'authoring', ('linux', 'bash', 'networks', 'docker'),
        'Получение дистрибутива и установка кластера, API, контроллеры, сеть, данные, безопасность и отказы.'),
    'helm': _book('Helm', 'authoring', ('kubernetes', 'git'),
        'Установка, chart, шаблоны, values, зависимости, выпуск, откат и проверка изменений.'),
    'argocd': _book('Argo CD', 'planned', ('kubernetes', 'helm', 'git'),
        'Установка, подключение репозитория, согласование, права, дрейф и восстановление.'),
    'practicum': _book('Практикум', 'released', ('linux', 'bash'),
        'Заявки с ограничениями доступа, проверяемый результат и продолжение работы в том же мире.'),
}

# These are paths through the books, not extra empty books or a copied syllabus.
THREADS = (
    dict(id='release', title='От изменения до выпуска',
         description='История → проверенная сборка → анализ → артефакт → конвейер → выпуск и возврат. Настройки и исходники остаются под контролем версий.',
         volumes=('git', 'go', 'sonarqube', 'nexus', 'artifactory', 'jenkins', 'gitlab', 'docker', 'practicum')),
    dict(id='recovery', title='Данные и восстановление',
         description='Разбирайте резервирование там, где известны формат данных и точка согласованности. Копия файла, дамп БД и снимок диска имеют разные гарантии.',
         volumes=('linux', 'postgres', 'flyway', 'mongodb', 'cache', 's3', 'minio', 'ceph', 'practicum')),
    dict(id='architecture', title='Распределённая система',
         description='Сеть, границы служб, балансировка, тайм-ауты, повторения и согласованность связывают механизмы отдельных технологий. Размер кластера выбирается после измерений.',
         volumes=('networks', 'go', 'postgres', 'cache', 'docker', 'kubernetes', 'practicum')),
    dict(id='operations', title='Наблюдение и решение о ресурсах',
         description='Журналы, метрики, очереди, стоимость и оповещения появляются в каждом эксплуатируемом сервисе; отдельные инструменты углубляют сбор и анализ.',
         volumes=('linux', 'go', 'postgres', 'cache', 'prometheus', 'grafana', 'practicum')),
    dict(id='infrastructure', title='Воспроизводимая среда и доверие',
         description='Разделяйте создание ресурсов, настройку ОС, доставку приложения и выдачу полномочий. Облачные примеры объясняются через эти границы, а не через одну панель управления.',
         volumes=('networks', 'linux', 'git', 'terraform', 'ansible', 'vault', 'kubernetes', 'practicum')),
)

STATUS_LABELS = {'available': 'Можно читать', 'authoring': 'В работе',
                 'planned': 'В очереди', 'unavailable': 'Нет в этой копии'}


def validate_structure():
    ordered = [slug for group in GROUPS for slug in group['volumes']]
    if len(ordered) != len(set(ordered)) or set(ordered) != set(BOOKS):
        raise ValueError('Each technology must occur in exactly one library group')
    group_ids = [group['id'] for group in GROUPS]
    if len(set(group_ids)) != len(group_ids):
        raise ValueError('Duplicate library group ID')
    positions = {slug: i for i, slug in enumerate(ordered)}
    for slug, book in BOOKS.items():
        if not re.fullmatch(r'[a-z][a-z0-9-]*', slug):
            raise ValueError('Unsafe technology slug: '+slug)
        if book['status'] not in {'released', 'authoring', 'planned'}:
            raise ValueError('Unknown work status: '+slug)
        for prerequisite in book['prerequisites']:
            if prerequisite not in positions or positions[prerequisite] >= positions[slug]:
                raise ValueError('Prerequisite must precede '+slug+': '+prerequisite)
    for thread in THREADS:
        if set(thread['volumes']) - set(BOOKS):
            raise ValueError('Unknown book in learning thread '+thread['id'])
    return tuple(ordered)


RECOMMENDED_ORDER = validate_structure()


def reading_map(root, stats, configs):
    """Resolve links only to built, registered books with substantive statistics."""
    root = Path(root)
    unknown = set(configs) - set(BOOKS)
    if unknown:
        raise ValueError('Add new volumes to scripts/library_structure.py: '+', '.join(sorted(unknown)))
    books = {}
    for slug in RECOMMENDED_ORDER:
        meta, cfg, row = BOOKS[slug], configs.get(slug, {}), stats.get(slug, {})
        registered = slug in BASE_SLUGS or slug in configs
        complete_stats = (type(row.get('chapters')) is int and row['chapters'] > 1 and
                          type(row.get('words')) is int and row['words'] > 0 and
                          type(row.get('terms')) is int and row['terms'] >= 0 and
                          isinstance(row.get('volume'), str) and
                          re.fullmatch(r'[IVXLCDM]+', row['volume']))
        available = bool(registered and complete_stats and (root/slug/'index.html').is_file())
        if available and cfg.get('volume', row['volume']) != row['volume']:
            raise ValueError('Publication number differs between CONFIG and stats: '+slug)
        status = 'available' if available else ('unavailable' if meta['status'] == 'released' else meta['status'])
        books[slug] = dict(slug=slug, title=cfg.get('short', meta['title']),
                           scope=meta['scope'], prerequisites=list(meta['prerequisites']),
                           status=status, work_status=meta['status'],
                           href=slug+'/index.html' if available else None,
                           publication_volume=row['volume'] if available else None,
                           stats={key: row[key] for key in ('chapters', 'words', 'terms')} if available else None,
                           blurb=cfg.get('blurb', meta.get('blurb', meta['scope'])))
    return dict(schema=SCHEMA, order=list(RECOMMENDED_ORDER),
                order_note='Номера идут по порядку доступных томов в библиотеке. Книги в очереди номера пока не получают; соседние ветки можно изучать независимо.',
                practice_note='Практикум можно начать после первых глав Linux и Bash и продолжать вместе с изучаемой технологией.',
                groups=[{**group, 'volumes': list(group['volumes'])} for group in GROUPS],
                books=books, threads=[{**thread, 'volumes': list(thread['volumes'])} for thread in THREADS],
                deferred=[dict(id='sql-depth', title='Большое расширение SQL', status='deferred',
                               note='Отложено. Действующий материал SQL остаётся в томе PostgreSQL; новая углублённая редакция ещё не подготовлена.')])


STYLE = '''<style id="library-structure-style">
.library-overview{margin:28px 0 38px;padding:20px 22px;border:1px solid var(--home-line);border-radius:16px;background:var(--home-paper)}
.library-overview p{margin:0 0 12px}.library-overview p:last-child{margin-bottom:0}
.library-guide{margin-top:12px}.library-guide>summary{cursor:pointer;font:600 14px/1.5 system-ui;padding:10px 0;min-height:44px;color:var(--home-accent)}
.library-guide[open]>summary{margin-bottom:12px}.library-guide .small{color:var(--home-muted)}
.library-group-nav{display:flex;flex-wrap:wrap;gap:9px;margin:18px 0 0;padding:0;list-style:none}
.library-group-nav a{display:block;padding:8px 12px;border:1px solid var(--home-line);border-radius:12px;text-decoration:none;font:600 13px/1.4 system-ui;color:var(--home-text);min-height:38px}
.library-group-nav a:hover,.library-group-nav a:focus-visible{background:var(--home-soft);color:var(--home-accent)}
.library-shelf{margin:0 0 48px;scroll-margin-top:20px}.library-shelf-heading{display:flex;align-items:baseline;gap:14px;margin-bottom:8px}
.library-shelf-number{font:700 13px/1.4 system-ui;color:var(--home-accent);flex-shrink:0}.library-shelf h2{font-size:27px;line-height:1.25;margin:0}
.library-shelf-description{max-width:850px;margin:10px 0 20px;color:var(--home-muted);font-size:16px}
.library-shelf .grid{margin:22px 0}.library-shelf .volume h3{font-size:29px;line-height:1.25;letter-spacing:-.02em;margin:9px 0}
.library-volume-prerequisites{display:block;color:var(--home-muted);font:12px/1.5 system-ui;margin:0 0 16px}
.library-queue{list-style:none;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 24px;margin:20px 0 0;padding:0}
.library-queue li{padding:14px 0;border-top:1px solid var(--home-line);min-width:0}.library-queue-title{display:flex;align-items:baseline;justify-content:space-between;gap:12px}
.library-queue strong{font-size:16px}.library-status{font:600 11px/1.4 system-ui;white-space:nowrap;color:var(--home-muted);background:var(--home-soft);border-radius:6px;padding:3px 6px}
.library-queue p{font-size:14px;line-height:1.55;color:var(--home-muted);margin:7px 0 0}
.library-threads{margin-bottom:28px}.library-threads h2{font-size:22px}.library-threads details+details{border-top:1px solid var(--home-line)}
.library-threads summary{cursor:pointer;font-weight:650}.library-threads p{font-size:15px}.library-thread-links{display:flex;flex-wrap:wrap;gap:8px 14px;margin:12px 0 18px;font-size:14px}
.library-thread-links span{color:var(--home-muted)}.library-deferred{border-top:1px solid var(--home-line);padding-top:14px}
@media(max-width:750px){.library-overview{padding:18px;border-radius:18px}.library-group-nav{gap:8px}.library-group-nav a{padding:11px 12px;min-height:44px}.library-shelf{margin-bottom:40px}.library-shelf h2{font-size:24px}.library-shelf-heading{gap:11px}.library-shelf .volume h3{font-size:28px}.library-queue{grid-template-columns:minmax(0,1fr);gap:0}.library-shelf-description{font-size:15px}.library-queue-title{flex-wrap:wrap;gap:7px}.library-status{font-size:11px}.library-thread-links a{min-height:36px;padding:5px 0}}
@media print{.library-group-nav{display:none}.library-shelf{break-inside:auto}.library-queue{display:block}.library-status{background:transparent}.library-overview{break-inside:avoid}}
</style>'''


def _plural(number, forms):
    remainder = number % 100
    return forms[2] if 11 <= remainder <= 14 else forms[0] if number % 10 == 1 else forms[1] if 2 <= number % 10 <= 4 else forms[2]


def _number(number):
    return format(number, ',').replace(',', '\u202f')


def render_shelves(route):
    """Semantic HTML and embedded JSON work without JavaScript or internet."""
    books = route['books']
    counts = {status: sum(book['status'] == status for book in books.values()) for status in STATUS_LABELS}
    overview = ('<aside class="library-overview" aria-label="Маршрут по библиотеке">'
                '<p><strong>Можно читать: '+str(counts['available'])+' '+_plural(counts['available'], ('том', 'тома', 'томов'))+
                '</strong> · в работе: '+str(counts['authoring'])+' · в очереди: '+str(counts['planned'])+'</p>'
                '<details class="library-guide"><summary>Разделы и порядок чтения</summary>'
                '<p class="small">'+escape(route['order_note'])+'</p>'
                '<p class="small">'+escape(route['practice_note'])+'</p>'
                '<ul class="library-group-nav">'+''.join(
                    '<li><a href="#library-'+group['id']+'">'+escape(group['title'])+'</a></li>' for group in route['groups'])+'</ul></details></aside>')
    sections = []
    for index, group in enumerate(route['groups'], 1):
        ready, pending = [], []
        for slug in group['volumes']:
            book = books[slug]
            prerequisites = ', '.join(books[other]['title'] for other in book['prerequisites'])
            if book['status'] == 'available':
                row = book['stats']
                ready.append('<a class="volume" href="'+escape(book['href'], quote=True)+'" data-volume="'+slug+'">'
                    '<div class="tag">Том '+escape(book['publication_volume'])+'</div><h3>'+escape(book['title'])+'</h3>'
                    '<p>'+escape(book['blurb'])+'</p>'+
                    ('<span class="library-volume-prerequisites">Опора: '+escape(prerequisites)+'</span>' if prerequisites else '')+
                    '<div class="counts">'+str(row['chapters'])+' '+_plural(row['chapters'], ('глава', 'главы', 'глав'))+' · '+_number(row['words'])+' слов · словарь: '+str(row['terms'])+'</div>'
                    '<span class="open">Открыть том →</span></a>')
            else:
                pending.append('<li data-planned-volume="'+slug+'"><div class="library-queue-title"><strong>'+escape(book['title'])+'</strong>'
                    '<span class="library-status">'+STATUS_LABELS[book['status']]+'</span></div><p>'+escape(book['scope'])+'</p></li>')
        sections.append('<section class="library-shelf" id="library-'+group['id']+'" aria-labelledby="library-'+group['id']+'-title">'
            '<div class="library-shelf-heading"><span class="library-shelf-number" aria-hidden="true">'+str(index).zfill(2)+'</span><h2 id="library-'+group['id']+'-title">'+escape(group['title'])+'</h2></div>'
            '<p class="library-shelf-description">'+escape(group['description'])+'</p>'+
            ('<div class="grid">'+''.join(ready)+'</div>' if ready else '')+
            ('<ul class="library-queue" aria-label="Следующие самостоятельные тома">'+''.join(pending)+'</ul>' if pending else '')+'</section>')
    threads = []
    for thread in route['threads']:
        labels = []
        for slug in thread['volumes']:
            book = books[slug]
            labels.append('<a href="'+escape(book['href'], quote=True)+'">'+escape(book['title'])+'</a>' if book['href'] else '<span>'+escape(book['title'])+' · '+STATUS_LABELS[book['status']].lower()+'</span>')
        threads.append('<details><summary>'+escape(thread['title'])+'</summary><p>'+escape(thread['description'])+'</p><div class="library-thread-links">'+''.join(labels)+'</div></details>')
    deferred = route['deferred'][0]
    threads_section = '<section class="notes library-threads"><h2>Связи между книгами</h2><p class="small">Каждая технология получает собственный том. Общие задачи проходят через несколько книг; установка, настройка и проверка своего экземпляра предшествуют его дальнейшей эксплуатации.</p>'+''.join(threads)+'<p class="small library-deferred"><strong>'+escape(deferred['title'])+'.</strong> '+escape(deferred['note'])+'</p></section>'
    data = json.dumps(route, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    return '<!--library-structure:start--><div id="library-shelves">'+overview+''.join(sections)+threads_section+'</div><script type="application/json" id="library-route-data">'+data+'</script><!--library-structure:end-->'
