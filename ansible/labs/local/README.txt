Это настоящая файловая лаборатория Ansible, без SSH, systemd и become.
Два имени counter_a/counter_b исполняются local и используют разные каталоги.
Все изменяемые пути и remote/local temp должны находиться под корнем /tmp/ansible-*.
Не запускайте site.yml с become и не подставляйте каталог пользователя.

Рабочий каталог следующих команд — исходный ansible/labs/local.
Проверьте, что рядом есть site.yml, ansible.cfg и inventory.ini; путь
../../tests относится к полной исходной копии тома. Если сохраняли только
local/, автоматические tests запускают отдельно из исходного ansible/.

При уже установленном в отдельном окружении ansible-core 2.21.5:
  export PATH="$HOME/ansible-lab-tools/bin:$PATH"
  python3 ../../tests/lab_check.py
Скрипт сам создаёт временный корень, исполняет последовательность и в конце
удаляет только собственный TemporaryDirectory. Вывод сохраняет PASS-пункты.
Это проверка исходников; для самостоятельных сохраняемых упражнений ниже
не применяется автоматическое удаление.

Учебный корень, сохраняемый между последовательными командами:
  export ANSIBLE_CONFIG="$PWD/ansible.cfg"
  export ANSIBLE_LAB_ROOT="$(mktemp -d /tmp/ansible-reader-lab-XXXXXX)"
  export ANSIBLE_LOCAL_TEMP="$ANSIBLE_LAB_ROOT/controller-tmp"
  export ANSIBLE_REMOTE_TEMP="$ANSIBLE_LAB_ROOT/remote-tmp"
  export ANSIBLE_COLLECTIONS_PATH="$ANSIBLE_LAB_ROOT/collections"
  export ANSIBLE_ROLES_PATH="$ANSIBLE_LAB_ROOT/roles"
  export ANSIBLE_HOME="$ANSIBLE_LAB_ROOT/ansible-home"
Выведите путь через printf и сохраните его в частной заметке.
/tmp может очищаться при перезагрузке: для следующего занятия сначала
проверьте наличие корня. Если нужен перенос, явно остановите изменяющие
действия и сохраните его копию в своём постоянном хранилище; затем
восстановите прежний изолированный /tmp/ansible-* путь и его переменные.
Это учебная файловая лаборатория; постоянные данные VM-версии живут
в /var/lib/counter на диске VM. Новый запуск shell не должен
создавать другой корень вместо продолжения прежнего.

Создайте файл vars.json внутри своего корня:
{"lab_root":"/tmp/ansible-reader-lab-ЗАМЕНИТЬ",
 "ansible_python_interpreter":"/ПРОВЕРЕННЫЙ/venv/bin/python"}
Пути заполните фактическими значениями; это документ с данными, не shell-код.
Первый запуск и повтор:
  ansible-playbook site.yml -e @"$ANSIBLE_LAB_ROOT/vars.json"
  ansible-playbook site.yml -e @"$ANSIBLE_LAB_ROOT/vars.json"
Первый изменит config/data/applied, второй должен дать changed=0 по каждому host.

Явный snapshot (не reset):
  cp -a "$ANSIBLE_LAB_ROOT/counter_a" "$ANSIBLE_LAB_ROOT/snapshot-a"
  cp -a "$ANSIBLE_LAB_ROOT/counter_b" "$ANSIBLE_LAB_ROOT/snapshot-b"
Измените count.txt на 41 в обоих data, затем примените другую desired version:
  ansible-playbook site.yml -e @"$ANSIBLE_LAB_ROOT/vars.json" -e counter_release=0.2.0 --check --diff
Проверьте: config остался 0.1.0, count=41. Потом тот же вызов без --check:
  ansible-playbook site.yml -e @"$ANSIBLE_LAB_ROOT/vars.json" -e counter_release=0.2.0 --diff
Конфигурация и marker теперь 0.2.0, count всё ещё 41.
Возврат конфигурации делается явным desired counter_release=0.1.0, а данные
не восстанавливаются автоматически. Восстановление snapshot data — отдельное
решение с потерей более новых записей; сначала сделайте копию текущих данных.

Семантика языка:
  ansible-playbook precedence.yml -e @"$ANSIBLE_LAB_ROOT/vars.json"
  ansible-playbook precedence.yml -e @"$ANSIBLE_LAB_ROOT/vars.json" -e '{"counter_port":8085,"counter_expected_port":8085,"extra_case":true}'
  ansible-playbook reuse.yml -e @"$ANSIBLE_LAB_ROOT/vars.json"
  ansible-playbook failure.yml -e @"$ANSIBLE_LAB_ROOT/vars.json"
  ansible-playbook serial.yml -e @"$ANSIBLE_LAB_ROOT/vars.json"
Ожидаемый failed в failure.yml будет rescued, это не реальный отказ сети.

Не очищайте корень между упражнениями. Удаление стенда — отдельное действие
после проверки сохранённых результатов; команда автоматического reset не даётся.
