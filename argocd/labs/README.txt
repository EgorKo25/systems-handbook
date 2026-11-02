ARGO CD 3.5.6 — ПРОДОЛЖАЕМАЯ ЛАБОРАТОРИЯ
Срез: 1 ноября 2026. Linux amd64. Этот каталог не устанавливает ничего автоматически.

1. ГРАНИЦЫ И ВХОДЫ

Нужны Bash, Python3, tar, Git, OpenSSL; для кластерной части — kubectl и
СОБСТВЕННЫЙ уже подготовленный Kubernetes. В соседнем томе основной VM-профиль
Kubernetes1.36.6/контекст handbook-admin, альтернативный kind1.36.4/контекст
kind-handbook. Матрица Argo3.5 включает Kubernetes1.36, но автор НЕ запускал
кластер/сервер Argo. Не направляйте сценарии на рабочий или общий кластер.
Полномочия создания CRD/ClusterRole/ClusterRoleBinding нужны именно владельцу
личного учебного кластера. Никакого sudo, смены current-context, облака и root
в этом комплекте нет. Новая машина не появляется от команды Argo.

Контракт приложения прежний: ledger-api:0.1.0, HTTP8080, MESSAGE,
GET /livez /readyz /api/hello /metrics. JSON /api/hello содержит service/message.
service/ побайтно сохраняет общий исходник Kubernetes. Иные байты не должны
получить тот же тег. Отдельное владение Argo: Application ledger-gitops,
AppProject ledger, namespace gitops-lab, Deployment/Service ledger-gitops.
Ни lab, ни helm-lab, ни соседний Helm release не захватываются.

Постоянный каталог читателя, например $HOME/handbook-argocd:
  bundle/   проверенные исходные файлы, не данные Redis
  tools/    личные закреплённые исполняемые файлы, без глобального PATH
  work/     продолжаемая копия ЭТОГО каталога
  private/  kubeconfig/сеанс/сертификаты/экспорт; закрытые права, не Git
  evidence/ результаты без секретов
  venv/     личное окружение Python
/tmp используют только автоматические одноразовые проверки; реальный стенд,
рабочие изменения и приватные данные там не размещаются.

2. ОДНОКРАТНОЕ ПОЛУЧЕНИЕ И ПРОИСХОЖДЕНИЕ

Откройте терминал в исходном каталоге argocd/labs скачанной книги. Этот исходный
каталог НЕ находится внутри будущего LAB_ROOT/work. Затем:

export LAB_ROOT="$HOME/handbook-argocd"
(
  set -euo pipefail
  umask 077
  test -f prepare_bundle.py
  mkdir -p "$LAB_ROOT/private" "$LAB_ROOT/evidence"
  test ! -e "$LAB_ROOT/work"
  cp -a . "$LAB_ROOT/work"
  python3 "$LAB_ROOT/work/prepare_bundle.py" --output "$LAB_ROOT/bundle"
  bash "$LAB_ROOT/work/scripts/prepare-tools.sh"
)

Скобки создают подпроцесс: первый отказ завершает только его, не интерактивный
shell. prepare_bundle.py скачивает четыре файла из bundle-lock.json, потоково
проверяет SHA, не исполняет их и отказывается использовать непустой каталог
для нового скачивания. prepare-tools.sh снова сверяет весь комплект, создаёт
новый tools/runtime-3.5.6, извлекает только названные файлы архивов и проверяет
фактические версии. PATH системы не меняется. Повторный запуск на уже созданном
runtime остановится, не перезапишет его. При прерывании сначала выясните,
какие файлы созданы; НЕ удаляйте work и не начинайте стенд с нуля.
Если bundle полный, python3 prepare_bundle.py --output "$LAB_ROOT/bundle"
--verify-only проверяет его без скачивания. Неполный каталог следует сохранить
для диагностики или переименовать, а новый комплект получать в НОВЫЙ каталог
и явно выбрать его после проверки. Нельзя убрать проверку хеша ради продолжения.

В каждом новом терминале задайте:
export LAB_ROOT="$HOME/handbook-argocd"
export ARGOCD_BIN="$LAB_ROOT/tools/runtime-3.5.6/argocd"
export HELM_BIN="$LAB_ROOT/tools/runtime-3.5.6/helm/linux-amd64/helm"
export KUSTOMIZE_BIN="$LAB_ROOT/tools/runtime-3.5.6/kustomize/kustomize"

