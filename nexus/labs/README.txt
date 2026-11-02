NEXUS REPOSITORY · авторский практикум · 1 ноября 2026

Режим L (реально выполнен): Python 3 + заранее подготовленный Go, только
временные файлы и loopback HTTP. Nexus не эмулируется и не запускается.
  python3 tests/local_client.py --go /path/to/prepared/go --report report.json
Запуск из каталога labs. Системные настройки Go/ОС не изменяются. Скрипт
создаёт и очищает собственный TemporaryDirectory. Результаты авторского
прогона: tests/results.json. Toolchain: go1.27.3 linux/amd64.

Исходники:
  module/ledger/ — собственный example.invalid/Acme/ledger v1.0.0;
  service/ — собственная HTTP-служба pulse, require ledger без replace;
  artifacts.py — allowlist ZIP fixture, SHA-256 manifest и ограниченный verifier;
  tests/local_client.py — настоящие Go/HTTP/file проверки;
  config/ — НЕ ПРИМЕНЁННЫЕ рецепты personal VM: Nexus/systemd/NGINX.

Режим N: следовать главам 01–16. Настоящий CE 3.97.3 живёт весь практикум.
Не запускать VM-команды sudo на рабочем хосте. Нет автоматического сброса
сервера, удаления releases, создания облака или запуска Docker daemon.
Ресурсный профиль VM 16 GiB требует host с запасом сверх этого объёма.
Бессрочный disconnected CE 3.97.3 не обещается: обязательная base telemetry.

Подготовить ZIP (из labs):
  python3 artifacts.py module --output ./lab-work/proxy
Это локальные файлы правильного Go protocol layout. Для Nexus Go hosted
загружается ZIP через PUT repository/go-internal/v1.0.0.zip; сервер сам
должен создать/выдать форматные ответы. Raw upload не Go module proxy.

Manifest после сборки linux/amd64 программы:
  python3 artifacts.py manifest --binary service/dist/pulse-linux-amd64 \
    --version 1.0.0 --toolchain 'go1.27.3 linux/amd64' \
    --output service/dist/manifest.json
Подставить фактически использованный toolchain, не копировать неверный.
Проверка:
  python3 artifacts.py verify --manifest service/dist/manifest.json \
    --directory service/dist
Verifier проверяет basename/regular file/размер/SHA-256, отвергает symlink.
Он не доказывает происхождение свободно заменяемого manifest и не создаёт
изоляцию исполнения. Каталог нельзя открывать постороннему писателю между
проверкой и запуском: защита от такой гонки здесь не реализована.

Упаковщик предназначен ровно для allowlist нашего крошечного модуля.
Для произвольного production module использовать проверенный x/mod/zip.
Файлы fixtures не содержат секретов, host-адресов или личных путей.

ДОПОЛНЕНИЕ SOURCE-РЕВЬЮ · 2 ноября 2026
Предыдущие results.json/h1-results.json/tls-results.json/source-results.json —
сохранённые авторские прогоны прежнего source, не новый PASS после этой правки.
Рабочий корень главы — копия тома с labs/. Этот README также даёт короткие
пути при запуске из самого labs/; не добавляйте второй labs/ к такому пути.

artifacts.py module теперь принимает --source и --version v1.MINOR.PATCH:
  python3 artifacts.py module --source ../lab-work/ledger-v1.0.1 \
    --version v1.0.1 --output ../lab-work/proxy
Это новая копия трёх исходников ledger, не другая module identity.
Старые version files не перезаписываются. list содержит обе numeric-v1 версии.
STAMP — фиксированная учебная metadata, не обнаруженное время коммита.
Нет транзакции нескольких файлов и защиты от чужого параллельного writer:
ошибка может оставить частичный новый вывод, который надо исследовать.
Не удаляйте автоматически старый рабочий стенд ради повторного запуска.

artifacts.py manifest добавляет --input-version (default v1.0.0).
Размер и SHA-256 вычисляются по файлу; version/toolchain/input-version
сообщает оператор. Target linux/amd64 и source_module заданы для нашей
сборки; helper не обнаруживает платформу или граф по Go build info.
Новый output создаётся эксклюзивно; существующий manifest не перезаписывается.

cold_backup.sh — новый НЕ ИСПОЛНЁННЫЙ рецепт личной VM из главы14.
Это Bash + systemd + util-linux mountpoint + rsync. Оба File blob store
должны быть внутри data-dir, запуск JVM только через nexus.service.
Полная install-копия увеличивает объём. TLS backup содержит private key.
Никакого сброса/удаления partial snapshot или чужих процессов нет.

В local_client.py ожидание LISTEN теперь читает pipe без блокирующего
readline: timeout/EOF/ранний exit/слишком длинная строка дают отказ.
Terminate/kill относятся только к Popen собственного pulse.
Readiness deadline не обещает мгновенный reap процесса в неотзывном
состоянии ядра. Эта новая ветка требует повторного native Linux прогона.
