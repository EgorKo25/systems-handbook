"""Original state-by-state illustrations. Fixed scenarios, no live platform calls."""


def step(title, explanation, actor, focus, active, states, field):
    name, before, after, why = field
    return dict(title=title, explanation=explanation, actor=actor, focus=focus,
                active=active, states=states,
                fields=[dict(name=name, before=before, after=after, why=why)],
                bands=[dict(label=name, value=after, detail=why)])


def diagram(identifier, chapter, title, intro, assumptions, nodes, edges, steps):
    return dict(id=identifier, volume='gitlab', chapter=chapter, anchor=chapter,
                title=title, intro=intro, assumptions=assumptions,
                nodes=[dict(id=i, label=label, sub=sub) for i, label, sub in nodes],
                edges=[dict(id=i, **{'from': a, 'to': b}, label=label) for i,a,b,label in edges],
                steps=steps)


DIAGRAMS = [diagram(
    'gitlab-from-push-to-process', '01-platform-and-state',
    'Коммит уже сохранён, а процесс Go ещё не запущен',
    'Один push проходит разные границы: Git, приложение, граф, Runner, среда и процесс. Следующий шаг не считается выполненным от одного существования предыдущего.',
    'Личный приватный проект; коммит C17; подходящий Runner имеет один слот и сначала занят. HTTPS/SSH и разрешения уже подготовлены. События и длительности условные; стрелки показывают логические действия, а не каждый пакет. Gitaly, Rails и очередь свернуты до нужной здесь границы; это не полный протокол GitLab.',
    [('git','Git-хранилище','Коммит и ссылка'),('app','Приложение','Права и описание CI'),('graph','Конвейер','Граф заданий'),('runner','Runner','Получение работы'),('work','Среда job','Исходники и файлы'),('process','Go-процесс','Команда ОС')],
    [('event','git','app','событие принятого push'),('create','app','graph','создать граф'),('claim','graph','runner','выдать готовое job'),('prepare','runner','work','подготовить среду'),('spawn','work','process','запустить Go'),('result','process','runner','код и вывод')],
    [step('Сервер принял C17','Ссылка ветки обновлена на C17. Это подтверждает Git-операцию, но пока не выполнение CI.','Git-службы',['git'],[],{'git':'C17 сохранён','app':'событие впереди','graph':'нет','runner':'другой job','work':'не создана','process':'нет'},('Исходники','клиентская копия','серверная ссылка → C17','Существование коммита не означает создания pipeline.')),
     step('Создан pipeline №81','Приложение разрешило событие, разобрало конфигурацию и создало задания.','GitLab',['app','graph'],['event','create'],{'git':'C17','app':'правила разрешили','graph':'unit готов','runner':'слот занят','work':'нет','process':'нет'},('Pipeline','не существовал','№81, unit ожидает','Правила и конфигурация обрабатываются до shell.')),
     step('Готовое задание ждёт','Единственный подходящий слот занят. Несоответствующий Runner не помогает.','Планирование',['graph','runner'],[],{'git':'C17','app':'№81','graph':'unit pending','runner':'занято 1/1','work':'нет','process':'нет'},('Время','job создан','растёт очередь','Задержка ожидания отличается от длительности Go-теста.')),
     step('Runner получил unit','После освобождения слота manager получил работу и начал подготовку executor.','Runner manager',['runner','work'],['claim','prepare'],{'git':'C17','app':'№81','graph':'unit назначен','runner':'unit, слот 1/1','work':'подготовка','process':'ещё нет'},('Слот','занят прежней работой','отдан unit','Получение работы ещё не гарантирует успешного создания контейнера.')),
     step('Готовы входы C17','Получены исходники, допустимый кэш и нужные артефакты; затем запускается основная часть.','Runner и executor',['work','process'],['prepare','spawn'],{'git':'C17','app':'№81','graph':'unit running','runner':'исполняет unit','work':'C17, reports/','process':'go test работает'},('Процесс','отсутствовал','go test -json -count=1','Теперь действительно началось выполнение пользовательской программы.')),
     step('Результат ещё надо сохранить','Go вернул код; Runner загружает предусмотренный отчёт и завершает работу.','Go и Runner',['process','runner','graph'],['result'],{'git':'C17','app':'№81','graph':'ждёт итог','runner':'передаёт результат','work':'junit.xml','process':'завершился 0'},('Доказательство','код 0 в ОС','отчёт и статус в GitLab','Неуспешная передача результата — отдельная возможная граница отказа.'))]
), diagram(
    'gitlab-graph-data-dependencies', '05-pipeline-compilation',
    'Зависимость исполнения и передача файла идут вместе',
    'В исходном графе unit и vet готовы одновременно. Build ждёт обе проверки, verify требует конкретный результат build. Необходимый файл не появляется от одного порядка слов YAML.',
    'Один успешный pipeline с двумя подходящими слотами; unit условно длится 8 с, vet 3 с, build 5 с, verify 1 с. Сеть и накладные затраты здесь нулевые исключительно для подсчёта модели. В реальном стенде их измеряют отдельно. Все четыре задания включены rules.',
    [('event','Событие','Выбран C17'),('unit','Unit','Go-тесты'),('vet','Vet','Статический анализ'),('build','Build','Создать echo'),('artifact','Артефакт','echo + manifest'),('verify','Verify','Запустить те же байты')],
    [('u','event','unit','первый этап'),('v','event','vet','первый этап'),('ub','unit','build','допуск'),('vb','vet','build','допуск'),('save','build','artifact','загрузка'),('get','artifact','verify','needs: artifacts')],
    [step('Сначала вычислен состав','Workflow разрешил событие; unit, vet, build и verify созданы.','GitLab',['event','unit','vet'],['u','v'],{'event':'C17 разрешён','unit':'ready','vet':'ready','build':'ждёт check','artifact':'нет','verify':'ждёт build'},('Граф','YAML и событие','четыре вершины','Правила выбирают состав до команд.')),
     step('Два задания исполняются','Два свободных слота позволяют unit и vet реально работать одновременно.','Два Runner-слота',['unit','vet'],['u','v'],{'event':'C17','unit':'running, 0..8 с','vet':'running, 0..3 с','build':'ждёт','artifact':'нет','verify':'ждёт'},('Параллелизм','готовы два','работают два','Без второго слота граф не обеспечивает одновременность.')),
     step('Vet готов раньше','К третьей секунде vet завершился, unit ещё работает; барьер check остаётся.','Планировщик',['unit','vet','build'],[],{'event':'C17','unit':'running до t=8','vet':'success t=3','build':'ещё ждёт unit','artifact':'нет','verify':'ждёт'},('Барьер','одна проверка готова','build не стартует','Успех одного предшественника не заменяет все обязательные проверки.')),
     step('Build получил допуск','В t=8 unit завершился; build начинает работу и создаёт бинарник.','Build',['unit','build'],['ub','vb'],{'event':'C17','unit':'success t=8','vet':'success','build':'running t=8..13','artifact':'ещё не загружен','verify':'ждёт'},('Исходники','C17 проверен','C17 компилируется','Пока файл в workspace, другой job его не имеет.')),
     step('Сохранён обязательный результат','Build создал echo и manifest и загрузил их как свой artifact.','Runner build',['build','artifact'],['save'],{'event':'C17','unit':'success','vet':'success','build':'success t=13','artifact':'SHA H17','verify':'может получить'},('Файл','workspace build','artifact build, SHA H17','Кэш здесь не используется как обязательное хранилище.')),
     step('Verify проверил H17','Отдельный job получил артефакт build, проверил SHA и запустил именно этот файл.','Verify',['artifact','verify'],['get'],{'event':'C17','unit':'success','vet':'success','build':'success','artifact':'SHA H17','verify':'success t=14'},('Время','сумма job 17 с','критический путь 14 с','8+5+1 определяют длительность этой идеализированной схемы.'))]
),  diagram(
    'gitlab-artifact-promotion', '10-caches-and-artifacts',
    'Кэш можно потерять; выпускаемый бинарник должен оставаться тем же',
    'Разделим ускорение Go, результат job и продвижение конкретного SHA через проверку.',
    'Учебный SHA H17 — символическое обозначение 256-битного хеша, не реальный хеш файла. Build и verify работают в разных чистых средах. Кэш необязателен, artifact build обязателен; публикация package показана как дальнейшее действие, не выполняемое локальным ci.py.',
    [('source','C17','Исходники'),('cache','Go-cache','Необязательное ускорение'),('build','Build workspace','Компилятор'),('artifact','Artifact build','Бинарник H17'),('verify','Verify workspace','Проверка H17'),('package','Versioned package','Долгий срок')],
    [('compile','source','build','входы'),('restore','cache','build','если есть'),('save','build','artifact','обязательная передача'),('download','artifact','verify','получить тот же файл'),('publish','verify','package','продвинуть H17')],
    [step('Кэш отсутствует','Build обязан уметь получить правильный результат из подготовленных исходников и инструментов без CI-cache.','Build',['source','cache','build'],['compile'],{'source':'C17','cache':'miss','build':'полная работа','artifact':'нет','verify':'не запущен','package':'нет'},('Корректность','нет cache','сборка всё равно возможна','В этом проекте нет внешних модулей; toolchain уже подготовлен.')),
     step('Получены байты H17','Go завершил сборку; manifest записал размер и SHA. Пока всё только в build workspace.','Go и ci.py',['build'],[],{'source':'C17','cache':'можно обновить','build':'echo, SHA H17','artifact':'нет','verify':'нет','package':'нет'},('Идентичность','исходный C17','результат H17','SHA бинарника и commit SHA описывают разные объекты.')),
     step('Артефакт сохранён','Runner загрузил echo и manifest как результат build.','Runner',['build','artifact'],['save'],{'source':'C17','cache':'необязателен','build':'успешен','artifact':'H17, срок 7 дней','verify':'готов к получению','package':'нет'},('Договор','локальные байты','обязательный artifact job','Успех только компилятора не гарантирует этот переход.')),
     step('Другая среда получила H17','Verify скачал artifact, а не использовал случайный общий cache.','Runner verify',['artifact','verify'],['download'],{'source':'C17','cache':'может быть пуст','build':'закончен','artifact':'H17','verify':'echo + manifest H17','package':'нет'},('Граница','другой workspace','конкретный artifact build','Изоляция job требует явной передачи нужных файлов.')),
     step('Проверена целостность и версия','Verify вычислил SHA, сравнил размер и запустил echo -version. Повреждение приводит к отказу до запуска.','ci.py verify',['verify'],[],{'source':'C17','cache':'не участвует','build':'закончен','artifact':'H17','verify':'H17 проверен','package':'ещё нет'},('Доказательство','файл загружен','байты совпали, версия отвечает','Это ограниченная проверка, не доказательство отсутствия всех ошибок.')),
     step('Продвигается тот же H17','Для длительного выпуска публикуют фиксированный package с политикой неизменности и доверенным происхождением.','Система выпуска',['verify','package'],['publish'],{'source':'C17','cache':'можно очистить','build':'закончен','artifact':'может позднее истечь','verify':'проверен H17','package':'версия v0.1.0 → H17'},('Срок','временный artifact','версионированный package','Ссылка latest и новый независимый build не равны продвижению H17.'))]
)]
