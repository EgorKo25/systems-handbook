"""Fixed original scenarios, rendered by the shared offline reader; no live execution."""


def step(title, explanation, actor, focus, active, states, field):
    name, before, after, why = field
    return dict(title=title, explanation=explanation, actor=actor, focus=focus,
                active=active, states=states,
                fields=[dict(name=name, before=before, after=after, why=why)],
                bands=[dict(label=name, value=after, detail=why)])


def diagram(identifier, chapter, title, intro, assumptions, nodes, edges, steps, marker=None):
    result = dict(id=identifier, volume='ansible', chapter=chapter, anchor=chapter,
                  title=title, intro=intro, assumptions=assumptions,
                  nodes=[dict(id=i, label=label, sub=sub) for i, label, sub in nodes],
                  edges=[dict(id=i, **{'from': a, 'to': b}, label=label) for i, a, b, label in edges],
                  steps=steps)
    if marker:
        result['insert_before'] = marker
    return result


DIAGRAMS = [diagram(
    'an-task-execution', 'an-04-task-engine', 'Один template проходит controller и target',
    'Проверяем, в какой момент появился новый файл, когда был получен changed и почему процесс ещё может быть старым.',
    'Фиксированная модель, не запись реального SSH. Один личный Linux-target, доверенный SSH, Python и become подготовлены. Template не содержит секретов. Модульные детали свёрнуты до контрактов; конкретный transport может передавать код через temporary file или stdin.',
    [('input','Входы','Inventory, play, vars'),('control','Controller','Шаблон/action'),('transport','Канал','SSH и become'),('module','Python target','Модуль/ОС'),('file','Файл','Конечные байты'),('result','Результат','Changed/notify')],
    [('select','input','control','выбрать host и вычислить'),('send','control','transport','код и аргументы'),('start','transport','module','запустить с UID'),('write','module','file','сравнить/заменить'),('reply','module','result','JSON ответа'),('notify','result','control','handler ожидает')],
    [step('Выбран counter_a','Hosts и limit дали одного участника. Данные ещё не изменяли ОС.','Загрузчик и strategy',['input','control'],['select'],{'input':'counter_a','control':'готовит task','transport':'нет обмена','module':'нет','file':'version=0.1','result':'нет'},('Выборка','группа из двух','один host','Limit сужает hosts play.')),
     step('Вычислены байты','Jinja на controller создала JSON версии 0.2. Ошибка undefined остановила бы путь здесь.','Template action',['control'],['select'],{'input':'release=0.2','control':'кандидат JSON','transport':'готов','module':'нет','file':'0.1','result':'нет'},('Кандидат','Jinja-источник','конкретные байты 0.2','Target не получает обязанность рендерить Jinja.')),
     step('Запущен модуль','Connection/become организовали запуск Python. Права определяет effective UID.','SSH, shell, become',['transport','module'],['send','start'],{'input':'0.2','control':'ждёт','transport':'канал активен','module':'читает состояние','file':'0.1','result':'нет'},('Исполнение','нет процесса','Python с нужным UID','Само соединение ещё не изменило файл.')),
     step('Кандидат проверен','Validate принял конфигурацию. Модуль публикует новые байты при разрешённом реальном применении.','Модуль и ОС',['module','file'],['write'],{'input':'0.2','control':'ждёт','transport':'активен','module':'замена прошла','file':'0.2','result':'ещё в пути'},('Файл','0.1','0.2','Реальная запись отличается от check-прогноза.')),
     step('Ответ принят','JSON сообщает changed=true. Action и changed_when формируют окончательный результат.','Модуль → controller',['module','result'],['reply'],{'input':'0.2','control':'результат принят','transport':'ответ получен','module':'закончен','file':'0.2','result':'changed=true'},('Свидетельство','ответа нет','changed=true','Потеря ответа могла бы оставить новый файл при неизвестном результате.')),
     step('Handler только ожидает','Notify поставил перезапуск в очередь host. Процесс пока может читать прежний config из памяти.','Controller',['result','control'],['notify'],{'input':'0.2','control':'restart ожидает','transport':'свободен','module':'закончен','file':'0.2','result':'notify принят'},('Процесс','версия config 0.1','всё ещё может быть 0.1','Изменение файла не перезапуск.')),
     step('После flush проверяется приложение','Handler применил изменение; отдельный HTTP-запрос должен подтвердить ожидаемую версию и данные.','Handler и проверочная task',['control','result'],['send','start','reply'],{'input':'0.2','control':'проверяет','transport':'новый запрос','module':'restart завершён','file':'0.2','result':'version/count наблюдены'},('Приёмка','только changed','проверена версия/данные','Recap суммирует события, но не заменяет прикладной проверки.'))],
    '<div id="an-task-marker"></div>'
), diagram(
    'an-variable-resolution', 'an-07-variables', 'Почему в задаче получилось 8084, затем 8083',
    'Для каждого использования видны источник, область и момент вычисления. Extra vars меняет обе задачи, set_fact сохраняет снимок.',
    'Фиксированная модель конфликта counter_port. Role default 8080, group 8081, host 8082, play 8083, task 8084. Все значения integer; special connection variables не участвуют. Полная таблица precedence шире показанного фрагмента.',
    [('defaults','Defaults','Роль: 8080'),('inventory','Inventory','Group/host'),('play','Play vars','8083'),('task','Task vars','8084'),('extra','Extra vars','опционально 8085'),('use','Использование','Тип и момент')],
    [('inv','defaults','inventory','более конкретный источник'),('playwins','inventory','play','play перекрывает'),('taskwins','play','task','только контекст task'),('usevalue','task','use','вычислить аргумент'),('extrawins','extra','use','высокий приоритет')],
    [step('Inventory сводится на host','Host8082 перекрывает group 8081 и default8080. Это ещё не итог task.','Inventory loader',['defaults','inventory'],['inv'],{'defaults':'8080','inventory':'8082','play':'ещё не контекст','task':'нет','extra':'нет','use':'не вычислено'},('Кандидат','8080/8081','host=8082','Узловое определение конкретнее группового.')),
     step('Play даёт 8083','В play значение 8083 перекрывает inventory для обычных задач.','Variable manager',['inventory','play'],['playwins'],{'defaults':'8080','inventory':'8082','play':'8083','task':'нет','extra':'нет','use':'кандидат 8083'},('Приоритет','host 8082','play 8083','Чтение inventory позже не делает его сильнее play vars.')),
     step('Первая задача видит 8084','Её локальные vars перекрывают play только в этом контексте.','Task executor',['task','use'],['taskwins','usevalue'],{'defaults':'8080','inventory':'8082','play':'8083','task':'8084','extra':'нет','use':'integer 8084'},('Аргумент','8083','8084','Область task заканчивается вместе с вызовом.')),
     step('Следующая задача видит 8083','У второй нет task override; set_fact фиксирует именно этот результат.','Следующая task',['play','use'],['playwins','usevalue'],{'defaults':'8080','inventory':'8082','play':'8083','task':'нет','extra':'нет','use':'frozen 8083'},('Снимок','ещё нет','frozen=8083','Позднее task value 9090 не пересчитывает уже присвоенный set_fact.')),
     step('Новый запуск с extra 8085','JSON extra var имеет высокий приоритет и сохраняет тип. Оба контекста увидят 8085.','Оператор/controller',['extra','use'],['extrawins'],{'defaults':'8080','inventory':'8082','play':'8083','task':'8084/9090','extra':'integer 8085','use':'8085 в обеих'},('Победитель','task/play','extra 8085','Обычный CLI -u и extra -e — разные категории.'))],
    '<div id="an-vars-marker"></div>'
), diagram(
    'an-release-interruption', 'an-17-go-release', 'Прерывание выпуска: файлы новые, процесс старый',
    'Потеря controller между switch и handler оставляет реальное промежуточное состояние. Повтор сначала читает его, затем выбирается явное действие.',
    'Фиксированная модель одной личной VM. Сохранённые releases 0.1/0.2, одинаковый формат data, один writer. Потеря controller — не обычный failed task, поэтому rescue не обещается. Число 41 условно, не значение рабочей машины.',
    [('operator','Оператор','Desired 0.2'),('release','Releases','Проверенные байты'),('link','Current','Выбор версии'),('config','Config','Проверенный JSON'),('process','Процесс','Работающая версия'),('data','Данные','Постоянный count')],
    [('stage','operator','release','проверить SHA/version'),('switch','release','link','переключить'),('render','operator','config','validate+publish'),('apply','link','process','restart'),('read','process','data','сохранить/прочитать')],
    [step('До выпуска','Текущий выбор и процесс 0.1, count 41. Старый manifest и config сохранены.','Оператор',['operator','process','data'],['read'],{'operator':'0.2 намерение','release':'0.1 есть','link':'0.1','config':'0.1','process':'0.1','data':'41'},('База','не зафиксирована','0.1/count 41','Возврат требует известного прежнего состояния.')),
     step('Stage проверен','Появились неизменяемые байты 0.2 с нужным SHA и compiled version.','Модули',['release'],['stage'],{'operator':'0.2','release':'0.1+0.2','link':'0.1','config':'0.1','process':'0.1','data':'41'},('Артефакт','нет 0.2','проверен 0.2','Новая папка ещё не новый процесс.')),
     step('Switch/config прошли','Current и JSON уже новые, restart ожидает.','Tasks',['link','config'],['switch','render'],{'operator':'0.2','release':'0.1+0.2','link':'0.2','config':'0.2','process':'0.1','data':'41'},('Согласованность','всё 0.1','диск 0.2/процесс 0.1','Это допустимый короткий промежуток до применения.')),
     step('Controller исчез','Нет гарантии rescue. На VM остаётся то, что действительно успело выполниться.','Внешний отказ',['operator','process'],[],{'operator':'нет процесса CLI','release':'0.1+0.2','link':'0.2','config':'0.2','process':'0.1','data':'41'},('Ответ','ожидался','отсутствует','Неизвестность результата не равна откату.')),
     step('Повтор без изменения файлов','Идемпотентные file/template могут не дать notify. Version probe обнаруживает старый процесс.','Новый controller',['link','config','process'],['read'],{'operator':'осматривает','release':'не меняются','link':'0.2 unchanged','config':'0.2 unchanged','process':'0.1 обнаружена','data':'41'},('Повтор','ожидание самопочинки','нужно явное решение','Changed 0 не доказывает применённое состояние службы.')),
     step('Явный restart или возврат','Оператор выбирает force_restart для 0.2 либо desired0.1 с его manifest; затем проверяет version/count.','Оператор и systemd',['operator','process','data'],['apply','read'],{'operator':'действие выбрано','release':'сохранены обе','link':'выбранная версия','config':'соответствует','process':'проверена','data':'не сбрасывается'},('Восстановление','диск/процесс расходятся','подтверждённый комплект','Если формат data несовместим, требуется отдельная стратегия миграции/резерва.'))]
)]
