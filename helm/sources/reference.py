"""Original Russian glossary and Helm 4.3.1 command cards. Import has no effects."""
GLOSSARY = [
('Helm','Клиентский инструмент получения Kubernetes-манифестов из пакетов и управления историей именованных релизов. Не является кластером, планировщиком или резервной копией приложения.'),
('CLI','Command Line Interface — интерфейс командной строки. Оболочка передаёт процессу массив строк argv; затем CLI разбирает их согласно правилам конкретной версии.'),
('API','Application Programming Interface — программный интерфейс. Kubernetes API принимает запросы над объектами; его успех отделён от последующего исполнения контроллеров.'),
('Chart','Чарт — пакет Helm с метаданными, параметрами, шаблонами и при необходимости зависимостями. Один пакет может породить несколько независимых релизов.'),
('Release','Релиз — именованное применение чарта с конфигурацией и историей ревизий в определённом пространстве имён и кластере.'),
('Revision','Ревизия — номер действия в истории релиза Helm. Откат создаёт следующую ревизию, а не уменьшает номер.'),
('Manifest','Манифест — текстовое описание объекта API. Сохранённый манифест Helm и текущее состояние объекта Kubernetes могут различаться.'),
('Rendering','Рендеринг — исполнение шаблонов с данными и получение текста. Его успех не доказывает принятие API или работоспособность приложения.'),
('Admission','Этап обработки запроса Kubernetes после установления личности и проверки полномочий. Admission controllers могут изменить допустимые части объекта или отклонить действие по политике; этот этап отделён от аутентификации, RBAC и последующей работы контроллеров workloads.'),
('Reconciliation','Согласование состояния — повторная работа контроллера для приближения наблюдаемого состояния к желаемому. Helm не заменяет контроллер Deployment.'),
('Namespace','Пространство имён Kubernetes ограничивает имена и область ряда объектов/прав. Само по себе не является полной изоляцией безопасности.'),
('Kubeconfig','Файл описания кластеров, личностей и контекстов доступа. Может запускать доверенный credential plugin; обращаться с ним следует как с полномочиями.'),
('Context','Контекст kubeconfig связывает кластер, личность и пространство имён по умолчанию. В Go templates context означает переданный текущий объект данных.'),
('Dot','Точка в Go template — текущий объект вычисления. With и range меняют его, if сохраняет.'),
('Root','Корень шаблона, первоначально связанный с $. Внутри include корнем становится явно переданный аргумент, который не обязан быть целым объектом Helm.'),
('Values','Дерево параметров чарта после загрузки пользовательских входов и объединения со значениями по умолчанию. Не является текстом исходного YAML.'),
('Coalescing','Объединение значений Helm с настройками чарта и дочерних пакетов. Отображения объединяются рекурсивно, скаляры и списки заменяются; null имеет смысл удаления ключа.'),
('Map','Отображение ключей в значения. Значение по ключу и наличие самого ключа — разные свойства; для второго используют hasKey.'),
('List','Упорядоченный список. Новый список values заменяет прежний целиком, не объединяется по Kubernetes name.'),
('Scalar','Скаляр — одно простое значение: строка, число, логическое значение или null. Похожее написание строкового и числового скаляра не делает типы равными.'),
('YAML','Текстовый формат отображений, списков и скаляров. Парсер получает структуру; YAML сам не исполняет Go template или shell.'),
('JSON','Текстовый формат структурированных данных с явно различаемыми строками, числами, логическими значениями, массивами, объектами и null.'),
('JSON Schema','Схема ограничений структуры и типов JSON-совместимых данных. В Helm проверяет итоговые values, но не доступную ёмкость узлов или существование образа.'),
('Empty','Правило пустоты шаблонных функций: nil, false, ноль и пустые строки/коллекции могут считаться пустыми. Default способен заменить законный false.'),
('Nil','Отсутствующее значение соответствующего типа Go. Доступ по цепочке через nil-родителя способен завершить исполнение шаблона до default.'),
('Default','Значение по умолчанию; одноимённая функция выбирает запасной вариант при пустоте входа. Для логических значений безопаснее явные defaults в values и схема типов.'),
('Required','Функция шаблона, отказывающая при пустом значении с сообщением. Не равна required JSON Schema, которое проверяет наличие свойства.'),
('Fail','Явное завершение исполнения шаблона ошибкой контракта, например при несовместимых режимах credentials.create и existingSecret.'),
('Pipeline','Конвейер выражений Go template. Результат слева передаётся последним аргументом следующей функции, а не по Unix pipe в другой процесс.'),
('Scope','Область видимости переменной и текущего контекста. Переменная из тела range не становится автоматически доступной после end.'),
('Define','Объявление именованного шаблона. Имена общие в загруженном дереве чартов, поэтому нужен устойчивый префикс.'),
('Include','Функция Helm, возвращающая результат именованного шаблона как строку. Даже напечатанное false становится непустой строкой для if.'),
('Template action','Вызов именованного шаблона, пишущий прямо в выходной поток. Отличается от include, результат которого можно передать функции.'),
('Sprig','Библиотека вспомогательных функций шаблонов, значительная часть которой доступна в Helm. Не превращает template в произвольную Go-программу.'),
('Dict','Создаваемое функцией dict отображение. Set и unset меняют его; при общей вложенной структуре нужна осознанная глубокая копия.'),
('Deep copy','Глубокое копирование структуры, разрывающее совместное использование вложенных отображений перед мутацией.'),
('ToYaml','Сериализация значения в строку YAML. После неё pipeline передаёт текст, а не исходное отображение.'),
('Nindent','Добавление перевода строки и заданного отступа к каждой строке текста. Число пробелов определяется местом итогового YAML.'),
('Whitespace trim','Удаление пробельных байтов около action через {{- и -}}. Может склеить две YAML-строки и изменить смысл результата.'),
('LF','Line feed — байт перевода строки 0x0A. Конечный LF из set-file является частью значения, пока его явно не преобразовали.'),
('Tpl','Исполнение строки как шаблона с переданным контекстом. Расширяет возможности автора values и ухудшает предсказуемость, если вход недоверенный.'),
('Lookup','Функция чтения Kubernetes API при разрешённом взаимодействии с сервером. Результат зависит от состояния и полномочий; forbidden отличается от отсутствующего объекта.'),
('Capabilities','Предоставляемая Helm модель версии Kubernetes и известных API. Локальные флаги моделируют её, но не устанавливают CRD или контроллер.'),
('Post-renderer','Постобработчик готовых манифестов. В Helm 4 подключается как плагин и должен проверяться вместе с окончательным результатом.'),
('SemVer','Semantic Versioning — соглашение major.minor.patch с дополнительными частями. Версия пакета и приложения имеют независимые контракты.'),
('AppVersion','Информативная строка версии приложения в Chart.yaml. Не меняет image tag в шаблоне автоматически.'),
('Subchart','Дочерний чарт с собственными параметрами и схемой, включаемый в общий релиз. Не получает произвольные параметры родителя.'),
('Library chart','Пакет типа library с общими вспомогательными шаблонами без самостоятельных Kubernetes-манифестов.'),
('Alias','Другое имя включённой зависимости, позволяющее иметь отдельное поддерево values для нескольких включений одного чарта.'),
('Global values','Явно выделенное поддерево global, доступное нескольким чартам по соглашению. Не является глобальной переменной ОС или настройкой всего кластера.'),
('Import-values','Перенос экспортированных или явно выбранных значений дочернего чарта в путь родителя до рендеринга. Не читает данные работающего приложения.'),
('Chart.lock','Файл выбранного набора зависимостей и связанного дайджеста. Не является подписью каждого архива зависимости.'),
('OCI','Open Container Initiative — семейство форматов/протоколов артефактов. Helm chart в OCI registry отличается от запускаемого контейнерного образа.'),
('Tag','Тег — именованный указатель в реестре. Если политика допускает перезапись, одно имя может позднее обозначать другие байты.'),
('Digest','Дайджест — идентификатор содержимого на основе хеша. Дайджест чарта и дайджест образа относятся к разным манифестам.'),
('SHA-256','Криптографический хеш байтов в 256-битное значение. Проверка с доверенным ожиданием устанавливает целостность, но не сама по себе полномочия издателя.'),
('Provenance','Сведения и проверяемая связь происхождения артефакта. Классическая подпись .prov связывает метаданные чарта и хеш архива с ключом OpenPGP.'),
('Fingerprint','Отпечаток криптографического ключа. Для проверки подписи его доверенное получение отделено от скачивания произвольного ключа рядом с архивом.'),
('OpenPGP','Формат криптографических ключей/подписей, используемый классической Helm provenance. Наличие подписи не доказывает безопасные privileges шаблонов.'),
('TLS','Transport Layer Security — защита канала и проверка идентичности сервера согласно доверенным сертификатам. Отключение проверки не исправляет неизвестную причину отказа.'),
('Dry-run','Пробный запуск без сохранения предусмотренных изменений. Точная граница зависит от команды и версии; Helm server mode не следует без проверки приравнивать к admission всех объектов.'),
('SSA','Server-Side Apply — серверное применение с учётом владельцев полей. Конфликт управляющих полями отличается от проверки принадлежности объекта релизу Helm.'),
('ManagedFields','Метаданные Kubernetes о менеджерах и управляемых полях. Не являются журналом бизнес-операций или копией данных.'),
('Ownership Helm','Связь объекта с release name/namespace через согласованные labels и annotations. Не равна Kubernetes ownerReferences и не отменяет существующие данные.'),
('Hook','Обработчик события Helm, обычно Job или Pod с аннотацией helm.sh/hook. Его внешний эффект не отменяется удалением самого Job.'),
('Hook weight','Целочисленный вес порядка обработчиков: меньший выполняется раньше. Значимое требование порядка не оставляют случайной сортировке имён.'),
('Hook delete policy','Правило удаления ресурса обработчика до повторного создания, после успеха или после ошибки. Не является откатом его внешних действий.'),
('Readiness','Готовность экземпляра принимать трафик. Ошибка проверки исключает его из готовых конечных точек, но не обязательно перезапускает контейнер.'),
('Liveness','Проверка жизнеспособности контейнера. Её отказ может вызвать перезапуск и поэтому отличается от временной неготовности внешней БД.'),
('Probe','Проба Kubernetes — периодическая проверка контейнера. Path, порт, thresholds и смысл ответа должны соответствовать приложению.'),
('Pod','Совместно планируемая единица контейнеров Kubernetes с общей сетью и рядом общих ресурсов. Не равна одному постоянному процессу.'),
('Deployment','Контроллер желаемого набора Pod через ReplicaSet и обновления их шаблона. Не является самим приложением или резервной копией.'),
('ReplicaSet','Контроллер числа Pod, подходящих по селектору. При обновлении Deployment новые и старые ReplicaSets могут сосуществовать.'),
('Service','Стабильная сетевая точка Kubernetes, выбирающая готовые Pod по селектору и задающая порты. ContainerPort сам не запускает слушающий процесс.'),
('EndpointSlice','API-объект набора конечных точек Service. Помогает отличить отсутствие готовых backend от ошибки самого HTTP-обработчика.'),
('ConfigMap','Kubernetes-объект строковой/двоичной конфигурации. EnvFrom копирует данные при создании контейнера; старый процесс не перечитывает окружение от изменения объекта.'),
('Secret','Объект конфиденциальных параметров Kubernetes. Base64 — кодирование; реальные гарантии требуют RBAC, защиты хранения и обращения с выводом.'),
('RBAC','Role-Based Access Control — управление разрешениями через роли и привязки личностей. Для Helm нужны также полномочия хранения metadata и наблюдения готовности.'),
('ServiceAccount','Личность приложения внутри Kubernetes. Её токен и kubeconfig клиента Helm относятся к разным доверительным границам.'),
('Requests','Запрашиваемые ресурсы для планирования и ряда политик Kubernetes. Не равны фактическому расходу CPU/памяти.'),
('Limits','Ограничения использования ресурсов. Память может привести к OOMKill, CPU quota — к ограничению времени исполнения.'),
('Millicpu','Тысячная доля CPU. 50m означает 0.05 CPU; это другая единица, чем миллисекунды задержки.'),
('Mi','Мебибайт — 2^20 байтов. Не равен десятичному мегабайту.'),
('RSS','Resident Set Size — объём резидентной памяти процесса. Не равен только Go-куче или всем данным chart на диске.'),
('OOMKill','Завершение контейнера при нарушении допустимого потребления памяти в соответствующей границе. Увеличение timeout Helm не устраняет причину.'),
('PVC','PersistentVolumeClaim — запрос постоянного хранилища. Связывание требует подходящего PV или подготовленного динамического provisioner. Монтирование выполняет механизм выбранного типа тома; статический local PV нашего упражнения не требует установки CSI.'),
('PV','PersistentVolume — ресурс предоставленного постоянного тома. ReclaimPolicy определяет судьбу тома после освобождения claim, отдельно от Helm keep.'),
('RWO','ReadWriteOnce — режим доступа, обычно ограничивающий запись одним узлом. Не обещает ровно один Pod и не является механизмом репликации БД.'),
('CSI','Container Storage Interface — интерфейс драйверов контейнерного хранилища. Подключение, монтирование и поддержка снимков зависят от драйвера.'),
('CRD','CustomResourceDefinition — определение собственного Kubernetes API. Его удаление может затронуть все экземпляры ресурса нескольких релизов.'),
('Rollback','Откат желаемых manifests выбранной ревизии через новое действие Helm. Не возвращает автоматически данные PVC, схему БД или внешние эффекты.'),
('Idempotence','Идемпотентность — свойство повторного действия приводить к требуемому состоянию без лишнего эффекта. У произвольного migration Job её надо доказывать.'),
('Drift','Дрейф — отличие фактического состояния от описанного. Get manifest Helm показывает сохранённое намерение, не обязательно текущий объект API.'),
('Graceful shutdown','Штатное завершение: прекратить новую работу, отметить неготовность и дождаться активных запросов в заданном бюджете до выхода процесса.'),
('RPO','Recovery Point Objective — допустимая потеря последних данных по времени. Определяется резервированием/согласованностью, а не наличием истории Helm.'),
('RTO','Recovery Time Objective — допустимое время восстановления услуги, включая инструменты, права, образы, данные и прикладную проверку.'),
('p99','Оценка 99-го процентиля измерений. Серия из десяти запусков недостаточна для устойчивого вывода о редком хвосте задержки.'),
]

