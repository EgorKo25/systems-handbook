HashiCorp Vault — сохраняемый личный стенд, редакция 02.11.2026.
Это исходники безопасного опыта, не поставка Vault/PG/Go и не служба хоста.
Все команды ниже: обычный владелец Linux amd64, cwd vault/labs личной копии.
Все зависимые shell-последовательности начинают set -euo pipefail; при
неожиданном отказе не исполняют следующий write. Ожидаемые status 2 / ACL 403 / CAS 400
обрабатываются отдельно в главах, не подавлением любых ошибок.
До начала нужны Python 3.11+ (hashlib.file_digest требует 3.11), GnuPG, OpenSSL, системные CA. Никакого sudo.
Не используйте рабочие credentials/network/listeners. В Windows — чтение
или доступ к собственной заранее разрешённой Linux VM.

0. Получение и проверка binary (он не лежит в книге):
   set -euo pipefail
   umask 077
   stand="$HOME/handbook-vault"
   labs_dir="$PWD"  # здесь cwd именно vault/labs
   python3 get_vault.py --root "$stand"
   Проверяет official signature primary C874011F0AB405110D02105534365D9472D7468F
   и SHA256; при отказе дальнейшие действия остановить. Профиль Vault 1.21.4
   закреплён для эксперимента, не latest/production recommendation.

1. Сохраняемый сервер:
   set -euo pipefail
   python3 lab.py --root "$stand" prepare --vault "$stand/bin/vault"
   python3 lab.py --root "$stand" start
   python3 lab.py --root "$stand" status
   python3 lab.py --root "$stand" init
   python3 lab.py --root "$stand" provision
   API 18200, cluster 18201, только 127.0.0.1; TLS CA/SAN, Raft, state/private/logs.
   env.sh задаёт private client.hcl/token-helper: get пустой, store disabled,
   host ~/.vault-token не читается. HOME не меняется. CLI tokens передаются
   явно из нужного private файла после source env.sh.
   Init JSON/shares/token только private 0600. 3 доли/порог 2 — учебная
   централизация, не настоящая независимость хранителей. Bootstrap root
   отзывается; lab operator TTL 8h/explicit max 24h, не credential приложения.
   Prepare/init/provision не повторяют при продолжении. После restart:
   python3 lab.py --root "$stand" start
   python3 lab.py --root "$stand" unseal
   Никакого повторного init/reset. Без renew оператор истекает через 8h, 24h —
   абсолютный предел с продлениями. Для своего unsealed Shamir стенда:
   python3 lab.py --root "$stand" recover-operator
   Явная церемония из главы 04: private/init.json с двумя разными source shares,
   попытка generate-root/nonce/OTP, временный root → orphan 8h/max 24h → root
   revoke+lookup 403. При живом операторе или занятом nonce отказ. Root/OTP/shares
   только в private 0600 operator-recovery-*.json. Если root_revoked не подтверждён,
   остановиться и завершить revoke по этой записи; новую попытку не начинать.
   Это не production разделение хранителей и не recovery потерянного KMS.

2. Единственный комплексный запуск в главе KV07:
   set -euo pipefail
   python3 lab.py --root "$stand" test-tokens
   python3 lab.py --root "$stand" checks
   Сразу после provision/currentVersion1. Не запускать после manual KV ветви.
   Tokens обновляются на 10m без изменения KV. Checks:13 assertions, версия 3,
   message=second/added=yes, версия 2 destroyed. Позднее читают checks.json,
   не повторяют checks и не сбрасывают state.

3. Продолжение того же стенда:
   set -euo pipefail
   python3 lab.py --root "$stand" approle
   python3 lab.py --root "$stand" pki
   python3 lab.py --root "$stand" agent
   AppRole SecretID TTL 5m/uses1, wrapping 60s; второй unwrap/login denied.
   PKI создаёт internal root/intermediate и leaf, отзывает serial; повтор
   pki с существующими mounts отвергается. Agent всегда берёт свежий SecretID
   у существующей роли, one-shot template 0600, без listener, logs private.
   Agent можно явно повторить для свежего app token после 5m. Go использует
   private/agent.token, а не старый token из AppRole09 и никогда root.
   Из labs/go-client с установленным Go 1.27.3:
   cd "$labs_dir/go-client"
   GOTOOLCHAIN=local GOFLAGS=-mod=readonly GOCACHE="$stand/go-cache" \
     GOMODCACHE="$stand/go-mod-cache" go build -o "$stand/bin/go-vault-client" .
   "$stand/bin/go-vault-client" -ca "$stand/tls/ca.crt" \
     -token-file "$stand/private/agent.token"
   Нативно проверенное API использует stdlib, сторонний Vault SDK не bundled.
   -watch включает token renewal; SIGTERM отменяет context. Нет PG pool logic.

