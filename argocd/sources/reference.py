"""Original glossary/cards. Actual help: Argo CD 3.5.6, 2026-11-01."""
GLOSSARY=[
('GitOps','Подход, при котором версионируемое желаемое состояние получается из доверенного источника, а контроллер сравнивает его с фактом и по политике согласует ресурсы.'),
('Continuous Delivery','Непрерывная доставка: подготовка и управляемый перенос проверенного изменения к исполнению. Не равна обязательному автоматическому выпуску каждого коммита.'),
('Argo CD','Контроллер и интерфейсы доставки приложений в Kubernetes из декларативного источника. Не компилирует автоматически Go и не заменяет Kubernetes.'),
('CLI','Command Line Interface — интерфейс командной строки. Оболочка передаёт массив строк argv, а конкретная программа разбирает их по собственной грамматике.'),
('API','Application Programming Interface — программный интерфейс. API Argo и Kubernetes имеют разные адреса, личности и правила доступа.'),
('Commit','Коммит Git фиксирует дерево файлов и родителей. Полная ревизия конфигурации отличается от дайджеста контейнерного образа.'),
('Desired state','Желаемое состояние: вычисленный набор объектов и полей, которые должен поддерживать контроллер. Не равно исходным файлам до рендеринга.'),
('Live state','Фактическое наблюдаемое состояние API. Имеет возраст кэша и может содержать поля, добавленные сервером или другими контроллерами.'),
('Reconciliation','Согласование состояния: повторяемый цикл наблюдения, сравнения и разрешённой корректировки. Не является общей транзакцией ресурсов и БД.'),
('Drift','Дрейф — отличие фактических объектов от требуемых. Для корректировки нужен определённый владелец и разрешённая политика.'),
('Application','API-объект Argo с источником, назначением, проектом, политикой и наблюдаемым состоянием приложения.'),
('AppProject','Граница разрешённых источников, кластеров, пространств имён и видов ресурсов для приложений. Не заменяет Kubernetes RBAC.'),
('ApplicationSet','Объект генерации дочерних Application по списку входов и шаблону. Его жизненный цикл может вызвать удаление дочерних приложений и ресурсов.'),
('Spec','Желаемая спецификация API-объекта. Статус контроллера хранится отдельно и не должен редактироваться как желаемая конфигурация.'),
('Status','Наблюдение и результат работы контроллера: сравнение, здоровье, условия ошибок и операция. Это не резервная копия данных приложения.'),
('Operation','Запрос и исполнение действия Argo, например синхронизации. Частичный успех API-запросов может пережить ошибку всей операции.'),
('Sync','Синхронизация вычисленного целевого набора с API. Её успех не заменяет проверку бизнес-операции приложения.'),
('Synced','Сравниваемое представление соответствует желаемому согласно правилам нормализации. Приложение при этом может быть нездоровым.'),
('OutOfSync','Наблюдается различие желаемого и фактического набора. Само состояние не является разрешением автоматически изменить кластер.'),
('Health','Оценка работоспособности ресурса по наблюдаемым полям и правилам. Отдельна от совпадения манифестов и точного HTTP-результата.'),
('Healthy','Ресурс соответствует своей проверке здоровья. Не доказывает бизнес-корректность за пределами этого правила.'),
('Degraded','Оценка ухудшенного состояния ресурса, например неуспешного продвижения Deployment. Не означает, что все старые Pod уже перестали обслуживать трафик.'),
('Progressing','Контроллер считает, что ресурс ещё движется к готовности. Причина может быть нормальным стартом или внешним ограничением.'),
('Repo-server','Компонент получения исходников и генерации манифестов. Его CPU, диск, сеть, доверие и учётные данные отделены от приложения.'),
('Application-controller','Контроллер наблюдения приложений/кластеров, сравнения, здоровья и операций. Продолжает работать без открытого браузера.'),
('Redis','Ускоряющее хранилище кэша соответствующих компонентов Argo. Не является вымышленной обязательной SQL-базой достоверного состояния.'),
('Dex','Компонент объединения внешних способов входа. Может использоваться для SSO, но не обязателен при каждой прямой OIDC-схеме.'),
('SSO','Single Sign-On — единый вход через доверенного поставщика личности. Успешная аутентификация не означает административных разрешений.'),
('OIDC','OpenID Connect — протокол идентификации поверх OAuth2. Группы/субъекты из claims должны сопоставляться ограниченным ролям.'),
('RBAC','Role-Based Access Control — разрешения через роли. Argo RBAC и Kubernetes RBAC проверяются разными системами.'),
('Casbin policy','Форма правил доступа Argo: строки p описывают разрешение/запрет, g связывают субъект с ролью. Локальная проверка полезна до применения.'),
('Default role','Роль по умолчанию, права которой получают вошедшие пользователи. Чрезмерно широкие исходные права нельзя считать безопасно ограниченными последующими ролями.'),
('Kubeconfig','Файл кластеров, личностей и контекстов Kubernetes. Может запускать доверенную программу получения токена; не совпадает с конфигурацией сеанса CLI Argo.'),
('Argo context','Именованное подключение CLI к Argo API, выбираемое --argocd-context. Отличается от --context у kubectl/admin-команд.'),
('Namespace','Пространство имён Kubernetes отделяет имена и область ряда прав. Не гарантирует полной изоляции и не ограничивает общие CRD само по себе.'),
('CRD','CustomResourceDefinition — определение собственного API Kubernetes. Удаление может уничтожить все его экземпляры, включая приложения нескольких владельцев.'),
('Manifest','Манифест — документ API-объекта. Исходный текст и нормализованное сравниваемое представление могут различаться.'),
('Rendering','Рендеринг — получение манифестов выбранным инструментом и параметрами. Не равен допуску API или выполнению синхронизации.'),
('Helm rendering','Исполнение шаблонов chart для получения текста. Argo обычно управляет результатом сам и не создаёт обычную Helm-историю релиза.'),
('Kustomize','Преобразование структурированных манифестов через базу, генераторы и наборы изменений. Версия инструмента влияет на вычисленные байты.'),
('ConfigMap generator','Механизм Kustomize, создающий ConfigMap с суффиксом хеша и обновляющий известные ссылки. Изменение ссылки меняет шаблон Pod.'),
('Multi-source application','Приложение с несколькими источниками. Порядок источников и повторяющиеся идентичности объектов могут влиять на окончательный набор.'),
('Normalization','Нормализация — приведение сравниваемых объектов по правилам Argo и API. Не тождественна простому git diff двух YAML-файлов.'),
('IgnoreDifferences','Исключение отдельных различий из сравнения. По умолчанию не означает, что применяемое поле вообще перестало управляться Argo.'),
('Server-side diff','Сравнение с участием серверного пробного применения. Требует API и совместимых разрешений; не является локальным Kustomize build.'),
('SSA','Server-Side Apply — серверное применение с принадлежностью полей управляющим. В выбранном Argo используется с force-conflicts по проверенному исходнику/документации.'),
('ManagedFields','Kubernetes-метаданные управляющих полями. Конфликт полей отличается от идентичности владельца Application.'),
('Self-heal','Автоматическое исправление управляемого дрейфа обратно к желаемому состоянию. Не ремонтирует физический диск или внешнюю БД.'),
('Prune','Удаление управляемых ресурсов, отсутствующих в желаемом наборе. Отдельно разрешается для операции или автоматической политики.'),
('AllowEmpty','Разрешение пустого целевого набора при соответствующей автоматической синхронизации. Не следует включать как лечение ошибки генерации.'),
('Sync window','Окно политики, разрешающее либо запрещающее синхронизацию по расписанию и условиям. Не является гарантией прикладной доступности.'),
('Selective sync','Синхронизация явно выбранных ресурсов, не полного приложения. Hooks не выполняются, история имеет ограничения; отличается от ApplyOutOfSyncOnly.'),
('ApplyOutOfSyncOnly','Опция синхронизации только отличающихся ресурсов полного приложения. В 3.5 обработчики всё ещё выполняются и операция записывается в историю.'),
('Sync phase','Фаза PreSync/Sync/PostSync/SyncFail и других поддержанных событий. Сначала выбирается фаза, затем волна и порядок ресурсов.'),
('Sync wave','Числовая волна порядка внутри фазы. Меньшая идёт раньше; здоровье ранней волны может заблокировать продвижение.'),
('Hook','Ресурс специальной фазы Argo, часто Job. Удаление объекта обработчика не отменяет внешние действия мигратора.'),
('Hook deletion policy','Правило удаления обработчика до повторного создания, после успеха или ошибки. Не является откатом данных.'),
('Tracking annotation','Аннотация argocd.argoproj.io/tracking-id, связывающая ресурс с приложением. В 3.5 аннотационный метод является основным по умолчанию.'),
('Installation ID','Идентификатор установки Argo для различения управляющих контуров в одном кластере. Не делает безопасным совместное управление одним полем.'),
('Finalizer','Финализатор задерживает окончательное удаление объекта до работы ответственного контроллера. Не является резервной копией.'),
('OwnerReferences','Ссылки владельца Kubernetes для сборки мусора. ApplicationSet использует их для дочерних Application; они не равны tracking-id прикладного ресурса.'),
('Replace','Замена объекта вместо обычного применения полей. Может менять доступность и требует понимания неизменяемых полей/идентичности.'),
('Force','Принудительный способ применения с риском удаления и пересоздания. Не является универсальной починкой любого конфликта.'),
('Repository credentials','Учётные данные чтения Git/Helm/OCI-источника repo-server. Отличаются от пароля пользователя UI и imagePullSecret узла.'),
('Known hosts','Доверенные SSH-ключи сервера. Автоматически увиденный ключ без независимой проверки не устанавливает доверия.'),
('TLS','Transport Layer Security — защита канала и проверка личности сервера. Разные каналы могут иметь разные доверенные CA.'),
('CA','Certification Authority — удостоверяющая сторона/материал доверия сертификатам. Корневые сертификаты клиента, repo-server и узла независимы.'),
('SAN','Subject Alternative Name — допустимые имена/адреса сертификата. Доверенный сертификат с другим именем всё равно не проходит проверку адреса.'),
('gRPC','Протокол удалённых вызовов, используемый CLI Argo. Прокси должен поддерживать нужный транспорт; gRPC-web является отдельным адаптером.'),
('OCI','Open Container Initiative — семейство форматов и протоколов артефактов. OCI-source Argo и Helm OCI chart имеют разные правила задания пути/ревизии.'),
('Image digest','Идентификатор содержимого манифеста контейнерного образа. Не равен Git-коммиту конфигурации или версии chart.'),
('SHA-256','Хеш содержимого в 256 бит. Проверяет байты относительно доверенного ожидания, не сам по себе полномочия издателя.'),
('Cosign','Инструмент подписания/проверки артефактов. Проверка требует доверенной личности издателя и параметров цепочки сертификатов.'),
('Provenance','Сведения о том, какими входами и процессом создан артефакт. Хеш, подпись и смысл процесса сборки — разные доказательства.'),
('SLSA','Supply-chain Levels for Software Artifacts — требования к защищённости цепочки сборки. Уровень не анализирует прикладные полномочия манифеста.'),
('HA','High Availability — высокая доступность при заданных отказах. Реплики контроллера, Redis и приложения решают разные задачи.'),
('Sharding','Разделение работы между экземплярами контроллера, например по кластерам. Не равно репликации всех данных в общую SQL-базу.'),
('Cache','Кэш повторно используемых результатов/наблюдений. Возраст и ключи важны; не заменяет источник и согласованную резервную копию.'),
('Webhook','Веб-обработчик уведомления об изменении. Ускоряет проверку источника, но не заменяет получение доверенной ревизии.'),
('Polling','Периодический опрос источника. Интервал и случайная добавка влияют на задержку обнаружения и нагрузку.'),
('RSS','Resident Set Size — резидентная память процесса. Не равна всему размеру Git-репозитория или одной куче Go.'),
('QPS','Queries Per Second — запросы в секунду в заданной границе. Ограничение клиента и ёмкость API-сервера не одинаковы.'),
('RPO','Recovery Point Objective — допустимая потеря последних данных по времени. Git и export Argo не заменяют резерв БД/PVC.'),
('RTO','Recovery Time Objective — допустимое время возврата услуги, включая инструменты, доступ, данные и прикладную приёмку.'),
('Rollback','Откат к прежним входам/истории. При включённом autosync обычный rollback приложения запрещён; Git остаётся источником будущего согласования.'),
('Idempotence','Идемпотентность — повтор действия без нежелательного дополнительного эффекта. Не следует предполагать её у миграции БД или внешнего API.'),
('Offline bundle','Подготовленный комплект байтов и инструментов. Чтение HTML офлайн, работа без Git и повторная установка без сети — разные режимы.'),
]
def flag(label,action,when,example,result):return dict(flag=label,action=action,when=when,example=example,result=result)
def command(name,purpose,syntax,chapter,flags=(),aliases=(),persistent=False):
 url='https://argo-cd.readthedocs.io/en/release-3.5/user-guide/commands/'+name.replace(' ','_')+'/'
 c=dict(name=name,purpose=purpose,syntax=syntax,chapter=chapter,volume='argocd',source=url,
  sources=[dict(title='Официальная справка 3.5; реальный CLI 3.5.6 проверен 01.11.2026',url=url)],
  aliases=list(aliases),flags=list(flags),situations=[])
 if persistent:c['persistentOptions']=True
 return c
