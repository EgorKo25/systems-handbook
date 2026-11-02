"""Original Artifactory terms and selected verified command grammar. No execution."""
GLOSSARY = [
('Artifactory','Сервер управления артефактами JFrog; связывает имена пакетов и файлов с содержимым, метаданными и правами. Не компилирует автоматически вашу программу от загрузки файла.'),
('Артефакт Artifactory','Сохраняемый именованный объект: исходный архив, исполняемый файл, манифест или другие байты. Его логический путь и физическое размещение различаются.'),
('Пакет','Единица формата экосистемы с координатами. Один Go module или OCI image может включать несколько сохраняемых артефактов.'),
('Repository key','Уникальное имя административной области Artifactory. Не Git URL и не имя файла внутри неё.'),
('Local repository','Репозиторий принятых публикаций этого экземпляра. Запись требует deploy и соответствующей политики перезаписи.'),
('Remote repository','Описание внешнего источника и кэш полученных по запросу объектов. Не полное зеркало и не цель ручного upload.'),
('Virtual repository','Логическая точка разрешения, объединяющая источники по правилам формата. Не создаёт независимую копию каждого объекта и не имеет собственного permission target.'),
('Upstream','Внешний источник, к которому обращается remote. Его credentials и CA отличаются от входящих материалов клиента.'),
('Remote cache','Содержимое, уже полученное remote; прогрев одного клиента не доказывает наличие полного набора на сервере.'),
('Negative cache','Сохранённый отрицательный ответ, например404, препятствующий повторному обращению до истечения заданного окна.'),
('Metadata retrieval period','Период повторной проверки изменяемых метаданных upstream. Не срок жизни каждого неизменяемого бинарного файла.'),
('Missed retrieval period','Срок сохранения404для отсутствующего артефакта. Новый объект upstream может появиться раньше его окончания.'),
('Assumed offline','Временное состояние remote после проблемы соединения. Отличается от явно включённого Offline и от автономности книги.'),
('Priority Resolution','Дополнительная настройка приоритета ограниченного формата. Не универсальная замена общей очередности local/cache/remote или проверке прав.'),
('Default deployment repository','Local-цель, выбранная для записи через virtual, если формат и конфигурация это поддерживают.'),
('Layout Artifactory','Правила логических путей и координат формата. Не буквальное расположение checksum-файлов на диске.'),
('Router JFrog','Служба направления прикладных запросов к компонентам платформы. Не IP-маршрутизатор VM.'),
('Frontend','Компонент интерфейса платформы; его готовность не доказывает чтение всех артефактов.'),
('Access JFrog','Служба пользователей, групп, разрешений и токенов. Проверяет отдельную от TLS модель личности и полномочий.'),
('JFROG_HOME','Корневой каталог поставки платформы. В нашем VM-рецепте /opt/jfrog, внутри artifactory/app и artifactory/var.'),
('App и var','Программная поставка и изменяемые данные/конфигурация соответственно. Замена app не откатывает миграции var/БД.'),
('System YAML','Конфигурация служб платформы в var/etc/system.yaml; содержит также чувствительные настройки и может получить зашифрованные представления секретов.'),
('Filestore','Хранилище бинарного содержимого, отдельное от отображения путей в SQL. Не восстанавливает логические имена без метаданных.'),
('Checksum storage','Адресация содержимого по контрольной сумме и отображение логических путей в БД. В документированном стандартном filestore используется SHA1 layout, SHA256 также сохраняется отдельно.'),
('Дедупликация','Повторные логические ссылки на одинаковые байты используют одно сохраняемое содержимое в пределах предусмотренного хранилища.'),
('Logical bytes','Сумма размеров по логическим ссылкам. Может многократно учитывать один физический blob.'),
('Physical bytes','Реальные байты выбранного физического уровня, с его накладными расходами, версиями и сжатием. Не обязаны совпадать со статистикой logical paths.'),
('Checksum deployment','Создание нового пути по уже доступному пользователю содержимому с тем же хешем без повторной передачи тела.404может означать необходимость обычного upload.'),
('SHA1','Историческая контрольная сумма, используемая в документированном layout Artifactory. Не самостоятельное доказательство доверенного происхождения.'),
('SHA256','Криптографический хеш конкретных байтов. Ожидаемое значение должно приходить по отдельно доверенному процессу.'),
('H1 Go','Каноническая сумма имён и содержимого файлов модуля. Не SHA256 упаковочных байтов ZIP.'),
('GoModSum','Отдельная сумма go.mod в формате Go; проверяет другой объект, чем общий модульный ZIP.'),
('Module path','Объявленная в go.mod идентичность модуля. Включает значимые регистр и major suffix при соответствующем версионировании.'),
('Uppercase escaping','Кодирование больших букв module path через ! и маленькую букву в proxy protocol; не заменяет слэши и не меняет исходный префикс ZIP.'),
('GOPROXY','Порядок источников Go proxy; запятая и вертикальная черта допускают разные условия перехода после ошибки.'),
('GOPRIVATE','Private prefix и умолчание для GONOPROXY/GONOSUMDB. Сам по себе способен направить модуль мимо внутреннего proxy.'),
('GONOPROXY','Определяет обход proxy для совпавшего модуля; none в нашем пути позволяет private module идти через Artifactory.'),
('GONOSUMDB','Ограниченное исключение обращения к публичной checksum database. Не создаёт независимое подтверждение первой полученной суммы.'),
('GOAUTH','Механизм получения credentials для предусмотренных HTTPS-запросов Go; netrc и off имеют различный наблюдаемый результат.'),
('GOMODCACHE','Кэш исходников и служебных объектов модулей. Новый кэш не стирает доверенный go.sum проекта.'),
('GOCACHE','Кэш результатов сборки Go. Его попадание не доказывает серверный cache hit.'),
('Netrc','Файл сопоставления адреса и credentials клиента. В принятом опыте закрыт mode0600 и выбран через NETRC только для процесса.'),
('JFrog CLI profile','Сохранённый адрес и секреты клиента под server ID. Наличие профиля не равно успешной сетевой приёмке.'),
('Resolver','Настройка источника разрешения зависимостей проекта JFrog CLI.'),
('Deployer','Настройка целевого репозитория публикации проекта JFrog CLI.'),
('Build-info','JSON-сведения о выполнении сборки, зависимостях и выходах. Сначала могут накапливаться локально; не являются подписью происхождения сами по себе.'),
('Build name/number','Область и идентификатор выполнения. Не равны версии программы, требуют защиты от смешения независимых jobs.'),
('Build partials','Локально накопленные части build-info до публикации. Их сохранность и конфиденциальность зависят от выбранного CLI temp directory.'),
('Promotion','Продвижение уже проверенных байтов к принятой области с записью статуса. Не повторная компиляция и не автоматическая транзакция всех объектов.'),
('Manifest выпуска','Собственный контракт набора version/toolchain/files, отличный от JFrog build-info и OCI manifest. Требует отдельно доверенной идентичности.'),
('Provenance','Утверждение о происхождении выполнения и входах. Требует доверия к процессу и, при принятом формате, проверки подписи.'),
('Permission target','Именованное назначение действий над физическими ресурсами/путями пользователям или группам.'),
('Deploy/Cache','Разрешение публикации в local либо получения в remote cache по соответствующему контексту; не универсальное право overwrite.'),
('Delete/Overwrite','Право удаления/замены по правилам формата. Отсутствие его у издателя помогает сохранять выпущенные версии неизменными.'),
('Annotate','Право изменения свойств/метаданных. Это влияние на сведения о выпуске, а не безвредное чтение.'),
('Scope токена','Заданная область действия вместе с моделью прав субъекта; не просто подпись JWT.'),
('Audience','Предусмотренные получатели токена. Адрес предъявления и круг доверия проверяются отдельно от subject.'),
('Reference token','Непрозрачное серверное представление материала доступа. Клиент не обязан уметь вывести username из его байтов.'),
('Revocable expiry threshold','Порог срока токена, определяющий возможность отзыва по механизму Access. Краткоживущий токен может доживать до expiry вместо мгновенного отзыва.'),
('Persistent expiry threshold','Порог сохранения токена в БД. Не то же самое, что срок его допустимого использования или порог отзыва.'),
('Project JFrog','Группа ресурсов и ролей платформы. Не автоматически Git-проект, папка module path или имя CI pipeline.'),
('Audit trail','Журнал выбранных значимых действий, нуждающийся в собственной защите, времени и сроке хранения; не полное доказательство происхождения бинарника.'),
('OCI artifact','Объект OCI с определённым типом и графом содержимого. Произвольный переданный Go binary не становится контейнерным образом.'),
('OCI layout','Локальный формат index.json/oci-layout/blobs. Не внутренний filestore Artifactory и не резерв его БД.'),
('Descriptor OCI','Связь типа содержимого, длины и digest. Проверяется относительно точных байтов описанного объекта.'),
('Platform manifest','Манифест конкретного варианта ОС/архитектуры; его digest отличается от индекса нескольких вариантов.'),
('Tag OCI','Изменяемая по политике именованная ссылка на манифест. Нельзя считать её безусловно неизменяемой координатой.'),
('Retention','Правила сохранения по времени/версии/свойствам и потребности возврата. Не автоматически удаление всего давно не скачанного.'),
('Trash Can','Отложенное хранение удаляемых объектов; влияет на восстановление и освобождение физических байтов.'),
('Garbage Collection Artifactory','Удаление неиспользуемых бинарных объектов по предусмотренным связям и правилам. Не равно немедленному delete logical path.'),
('AQL','Язык запросов к известным Artifactory метаданным. Не полный поиск по всему внешнему upstream.'),
('Master key','Ключ шифрования конфиденциального состояния платформы. Его потеря не исправляется генерацией нового ключа над прежними данными.'),
('Join key','Материал внутреннего доверия служб. Не заменяет master key и клиентский access token.'),
('Согласованный резерв','Полный принимаемый набор DB, bytes, конфигурации и ключей, который можно восстановить как одну историю.'),
('Fencing','Исключение прежней стороны из пути записи/связности при аварийном переключении, чтобы две истории не работали одновременно.'),
('RPO','Допускаемая потеря последних данных по времени/принятым записям; требует фактической оценки контрольной точки.'),
('RTO','Целевое время до возврата нужной функции с проверкой данных, а не только до старта процесса.'),
('HA Artifactory','Лицензированная топология нескольких узлов с принятым общим DB/filestore и балансировкой; не исторический резерв.'),
('Repository replication','Перенос выбранных объектов между экземплярами. Отставание/удаления/метаданные и права требуют отдельной проверки.'),
('RTFS','Artifactory Federation Service, отдельная служба нового механизма федерации репозиториев с собственными предпосылками.'),
('Access Federation','Отдельная синхронизация субъектов безопасности по соответствующему Enterprise+ договору, не побочный эффект передачи файлов.'),
('CLI startup measurement','Время старта клиентского процесса на данной машине. Не измерение пропускной способности сервера или стоимости PostgreSQL.'),
]