4. Snapshot и ДРУГАЯ цель:
   set -euo pipefail
   cd "$labs_dir"  # вернуться из go-client в vault/labs
   python3 lab.py --root "$stand" snapshot --name checkpoint-v3.snap
   target="$HOME/handbook-vault-restore"
   python3 lab.py --root "$target" prepare --vault "$stand/bin/vault" \
     --port 18210 --cluster-port 18211
   python3 lab.py --root "$target" start
   python3 lab.py --root "$target" restore --source "$stand" \
     --name checkpoint-v3.snap
   Target должен быть новым, GET sys/init initialized=false. Служебные файлы
   Raft в state допустимы до init. Snapshot/custody проверяются до target init.
   -force только здесь, на отдельной цели. После импорта нужны SOURCE shares, target bootstrap shares устарели. Helper ждёт завершения async
   restore до sealed, затем unseal/active; source shares сохраняет в target
   private для будущего restart, старый targetinit помечает obsolete.
   Текущий source operator может отсутствовать в старом snapshot или истечь.
   Если импорт/unseal выполнен, но lookup 403: НЕ повторять restore, а явно:
   python3 lab.py --root "$target" recover-operator
   python3 lab.py --root "$target" verify-restore
   restore-imported.json означает импорт, restore-complete.json — успешное
   чтение восстановленного KV. recover не переиздаёт CA и не меняет KV.
   Snapshot не копирует TLS keys/config/binary, shares и данные/роли внешнего PG.
   Записи Vault после точки отсутствуют на restore-target, но source сохранён.
   Относительный audit file_path пишет в target/logs благодаря его cwd.
   python3 lab.py --root "$stand" measure --count 100
   Профиль: последовательные KV reads, новый TLS каждый раз, audit включён.

5. PostgreSQL (дополнительный backend, не автоматический запуск Flyway).
   set -euo pipefail
   PG_BIN — bin уже проверенной OpenSSL-сборки PostgreSQL 18.6. Основной
   постоянный reader PG root="$HOME/handbook-lab/pg18", loopback 15432.
   Никакого reinit поверх существующего PGDATA от Flyway: для общего сервера
   применяйте согласованный SQL отдельно, сверив владельцев/права. Helper
   ниже только для НОВОГО собственного PG root. Сначала прочитайте главу PG.
   pg="$HOME/handbook-lab/pg18"
   python3 pg_lab.py --root "$pg" prepare --pg-bin "$PG_BIN"
   python3 pg_lab.py --root "$pg" start
   python3 pg_lab.py --root "$pg" bootstrap
   python3 pg_lab.py --root "$pg" check --vault-root "$stand"
   TLS verify-full/SCRAM, handbook/app/flyway_meta, bootstrap roles, no plaintext.
   Check одноразовый: rotate-root меняет password plugin-role; 10 checkpoints,
   revoke NEW login denied; old session SELECT1 survives, table read denied.
   Не выдаются pg_signal_backend/superuser. PG backup/restore этим check
   не выполняется. Config/credentials и роли остаются в личном состоянии.

6. Остановка сохраняет данные:
   set -euo pipefail
   python3 lab.py --root "$stand" stop
   Если restore-target запущен, отдельно остановите его:
   python3 lab.py --root "$target" stop
   Если дополнительный собственный PG запущен, отдельно:
   python3 pg_lab.py --root "$pg" stop
   Команды для непройденных optional ветвей не выполняют. Helper проверяет
   свои PID/cwd; неожиданный отказ не подавлять. Никаких rm/reset.

Независимые тесты — НОВАЯ отдельная цель, cwd vault/tests:
   set -euo pipefail
   python3 check_sources.py
   python3 native_repeat.py --vault "$stand/bin/vault" \
     --work-root "$HOME/handbook-vault-independent-1"
   При необходимости --pg-bin "$PG_BIN" создаёт СВОЙ новый PG с другим
   свободным loopback port; не трогает reader PG 15432. Work-root должен
   отсутствовать, результаты сохраняются, owned процессы stop в finally.
   Это native experiment, не mobile/export acceptance. Node нужен только
   статическому тесту production parser. Модели DIAGRAMS ничего не запускают.

Поставку runtimes/keys/privatecerts/tokens/init.json/snapshots/audit logs
не включать в исходники, web export и offline copies. При экспорте сохранить
labs/.gitignore, labs/.env.example, sql/, policies/, go-client/ и licenses/.
Для offline запуска runtime/CA/key custody готовят ЗАРАНЕЕ в private. HTML
offline чтение и проверенная автономная server поставка — разные результаты.

Иллюстрации labs/illustrations/*.svg — локальные оригиналы; в главы вставлен
тот же SVG inline для наследования 8 тем reader. Отдельный SVG имеет paper
fallback. В title/desc и тексте главы перечислены состояния; SVG не делает
API-запросов и не хранит пользовательский stand. TTL шкала — расчёт, не таймер.
