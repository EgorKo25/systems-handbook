Проверяемый адаптер, не часть автоматического apply
Редакция: 01.11.2026; Terraform 1.17.1; dmacvicar/libvirt 0.9.9.

Целевая среда: отдельная собственная Linux VM с подготовленной libvirt
system connection qemu:///system ВНУТРИ этой личной VM. Используется type=qemu, не обещается KVM
или nested virtualization. Провайдер — сторонний community project;
его документация является первичным источником именно его схемы.

Источники точной версии:
https://github.com/dmacvicar/terraform-provider-libvirt/blob/v0.9.9/docs/index.md
https://github.com/dmacvicar/terraform-provider-libvirt/blob/v0.9.9/docs/resources/domain.md
https://github.com/dmacvicar/terraform-provider-libvirt/releases/tag/v0.9.9
https://libvirt.org/uri.html

В 0.9 структура domain использует os/devices attributes-объекты.
Не подставляйте старые примеры 0.8 с другой схемой блоков.
Remote URI в provider docs этой версии помечен not yet implemented;
не обещается qemu+ssh transport. Клиент CLI можно запускать внутри
личной VM. На хосте пользователя libvirt не устанавливался.

Сначала подготовить согласованный профиль (это инструкции для личной VM,
не разрешение менять рабочий хост): получить libvirt-daemon-system,
libvirt-clients, qemu-system-x86 и qemu-utils из доверенного APT Ubuntu24.
Проверить пакеты/службы и разрешить выбранной учётной записи управление
через принятую в этой VM polkit/group policy; при смене групп открыть новый
login и проверить id. Не запускать Terraform через sudo ради обхода ошибки:
так изменятся identity, пути credentials и владение state.

Нужна собственная активная managed network в ЭТОЙ ЖЕ qemu:///system области.
Для её первого создания используют virsh net-define своего XML, затем
net-start; адресный диапазон, NAT/изоляцию и пересечения выбирает владелец.
Синтаксис XML и профиль Ubuntu: https://libvirt.org/formatnetwork.html
https://ubuntu.com/server/docs/how-to/virtualisation/libvirt/
Перед Terraform выполняют чтение с тем же URI:
  id
  virsh --connect qemu:///system version
  virsh --connect qemu:///system capabilities
  virsh --connect qemu:///system net-list --all
  virsh --connect qemu:///system net-info ИМЯ_СВОЕЙ_СЕТИ
  virsh --connect qemu:///system net-dumpxml ИМЯ_СВОЕЙ_СЕТИ
  qemu-img info --output=json /абсолютный/путь/к/своей-копии.qcow2
Нужно подтвердить активность своей сети и format=qcow2 у расходуемой копии.
Session network другого URI не подходит. Не изменять права всем на каталоги:
пользователь QEMU и политика ОС должны иметь доступ к выбранному диску.
В devices.disks driver явно qemu/qcow2: расширение пути формат не задаёт.
Копия диска уже подготовлена владельцем; base image другой VM не используем.

До plan: скопировать каталог в новую личную VM; проверить источник CLI
и provider, init, providers schema -json, validate; сохранить lock file.
Уточнить libvirt/QEMU версии в VM и проверить формат image. Образ нужен
как собственная расходуемая копия qcow2, с проверенной ОС, checksum и
лицензией. Не использовать диск действующей VM: QEMU будет его менять.
Сеть уже должна быть собственной и подготовленной владельцем; adapter
её не создаёт. SSH-user, host key и bootstrap готовятся в образе/отдельной
проверенной cloud-init поставке, здесь не изобретается универсальный default.

terraform plan -var-file=personal.tfvars -out=vm.tfplan
terraform show vm.tfplan
terraform apply vm.tfplan

start_guest=false по умолчанию: создаёт описание domain, не обещает boot.
Только после проверки собственного диска/сети задать start_guest=true,
сделать новый plan, затем отдельную приёмку VM, IP, SSH и Go-службы.
Получаем uuid/name; IP не угадывается из имени. Его надо получить из
предусмотренного источника libvirt/network/guest и проверить соответствие
uuid, MAC и адреса. IP и SSH-host-key входят в отдельный контракт доступа.

Destroy только собственный domain по проверенному state/URI и личной
VM; не запускать его в случайном каталоге. Этот пример не владеет
image_path как libvirt_volume: не обещается удаление диска при destroy.
По завершении данные и образ убирает владелец согласно явной карте.

Статус проверки указан в ПРОВЕРКИ.txt. Установки гипервизора, создания
network/domain, запуска гостя и подключения SSH автор не выполнял.

Безопасный повтор формы схемы без libvirt API:
python3 labs/adapters/libvirt/check_schema.py --terraform terraform
Сценарий копирует только адаптер во временную область, использует пустой
CLI-конфиг и выполняет init -backend=false -lockfile=readonly, validate,
providers schema -json. Никаких plan/apply. Для заранее подготовленного
filesystem mirror добавить --mirror /YOUR/PRIVATE/provider-mirror:
fallback direct отсутствует, поэтому registry сеть при этом не нужна.

Реальная проверка выявила неточность upstream Example Usage 0.9.9:
boot_devices там показан как ["hd"], но schema требует [{dev="hd"}].
В этом адаптере используется подтверждённая schema форма.
