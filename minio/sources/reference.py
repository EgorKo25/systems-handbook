GLOSSARY = [
    ('MinIO Server', 'Процесс объектного хранения; принимает поддерживаемые S3-запросы и управляет собственным форматом данных.'),
    ('mc', 'Самостоятельный клиент MinIO; его alias и config.json являются клиентским состоянием.'),
    ('Storage endpoint', 'Отдельный путь или сетевой адрес области хранения в серверной топологии. Его независимость от других endpoints нужно проверять физически.'),
    ('Erasure set', 'Закреплённая группа endpoints, между которыми кодируется отдельная версия объекта.'),
    ('Pool', 'Группа ресурсов размещения, содержащая один или несколько erasure sets.'),
    ('Data shard', 'Часть разделённых данных кодированного объекта.'),
    ('Parity shard', 'Математическая избыточность, позволяющая восстановить отсутствующие части; не полная копия объекта.'),
    ('Quorum', 'Минимальное достаточное число согласованных пригодных ответов для конкретной операции.'),
    ('Failure domain', 'Общая причина отказа нескольких ресурсов: диск, узел, питание или другая совместная зависимость.'),
    ('xl.meta', 'Внутреннее представление metadata версий; для небольших объектов может содержать также inline data.'),
    ('Healing', 'Серверное восстановление отсутствующих или повреждённых частей по пригодным данным и metadata; не извлечение объекта из ничего.'),
    ('Alias mc', 'Сохранённое имя клиентского подключения: endpoint, credentials, подпись и режим адресации.'),
]

def flag(label, action, when, example, result):
    return dict(flag=label, action=action, when=when,
                example=example, result=result)

def card(name, purpose, syntax, chapter, source, flags=()):
    return dict(
        name=name, aliases=[], purpose=purpose, syntax=syntax,
        chapter=chapter, volume='minio',
        source=source,
        sources=[dict(title='Закреплённый официальный исходник', url=source)],
        flags=list(flags), situations=[],
    )

COMMANDS = [
    card(
        'minio', 'Запустить выбранную серверную программу или открыть её справку.',
        'minio [ГЛОБАЛЬНЫЕ ОПЦИИ] КОМАНДА',
        'minio-03-workbench',
        'https://raw.githubusercontent.com/minio/minio/RELEASE.2025-10-15T17-29-55Z/cmd/main.go',
        [
            flag(
                '-S КАТАЛОГ / --certs-dir КАТАЛОГ',
                'Выбрать каталог сертификата и закрытого ключа сервера.',
                'До server явно указать подготовленное TLS-состояние.',
                'minio --certs-dir ./tls server --address 127.0.0.1:19000 ./data',
                'Сервер использует public.crt и private.key из ./tls; имя каталога не отключает проверку их пригодности.',
            ),
        ],
    ),
    card(
        'minio server', 'Запустить процесс хранения с заданными endpoints.',
        'minio [ГЛОБАЛЬНЫЕ ОПЦИИ] server [ОПЦИИ SERVER] ENDPOINT...',
        'minio-03-workbench',
        'https://raw.githubusercontent.com/minio/minio/RELEASE.2025-10-15T17-29-55Z/cmd/server-main.go',
        [
            flag('--address АДРЕС:ПОРТ', 'Выбрать listener API.',
                 'Ограничить личный стенд loopback.',
                 'minio server --address 127.0.0.1:19000 ./data',
                 'API слушает только указанный адрес; это не настройка порта браузерного интерфейса.'),
            flag('--console-address АДРЕС:ПОРТ', 'Выбрать listener браузерного интерфейса.',
                 'Зафиксировать отдельный адрес интерфейса.',
                 'minio server --console-address 127.0.0.1:19001 ./data',
                 'Интерфейс получает указанный listener; S3-клиенту нужен API endpoint.'),
        ],
    ),
    card(
        'mc', 'Обратиться к объектному серверу или поддерживаемой локальной цели.',
        'mc [ГЛОБАЛЬНЫЕ ОПЦИИ] КОМАНДА',
        'minio-04-first-object',
        'https://raw.githubusercontent.com/minio/mc/RELEASE.2025-08-13T08-35-41Z/cmd/flags.go',
        [
            flag('-C КАТАЛОГ / --config-dir КАТАЛОГ',
                 'Выбрать отдельное клиентское состояние.',
                 'Не смешивать учебные alias и доверенные CA с другими подключениями.',
                 'mc --config-dir "./state with spaces" alias list',
                 'Клиент читает выбранный config.json; каталог может содержать secrets.'),
            flag('--disable-pager', 'Печатать справку непосредственно в stdout.',
                 'Сохранять help без внутреннего pager.',
                 'mc --disable-pager --help',
                 'Справка доступна напрямую; серверная операция не выполняется.'),
        ],
    ),
    card(
        'mc alias set', 'Создать или заменить сохранённое клиентское подключение.',
        'mc [ГЛОБАЛЬНЫЕ ОПЦИИ] alias set [ОПЦИИ] ИМЯ ENDPOINT [ACCESS_KEY] [SECRET_KEY]',
        'minio-04-first-object',
        'https://raw.githubusercontent.com/minio/mc/RELEASE.2025-08-13T08-35-41Z/cmd/alias-set.go',
        [
            flag('--api ПОДПИСЬ', 'Выбрать явно поддерживаемую схему подписи.',
                 'Закрепить S3v4 для учебного endpoint.',
                 'mc alias set --api S3v4 lab https://127.0.0.1:19000',
                 'Схема указана явно; credentials читаются интерактивно либо из stdin.'),
            flag('--path РЕЖИМ', 'Выбрать path-style режим on, off или auto.',
                 'Использовать bucket в URL path на loopback.',
                 'mc alias set --path on lab https://127.0.0.1:19000',
                 'Bucket передаётся в пути URL; отдельный DNS на bucket не требуется.'),
        ],
    ),
]

