Сохраняемый стенд Prometheus / Go

1. Выберите собственную Linux-VM либо личный пользовательский процесс.
   Привяжите HTTP к 127.0.0.1. Не меняйте рабочие серверы.
2. Получите официальный Prometheus/promtool 3.13.5, проверьте SHA-256
   по официальному release. Бинарники не входят в исходники тома.
3. Один раз создайте prom-lab/{bin,config,data,evidence,go-service,fixtures}.
   Копируйте prometheus.yml и rules.yml в config/, Go-проект в go-service/.
   Скопируйте ВЕСЬ labs/fixtures/ в prom-lab/fixtures/, включая
   alert-rules.yml: promql.yml ссылается на соседний файл.
   Относительный rules.yml разрешается от каталога prometheus.yml.
4. Из prom-lab:
   bin/promtool check config config/prometheus.yml
   bin/prometheus --config.file=config/prometheus.yml --storage.tsdb.path=data \
     --web.listen-address=127.0.0.1:9090 --storage.tsdb.retention.time=7d
5. Откройте другой терминал и перейдите в тот же prom-lab.
   Следующие строки выполняются из его корня:
   cd go-service
   go mod download
   go test -race ./...
   go build -o ../bin/lab-service .
   ../bin/lab-service -port 18080
   Последняя команда занимает Go-терминал до остановки процесса.
   После его штатной остановки выполните cd .. для возврата в prom-lab.
   Терминал наблюдений откройте отдельно и начните в prom-lab:
   bin/promtool test rules fixtures/promql.yml
6. Читайте prom-19-lab по порядку. История, имена и data сохраняются.
   Нет автоматического reset. Snapshot/rollback — явные действия читателя.

Офлайн: подготовьте toolchain, архивы/суммы, go.mod/go.sum и module cache
либо vendor заранее. Для vendor выполните go mod vendor на сетевой машине,
сохраните всю полученную директорию и собирайте go build -mod=vendor.
Эта операция не выполнена в опубликованном дереве: библиотека не включает
сторонние исходники модулей и бинарники.

Автоматическая проверка из каталога prometheus/:
python3 tests/check_sources.py
python3 labs/check.py --prometheus /path/to/prometheus \
  --promtool /path/to/promtool --go /path/to/go/bin/go --module-cache /path/to/prepared-modules

Второй скрипт требует именно Prometheus/promtool 3.13.5; ничего не
скачивает и не устанавливает. Параметр --module-cache задаёт заранее подготовленный GOMODCACHE:
скрипт копирует его во временную область, отключает сетевой module lookup
и задаёт временные GOPATH/GOCACHE. Изменения go.mod/go.sum запрещены. Он использует TemporaryDirectory, свободные
loopback-порты, отдельное TSDB-хранилище и завершает только свои процессы.
Временная проверка НЕ удаляет сохраняемый prom-lab/data.

fixtures/promql.yml — положительные тесты настоящего engine.
fixtures/many-to-many-invalid.yml — специально неверный join: runner
ожидает отказ с many-to-many matching not allowed. Не включать его
в набор «все YAML должны пройти promtool test rules» без учёта назначения.

Все числовые fixtures заданы вручную. Они проверяют семантику языка,
а не воспроизводят реальную сетевую нагрузку. Пошаговые схемы книги
показывают фиксированную модель; JavaScript не исполняет PromQL.
