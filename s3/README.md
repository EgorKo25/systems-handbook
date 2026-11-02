# S3 · исходный самостоятельный том

Это авторский source-кандидат к main 9c97f1957e24c336a4c42833dfb889a0340868c6. Исходников s3/ в этой базе не было. Физическое сохранение и регистрация принадлежат координатору. В авторской сессии filesystem read-only: файлы не записывались, native-сборка и серверная приёмка не выполнялись.

## Состав

00-route и главы01–16 читаются по volume_config.py. Словарь99-glossary генерирует общий builder из reference.py. Главы06/07 сохраняют подробный путь подписанных байтов и операций; новые главы развивают условия, версии, multipart, pagination, IAM, сохранность и расходы. Номер тома XXVI. Это не полное руководство по всем продуктам AWS: выбран general purpose bucket; directory buckets, S3 Express/Tables/Vectors, CopyObject и событийные очереди не реализованы учебным helper.

build.py вызывает только scripts.build_volume.build("s3"). Он требует предварительного включения S3 в private CONFIGS/managed registry основным координатором. Сам по себе новый каталог ещё не зарегистрированный standalone build. Shared reader, registry, allowlist и Pages этот пакет не меняет.

signature_diagrams.py содержит DIAGRAMS=[]: прежняя карточочная схема убрана. Предметный рисунок s3-sigv4-bytes с собственными CSS/SVG уже inline в06. HTML не требует внешних шрифтов/fetch. Его численные данные проверяет sigv4_vectors.py. Полный HTTP/state путь07 включает собственную таблицу переходов. Другие source-каталоги для исполнения не требуются: все запускаемые модели и helper находятся в labs/.

## Режимы практики

* Python3.12+: `python3 -B s3/labs/storage_models.py check`, `python3 -B s3/labs/sigv4_vectors.py`, `python3 -B s3/labs/object_operations.py`. Это pure модели/арифметика без сети и записи файлов.
* Go helper object-study: полный source и go.mod в labs/object-client. Только put/get/head; Linux, конечные тайм-ауты, explicit config/profile/TLS, no-clobber GET. Сборка, лицензии зависимостей и endpoint acceptance — отдельный обязательный native gate.
* Amazon S3 — облачная служба, локально не устанавливается. Для MinIO/RGW сначала нужен принятый сервер/CA/учётка/корзина из соответствующего тома. Совместимость не выдаёт гарантий AWS.

Прочтите03 для получения Go и приватных каталогов,04 для JSON и первого сетевого действия. Credentials не входят в source-пакет. Все ключи подписи в06/07 публично вымышленные. Не снимайте условия PUT после unknown и не перенаправляйте вывод поверх существующего output/secret.

## Источники и проверка

source-provenance.json перечисляет первичные URL и выбранные версии. VALIDATION.json разделяет фактическую RAM-проверку, сохранённые прошлые receipts и незавершённые native/build/render проверки. go.sum не выдуман: его создаёт получение реального графа модулей; это checksums .mod/.zip, а build list определяется MVS. Не распространяются runtime, module cache, vendor, бинарники или личные профили. Полностью offline-сборка helper требует заранее полученных проверенных зависимостей и их лицензий.

Для exporter нет требуемых скрытых файлов; новый .gitignore не добавлен. Публично включаются только перечисленные manifest source paths. generated index/commands/glossary/diagrams и site artifacts получает main после интеграции.
