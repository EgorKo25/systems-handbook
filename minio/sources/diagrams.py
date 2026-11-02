DIAGRAMS = [
    dict(
        id='minio-four-quorum',
        volume='minio',
        chapter='minio-01-model',
        anchor='minio-01-model',
        insert_before='<h2>Восемь мегабайт на восьми endpoints</h2>',
        title='Чтение и запись требуют разного числа ответов',
        intro='Проследите один set N=4, K=2, P=2 после последовательных отказов.',
        assumptions=(
            'Учебные состояния, не работающий сервер. Обычный непустой объект; '
            'пригодная metadata и shards одной версии; нет tiering, '
            'delete markers, нового degraded PUT и реального healing.'
        ),
        nodes=[
            dict(id='client', label='Клиент', sub='GET или PUT'),
            dict(id='server', label='Server', sub='Проверяет достаточность'),
            dict(id='set', label='Set 4', sub='K=2, P=2'),
            dict(id='read', label='Read', sub='Нужно 2'),
            dict(id='write', label='Write', sub='Нужно 3'),
        ],
        edges=[
            dict(id='request', **{'from':'client', 'to':'server'}, label='запрос'),
            dict(id='dispatch', **{'from':'server', 'to':'set'}, label='получить ответы'),
            dict(id='read-result', **{'from':'set', 'to':'read'}, label='read quorum'),
            dict(id='write-result', **{'from':'set', 'to':'write'}, label='write quorum'),
        ],
        steps=[
            dict(
                title='Все доступны',
                explanation='Четыре пригодных endpoints превышают оба порога.',
                actor='Server', focus=['set'], active=['dispatch'],
                states={'client':'запрос', 'server':'считает ответы',
                        'set':'4 online', 'read':'4 ≥ 2', 'write':'4 ≥ 3'},
                fields=[dict(name='Пригодные ответы', before='нет запроса',
                             after='4', why='Все endpoints отвечают согласованно.')],
                bands=[dict(label='Порог', value='R=2, W=3',
                            detail='Числа относятся к заданному layout.')],
            ),
            dict(
                title='Потерян один endpoint',
                explanation='Остаётся три; чтение и запись ещё имеют quorum.',
                actor='Отказ устройства', focus=['set','write'], active=['write-result'],
                states={'client':'повторный запрос', 'server':'учитывает отказ',
                        'set':'3 online', 'read':'3 ≥ 2', 'write':'3 ≥ 3'},
                fields=[dict(name='Доступность', before='4', after='3',
                             why='Один endpoint перестал давать пригодный ответ.')],
                bands=[dict(label='Запас записи', value='0 сверх порога',
                            detail='Ещё один отказ изменит доступность записи.')],
            ),
            dict(
                title='Потерян второй endpoint',
                explanation='Два shards достаточны для чтения этой версии, '
                            'но не для подтверждения записи 2+2.',
                actor='Server', focus=['read','write'],
                active=['read-result','write-result'],
                states={'client':'GET или PUT', 'server':'разделяет решения',
                        'set':'2 online', 'read':'2 ≥ 2: возможно',
                        'write':'2 < 3: отказ'},
                fields=[dict(name='Ответ', before='обе операции возможны',
                             after='read возможно, write отказ',
                             why='Пороги операций различаются.')],
                bands=[dict(label='Quorum', value='R достигнут, W нет',
                            detail='Схема не обещает успех без пригодной metadata.')],
            ),
            dict(
                title='Остаётся один',
                explanation='Одного shard меньше K: эта модель больше '
                            'не может восстановить тело.',
                actor='Server', focus=['set','read'], active=['read-result'],
                states={'client':'GET', 'server':'не придумывает данные',
                        'set':'1 online', 'read':'1 < 2: отказ',
                        'write':'1 < 3: отказ'},
                fields=[dict(name='Пригодные shards', before='2', after='1',
                             why='Недостаточно данных для декодирования.')],
                bands=[dict(label='Восстановление', value='нет в этой модели',
                            detail='Healing не создаёт утраченную информацию.')],
            ),
        ],
    ),
]

def _minio_io_step(title, explanation, actor, focus, active,
                   values, name, before, after, why):
    keys = ("client", "api", "codec", "temp", "meta", "disks")
    return {
        "title": title,
        "explanation": explanation,
        "actor": actor,
        "focus": focus,
        "active": active,
        "states": dict(zip(keys, values)),
        "fields": [{
            "name": name, "before": before, "after": after, "why": why,
        }],
        "bands": [{
            "label": name, "value": after, "detail": why,
        }],
    }