def flag(label,action,when,example,result):
    return dict(flag=label,action=action,when=when,example=example,result=result)

def card(name,purpose,syntax,chapter,flags=(),aliases=(),url=None):
    url=url or 'https://github.com/jfrog/jfrog-cli/tree/v2.129.0'
    return dict(name=name,aliases=list(aliases),purpose=purpose,syntax=syntax,chapter=chapter,volume='artifactory',source=url,
                sources=[dict(title='Первичный источник / выбранная версия',url=url)],flags=list(flags),situations=[])

def server(command):
    return flag('--server-id ID','Выбрать заранее сохранённый profile именно этой операции.','Работать с определённой личностью/экземпляром.',command+' --server-id=lab-publisher','Не глобальная настройка jf или rt; права остаются серверными.')

def buildflags(command):
    return [flag('--build-name ИМЯ','Связать локально накапливаемые сведения с областью выполнения.','Есть однозначный номер того же build.',command+' --build-name=receipt --build-number=1','Нужен парный номер; публикация JSON происходит отдельно.'),
            flag('--build-number НОМЕР','Задать идентичность выполнения в области имени.','Не смешать части разных запусков.',command+' --build-name=receipt --build-number=1','Не меняет автоматически версию программы или модуля.')]

COMMANDS=[
card('jf','Проверенный клиент JFrog; команда может обращаться к выбранной платформе.','jf [КОРНЕВЫЕ ОПЦИИ] КОМАНДА','artifactory-08-cli',[
 flag('-v / --version','Показать версию клиента.','Проверить выбранный файл до настройки сервера.','jf --version','Не доказывает версию/готовность Artifactory.'),
 flag('-h / --help','Показать справку этого уровня.','Сопоставить корневую грамматику с локальными опциями.','jf --help','Для операции нужен её собственный --help.')]),
card('jf config','Пространство управления локальными профилями; само не равно API безопасности.','jf config ПОДКОМАНДА','artifactory-08-cli',aliases=['jf c']),
card('jf config add','Сохранить профиль платформы в выбранном CLI home.','jf config add ID [ОПЦИИ]','artifactory-08-cli',[
 flag('--url URL','Задать HTTPS-базу платформы.','Новый profile без случайного default.','jf config add lab-publisher --url=https://aft.lab.example --interactive=false --access-token-stdin','База платформы без /artifactory для этой формы.'),
 flag('--user ИМЯ','Явно задать имя субъекта.','Особенно при непрозрачном reference token и Go-клиенте.','jf config add lab-publisher --user=receipt-publisher --access-token-stdin --interactive=false --url=https://aft.lab.example','Имя не выдаёт новых прав.'),
 flag('--access-token-stdin','Прочитать access token через стандартный ввод.','Не помещать секрет в argv.','jf config add lab-publisher --access-token-stdin --interactive=false --url=https://aft.lab.example','Конфигурация после сохранения всё равно конфиденциальна.'),
 flag('--interactive','Управлять запросами к пользователю; для скрипта задают =false.','Автоматический сценарий с полными входами.','jf config add lab-publisher --interactive=false --url=https://aft.lab.example --access-token-stdin','Отсутствующий обязательный ввод не должен зависнуть в CI.'),
 flag('--overwrite','Явно разрешить замену профиля с тем же ID.','После принятого решения заменить именно свои credentials.','jf config add lab-publisher --overwrite --interactive=false --url=https://aft.lab.example --access-token-stdin','Не отзывает прежний токен и может изменить последующие цели.')],aliases=['jf c add'],url='https://docs.jfrog.com/integrations/docs/jf-config-add'),
card('jf config show','Показать сохранённый профиль с маскированием чувствительных полей.','jf config show [ID]','artifactory-08-cli',[
 flag('--format ФОРМАТ','Выбрать json/table для вывода.','Нужен управляемый формат диагностики.','jf config show lab-publisher --format=json','Маскирование show не делает config export безопасным.')],aliases=['jf c show'],url='https://docs.jfrog.com/integrations/docs/jf-config-show'),
card('jf config remove','Удалить локальный профиль; не отозвать серверный токен.','jf config remove ID [ОПЦИИ]','artifactory-08-cli',[
 flag('--quiet','Не запрашивать подтверждение удаления локального profile.','Удаляется только известный собственный ID.','jf config remove lab-publisher --quiet','Без ID операция имеет более широкий смысл; не применять молча.')],aliases=['jf config rm','jf c rm','jf c remove']),
card('jf rt','Пространство операций Artifactory; локальные флаги ставят после выбранной операции.','jf rt ОПЕРАЦИЯ','artifactory-08-cli'),
card('jf rt ping','Проверить ответ Artifactory ping, отдельно от прав repository.','jf rt ping [ОПЦИИ]','artifactory-02-runtime',[server('jf rt ping')],aliases=['jf rt p']),
card('jf rt curl','Добавить Artifactory-базу/credentials к настоящему curl; его параметры имеют свою грамматику.','jf rt curl [CURL АРГУМЕНТЫ] --server-id=ID','artifactory-08-cli',[
 server('jf rt curl /api/system/ping'),
 flag('-X МЕТОД / --request МЕТОД','Передать HTTP-метод внешнему curl.','Точный API требует POST/PUT.','jf rt curl -X POST /api/search/aql --server-id=lab-publisher --data-binary @fixtures/receipt-query.aql','Метод не выдаёт полномочия и не делает операцию безопасной по названию.'),
 flag('-H ЗАГОЛОВОК / --header ЗАГОЛОВОК','Передать один явный HTTP-заголовок.','Указать формат собственного тела.','jf rt curl -X POST /api/search/aql -H "Content-Type: text/plain" --data-binary @fixtures/receipt-query.aql --server-id=lab-publisher','Значение с пробелами передаётся одним argv-элементом.'),
 flag('--data-binary ДАННЫЕ','Передать точные байты, @ФАЙЛ читает подготовленный файл.','Не менять LF или сериализацию тела.','jf rt curl -X POST /api/search/aql --data-binary @fixtures/receipt-query.aql --server-id=lab-publisher','Файл должен существовать до запроса.'),
 flag('--fail','Считать HTTP4xx/5xx ошибкой curl.','Остановить зависимые действия.','jf rt curl /api/system/ping --server-id=lab-publisher --fail','Не все сетевые отказы являются HTTP-ответом.'),
 flag('--silent','Убрать индикатор прогресса curl.','Читать короткий ответ или JSON.','jf rt curl /api/system/ping --server-id=lab-publisher --silent --show-error','--show-error сохраняет видимость ошибки.'),
 flag('--show-error','Вывести ошибку при --silent.','Нужен тихий, но диагностируемый запрос.','jf rt curl /api/system/ping --server-id=lab-publisher --silent --show-error --fail','Код выхода всё равно проверяется.')],aliases=['jf rt cl']),
card('jf go-config','Создать проектный resolver/deployer .jfrog/projects/go.yaml.','jf go-config [ОПЦИИ]','artifactory-08-cli',[
 flag('--repo-resolve КЛЮЧ','Выбрать Go источник разрешения.','Настроены local/virtual и доступ.','jf go-config --repo-resolve=go-virtual --server-id-resolve=lab-publisher','Не меняет глобальный go env.'),
 flag('--repo-deploy КЛЮЧ','Выбрать Go local-цель публикации.','Модуль будет публиковаться этим проектом.','jf go-config --repo-deploy=go-local --server-id-deploy=lab-publisher','Не означает deploy в remote.'),
 flag('--server-id-resolve ID','Ссылка на profile разрешения.','Иная личность/площадка чем публикация.','jf go-config --repo-resolve=go-virtual --server-id-resolve=lab-publisher','Это локальная опция go-config, не root jf.'),
 flag('--server-id-deploy ID','Ссылка на profile публикации.','Цель выбрана и полномочия выданы.','jf go-config --repo-deploy=go-local --server-id-deploy=lab-publisher','Токен остаётся в profile, не в этом YAML.')],aliases=['jf goc'],url='https://docs.jfrog.com/artifactory/docs/jf-go'),
card('jf go','Выполнить Go через JFrog resolver с отдельными опциями build-info.','jf go GO_АРГУМЕНТЫ [JF ОПЦИИ]','artifactory-08-cli',[
 flag('--no-fallback','Запретить VCS fallback при отсутствии в Artifactory.','Private путь должен оставаться у утверждённого источника.','jf go build ./cmd/receipt --no-fallback','Не заменяет GONOPROXY/GONOSUMDB или серверную политику.')]+buildflags('jf go build ./cmd/receipt'),url='https://docs.jfrog.com/artifactory/docs/jf-go'),
card('jf go-publish','Опубликовать Go source module выбранного проекта.','jf go-publish ВЕРСИЯ [ОПЦИИ]','artifactory-06-go-protocol',[
 flag('--exclusions ШАБЛОНЫ','Исключить выбранные файлы из публикации.','Проверенный состав module archive требует ограничения.','jf go-publish v1.0.0 --exclusions="private/*;*.pem"','Не замена allowlist и проверке ZIP; меняет содержимое/h1.'),
 flag('--detailed-summary','Включить список затронутых файлов в summary.','Разобрать состав публикации.','jf go-publish v1.0.0 --detailed-summary','Журнал может раскрывать пути, не публикуйте секреты.')]+buildflags('jf go-publish v1.0.0'),aliases=['jf gp'],url='https://docs.jfrog.com/artifactory/docs/jf-go'),
card('jf rt upload','Передать собственные файлы в Artifactory и при выборе собрать сведения build.','jf rt upload ИСТОЧНИК ЦЕЛЬ [ОПЦИИ]','artifactory-09-promotion',[
 server('jf rt upload release/manifest.json generic-candidates/receipt/1.0.0/'),
 flag('--flat','При =true использовать basename вместо сохранения локального дерева.','Точные два файла выпуска.','jf rt upload release/manifest.json generic-candidates/receipt/1.0.0/ --flat=true --server-id=lab-publisher','Не публикуется абсолютная структура папок клиента.'),
 flag('--fail-no-op','При =true вернуть2, если ни один файл не затронут.','Пустой pattern не должен выглядеть успешной поставкой.','jf rt upload "release/missing*" generic-candidates/receipt/1.0.0/ --fail-no-op=true --server-id=lab-publisher','Код2проверяется как отказ пустого шаблона; явный отсутствующий путь даёт другую ошибку.'),
 flag('--dry-run','Предварительно посмотреть передачу без общения с Artifactory по контракту версии.','Разобрать локальное сопоставление до upload.','jf rt upload release/manifest.json generic-candidates/receipt/1.0.0/ --dry-run --server-id=lab-publisher','Не проверяет реальные права или существование цели.'),
 flag('--detailed-summary','Добавить список source/target в результат передачи.','Сравнить flat на том же входе без сервера.','jf rt upload input/tree/item.txt generic-candidates/test/ --dry-run --flat=true --detailed-summary --server-id=lab-publisher','Dry-run показывает план; пустая sha256 не является принятой суммой файла.'),
 flag('--threads ЧИСЛО','Ограничить одновременные передачи файлов.','Сравнить одинаковый набор при измеренной нагрузке.','jf rt upload "release/*" generic-candidates/receipt/1.0.0/ --threads=1 --server-id=lab-publisher','Больше потоков не равно автоматически быстрее.')]+buildflags('jf rt upload release/manifest.json generic-candidates/receipt/1.0.0/'),aliases=['jf rt u']),
card('jf rt download','Получить разрешённые объекты в определённую папку.','jf rt download ИСТОЧНИК КАТАЛОГ [ОПЦИИ]','artifactory-09-promotion',[
 server('jf rt download generic-releases/receipt/1.0.0/manifest.json receiving/'),
 flag('--flat','При =true не воспроизводить repository path на клиенте.','Чистый receiving для manifest verifier.','jf rt download generic-releases/receipt/1.0.0/manifest.json receiving/ --flat=true --server-id=lab-reader','В принимающем каталоге не должно быть конфликтующих чужих basename.'),
 flag('--fail-no-op','При =true считать пустой результат отказом.','Нужен именно указанный принятый объект.','jf rt download generic-releases/receipt/1.0.0/missing receiving/ --fail-no-op=true --server-id=lab-reader','Не обойти отказ расширением pattern на всё.'),
 flag('--threads ЧИСЛО','Задать параллелизм между файлами.','Ограниченный опыт сетевой/дисковой цены.','jf rt download "generic-releases/receipt/1.0.0/*" receiving/ --threads=1 --server-id=lab-reader','Сравнивать те же исходные кэши и ошибки.')],aliases=['jf rt dl']),
card('jf rt build-add-dependencies','Записать файлы как зависимости локально накапливаемого build-info.','jf rt build-add-dependencies ИМЯ НОМЕР PATTERN [ОПЦИИ]','artifactory-08-cli',[
 flag('--dry-run','Показать план добавления без записи зависимостей.','Сверить local pattern.','jf rt build-add-dependencies receipt-proof 1 input.txt --dry-run','Не скачивает зависимости и не публикует build-info.'),
 flag('--module ИМЯ','Выбрать модуль в описании сборки.','Несколько осмысленных частей одного выполнения.','jf rt build-add-dependencies receipt-proof 1 input.txt --module=inputs','Идентичность модуля не равна module path Go.')],aliases=['jf rt bad']),
card('jf rt build-publish','Собрать и отправить накопленное build-info, отдельно от байтов.','jf rt build-publish ИМЯ НОМЕР [ОПЦИИ]','artifactory-09-promotion',[
 server('jf rt build-publish receipt 1'),
 flag('--dry-run','Вывести собранный JSON без его публикации на сервер.','Прочитать состав/секреты перед отправкой.','jf rt build-publish receipt 1 --dry-run --server-id=lab-publisher','Настоящий CLI, но не проверка server rights.'),
 flag('--collect-env','Включить сбор окружения; по умолчанию этого не делаем.','Только после принятия allowlist и проверки вывода.','jf rt build-publish receipt 1 --dry-run --collect-env --env-include=CI_PIPELINE_ID --server-id=lab-publisher','Не публикуйте все секреты под видом provenance.'),
 flag('--env-include ШАБЛОНЫ','Выбрать разрешённые имена переменных.','Нужны только определённые сведения CI.','jf rt build-publish receipt 1 --dry-run --collect-env --env-include="CI_PIPELINE_ID;CI_COMMIT_SHA" --server-id=lab-publisher','Список через; передаётся одним аргументом.'),
 flag('--overwrite','Явно заменить прежние записи build-info этого имени/номера.','Только осмысленное восстановление своих записей.','jf rt build-publish receipt 1 --overwrite --server-id=lab-publisher','Не удаляет и не пересобирает бинарники, может изменить доказательства.')],aliases=['jf rt bp'],url='https://docs.jfrog.com/artifactory/docs/build-integration'),
card('jf rt build-promote','Продвинуть артефакты опубликованного build.','jf rt build-promote ИМЯ НОМЕР ЦЕЛЬ [ОПЦИИ]','artifactory-09-promotion',[
 server('jf rt build-promote receipt 1 generic-releases'),
 flag('--copy','При =true копировать вместо перемещения.','Кандидат должен остаться доступным.','jf rt build-promote receipt 1 generic-releases --copy=true --server-id=lab-promoter','Не удваивает обязательно физические байты checksum storage.'),
 flag('--include-dependencies','При =true включить зависимости; в нашем выпуске явно =false.','Не переносить Go dependencies в Generic.','jf rt build-promote receipt 1 generic-releases --include-dependencies=false --server-id=lab-promoter','Состав должен соответствовать принятому набору.'),
 flag('--source-repo КЛЮЧ','Ограничить источник указанным repository.','Build содержит объекты из нескольких областей.','jf rt build-promote receipt 1 generic-releases --source-repo=generic-candidates --server-id=lab-promoter','Не меняет сам build number.'),
 flag('--status СТАТУС','Записать состояние процесса продвижения.','Доказательства приёмки уже есть.','jf rt build-promote receipt 1 generic-releases --status=Released --server-id=lab-promoter','Статус не является подписью или автоматической неизменностью.'),
 flag('--comment ТЕКСТ','Сохранить пояснение одним аргументом.','Связать решение с журналом.','jf rt build-promote receipt 1 generic-releases --comment="Личный выпуск принят" --server-id=lab-promoter','Пробелы требуют кавычек оболочки.'),
 flag('--fail-fast','При =true остановить дальнейшую обработку после ошибки.','Избежать продолжения заведомо неуспешного плана.','jf rt build-promote receipt 1 generic-releases --fail-fast=true --server-id=lab-promoter','Уже выполненное не откатывается транзакционно.'),
 flag('--dry-run','Предварительно смоделировать продвижение серверной операцией.','Оценить план до изменений.','jf rt build-promote receipt 1 generic-releases --dry-run --server-id=lab-promoter','Не обещает полного отсутствия HTTP и не равно build-publish dry-run.')],aliases=['jf rt bpr'],url='https://docs.jfrog.com/artifactory/docs/build-integration'),
]

