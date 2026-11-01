SONARQUBE: ОДИН ЛИЧНЫЙ ЭКЗЕМПЛЯР И НАСТОЯЩИЕ ВХОДЫ GO
Редакция 1 ноября 2026.

Комплект не является браузерной эмуляцией сервера. При открытии книги ничего
не устанавливается и команды не исполняются. Используйте свой стенд.

1. СОСТАВ
compose.yaml — Community Build + PostgreSQL17 на своём Docker Engine.
init-sonar-db.sh — init официального PostgreSQL image: создаёт отдельную
LOGIN-роль sonar, без superuser, и принадлежащую ей БД.
compose.restore.yaml — изоляция исходящих соединений репетиции восстановления.
sonar-project.properties — область собственного Go-проекта.
prepare_reports.py — реальные go test JSONL/coverage + go vet, стандартный Python.
test_reports.py — реальные проверки helper на временной копии общего Go-сервиса.
backup-db.sh — новый уникальный набор, временный dump, проверка TOC/SHA/COMPLETE.
restore-db.sh — новая цель: wait+SQL → транзакционный restore → запуск Sonar.
test_db_scripts.py — Bash с stub Docker CLI; не тест настоящей PostgreSQL.
Dockerfile.scanner-go — подготовка scanner image с отдельной Go toolchain.
gitlab-ci.yml / Jenkinsfile — оригинальные варианты интеграции.

2. УСТАНОВКА
Подробный маршрут находится в главах 02–04. Выберите свою Linux-VM, подготовьте
Docker Engine/Compose, пределы ядра и ресурсы. Скопируйте compose.yaml вместе
с init-sonar-db.sh в один личный каталог. Получите официальный
sonarqube:26.10.0.133078-community и образ семейства postgres:17.
Запишите реальные RepoDigests в частном images.env:
SONAR_IMAGE=sonarqube@sha256:ВАШ_РЕАЛЬНЫЙ_DIGEST
POSTGRES_IMAGE=postgres@sha256:ВАШ_РЕАЛЬНЫЙ_DIGEST
Это форма записи, не готовые придуманные идентификаторы.

Подготовьте разные частные SONAR_DB_PASSWORD и POSTGRES_ADMIN_PASSWORD.
Bootstrap postgres и приложение sonar имеют разные роли.
docker compose --env-file images.env config --quiet
docker compose --env-file images.env up -d
Не публикуйте полный config: он способен показать значения окружения.
Исходный адрес: 127.0.0.1:9000 на VM. Для другого ПК используется свой
разрешённый SSH-туннель либо заранее настроенный HTTPS-вход.

Данные сохраняются в именованных томах handbook-sonar_*.
stop/start продолжает тот же экземпляр. down -v уничтожает тома этого проекта.
POSTGRES_USER/PASSWORD/DB и init-скрипт не переинициализируют уже заполненную БД.
Параметр SONAR_BIND_PORT меняет опубликованный порт (по умолчанию 9000).

3. GO-БЕЗ-СЕРВЕРА
Используется тот же пример go/labs/service основной книги:
module example.org/handbook-service, /healthz, /greet, -version.
Скопируйте его в собственный проект; не меняйте общую книгу.
В .gitignore собственного проекта добавьте:
reports/
.scannerwork/
.sonar/
Не заменяйте уже имеющиеся правила ignore целиком.

Команда из любого каталога, пути подставляются собственные:
python3 /ПУТЬ/К/prepare_reports.py --project /ПУТЬ/К/ПРОЕКТУ --go /ПУТЬ/К/go

Подготавливает reports/test.jsonl, coverage.out, test-stderr.txt, vet.txt,
reports-manifest.json. Старые собственные отчёты предварительно удаляются.
Ненулевой test или vet дают код 1. Некорректная подготовка даёт код 2.
GOFLAGS очищается, GOWORK=off, GOTOOLCHAIN=local, CGO_ENABLED=0.
Это профиль pure-Go примера, не заявление о пригодности всех cgo-проектов.
Manifest хранит версию, команду/коды и хеши; он не подписан и не является
серверным заключением или удостоверением Git-происхождения.

4. НАСТОЯЩИЙ АНАЛИЗ
Создайте свой projectKey handbook-service и узкий проектный analysis token.
Скопируйте sonar-project.properties в корень той же ревизии, где получены
отчёты. Подготовьте SonarScanner CLI на машине с Go для импорта покрытия.
Адрес и токен передаются через SONAR_HOST_URL и SONAR_TOKEN.
sonar-scanner -Dsonar.qualitygate.wait=true -Dsonar.qualitygate.timeout=300
Проверьте ceTaskId, обработку CE, analysisId, реальные метрики и gate.
Community-пример анализирует только основную ветку; MR-функции не обещаются.

