KUBERNETES · СОХРАНЯЕМЫЙ СТЕНД
Дата версии: 2026-11-01. Книга описывает Kubernetes 1.36.6, kind-профиль 1.36.4.
Ни один файл не запускается автоматически. Не выполняйте VM-команды на хосте.

Локально, без контейнеров, root, службы и кластера:
  cd service
  go test -race -count=1 ./...
  go vet ./...
  CGO_ENABLED=0 go build -trimpath -o ledger-api .
  cd ..
  python3 validate.py
  python3 test_bundle.py
Нужны подготовленный Go >=1.26, Python3, PyYAML, jsonschema. Зависимости Python
не скачиваются этими сценариями. Go-программа использует только stdlib.
Schema — офлайн-подмножество официального OpenAPI v1.36.6: это статическая
форма объектов; не admission, RBAC, CNI, работа image, readiness или CSI.

Сервис ledger-api слушает :8080; LISTEN_ADDR меняет адрес; MESSAGE — публичное
сообщение. GET /livez, /readyz, /api/hello, /metrics. SIGTERM закрывает listener
и ждёт активные запросы до 8 секунд. Это не бухгалтерская БД: имя служит
общим контрактом томов. Секретов и внешних модулей нет.

Основной VM-стенд: cp1 192.168.56.10, wk1 192.168.56.11, Ubuntu24.04,
containerd2.4.2/runc1.5.2, Calico3.33.0 VXLAN Always, iptables kube-proxy,
PodCIDR10.244/16, ServiceCIDR10.96/16. Выбор непересекающихся подсетей читатель
проверяет в своей VM-сети. Без кластера применимость адресов не доказана.

Первый запуск подробно разобран в FIRST-WORKLOAD.txt. Сначала используйте его:
он получает один Linux/amd64 release, объясняет доставку image, явные отказы
и сохранение состояния. Относительные пути ниже отсчитываются от labs,
K8S_LAB_ROOT — абсолютный путь к этой вашей копии. Если приложение уже работает,
не повторяйте исходный apply поверх своих упражнений: начните с чтения status.
Краткая памятка ниже не заменяет подготовку и проверку каждого шага.

Краткий порядок на своём уже принятом кластере (из каталога labs):
  export LAB_CONTEXT=handbook-admin  # либо kind-handbook; не менять молча
  kubectl --context "$LAB_CONTEXT" get nodes -o wide
  kubectl --context "$LAB_CONTEXT" apply --server-side --field-manager=handbook -f manifests/00-namespace.yaml
  kubectl --context "$LAB_CONTEXT" -n lab diff --server-side --field-manager=handbook -f manifests/10-app.yaml
  # Read the diff. Exit 1 means changes; exit >1 stops this procedure.
  kubectl --context "$LAB_CONTEXT" -n lab apply --server-side --field-manager=handbook -f manifests/10-app.yaml
  kubectl --context "$LAB_CONTEXT" -n lab rollout status deployment/ledger-api --timeout=120s
  kubectl --context "$LAB_CONTEXT" -n lab port-forward service/ledger-api 18080:80 --address=127.0.0.1
В другом терминале curl -fsS http://127.0.0.1:18080/api/hello.
Перед этим образ ledger-api:0.1.0 должен быть собран и загружен в каждый node
(kind load docker-image либо ctr -n k8s.io images import в личных VM).
Файл10-app рассчитан на локальный образ и IfNotPresent. Для registry замените
image на реальный immutable digest и проверьте TLS/auth. Заглушек digest нет.

20-rbac выдаёт investigator чтение и logs; не exec, secrets, update, delete.
30-policy включать отдельно после baseline: нужен CNI enforcement; kindnet
по умолчанию policy не обеспечивает. Port-forward не является тестом policy.
40-availability НЕ применять вместе с ручным scale до раздела HPA: HPA станет
владельцем числа replicas и требует metrics-server, которого набор не ставит.
50-storage/51-data-job — отдельное упражнение VM/local PV, имя node wk1,
каталог /srv/handbook/ledger-data заранее создан владельцем VM под uid65532.
Нет CSI, автоматического provisioner или обещания failover на другой node.
BusyBox 1.37.0 закреплён проверенным OCI index digest в Job и diagnostic.yaml;
его bytes также заранее staged на nodes.

Не удаляйте namespace между заданиями. Сохраняйте журнал UID, revision,
образов, времени и результата. kubectl delete namespace lab — явное финальное
уничтожение; PVC/reclaim/внешние диски и backup проверяются до него.
Helm использует namespace helm-lab/release ledger и свои ресурсы: не передавать
один Deployment двум владельцам. Контракт HTTP тот же, lifecycle отдельный.

Дополнительно http_measure.py измеряет HTTP с явными единицами, количеством
успехов/ошибок и nearest-rank квантилями. Это closed-loop клиент; запрос через
port-forward не доказывает Service dataplane или capacity всего кластера.
vm/ownership-a.yaml и vm/ownership-b.yaml — два намерения для одного учебного
ConfigMap. vm/scheduling-probe.yaml — отдельный Deployment для request-отказа,
его Pods не выбираются Service ledger-api. Эти файлы не применяют все сразу.

Дополнительно vm/diagnostic.yaml содержит два клиента для VM Calico policy: один
явно допускается на cp1 через toleration, другой без access label; control-plane
taint не снимается. vm/workload-patterns.yaml — независимые формы RS/StatefulSet/
DaemonSet/CronJob, не применять одновременно на маленькой машине. Их schema
проверяется локально, cluster lifecycle не исполнялся.