MC_SOURCE = (
    'https://raw.githubusercontent.com/minio/mc/'
    'RELEASE.2025-08-13T08-35-41Z/cmd/'
)

_MC_CARDS = [
    card(
        'mc',
        'Клиент выбранной объектной цели. Доступ определяют alias, credentials и серверная policy.',
        'mc [ГЛОБАЛЬНЫЕ ОПЦИИ] КОМАНДА',
        'minio-04-first-object', MC_SOURCE + 'flags.go',
        [
            flag('-h / --help', 'Показать справку.', 'Сверить собственную сборку до серверных действий.',
                 'mc --help', 'Справка не подтверждает доступность сервера.'),
            flag('-C КАТАЛОГ / --config-dir КАТАЛОГ', 'Выбрать клиентское состояние.',
                 'Изолировать alias и CA учебного проекта.',
                 'mc --config-dir "./state with spaces" stat lab/handbook-minio/project/manifest.txt',
                 'Используется выбранный config.json и его certs/CAs.'),
            flag('--disable-pager / --dp', 'Отключить внутренний pager.',
                 'Сохранить help в файл.', 'mc --disable-pager --help',
                 'Вывод доступен непосредственно через stdout.'),
            flag('--json', 'Выбрать структурированный вывод.',
                 'Разбирать разрешённый несекретный результат либо закрытый credential workflow.',
                 'mc --json stat lab/handbook-minio/project/manifest.txt',
                 'Формат меняется; JSON alias/account может содержать secret и не становится публичным автоматически.'),
        ],
    ),
    card(
        'mc alias set',
        'Сохранить или заменить alias. Явное --api может исключить сетевую signature probe.',
        'mc [ГЛОБАЛЬНЫЕ ОПЦИИ] alias set [ОПЦИИ] ИМЯ ENDPOINT [ACCESS_KEY] [SECRET_KEY]',
        'minio-04-first-object', MC_SOURCE + 'alias-set.go',
        [
            flag('--api ПОДПИСЬ', 'Задать S3v4 или S3v2.', 'Закрепить S3v4.',
                 'mc alias set --api S3v4 lab https://127.0.0.1:19000',
                 'При отсутствии credentials в argv читается stdin; успех сохранения не равен успешному PUT.'),
            flag('--path РЕЖИМ', 'Выбрать on, off или auto для bucket addressing.',
                 'Работать с loopback без bucket DNS.',
                 'mc alias set --path on lab https://127.0.0.1:19000',
                 'В on bucket находится в URL path.'),
        ],
    ),
    card(
        'mc mb',
        'Создать bucket либо локальную directory-цель. Для серверного опыта указывается alias/bucket.',
        'mc [ГЛОБАЛЬНЫЕ ОПЦИИ] mb [ОПЦИИ] TARGET [TARGET...]',
        'minio-04-first-object', MC_SOURCE + 'mb-main.go',
        [
            flag('--ignore-existing / -p', 'Не считать уже существующую цель ошибкой.',
                 'Только после независимой проверки её принадлежности и настроек.',
                 'mc mb --ignore-existing lab/handbook-minio',
                 'Не проверяет автоматически versioning, Object Lock и прежние данные.'),
            flag('--region REGION', 'Задать регион создаваемого bucket.',
                 'Закрепить требуемое имя региона.',
                 'mc mb --region us-east-1 lab/handbook-minio',
                 'Создание должно подтвердить сервер; region не выбирает endpoint.'),
            flag('--with-versioning', 'После создания включить versioning.',
                 'Осознанно создать новый versioned bucket.',
                 'mc mb --with-versioning lab/new-study',
                 'Это последовательные действия; ошибка включения не доказывает, что bucket не был создан.'),
        ],
    ),
    card(
        'mc version enable',
        'Включить versioning выбранного bucket. Ранее утраченные данные от этого не появляются.',
        'mc [ГЛОБАЛЬНЫЕ ОПЦИИ] version enable ALIAS/BUCKET',
        'minio-04-first-object', MC_SOURCE + 'version-enable.go',
    ),
    card(
        'mc version info',
        'Прочитать серверную конфигурацию versioning, включая возможные исключения.',
        'mc [ГЛОБАЛЬНЫЕ ОПЦИИ] version info ALIAS/BUCKET',
        'minio-04-first-object', MC_SOURCE + 'version-info.go',
    ),
    card(
        'mc cp',
        'Передать содержимое между явно выбранными source и target. Новый PUT в versioned bucket создаёт версию.',
        'mc [ГЛОБАЛЬНЫЕ ОПЦИИ] cp [ОПЦИИ] SOURCE [SOURCE...] TARGET',
        'minio-04-first-object', MC_SOURCE + 'cp-main.go',
        [
            flag('--version-id ID / --vid ID', 'Выбрать версию источника.',
                 'Копировать известное серверное состояние.',
                 'mc cp --version-id V1 lab/handbook-minio/project/manifest.txt ./new-copy.txt',
                 'ID относится к source; destination version ID не сохраняется автоматически.'),
            flag('--disable-multipart', 'Отключить multipart upload.',
                 'Исследовать небольшой single-PUT опыт.',
                 'mc cp --disable-multipart ./small.txt lab/handbook-minio/project/small.txt',
                 'Меняется способ передачи; это не гарантия отсутствия retries или дубликатов версий.'),
            flag('--attr СПИСОК', 'Передать metadata в формате key=value;key=value.',
                 'Сопоставлять собственное намерение с сохранённой версией.',
                 'mc cp --attr "operation-id=op-01" ./small.txt lab/handbook-minio/project/small.txt',
                 'Metadata не является серверным ключом идемпотентности.'),
        ],
    ),
    card(
        'mc stat',
        'Прочитать metadata объекта или сведения bucket. Наличие metadata не доказывает совпадение тела.',
        'mc [ГЛОБАЛЬНЫЕ ОПЦИИ] stat [ОПЦИИ] TARGET [TARGET...]',
        'minio-04-first-object', MC_SOURCE + 'stat-main.go',
        [
            flag('--version-id ID / --vid ID', 'Выбрать конкретную версию.',
                 'Не подменять результат текущим key.',
                 'mc stat --version-id V1 lab/handbook-minio/project/manifest.txt',
                 'Исследуется выбранная версия; требуется соответствующее право чтения версии.'),
            flag('--no-list', 'Отключить LIST fallback операции stat.',
                 'Исследовать точный object target без перечисления.',
                 'mc stat --no-list lab/handbook-minio/project/manifest.txt',
                 'Отказ object lookup не маскируется успешным списком похожего prefix.'),
        ],
    ),
    card(
        'mc cat',
        'Прочитать тело в stdout. Redirect в новый файл сохраняет отдельную цель для cmp.',
        'mc [ГЛОБАЛЬНЫЕ ОПЦИИ] cat [ОПЦИИ] TARGET',
        'minio-04-first-object', MC_SOURCE + 'cat-main.go',
        [
            flag('--version-id ID / --vid ID', 'Прочитать заданную версию.',
                 'Проверить старые байты под новым current version либо marker.',
                 'mc cat --version-id V1 lab/handbook-minio/project/manifest.txt',
                 'GET выбирает versionId; право GetObjectVersion отличается от GetObject.'),
        ],
    ),
    card(
        'mc ls',
        'Перечислить объекты выбранной цели; список текущих объектов и история версий решают разные задачи.',
        'mc [ГЛОБАЛЬНЫЕ ОПЦИИ] ls [ОПЦИИ] TARGET [TARGET...]',
        'minio-06-versions-and-unknown-put', MC_SOURCE + 'ls-main.go',
        [
            flag('--versions', 'Включить предыдущие версии и markers.',
                 'Исследовать историю key после DELETE.',
                 'mc ls --versions lab/handbook-minio/project/manifest.txt',
                 'Старые версии могут существовать при отсутствии текущего тела.'),
            flag('--recursive / -r', 'Перечислить вложенные prefixes.',
                 'Адресно исследовать собственную область.',
                 'mc ls --recursive lab/handbook-minio/project/',
                 'Перечисление не превращает prefix в файловый каталог.'),
        ],
    ),
    card(
        'mc rm',
        'Удалить выбранный объект либо конкретную версию. Без versionId в versioned bucket может создаваться marker.',
        'mc [ГЛОБАЛЬНЫЕ ОПЦИИ] rm [ОПЦИИ] TARGET [TARGET...]',
        'minio-06-versions-and-unknown-put', MC_SOURCE + 'rm-main.go',
        [
            flag('--dry-run', 'Показать предполагаемое удаление без его выполнения.',
                 'Сравнить поведение на сохранённом исходном состоянии.',
                 'mc rm --dry-run lab/handbook-minio/project/manifest.txt',
                 'Текущий version ID должен остаться прежним; это проверяется отдельно.'),
            flag('--version-id ID / --vid ID', 'Удалить ровно указанную версию либо marker.',
                 'Осознанно удалить собственный marker M.',
                 'mc rm --version-id M lab/handbook-minio/project/manifest.txt',
                 'Удаление marker раскрывает предыдущую current version; удаление data version уничтожает её тело.'),
        ],
    ),
    card(
        'mc admin user svcacct add',
        'Создать service account для указанного parent. Ответ содержит новый secret и сохраняется только приватно.',
        'mc [ГЛОБАЛЬНЫЕ ОПЦИИ] admin user svcacct add [ОПЦИИ] ALIAS ACCOUNT',
        'minio-05-limited-access', MC_SOURCE + 'admin-user-svcacct-add.go',
        [
            flag('--policy ФАЙЛ', 'Передать embedded policy.', 'Ограничить service account.',
                 'mc admin user svcacct add --policy ./policy.json lab study-admin',
                 'Policy должна быть валидной и непустой; её отсутствие может означать наследование широких прав.'),
            flag('--access-key ID', 'Задать заранее сохранённый идентификатор.',
                 'Иметь цель reconciliation после неоднозначного ответа.',
                 'mc admin user svcacct add --access-key study-example lab study-admin',
                 'Secret при отсутствии --secret-key генерирует клиент; его потерю info не исправляет.'),
            flag('--name ТЕКСТ', 'Задать понятное имя account.',
                 'Сопоставлять доступ с проектом.',
                 'mc admin user svcacct add --name "handbook object client" lab study-admin',
                 'Имя не заменяет access key и не задаёт полномочия.'),
        ],
    ),
    card(
        'mc admin user svcacct info',
        'Прочитать состояние, parent и policy service account. Secret повторно не выдаётся.',
        'mc [ГЛОБАЛЬНЫЕ ОПЦИИ] admin user svcacct info [ОПЦИИ] ALIAS ACCESS_ID',
        'minio-05-limited-access', MC_SOURCE + 'admin-user-svcacct-info.go',
        [
            flag('--policy', 'Показать policy как JSON.',
                 'Проверить фактическое ограничение созданного account.',
                 'mc admin user svcacct info --policy lab study-example',
                 'Вывод описывает policy; работоспособность доступа принимается отдельными запросами.'),
        ],
    ),
    card(
        'mc admin user svcacct disable',
        'Отключить будущую авторизацию указанного service account, сохранив его идентичность для разбора.',
        'mc [ГЛОБАЛЬНЫЕ ОПЦИИ] admin user svcacct disable ALIAS ACCESS_ID',
        'minio-05-limited-access', MC_SOURCE + 'admin-user-svcacct-disable.go',
    ),
]

