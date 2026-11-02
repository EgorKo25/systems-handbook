MongoDB · учебный стенд и исходники лабораторий
Редакция: 2 ноября 2026; исторические проверки — 1 ноября. Основной путь подробно разобран в главах тома.

НАЗНАЧЕНИЕ И ПРЕДПОСЫЛКИ
Документы jobs, миграция schemaVersion1→2, индекс и Go HTTP-сервис сохраняют
данные между заданиями. Обычный пользователь личной Ubuntu 24.04 x86-64,
уже доступные Python 3.12+, GnuPG, совместимые CPU/OpenSSL и Go 1.25+.
TLS-опыт требует уже доступный openssl CLI. Root, host packages/services,
Docker/privileged containers и рабочая сеть не нужны. Все listeners только
127.0.0.1; не исполнять на чужой/production БД.
Для чтения на рабочем Windows ничего устанавливать не нужно. Практический
путь требует собственного подходящего Linux окружения, которое имеет свои
следы/каталоги/процессы. Все службы всей книги одновременно не требуются.

ВЕРСИИ
MongoDB Community 8.0.34 Ubuntu 24.04 x86-64, source tag r8.0.34, SSPL-1.0;
mongosh 2.14.1 и Database Tools 100.20.0 отдельны от server tarball, Apache-2.0;
Go-driver v2.9.2, Apache-2.0, требует Go 1.25+ и MongoDB 4.4+ по самому тегу.
Реально испытана пара server 8.0.34 + driver 2.9.2 на Go 1.27.3. Лицензии в
../licenses/, ссылки/sha256/fingerprint и границы в главе mongodb-sources.

ПОСТОЯННОЕ СОСТОЯНИЕ ЧИТАТЕЛЯ
LAB=$HOME/handbook-lab/mongodb — новый собственный абсолютный каталог,
единственная копия данных не должна находиться в /tmp. Cwd для публичных
команд — каталог тома mongodb/ (выше labs/). Каждый зависимый Bash-блок
начинается с set -euo pipefail; отказ прекращает дальнейшие изменения.
prepare.py не переиспользует существующий каталог и не сбрасывает данные.
Работающие пользователи MongoDB и межузловой ключ создаются в private/,
не в книге. Доступ к файлам/credentials ограничен правами 0600/0700.

ПОРЯДОК, БЕЗ ПОВТОРНОГО BOOTSTRAP
1. Прочитать модель документа и установку. labs/prepare.py LAB создаёт
   data/log/run/private/backups/shell-config и mongod.yml. Сервер ещё не запущен.
2. labs/install.py LAB получает закреплённые archives, сверяет SHA256,
   проверяет подпись server и распаковывает отдельные tools/server,
   tools/shell и tools/dbtools. При несовпадении остановка до распаковки.
3. PATH выбирает эти bin; MONGOSH_CONFIG_DIR=$LAB/shell-config и
   MONGOSH_DISABLE_TELEMETRY=1 делают клиентское состояние явным.
   mongod --config LAB/mongod.yml --fork запускает свой сервер на 27117.
4. bootstrap.js PHASE=init выполняет первичную инициализацию replica set;
   отдельная hello-проба ждёт isWritablePrimary; PHASE=users создаёт
   operator@admin и app@workshop, закрывая localhost exception. admin.js
   ACTION=accept проверяет именно 8.0.34/study/loopback и запись majority+j/read.
   При частичной ошибке users выяснить, кто уже создан; не повторять вслепую.
5. До CRUD пройти главу доступа: anonymous Unauthorized, TLS-профиль.
   Штатно остановить свой mongod; tls-profile.py создаёт новую CA/SAN только
   для этого опыта; mongod-tls.yml использует тот же dataPath и пользователей.
   TrustedCA/IP работают; wrongCA, localhost вместо SAN-IP и plaintext должны
   отказать. Затем собственный --shutdown TLS и запуск обычного mongod.yml
   возвращают основной loopback-маршрут, пользователи/данные сохраняются.
6. Скопировать labs/service в новый LAB/service, собрать Go с -mod=readonly.
   GOTOOLCHAIN=local, свои GOCACHE/GOMODCACHE/GOPATH; app.json читается через
   MONGO_AUTH_FILE, пароль не помещается в URI/argv. -mode=bson проверяет
   байты без сервера. -mode=seed -n=20000 создаёт стабильный набор ID,
   повтор даёт new=0. До миграции выполнить explain и измерение.
