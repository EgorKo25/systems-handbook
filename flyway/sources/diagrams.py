"""Original finite teaching models; no server, SQL or timing simulation."""


def make(identifier, chapter, marker, title, intro, nodes, edges, rows):
    keys=[node[0] for node in nodes]
    steps=[]
    for title_,explanation,actor,focus,active,values,field in rows:
        name,before,after,why=field
        assert len(values)==len(keys)
        steps.append(dict(title=title_,explanation=explanation,actor=actor,
                          focus=focus,active=active,states=dict(zip(keys,values)),
                          fields=[dict(name=name,before=before,after=after,why=why)],
                          bands=[dict(label=name,value=after,detail=why)]))
    return dict(id=identifier,volume='flyway',chapter=chapter,anchor=chapter,
                insert_before=marker,title=title,intro=intro,
                assumptions='Учебная модель одного собственного PostgreSQL. Числа версий/строк заданы примером; схема не исполняет команды, не показывает живую БД и не измеряет задержки. Не моделирует потерю сети в точке commit или отказ хоста.',
                nodes=[dict(id=key,label=label,sub=sub) for key,label,sub in nodes],
                edges=[dict(id=key,**{'from':a,'to':b},label=label) for key,a,b,label in edges],steps=steps)


DIAGRAMS=[
    make('flyway-resource-resolution','flyway-05-discovery','<h2>Versioned и repeatable</h2>',
         'От каталога до упорядоченного набора',
         'Имя, доступность и применимость файла проверяются до SQL.',
         [('files','migrations/','Байты релиза'),('resolve','Resolver','Имя/версия/checksum'),('history','History','Принято V1'),('plan','План','V2, затем R')],
         [('scan','files','resolve','location'),('compare','history','resolve','принятые факты'),('select','resolve','plan','допустимый набор')],
         [
          ('Ресурсы существуют','Файлы V1,V2,R лежат в известной location, но сервер их ещё не исполняет.','Оператор',['files'],[],['V1,V2,R','не читает','V1 Success','нет'],('Ресурс','каталог','известная location','Нужны правильный cwd и права чтения.')),
          ('Разобрано имя','Resolver выделяет version2 и описание; дубликат версии остановил бы построение.','Resolver',['files','resolve'],['scan'],['те же байты','V2 SQL + checksum','V1','кандидаты'],('Имя','V2__expand_title.sql','version=2','Сортировка по числовым частям, не по байтам имени.')),
          ('Сопоставлена история','V1 уже принята, поэтому не становится Pending второй раз.','Flyway',['history','resolve'],['compare'],['не меняются','V1 известна','rank1/version1','V2 Pending'],('Применимость','все файлы','только новое','История относится к выбранной базе.')),
          ('Применён target','Верхняя граница2 позволяет V2 и не означает откат будущей принятой версии.','Flyway',['plan'],['select'],['V1,V2,R','порядок известен','V1','V2, затем R'],('Target','latest','2','R не получает собственный номер и идёт после V.')),
          ('Готово к исполнению','Для SQL ещё нужны соединение, координация и права; план не является commit.','CLI',['plan'],[],['закреплённый релиз','разбор окончен','не менялась','ожидает migrate'],('Граница','ресурс выбран','SQL ещё не принят','Info не исполняет Pending.')),
         ]),
    make('flyway-migrate-wire-history','flyway-06-request-path','<h2>Исполнение и ответ</h2>',
         'V2: от JDBC до принятой history',
         'Проследите обычную транзакционную миграцию после получения сессионной координации.',
         [('cli','CLI/JDBC','Файлы+настройки'),('pg','PostgreSQL','TLS/auth/SQL'),('lock','Advisory lock','Ключ history'),('data','app.notes','Каталог/данные'),('hist','flyway_meta','Факты исполнения')],
         [('connect','cli','pg','TLS+SCRAM'),('acquire','pg','lock','try advisory lock'),('ddl','pg','data','ALTER TABLE'),('record','pg','hist','result+commit'),('reply','pg','cli','ответ')],
         [
          ('Подключение','Драйвер проверяет серверный сертификат и пароль роли.','JDBC',['cli','pg'],['connect'],['V2 прочитана','flyway_owner принят','свободен','без title','V1'],('Доступ','есть URL','проверенное соединение','Наличие TCP-порта не доказывало права.')),
          ('Координация','Flyway получает свой ключ и обновляет состояние history под ним.','Flyway',['lock','hist'],['acquire'],['ждёт SQL','сессия активна','удерживается','без title','V2 Pending'],('План','предварительный','обновлён под lock','Другой deploy мог успеть до нас.')),
          ('DDL внутри транзакции','PostgreSQL получает relation lock и добавляет nullable title.','PostgreSQL',['pg','data'],['ddl'],['V2 исполняется','транзакция открыта','удерживается','title ещё не commit','пока V1'],('Объект','нет столбца','изменение внутри tx','Advisory и DDL locks имеют разные роли.')),
          ('Результат принят','Для этой транзакционной V2 фиксируются DDL и запись успеха.','PostgreSQL',['data','hist'],['record'],['ждёт результат','commit','пока удерживается','title видим','V2 Success'],('Видимость','незавершённое','зафиксированное','При обычном rollback эта V2 не оставила бы столбец.')),
          ('Завершение','CLI освобождает сессионный advisory lock и возвращает успех.','Flyway',['cli','lock'],['reply'],['exit0','сессия завершится','освобождён','title остаётся','V2 остаётся'],('Процесс','работает','окончен','Данные живут дольше Java-процесса.')),
         ]),
    make('flyway-two-locks','flyway-13-concurrency-failure','<h2>Другой тип ожидания — приложение держит таблицу</h2>',
         'Два deploy и один читающий Go-процесс',
         'Инструмент сериализует себя, но не блокирует прикладные транзакции своим advisory key.',
         [('a','Deploy A','V3'),('b','Deploy B','Тот же V3'),('meta','Advisory','History key'),('app','Go/SQL tx','Долгий SELECT'),('table','Relation lock','app.notes')],
         [('akey','a','meta','получить'),('bkey','b','meta','ожидать'),('read','app','table','AccessShareLock'),('alter','a','table','AccessExclusiveLock')],
         [
          ('Приложение читает','Открытая транзакция удерживает relation lock после SELECT.','Go',['app','table'],['read'],['ещё не начал','ещё не начал','свободен','tx открыта','AccessShare granted'],('Транзакция','короткий запрос','удерживаемый lock','Завершение SELECT не равно commit транзакции.')),
          ('A согласовал history','Advisory key свободен и получен A. Это не даёт relation lock.','Deploy A',['a','meta'],['akey'],['advisory granted','не начал','владеет A','всё ещё открыта','занята app'],('Координация','свободна','занята A','Go не участвует в этом advisory-протоколе.')),
          ('B ждёт A','Второй Flyway не должен выбирать и исполнять V3 параллельно.','Deploy B',['b','meta'],['bkey'],['дальше к ALTER','retry advisory','A','открыта','AccessShare'],('Ожидание B','не начал','lockRetryCount','Это бюджет инструмента, не lock_timeout SQL.')),
          ('A ждёт приложение','ALTER конфликтует с relation lock; срабатывает lock_timeout.','PostgreSQL',['a','table'],['alter'],['V3 timeout','ждёт A','A до cleanup','открыта','DDL не granted'],('Ожидание A','advisory получен','DDL ждёт','Иной lock и иной способ диагностики.')),
          ('Проверка и повтор','После завершения app tx новый deploy заново читает историю и пробует V3.','Оператор',['a','b','app'],[],['предыдущий остановлен','не продолжает слепо','освобождён','commit','DDL может пройти'],('Допуск','ошибка','осмотр, затем новый запуск','Увеличение retries само не устраняло долгую app-транзакцию.')),
         ]),
    make('flyway-expand-contract-states','flyway-11-expand-contract','<h2>Выпуск по воротам допуска</h2>',
         'Условия возврата меняются вместе со схемой',
         'Один текст временно хранится в body и title; удаление старого представления требует отдельного решения.',
         [('old','Go v1','body'),('new','Go v2/v3','Переходный/новый'),('db','app.notes','Два представления'),('gate','Gate','Условия выпуска')],
         [('writeold','old','db','body only'),('writenew','new','db','dual/title'),('observe','db','gate','инварианты'),('release','gate','new','допуск')],
         [
          ('V1','Старое приложение понимает только body; title ещё нет.','Go v1',['old','db'],['writeold'],['работает','v2 ещё нельзя','body NOT NULL','V1 принята'],('Совместимость','исходная','v1','Новая Go-программа до expand не запускается.')),
          ('V2 expand','Добавлен nullable title, body допускает NULL для будущей v3.','Flyway',['db','gate'],['observe'],['ещё работает','v2 допускается','body+title nullable','дренировать v1'],('Схема','body','body+title','Добавление не переносит старые строки.')),
          ('V2 app и backfill','После drain v1 job заполняет title; v2 пишет оба значения.','Go v2 / job',['new','db'],['writenew'],['все остановлены','dual write','title заполнен','NULL=0 проверен'],('Данные','частично NULL','перенесены','Без drain новые NULL продолжали бы появляться.')),
          ('V3/V4','CHECK защищает новые строки и затем проверяет старые.','Flyway',['db','gate'],['observe'],['писать уже нельзя','v2/v3 допустимы','validated title','возврат v1 закрыт'],('Возврат','v1 возможен','v1 отвергает INSERT','Ограничение меняет совместимость до DROP.')),
          ('V6 contract','После всех v2 и принятого резерва удаляется body.','Flyway',['new','db'],['release'],['не допускается','только v3','только title','возврат v2 закрыт'],('Данные','два представления','старое удалено','Возврат binary не вернёт столбец/новые строки.')),
         ]),
    make('flyway-repair-boundary','flyway-14-baseline-repair','<h2>Undo — отдельная функция Teams</h2>',
         'Repair исправил history, но не partial_probe',
         'Нетранзакционный V7 успел выполнить CREATE и первый INSERT до duplicate key.',
         [('file','V7 SQL','Три statements'),('pg','PostgreSQL','Автопринятие'),('obj','partial_probe','Объект+строки'),('hist','History','V7 result')],
         [('exec','file','pg','SQL'),('data','pg','obj','изменение'),('result','pg','hist','сохранить факт'),('repair','file','hist','repair metadata')],
         [
          ('Начало без tx','executeInTransaction=false означает отсутствие общей атомарной границы.','Flyway',['file','pg'],['exec'],['CREATE,INSERT,INSERT','вне общей tx','отсутствует','нет V7'],('Граница','обычная tx','нет общей tx','Успех раннего statement может сохраниться.')),
          ('Часть SQL commit','Таблица и первая строка уже приняты сервером.','PostgreSQL',['obj'],['data'],['последний INSERT','первые commit','id=1','ещё нет результата'],('Объект','отсутствует','существует +1','Следующая ошибка не отменит прошлые commits.')),
          ('Duplicate key','Второй INSERT отказал; живое соединение позволяет зарегистрировать Failed.','PostgreSQL',['pg','hist'],['result'],['прерван','ошибка','id=1 остаётся','V7 Failed'],('Результат','неизвестен','Failed','При потере соединения даже этот факт мог не записаться.')),
          ('Repair','Команда удаляет failed-запись, не запуская обратный SQL.','Flyway',['hist'],['repair'],['тот же V7','не удаляет объект','id=1 остаётся','V7-записи нет'],('History','Failed','удалена failed','Миграция снова выглядит непринятой, данные не исправлены.')),
          ('Нужно решение','Перед повтором устанавливают допустимое согласование частичного результата.','Оператор',['obj','file'],[],['доработать/согласовать','ещё не повторяет','исследован','история сохранена'],('Допуск','repair exit0','отдельный план SQL','Слепой повтор CREATE TABLE снова упадёт.')),
         ]),
    make('flyway-backup-point','flyway-15-restore','<h2>Что произойдёт с новыми строками</h2>',
         'Новая цель принимает точку T, а не дальнейшие записи',
         'App и history попадают в один dump базы; роли/runtime/TLS сохраняются отдельно.',
         [('source','handbook','Исходная база'),('dump','Custom dump','Снимок T'),('target','handbook_restore','Другая цель'),('app','Go','Маршрут подключения')],
         [('backup','source','dump','pg_dump'),('restore','dump','target','pg_restore'),('newwrite','app','source','новая запись'),('switch','target','app','после сверки')],
         [
          ('Контрольная точка','На время учебной сверки писатели остановлены, строки и history согласованы.','Оператор',['source'],[],['1000 строк/V5','ещё нет','ещё нет','остановлен'],('Точка','живой поток','T','В реальном concurrent dump используется согласованный snapshot.')),
          ('Получен dump','Создан файл без владельцев/ACL; роли ещё вне него.','pg_dump',['dump'],['backup'],['1000/V5','1000/V5 в T','нет','не переключён'],('Резерв','нет файла','есть dump','Наличие файла ещё не означает принятую поставку.')),
          ('Восстановлено','Другой database получает объекты/history; права возвращаются явно.','pg_restore',['target'],['restore'],['не overwrite','сохранён','1000/V5','проверяет новую цель'],('Цель','не существует','восстановлена','Не затираем исходник при репетиции.')),
          ('После снимка','Исходник принимает новую строку, которой нет в старом dump.','Go',['source','app'],['newwrite'],['1001/V5','всё ещё1000','1000/V5','пишет в исходник'],('Данные','точка T','T+1 на исходнике','Старый dump не содержит будущую запись.')),
          ('Решение о переключении','Сверяют данные/history/ACL/версию и принимают судьбу T+1.','Оператор',['target','app'],['switch'],['сохранён','не изменён','принят T','только после решения'],('RPO','не определён','новые строки вне точки','Rollback binary не решает эту потерю.')),
         ]),
]
