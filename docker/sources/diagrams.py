"""Original stepped models. No calls to a daemon, no claims of live execution."""
def step(title, text, actor, focus, edges, states, field):
    name,before,after,why=field
    return dict(title=title,explanation=text,actor=actor,focus=focus,active=edges,states=states,
                fields=[dict(name=name,before=before,after=after,why=why)],
                bands=[dict(label=name,value=after,detail=why)])
def diagram(identifier,chapter,title,intro,assumptions,nodes,edges,steps,marker):
    return dict(id=identifier,volume='docker',chapter=chapter,anchor=chapter,title=title,intro=intro,
                assumptions=assumptions,insert_before=marker,
                nodes=[dict(id=i,label=l,sub=s) for i,l,s in nodes],
                edges=[dict(id=i,**{'from':a,'to':b},label=l) for i,a,b,l in edges],steps=steps)
DIAGRAMS=[



 diagram('docker-compose-health','11-compose-lifecycle','Running, healthy и готовая запись не совпадают',
 'Один сервис проходит нормальную работу, отказ записи и явную остановку. Разделите признаки управления и приложения.',
 'Условная последовательность; времени точного планировщика здесь нет. Healthcheck проверяет только /health, а counter использует отдельный volume. Restart policy unless-stopped; ручной stop преднамеренный.',
 [('model','Compose','Проверенный файл'),('engine','Engine','Объект контейнера'),('process','Go','Работающий процесс'),('probe','Health','GET/health'),('data','Данные','POST/counter'),('operator','Оператор','Приёмка')],
 [('up','model','engine','up'),('start','engine','process','запустить'),('test','probe','process','локальный запрос'),('write','process','data','запись'),('check','probe','operator','ограниченный признак'),('stop','operator','engine','ручной stop')],
 [step('Config проверен','Итоговая конфигурация известна; это ещё описание будущих ресурсов.','Compose',['model'],[],{'model':'нормализован','engine':'ещё не создан','process':'нет','probe':'не запускалась','data':'том сохранён','operator':'проверяет входы'},('Доказательство','YAML','модель принята','Разбор конфигурации не запускает приложение.')),
  step('Go работает','Engine создал и запустил задачу. Приложение ещё не прошло ни одной предусмотренной проверки.','Engine',['engine','process'],['up','start'],{'model':'применена','engine':'running','process':'слушает 8080','probe':'starting','data':'доступ проверяется','operator':'ждёт'},('Состояние','created','running','Running описывает задачу, а не все функции.')),
  step('Health прошёл','Команда /echo check получила 200. Этот признак не обращался к counter.','Probe',['probe'],['test','check'],{'model':'та же','engine':'running','process':'ответил health','probe':'healthy','data':'запись не проверена','operator':'ограниченный признак'},('Проверка','starting','healthy','Состав probe определяет силу вывода.')),
  step('Запись получила отказ','Неправильные права или ошибка диска дали 503 у counter; процесс и /health остаются живыми.','Go',['data','process'],['write'],{'model':'та же','engine':'running','process':'обслуживает HTTP','probe':'healthy','data':'POST503','operator':'фиксирует ошибку'},('Функция','ожидается запись','отказ записи','Healthy не доказывает готовность конкретной операции.')),
  step('Оператор остановил сервис','Штатный stop запрашивает завершение; unless-stopped не обязан немедленно отменять осознанную остановку. Данные остаются.','Оператор',['operator','engine'],['stop'],{'model':'сохранена','engine':'stopped','process':'закончился','probe':'нет новых','data':'volume на месте','operator':'исследует права'},('Жизненный цикл','running','остановлен вручную','Исправление причины выполняется в том же мире.'))],
 '<h2>Restart не равен ремонту</h2>'),

]
