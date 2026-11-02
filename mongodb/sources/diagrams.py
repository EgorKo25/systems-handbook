"""Original bounded teaching scenarios, never a MongoDB simulator or packet capture."""
def make(identifier,chapter,marker,title,intro,nodes,edges,rows):
 keys=[x[0] for x in nodes];steps=[]
 for caption,explanation,actor,focus,active,values,field in rows:
  name,before,after,why=field
  assert len(keys)==len(values)
  steps.append(dict(title=caption,explanation=explanation,actor=actor,focus=focus,active=active,
   states=dict(zip(keys,values)),fields=[dict(name=name,before=before,after=after,why=why)],
   bands=[dict(label=name,value=after,detail=why)]))
 return dict(id=identifier,volume='mongodb',chapter=chapter,anchor=chapter,insert_before=marker,title=title,intro=intro,
  assumptions='Оригинальная пошаговая модель с условными ID. Это не запущенный сервер и не снятый сетевой trace. Не моделируются все ошибки/планировщики/версии; каждый шаг имеет текстовое объяснение и таблицу для печати.',
  nodes=[dict(id=k,label=l,sub=s) for k,l,s in nodes],edges=[dict(id=k,**{'from':a,'to':b},label=l) for k,a,b,l in edges],steps=steps)
DIAGRAMS=[
make('mongodb-durable-path','mongodb-storage','<h2>Границы сохранности и наблюдение</h2>','Память, journal и checkpoint','Отдельные состояния не схлопываются в слово «сохранено». Модель одной локальной записи; не моделирует питание диска.',
 [('cmd','Команда','Update документа'),('cache','Cache','Версии и страницы'),('journal','Journal','WiredTiger WAL'),('disk','Checkpoint','Согласованные файлы'),('ack','Ответ','Выбранный concern')],
 [('modify','cmd','cache','изменить'),('log','cache','journal','write-ahead'),('sync','journal','ack','j подтверждён'),('cp','cache','disk','новая точка'),('recover','journal','disk','replay после аварии')],
 [('До записи','Согласованная точка C10 и старые версии остаются исходным состоянием.','WiredTiger',['disk'],[],['ожидает','v1','до X','C10','нет'],('Версия','v1','v1','Изменение ещё не подготовлено.')),
 ('Изменение в cache','Документ и индексные изменения согласованы внутри engine; видимость зависит от операции/concern.','WiredTiger',['cmd','cache'],['modify'],['X','v2 dirty','буфер X','C10','ждёт'],('Память','v1','v2','Dirty не значит устойчивый checkpoint.')),
 ('Journal синхронизирован','Запись X устойчива по договору storage; j:true может завершить локальную часть ожидания до следующего checkpoint.','Journal',['journal','ack'],['log','sync'],['X','v2','X durable','C10','локальный j выполнен'],('Устойчивость','X в буфере','X на journal','Это ещё не majority другой topology.')),
 ('Новый checkpoint','После согласованного построения метаданные переключают C10 на C11; прежняя точка была пригодна до переключения.','Checkpoint',['cache','disk'],['cp'],['окончен','версии по нужде','может переиспользоваться','C11','уже мог быть отдан'],('Файлы','C10','C11','Ответ не обязан ждать именно этого события.')),
 ('Авария между точками','Если C11 не завершён, recovery использует C10 и устойчивую часть journal. Это не повтор HTTP с новым ID.','Recovery',['journal','disk'],['recover'],['после рестарта','восстанавливается','replay X','C10 + X','старый клиент мог потерять ответ'],('Recovery','C10','C10+X','Материал восстановления — внутренние записи, не исходный бизнес-вызов.'))]),
make('mongodb-repl-path','mongodb-replication','<h2>Почему два недоступных узла нельзя заменить воображаемым большинством</h2>','Передача истории и majority в8.0','Три data-bearing голосующих участника PSS; majority count=2. Это модель, авторский native стенд имеет одного участника.',
 [('client','Клиент','w:majority,j:true'),('a','A primary','Принимает запись'),('b','B secondary','Копирует/applies'),('c','C secondary','Копирует/applies'),('commit','Commit point','Граница истории')],
 [('write','client','a','X'),('repb','a','b','oplog X'),('repc','a','c','oplog X'),('ackb','b','commit','durable X'),('acka','a','commit','durable X'),('reply','commit','client','подтверждение')],
 [('До X','У всех есть история до10.','Set',['a','b','c'],[],['ждёт','10','10','10','10'],('История','10','10','Новая запись ещё не принята.')),
 ('Primary принял X','Локальное изменение и oplog11 подготовлены; одного A недостаточно для majority PSS.','A',['a'],['write'],['ждёт','11 durable','10','10','10'],('Порог','0/2','1/2','Нужен ещё один data-bearing участник.')),
 ('B устойчиво получил oplog','В8.0 durable oplog на B участвует в подтверждении; применение к коллекции может отставать.','B',['b','commit'],['repb','ackb','acka'],['ждёт','11 durable','11 durable, apply10','10','11'],('Commit','10','11','Это не обещание немедленной свежести произвольного secondary read.')),
 ('Ответ majority','Условие большинства выполнено; C ещё отстаёт.','Set',['client','commit'],['reply'],['X accepted','11','11 apply10','10','11'],('Клиент','неизвестно','majority accepted','Возвращённый ответ не значит all replicas applied.')),
 ('Применение догнало','B и C применяют историю, C сначала её получает; при долгом отставании важно окно oplog.','Secondaries',['b','c'],['repc'],['завершён','11','11 applied','11 applied','11'],('Копии','разные стадии','все applied11','Lag измеряется с указанием стадии и времени.'))]),
make('mongodb-election-path','mongodb-replication','<h2>Rollback и судьба принятого w:1</h2>','Раздел1+2 и новая эпоха','Три голоса; стороне B+C нужны два. Не моделируются все условия пригодности кандидата, catch-up и сетевые таймеры.',
 [('a','A','Бывший primary'),('b','B','Кандидат'),('c','C','Голосующий'),('epoch','Term','Эпоха'),('app','Клиент','Server selection')],
 [('partition','a','b','связь потеряна'),('vote','c','b','голос'),('term','b','epoch','новая эпоха'),('retry','app','b','после discovery'),('join','a','b','вернулся')],
 [('До раздела','A ведёт epoch7, B/C копируют.','Set',['a','b','c'],[],['primary t7','secondary t7','secondary t7','7','пишет A'],('Кворум','3 доступны','3 доступны','Лидер имеет связь с большинством.')),
 ('Сеть1+2','A не может получать большинство; пока новый допустимый primary не выбран, клиент ждёт/получает ошибку.','Network',['a','b','c','app'],['partition'],['изолирован','видит C','видит B','7','нет допустимого primary'],('Доступность','записи принимаются','окно недоступности','Не лечится слепым выбором любого живого узла.')),
 ('Новая эпоха','Пригодный B получает свой голос и голос C:2/3; A не может получить такой quorum.','B',['b','c','epoch'],['vote','term'],['старое лидерство прекращено','primary t8','secondary t8','8','обнаруживает B'],('Term','7','8','Эпоха отличает старое лидерство от нового.')),
 ('Клиент выбрал B','Discovery и поддержанный retry позволяют продолжить; исход прежней записи может требовать сверкиID.','Driver',['app','b'],['retry'],['вне большинства','primary t8','secondary t8','8','пишет B'],('Операция','неизвестный исход','сверка/повтор по договору','Новый ID сделал бы новую прикладную запись.')),
 ('A присоединился','Расходящаяся w:1 ветка не сливается автоматически; A согласует общую историю с B.','A',['a','b'],['join'],['rollback/catch-up','primary t8','secondary t8','8','работает с принятой историей'],('История','возможен X лишь на A','общая ветка B','Локальный journal не предотвращает rollback сетевой ветки.'))]),
]
