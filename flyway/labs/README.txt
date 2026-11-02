СОХРАНЯЕМЫЙ СТЕНД FLYWAY / GO / POSTGRESQL

Читать главы по порядку. Эти файлы копируют в $HOME/handbook-lab/flyway;
не исполняют из public checkout. pg18 живёт отдельно в $HOME/handbook-lab/pg18.
Python 3.12+, личный PostgreSQL 18.6 с OpenSSL, openssl CLI, Flyway OSS 13.12.0
и Go 1.27.3 должны уже быть получены/проверены. На рабочем Windows только чтение.

lab.py configure --pg-bin /личный/pg/bin --flyway /личный/flyway
создаёт private конфиг/пароли и маркер нового PG root. Не принимает существующий
чужой root. По умолчанию TLS verify-full, loopback 15432, SCRAM. --no-tls только
для изолированного теста, не проверяет основной защищённый профиль.
start -> bootstrap -> flyway info -> flyway migrate -target=1.
Команды flyway после первого слова принимают собственные -key=value аргументы.
lab.py не реализует Flyway, а запускает реальный официальный CLI дочерним процессом.

Контракт: handbook, app, flyway_meta. defaultSchema=flyway_meta;
schemas=flyway_meta,app; createSchemas=false. lab_admin только bootstrap;
flyway_owner owns schemas/objects; app_runtime NOLOGIN; app_local LOGIN/member.
Нет прав приложения на metadata/DDL. Vault самостоятельно не запускается.

Стадии:
V1 create notes; R note_count; seed.sql один раз -> v1;
V2 добавить nullable title и разрешить будущую запись только title -> v2;
drain v1 -> backfill --batch 200 -> sql --file check-backfill.sql -> V3 CHECK NOT VALID -> V4 VALIDATE;
V5 index CONCURRENTLY с executeInTransaction=false и session advisory lock;
v3 -> принятый backup/restore -> V6 drop body. Gate нельзя пропускать.

app/main.go три release-режима одного своего Go-сервиса:
v1 body; v2 COALESCE(title,body)+dual write; v3 title-only.
go.mod/go.sum закрепляют pgx. Получение Go modules до offline-дня.
app-build не выполняет миграции; app-run заменяет Python-процесс Go-процессом
с тем же PID и группой терминала. Ctrl-C поступает Go напрямую: он закрывает listener
и ожидает активные handlers до 5 секунд;
после deadline печатает предупреждение, результаты незавершённых записей нужно сверить.
HTTP только 127.0.0.1:18080. request/--text вызывают этот сервис с отключённым наследованием HTTP proxy.
POST принимает один JSON-объект text, полный body до 8192 байт.
Decoder требует EOF после завершающих пробелов, до любого SQL.
app/decode_test.go проверяет эти условия без БД через httptest.
Нет idempotency key: не повторять неопределённо принятый POST слепо.

snapshot -> backups/handbook-TIMESTAMP.dump; restore ПУТЬ -> новая handbook_restore.
restore-check --allow-pending проверяет только handbook_restore через info/validate,
разрешая Pending V6 после принятой точки V5, но не checksum mismatch.
Без --allow-pending validate требует отсутствия Pending. Произвольный URL action не принимает.
Исходник не overwrite; существующая restore DB не удаляется. ACL восстановлены
только именованным app объектам, history остаётся закрытой. Для V1 backup,
пока title ещё нет, check-restore-app.sql UPDATE title неприменим: выполняйте
этот restore-практикум после V4/V5. В тестах ранние restore сверяются отдельно.

experiments/ намеренно НЕ входит в locations. Эти файлы только для отдельного
native harness/одноразовой копии: отрицательные SQL, late 1.5 и slow V7.
Нельзя копировать все experiments в migrations одновременно: одинаковые V7.

measure.sql/inspect.sql/check-restore*.sql читают состояние или явно делают
нулевой UPDATE в транзакции rollback. seed.sql меняет данные и не идемпотентен.

Секретные .private/, backups/, state/, logs/, app/bin/, vendor/ не публиковать.
Сохранять этот .gitignore при копировании. Gitignore не заменяет права 0600.
Срок CA 30 дней / server 14 дней: после истечения нужна ротация, не sslmode=disable.
Нет reset/clean. stop останавливает только PGDATA из проверенного private marker.