ORAS='https://github.com/oras-project/oras/tree/v1.3.6'
def oci_common(command):
    return [flag('--ca-file ФАЙЛ','Выбрать доверенную CA для registry HTTPS.','Личная учебная CA без общего --insecure.',command+' --ca-file private/ca.crt','Не является приватным ключом или разрешением доступа.'),
            flag('--registry-config ФАЙЛ','Выбрать отдельное хранилище credentials.','Не использовать общий Docker profile.',command+' --registry-config private/oras-reader.json','Файл с токеном не публикуется.')]
COMMANDS += [
card('oras version','Показать версию подготовленного ORAS.','oras version','artifactory-10-oci',url=ORAS),
card('oras login','Установить доступ к принятому registry; требует его готовности.','oras login HOST [ОПЦИИ]','artifactory-10-oci',[
 flag('-u ИМЯ / --username ИМЯ','Задать обычную личность registry.','Токен не содержит подходящего client username.','oras login aft.lab.example --username receipt-publisher --password-stdin','Не выдаёт серверных прав.'),
 flag('--password-stdin','Прочитать секрет через stdin.','Избежать токена в argv.','oras login aft.lab.example --username receipt-publisher --password-stdin','Файл registry-config после login чувствителен.')]+oci_common('oras login aft.lab.example'),url=ORAS),
card('oras push','Передать граф OCI либо создать локальный layout.','oras push REFERENCE ФАЙЛ[:MEDIA_TYPE]... [ОПЦИИ]','artifactory-10-oci',[
 flag('--oci-layout','Использовать локальный layout вместо registry.','Проверить формат без сети/daemon.','oras push --oci-layout work/layout:1.0.0 payload.txt:text/plain','Не доказывает работу Artifactory.'),
 flag('--artifact-type ТИП','Указать смысл типа произвольного OCI artifact.','Передаём файл выпуска, не контейнерный image.','oras push --oci-layout work/layout:1.0.0 --artifact-type application/vnd.handbook.receipt.v1 payload.txt:text/plain','Тип не создаёт entrypoint/rootfs.'),
 flag('-a ЗАПИСЬ / --annotation ЗАПИСЬ','Добавить key=value к манифесту.','Зафиксировать метаданные контролируемого опыта.','oras push --oci-layout work/layout:1.0.0 --annotation org.opencontainers.image.created=2026-11-01T00:00:00Z payload.txt:text/plain','Изменение этих байтов меняет manifest digest.')]+oci_common('oras push aft.lab.example/oci-local/receipt:1.0.0 payload.txt:text/plain'),url=ORAS),
card('oras pull','Получить файлы OCI graph, отдельно от запуска программы.','oras pull REFERENCE [ОПЦИИ]','artifactory-10-oci',[
 flag('--oci-layout','Читать из локального формата.','Принять сохранённый layout без registry.','oras pull --oci-layout work/layout:1.0.0 --output receiving','Не восстанавливает БД Artifactory.'),
 flag('-o КАТАЛОГ / --output КАТАЛОГ','Выбрать каталог получаемых файлов.','Новая пустая принимающая папка.','oras pull --oci-layout work/layout:1.0.0 --output receiving','Не включайте allow-path-traversal ради прохождения ошибки.')]+oci_common('oras pull aft.lab.example/oci-local/receipt:1.0.0'),url=ORAS),
card('oras manifest fetch','Получить манифест либо дескриптор; не все blobs сразу.','oras manifest fetch REFERENCE [ОПЦИИ]','artifactory-10-oci',[
 flag('--oci-layout','Получить объект из локального layout.','Разбор точных байтов формата.','oras manifest fetch --oci-layout work/layout:1.0.0','Это другой формат, чем filestore.'),
 flag('--descriptor','Вывести descriptor вместо тела манифеста.','Зафиксировать digest,size,mediaType.','oras manifest fetch --oci-layout --descriptor work/layout:1.0.0','Digest относится к байтам описанного манифеста.')]+oci_common('oras manifest fetch aft.lab.example/oci-local/receipt:1.0.0'),url=ORAS),
]