7. -mode=migrate добавляет priority/schemaVersion и создаёт составной индекс.
   Повтор modified=0; explain сравнивается с прежним. -hint=natural и
   -hint=tenant_state_recent в -mode=measure сравнивают одинаковые данные.
8. -mode=serve слушает 127.0.0.1:18089 после Ping(primary). Во втором окне
   выполнить описанный HTTP-блок: 201→200 при том же ID/payload, 409 при другом
   payload, close modified1→0. Существующий ID не стирается для повтора.
   Ctrl+C останавливает Go, но оставляет mongod и данные.
9. -mode=transaction дважды согласует закрытие seed-000001 и одну ledger
   запись. -mode=check проверяет наличие 20001 jobs и версии. Штатный restart
   того же mongod.yml не требует prepare/init/users; данные должны остаться.
10. Сервис остановлен, никто не изменяет workshop. admin.js backup-count,
   новый dump archive и отдельная restore-1/data на 27118. URI restore без
   /admin. --stopOnError не откатывает частичный импорт; новая цель принимается
   count/index/BSONDate, полный test также сверяет digest. Остановить restore
   собственным --shutdown, сохранить исходный архив/данные.

В открытом shell AUTH не является бессрочным: admin.js удостоверяет operator
в каждом вызове; Go получает app credentials при каждом старте процесса.
Основной URI без пароля: mongodb://127.0.0.1:27117/?replicaSet=study&retryWrites=true
Пароли, keyfile, CA privatekey, database files и backups не распространяются.

ТОЧНЫЙ ОФЛАЙН-КОМПЛЕКТ ДЛЯ ИСПОЛНЕНИЯ
Читаемый том и исполняемая поставка — разные комплекты.
Публично в этом томе: источники HTML/config/reference/diagrams, Python/JS
helpers, Go source+go.mod+go.sum, tests и синтетические observed JSON, лицензии
и NOTICE. Требуемых dotfiles в этих лабораториях нет. Общий offline reader,
его mobile/8 темы и export проверяет координатор отдельно; этот README не
подтверждает уже выполненную визуальную/экспортную приёмку.

В личный внешний bundle для Ubuntu 24.04 x86-64 заранее получают:
- downloads/server.tgz: MongoDB Community 8.0.34 с закреплённым sha256;
- downloads/server.sig: detached подпись этого архива;
- downloads/server-8.0.asc: официальный публичный ключ с проверенным fingerprint;
- downloads/shell.tgz: mongosh 2.14.1 linux-x64 и ожидаемый release digest;
- downloads/dbtools.tgz: Tools 100.20.0 ubuntu2404-x86_64 и manifest digest.
Имена — точный интерфейс install.py; существующие архивы повторно не качаются,
но всегда проверяются. После нового prepare.py скопировать только эти файлы
в LAB/downloads и выполнить install.py. Созданные tools/... до проверки
повторно не использовать. В private/gnupg install создаст отдельный keyring.
Этот offline replay реально исполнен автором с запрещённым urllib network:
все hashes/signature прошли, binaries распакованы, --version выполнен.

Для Go нужен весь подходящий личный Go runtime с его лицензиями/NOTICE и
предварительно прогретый отдельный GOMODCACHE для данного go.mod/go.sum.
Нужны module .mod/.info/.zip/.ziphash, разрешённые зависимости и локальные
checksum-database записи; одного Go-binary либо go.sum недостаточно.
Существующий GOCACHE ускоряет, но не заменяет module source. Перед offline
днём собрать тот же источник с GOPROXY=off и -mod=readonly на целевом runtime.
Базовые Python/GnuPG/OpenSSL/системные shared libraries и подходящий CPU
остаются предпосылками ОС; серверный tgz не содержит весь Linux.
Полные third-party notices остаются с отдельными полученными distributions;
лицензии в книге не заменяют их при распространении binaries/modules/runtime.

Private bundle не включает обязательную копию старых credentials/data для
создания нового стенда: prepare генерирует новые. Для возврата существующего
стенда отдельно защищают private credentials/keyfile/CA, data/backup и config,
согласуя секреты и точку восстановления. Не переносить живую data выборочным
копированием .wt файлов. Archive в backups того же диска ещё не независимый
носитель; внешнее хранение и проверка восстановления требуют своей политики.

