"""Original native reference. No command, I/O or runtime starts on import."""
GLOSSARY = [
('Vault','Сервер, который проверяет идентичность и правила доступа, хранит секреты за криптографическим барьером и управляет поддержанными выдачами и отзывами.'),
('Секрет','Материал, владение которым даёт полномочие: пароль, private key, API token. Выдача требует контроля дальнейших копий.'),
('Trust bootstrap','Начальное установление доверия: чей binary запущен, какой CA принят, кто вправе выдать первую identity и разблокировать storage.'),
('Fingerprint','Полный криптографический отпечаток публичного ключа. Проверяет ожидаемую идентичность ключа отдельно от математической корректности подписи.'),
('Barrier','Криптографический слой Vault между логическими защищёнными данными и storage backend. Не заменяет ACL и резерв.'),
('Keyring','Набор ключей шифрования данных. Root key защищает keyring; это не root token API.'),
('Root key','Криптографический ключ защиты ключевого материала Vault. В модели 1.21 его доступность при unseal обеспечивается seal mechanism.'),
('Root token','Особый API credential с административными полномочиями. Не расшифровывает storage вместо unseal keys и не предназначен приложению.'),
('Shamir shares','Доли секрета разблокирования. Требуемый порог различных долей реконструирует материал; копии одной доли не увеличивают число.'),
('Init','Однократная инициализация пустого storage кластера и создание первоначального доступа. Не операция каждого restart или join.'),
('Unseal','Возвращение доступа процесса к ключевому материалу для работы barrier. Само не выдаёт приложению token и policy.'),
('Seal','Прекращение доступа узла к расшифрованному ключевому материалу. Не уничтожает ранее выданные пароли и внешние сессии.'),
('Recovery keys','Материал quorum-авторизации административных операций auto-unseal. Не заменяет навсегда потерянный внешний KMS key.'),
('Auto-unseal','Доступ к ключевому материалу через поддержанный внешний доверенный seal provider. Переносит bootstrap к identity/правам на этот provider.'),
('Mount','Точка подключения движка или auth method к логическому API-префиксу. Не каталог Linux.'),
('Secrets engine','Обработчик секретных операций определённого типа: KV хранит введённые значения, database управляет внешними ролями, PKI подписывает сертификаты.'),
('Auth method','Настроенный способ проверки исходного доказательства личности и выдачи Vault token.'),
('Entity','Внутренняя запись личности Vault. Может связывать несколько alias из определённых auth mounts.'),
('Alias','Связь внешнего имени/идентификатора в конкретном auth mount с entity. Совпадение строк не означает одну identity.'),
('Identity group','Группа entity или отображённых внешних участников с policy. Её членство может менять identity policies выданного token.'),
('ACL','Access control list — правила API-путей и разрешённых capabilities; проверяется реальный путь движка, не только удобная CLI запись.'),
('Capability','Имя разрешённой API-операции: read, list, create, update, patch, delete, sudo или deny. Не Linux capability.'),
('Policy','Именованный набор правил Vault; клиентский HCL файл действует только после загрузки. Policy names в token ссылаются на серверные правила.'),
('Token accessor','Управленческий идентификатор service token, не пригодный вместо token для чтения секретов.'),
('Orphan token','Token без родителя в дереве отзыва. Сохраняет свои policy/TTL и возможность прямого revoke.'),
('TTL','Time to live — оставшееся время пригодности конкретного объекта. Token TTL, SecretID TTL, lease TTL и notAfter сертификата не одно и то же.'),
('Lease','Запись динамической выдачи со сроком и обработчиками renewal/revoke. Lease ID не является password и не стирает его копии.'),
('Renewal','Запрос продления ещё пригодного объекта. Фактический срок берут из ответа; maxTTL может запретить дальнейшее продление.'),
('Revoke','Прекращение полномочий token/lease по правилам обработчика. Cleanup внешней системы может отказать или запаздывать.'),
('CAS','Compare-and-set — условная запись только при ожидаемой текущей версии. Защищает от потерянных конкурентных изменений, не заменяет ACL.'),
('KVv2 metadata','Версии/сроки/deleted/destroyed и настройки ключа отдельно от его пользовательских данных. LIST и READ используют разные API-пути.'),
('Soft-delete','Логическая пометка удалённой версии KVv2 с возможностью undelete, пока содержимое не destroyed/вытеснено.'),
('Destroy','Необратимое удаление содержимого выбранных KVv2 версий через API. Не доказательство стирания всех backup/копий.'),
('AppRole','Машинный auth method с role constraints и обычно RoleID/SecretID. Доставка обоих в одной открытой папке не создаёт независимых факторов.'),
('Response wrapping','Однократная ограниченная по TTL доставка ответа через wrapping token; получатель проверяет creation_path перед unwrap.'),
('Cubbyhole','Изолированная область хранения, связанная с token; используется в механизме response wrapping.'),
('ServiceAccount','Учётная запись workload Kubernetes. Её JWT может быть исходным доказательством login, но не является Vault token.'),
('OIDC','OpenID Connect — flow входа через провайдера личности с проверкой issuer/audience/redirect/claims и отображением на Vault role.'),
('SAN','Subject alternative name — удостоверяемые DNS/IP в сертификате. CN сам по себе не заменяет проверку IP SAN.'),
('CSR','Certificate signing request — подписанный запрос с открытым ключом и желаемыми именами; закрытый ключ остаётся у создателя.'),
('Issuer','Выпускающий CA с собственным ключом/сертификатом и ограничениями. Смена default issuer не обновляет trust stores клиентов.'),
('CRL','Certificate revocation list — подписанный перечень отозванных serial. Должен быть доставлен и применён verifier; не закрывает established TLS автоматически.'),
('Agent','Отдельный процесс Vault для auto-auth, renewal и templates в поддержанной конфигурации. Требует исходного bootstrap и не меняет environment уже работающей программы.'),
('Token sink','Назначение сохранения token Agent, например частный file 0600. Читатель sink получает полномочие этого token.'),
('Integrated storage','Встроенное сохраняемое состояние Vault с Raft consensus. Snapshot этой системы не включает SQL данные внешнего PostgreSQL.'),
('Raft term','Номер эпохи выборов в протоколе Raft. Помогает отвергать старого лидера; не является timestamp.'),
('Quorum','Большинство voters, необходимое для согласования/выборов Raft. У двух voters quorum 2, у трёх 2.'),
('Commit/apply','Запись сначала согласована, затем применена к детерминированной машине состояния. Vault блокирует writes до обоих этапов.'),
('Standby','Обычный неактивный узел Vault. Forwarding/redirect к active отличается от Enterprise performance standby.'),
('Audit device','Настроенное назначение записей API-взаимодействий. Если ни одно включённое устройство не пишет, соответствующая обработка не должна молча обходить аудит.'),
('HMAC','Hash-based message authentication code — ключевой отпечаток для проверки/сопоставления. Не обратимое шифрование секретного поля.'),
('RPO/RTO','Цели допустимой потери истории и времени до принятого восстановления. Созданный snapshot не доказывает достижение этих целей.'),
('Lease reconciliation','Сверка восстановленных leases Vault с настоящими внешними ролями/credentials после рассогласованного recovery.'),
('Jitter','Случайное смещение времени renewal/retry для распределения нагрузки; выбирается в пределах остатка TTL и deadline.'),
('Unseal key','Ключ, который Shamir seal реконструирует из порога долей и которым защищён root key. После unseal используется в памяти, не является API token.'),
('OTP generate-root','Одноразовая маска для получения временного root token из encoded_token. Нужна вместе с завершённой quorum-попыткой; хранится private отдельно от публичных отчётов.'),
]

