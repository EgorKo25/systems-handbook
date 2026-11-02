"""Original definitions and command cards. No subprocesses or network on import."""
GLOSSARY = [
    ('HTTP', 'Hypertext Transfer Protocol — протокол запросов/ответов. Для scrape важны URL, статус, заголовки Content-Type/Accept и тело ответа.'),
    ('TCP', 'Transmission Control Protocol — транспорт соединения с адресами и портами. Открытый порт не доказывает HTTP/readiness и корректный scrape.'),
    ('DNS', 'Domain Name System — система разрешения имён. Правильное имя в конфигурации ещё должно разрешаться из сетевой области scraper.'),
    ('TLS', 'Transport Layer Security — защищённый канал с проверкой сертификата/имени и выбранным доверием. Отключение проверки не доказывает происхождение endpoint.'),
    ('YAML', 'Текстовый формат структурированных данных. Парсер конфигурации превращает его в настройки; отступы и типы имеют значение.'),
    ('JSON', 'Текстовый формат объектов, массивов и скаляров; используется HTTP API и file discovery. Успех разбора JSON не доказывает бизнес-смысл значений.'),
    ('CPU', 'Central processing unit — центральный процессор. CPU seconds/s выражают среднее число занятых ядер, а не автоматически процент всей машины.'),
    ('RAM', 'Random-access memory — оперативная память. Head, Go heap, query working set и файловый кэш расходуют её по-разному.'),
    ('GC', 'Garbage collection — сборка мусора в Go. Частота/паузы и CPU зависят от выделений, живых объектов и настроек runtime.'),
    ('I/O', 'Input/output — ввод-вывод. Пропускная способность и задержка диска/сети не являются взаимозаменяемыми показателями.'),
    ('systemd', 'Менеджер служб Linux. Unit задаёт пользователя, команду, перезапуск и ограничения доступа, но не заменяет проверку данных приложения.'),
    ('Endpoint', 'Адресованный HTTP-путь сервиса, например /metrics. Доступность одного endpoint не доказывает исправность всей бизнес-функции.'),
    ('Fixture', 'Фиксированный набор входных данных и ожидаемых результатов для воспроизводимого теста. Не является реальным сетевым измерением.'),
    ('Toolchain', 'Набор инструментов языка: компилятор, линковщик и вспомогательные команды выбранной версии. Версия модуля и версия toolchain различаются.'),
    ('Prometheus', 'Сервер сбора метрик, локальная база временных рядов и система вычисления PromQL/rules. Один экземпляр хранит собственные данные и не является распределённой TSDB.'),
    ('PromQL', 'Prometheus Query Language — функциональный язык вычислений над временными рядами. Тип, labels, время и единицы каждого подвыражения определяют смысл результата.'),
    ('Metric', 'Метрика — величина с именем, единицей и определённым договором измерения. Число без описанного события или состояния не становится полезной метрикой.'),
    ('Sample', 'Образец: timestamp плюс float либо структурированное native histogram значение. Он относится к одной series, а не ко всем строкам HTTP-ответа.'),
    ('Timestamp', 'Временная отметка образца. Время события, чтения состояния, получения HTTP и query evaluation могут различаться.'),
    ('Label', 'Метка ключ→строковое значение, участвующая в идентичности series. Изменение любой метки создаёт другую идентичность.'),
    ('Time series', 'Временной ряд: имя метрики и полный набор labels плюс последовательность samples. Порядок labels в тексте не меняет ряд.'),
    ('Cardinality', 'Кардинальность — число различных series в выбранной области/интервале. Это отдельная стоимость от числа samples на одну series.'),
    ('Churn', 'Сменяемость идентичностей series: создание и исчезновение рядов во времени. Высокий churn нагружает head/index/WAL даже при стабильном числе активных targets.'),
    ('Pull', 'Модель сбора, в которой Prometheus инициирует HTTP-запрос к источнику. Это направление запроса, а не гарантия доступности источника.'),
    ('Scrape', 'Одна попытка опроса target, разбора exposition и записи samples с служебными метриками попытки.'),
    ('Target', 'Конкретный endpoint сбора с адресом, labels и параметрами HTTP. Наличие в discovery не означает успешный scrape.'),
    ('Job', 'Именованная группа целей с общим способом сбора. Label job полезна для группировки, но не тождественна процессу ОС.'),
    ('Instance', 'Метка экземпляра цели, обычно адрес endpoint после relabeling. Её изменение создаёт новые series.'),
    ('Exporter', 'Программа или endpoint, преобразующий состояние наблюдаемой системы в exposition метрик. Успех HTTP exporter не всегда означает свежесть его внешнего источника.'),
    ('Exposition', 'Сериализованное представление метрик для HTTP scrape. Формат, Content-Type, типы и экранирование должны соответствовать согласованному протоколу.'),
    ('OpenMetrics', 'Стандарт представления метрик с собственными правилами формата. Его текстовый вариант отличается от старого Prometheus text, в том числе завершающим EOF.'),
    ('Service discovery', 'Обнаружение кандидатов targets. Оно предоставляет адреса/метаданные и не выполняет само по себе проверку готовности endpoint.'),
    ('Relabeling', 'Преобразование labels кандидата до scrape. Может изменить адрес запроса, скопировать метаданные или исключить цель.'),
    ('Metric relabeling', 'Преобразование labels/samples после разбора scrape и до ingestion. Не экономит уже переданные байты или работу exporter.'),
    ('Staleness', 'Устаревание series: механизм прекращения участия прежних samples в instant selection после stale marker. Не означает numeric zero.'),
    ('Lookback delta', 'Допустимая глубина поиска предыдущего sample instant selector. Не является ни scrape interval, ни шириной rate окна.'),
    ('TSDB', 'Time series database — база временных рядов. Локальный Prometheus хранит head, WAL и immutable blocks, а не одну текстовую таблицу метрик.'),
    ('Head', 'Изменяемая область последних данных TSDB: series, postings, текущие и mmap chunks. Не равна только Go heap и не является готовым block.'),
    ('WAL', 'Write-ahead log — журнал упреждающей записи для восстановления последних данных. Не является копией на независимом устройстве или гарантией fsync каждого sample.'),
    ('Chunk', 'Сжатая последовательность samples одной series. Текущий chunk и chunk внутри закрытого блока имеют разные жизненные циклы.'),
    ('Postings', 'Индексные списки series refs для пар label=value. Их пересечения помогают выбрать series перед чтением chunks.'),
    ('Series ref', 'Внутренняя числовая ссылка TSDB на series. Это ускорение поиска/журнала, а не постоянный публичный идентификатор.'),
    ('mmap', 'Memory mapping — отображение файлов в адресное пространство процесса. Отображённые страницы используют память/кэш и не исчезают из стоимости хранения.'),
    ('Immutable block', 'Завершённый TSDB block с chunks, index и metadata, который не дописывается как head. Compaction создаёт новые блоки.'),
    ('Compaction', 'Фоновое уплотнение и объединение TSDB blocks. Потребляет CPU/I/O и временное место, а не только экономит диск.'),
    ('Retention', 'Политика удержания истории по времени и/или размеру. Удаление целых подходящих blocks не даёт точной посекундной границы каталога.'),
    ('Tombstone', 'Запись логического удаления временного интервала series. Физическое удаление chunks может происходить позже.'),
    ('Checkpoint', 'Сохранение нужной части WAL перед отсечением покрытых сегментов; уменьшает объём последующего replay.'),
    ('Replay', 'Повторное чтение журнала для восстановления head после запуска. Продолжительность зависит от объёма состояния и ресурсов.'),
    ('Counter', 'Накопительный счётчик событий/объёма, который растёт кроме сброса жизненного цикла. Float sample не хранит этот тип, поэтому смысл должен соблюдать автор запроса.'),
    ('Gauge', 'Текущее значение состояния, способное расти и уменьшаться без reset. Его нельзя автоматически трактовать как counter.'),
    ('Summary', 'Клиентское распределение с sum/count и при настройке целевыми quantiles. Квантили разных экземпляров нельзя усреднять для общего квантиля.'),
    ('Classic histogram', 'Набор float series cumulative buckets с label le, а также sum/count. Один набор labels порождает несколько series.'),
    ('Native histogram', 'Структурированный sample распределения с count/sum/buckets и схемой. Один ряд не означает стоимость одного float sample.'),
    ('Bucket', 'Корзина распределения. Classic bucket cumulative: включает все наблюдения до верхней границы, а не только интервал между соседними границами.'),
    ('Quantile', 'Квантиль — порог значения для выбранной доли распределения. Оценка histogram зависит от интерполяции внутри buckets и числа наблюдений.'),
    ('Scalar', 'Числовой тип PromQL без labels. Отличается от одноэлементного instant vector.'),
    ('Instant vector', 'Набор series с одним выбранным sample на series при одном evaluation timestamp.'),
    ('Range vector', 'Набор series с samples в окне (T−W,T]. Это тип данных выражения, а не синоним range query API.'),
    ('Step', 'Шаг сетки вычислений range query. Не меняет scrape interval и не создаёт недостающих исходных измерений.'),
    ('Rate', 'Оценка counter-прироста в секунду с обработкой наблюдаемых resets и экстраполяцией по правилам движка.'),
    ('Increase', 'Оценка прироста counter на полное окно; равна rate, умноженному на длительность окна в секундах, для обычной семантики.'),
    ('Irate', 'Оценка скорости по последним двум пригодным samples в окне с исправлением reset. Не средняя скорость по всему окну.'),
    ('Reset', 'Наблюдаемый сброс counter, для float обычно падение значения. Сброс между scrapes, скрытый последующим ростом, обнаружить нельзя.'),
    ('Extrapolation', 'Экстраполяция: оценка поведения на краях окна вне фактического span samples. Не доказательство событий в пропущенном интервале.'),
    ('Vector matching', 'Сопоставление элементов двух vectors по ключу labels для binary operation. Позиция строки ответа значения не имеет.'),
    ('on', 'Modifier PromQL, ограничивающий ключ сопоставления указанными labels. Не добавляет отсутствующие labels автоматически.'),
    ('ignoring', 'Modifier, исключающий перечисленные labels из ключа сопоставления.'),
    ('group_left', 'Разрешение many-to-one arithmetic/comparison matching, где множество слева и уникальная сторона справа.'),
    ('group_right', 'Разрешение one-to-many arithmetic/comparison matching, где уникальная сторона слева и множество справа.'),
    ('NaN', 'Not a number — особое float значение. Отличается от отсутствующей series и внутреннего stale marker.'),
    ('Offset', 'Сдвиг времени selector относительно evaluation timestamp. Не изменяет физические timestamps хранения.'),
    ('Subquery', 'Вычисление instant expression на собственной временной сетке с возвращением range vector результатов.'),
    ('Recording rule', 'Периодическое вычисление выражения с записью результата в новые series. Добавляет фиксированный interval, данные и версионный контракт.'),
    ('Alerting rule', 'Периодическое выражение, элементы которого образуют alert instances с labels и состояниями pending/firing.'),
    ('Pending', 'Состояние алерта, когда условие присутствует, но длительность for ещё не выполнена.'),
    ('Firing', 'Активное состояние алерта после выполнения for либо немедленно без for. Не доказывает доставку уведомления человеку.'),
    ('keep_firing_for', 'Удержание уже firing алерта после исчезновения условия на evaluation. Не превращает missing data в успешное наблюдение.'),
    ('SLI', 'Service level indicator — строго определённый показатель качества услуги с eligible/good событиями или временными условиями.'),
    ('SLO', 'Service level objective — цель для SLI на заданном окне с осмысленным бюджетом ошибок.'),
    ('Burn rate', 'Отношение текущей доли плохих событий к допустимой доле SLO. Безразмерная скорость расхода бюджета относительно целевого режима.'),
    ('HA', 'High availability — высокая доступность. Пара самостоятельных Prometheus не создаёт общую реплицируемую локальную TSDB.'),
    ('Deduplication', 'Устранение дублирующих наблюдений HA-реплик внешней поддерживающей системой по её договору labels/времени.'),
    ('Remote write', 'Передача samples во внешнее совместимое хранилище через очереди и протокол. Local query availability не равна remote delivery.'),
    ('Remote read', 'Чтение storage данных из внешней системы. Само по себе не переносит выполнение всего PromQL на receiver.'),
    ('Backpressure', 'Обратное давление: downstream не успевает, очередь/задержка растут и ограничивают upstream.'),
    ('Snapshot', 'Согласованный снимок данных. На том же устройстве не заменяет независимый резерв и проверенное восстановление.'),
    ('RSS', 'Resident set size — резидентные страницы процесса. Это не только Go heap и не точный объём всех обещанных виртуальных mappings.'),
    ('Instrumentation', 'Код, который связывает реальные события/состояние с обновлением метрик; требует ограниченных labels, единиц и понимания стоимости.'),
    ('Registry', 'Реестр collectors с согласованными descriptors. Его создают и регистрируют при инициализации, а не на каждый запрос.'),
    ('Collector', 'Компонент client library, который собирает metric families. Собственный collector обязан сам обеспечить безопасность общего состояния.'),
    ('LTS', 'Long-term support — ветка с более длительным периодом выбранных исправлений. Не обещает поддержку любой экспериментальной возможности.'),
    ('SHA-256', 'Криптографический хеш содержимого. Сравнение проверяет байты относительно ожидаемой суммы, происхождение самой суммы требует доверенного источника.'),
]