for _entry in _MC_CARDS:
    if _entry['name'] == 'mc alias set':
        _entry['aliases'] = ['mc alias s']

_names = {entry['name'] for entry in _MC_CARDS}
COMMANDS = [entry for entry in COMMANDS if entry['name'] not in _names] + _MC_CARDS

import re

_mc_root = next(c for c in COMMANDS if c["name"] == "mc")

# Только реально общие флаги, уже описанные в root card.
# --help добавляется CLI на каждом используемом уровне отдельно.
_mc_shared_names = {
    "--config-dir", "--quiet", "--disable-pager", "--no-color",
    "--json", "--debug", "--resolve", "--insecure",
    "--limit-upload", "--limit-download",
    "--conn-read-deadline", "--conn-write-deadline",
    "--custom-header", "--help",
}

def _mc_is_shared(flag):
    forms = set(re.findall(r"--[a-z][a-z0-9-]*", flag["flag"]))
    return bool(forms & _mc_shared_names)

_mc_shared_flags = [
    dict(flag) for flag in _mc_root["flags"] if _mc_is_shared(flag)
]

_mc_namespace_specs = [
    ("mc alias", "mc alias set", "alias-main.go",
     "Группа команд для сохранённых aliases."),
    ("mc admin", "mc admin user svcacct add", "admin-main.go",
     "Группа административных команд сервера."),
    ("mc admin user", "mc admin user svcacct add", "admin-user.go",
     "Группа команд управления учётными записями."),
    ("mc admin user svcacct", "mc admin user svcacct add",
     "admin-user-svcacct.go",
     "Группа команд управления service accounts."),
    ("mc version", "mc version enable", "version-main.go",
     "Группа команд настройки versioning bucket."),
]