def f(flag,action,when,example,result):return dict(flag=flag,action=action,when=when,example=example,result=result)
HTTP=[
f('-address АДРЕС','Выбрать HTTPS endpoint для этой операции.','Проверка другого собственного stand.','vault status -address=https://127.0.0.1:18200','Флаг локален выбранной команде; адрес не отключает проверку TLS.'),
f('-ca-cert ФАЙЛ','Принять конкретный PEM CA для проверки listener.','Свой локальный CA, абсолютный путь private stand.','vault status -ca-cert=/home/student/handbook-vault/tls/ca.crt','Проверяется также SAN; неверная CA даёт transport error, а не ACL403.'),
]
OUT=[f('-format ФОРМАТ','Выбрать table/json/yaml в поддержанной команде.','Машинная обработка результата в private файл.','vault kv get -format=json -mount=secret handbook/config','JSON сохраняет структуру; вывод может содержать секреты и не является public artifact.')]
MOUNT=f('-mount ПУТЬ','Отделить KV mount от относительного имени ключа.','Не путать CLI имя с secret/data API-путём.','vault kv get -mount=secret handbook/config','KVv2 CLI сам выбирает data/metadata endpoints; ACL задаётся на них.')

def c(name,purpose,syntax,chapter,flags=(),http=True,out=False,aliases=()):
    suffix=name.removeprefix('vault ').replace(' ','/')
    if name=='vault -help': suffix=''
    if name.startswith('vault operator raft snapshot '):suffix='operator/raft#snapshot'
    source='https://developer.hashicorp.com/vault/docs/v1.21.x/commands/'+suffix
    return dict(name=name,aliases=list(aliases),purpose=purpose,syntax=syntax,chapter=chapter,volume='vault',source=source,sources=[dict(title='Официальный CLI1.21.x; actual help1.21.4',url=source)],flags=[*(HTTP if http else []),*(OUT if out else []),*flags],situations=[],optionBoundary='first-operand')