def flag(name, action, when, example, result):
    return dict(flag=name,action=action,when=when,example=example,result=result)

def command(name,purpose,syntax,chapter,flags=(),situations=(),page=None):
    url='https://helm.sh/docs/helm/'+(page or name.replace(' ','_'))+'/'
    card = dict(name=name,aliases=[],purpose=purpose,syntax=syntax,chapter=chapter,volume='helm',source=url,
      sources=[dict(title='Официальная справка Helm 4.3.1; проверено 01.11.2026',url=url)],flags=list(flags),situations=list(situations))
    if name == 'helm':
        card['persistentOptions'] = True
    cluster_commands = (
        'helm install', 'helm upgrade', 'helm rollback', 'helm uninstall',
        'helm status', 'helm history', 'helm list', 'helm get values',
        'helm get manifest', 'helm get hooks', 'helm test',
    )
    for item in card['flags']:
        lines = []
        for line in item['example'].splitlines():
            if any(line == cmd or line.startswith(cmd + ' ') for cmd in cluster_commands):
                if '--kubeconfig' not in line:
                    line += ' --kubeconfig "$LAB_KUBECONFIG"'
                if '--kube-context' not in line:
                    line += ' --kube-context "$LAB_CONTEXT"'
                if '--namespace' not in line and ' -n ' not in line:
                    line += ' --namespace helm-lab'
            elif line.startswith('helm template ') and '--namespace' not in line:
                line += ' --namespace helm-lab'
            lines.append(line)
        item['example'] = '\n'.join(lines)
    return card