OWN='labs/README.txt'
COMMANDS += [
card('python3 tests/local_checks.py','Исполнить настоящий Go/CLI и собственные fixtures/models в новом временном каталоге.','python3 tests/local_checks.py --go ПУТЬ --jf ПУТЬ [--report ФАЙЛ]','artifactory-17-lab',[
 flag('--go ПУТЬ','Выбрать проверенный подготовленный Go.','Нельзя автоматически скачивать toolchain.','python3 tests/local_checks.py --go /path/to/go --jf /path/to/jf','Не меняет общий go env.'),
 flag('--jf ПУТЬ','Выбрать проверенный CLI2.129.0.','Сравнить реальную грамматику и локальные операции.','python3 tests/local_checks.py --go /path/to/go --jf /path/to/jf','Не запускает Artifactory.'),
 flag('--report ФАЙЛ','Записать обезличенный отчёт.','Сохранить фактический результат.','python3 tests/local_checks.py --go /path/to/go --jf /path/to/jf --report report.json','Приватные paths/keys/tokens не сохраняются.')],url=OWN),
card('python3 release_manifest.py','Создать либо проверить собственный непустой manifest выпуска.','python3 release_manifest.py create|verify ОПЦИИ','artifactory-09-promotion',url=OWN),
card('python3 release_manifest.py create','Сохранить version/toolchain и сведения конкретных файлов.','python3 release_manifest.py create --version ВЕРСИЯ --toolchain ТЕКСТ --file ФАЙЛ --output JSON','artifactory-09-promotion',[
 flag('--file ФАЙЛ','Добавить ровно один regular file; флаг повторяется.','Известен точный состав выпуска.','python3 release_manifest.py create --version 1.0.0 --toolchain "go1.27.3 linux/amd64" --file release/receipt-linux-amd64 --output release/manifest.json','Дубликаты basename не принимаются.'),
 flag('--version ВЕРСИЯ','Обозначить выпуск программы.','Не путать с build number.','python3 release_manifest.py create --version 1.0.0 --toolchain Go --file release/app --output release/manifest.json','Правдивость поля — ответственность процесса.'),
 flag('--toolchain ТЕКСТ','Записать фактически использованный compiler.','Нужна опись входов.','python3 release_manifest.py create --version 1.0.0 --toolchain "go1.27.3 linux/amd64" --file release/app --output release/manifest.json','Поле само не устанавливает/проверяет compiler.'),
 flag('--output JSON','Сохранить manifest по выбранному пути.','Каталог уже подготовлен.','python3 release_manifest.py create --version 1.0.0 --toolchain Go --file release/app --output release/manifest.json','Доверенная доставка manifest отдельно от файла.')],url=OWN),
card('python3 release_manifest.py verify','Проверить контракт, имена, границы bundle и SHA256.','python3 release_manifest.py verify --manifest JSON --directory КАТАЛОГ','artifactory-09-promotion',[
 flag('--manifest JSON','Прочитать отдельно принятый JSON.','Сравнить received bytes с ожиданием.','python3 release_manifest.py verify --manifest release/manifest.json --directory release','Пустые files/дубликаты/неверные поля отвергаются.'),
 flag('--directory КАТАЛОГ','Задать разрешённую область файлов.','Отвергнуть symlink/выход за bundle.','python3 release_manifest.py verify --manifest release/manifest.json --directory release','Не защищает от другого процесса, меняющего файлы во время проверки.')],url=OWN),
]