_mc_base = (
    "https://raw.githubusercontent.com/minio/mc/"
    "7394ce0dd2a80935aded936b09fa12cbb3cb8096/cmd/"
)

for name, leaf_name, filename, purpose in _mc_namespace_specs:
    if any(c["name"] == name for c in COMMANDS):
        continue
    leaf = next(c for c in COMMANDS if c["name"] == leaf_name)
    COMMANDS.append({
        "name": name,
        "aliases": [],
        "purpose": purpose,
        "syntax": name + " [ОБЩИЕ ФЛАГИ] COMMAND ...",
        "chapter": leaf["chapter"],
        "volume": "minio",
        "source": _mc_base + filename,
        "sources": [{
            "title": "Закреплённая структура команды mc",
            "url": _mc_base + filename,
        }],
        "flags": [dict(flag) for flag in _mc_shared_flags],
        "situations": [{
            "problem": "Флаг распознан после namespace",
            "explanation": (
                "mc повторно регистрирует globalFlags на этом уровне. "
                "Это не доказывает одинаковый эффект всех позиций."
            ),
            "solution": (
                "В маршруте ставьте --config-dir сразу после executable; "
                "локальные флаги — после имени конечной команды."
            ),
        }],
    })

for command in COMMANDS:
    if command["name"] == "mc" or command["name"].startswith("mc "):
        command.pop("persistentOptions", None)
        if command["name"] == "mc":
            continue
        existing = {flag["flag"] for flag in command["flags"]}
        command["flags"].extend(
            dict(flag) for flag in _mc_shared_flags
            if flag["flag"] not in existing
        )