Версии: Argo v3.5.6+c2b1e30, Helm v4.2.1+gd591a19, Kustomize v5.8.1.
Выбор проверен по исходному tag Argo hack/tool-versions.sh и реальному запуску.
Это НЕ Helm4.3.1 соседнего тома. Суммы/URL — bundle-lock.json.
SHA проверена автором и независимо координатором для CLI; cosign/SLSA НЕ
исполнялись. Образы Argo/Dex/Redis/ledger/busybox подготовщик НЕ скачивает.
Нужны отдельные платформенные digest и доставка на узлы/в свой реестр.

3. ЛОКАЛЬНЫЕ ПРОВЕРКИ, БЕЗ ARGO API И KUBERNETES

Автор использовал Python3.12.3, PyYAML6.0.1, jsonschema4.10.3. Это закрепление
окружения теста, не обещание совместимости любой другой версии Python.
Можно использовать заранее подготовленное собственное окружение с этими
библиотеками. Если создаёте новое локально (потребуется доступ к Python package
index или доверенные заранее сохранённые wheels):
(
  set -euo pipefail
  test ! -e "$LAB_ROOT/venv"
  python3 -m venv "$LAB_ROOT/venv"
  "$LAB_ROOT/venv/bin/python" -m pip install -r "$LAB_ROOT/work/requirements.txt"
)

Этот шаг тоже не выполняйте повторно поверх существующего окружения без
понимания его состояния. Никакие библиотеки системного Python не меняются.
После успешной подготовки:
"$LAB_ROOT/venv/bin/python" "$LAB_ROOT/work/check.py"

Опционально задайте GO_BIN абсолютным путём своего Go1.27.3, чтобы проверить
service/ с race detector. Без GO_BIN сценарий честно НЕ пишет PASS Go-тестам.
Реальная авторская проверка включала Go. Без Go остаются настоящие RBAC,
Kustomize, Helm и схемы. results.json записывается в свою work, не исходник книги.

Check.py изолирует HOME, клиентский config и Kubernetes-файл во временном
каталоге; убирает ARGOCD_AUTH_TOKEN/ARGOCD_SERVER; настоящую локальную RBAC-
команду направляет на loopback-ловушку и требует0 запросов. Отдельные
fake-kubectl-тесты проверяют прекращение четырёх Bash-сценариев, НЕ эмулируют
успешный кластер. git diff --no-index сравнивает файлы без commit/push.
CRD-схемы — неизменённые upstream структурные схемы, jsonschema не выполняет
Kubernetes admission/defaults/CEL/RBAC. Helm-пример выдаёт ОДИН ConfigMap,
это отдельная проверка рендерера, не полная замена Kustomize-приложения.

Для ручного локального целевого файла:
(
  set -euo pipefail
  mkdir -p "$LAB_ROOT/evidence"
  "$KUSTOMIZE_BIN" build "$LAB_ROOT/work/gitops/apps/ledger/overlays/lab" \
    > "$LAB_ROOT/evidence/desired-local.yaml"
)

4. УСТАНОВКА — ТОЛЬКО СВОЙ КЛАСТЕР, АВТОРОМ НЕ ВЫПОЛНЕНА

Задайте уже существующий личный kubeconfig и один правильный context:
export LAB_KUBECONFIG="$HOME/handbook-lab/kubeconfig"
export LAB_CONTEXT=handbook-admin
Для kind вместо этого LAB_CONTEXT=kind-handbook. Не создавайте пустой файл
по этому пути для обхода проверки: это реальный доступ, не offline fixture.
Сначала просмотрите scripts/preflight.sh и scripts/install.sh.

bash "$LAB_ROOT/work/scripts/preflight.sh"
bash "$LAB_ROOT/work/scripts/install.sh"

Installer сам повторяет preflight и проверку bundle, поэтому вставка двух строк
без shell errexit не позволяет пройти зависимую установку после отказа проверки.
Он создаёт argocd и gitops-lab только при отсутствии; у уже существующего
namespace требует handbook.example/owner=argocd-lab. Чужое пространство не
перемечается автоматически. Dry-run предшествует apply, --force-conflicts не
используется. При отказе create/dry-run/apply/ready сценарий заканчивается;
следующие вход/приложение НЕ запускаются внутри него. Повтор не сбрасывает
состояние. Не заменяйте этот процесс kubectl apply -f URL плавающей ветки.

Критерии: CRD Established, Deployments Available, StatefulSet controller
развёрнут; изучены события, образы скачаны на нужные узлы. dry-run этого НЕ
доказывает. Потребление CPU/RAM измерьте вместе с CNI/DNS и приложением.

