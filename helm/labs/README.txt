HELM — ПОСТОЯННЫЙ УЧЕБНЫЙ РЕЛИЗ
Редакция: 1 ноября 2026. CLI Helm 4.3.1; chart API v2.

Это собственная лаборатория, не копия публичного крупного chart.
Скопируйте labs/ в свою рабочую папку. Сохраняются chart/, environment.yaml,
журнал и один release ledger в namespace helm-lab. Между шагами нет reset.
Кластерные рецепты не исполнены автором; локальные проверки исполнены.
Все действия с Kubernetes — только в личном подготовленном стенде.

КОНТРАКТ С KUBERNETES
Личный kubeadm: Kubernetes 1.36.6, context handbook-admin.
Компактный kind0.33.0: Kubernetes1.36.4, context kind-handbook.
Сервис ledger-api:8080, /livez /readyz /api/hello, MESSAGE, JSON.message.
service/main.go, main_test.go, go.mod совпадают с Kubernetes-томом.
Один tag ledger-api:0.1.0 не должен обозначать разные программы.
API_TOKEN — только демонстрация передачи Secret; аутентификация не реализована.

ФАЙЛЫ
chart/ — основной чарт, defaults и schema; без внешних dependencies.
fixtures/ — сравнимые положительные/отрицательные параметры.
service/ — совместимый Go-сервис и реальные HTTP/graceful tests.
dependency/ — library chart только для временной копии в check.py.
recipes/storage-inspector.yaml — самостоятельный Pod, явно пишет marker
на PVC после остановки приложения. Он не управляется Helm.
check.py — только локальная проверка, не вызывает кластер.
results.json — сохранённый исторический отчёт прогона автора. По умолчанию
новый check.py печатает новый отчёт в stdout и не меняет этот файл. Для записи
в отдельный новый файл явно задайте HELM_CHECK_REPORT; существующий файл будет
отвергнут, а не перезаписан. Не назначайте исходный labs/results.json.

0. ПРИЁМКА КЛИЕНТА
Скачивание, ожидаемая SHA и происхождение описаны в главе01.
Укажите свои абсолютные пути, не используйте заполнители буквально:
  export HELM_BIN=/path/to/verified/helm
  export GO_BIN=/path/to/go
  "$HELM_BIN" version --short
  python3 check.py
Нужен PyYAML в своей подготовленной Python-среде. Это не команда установки
пакетов в систему. Checker требует4.3.1; HELM_CONFIG_HOME/CACHE_HOME/DATA_HOME
и несуществующий kubeconfig помещаются во временный каталог.
GO_BIN включает Go tests с ephemeral loopback listener; сервер прекращается
после теста. Кластерные действия не выполняются. Go toolchain должна быть
подготовлена заранее; в собственной учебной VM до офлайна настройте
`go telemetry off`, если требуется этот режим. GOTOOLCHAIN=local, GOWORK=off,
GOPROXY=off/GOSUMDB=off не являются общим сетевым sandbox произвольного кода.
Helm config/cache/data/content, registry/repository overrides и plugin path
изолированы временной областью; реальный kubeconfig не выбирается.

Для краткой записи последующих команд в текущей оболочке:
  helm() { "$HELM_BIN" "$@"; }
Функция не меняет PATH или глобальную установку.

1. ДАННЫЕ И ТИПЫ
  helm lint ./chart --strict --kube-version 1.36.6
  helm template ledger ./chart --kube-version 1.36.6 -f fixtures/prod.yaml -f fixtures/last.yaml
Ожидается replicas1; при обратном порядке3. В обоих CPU100m, memory32Mi.
  helm template ledger ./chart --kube-version 1.36.6 --set replicaCount=3
  helm template ledger ./chart --kube-version 1.36.6 --set-string replicaCount=3
Второй должен отказать schema, а не устанавливаться.
  helm template ledger ./chart --kube-version 1.36.6 -f fixtures/wrong-env.yaml
Намеренный отказ: env.value должен быть строкой, а не bool.
Не добавляйте skip-schema-validation вместо исправления типа.
Проверьте LF файла fixtures/token.txt только с учебным token:
  helm template ledger ./chart --kube-version 1.36.6 --set credentials.create=true --set-file credentials.token=fixtures/token.txt