def _add_flag_once(command_name, entry):
    command = next(c for c in COMMANDS if c["name"] == command_name)
    option = re.search(r"--[a-z][a-z0-9-]*", entry["flag"]).group()
    if not any(option in re.findall(r"--[a-z][a-z0-9-]*", f["flag"])
               for f in command["flags"]):
        command["flags"].append(entry)

for name, example in (("minio", "minio --help"),
                      ("minio server", "minio server --help")):
    _add_flag_once(name, flag(
        "-h / --help", "Показать справку выбранной команды.",
        "Сверить CLI собственной сборки.", example,
        "Печатается справка; сервер хранения не запускается."))

for name in ("minio", "mc"):
    _add_flag_once(name, flag(
        "--version", "Показать встроенную метку сборки и runtime.",
        "Сохранить сведения о полученной программе.", name + " --version",
        "Без релизных ldflags ожидается DEVELOPMENT.GOGET; commit проверяют отдельно по Git и buildinfo."))

for command in COMMANDS:
    if command["name"] == "mc" or command["name"].startswith("mc "):
        for entry in command["flags"]:
            if "--config-dir" in re.findall(r"--[a-z][a-z0-9-]*", entry["flag"]):
                entry["result"] = (
                    "Каталог выбирается при root registerBefore и initMC(). "
                    "Флаг зарегистрирован также у namespace/leaf, но поздний "
                    "setGlobalsFromContext не повторяет эту инициализацию. "
                    "В рецепте --config-dir стоит сразу после executable; "
                    "равнозначность позднего положения не подтверждена native."
                )