5. ЛОКАЛЬНЫЙ КАНАЛ И ПЕРВЫЙ ВХОД

В отдельном терминале с теми же экспортами держите foreground:
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n argocd \
  port-forward --address 127.0.0.1 service/argocd-server 8443:443

В основном терминале после проверки сценария:
bash "$LAB_ROOT/work/scripts/first-login.sh"

Сценарий получает только tls.crt стандартного argocd-secret через доверенный
Kubernetes API, проверяет его непустоту, имя localhost и цепочку OpenSSL,
выводит initial-password, затем интерактивно login/admin и update-password.
У внешнего argocd-server-tls путь к сертификату другой: сценарий должен
остановиться, а владелец выяснить конфигурацию; не включайте --insecure.
Закрытый tls.key не выгружается. Пароль не записывайте в argv/Git/публичный лог.
Это сценарий первого входа, не автоматического сброса пароля при каждом повторе.

CLI --config "$LAB_ROOT/private/argocd-config" хранит сеанс. Имя handbook —
Argo-подключение (--argocd-context), а handbook-admin — Kubernetes-контекст.
Для admin-команд --context/--kubeconfig выбирают Kubernetes; локальный --server
там означает Kubernetes API, а не Argo endpoint. Canonical флаги размещайте
после конечной admin-команды, чтобы этот смысл был однозначен.

6. СВОЁ ДЕРЕВО, C1 И ПЕРВЫЙ APPLICATION

Читатель размещает содержимое work/gitops в своём конфигурационном репозитории:
apps/ledger/... находится от КОРНЯ Git. Не загружайте bundle/tools/private.
Книга не создаёт внешний репозиторий и не выполняет commit/push.
LAB_REPO_URL — собственный HTTPS или ssh:// адрес, LAB_COMMIT — полный40-hex C1.
Проверьте, что repo-server может его читать. Для приватного Git сначала
настройте собственные credentials/CA/known_hosts по главе12; примеры секретов
намеренно не содержат настоящих значений. Токен Git не заменяет imagePullSecret.

Сервис ledger-api:0.1.0 должен быть доступен во ВСЕХ нужных узлах выбранного
кластера. Если образ уже построен в Kubernetes-томе, используйте тот же артефакт.
Для самостоятельной сборки без прежнего артефакта используйте отдельный guarded
блок главы17. Он требует личный Linux/amd64 Docker-контекст,Go1.27.3 и C-среду
для race-теста, сохраняет новый каталог artifacts/argocd-local-1 и создаёт тег
ledger-api:argocd-local-1 без перезаписи существующего образа. В собственной
Kustomize-копии явно выберите этот новый тег до C1; остальные поля сохраняются.
Build не загружает образ на узлы. При готовом0.1.0 блок пропускают. При kind
загрузка kind load docker-image ledger-api:0.1.0 --name handbook относится
только к вашему kind-handbook; VM требует доставки на все нужные containerd
узлы/свой registry. Для собственного повторного build сначала проверьте toolchain/платформу;
исходники service/ не менялись. Не называйте иное приложение тем же тегом.

После выставления LAB_REPO_URL/LAB_COMMIT:
(
  set -euo pipefail
  : "${LAB_REPO_URL:?}" "${LAB_COMMIT:?}"
  "$LAB_ROOT/venv/bin/python" "$LAB_ROOT/work/configure.py" \
    --repo "$LAB_REPO_URL" --revision "$LAB_COMMIT" \
    --output "$LAB_ROOT/bootstrap-initial"
)

Сначала ПРОЧИТАЙТЕ два созданных файла: namespace argocd, проект ledger,
назначение gitops-lab, разрешённые только нужные виды, automated.enabled=false,
FailOnSharedResource=true, без ресурсного финализатора. Затем:
bash "$LAB_ROOT/work/scripts/first-app.sh"

Он ждёт server, делает dry-run и apply проекта, затем dry-run и apply приложения,
останавливаясь при любом отказе. Не делайте sync после ошибки source/render.
Наблюдение (без мутации приложения):
"$ARGOCD_BIN" --config "$LAB_ROOT/private/argocd-config" --argocd-context handbook \
  app get ledger-gitops --refresh --output yaml
"$ARGOCD_BIN" --config "$LAB_ROOT/private/argocd-config" --argocd-context handbook \
  app manifests ledger-gitops
"$ARGOCD_BIN" --config "$LAB_ROOT/private/argocd-config" --argocd-context handbook \
  app diff ledger-gitops