DOC = 'https://prometheus.io/docs/prometheus/3.13/command-line/'


def flag(name, action, when, example, result):
    return dict(flag=name, action=action, when=when, example=example, result=result)


def command(name, purpose, syntax, chapter, flags, situations):
    url = DOC + ('prometheus/' if name == 'prometheus' else 'promtool/')
    if name == 'prometheus':
        for item in flags:
            item['example'] = '\n'.join(
                line + ' --config.file=config/prometheus.yml --storage.tsdb.path=data'
                if line.startswith('prometheus ') and '--config.file' not in line and '--version' not in line
                else line for line in item['example'].splitlines())
    return dict(name=name, aliases=[], purpose=purpose, syntax=syntax,
                chapter=chapter, volume='prometheus', source=url,
                sources=[dict(title='CLI Prometheus 3.13, сверено --help 3.13.5', url=url)],
                flags=flags, situations=situations)


COMMANDS = [
    command('prometheus', 'Запустить свой сервер с явными путями и loopback-сокетом. Пишет TSDB; один data directory принадлежит одному процессу.', 'prometheus [ФЛАГИ]', 'prom-01-install', [
        flag('--version', 'Вывести версию и завершиться.', 'Зафиксировать реально запускаемые байты.', 'prometheus --version', 'Версия/сборка; сервер не запускается.'),
        flag('--config.file', 'Выбрать YAML конфигурацию.', 'Не полагаться на рабочий каталог.', 'prometheus --config.file=config/prometheus.yml --storage.tsdb.path=data --web.listen-address=127.0.0.1:9090', 'Читается выбранный файл; ошибка YAML/пути прекращает запуск.'),
        flag('--storage.tsdb.path', 'Выбрать постоянный каталог данных.', 'Перезапуск с прежней историей.', 'prometheus --config.file=config/prometheus.yml --storage.tsdb.path=data --web.listen-address=127.0.0.1:9090', 'WAL/head/blocks остаются в data. Новый путь создаёт другую историю; два процесса конфликтуют по lock.'),
        flag('--web.listen-address', 'Выбрать интерфейс и TCP-порт HTTP.', 'Оставить личный стенд на loopback.', 'prometheus --web.listen-address=127.0.0.1:9090\nprometheus --web.listen-address=0.0.0.0:9090', 'Первый сокет локален; второй слушает сетевые интерфейсы. Сравнивают в VM отдельно, порт не должен быть занят.'),
        flag('--storage.tsdb.retention.time', 'Выбрать срок удержания истории.', 'Ограничить рост при известном ingestion.', 'prometheus --storage.tsdb.retention.time=7d --web.listen-address=127.0.0.1:9090\nprometheus --storage.tsdb.retention.time=30d --web.listen-address=127.0.0.1:9090', 'Второй профиль держит больше истории при прочих равных; удаление blocks не посекундное, нужен запас диска.'),
        flag('--web.enable-lifecycle', 'Разрешить HTTP lifecycle endpoints.', 'Осознанный reload через POST /-/reload.', 'prometheus --web.listen-address=127.0.0.1:9090\nprometheus --web.listen-address=127.0.0.1:9090 --web.enable-lifecycle', 'Без флага HTTP reload отключён, с ним разрешён; SIGHUP остаётся отдельным путём.'),
        flag('--web.enable-admin-api', 'Включить административные TSDB endpoints.', 'Только подготовленный snapshot в собственном стенде.', 'prometheus --web.listen-address=127.0.0.1:9090\nprometheus --web.listen-address=127.0.0.1:9090 --web.enable-admin-api', 'Без флага snapshot API отказывает; с ним доступны также изменяющие данные действия. Флаг не создаёт резерв автоматически.'),
        flag('--query.lookback-delta', 'Ограничить поиск последнего sample instant selector.', 'Контролируемый опыт с редкими samples.', 'prometheus --query.lookback-delta=5m --web.listen-address=127.0.0.1:9090\nprometheus --query.lookback-delta=1m --web.listen-address=127.0.0.1:9090', 'Старый sample может исчезнуть раньше; scrape interval и range selector не меняются.'),
    ], ['Проверить владельца data, свободный порт и конфигурацию до запуска.']),
    command('promtool check config', 'Проверить YAML и связанные файлы без запуска сервера; не проверяет сетевую доступность targets.', 'promtool check config [ФЛАГИ] ФАЙЛ...', 'prom-01-install', [
        flag('--syntax-only', 'Проверять только синтаксис без полной проверки ссылочных файлов.', 'Локализовать ошибку структуры.', 'promtool check config config/prometheus.yml\npromtool check config --syntax-only config/prometheus.yml', 'Полная проверка может найти отсутствующий rules.yml, syntax-only такой проверки не заменяет.'),
        flag('--lint-fatal', 'Сделать lint замечания причиной exit code 3.', 'Автоматическая проверка согласованной политики.', 'promtool check config --lint-fatal config/prometheus.yml', 'Отказ при выбранных lint замечаниях; код не равен сетевому health check.'),
    ], ['Перед reload; при ненулевом коде исправить исходник и повторить.']),
    command('promtool check rules', 'Проверить файлы recording/alert rules синтаксически, не доказав бизнес-смысл.', 'promtool check rules [ФЛАГИ] ФАЙЛ...', 'prom-14-rules', [], ['Проверка перед test rules и reload.']),
    command('promtool test rules', 'Вычислить fixtures настоящим engine без HTTP сервера и сравнить samples/alerts.', 'promtool test rules [ФЛАГИ] TEST.yml...', 'prom-09-counters', [
        flag('--run', 'Выбрать группы tests по regex имени.', 'Изолировать один расчёт.', "promtool test rules fixtures/promql.yml\npromtool test rules --run=counter_reset fixtures/promql.yml", 'Первый запуск выполняет все группы; второй только совпавшие имена. Меньший набор не заменяет финальную полную проверку.'),
        flag('--junit', 'Записать отчёт JUnit XML в указанный файл.', 'Сохранить доказательство для CI.', 'promtool test rules --junit=evidence/promql.xml fixtures/promql.yml', 'Появится/заменится файл отчёта, ненулевой код означает отказ теста/разбора.'),
    ], ['Нужны только закреплённый promtool и локальные fixture files.']),
    command('promtool query instant', 'Выполнить выражение через API своего сервера в один момент.', 'promtool query instant [ФЛАГИ] SERVER EXPR', 'prom-08-time-evaluation', [
        flag('--time', 'Выбрать RFC3339 либо Unix seconds.', 'Воспроизвести результат на одном T.', "promtool query instant --time=2026-11-01T12:00:00Z http://127.0.0.1:9090 'up'", 'Один evaluation timestamp; прошлое время без данных даёт пустой result, а не ошибку установки.'),
    ], ['Сравнить с ручной выборкой и query API.']),
    command('promtool query range', 'Вычислить выражение на сетке времён через API.', 'promtool query range [ФЛАГИ] SERVER EXPR', 'prom-08-time-evaluation', [
        flag('--start', 'Начало сетки RFC3339/Unix seconds.', 'Ограничить исследуемый интервал.', "promtool query range --start=2026-11-01T12:00:00Z --end=2026-11-01T13:00:00Z --step=1m http://127.0.0.1:9090 'up'", 'Выбраны моменты на часе; это не сканирование исходных samples без выражения.'),
        flag('--end', 'Конец сетки.', 'Не включать будущую/другую фазу опыта.', "promtool query range --start=2026-11-01T12:00:00Z --end=2026-11-01T13:00:00Z --step=1m http://127.0.0.1:9090 'up'", 'Конечный момент включён, когда лежит на сетке.'),
        flag('--step', 'Шаг повторных evaluations.', 'Сравнить стоимость и детализацию.', "promtool query range --start=2026-11-01T12:00:00Z --end=2026-11-01T13:00:00Z --step=15s http://127.0.0.1:9090 'up'\npromtool query range --start=2026-11-01T12:00:00Z --end=2026-11-01T13:00:00Z --step=1m http://127.0.0.1:9090 'up'", '241 против61 моментов для этого выровненного часа; исходный scrape interval не изменился.'),
    ], ['Записать выражение, start/end/step и версию для повторяемости.']),
    command('promtool check metrics', 'Разобрать и lint-ить exposition из stdin. Не опрашивает URL самостоятельно.', 'promtool check metrics [ФЛАГИ] < metrics.prom', 'prom-02-model-and-time', [
        flag('--extended', 'Добавить анализ кардинальности.', 'Исследовать сохранённый ответ endpoint.', 'promtool check metrics < metrics.prom\npromtool check metrics --extended < metrics.prom', 'Второй запуск даёт дополнительную сводку; оба анализируют тот же файл, не свежесть источника.'),
    ], ['Сначала сохранить HTTP body, затем анализировать, различая transport error и parser error.']),
    command('promtool check ready', 'Проверить readiness своего Prometheus.', 'promtool check ready [--url=URL]', 'prom-01-install', [
        flag('--url', 'Задать базовый URL сервера.', 'Использовать отдельный loopback-порт копии.', 'promtool check ready --url=http://127.0.0.1:19090', 'Запрос readiness; доступный TCP без ready недостаточен.'),
    ], ['Ожидание восстановления head после запуска.']),
    command('promtool tsdb analyze', 'Анализировать churn/labels/series выбранного закрытого блока на согласованной копии.', 'promtool tsdb analyze [ФЛАГИ] [DB_PATH] [BLOCK_ID]', 'prom-16-capacity-diagnostics', [
        flag('--limit', 'Число элементов в диагностических списках.', 'Сузить либо расширить сводку.', 'promtool tsdb analyze --limit=10 restore-data\npromtool tsdb analyze --limit=40 restore-data', 'Меняется объём вывода; исходные данные не очищаются.'),
        flag('--extended', 'Дополнительный анализ.', 'Исследовать блок подробнее.', 'promtool tsdb analyze --extended restore-data', 'Больше вычисления/вывода; на пустом каталоге без blocks анализ не даст статистику head.'),
        flag('--match', 'Один selector для анализа.', 'Выбрать семью рядов.', "promtool tsdb analyze --match='{__name__=\"lab_requests_total\"}' restore-data", 'Ограничена выборка, а не установлен лимит ingestion.'),
    ], ['Сначала получить snapshot/копию, не удалять WAL по результату анализа.']),
    command('promtool tsdb list', 'Показать закрытые TSDB blocks, временные границы и статистику копии.', 'promtool tsdb list [ФЛАГИ] [DB_PATH]', 'prom-17-backup-upgrade', [], ['Проверить состав snapshot; отсутствие blocks в только начатом сервере не означает отсутствия head samples.']),
]