Вывод содержит Secret. Не публикуйте аналогичный вывод с реальным секретом.

2. ПАКЕТ И ЗАВИСИМОСТЬ
  mkdir -p dist
  helm package ./chart --destination ./dist
  tar -tzf ./dist/ledger-api-0.1.0.tgz
  helm template ledger ./dist/ledger-api-0.1.0.tgz --kube-version 1.36.6
Не размещайте dist/ внутри chart/. Check.py отдельно проверяет точный member,
исключение test-secret.private и структурное равенство manifests.
Dependency update/build запускаются checker только на временной копии.
Он удаляет charts/ той копии, сохраняет lock и восстанавливает библиотеку
без сети. Основной рабочий chart не сбрасывается.

3. ПОДГОТОВИТЬ IMAGE
Если тот же ledger-api:0.1.0 из Kubernetes-практикума уже есть, используйте
его исходный проверенный artifact; не пересобирайте под тем же tag без причины.
Иначе в личной среде, выбрав архитектуру nodes:
  (
    cd service || exit 1
    mkdir -p bin || exit 1
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -o bin/ledger-api . || exit 1
    docker build -t ledger-api:0.1.0 . || exit 1
  )
Сборка выполняется в subshell: текущая папка остаётся labs. Ошибка Go не
допускает docker build со старым bin/ledger-api. Профиль здесь только amd64.
Для своего kind handbook:
  kind load docker-image ledger-api:0.1.0 --name handbook
Для kubeadm нужно доставить image в доступный nodes registry и изменить
repository/digest. Docker images клиента не равен CRI image store nodes.
Образ test/inspector busybox:1.37.0 тоже должен быть доступен; для надёжной
доставки фиксируйте проверенный digest нужной платформы.

4. ОДИН RELEASE
В своей подготовленной среде выберите один файл/контекст, не переключая общий:
  export LAB_KUBECONFIG="$HOME/handbook-lab/kubeconfig"
  export LAB_CONTEXT=handbook-admin
  if test -e environment.yaml || test -L environment.yaml; then
    printf '%s\n' 'Using existing environment.yaml; inspect it before the release.'
  else
    (set -C; cat chart/values.yaml > environment.yaml) || exit 1
  fi
Для kind вместо context один раз выберите kind-handbook.
Namespace helm-lab и минимальную роль готовит владелец стенда.
  kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" auth can-i create deployments.apps -n helm-lab
  helm template ledger ./chart --namespace helm-lab --kube-version 1.36.6 -f environment.yaml > rendered.yaml
  kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n helm-lab apply --server-side --dry-run=server -f rendered.yaml
  helm install ledger ./chart -f environment.yaml --kubeconfig "$LAB_KUBECONFIG" --kube-context "$LAB_CONTEXT" --namespace helm-lab --wait=watcher --timeout 180s
  helm status ledger --kubeconfig "$LAB_KUBECONFIG" --kube-context "$LAB_CONTEXT" -n helm-lab
  helm history ledger --kubeconfig "$LAB_KUBECONFIG" --kube-context "$LAB_CONTEXT" -n helm-lab
  kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n helm-lab get deployment,pod,service,endpointslice
Критерий: revision1 deployed,2 Ready, Service endpoints и правильный JSON.
  kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n helm-lab port-forward service/ledger-ledger-api 18080:80
Во втором терминале curl --fail http://127.0.0.1:18080/api/hello.
Port-forward не доказывает полный обычный ClusterIP/Ingress packet path.
Ctrl+C завершает именно процесс port-forward.

5. ОБНОВЛЕНИЕ И ПОЛОМКА
Измените config.message в environment.yaml. Не меняйте release name.
  helm upgrade ledger ./chart --reset-values -f environment.yaml --kubeconfig "$LAB_KUBECONFIG" --kube-context "$LAB_CONTEXT" -n helm-lab --wait=watcher --timeout 180s