app diff код0 — нет различия, по умолчанию1 — есть различия; прочие отказы
соединения/генерации надо различать по результату и stderr. Не используйте
«любой ненулевой код» как разрешение на автоматический sync. app diff --local
НЕ автономная команда: ей требуется сервер и живое приложение.

7. ОДНА РУЧНАЯ ПОСТАВКА

Только после принятого просмотра цели и доступности образа:
"$ARGOCD_BIN" --config "$LAB_ROOT/private/argocd-config" --argocd-context handbook \
  app sync ledger-gitops --timeout 180

Эта операция не включает prune. Если она отказала, разберите operationState,
Deployment и события; не повторяйте Force/Replace вслепую. app sync --dry-run
тоже серверная операция, НЕ локальный Helm render. Затем отдельно:
"$ARGOCD_BIN" --config "$LAB_ROOT/private/argocd-config" --argocd-context handbook \
  app wait ledger-gitops --sync --health --timeout 180

--timeout здесь секунды целым числом. --async доказывает только принятие запроса.
Проверьте новый Deployment, endpoints и JSON через отдельный терминал:
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n gitops-lab \
  port-forward --address 127.0.0.1 service/ledger-gitops 18080:80

В другом терминале curl --fail http://127.0.0.1:18080/api/hello.
Ожидаемый ответ содержит service=ledger-api,message=Hello from GitOps lab.
Это ОЖИДАНИЕ рецепта, не сохранённый авторский cluster-output.

8. C2, C3 И C4 — БЕЗ ПЕРЕУСТАНОВКИ И RESET

В том же собственном дереве измените MESSAGE, локально проверьте Kustomize,
создайте C2 своим обычным согласованным Git-процессом. Application пока pinned
на C1, поэтому сам новый коммит не должен менять цель. Переведите targetRevision
того же Application на C2 через собственный декларативный файл либо app set
ledger-gitops --revision "$LAB_NEXT_COMMIT" с явным Argo config/context.
Проверьте diff, выполните ручной sync, дождитесь здоровья и нового JSON.message.
Имя ConfigMap получит другой хеш, ссылка в Pod template тоже. Старые ConfigMap
без prune остаются; сначала определите актуальные ссылки работающих Pod.

Для C3 скопируйте fixtures/not-ready.patch.yaml внутрь своего
apps/ledger/overlays/lab и добавьте patches: [{path: not-ready.patch.yaml}]
в ТОТ ЖЕ kustomization.yaml, сохраняя MESSAGE C2. Путь readiness станет
/missing-readyz. После осознанного перевода цели/sync ожидайте отказа готовности,
а не успешного PostSync. Запишите отдельно Synced/OutOfSync,health,operationState,
Deployment conditions,новые/старые Pod и ответ Service. C4 исправляет путь
новым коммитом, не стирая остальные настройки. Удаление Pod/namespace не нужно.

fixtures/post-sync-test.yaml — необязательный PostSync Job. Для добавления в
Git нужно разрешение Job, доступный образ busybox:1.37.0 и сеть Service. Это
прикладной HTTP-тест; он НЕ выполняется при selective sync --resource.
ApplyOutOfSyncOnly=true в3.5 — другой режим: hooks/история сохраняются.
fixtures/automated-policy.yaml — фрагмент для изучения, не самостоятельный
Application для apply. Включать его надо в собственную спецификацию после
ручного маршрута. Enabled=false отключает auto независимо от других bool;
automated:{} включает, prune/selfHeal/allowEmpty — отдельные разрешения.

9. НЕОБЯЗАТЕЛЬНЫЙ FLEET И APPLICATIONSET

Сохраняйте исходный Application ledger-gitops. Для отдельного набора:
"$LAB_ROOT/venv/bin/python" "$LAB_ROOT/work/configure.py" --fleet \
  --repo "$LAB_REPO_URL" --revision "$LAB_COMMIT" \
  --output "$LAB_ROOT/bootstrap-fleet"

Это создаёт project-fleet.yaml и applicationset.yaml для ПРОСМОТРА, не API.
Назначения gitops-fleet-practice/gitops-fleet-review создаёт владелец личного
кластера с собственной меткой; чужие существующие пространства не принимают.
Полный apps/ledger/base не содержит жёсткого namespace, поэтому подходит двум
назначениям. Overlay/lab сюда не переносится. После проверки namespaces,
проекта и источника применяйте проект, затем набор отдельными server dry-run/
apply с такими же fail-closed границами, как first-app.sh. Новые дети manual.

