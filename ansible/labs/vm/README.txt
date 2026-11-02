MULTI-VM РЕЦЕПТ, НЕ РЕЗУЛЬТАТ ИСПОЛНЕНИЯ

Назначение: две собственные Debian/Ubuntu Linux VM с systemd, SSH и Python
из поддерживаемого диапазона target core2.21.5 (3.9–3.14). Этот рецепт не
создаёт VM и не покупает облако. Привилегированные задачи исполняются только
в этих личных VM. На хосте пользователя их не запускать.

Рабочие каталоги различаются: inventory/site.yml команды ниже выполняют
из своей сохранённой копии labs/vm, содержащей ansible.cfg и roles/.
Перейдите в неё до пункта 2 и запишите абсолютный путь проекта в частной
заметке. Это не каталог service и не корень книги. Команды Go пункта 3
выполняют в отдельном терминале из исходного ansible/labs/service, где
находятся go.mod/main.go. Терминал VM-проекта остаётся в прежнем каталоге.

1. Зафиксируйте ОС/архитектуру каждой VM, snapshot VM и способ возврата.
   Подготовьте deploy-пользователя, SSH-ключи, проверенный fingerprint сервера,
   known_hosts, разрешённый sudo и Python. Не выключайте host_key_checking.
   Сохраните inventory-имена counter_a/counter_b на все упражнения.
2. Скопируйте hosts.example.yml в private inventory/hosts.yml, замените
   documentation-only адреса 192.0.2.11/12 адресами своих VM. Файл hosts.yml
   публичного комплекта намеренно отсутствует. Проверьте без изменения ОС:
     ansible-inventory -i inventory/hosts.yml --graph
     ansible counters -i inventory/hosts.yml -m ansible.builtin.ping
     ansible counters -i inventory/hosts.yml -m ansible.builtin.command -a id
     ansible counters -i inventory/hosts.yml -m ansible.builtin.command -a id -b -K
3. Перейдите в исходный ansible/labs/service в отдельном терминале сборки.
   Проверьте наличие go.mod/main.go; это не копия labs/vm. Соберите сервис
   на отдельном совместимом Go toolchain (go.mod требует
   минимум Go1.24). Для первой версии на своей сборочной машине:
     GOTOOLCHAIN=local go test ./...
     CGO_ENABLED=0 GOTOOLCHAIN=local GOOS=linux GOARCH=amd64 go build -trimpath -ldflags='-X main.version=0.1.0' -o counter-0.1.0 .
     sha256sum counter-0.1.0
   GOARCH должен соответствовать target; arm64 требует иной файл/manifest.
   Сохраните версию Go, исходный commit, build flags, OS/arch и SHA-256 в
   manifest. Тесты нельзя заменять одним успешным build. Полученный SHA
   фиксируют доверенно; калькуляция рядом с уже подменённым бинарником
   сама не восстанавливает его происхождение.
4. Вернитесь в терминал своей сохранённой VM-копии labs/vm: здесь находятся
   site.yml и ansible.cfg. Создайте частный release-vars.yml, например:
     counter_personal_vm: true
     counter_release: '0.1.0'
     counter_artifact: /абсолютный/путь/к/counter-0.1.0
     counter_sha256: 'ЗАМЕНИТЬ_64_HEX_ИЗ_ДОВЕРЕННОГО_МАНИФЕСТА'
   Шаблон не является готовым к выполнению значением. Путь controller,
   сведения доступа и secrets не публикуют. Стенд намеренно ограничен
   fixed /opt/counter, /etc/counter, /var/lib/counter и loopback:8080.
   Адаптация путей/порта требует согласованного изменения проверок/probes.
5. В каталоге labs/vm выберите cfg и проверьте состав:
     export ANSIBLE_CONFIG="$PWD/ansible.cfg"
     ansible-playbook site.yml -i inventory/hosts.yml -e @release-vars.yml --list-hosts
     ansible-playbook site.yml -i inventory/hosts.yml -e @release-vars.yml --syntax-check
   Затем только в личных VM:
     ansible-playbook site.yml -i inventory/hosts.yml -e @release-vars.yml --limit counter_a -b -K --diff
   На пустой VM --check не моделирует создание пользователя/каталогов/бинарника
   для следующих задач: используйте его осмысленно после bootstrap, не как
   доказательство отсутствия записей произвольного playbook.