COMMANDS=[
c('vault -help','Показать корневую справку установленного бинарника; сервер не запускается.','vault -help','vault-02-supply',http=False),
c('vault version','Показать версию, build и commit фактически запущенного файла.','vault version','vault-02-supply',http=False,aliases=['vault -version']),
c('vault server','Запустить сохраняемый сервер по подготовленному HCL; сам запуск не init/unseal.','vault server -config ФАЙЛ','vault-03-server',[
f('-config ФАЙЛ','Загрузить HCL/JSON конфигурацию или каталог согласно CLI.','Личный loopback stand с созданными paths и TLS.','vault server -config /home/student/handbook-vault/server.hcl','Процесс остаётся работающим; неверные права/порт прекращают запуск.')],http=False),
c('vault status','Прочитать init/seal/HA состояние через TLS.','vault status [ОПЦИИ]','vault-03-server',out=True),
c('vault operator init','Однократно инициализировать пустой storage; результат чувствителен.','vault operator init [ОПЦИИ]','vault-04-keys',[
f('-key-shares N','Создать N долей Shamir.','Только первый init нового кластера.','vault operator init -key-shares=3 -key-threshold=2 -format=json','Частный JSON хранит доли и первоначальный root; stdout не публикуют.'),
f('-key-threshold N','Задать необходимый порог различных долей.','При принятой церемонии хранителей.','vault operator init -key-shares=3 -key-threshold=2','Порог≤числа долей; две копии одной доли не считаются двумя.'),
],out=True),
c('vault operator unseal','Подать долю скрытым tty-вводом либо по защищённому API; не аргументом shell.','vault operator unseal','vault-04-keys',[
f('-reset','Сбросить накопленный незавершённый unseal progress этого узла.','Ошибочно начатая церемония; не reset storage.','vault operator unseal -reset','Данные не удаляются; для завершения нужны доли заново.')]),
c('vault operator seal','Перевести узел в sealed, прекратив доступ barrier к ключам.','vault operator seal','vault-04-keys'),
c('vault operator rekey','Провести quorum-церемонию смены unseal/recovery shares.','vault operator rekey [ОПЦИИ]','vault-04-keys',[
f('-target ЦЕЛЬ','Выбрать barrier/recovery по реальному seal contract.','Планируемая ротация хранителей.','vault operator rekey -target=recovery -init','Не заменяет ключ внешнего KMS и требует принятой процедуры, не исполняется автоматически.'),
f('-init','Начать новую церемонию rekey.','После выбора числа долей/порога и хранителей.','vault operator rekey -init -key-shares=3 -key-threshold=2','Это не одношаговая замена: требуются quorum inputs и проверка.'),
f('-key-shares N','Число новых долей.','Старт rekey.','vault operator rekey -init -key-shares=3 -key-threshold=2','Не меняет SQL passwords.'),
f('-key-threshold N','Порог новых долей.','Старт rekey.','vault operator rekey -init -key-shares=3 -key-threshold=2','Судьбу старых shares принимают после завершения и backup.')]),
c('vault operator rotate','Ротировать ключ шифрования новых storage-записей.','vault operator rotate','vault-04-keys'),
c('vault operator generate-root','Quorum-церемония аварийного восстановления административного API-доступа.','vault operator generate-root [ОПЦИИ]','vault-04-keys',[
f('-init','Начать принятую процедуру с OTP/PGP и nonce.','При потере/истечении оператора, в собственной среде.','vault operator generate-root -init','Команда не выдаёт готовый root без quorum; не автоматический helper.')]),
c('vault secrets enable','Подключить secrets engine к новому mount; влияет на сервер.','vault secrets enable [ОПЦИИ] ТИП','vault-07-kv',[
f('-path ПУТЬ','Выбрать свободный логический mount.','Создание secret/database/pki в своём стенде.','vault secrets enable -path=secret -version=2 kv','Не каталог Linux; существующий mount не перезаписывают.'),
f('-version N','Выбрать поддержанную версию KV.','Новый KVv2.','vault secrets enable -path=secret -version=2 kv','Не то же, что /v1/ в HTTP API; не обновляет существующий mount.')]),
c('vault secrets list','Прочитать список подключений engines и их опций.','vault secrets list [ОПЦИИ]','vault-07-kv',[
f('-detailed','Показать расширенную конфигурацию mount.','Выяснить версию KV и tune перед операцией.','vault secrets list -detailed','Имя secret само не доказывает KVv2.')],out=True),
c('vault secrets tune','Изменить сроки/параметры существующего mount.','vault secrets tune [ОПЦИИ] ПУТЬ','vault-08-leases',[
f('-max-lease-ttl ДЛИТЕЛЬНОСТЬ','Установить верхний предел срока mount.','При подготовке PKI CA и выдач.','vault secrets tune -max-lease-ttl=8760h pki-root','Role/issuer/запрос могут дополнительно ограничить фактическую выдачу.'),
f('-default-lease-ttl ДЛИТЕЛЬНОСТЬ','Настроить default срока.','После расчёта renewal-нагрузки.','vault secrets tune -default-lease-ttl=10m database','Не обещает мгновенно переписать каждый ранее выданный lease.')]),
c('vault policy write','Загрузить уже созданный HCL файл как серверную ACL policy.','vault policy write ИМЯ ФАЙЛ','vault-06-acl'),
c('vault token capabilities','Показать capabilities текущего token на реальном API-пути.','vault token capabilities ПУТЬ','vault-06-acl'),
c('vault token create','Выдать service token; результат хранить private, не в логе.','vault token create [ОПЦИИ]','vault-08-leases',[
f('-policy ИМЯ','Привязать policy; повторяемый флаг.','Создание ограниченного тестового reader.','vault token create -policy=handbook-reader -ttl=10m -format=json','Issuer должен иметь право выдать эти policies; имя не доказывает минимальность.'),
f('-ttl ДЛИТЕЛЬНОСТЬ','Запросить срок token.','Короткий native TTL test.','vault token create -policy=handbook-reader -ttl=3s','Фактическое время ограничено server/auth/role; результат содержит секрет.'),
f('-explicit-max-ttl ДЛИТЕЛЬНОСТЬ','Закрепить абсолютный lifetime token.','Ограниченный оператор личного stand.','vault token create -policy=handbook-operator -ttl=8h -explicit-max-ttl=24h','Renewal не обходит предел.'),
f('-orphan','Создать token без родителя при достаточном полномочии.','Отделить временного оператора перед отзывом bootstrap root.','vault token create -orphan -policy=handbook-operator -ttl=8h','Не отменяет TTL/direct revoke; приложения не получают вечный root.')],out=True),
c('vault token lookup','Прочитать metadata текущего token.','vault token lookup [ОПЦИИ]','vault-08-leases',out=True),
c('vault token renew','Попросить продлить token до фактически разрешённого срока.','vault token renew [ОПЦИИ]','vault-08-leases',[
f('-increment ДЛИТЕЛЬНОСТЬ','Запросить новый renewal increment.','До expiry и при renewable=true.','vault token renew -increment=30s','Не добавляет безусловно30s к прежнему TTL; actual lease_duration важнее запроса.')],out=True),
c('vault token revoke','Отозвать token и предусмотренное дерево доступа.','vault token revoke [ОПЦИИ]','vault-08-leases',[
f('-self','Отозвать предъявленный token без передачи его в argv.','Завершение bootstrap/root или сессии.','vault token revoke -self','Самоотзыв не стирает копии секретов и может отозвать детей/leases.')]),
c('vault kv put','Записать новую полную версию KV, с условием CAS при необходимости.','vault kv put [ОПЦИИ] КЛЮЧ ДАННЫЕ','vault-07-kv',[
MOUNT,f('-cas N','Сохранить только при ожидаемом текущем номере;0 означает ещё не существующий ключ.','Защита от конкурентного writer.','vault kv put -mount=secret -cas=1 handbook/config message=second','Mismatch даёт отказ400 и не меняет текущую версию; безусловный retry без CAS теряет защиту.')],out=True),
c('vault kv get','Прочитать текущее/конкретное KV-значение.','vault kv get [ОПЦИИ] КЛЮЧ','vault-07-kv',[
MOUNT,f('-version N','Выбрать сохранённую версию KVv2.','Проверка истории/soft-delete.','vault kv get -mount=secret -version=2 handbook/config','Destroyed/soft-deleted версия не выдаёт значение; current не обязательно эта версия.'),
f('-field ИМЯ','Вывести одно поле без trailing newline.','Защищённый частный канал потребителя.','vault kv get -mount=secret -field=message handbook/config','Флаг не обезличивает секрет; stdout защищают.')],out=True),
c('vault kv patch','Частично изменить существующее KVv2-значение; native PATCH отличается от read/write fallback.','vault kv patch [ОПЦИИ] КЛЮЧ ДАННЫЕ','vault-07-kv',[
MOUNT,f('-cas N','Условный PATCH известной версии.','Не затереть конкурентное обновление.','vault kv patch -mount=secret -cas=2 handbook/config added=yes','Новая версия сохраняет прежние непереданные поля.'),
f('-method МЕТОД','Выбрать patch или rw.','Явное сравнение CLI native PATCH и fallback.','vault kv patch -method=patch -mount=secret -cas=2 handbook/config added=yes','rw требует read+write и имеет другое окно гонки; основной опыт использует patch.')],out=True),
c('vault kv delete','Soft-delete текущую или выбранные KVv2 версии.','vault kv delete [ОПЦИИ] КЛЮЧ','vault-07-kv',[MOUNT,f('-versions СПИСОК','Выбрать номера KVv2 версий через запятую.','Удалить учебную version2, сохраняя возможность undelete.','vault kv delete -mount=secret -versions=2 handbook/config','Не destroy, не удаление всего mount.')]),
c('vault kv undelete','Снять soft-delete выбранных ещё существующих версий.','vault kv undelete [ОПЦИИ] КЛЮЧ','vault-07-kv',[MOUNT,f('-versions СПИСОК','Указать возвращаемые версии.','Проверить отличие от destroy.','vault kv undelete -mount=secret -versions=2 handbook/config','Не возвращает destroyed/вытесненные версии.')]),
c('vault kv destroy','Необратимо удалить содержимое выбранных версий через KV API.','vault kv destroy [ОПЦИИ] КЛЮЧ','vault-07-kv',[MOUNT,f('-versions СПИСОК','Выбрать уничтожаемые версии.','Только принятый учебный ключ.','vault kv destroy -mount=secret -versions=2 handbook/config','Metadata сохраняет destroyed=true; backup/внешние копии имеют отдельный lifecycle.')]),
c('vault kv metadata get','Прочитать версии и состояние KVv2 без запроса значения.','vault kv metadata get [ОПЦИИ] КЛЮЧ','vault-07-kv',[MOUNT],out=True),
c('vault auth enable','Подключить auth method к новому пути.','vault auth enable [ОПЦИИ] ТИП','vault-09-auth',[
f('-path ПУТЬ','Выбрать auth mount.','Своя AppRole роль.','vault auth enable -path=approle approle','Подключение не создаёт автоматически role/SecretID.')]),
c('vault auth list','Исследовать подключённые auth methods.','vault auth list [ОПЦИИ]','vault-09-auth',out=True),
c('vault write','Вызвать endpoint записи; чувствительные данные передавать из private @JSON, а не в argv.','vault write [ОПЦИИ] ПУТЬ [ДАННЫЕ]','vault-09-auth',[
f('-f / -force','Разрешить write без данных.','Генерация SecretID/rotate-root на endpoint с такой семантикой.','vault write -wrap-ttl=60s -f auth/approle/role/handbook/secret-id','Это разрешение пустого запроса, не универсальный обход ACL.'),
f('-wrap-ttl ДЛИТЕЛЬНОСТЬ','Вернуть ограниченную однократную обёртку ответа.','Безопасная доставка SecretID.','vault write -wrap-ttl=60s -f auth/approle/role/handbook/secret-id','Сам wrapping token тоже secret; проверяют creation_path и одноразовый unwrap.')],out=True),
c('vault read','Вызвать read endpoint; динамический creds read имеет побочный эффект выдачи.','vault read [ОПЦИИ] ПУТЬ','vault-10-postgresql',out=True),
c('vault list','Запросить LIST поддержанного endpoint, не GET содержимого.','vault list [ОПЦИИ] ПУТЬ','vault-06-acl',out=True),
c('vault login','Войти через настроенный auth method; не сохранять token в host HOME.','vault login [ОПЦИИ]','vault-09-auth',[
f('-method ИМЯ','Выбрать настроенный метод, например oidc/cert.','После подготовки обеих сторон trust.','vault login -method=oidc -no-store','OIDC требует зарегистрированный callback/issuer; это не первый bootstrap.'),
f('-no-store','Не писать полученный token в token helper.','Личный ручной login без ~/.vault-token.','vault login -method=oidc -no-store','Вывод всё ещё содержит credential; учебный helper использует API без печати.')]),
c('vault unwrap','Однократно извлечь wrapped response с предъявленным wrapping token.','vault unwrap','vault-09-auth'),
c('vault agent','Запустить Agent auto-auth/templates по созданной конфигурации.','vault agent -config ФАЙЛ','vault-12-agent-go',[
f('-config ФАЙЛ','Прочитать конфигурацию Agent.','Файлы role-id/нового SecretID уже доставлены private.','vault agent -config /home/student/handbook-vault/private/agent.hcl','exit_after_auth в учебном config проверяет one-shot, а не длительный renewal.')],http=False),
c('vault audit enable','Включить устройство аудита; путь должен быть доступен server UID.','vault audit enable [ОПЦИИ] ТИП [ДАННЫЕ]','vault-14-audit'),
c('vault audit list','Прочитать уже включённые audit devices.','vault audit list [ОПЦИИ]','vault-14-audit',[f('-detailed','Показать опции устройства.','Проверка file_path/mode без повторного enable.','vault audit list -detailed','Журналы и ключи HMAC сюда не копируются.')],out=True),
c('vault operator raft list-peers','Прочитать voters/leader текущего Raft peer set.','vault operator raft list-peers','vault-13-raft'),
c('vault operator raft snapshot save','Создать согласованный экспорт Raft на частный путь.','vault operator raft snapshot save ФАЙЛ','vault-15-recovery'),
c('vault operator raft snapshot restore','Импортировать snapshot в явно выбранную цель; операция меняет state.','vault operator raft snapshot restore [ОПЦИИ] ФАЙЛ','vault-15-recovery',[
f('-force','Пропустить проверку соответствия seal snapshot текущему target.','Только новый отдельный target лаборатории с source shares.','vault operator raft snapshot restore -force /private/checkpoint-v3.snap','Не универсальное исправление failed restore; после импорта нужны ключи SOURCE, target данные заменены.')]),
]