DIAGRAMS.append({
    "id": "minio-object-io",
    "volume": "minio",
    "chapter": "minio-08-object-io",
    "anchor": "minio-08-object-io",
    "insert_before": "<h2>Что меняется при публикации</h2>",
    "title": "Временные chunks, публикация V и последующий GET",
    "intro": (
        "Проследите одну условную версию V. Сначала E4 теряется "
        "во время PUT; после принятия V повреждается chunk на E3."
    ),
    "assumptions": (
        "Один pool и один set; N=4, K=2, P=2, W=3, R=2. "
        "Single PUT, S=2 MiB+1, B=1 MiB, non-inline. "
        "Layout выбран до отказа E4. Distribution [3,4,1,2]: "
        "E1/E2 хранят parity, E3/E4 — data. "
        "Для GET metadata V на E1/E2 согласованы, их chunks исправны. "
        "В этом GET reader E3 был вызван и обнаружил ошибку hash. "
        "Каждый endpoint в модели находится на отдельном физическом диске "
        "своего узла. Это модель, не топология запущенного стенда."
    ),
    "nodes": [
        {"id": "client", "label": "S3-клиент",
         "sub": "body PUT / результат GET"},
        {"id": "api", "label": "HTTP / ObjectLayer",
         "sub": "Проверки запроса, блокировка, ответ"},
        {"id": "codec", "label": "Erasure + bitrot",
         "sub": "K/P, chunks и контрольные суммы"},
        {"id": "temp", "label": "Временная область",
         "sub": ".minio.sys/tmp/U/T/part.1"},
        {"id": "meta", "label": "Описание V",
         "sub": "FileInfo в RAM → xl.meta"},
        {"id": "disks", "label": "E1 / E2 / E3 / E4",
         "sub": "Данные и metadata по endpoints"},
    ],
    "edges": [
        {"id": "request", "from": "client", "to": "api",
         "label": "PUT / GET"},
        {"id": "body", "from": "api", "to": "codec",
         "label": "поток body"},
        {"id": "params", "from": "api", "to": "meta",
         "label": "V, T, K/P, B"},
        {"id": "coded", "from": "codec", "to": "temp",
         "label": "hash | chunk"},
        {"id": "publish-data", "from": "temp", "to": "disks",
         "label": "перемещение DataDir"},
        {"id": "publish-meta", "from": "meta", "to": "disks",
         "label": "публикация xl.meta"},
        {"id": "read-meta", "from": "disks", "to": "meta",
         "label": "metadata выбранной V"},
        {"id": "select", "from": "meta", "to": "codec",
         "label": "параметры и номера shards"},
        {"id": "sources", "from": "disks", "to": "codec",
         "label": "проверенные chunks"},
        {"id": "bytes", "from": "codec", "to": "api",
         "label": "логические байты GET"},
        {"id": "response", "from": "api", "to": "client",
         "label": "ответ и тело"},
    ],
    "steps": [
        _minio_io_step(
            "Запрос принят к обработке",
            "Handler проверил запрос. V и T созданы в RAM; "
            "новая версия ещё не опубликована.",
            "MinIO PUT", ["api", "meta"], ["request", "params"],
            ["отправляет body", "проверки запроса пройдены",
             "готов читать blocks", "новые потоки ещё не закончены",
             "FileInfo V в RAM", "V ещё нет в публичном xl.meta"],
            "Состояние V", "нет новой версии", "подготовлена в RAM",
            "Создание VersionID не равнозначно публикации на storage."),
        _minio_io_step(
            "Encode и close прошли на трёх endpoints",
            "E4 отказал после выбора layout. E1/E2/E3 сохранили "
            "chunks во временной области; W=3 выполнен для этого этапа.",
            "Erasure writers", ["codec", "temp"], ["body", "coded"],
            ["ещё ждёт ответ", "ещё не вернул ObjectInfo",
             "Encode и close quorum приняты",
             "E1/E2/E3 готовы; E4 ошибся",
             "размеры и metadata V заполнены",
             "публичная V ещё не добавлена"],
            "Пригодные временные потоки", "пишутся", "3",
            "Проверка этих writers предшествует RenameData."),
        _minio_io_step(
            "V опубликована",
            "DataDir и xl.meta опубликованы на E1/E2/E3. "
            "Код принял write quorum RenameData.",
            "RenameData", ["temp", "meta", "disks"],
            ["publish-data", "publish-meta"],
            ["ещё может не получить ответ", "ObjectInfo V подготовлен",
             "кодирование завершено", "пригодные данные перемещены",
             "xl.meta с V на трёх endpoints",
             "E1:shard3; E2:shard4; E3:shard1; E4:нет V"],
            "Публикации V", "0", "3, W=3",
            "Участники публикуют отдельно; четвёртый endpoint ещё требует восстановления."),
        _minio_io_step(
            "Подтверждение дошло клиенту",
            "В этой ветви успешный ответ действительно получен. "
            "При потере соединения знание клиента было бы другим.",
            "HTTP handler", ["api", "client"], ["response"],
            ["PUT подтверждён; сохранён ID V", "успешный ответ отправлен",
             "работа PUT закончена", "cleanup временной области",
             "V опубликована", "три участника содержат V"],
            "Знание клиента", "ждёт ответ", "подтверждённая V",
            "Момент серверной публикации и получение HTTP-ответа разделены."),
        _minio_io_step(
            "GET исключил повреждённый chunk",
            "После PUT chunk на E3 испортился, E4 всё ещё без V. "
            "E1/E2 дают пригодные parity chunks и согласованную metadata V.",
            "MinIO GET", ["api", "meta", "codec", "disks"],
            ["request", "read-meta", "select", "sources"],
            ["запросил V", "GET читает выбранную версию",
             "shard1 непригоден; shard2 недоступен; shard3/4 проверены",
             "новый repair ещё не выполнялся",
             "read quorum V получен",
             "E1/E2:источники; E3:bad chunk; E4:нет V"],
            "Пригодные chunks", "ожидаются", "2 parity chunks",
            "R=K=2 достаточно при согласованной metadata и правильных номерах shards."),
        _minio_io_step(
            "GET вернул V, копии ещё не восстановлены",
            "Декодер восстановил data shards в RAM и отдал S байт. "
            "Выявленный bitrot может поставить V в фоновую очередь.",
            "Erasure decoder", ["codec", "api", "client"],
            ["sources", "bytes", "response"],
            ["в модели получены все байты V", "передал S байт",
             "data shards восстановлены в RAM",
             "нет опубликованной записи healing",
             "описание V не заменено новым PUT",
             "E3 всё ещё повреждён; E4 всё ещё без V"],
            "Результат GET", "нужно тело", "S байт V",
            "Реконструкция ответа не подтверждает RenameData ни одной цели healing."),
    ],
})