6. Приёмка из VM (через свой SSH, вручную или безопасные read-only задачи):
     systemctl status counter
     readlink /opt/counter/current
     /opt/counter/current/counter --version
     curl --fail http://127.0.0.1:8080/version
     curl --fail http://127.0.0.1:8080/counter
     curl --fail -X POST http://127.0.0.1:8080/counter
   POST увеличивает сохраняемый count; GET только читает. Приложение не имеет
   аутентификации и намеренно слушает loopback. Для удалённого доступа нужен
   собственный проверенный access contract, здесь он не разворачивается.
   Не удаляйте /var/lib/counter между версиями. У двух VM независимые счётчики:
   это не кластерное хранилище и не общий глобальный counter.
7. Добавьте несколько POST-записей, зафиксируйте GET count и snapshot данных
   явно с остановкой писателя/сервиса. Копия одного файла во время неизвестного
   изменения не равна согласованному резерву общего приложения.
8. Соберите 0.2.0 из того же исходного проекта с новым -X main.version,
   отдельным бинарником/SHA и новым private vars. Сначала counter_a, затем
   весь inventory. Serial1 + any_errors_fatal не допускает следующую VM при
   failed. В сценарии проверяются SHA, compiled version, validated config,
   active link, handler flush, HTTP version и непрерывность count (не меньше
   предыдущего значения). При неизменных входах повтор должен не менять
   файлы и не перезапускать процесс: counter_force_restart по умолчанию false.
9. Неявный gather_facts выключен. Проверка выбранной личной цели и
   controller artifact через stat SHA256 выполняются с delegate_to localhost
   и become:false до target transport; лишь затем явный setup собирает
   facts на target. Это предохранитель доверенного рецепта, не изоляция
   произвольного plugin/playbook. Существующий верный release
   никогда не передаётся повторному copy; file поправляет только metadata.
   Отсутствующий файл копируется, затем SHA/version повторно проверяются
   уже на target до активации. Подмена source artifact на controller должна
   остановить preflight без записи в действующий target release.
   Смоделируйте осмысленный отказ в своей VM: неверный SHA должен отвергнуться
   до перезаписи уже существующей release-version; неверный config — до
   switch. Не подменяйте имя уже выпущенной версии другими байтами: каталог
   releases/<version> считается неизменным. Rescue восстанавливает предыдущие
   config/link этой попытки, перезапускает прежний процесс и проверяет health, прежнюю /version и count,
   затем явно оставляет rollout failed. Если старая служба сломана до запуска,
   preflight остановит play до попытки — сначала диагностируйте её отдельно.
10. Потеря SSH, kill controller и reboot между switch/handler/health не являются
    транзакцией rescue. Через консоль VM проверьте link, config, process version
    и данные. Если файлы уже новые, а процесс старый, следующий обычный запуск
    может не получить notify. Выберите явный recovery:
      ansible-playbook site.yml -i inventory/hosts.yml -e @release-vars.yml --limit counter_a -e '{"counter_force_restart":true}' -b -K
    Это осознанно перезапускает службу и потому changed, не идемпотентный no-op.
    Для возврата версии создайте vars для сохранённого 0.1.0/SHA и примените
    их явно. Не откатывайте data вместе с бинарником, если это не требуется
    проверенной совместимостью формата. Наши версии используют один формат
    uint64 + newline и не делают migrations. Универсального rollback данных нет.
11. Перед обновлением core/collections/OS сохраните текущий комплект и прогоните
    local checks плюс этот сценарий на клоне snapshot. Совместимость Python,
    пакетов ОС, systemd directives и архитектуры проверяется независимо.

Ограничения: SSH/sudo/systemd, два независимых target и реальный partial
network failure в этой редакции не исполнялись. Рецепт не содержит LB, TLS,
кластерной БД или блокировки двух одновременно запущенных controller. Для
стенда действует один оператор/запуск в момент изменения. Сохраняемые данные
и частные credentials не входят в публичный комплект.

Дополнительная изолированная проверка controller preflight:
Следующую команду выполняют из корня исходной копии тома ansible/,
где находятся каталоги tests/ и labs/. Это не каталог labs/vm и не
отдельная личная VM-копия проекта; при необходимости откройте исходный
том в другом терминале, сохранив прежний рабочий каталог стенда.
python3 tests/preflight_check.py --ansible-bin /путь/к/подготовленному/bin
Fake SSH только отмечает попытку вызова и отказывает: сеть не используется.
Сервисные go test -race проверяют завершение активного HTTP перед Shutdown
и конечный deadline; это отдельные loopback-тесты, не запуск systemd.