# Additional original definitions for the complete volume.
GLOSSARY.extend([
  [
    "Body",
    "Тело объекта: последовательность пользовательских bytes, отдельно от заголовков и metadata."
  ],
  [
    "Bucket",
    "Область имён и правил сервера; вместе с key выбирает объект."
  ],
  [
    "Key",
    "Строковое имя объекта внутри bucket; косая черта не создаёт POSIX каталог."
  ],
  [
    "Metadata",
    "Сведения об объекте или версии: размеры, тип, пользовательские поля и служебные параметры."
  ],
  [
    "Version ID",
    "Выданный сервером идентификатор версии; не checksum тела."
  ],
  [
    "Delete marker",
    "Версия-отметка без обычного тела, скрывающая текущее содержимое при обычном GET."
  ],
  [
    "Noncurrent version",
    "Сохранившаяся версия, которая больше не является текущей для key."
  ],
  [
    "Distribution",
    "Сохранённое соответствие позиций endpoints и shard indices выбранной версии."
  ],
  [
    "Part",
    "Часть представления объекта; у multipart их несколько, каждая имеет номер и собственные сведения."
  ],
  [
    "Chunk",
    "Непрерывный фрагмент shard stream, проверяемый выбранным bitrot checksum."
  ],
  [
    "Payload",
    "Полезное содержимое рассматриваемого уровня; у shard отличается от всего S3 body и от потока с hash headers."
  ],
  [
    "Bitrot",
    "Повреждение сохранённых bytes, обнаруживаемое проверкой целостности; checksum не выбирает историю и не является аутентификацией."
  ],
  [
    "Reed–Solomon",
    "Код избыточности, который при заданных параметрах восстанавливает данные из достаточного числа пригодных shards одной версии."
  ],
  [
    "Read quorum",
    "Численное условие достаточности согласованных пригодных источников для выбранного пути чтения."
  ],
  [
    "Write quorum",
    "Достаточное число принятых согласованных результатов записи конкретного layout; для симметричного K=P обычного тела требуется K+1."
  ],
  [
    "TLS",
    "Защита соединения и проверка связи сертификата с именем/IP сервера по принятому доверию."
  ],
  [
    "CA",
    "Удостоверяющая сторона; её публичный сертификат позволяет клиенту проверять подпись server certificate."
  ],
  [
    "SAN",
    "Поле сертификата с допустимыми именами/IP; URL клиента должен ему соответствовать."
  ],
  [
    "Access key",
    "Идентификатор credentials; не secret для вычисления подписи."
  ],
  [
    "Secret key",
    "Закрытое значение для подписи запросов; info service account не возвращает потерянный secret."
  ],
  [
    "Policy",
    "Документ разрешений над действиями и ресурсами; неперечисленное действие не становится разрешённым от наличия credentials."
  ],
  [
    "Service account",
    "Отдельные credentials, связанные с parent; embedded policy ограничивает их действия."
  ],
  [
    "ARN",
    "Строковая идентичность ресурса в совместимом policy; сама не выбирает сетевой endpoint."
  ],
  [
    "Scanner",
    "Фоновый обход сохранённого состояния; выбор режима и задания проверки не равен немедленному deep scan всех bytes."
  ],
  [
    "MRF",
    "Очередь последующих попыток исправления неполных операций; её наличие не означает завершённый repair."
  ],
  [
    "Rebalance",
    "Перемещение подходящих сохранённых версий между pools для выбранной цели заполнения."
  ],
  [
    "Decommission",
    "Управляемый вывод pool с переносом данных; назначение нового места не означает завершённый перенос."
  ],
  [
    "RPO",
    "Допустимая потеря изменений относительно контрольной точки резерва."
  ],
  [
    "RTO",
    "Время восстановления требуемого обслуживания, включая проверку доступа и данных."
  ],
  [
    "Throughput",
    "Подтверждённая полезная работа за выбранный интервал; ошибки/unknown и физические shard IO учитываются отдельно."
  ],
  [
    "Percentile",
    "Квантиль распределения наблюдений по указанному определению; percentiles узлов не усредняют для общего результата."
  ],
  [
    "Concurrency",
    "Число одновременных запросов, влияющее на очередь, ресурсы и ошибки."
  ],
  [
    "Toolchain",
    "Компилятор и сопутствующие инструменты выбранной версии; исторический Go не является обещанием текущей поддержки."
  ],
  [
    "Checksum",
    "Вычисленное по bytes значение проверки целостности; при отсутствии доверенного эталона не доказывает подлинность."
  ]
])