COMMANDS=[
command('helm','Клиент Helm; полномочия и каталог задаются для конкретного вызова. В основной линии только версия4.3.1.','helm [ГЛОБАЛЬНЫЕ_ФЛАГИ] КОМАНДА','01-helm-install',[
 flag('--kubeconfig <файл>','Выбрать отдельный файл доступа.','Каждое кластерное действие личного стенда.','helm status ledger --kubeconfig "$LAB_KUBECONFIG" --kube-context "$LAB_CONTEXT" --namespace helm-lab','Не меняет общий current-context; файл может запускать credential plugin.'),
 flag('--kube-context <имя>','Явно выбрать контекст из указанного kubeconfig.','Не полагаться на значение по умолчанию.','helm list --kubeconfig "$LAB_KUBECONFIG" --kube-context "$LAB_CONTEXT" --namespace helm-lab','Endpoint и личность определены явно; ошибочный контекст остаётся опасным.'),
 flag('--namespace <имя> / -n <имя>','Выбрать пространство имён запроса и истории релиза.','Одинаковый release может существовать в разных namespaces.','helm history ledger --namespace helm-lab --kubeconfig "$LAB_KUBECONFIG" --kube-context "$LAB_CONTEXT"','Это не ограничивает chart от cluster-scoped ресурсов.'),
 flag('--debug','Добавить диагностический контекст.','Короткое расследование с защищённым выводом.','helm template ledger ./chart --kube-version 1.36.6 --debug','Вывод может содержать секретные значения и пути; это не дополнительная проверка здоровья.'),
 flag('--qps <число>','Ограничить частоту клиентских запросов к API.','Только после измерения задержки и throttling.','helm status ledger --qps 5 --burst-limit 10 --namespace helm-lab','Не увеличивает серверную ёмкость и не ускоряет scheduling автоматически.')]),
command('helm version','Показать версию фактически запущенного executable.','helm version [ФЛАГИ]','01-helm-install',[
 flag('--short','Сократить представление версии.','Приёмка проверенного binary.','helm version --short','Ожидаемая ветка4.3.1; это не проверка доступности Kubernetes.')]),
command('helm env','Показать пути и переменные среды клиента без установки кластера.','helm env','01-helm-install'),
command('helm plugin list','Показать установленные плагины выбранной пользовательской среды.','helm plugin list','18-helm-migration'),
command('helm lint','Проверить структуру, schema и исполнимость chart, не устанавливая workloads.','helm lint ПУТЬ [ФЛАГИ]','03-helm-chart',[
 flag('--strict','Считать предупреждения ошибками.','Стабильная локальная приёмка.','helm lint ./chart --strict --kube-version 1.36.6','Успех lint не доказывает admission или запуск Pod.'),
 flag('-f, --values <файл>','Добавить параметры для проверки.','Проверить именно окружение выпуска.','helm lint ./chart --strict -f fixtures/wrong-replicas.yaml','Отрицательный пример отвергает строковую replicaCount.'),
 flag('--kube-version <версия>','Задать моделируемую версию Kubernetes.','Проверка kubeVersion chart и ветвей шаблона.','helm lint ./chart --strict --kube-version 1.36.6','Не обращается к выбранному кластеру для доказательства API.')]),
command('helm template','Локально получить манифесты; в клиентском режиме не доказывает API и readiness.','helm template ИМЯ CHART [ФЛАГИ]','04-helm-values',[
 flag('-f, --values <файл>','Объединять файлы слева направо; последний конфликтующий ключ важнее.','Сравнение окружений.','helm template ledger ./chart --kube-version 1.36.6 -f fixtures/prod.yaml -f fixtures/last.yaml','Реплик1; при обратном порядке3; memory default сохраняется.'),
 flag('--set <ключ=значение>','Разобрать strvals с выводом поддерживаемых типов.','Целочисленные replicas и bool.','helm template ledger ./chart --kube-version 1.36.6 --set replicaCount=3','Число3 проходит schema, в отличие от --set-string.'),
 flag('--set-string <ключ=строка>','Принудительно передать строку.','Теги/идентификаторы, где число теряет смысл.','helm template ledger ./chart --kube-version 1.36.6 --set-string replicaCount=3','Намеренный schema failure: replicaCount должен быть integer.'),
 flag('--set-json <JSON>','Разобрать объекты/списки/скаляры JSON.','Список объектов env без индексной записи.','helm template ledger ./chart --kube-version 1.36.6 --set-json \'extraEnv=[{"name":"TRACE","value":"true"}]\'','Env.value остаётся string; JSON true без кавычек отвергается.'),
 flag('--set-file <ключ=файл>','Прочитать точные bytes файла как строку.','Dummy token или многострочная конфигурация.','helm template ledger ./chart --kube-version 1.36.6 --set credentials.create=true --set-file credentials.token=fixtures/token.txt','Сохранён конечный LF; выход содержит Secret и требует защиты.'),
 flag('--set-literal <ключ=строка>','Принять буквальную правую часть по правилам выбранного CLI.','Когда обычный RHS strvals нежелателен.','helm template ledger ./chart --kube-version 1.36.6 --set-literal config.message=a,b','MESSAGE содержит запятую; для большого интерфейса предпочтителен файл.'),
 flag('--kube-version <версия>','Задать модель KubeVersion.','Локальный render стабильного API.','helm template ledger ./chart --kube-version 1.36.6','CRD/контроллеры этим не устанавливаются.'),
 flag('--api-versions <API>','Добавить моделируемую возможность API.','Проверка условного ветвления шаблона.','helm template ledger ./chart --kube-version 1.36.6 --api-versions example.invalid/v1/Widget','Не доказывает наличие API у сервера.'),
 flag('--show-only <путь>','Печатать выбранный manifest после исполнения chart.','Сократить исследуемый output.','helm template ledger ./chart --kube-version 1.36.6 --show-only templates/configmap.yaml','Другой сломанный шаблон всё ещё может сорвать общий render.'),
 flag('--is-upgrade','Задать контекст IsUpgrade для локальной проверки ветвей.','Сравнить условные шаблоны без revision кластера.','helm template ledger ./chart --kube-version 1.36.6 --is-upgrade','Не читает реальную историю release и не моделирует весь upgrade.'),
 flag('--include-crds','Включить CRD-документы в локальный output.','Инвентаризация пакета с CRD.','helm template ledger ./chart --kube-version 1.36.6 --include-crds','В нашем chart CRD нет; вывод не равен их успешной установке.')]),
command('helm install','Создать новый именованный релиз из chart и выбранных values.','helm install ИМЯ CHART [ФЛАГИ]','11-helm-first-release',[
 flag('--dry-run <client|server>','Подготовить действие без штатного сохранения; server требует API.','Разделить локальный render и discovery/lookup.','helm install ledger ./chart --namespace helm-lab --dry-run=client --hide-secret','Не устанавливает; точная граница server описана по install.go, admission не обещан.'),
 flag('--hide-secret','Скрыть Secret-документы при dry-run.','Защитить диагностический output частично.','helm install ledger ./chart --namespace helm-lab --dry-run=client --hide-secret','Чувствительные строки в NOTES/ConfigMap/ошибках всё ещё возможны.'),
 flag('--wait <strategy>','Выбрать watcher, hookOnly или legacy.','Нужна наблюдаемая готовность workloads.','helm install ledger ./chart --namespace helm-lab --wait=watcher --timeout 180s','С --wait без значения watcher; без флага hookOnly; HTTP business contract отдельно.'),
 flag('--timeout <duration>','Ограничить конкретные ожидания Kubernetes.','Диагностированный бюджет rollout/hooks.','helm install ledger ./chart --namespace helm-lab --wait=watcher --timeout 180s','Это не общий deadline всех фаз и не лечение неверного readiness path.'),
 flag('--rollback-on-failure','Попытаться удалить неуспешную установку.','Осознанная компенсирующая политика.','helm install ledger ./chart --namespace helm-lab --rollback-on-failure --timeout 180s','При default hookOnly включает watcher; внешние side effects могут сохраниться.'),
 flag('--server-side <bool>','Выбрать серверное применение для нового release.','Явно контролировать SSA.','helm install ledger ./chart --namespace helm-lab --server-side=true','В4.3.1 default true; нужны полномочия apply/наблюдения.'),
 flag('--create-namespace','Создать namespace при отсутствии.','Только если владелец стенда выдал соответствующее право.','helm install ledger ./chart --namespace helm-lab --create-namespace','Cluster-scoped create namespaces; не создаёт безопасную роль автоматически.'),
 flag('--verify','Требовать корректную классическую provenance.','Доверенно полученный подписанный chart.','helm install ledger ./dist/ledger-api-0.1.0.tgz --verify --keyring ./trusted-public.gpg --namespace helm-lab','Нужен .prov и доверенный key; содержимое chart всё равно проходит review.')]),
command('helm upgrade','Создать следующую ревизию существующего release и применить целевые объекты.','helm upgrade ИМЯ CHART [ФЛАГИ]','12-helm-upgrade',[
 flag('--reset-values','Использовать defaults нового chart и новые явно переданные параметры.','Полный versioned environment file.','helm upgrade ledger ./chart --reset-values -f environment.yaml --namespace helm-lab','Старый user config игнорируется; приоритет над reuse.'),
 flag('--reuse-values','Наследовать старое coalesced дерево и наложить новые параметры.','Явное сохранение старой настройки с пониманием потери новых defaults.','helm upgrade ledger ./chart --reuse-values --set replicaCount=2 --namespace helm-lab','Новые defaults chart могут не войти; reset-values имеет приоритет.'),
 flag('--reset-then-reuse-values','Новый chart default → прежний user config → новые overrides.','Нужны новые defaults и старые пользовательские выборы.','helm upgrade ledger ./chart --reset-then-reuse-values --set replicaCount=2 --namespace helm-lab','Игнорируется при reset-values или reuse-values.'),
 flag('--install','Установить release, если его нет.','Автоматизация с явным разрешением первичной установки.','helm upgrade ledger ./chart --install --reset-values -f environment.yaml --namespace helm-lab','Первый install и последующий upgrade имеют разные lifecycle hooks/SSA defaults.'),
 flag('--rollback-on-failure','Попытаться вернуться к предыдущему успешному релизу при ошибке.','Обратимые изменения workloads с отдельным планом данных.','helm upgrade ledger ./chart --reset-values -f environment.yaml --namespace helm-lab --rollback-on-failure --timeout 180s','Компенсация может тоже отказать; БД автоматически не возвращается.'),
 flag('--cleanup-on-fail','Разрешить удалить новые ресурсы неудачного upgrade.','Понятна судьба созданных объектов.','helm upgrade ledger ./chart --reset-values -f environment.yaml --namespace helm-lab --cleanup-on-fail','Не отменяет внешние эффекты hooks и не стирает все изменения.'),
 flag('--history-max <число>','Ограничить число сохраняемых ревизий.','Контроль metadata size и срока хранения секретных values.','helm upgrade ledger ./chart --namespace helm-lab --reset-values -f environment.yaml --history-max 20','0 означает без лимита; отличается от history --max.'),
 flag('--server-side <true|false|auto>','Выбрать метод apply либо унаследовать прежний.','Миграция Helm3 release или осознанный SSA.','helm upgrade ledger ./chart --namespace helm-lab --server-side=auto --reset-values -f environment.yaml','Default auto сохраняет предыдущий метод, а не безусловно включает SSA.'),
 flag('--force-conflicts','Разрешить SSA отнять конфликтующие поля у другого manager.','Только после review managedFields и владельца.','helm upgrade ledger ./chart --namespace helm-lab --server-side=true --force-conflicts --dry-run=server','Это изменение ownership, не обычная починка любого отказа.'),
 flag('--force-replace','Применять замену ресурса вместо обычного обновления.','Осознанная операция с планом outage/data.','helm upgrade ledger ./chart --namespace helm-lab --force-replace --dry-run=server','Может изменить UID/доступность; dry-run не доказывает безопасную миграцию.'),
 flag('--take-ownership','Обойти Helm-проверку принадлежности существующего ресурса.','Только согласованный перенос конкретного объекта.','helm upgrade ledger ./chart --namespace helm-lab --take-ownership --dry-run=server','Будущий uninstall может удалить принятый ресурс; это не SSA force-conflicts.'),
 flag('--wait-for-jobs','Добавить ожидание обычных Jobs при включённом wait.','Chart действительно содержит конечные Jobs.','helm upgrade ledger ./chart --namespace helm-lab --wait=watcher --wait-for-jobs --timeout 180s','Hook Job имеет собственную фазу; приложение HTTP проверяется отдельно.')]),
command('helm rollback','Применить manifest выбранной ревизии как новую ревизию.','helm rollback ИМЯ [РЕВИЗИЯ] [ФЛАГИ]','14-helm-recovery',[
 flag('--wait <strategy>','Дождаться состояния возвращённых ресурсов.','После осознанного выбора target history.','helm rollback ledger 1 --namespace helm-lab --wait=watcher --timeout 180s','Новый номер ревизии; данные не возвращаются автоматически.'),
 flag('--no-hooks','Пропустить rollback hooks.','Только если внешний протокол допускает пропуск.','helm rollback ledger 1 --namespace helm-lab --no-hooks --dry-run=server','Меняет семантику восстановления, не ускоряет тот же сценарий.')]),
command('helm uninstall','Удалить управляемые обычные ресурсы release с указанной политикой истории.','helm uninstall ИМЯ [ФЛАГИ]','14-helm-recovery',[
 flag('--keep-history','Сохранить историю с состоянием uninstalled.','Финальная очистка с аудитом.','helm uninstall ledger --namespace helm-lab --keep-history --wait=watcher','Приложение удаляется; namespace, CRD, keep PVC и часть hooks могут остаться.'),
 flag('--cascade <background|foreground|orphan>','Выбрать распространение удаления Kubernetes dependents.','Согласовать ownerReferences/finalizers.','helm uninstall ledger --namespace helm-lab --cascade foreground --wait=watcher --timeout 180s','Foreground с wait позволяет наблюдать полное удаление зависимых ресурсов; внешние данные отдельно.'),
 flag('--ignore-not-found','Считать отсутствие release успехом.','Явная повторяемая финальная очистка своего стенда.','helm uninstall ledger --namespace helm-lab --ignore-not-found --dry-run','Может скрыть ошибку имени/context, поэтому нужны явные входы.')]),
command('helm status','Показать сведения текущей или указанной ревизии release. Не заменяет HTTP-проверку.','helm status ИМЯ [ФЛАГИ]','16-helm-diagnostics',[
 flag('--revision <число>','Читать указанную историческую ревизию.','Исследовать предыдущий успех/ошибку.','helm status ledger --namespace helm-lab --revision 1','Только чтение; состояние кластера назад не переносится.')]),
command('helm history','Показать историю действий release.','helm history ИМЯ [ФЛАГИ]','12-helm-upgrade',[
 flag('--max <число>','Ограничить число выводимых записей.','Краткая диагностика.','helm history ledger --namespace helm-lab --max 20','Не меняет history-max сохраняемых ревизий.')]),
command('helm list','Показать releases в выбранной области доступа.','helm list [ФЛАГИ]','16-helm-diagnostics',[
 flag('--failed / --pending / --uninstalled','Ограничить вывод состояниями: failed — неуспешный выпуск, pending — незавершённое действие, uninstalled — удалённый релиз с сохранённой историей.','Найти ошибки и незавершённые действия; несколько фильтров объединяются как ИЛИ.','helm list --namespace helm-lab --failed --pending --uninstalled --output json','В 4.3.1 без фильтров выбраны все состояния; явные фильтры сужают набор. Это актуальные записи релизов, а не вся история ревизий.'),
 flag('--output <table|json|yaml>','Выбрать формат данных.','Сохранить структурированный журнал.','helm list --namespace helm-lab --output json','Формат не меняет выбор состояний. Helm status и готовность рабочих нагрузок проверяют отдельно.')]),
command('helm get values','Получить user config либо вычисленные values из истории; вывод может раскрывать Secret.','helm get values ИМЯ [ФЛАГИ]','12-helm-upgrade',[
 flag('--all','Добавить defaults и вычисленные значения.','Сравнить с user config.','helm get values ledger --namespace helm-lab --all','Без --all видны переданные overrides; оба вывода защищают.'),
 flag('--revision <число>','Выбрать историческую запись.','Восстановить входы конкретного действия.','helm get values ledger --namespace helm-lab --revision 1','Не равен чтению live ConfigMap/Secret.')]),
command('helm get manifest','Прочитать сохранённые manifests релиза, включая возможные Secret bytes.','helm get manifest ИМЯ [ФЛАГИ]','16-helm-diagnostics',[
 flag('--revision <число>','Читать manifest конкретной ревизии.','Сопоставить цель rollback.','helm get manifest ledger --namespace helm-lab --revision 1','Не является полным live snapshot объектов API.')]),
command('helm get hooks','Прочитать сохранённые шаблоны обработчиков релиза.','helm get hooks ИМЯ','13-helm-hooks'),
command('helm test','Запустить chart test hooks на настоящем развернутом релизе.','helm test ИМЯ [ФЛАГИ]','13-helm-hooks',[
 flag('--logs','Получить логи тестовых Pod до предусмотренной очистки.','Диагностировать HTTP/DNS тест.','helm test ledger --namespace helm-lab --logs --timeout 60s','Это реальные Pod/API операции; лог может раскрывать данные.'),
 flag('--filter <name=...>','Выбрать тесты по поддерживаемому атрибуту.','Повторить конкретный тест.','helm test ledger --namespace helm-lab --filter name=ledger-ledger-api-test','Имя должно совпасть с фактическим hook; это не локальный unit test.')]),
command('helm dependency update','Разрешить версии dependencies и обновить charts/ и lock.','helm dependency update CHART','09-helm-dependencies'),
command('helm dependency build','Восстановить dependencies из Chart.lock; без lock может заново разрешить набор.','helm dependency build CHART','09-helm-dependencies'),
command('helm dependency list','Показать объявленные dependencies и их состояние.','helm dependency list CHART','09-helm-dependencies'),
command('helm package','Упаковать chart; не собирает Go и контейнерные образы.','helm package CHART [ФЛАГИ]','10-helm-distribution',[
 flag('--destination <каталог>','Записать tgz вне исходного chart.','Избежать повторного вложения artifacts.','helm package ./chart --destination ./dist','Имя пакета зависит от Chart.yaml name/version.'),
 flag('--version <SemVer>','Задать chart version пакета.','Осознанная новая версия интерфейса.','helm package ./chart --version 0.2.0 --destination ./dist','Не изменяет автоматически image tag/application bytes.'),
 flag('--sign','Создать classic .prov с подготовленным ключом.','Свой процесс доверенной публикации.','helm package ./chart --destination ./signed --sign --key "HANDBOOK SIGNER" --keyring ./private-signing-keyring.gpg','Рецепт требует своих ключей; в редакции подпись chart не выполнялась.')]),
command('helm verify','Проверить classic provenance архива по доверенному public keyring.','helm verify АРХИВ --keyring ФАЙЛ','10-helm-distribution',[
 flag('--keyring <файл>','Выбрать доверенное кольцо открытых ключей.','Проверка конкретного издателя.','helm verify ./dist/ledger-api-0.1.0.tgz --keyring ./trusted-public.gpg','Не анализирует опасные полномочия и hooks пакета.')]),
command('helm pull','Скачать chart archive для проверки или распаковки.','helm pull CHART [ФЛАГИ]','10-helm-distribution',[
 flag('--version <версия>','Выбрать конкретный chart version.','Воспроизводимая доставка.','helm pull handbook/ledger-api --version 0.1.0 --destination ./dist','Версия пакета отличается от image digest.'),
 flag('--verify','Требовать .prov и корректную подпись.','Classic provenance с доверенными ключами.','helm pull handbook/ledger-api --version 0.1.0 --verify --keyring ./trusted-public.gpg','Просто наличие файла .prov недостаточно.'),
 flag('--untar','Распаковать пакет.','Исследование исходников в отдельном каталоге.','helm pull handbook/ledger-api --version 0.1.0 --untar --untardir ./inspection','Распаковка не добавляет доверия или проверки workloads.')]),
command('helm push','Публиковать уже созданный chart tgz в свой OCI registry.','helm push АРХИВ oci://РЕЕСТР/ПУТЬ','10-helm-distribution'),
command('helm registry login','Сохранить авторизацию Helm для своего OCI registry; в4.x аргумент domain[:port].','helm registry login РЕЕСТР [ФЛАГИ]','10-helm-distribution',[
 flag('--password-stdin','Прочитать пароль из stdin вместо argv.','Подготовленная переменная секрета своего registry.','printf \'%s\' "$REGISTRY_PASSWORD" | helm registry login registry.example.invalid --username "$REGISTRY_USER" --password-stdin','Credential file защищают; это не imagePullSecret Kubernetes.')]),
command('helm repo add','Зарегистрировать имя HTTP(S) chart repository в личной среде клиента.','helm repo add ИМЯ URL','10-helm-distribution'),
command('helm repo update','Скачать свежий индекс указанных зарегистрированных repositories.','helm repo update [ИМЯ]','10-helm-distribution'),
command('helm repo index','Создать index.yaml для собственной staging-папки chart repository.','helm repo index КАТАЛОГ [ФЛАГИ]','10-helm-distribution',[
 flag('--url <URL>','Задать базовый адрес публикуемых archives.','Подготовка своего HTTP chart repository.','helm repo index ./dist --url https://charts.example.invalid','Само индексирование не публикует сервер и не подписывает archives.')]),
command('helm search repo','Искать по сохранённым локально индексам repositories.','helm search repo ЗАПРОС [ФЛАГИ]','10-helm-distribution',[
 flag('--versions','Показать доступные версии из индекса.','Перед фиксацией chart version.','helm search repo handbook/ledger-api --versions','Устаревший index может отличаться от текущего сервера.')]),
command('helm show chart','Прочитать метаданные пакета без создания release.','helm show chart CHART','03-helm-chart'),
command('helm show values','Прочитать исходные defaults пакета, не effective config release.','helm show values CHART','03-helm-chart'),
]