ПРОВЕРКИ И ГРАНИЦЫ
Из корня полного исходного дерева книги: python3 mongodb/tests/check_sources.py (нужен Node для
исполнения настоящего production command_reference_parser.js).
Native runner tests/native_accept.py принимает новые --lab и явные пути
--mongod/--mongosh/--dbtools/--service; занятые27117/27118/18089 даютSTOP ещё
до подготовки и запросов. Он создаёт собственные процессы, seed/HTTP/
transaction/restart/dump/restore и штатно завершает их. Старый LAB не трогает.
TLS runner tests/tls_accept.py принимает тот же OWN STOPPED LAB после native,
создаёт новый TLS-profile и возвращает экземпляр остановленным. Он требует
свободный 27117 и не останавливает уже работающую чужую службу.

Отрицательные ветки реально проверены: anonymous denied, duplicatepayload
409, неправильный CA/hostname/plaintext, существующий prepare без перезаписи,
неверный archive hash до распаковки, занятый port до prepare, unknown Go flag
exit2. Реальные aliases -f/--file с пробелами в имени файла и Goone/twodash/
--delimiter проверены отдельным CLI опытом; это не исчерпывающий help-alias audit.

Один участник replica set даёт настоящие сессии/транзакции/oplog, но не
репликацию между хостами. Здесь не испытывались election/partition/rollback,
sharding/balancer/reshard, liveoplog/PIT/physicalsnapshot, majorFCVupgrade/
downgrade, powerfailure, Enterprise/Atlas и productionconcurrency.
Ни схема в браузере, ни наличие архива не доказывают эти свойства.

ДОПОЛНИТЕЛЬНЫЙ КОНКУРЕНТНЫЙ ОПЫТ
tests/concurrency_accept.py принимает уже подготовленный OWN STOPPED TEST LAB, не reader LAB, и новые ID:
--lab OWN_PATH --mongod VERIFIED_BIN --mongosh VERIFIED_BIN
--service OWN_PUBLIC_SOURCE_BINARY_BUILT_WITH_RACE --case-id NEW_SIMPLE_ID.
Сборка go build -race -mod=readonly требует уже доступного cgo/C toolchain
поддержанного Go/OS; тест не устанавливает его. stderr остаётся в TEST LAB/log.
16 клиентов одного payload дают201x1/200x15, конкурирующие 8+8 payload —
201x1/200x7/409x8; одна запись и исходные поля сверяются напрямую в MongoDB.
16 close изменяют один раз (version1→2), HTTP exit code обязан быть 0; неизвестный
исход сети/503 фиксируется и останавливает тест без скрытого повтора.
Это correctness опыт конкретной конкуренции; serial n200 и production p99
он не заменяет. Детектор гонок в этом запуске не нашёл проблемы, но это не
формальное доказательство отсутствия любой гонки при любом расписании.

АДРЕСНЫЕ УТОЧНЕНИЯ 2 НОЯБРЯ 2026
После копирования service в свой LAB выполните из LAB/service:
  go test -mod=readonly .
Это 13 случаев реального JSON-reader через httptest без TCP/listener и БД,
а также один тест ожидания активного обработчика при остановке HTTP: собственный
временный loopback listener, без MongoDB и без сигнала чужому процессу.
Он должен принять ровно один объект, дочитать EOF и отвергнуть второй объект,
мусор и whitespace-хвост сверх 4096 байт. ID/tenant/title ограничены байтами
UTF-8 (80/80/200), не числом русских букв. Ошибка теста останавливает сборку.

Из каталога тома с Python 3.12:
  python3 tests/mechanisms.py --limit 20
  python3 tests/mechanisms.py --limit 5
Код 0: декодер проверил собственный 51 B запрос и 38 B ответ, пять повреждений
отвергнуты; арифметика сортировки seed вернула ожидаемые ID. --limit принимает
1..200 и меняет только модель. Ни запросов к БД, ни нового explain/latency нет.

Старые observed-*-2026-11-01.json остаются историческими. Новый main.go имеет
другой SHA из-за JSON-reader и ожидания Shutdown; операция MongoDB после разбора запроса, close,
seed/migrate/transaction сохранены. Новый observed-mechanisms-2026-11-02.json
отдельно перечисляет выполненные unit/native/model проверки. ACTION=types
теперь сам утверждает ожидаемые ID, а не только печатает их. Native-повтор
этой ветки выполнен на новом временном экземпляре; полный seed/restore/TLS
и concurrency после правки не объявляются снова пройденными.