Критерий: новая revision, checksum/config изменён,selector прежний,
новый ReplicaSet и новый JSON.message после готовности.
Намеренный отказ на своём release:
  helm upgrade ledger ./chart --reset-values -f environment.yaml -f fixtures/not-ready.yaml --kubeconfig "$LAB_KUBECONFIG" --kube-context "$LAB_CONTEXT" -n helm-lab --wait=watcher --timeout 45s
Новый Pod Running,readiness404; liveness200. Сохраните events/describe/history.
Исправьте следующим upgrade только с environment.yaml без overlay поломки.
Не удаляйте namespace/release. Отдельно сравните --rollback-on-failure,
понимая, что это компенсация, а не транзакционный rollback внешних данных.

6. TEST HOOK
  helm test ledger --kubeconfig "$LAB_KUBECONFIG" --kube-context "$LAB_CONTEXT" -n helm-lab --logs --timeout 60s
Критерий: настоящий Pod выполнил wget по Service DNS. Это не выполнено автором.
Тест проверяет HTTP success, но не все JSON-поля. Go tests отдельно проверяют
контракт обработчика. Failed test Pod остаётся для диагностики,successful
удаляется согласно политике hook; --logs получает вывод до очистки в4.3.1.

7. ХРАНИЛИЩЕ — ОТДЕЛЬНЫЙ РЕЖИМ
Запишите, какой том сейчас смонтирован и есть ли в нём нужные файлы.
Учебное приложение бизнес-данные в /data не пишет. Storage overlay даёт replica1 и Recreate, то есть downtime:
Сначала выполните recipes/LOCAL-STORAGE.txt владельцами своей VM и кластера:
отдельный каталог на wk1, класс helm-local no-provisioner, PV helm-ledger-local
ёмкостью 256Mi. Fixtures/storage.yaml выбирает этот класс и 128Mi ДО первого PVC.
Для kind/CSI нужен другой подготовленный профиль; overlay не универсален.
Статический local PV этого маршрута не требует CSI. Только после подготовки:
  helm upgrade ledger ./chart --reset-values -f environment.yaml -f fixtures/storage.yaml --kubeconfig "$LAB_KUBECONFIG" --kube-context "$LAB_CONTEXT" -n helm-lab --wait=watcher --timeout 180s
Template не доказывает настоящее связывание или монтирование.
Для явной записи marker остановите приложение отдельным осознанным drift:
  kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n helm-lab scale deployment/ledger-ledger-api --replicas=0
Дождитесь удаления его Pod. В основном статическом local PV профиле CSI
не установлен: проверьте, что прежний потребитель закончил работу и путь
узла больше не используется этим Pod. Для другого CSI-профиля отдельно
проверяют его attach/detach. Затем:
  kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n helm-lab apply -f recipes/storage-inspector.yaml
  kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n helm-lab wait --for=jsonpath='{.status.phase}'=Succeeded pod/ledger-storage-inspector --timeout=120s
  kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n helm-lab logs ledger-storage-inspector
Сохраните значение marker, удалите только inspector Pod,создайте его ещё раз
и сравните тот же marker. Команды create/delete выполняются явно читателем.
После удаления inspector повторите storage upgrade,чтобы вернуть replica1
и устранить осознанный drift. RWO — не обещание одного Pod; режим зависит от
node/backend. Recreate избегает surge-конкуренции за том,но не гарантирует
мгновенного attach/mount. PVC keep — не резервная копия.

8. ОТКАТ И КОНЕЦ
Выберите действительно успешную revision после чтения history:
  helm rollback ledger 1 --kubeconfig "$LAB_KUBECONFIG" --kube-context "$LAB_CONTEXT" -n helm-lab --wait=watcher --timeout 180s
Цифра1 — пример,не автоматический выбор target. Возникает новая revision.
HTTP,данные и совместимость приложения проверяются отдельно.
Только когда практикум завершён:
  helm uninstall ledger --keep-history --kubeconfig "$LAB_KUBECONFIG" --kube-context "$LAB_CONTEXT" -n helm-lab --wait=watcher --timeout 180s
Проверьте оставшиеся namespace,release history,CRD(их у ledger нет),PVC keep
и самостоятельный inspector. Решение удалить данные принимается отдельно.