COMMANDS=[
command('argocd','CLI выбранного Argo CD3.5.6. Серверное подключение Argo и Kubernetes-доступ admin-команд различаются.','argocd [ГЛОБАЛЬНЫЕ_ФЛАГИ] КОМАНДА','argocd-02-distribution',[
 flag('--config ФАЙЛ','Выбрать частный файл сеанса клиента.','Не читать/менять общий клиентский профиль.','argocd --config "$LAB_ROOT/private/argocd-config" app list','Чувствительный сеанс хранится вне Git; локальные тесты выбирают отдельный пустой путь.'),
 flag('--argocd-context ИМЯ','Выбрать именованное подключение к Argo API.','После login --name handbook.','argocd --config "$LAB_ROOT/private/argocd-config" --argocd-context handbook app get ledger-gitops','Это не Kubernetes --context.'),
 flag('--server АДРЕС','Указать сервер Argo API.','Прямое подключение без выбора сохранённого имени.','argocd --server localhost:8443 --config "$LAB_ROOT/private/argocd-config" app list','В admin-командах с флагами Kubernetes локальный --server затеняет это значение.'),
 flag('--server-crt ФАЙЛ','Использовать доверенный сертификат сервера.','Проверенный сертификат локального либо другого собственного адреса сервера.','argocd --server-crt "$LAB_ROOT/private/server.crt" login localhost:8443 --name handbook','Имя сертификата тоже должно соответствовать адресу.'),
 flag('--grpc-web','Выбрать gRPC-web при соответствующем прокси.','Прокси не пропускает обычный HTTP/2 gRPC.','argocd --grpc-web --argocd-context handbook app list','Меняет транспорт клиента,не исправляет пароль/TLS/политику проекта.'),
 flag('--core','Работать через Kubernetes вместо обычного Argo API.','Отдельная Core-модель с собственными правами.','argocd --core --kube-context handbook-admin app list','Не означает отсутствие полномочий и не является обычным login профилем.'),
 flag('--kube-context ИМЯ','Выбрать Kubernetes context для применимого режима core/port-forward.','Явный личный кластер.','argocd --core --kube-context handbook-admin app list','Admin-команды также имеют собственный --context; не заменять один флаг другим механически.'),
 flag('--insecure','Отключить проверку сертификата/домена Argo API.','Только осознанная диагностическая альтернатива с понятной границей.','argocd --insecure login localhost:8443','Ослабляет доверие;основная линия использует --server-crt.'),
 flag('--plaintext','Отключить TLS транспорта Argo API.','Только отдельно подготовленная личная схема.','argocd --plaintext --server localhost:8080 app list','Не является синонимом --insecure и не используется для обычного HTTPS.'),
 flag('--loglevel УРОВЕНЬ','Выбрать debug/info/warn/error.','Короткая диагностика с защищённым выводом.','argocd --loglevel debug --argocd-context handbook app get ledger-gitops','Больше деталей не доказывает здоровье и может раскрывать адреса/параметры.')],persistent=True),
command('argocd version','Показать версию клиента и при запросе сервер.','argocd version [ФЛАГИ]','argocd-02-distribution',[
 flag('--client','Ограничить проверку клиентом.','Проверка исполняемого файла до подключения к API.','argocd version --client --short','Реально выполнено;не доказывает установленный сервер.'),
 flag('--short','Сократить представление.','Записать фактическую версию.','argocd version --client --short','Ожидается argocd:v3.5.6+c2b1e30.')]),
command('argocd login','Войти на свой сервер и сохранить сеанс в выбранный --config.','argocd login СЕРВЕР [ФЛАГИ]','argocd-03-install',[
 flag('--name ИМЯ','Назвать подключение клиента.','Различать handbook и другие сервера.','argocd --config "$LAB_ROOT/private/argocd-config" login localhost:8443 --name handbook','Позднее выбирается --argocd-context handbook.'),
 flag('--username ИМЯ','Выбрать локального пользователя;пароль вводится интерактивно.','Первый admin-вход своего стенда.','argocd login localhost:8443 --username admin','Не помещайте пароль в argv/пример журнала.'),
 flag('--sso','Войти через настроенный единый вход.','Уже подготовлены OIDC/Dex и разрешённый клиент.','argocd login argocd.example.invalid --sso','Placeholder адреса не является готовой службой;после входа права проверяются отдельно.')]),
command('argocd logout','Удалить сохранённое подключение/сеанс клиента к указанному серверу.','argocd logout СЕРВЕР','argocd-13-access'),
command('argocd context','Показать либо переключить именованное подключение Argo в выбранном файле.','argocd context [ИМЯ]','argocd-13-access',aliases=['argocd ctx']),
command('argocd account update-password','Сменить пароль локальной учётной записи с достаточными правами.','argocd account update-password [ФЛАГИ]','argocd-03-install',[
 flag('--account ИМЯ','Выбрать пользователя вместо текущего.','Осознанное управление своей учётной записью.','argocd account update-password --account admin','Основной рецепт вводит пароли интерактивно;это серверная операция.')]),
command('argocd account can-i','Проверить право текущего сеанса на сервере.','argocd account can-i ДЕЙСТВИЕ РЕСУРС ОБЪЕКТ','argocd-13-access'),
command('argocd account generate-token','Создать токен разрешённой локальной учётной записи.','argocd account generate-token [ФЛАГИ]','argocd-13-access',[
 flag('--account ИМЯ','Выбрать разрешённую учётную запись.','Отдельная учётка CI с минимальной ролью.','argocd account generate-token --account ci-reader --expires-in 1h','Токен является секретом; его не включают в публичный вывод или журнал.'),
 flag('--expires-in ДЛИТЕЛЬНОСТЬ','Ограничить срок токена.','Краткоживущая автоматизация.','argocd account generate-token --account ci-reader --expires-in 1h','Истечение/отзыв планируют отдельно от сохранённого Git-доступа repo-server.')]),
command('argocd admin initial-password','Прочитать первый пароль из Secret пространства имён собственной установки Argo.','argocd admin initial-password [ФЛАГИ]','argocd-03-install',[
 flag('--kubeconfig ФАЙЛ','Выбрать явный Kubernetes kubeconfig.','Первый вход собственного стенда.','argocd admin initial-password --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" --namespace argocd','Требуется право читать начальный Secret;вывод чувствительный.'),
 flag('--context ИМЯ','Выбрать Kubernetes context этой admin-команды.','Не полагаться на общий current-context.','argocd admin initial-password --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" --namespace argocd','Не --argocd-context:сеанса Argo ещё может не быть.'),
 flag('-n ИМЯ / --namespace ИМЯ','Выбрать пространство имён управляющей установки.','Читать пароль нужной установки.','argocd admin initial-password --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n argocd','Namespace приложения gitops-lab здесь неверен.')]),
command('argocd app create','Создать Application через Argo API;не является локальным рендерингом.','argocd app create ИМЯ [ФЛАГИ]','argocd-05-application',[
 flag('-f ФАЙЛ / --file ФАЙЛ','Прочитать подготовленный Application.','После configure.py и создания AppProject.','argocd app create ledger-gitops --file "$LAB_ROOT/bootstrap-initial/application.yaml"','Файл проверяемый;API всё равно требует доступ/права. В основном рецепте используется kubectl apply того же объекта.'),
 flag('--repo URL','Указать источник.','Альтернативная явная сборка спецификации.','argocd app create ledger-gitops --repo "$LAB_REPO_URL" --path apps/ledger/overlays/lab --revision "$LAB_COMMIT" --dest-server https://kubernetes.default.svc --dest-namespace gitops-lab --project ledger','URL сам по себе не содержит учётных данных и не устанавливает доверие к серверу.'),
 flag('--revision РЕВИЗИЯ','Выбрать коммит/tag/branch или версию chart соответствующего источника.','Первое приложение закрепляет полный Git коммит.','argocd app create ledger-gitops --file "$LAB_ROOT/bootstrap-initial/application.yaml" --revision "$LAB_COMMIT"','Плавающая ветка и неизменяемый коммит имеют разную модель обновления.'),
 flag('--project ИМЯ','Выбрать AppProject.','Ограниченный проект ledger вместо широкого проекта default.','argocd app create ledger-gitops --file "$LAB_ROOT/bootstrap-initial/application.yaml" --project ledger','Проект не создаёт namespace и не заменяет Kubernetes RBAC.')]),
command('argocd app get','Получить состояние,условия и описание приложения через сервер.','argocd app get ИМЯ [ФЛАГИ]','argocd-07-diff-health',[
 flag('--refresh','Запросить обновлённое наблюдение.','Проверить новый Git/наблюдаемый факт.','argocd app get ledger-gitops --refresh --output yaml','Не равно принудительному пересозданию всех объектов.'),
 flag('--hard-refresh','Обновить данные с очисткой кэша целевых манифестов.','Исследовать устаревший результат генерации.','argocd app get ledger-gitops --hard-refresh --output yaml','Дороже обычного refresh;не исправляет неповторяемые входы.'),
 flag('-o ФОРМАТ / --output ФОРМАТ','Выбрать yaml/json/wide и поддержанные представления.','Сохранить структурированное наблюдение.','argocd app get ledger-gitops --output yaml','Наблюдение, оценку здоровья и результат операции читают раздельно.')]),
command('argocd app list','Перечислить доступные приложения выбранного сервера.','argocd app list [ФЛАГИ]','argocd-18-diagnostics',[
 flag('-p ПРОЕКТ / --project ПРОЕКТ','Ограничить проект.','Смотреть только ledger.','argocd app list --project ledger','Отсутствие строки может быть следствием RBAC/фильтра.'),
 flag('-o ФОРМАТ / --output ФОРМАТ','Выбрать формат.','Сохранить наблюдения без скриншотов.','argocd app list --project ledger --output json','Это список Application,не полный список Pod.')]),
command('argocd app set','Изменить спецификацию Application через API.','argocd app set ИМЯ [ФЛАГИ]','argocd-08-sync',[
 flag('--revision РЕВИЗИЯ','Изменить отслеживаемую ревизию.','Явно перейти с коммита C1 на C2 либо на свою защищённую ветку main.','argocd app set ledger-gitops --revision "$LAB_NEXT_COMMIT"','При pinned коммит один новый push сам не меняет желаемый набор.'),
 flag('--sync-policy ПОЛИТИКА','Указать automated/manual по грамматике CLI.','Изменить разрешение автоматического применения.','argocd app set ledger-gitops --sync-policy manual','Для ApplicationSet-детей источник изменения может перезаписать ручную настройку.'),
 flag('--self-heal','Разрешить исправление управляемого дрейфа.','После осознанного принятия автоматической политики.','argocd app set ledger-gitops --sync-policy automated --self-heal','Не ремонтирует БД/узел и не означает prune.'),
 flag('--auto-prune','Разрешить автоматическое удаление исчезнувших ресурсов.','После проверки перечня удаляемых ресурсов и сохранности их данных.','argocd app set ledger-gitops --sync-policy automated --auto-prune','Отдельный риск удаления;основной первый режим оставляет false.'),
 flag('--allow-empty','Разрешить пустой автоматический целевой набор.','Осознанное полное удаление при корректной генерации.','argocd app set ledger-gitops --allow-empty','Не лечит ошибку repo-server и не включается автоматически.')]),
command('argocd app manifests','Получить вычисленные целевые либо живые манифесты через Argo API.','argocd app manifests ИМЯ [ФЛАГИ]','argocd-06-render',[
 flag('--revision РЕВИЗИЯ','Получить целевой набор конкретной ревизии.','Сравнить C1/C2.','argocd app manifests ledger-gitops --revision "$LAB_COMMIT"','Использует сервер и его средство генерации/cache;не локальный Helm template.'),
 flag('--source ИСТОЧНИК','Выбрать git либо наблюдаемый по CLI.','Отличить желаемое от наблюдаемого.','argocd app manifests ledger-gitops --source live','Данные могут раскрывать Secret;живое состояние не тождественно Git.')]),
command('argocd app diff','Сравнить приложение с живым состоянием через сервер;обычный текстовый git diff этого не заменяет.','argocd app diff ИМЯ [ФЛАГИ]','argocd-07-diff-health',[
 flag('--local КАТАЛОГ','Использовать локальные манифесты как один вход сравнения.','Сравнить рабочий вариант с состоянием существующего Application.','argocd app diff ledger-gitops --local ./rendered','Всё ещё нужен сервер/наблюдаемый app;не офлайн-движок сравнения.'),
 flag('--revision РЕВИЗИЯ','Сравнить наблюдаемый набор ресурсов с выбранной ревизией.','Проверить будущую или историческую цель.','argocd app diff ledger-gitops --revision "$LAB_NEXT_COMMIT"','Не применяет автоматически;проверка зависит от состояния сервера.'),
 flag('--diff-exit-code ЧИСЛО','Выбрать код при обнаруженном различии.','Отличить ожидаемый diff от ошибки в автоматизации.','argocd app diff ledger-gitops --diff-exit-code 10','0 — нет различий;код различия и общий error надо обрабатывать отдельно.'),
 flag('--server-side-diff','Сравнивать с серверным применением Kubernetes.','Уже подготовлены API и разрешения.','argocd app diff ledger-gitops --server-side-diff','Это не локальный dry-run и не гарантия прикладного успеха.')]),
command('argocd app sync','Запросить операцию синхронизации приложения на сервере.','argocd app sync ИМЯ [ФЛАГИ]','argocd-08-sync',[
 flag('--dry-run','Предварительно выполнить предусмотренную серверную операцию без штатного изменения.','Просмотреть результат против существующего приложения.','argocd app sync ledger-gitops --dry-run','Требует Argo и Kubernetes; локальная генерация файлов эту операцию не выполняет.'),
 flag('--prune','Разрешить удаление лишних управляемых объектов.','Осознанная очистка после сравнения.','argocd app sync ledger-gitops --prune --timeout 180','Не восстанавливает данные удалённого объекта;контроль namespace/ownership обязателен.'),
 flag('--resource ОБЪЕКТ','Ограничить выбор GROUP:KIND:NAME,возможны отрицание и namespace.','Выборочное применение с пониманием отсутствия обработчиков hooks.','argocd app sync ledger-gitops --resource apps:Deployment:ledger-gitops','Это выборочная синхронизация без полного протокола приложения.'),
 flag('--apply-out-of-sync-only','Применять только отличающиеся ресурсы полной синхронизации.','Снизить число API-изменений большого набора.','argocd app sync ledger-gitops --apply-out-of-sync-only','В 3.5 обработчики hooks продолжают выполняться, история сохраняется; не равно --resource.'),
 flag('--server-side','Выбрать серверное применение.','Осознанный SSA после проверки владельцев полей.','argocd app sync ledger-gitops --server-side','Выбранная реализация использует force-conflicts;это существенная передача полей.'),
 flag('--replace','Использовать create/replace вместо обычного apply.','Понятны неизменяемые поля и доступность.','argocd app sync ledger-gitops --replace --dry-run','Replace имеет приоритет над SSA и может менять последствия.'),
 flag('--force','Принудительное применение по правилам Argo.','Только явно разобранное удаление/пересоздание.','argocd app sync ledger-gitops --force --dry-run','Не универсальная починка;Job/данные требуют отдельного протокола.'),
 flag('--timeout СЕКУНДЫ','Ограничить ожидание CLI числом секунд.','Сравнение операций с одинаковым бюджетом.','argocd app sync ledger-gitops --timeout 180','Это uint seconds,не Helm duration180s;ошибка ожидания не отменяет уже выполненные действия.'),
 flag('--async','Вернуться после запуска операции без ожидания.','Наблюдать отдельно app wait/get.','argocd app sync ledger-gitops --async','Выход CLI ещё не доказывает завершения.'),
 flag('--retry-limit ЧИСЛО','Задать предел повторов операции.','Диагностированная временная ошибка.','argocd app sync ledger-gitops --retry-limit 3 --retry-backoff-duration 5s --retry-backoff-max-duration 30s','Повтор не делает мигратор идемпотентным.'),
 flag('--retry-refresh','Использовать новую ревизию на повторе по политике.','Разрешённая смена ревизии при повторе операции.','argocd app sync ledger-gitops --retry-limit 3 --retry-refresh','Это уже не повтор тех же неизменяемых входов.')]),
command('argocd app wait','Дождаться выбранных наблюдаемых состояний существующего приложения.','argocd app wait ИМЯ [ФЛАГИ]','argocd-07-diff-health',[
 flag('--sync','Ожидать совпадения целевого набора.','После запрошенной полной синхронизации.','argocd app wait ledger-gitops --sync --health --timeout 180','Добавление --health требует отдельного здоровья,не только совпадения.'),
 flag('--health','Ожидать здоровья.','Проверить второй критерий операции.','argocd app wait ledger-gitops --health --timeout 180','Не выполняет HTTP-бизнес-тест.'),
 flag('--timeout СЕКУНДЫ','Задать число секунд.','Ограниченное наблюдение личного стенда.','argocd app wait ledger-gitops --sync --health --timeout 180','Не строка 180s;истечение не отменяет приложение.')]),
command('argocd app history','Прочитать историю успешных доставок приложения.','argocd app history ИМЯ','argocd-14-recovery'),
command('argocd app rollback','Запросить откат к ID истории при допустимой политике.','argocd app rollback ИМЯ ID [ФЛАГИ]','argocd-14-recovery',[
 flag('--prune','Разрешить удаление при откате.','Обдуманная судьба ресурсов прошлой версии.','argocd app rollback ledger-gitops 1 --prune','При включённой автоматической синхронизации откат через rollback запрещён; данные не возвращаются автоматически.')]),
command('argocd app terminate-op','Прекратить текущую операцию;не вернуть автоматически прежние данные.','argocd app terminate-op ИМЯ','argocd-18-diagnostics'),
command('argocd app delete','Удалить Application с явно выбранной судьбой управляемых ресурсов.','argocd app delete ИМЯ [ФЛАГИ]','argocd-10-ownership',[
 flag('--cascade','Управлять каскадным удалением;исходный true.','Разобрать судьбу приложения перед финальной очисткой.','argocd app delete ledger-gitops --cascade=false','Сравните с true:сохранение ресурсов не равно удалению finalizer вслепую.'),
 flag('-p ПОЛИТИКА / --propagation-policy ПОЛИТИКА','Выбрать foreground/background удаления ресурсов.','Ожидаемая обработка finalizer/дочерних объектов.','argocd app delete ledger-gitops --cascade=true --propagation-policy foreground --wait','Это реальные API-удаления;не выполняются в локальных тестах.'),
 flag('--wait','Дождаться удаления приложения.','Финальная проверка жизненного цикла.','argocd app delete ledger-gitops --cascade=false --wait','Не означает физического удаления внешней БД/PV.')]),
command('argocd repo add','Зарегистрировать источник и его доступ для repo-server.','argocd repo add URL [ФЛАГИ]','argocd-12-repositories',[
 flag('--ssh-private-key-path ФАЙЛ','Прочитать свой ключ доступа SSH.','Минимальный read-only deploy key.','argocd repo add "$LAB_REPO_SSH_URL" --ssh-private-key-path "$LAB_ROOT/private/repo-key"','Ключ не помещают в Git;known_hosts проверяется отдельно.'),
 flag('--type ТИП','Выбрать тип источника,например helm.','Отличить chart repository от Git.','argocd repo add registry.example.invalid/handbook --type helm --enable-oci','Адресplaceholder,не реальный push;Argo читает источник.'),
 flag('--enable-oci','Включить OCI-режим Helm repository.','Для зарегистрированного Helm OCI источника.','argocd repo add registry.example.invalid/handbook --type helm --enable-oci','Не путать с отдельным универсальным источником oci:// и imagePullSecrets для получения образов узлами.')]),
command('argocd repo list','Показать зарегистрированные доступные источники и состояние связи.','argocd repo list','argocd-12-repositories'),
command('argocd repo get','Прочитать регистрацию/состояние источника.','argocd repo get URL','argocd-12-repositories'),
command('argocd repo rm','Удалить регистрацию репозитория из своего Argo,не исходники Git.','argocd repo rm URL','argocd-12-repositories'),
command('argocd cluster list','Показать доступные Argo назначения.','argocd cluster list','argocd-13-access'),
command('argocd cluster add','Добавить кластер;может создавать привилегированные учётные объекты в нём. В основной same-cluster линии не требуется.','argocd cluster add KUBE_CONTEXT [ФЛАГИ]','argocd-13-access',[
 flag('--kubeconfig ФАЙЛ','Выбрать отдельный kubeconfig добавляемого личного кластера.','Только явно разрешённая регистрация.','argocd cluster add handbook-admin --kubeconfig "$LAB_KUBECONFIG" --namespace gitops-lab','Это не просто чтение файла;оценить создаваемый service account/роль.'),
 flag('--namespace ИМЯ','Ограничить заявленную область управляемых namespaces.','Минимальное назначение.','argocd cluster add handbook-admin --kubeconfig "$LAB_KUBECONFIG" --namespace gitops-lab','Дополняется фактическим Kubernetes RBAC,не заменяет его.')]),
command('argocd proj get','Прочитать AppProject и его границы.','argocd proj get ИМЯ','argocd-05-application'),
command('argocd proj role create','Создать проектную роль,после чего определить её ограниченную политику.','argocd proj role create ПРОЕКТ РОЛЬ','argocd-13-access'),
command('argocd proj role create-token','Создать чувствительный токен проектной роли.','argocd proj role create-token ПРОЕКТ РОЛЬ [ФЛАГИ]','argocd-13-access',[
 flag('--expires-in ДЛИТЕЛЬНОСТЬ','Ограничить срок проектного токена.','Минимальная временная автоматизация.','argocd proj role create-token ledger deployer --expires-in 1h','Не публиковать вывод; роль должна уже существовать с проверенными разрешениями.')],aliases=['argocd proj role token-create']),
command('argocd proj windows list','Прочитать окна синхронизации проекта.','argocd proj windows list ПРОЕКТ','argocd-08-sync'),
command('argocd appset create','Создать ApplicationSet через API;он может создать много дочерних Application.','argocd appset create ФАЙЛ','argocd-11-applicationset'),
command('argocd appset generate','Получить сгенерированные Application через сервер.','argocd appset generate ФАЙЛ [ФЛАГИ]','argocd-11-applicationset',[
 flag('-o ФОРМАТ / --output ФОРМАТ','Выбрать json/yaml/wide.','Просмотр перед отдельным применением.','argocd appset generate ./configured-fleet.yaml --output yaml','Команда требует API, не объявлена автономным генератором в проверках.')]),
command('argocd appset list','Показать доступные ApplicationSet.','argocd appset list','argocd-11-applicationset'),
command('argocd appset delete','Удалить ApplicationSet с рассмотрением ownerReferences/finalizers.','argocd appset delete ИМЯ','argocd-11-applicationset'),
command('argocd admin export','Экспортировать данные управляющего контура из Kubernetes.','argocd admin export [ФЛАГИ]','argocd-14-recovery',[
 flag('--kubeconfig ФАЙЛ','Выбрать Kubernetes-доступ источника резерва.','Только свой управляющий контур.','argocd admin export --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" --namespace argocd --out "$LAB_ROOT/private/argo-export.yaml"','Экспорт содержит секреты;ошибочный namespace может не дать ожидаемой ошибки.'),
 flag('--context ИМЯ','Выбрать Kubernetes context,не Argo login context.','Предотвратить резерв не той системы.','argocd admin export --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n argocd','Полнота проверяется составом и восстановлением; одного кода 0 недостаточно.'),
 flag('-n ИМЯ / --namespace ИМЯ','Выбрать namespace управляющей установки Argo.','Не смешать с gitops-lab.','argocd admin export --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n argocd','Приложения в иных namespaces требуют своих опций.'),
 flag('-o ФАЙЛ / --out ФАЙЛ','Записать приватный файл вместо stdout.','Резерв с umask077.','argocd admin export --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n argocd --out "$LAB_ROOT/private/argo-export.yaml"','Git не является местом открытого хранения этого файла.')]),
command('argocd admin import','Восстановить данные в отдельно подготовленную цель;не запускать на исходной системе ради теста.','argocd admin import ИСТОЧНИК [ФЛАГИ]','argocd-14-recovery',[
 flag('--dry-run','Показать предусмотренные действия импорта.','Перед реальным восстановлением отдельной цели.','argocd admin import "$LAB_ROOT/private/argo-export.yaml" --kubeconfig "$RESTORE_KUBECONFIG" --context "$RESTORE_CONTEXT" -n argocd --dry-run','Не является проверенным restore и может требовать API.'),
 flag('--prune','Удалить целевые объекты,отсутствующие в резерве.','Только сознательное восстановление полного набора.','argocd admin import "$LAB_ROOT/private/argo-export.yaml" --kubeconfig "$RESTORE_KUBECONFIG" --context "$RESTORE_CONTEXT" -n argocd --prune --dry-run','Может удалить записи, созданные после сохранения резерва. Сначала проверяют отдельную цель и план удаления.'),
 flag('--kubeconfig ФАЙЛ','Выбрать отдельный Kubernetes-доступ восстановления.','Проверка на другой цели.','argocd admin import "$LAB_ROOT/private/argo-export.yaml" --kubeconfig "$RESTORE_KUBECONFIG" --context "$RESTORE_CONTEXT" -n argocd --dry-run','Источник и цель должны быть явно различимы.')]),
command('argocd admin settings rbac validate','Проверить синтаксис политики; в 3.5.6 также требуется сформировать конфигурацию Kubernetes-клиента.','argocd admin settings rbac validate [ФЛАГИ]','argocd-13-access',[
 flag('--policy-file ФАЙЛ','Прочитать CSV либо ConfigMap с политикой.','Нативная проверка до применения.','argocd admin settings rbac validate --policy-file rbac/policy.csv --server http://127.0.0.1:9 --token offline-dummy','С изолированным пустым kubeconfig и фиктивным адресом сервера не посылает запросов; это подтверждено ловушкой соединения.'),
 flag('--server URL','Задать локально затеняющий Kubernetes адрес сервера.','Только автономная проверка политики с фиктивным токеном.','argocd admin settings rbac validate --policy-file rbac/policy.csv --server http://127.0.0.1:9 --token offline-dummy','Это НЕ корневой --server Argo API;создаёт объект клиента,но файл читает локально.'),
 flag('--kubeconfig ФАЙЛ','Выбрать существующий изолированный пустой/фиктивный файл.','Не читать рабочую конфигурацию пользователя.','argocd admin settings rbac validate --kubeconfig ./empty-kubeconfig --policy-file rbac/policy.csv --server http://127.0.0.1:9 --token offline-dummy','Явно несуществующий --kubeconfig вызывает ошибку stat;файл сначала создают.')]),
command('argocd admin settings rbac can','Нативно проверить конкретное разрешение по локальной политике или серверному ConfigMap.','argocd admin settings rbac can СУБЪЕКТ ДЕЙСТВИЕ РЕСУРС ОБЪЕКТ [ФЛАГИ]','argocd-13-access',[
 flag('--policy-file ФАЙЛ','Выбрать локальную проверяемую политику.','Сравнить reader/releaser на одном объекте.','argocd admin settings rbac can reader get applications ledger/ledger-gitops --policy-file rbac/policy.csv --server http://127.0.0.1:9 --token offline-dummy','Yes/код 0 для get,No/код 1 для sync у reader;это не проверка Kubernetes RBAC.'),
 flag('--use-builtin-policy','Управлять включением встроенных правил;для изолированного опыта false.','Измерить только собственную policy.csv.','argocd admin settings rbac can reader sync applications ledger/ledger-gitops --policy-file rbac/policy.csv --use-builtin-policy=false --server http://127.0.0.1:9 --token offline-dummy','Иначе встроенные роли могут изменить вывод.'),
 flag('--default-role РОЛЬ','Задать исходную роль проверки.','Разобрать чрезмерные исходные разрешения.','argocd admin settings rbac can reader get applications ledger/ledger-gitops --policy-file rbac/argocd-rbac-cm.yaml --default-role role:none --server http://127.0.0.1:9 --token offline-dummy','Роль по умолчанию и персональные правила исследуют отдельно.'),
 flag('--server URL','Задать адрес Kubernetes API этой конечной команды.','Локальная политика с изолированной конфигурацией.','argocd admin settings rbac can reader get app ledger/ledger-gitops --policy-file rbac/policy.csv --server http://127.0.0.1:9 --token offline-dummy','Псевдоним ресурса app реально проверен; ни один запрос API не выполнялся.'),
 flag('--token СТРОКА','Дать фиктивный Kubernetes token для конструирования клиента без интерактивного запроса.','Только изолированная автономная проверка политики.','argocd admin settings rbac can reader get applications ledger/ledger-gitops --policy-file rbac/policy.csv --server http://127.0.0.1:9 --token offline-dummy','Не реальный токен;Argo auth-token — другой флаг.'),
 flag('-q / --quiet','Не печатать Yes/No,использовать код.','Безопасная автоматизация локальной проверки.','argocd admin settings rbac can reader sync applications ledger/ledger-gitops --quiet --policy-file rbac/policy.csv --server http://127.0.0.1:9 --token offline-dummy','Отказ всё равно должен остановить зависимое изменяющее действие.')])
]
# Leaf-local Kubernetes flags shadow root Argo flags. Keep ownership explicit.
extra_flags={
 'argocd app create':[
  flag('--path ПУТЬ','Выбрать каталог внутри Git.','Путь уже существует в выбранном коммите.','argocd app create ledger-gitops --repo "$LAB_REPO_URL" --path apps/ledger/overlays/lab --revision "$LAB_COMMIT" --dest-server https://kubernetes.default.svc --dest-namespace gitops-lab --project ledger','Это не локальный текущий каталог клиента.'),
  flag('--dest-server URL','Выбрать зарегистрированный API целевого кластера.','Тот же кластер использует внутренний адрес.','argocd app create ledger-gitops --file "$LAB_ROOT/bootstrap-initial/application.yaml" --dest-server https://kubernetes.default.svc','Отличается от --server Argo API.'),
  flag('--dest-namespace ИМЯ','Выбрать назначение для ресурсов с пространством имён.','Отдельная область gitops-lab.','argocd app create ledger-gitops --file "$LAB_ROOT/bootstrap-initial/application.yaml" --dest-namespace gitops-lab','Явный metadata.namespace документа сохраняет своё значение; destination.namespace подставляется только при его отсутствии.')],
 'argocd app sync':[
  flag('--retry-backoff-duration ДЛИТЕЛЬНОСТЬ','Задать начальную паузу между повторами.','Временный диагностированный отказ.','argocd app sync ledger-gitops --retry-limit 3 --retry-backoff-duration 5s','Строка длительности отличается от --timeout seconds.'),
  flag('--retry-backoff-max-duration ДЛИТЕЛЬНОСТЬ','Ограничить максимальную паузу между повторами.','Не допустить неограниченного роста задержки.','argocd app sync ledger-gitops --retry-limit 3 --retry-backoff-max-duration 30s','Не задаёт общий deadline и не отменяет побочные эффекты.')],
 'argocd admin settings rbac validate':[
  flag('--token СТРОКА','Дать фиктивный Kubernetes token только для создания автономной настройки клиента.','Изолированная локальная проверка файла политики.','argocd admin settings rbac validate --policy-file rbac/policy.csv --server http://127.0.0.1:9 --token offline-dummy','Это не --auth-token Argo API; ловушка подтверждает0 запросов.'),
  flag('--context ИМЯ','Выбрать существующий контекст внутри указанного Kubernetes kubeconfig.','Проверка политики с явно выбранным собственным доступом; для пустого автономного файла контекст опускают.','argocd admin settings rbac validate --policy-file rbac/policy.csv --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT"','Имя должно существовать в файле. Это не --argocd-context сохранённой сессии Argo и не создание нового контекста.')],
 'argocd admin settings rbac can':[
  flag('--kubeconfig ФАЙЛ','Выбрать существующий Kubernetes-файл, из которого строится клиентская конфигурация этой конечной команды.','Файловая автономная проверка с заранее созданным пустым файлом либо явно подготовленным собственным доступом.','argocd admin settings rbac can reader get applications ledger/ledger-gitops --policy-file rbac/policy.csv --kubeconfig ./empty-kubeconfig --server http://127.0.0.1:9 --token offline-dummy --use-builtin-policy=false','Пустой файл сначала создают по главе доступа. Несуществующий путь отказывает; без явного выбора можно случайно прочитать пользовательский Kubernetes-профиль.'),
  flag('--context ИМЯ','Выбрать контекст Kubernetes из явно указанного kubeconfig.','Нужно проверить выбранную конфигурацию клиента по имени, не полагаясь на current-context.','argocd admin settings rbac can reader get applications ledger/ledger-gitops --policy-file rbac/policy.csv --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" --use-builtin-policy=false','Это локальный флаг admin-команды. В пустом автономном kubeconfig именованных контекстов нет: там его не задают. Сеанс --argocd-context относится к другому API.')],
 'argocd admin import':[
  flag('--context ИМЯ','Выбрать Kubernetes context отдельной цели.','Восстановление не на исходный кластер.','argocd admin import "$LAB_ROOT/private/argo-export.yaml" --kubeconfig "$RESTORE_KUBECONFIG" --context "$RESTORE_CONTEXT" -n argocd --dry-run','Сеанс --argocd-context не определяет эту цель.'),
  flag('-n ИМЯ / --namespace ИМЯ','Выбрать namespace управляющей установки в целевом кластере.','Одинаковое имя в другом кластере — отдельная цель.','argocd admin import "$LAB_ROOT/private/argo-export.yaml" --kubeconfig "$RESTORE_KUBECONFIG" --context "$RESTORE_CONTEXT" -n argocd --dry-run','Неверный namespace способен привести к неполному восстановлению.')]
}
extra_flags['argocd app diff']=[
 flag('--exit-code','Выбирать ненулевой код при обнаруженном различии.','Различать ожидаемое расхождение и отказ вычисления.','argocd app diff ledger-gitops --exit-code=false','False отключает код различия, но не исправляет соединение или ошибку сервера.'),
 flag('--server-side-generate','Передавать локальные файлы серверу для вычисления сравнения.','Явно выбран доверенный сервер и разрешена передача исходников.','argocd app diff ledger-gitops --local ./rendered --server-side-generate','Это передача файлов через API, а не автономный запуск. Совместно с --local.')]