5. CI И ВОССТАНОВЛЕНИЕ
GitLab-пример требует подготовленные immutable GO_IMAGE/SONAR_GO_IMAGE,
доступный URL, protected token и соответствующий Runner.
Jenkins-пример требует plugin/server installation handbook-sonar, агент
go-sonar с инструментами, доступный webhook и отдельный sonar-webhook secret.
Шаблоны не создают автоматически сервер, Runner, Jenkins или credentials.

Backup: скопируйте helper в свой каталог инструментов. Выполняйте отдельным Bash:
bash ./backup-db.sh /ПУТЬ/К/ЭКЗЕМПЛЯРУ /ПУТЬ/К/ЧАСТНЫМ/КОПИЯМ
Каждый запуск создаёт новый уникальный набор. Старый sonar.dump не обнуляется.
При отказе dump/TOC/проверки новый набор не принимается; прежние сохраняются.
Только после успеха выводится принятый путь с COMPLETE и SHA.
TOC/SHA не заменяют настоящую репетицию восстановления.

Restore: явно выберите один принятый набор, отдельный НОВЫЙ Compose project,
например handbook-sonar-restore-01, порт 19001, compose.restore.yaml и прежнюю
совместимую версию. Helper сначала проверяет набор и отсутствие ресурсов цели,
затем up --wait --wait-timeout 180 db, затем настоящий SQL-вход/пустую БД.
После этого pg_restore --exit-on-error --single-transaction, и только при
успехе запуск Sonar. Ошибка любой ступени останавливает весь сценарий.
bash ./restore-db.sh /ПУТЬ/К/КАТАЛОГУ/ВОССТАНОВЛЕНИЯ \
  /ПУТЬ/К/ПРИНЯТОМУ/backup-ИМЯ handbook-sonar-restore-01 19001
--no-owner/--no-privileges ограничены нашим примером одного владельца.
Для большой БД общая транзакция требует отдельной оценки ресурсов;
никакой универсальный параллельный restore helper здесь не заявлен.
Полный разбор каждой ступени и флага находится в главе 12.
После запуска Sonar ещё требуется прикладная приёмка/индексирование.

6. ЧТО ПРОВЕРЕНО
Реально выполнены 5 regression-тестов prepare_reports.py с Go 1.27.3:
успешные нативные отчёты текущего приложения и их SHA;
намеренный fail теста не скрыт успешным vet/старым отчётом;
унаследованные неверные GOFLAGS/GOWORK не меняют договор;
символьная ссылка не перезаписывает посторонний файл;
отсутствующий Go-модуль отклоняется до запуска.
Команда:
HANDBOOK_GO=/СВОЙ/go python3 -m unittest discover -s sonarqube/labs -p test_reports.py -v
Локальный наблюдённый результат: 5 tests OK, 7.787s.
Число секунд — наблюдение конкретной машины, не целевая скорость чужого стенда.

Полный SonarQube Server/Community, реальный CI, реальный импорт Go в Sonar,
webhook и backup/restore не запускались в подготовке этой редакции.
Для них книга даёт собственный маршрут с критериями приёмки.
Они не объявляются проверенными за счёт локального go test.

Дополнительно: 5 source-checks прошли (главы/реальные ссылки/схемы/словарь/схема карточки).
Настоящий Docker Compose CLI принял base и isolated-restore конфигурации
с синтетическими входами; проверены project/порт 19001/internal-network/healthcheck.
Контейнеры этой проверкой не создавались. YAML GitLab разобран, но CI Lint и
живой GitLab/Jenkins не выполнялись. bash -n init-скрипта прошёл.

После независимой вычитки добавлены 7 shell-controlflow regression-тестов:
исполняют настоящий Bash с временной stub-командой docker.
Проверяют backup failure/empty/TOC, сохранность старого файла/уникальность,
ready→SQL→restore→start и прекращение цепочки на отказе любой ступени.
Также проверяют неверную роль/непустую цель, существующие ресурсы,
изменённый checksum и отсутствие COMPLETE. Реальный сервер/restore ими
не подтверждается; все данные в этих тестах синтетические.
Полный набор 5 Go + 5 source + 7 controlflow:
HANDBOOK_GO=/СВОЙ/go python3 -m unittest discover -s sonarqube/labs -p 'test_*.py' -v
После ремонта полный набор: 17 tests OK, 2.336s с Go 1.27.3.
Результат и границы также сохранены в sonarqube/ПРОВЕРКИ.txt.
