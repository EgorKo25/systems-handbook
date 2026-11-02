Terraform — собственный продолжаемый локальный стенд
Редакция: 01.11.2026. CLI строго 1.17.1. Python3, пользовательские права.

Назначение:
terraform_data сохраняет значения и IDs в local state, не создаёт VM.
Два creation provisioner записывают JSON только в помеченную область.
Эти файлы не имеют provider Read: drift файла невидим для terraform_data.
Это проверяемая граница, а не универсальный способ управлять файлами.

Из каталога тома terraform/:
TF_LAB_TOOLS="$PWD/labs"
umask 077
mkdir -p "$HOME/terraform-learning/stands" "$HOME/terraform-learning/snapshots"
TF_LAB_ROOT="$HOME/terraform-learning/stands/foundation"
TF_LAB_SNAPSHOT="$HOME/terraform-learning/snapshots/foundation-checkpoint-1"
if python3 "$TF_LAB_TOOLS/lab.py" prepare "$TF_LAB_ROOT"; then
  cd "$TF_LAB_ROOT" &&
  terraform init -input=false &&
  terraform validate &&
  terraform plan -out=first.tfplan &&
  terraform show first.tfplan &&
  terraform apply first.tfplan &&
  terraform plan -detailed-exitcode
else
  printf '%s\n' 'Подготовка отказала; дальнейшие Terraform-команды не выполнены.' >&2
fi

Дальше тот же каталог и те же переменные: глава tf-21-lab описывает
drift, update/replacement, moved, lock conflict, stale plan, partial apply,
repair и явный restore. prepare второй раз не запускают: он не reset.
В новом shell значения TOOLS/ROOT восстанавливают по фактическим путям
своей копии, не создают другой корень вместо продолжения state.
Сам foundation до prepare не создают: требуется новый отсутствующий путь.
Рабочая область и snapshot постоянные, вне /tmp; сохраните эти пути,
путь/версию CLI, marker и backend=local в собственном паспорте стенда.
Резерв на том же диске не переживает отказ диска: переносите проверенную
копию в отдельное собственное хранилище. mktemp используют только тесты.

Snapshot при остановленных Terraform-процессах:
python3 "$TF_LAB_TOOLS/lab.py" snapshot "$TF_LAB_ROOT" "$TF_LAB_SNAPSHOT"
Restore при остановленных процессах:
if python3 "$TF_LAB_TOOLS/lab.py" restore "$TF_LAB_ROOT" "$TF_LAB_SNAPSHOT"; then
  cd "$TF_LAB_ROOT" &&
  terraform init -input=false &&
  terraform plan
else
  printf '%s\n' 'Restore отказал; дальнейшие Terraform-команды не выполнены.' >&2
fi

Snapshot/restore проверяет marker/checksums, сохраняет старую область
*.before-restore и не перезаписывает существующую резервную копию.
Этот способ возвращает весь учебный local-only stand: source/state/files.
Он НЕ возвращает внешнюю инфраструктуру и не предназначен для remote
backend. Остановка процессов обязательна; lock-info не полноценный freeze.

Независимая реальная проверка, из каталога тома:
python3 labs/check.py --terraform terraform
Сценарий создаёт собственный TemporaryDirectory, проходит 15 наблюдений
в одной цепочке state, затем удаляет только её. Читательский state и чужие
файлы не выбираются. Нет покупки облака, root-операций, SSH, установки
служб, обращения к libvirt. Дополнительные HCL fixtures проверяются
python3 labs/check_language.py --terraform terraform

Локальное измерение в отдельной временной области:
python3 labs/benchmark.py --terraform terraform --counts 10,100 --repeats 5
Пять наблюдений — не достаточная оценка p95; сохраняются median/min/max.

adapters/libvirt/ — отдельный проверяемый рецепт CLI1.17.1/provider0.9.9
для уже подготовленной личной Linux VM, не часть foundation/check apply.
check_schema.py выполняет только init/schema/validate, без plan/apply/API.
Описание диска/сети/версий и ограничений — в его README.txt.

Ни один тест не является общей сборкой библиотеки. build.py не запускать
при авторской работе: его wrapper меняет общий каталог и главную.

Передача в Ansible:
foundation contract api/worker — учебные записи, не inventory и не запущенные
процессы. Libvirt adapter описывает один domain api, не пару counter_a/counter_b.
После реального собственного boot получают и сверяют UUID/диск/IP/host key;
лишь затем заполняют private inventory Ansible и проверяют SSH/Python.
В паспорте держат root/backend/address ресурса, UUID/диск VM, inventory-имя,
release/SHA и /var/lib/counter/count.txt. Возврат state не откатывает файл данных.

Дополнение source-only, 02.11.2026:
После шага4 практикума можно сравнить state с файлами без изменения стенда:
  set -o pipefail
  terraform show -json | python3 "$TF_LAB_TOOLS/observe.py" --root "$TF_LAB_ROOT"
observe.py только читает уже переданный JSON view и собственные rendered-файлы.
Проверяет прежний service и переименованный node; не делает refresh/API.
Отсутствие файла даёт null и receipt_matches=false; неверный JSON — отказ.
Вывод содержит ID/поля учебных объектов, его также хранят в собственной области.

Чистая модель, без Terraform и записи:
  python3 -B "$TF_LAB_TOOLS/mechanism_model.py"
Из корня тома:
  python3 -B tests/check_mechanisms.py
Это вычисления с условными ID и JSON fixtures. Они не воспроизводят init/apply
и не заменяют сохранённые native tests. Новые nullable/try validations в foundation
сверены статически; их фактический validate/plan/fmt проверит интегратор.