# Additional concrete terms introduced by the finite 2026-11-02 source review.
GLOSSARY += [
 ('Last-applied configuration','Сохранённое прежнее описание объекта в аннотации kubectl.kubernetes.io/last-applied-configuration. Вместе с желаемым и живым объектами участвует в Legacy diff; не является снимком всех полей и внешних данных.'),
 ('ResourceVersion','Служебная версия наблюдаемого объекта Kubernetes. Меняется при его изменении и используется для чтения/наблюдения; это не Git-коммит и не номер образа.'),
 ('Admission','Проверки и преобразования запроса Kubernetes API перед сохранением. Проверяющий webhook может отказать, изменяющий — добавить или изменить поля.'),
 ('JSON Pointer','Путь к значению JSON: /spec/replicas выбирает replicas внутри spec. В имени ключа ~0 обозначает тильду, ~1 — косую черту.'),
 ('HPA','HorizontalPodAutoscaler — контроллер Kubernetes, меняющий число реплик по метрикам. Его управление replicas необходимо согласовать с желаемой конфигурацией Argo.'),
 ('ServiceAccount','Служебная учётная запись Kubernetes для процессов. RoleBinding либо ClusterRoleBinding связывает её с разрешениями; права установившего манифест пользователя автоматически ей не передаются.'),
 ('ReplicaSet','Контроллер поддержания требуемого числа Pod по шаблону. Deployment создаёт и меняет ReplicaSet при обновлении шаблона.'),
 ('StatefulSet','Контроллер реплик с устойчивыми именами и предусмотренной моделью идентичности. В выбранной установке так запускается application-controller; его готовность проверяется отдельно.'),
 ('Backoff','Пауза перед повторной попыткой. Начальная длительность, множитель и верхний предел задают отдельные паузы; время выполнения попыток увеличивает полную длительность операции.'),
 ('Restore quarantine','Изолированная цель восстановления: проверены кластер и назначение, контроллеры изменений остановлены, прежние доступы и сохранённые операции пересмотрены до возобновления.')
]
# New trust-command cards are source-level descriptions. The historical native
# help result for 39 commands is retained unchanged and does not cover these two.
for _name,_purpose,_syntax in [
 ('argocd cert add-tls','Добавить проверенный материал доверия HTTPS-репозиторию в свою установку Argo. Сначала проверить имя хоста и происхождение сертификата по главе12.','argocd cert add-tls ИМЯ_ХОСТА [ФЛАГИ]'),
 ('argocd cert add-ssh','Добавить предварительно проверенные открытые SSH-ключи хостов. Это доверие к серверу, а не загрузка закрытого ключа пользователя.','argocd cert add-ssh [ФЛАГИ]')]:
 _card=command(_name,_purpose,_syntax,'argocd-12-repositories')
 _card['source']='https://github.com/argoproj/argo-cd/blob/v3.5.6/docs/user-guide/private-repositories.md'
 _card['sources']=[dict(title='Первичный раздел о доверии репозиториям 3.5.6; новая native-проверка справки не выполнялась',url=_card['source'])]
 COMMANDS.append(_card)

for c in COMMANDS:
 c['flags'].extend(extra_flags.get(c['name'],[]))
 if c['name'] in ['argocd admin export','argocd admin import','argocd admin initial-password']:
  c['flags'].append(flag('--server URL','Локальный адрес Kubernetes API admin-команды, затеняющий корневой --server.','Обычно адрес берётся из выбранного kubeconfig.','argocd '+c['name'].split('argocd ',1)[1]+' --help','Показана справка без подключения;не переопределять сервер без явной модели доверия.'))