Локальная схема не генерирует AppSet; argocd appset generate требует сервер.
ApplicationsSync=create-update не блокирует Kubernetes GC при удалении родителя.
PreserveResourcesOnDeletion=true не добавляет ресурсный финализатор новым детям;
всегда проверяйте фактические ownerReferences/finalizers до удаления.
Никакого автоматического teardown в комплекте нет: этот стенд продолжается.

10. РЕЗЕРВ, АВТОНОМНОСТЬ, ИЗМЕРЕНИЯ

admin export/import — Kubernetes admin-команды, не чистые локальные операции.
Перед import нужен КОНКРЕТНЫЙ карантин: другой самостоятельно подготовленный
кластер и endpoint, независимо записанный UID kube-system, тот же3.5.6 без apps.
Владелец явно метит собственный argocd handbook.example/restore=quarantine.
Сценарий scripts/quarantine-restore.sh требует RESTORE_KUBECONFIG,
RESTORE_CONTEXT,RESTORE_EXPECTED_SERVER,RESTORE_EXPECTED_CLUSTER_UID, сравнивает
новый endpoint/UID с исходным,останавливает application-controller StatefulSet
applicationset-controller и notifications-controller Deployment до replicas0,
проверяет отсутствие Pod всех трёх. Без исходного API нужен заранее сохранённый
SOURCE_CLUSTER_UID из доверенного журнала; тогда старый API не читается.
Он НЕ выполняет import и НЕ запускает их обратно. При любом отказе — остановка.
До ручного import также ограничивают сеть к прежним назначениям; после import
при ещё остановленных трёх контроллерах просматривают Application destinations,
cluster Secrets,AppProject destinations,auto policies и AppSet templates.
Сначала исправляют адреса/владельцев/credentials,затем включают только тестовое
приложение;генератор набора пока не запускают. См. точный порядок главы14.
Экспорт приватный: argocd-secret signing/server keys,repo/cluster credentials
нужны для восстановления, а данные приложения — отдельно. Проверяйте выбранный
namespace и состав. Restore сначала в изолированное назначение с отключённой
автоматизацией; импорт с прежними credentials может задеть настоящий кластер.
Redis cache не SQL source of truth. Rollback приложения не откатывает БД.

Для изолированной сети кроме bundle нужны platform-specific образы,Git-объекты,
зависимости,CA/SSH trust,credentials,DNS/время и способы загрузки узлов. Кэш — не
доказательство полной автономной установки. Тест этой книги после доставки
инструментов локален; установка в air-gap не исполнена.

metrics в results.json:10 запусков маленького Kustomize,байты/числообъектов,
медиана/минимум/максимум. Это НЕ repo-server,SLA,HA или кластерная нагрузка.
Для своего сервера разделяйте обнаружение,очередь,Git,генерацию,API,готовность,
HTTP; фиксируйте версии,коммит,ресурсы и холодный/тёплый кэш. Сохраняйте историю
измерений в evidence без секретов. Подробности — главы14–18 и ПРОВЕРКИ.txt.

11. ИСХОДНАЯ И ЧИТАТЕЛЬСКАЯ КОПИИ: РАЗНЫЕ ПРОВЕРКИ

Полный source-checkout содержит argocd/sources с20 ожидаемыми HTML-главами.
В нём check.py выполняет23 группы при заданных GO_BIN/BUNDLE_FIXTURE_DIR,
включая source-only синтаксическую проверку25 исполнимых HTML Bash-блоков.
Results.json явно содержит mode=source-checkout и пустой список skipped.

Читательский reading-export штатно НЕ содержит author sources/. Отдельная
продолжаемая копия одного labs в LAB_ROOT/work тоже не содержит этого каталога.
В таком режиме check.py выполняет22 группы при тех же GO_BIN/BUNDLE_FIXTURE_DIR;
нативные RBAC,рендереры,структурные схемы,guard/bundle/Go проверки сохраняются.
В results.json mode=reading-export;source-only HTML syntax записан в skipped
со status=SKIPPED и причиной отсутствия авторских исходников. Он НЕ получает
PASS и НЕ включается в groups. Отсутствующие необязательные GO/BUNDLE по-прежнему
уменьшают число реально пройденных групп;23/22 относятся к полному набору входов.

Самостоятельный test_snippets.py без всех20 ожидаемых HTML-глав завершится
ошибкой. Пустой sources/,неполный checkout,пустая глава и ноль исполнимых блоков
не дают PASS:0. Если sources/ присутствует в check.py,неполный набор тоже
ошибка,а не автоматический SKIPPED. Для reader-export не копируйте авторские
sources внутрь labs:это отдельная проверка исходной книги,не проверка сервиса.