# Pinned operations; shared flags are registered explicitly, without a
# persistence claim. The recipe keeps --config-dir before admin.
for _name, _file, _purpose, _syntax, _chapter in [
    ("mc admin info", "admin-info.go", "Прочитать состояние deployment; это не запуск heal.", "mc [ROOT_FLAGS] admin info ALIAS", "minio-09-pools-and-operations"),
    ("mc admin rebalance", "admin-rebalance-main.go", "Группа управления переносом между pools.", "mc [ROOT_FLAGS] admin rebalance COMMAND ALIAS", "minio-09-pools-and-operations"),
    ("mc admin rebalance start", "admin-rebalance-start.go", "Принять задание rebalance подходящего multi-pool deployment; ID не означает завершение.", "mc [ROOT_FLAGS] admin rebalance start ALIAS", "minio-09-pools-and-operations"),
    ("mc admin rebalance status", "admin-rebalance-status.go", "Прочитать per-pool progress; Bytes и ETA имеют ограничения версии.", "mc [ROOT_FLAGS] admin rebalance status ALIAS", "minio-09-pools-and-operations"),
]:
    COMMANDS.append(card(_name, _purpose, _syntax, _chapter,
                         _mc_base + _file, [dict(f) for f in _mc_shared_flags]))
for _action, _purpose in [
    ("snapshot", "После полной остановки единственного стенда создать новую приватную копию и inventory."),
    ("verify", "Сравнить bytes snapshot с сохранённым inventory; не запускать MinIO."),
    ("restore", "Восстановить проверенный snapshot в новый отдельный runtime, не перезаписывая оригинал."),
]:
    COMMANDS.append(card(
        "cold_copy.py " + _action, _purpose,
        "python3 -B labs/cold_copy.py " + _action + " SOURCE" + ("" if _action == "verify" else " DEST"),
        "minio-10-backup-and-recovery", "https://docs.python.org/3/library/shutil.html", [
            flag("-h / --help", "Показать argparse help.", "Проверить аргументы до копирования.",
                 "python3 -B labs/cold_copy.py --help", "Никакая копия не создаётся."),
        ]))
for _command in COMMANDS:
    if _command["name"].startswith("mc "):
        for _entry in _command["flags"]:
            if "--config-dir" in re.findall(r"--[a-z][a-z0-9-]*", _entry["flag"]):
                _entry["result"] = (
                    "Каталог выбирается root registerBefore/initMC. "
                    "Поздняя регистрация флага не повторяет инициализацию: "
                    "в рецепте --config-dir стоит сразу после executable; "
                    "равнозначность позднего положения не подтверждена native.")
