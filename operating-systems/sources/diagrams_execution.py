"""Execution stories from the same checked original states as the browser model."""
import json
from pathlib import Path

_DATA = json.loads((Path(__file__).resolve().parents[1]/'labs/execution/traces.json').read_text())


def make(identifier, chapter, marker, title, intro, assumptions, nodes, edges, rows):
    keys = [n[0] for n in nodes]
    steps=[]
    for caption, explanation, actor, focus, active, values, fields in rows:
        assert len(keys)==len(values)
        steps.append(dict(title=caption,explanation=explanation,actor=actor,focus=focus,
                          active=active,states=dict(zip(keys,values)),
                          fields=[dict(name=n,before=b,after=a,why=w) for n,b,a,w in fields],
                          bands=[dict(label=n,value=a,detail=w) for n,b,a,w in fields]))
    return dict(id=identifier,volume='operating-systems',chapter=chapter,anchor=chapter,
                insert_before=marker,title=title,intro=intro,assumptions=assumptions,
                nodes=[dict(id=k,label=l,sub=s) for k,l,s in nodes],
                edges=[dict(id=k,**{'from':a,'to':b},label=l) for k,a,b,l in edges],steps=steps)


def boundary(name, chapter, marker, identifier, title, subset=None):
    states=_DATA['boundary'][name]
    if subset is not None: states=states[subset[0]:subset[1]]
    rows=[]
    for i,s in enumerate(states):
        previous=states[max(0,i-1)]
        if s['mode']=='ядро/IRQ':focus=['cpu','kernel','device'];active=['irq']
        elif s['mode']=='ядро':focus=['cpu','kernel','saved'];active=['enter'] if previous['mode']=='пользователь' else []
        else:focus=['cpu','user'];active=['return'] if previous['mode'].startswith('ядро') else []
        if s['offset']!=previous['offset']:focus+=['file','buffer'];active+=['read']
        saved=s.get('savedUser')
        saved_text=(saved['owner']+'; UPC '+saved['pc']+'; USP '+saved['sp']) if saved else 'пока нет кадра входа'
        if s.get('savedKernel'):saved_text+='; KPC '+s['savedKernel']['pc']+'; KSP '+s['savedKernel']['sp']
        if s.get('irqFrame'):saved_text+='; отдельный кадр IRQ '+s['irqFrame']['thread']
        values=[s['thread']+' / '+s['process']+' / '+s['addressSpace']+' / '+s['mode'],
                'PC '+s['pc']+'; SP '+s['sp'],saved_text,
                'Открытие 3: позиция '+str(s['offset']),
                ' '.join(f'{b:02x}' for b in s['buffer']) or 'ещё не заполнен',
                ('J17 завершена; IRQ учтён' if s.get('irqFrame') else 'J17 ожидается' if s.get('savedKernel') else 'J17 не запрашивалась'),
                'T1 '+s['threads']['T1']+'; T2 '+s['threads']['T2']]
        fields=[('Текущее продолжение',previous['pc']+' / '+previous['sp'],s['pc']+' / '+s['sp'],s['explanation']),
                ('Исполнитель и режим',previous['thread']+' / '+previous['mode'],s['thread']+' / '+s['mode'],'Смена режима и смена потока учитываются отдельно.'),
                ('Переключений потоков',str(previous['switches']),str(s['switches']),'Считаются T1↔T2; вход/выход того же потока не увеличивает число.')]
        rows.append((s['title'],s['explanation'],s['thread']+' на '+s['cpu'],focus,active,values,fields))
    return make(identifier,chapter,marker,title,
        'Выберите шаг и сопоставьте текущие PC/SP/режим с отдельно сохранёнными продолжениями. Все значения — модельные состояния.',
        'Учебный 32-разрядный ABI с именованными полями; не x86/Linux ABI. CALL сохраняет четырёхбайтовый возврат. Общая защищённая область ядра и отдельные стеки T1/T2; без изоляции отображений ядра при входе/выходе. Буфер '+ '0x00403124, известный PFN 0x12A; файл counter.bin, чтение 4 байт с позиции 0. Не исчерпывающий машинный трассировщик.',
        [('user','Кто исполняется','Поток/процесс/адресная среда'),('cpu','CPU0','Текущие PC и SP'),
         ('saved','Сохранённое состояние','Кадры разных владельцев'),('file','Открытие 3','Последовательная позиция'),
         ('buffer','Буфер T1','Четыре байта'),('device','Завершение ввода','Связь с J17'),('ready','Потоки','Ожидание и готовность')],
        [('enter','user','kernel','вход'),('return','kernel','user','возврат'),('read','file','buffer','передать байты'),('irq','device','kernel','завершение J17')],
        # The labels kernel in edges are mapped to the cpu node below.
        rows)


DIAGRAMS=[]
for spec in [
    ('cached','os-05-syscalls-exceptions','<h2 id="os-entry-blocked">','os-exec-cached-call','Функция → ядро → функция: тот же поток'),
    ('blocked','os-05-syscalls-exceptions','<h2 id="os-entry-result">','os-exec-blocked-call','Ожидание T1, IRQ в T2 и возврат к T1'),
    ('fault','os-05-syscalls-exceptions','<h2 id="os-entry-interrupt">','os-exec-fault-return','Исправленное исключение возвращает повторяемый PC'),
    ('blocked','os-07-context-switch','<h2 id="os-switch-cost">','os-exec-kernel-continuation','Что хранит T1, пока CPU исполняет T2',(4,10)),
]:
    kind,chapter,marker,identifier,title,*subset=spec
    d=boundary(kind,chapter,marker,identifier,title,subset[0] if subset else None)
    # There is one CPU execution node. The user/kernel labels express its mode,
    # rather than inventing a second CPU or separate mandatory kernel process.
    for edge in d['edges']:
        if edge['from']=='kernel':edge['from']='cpu'
        if edge['to']=='kernel':edge['to']='cpu'
    for step in d['steps']:
        step['focus']=[('cpu' if x=='kernel' else x) for x in step['focus']]
        step['focus']=list(dict.fromkeys(step['focus']))
    DIAGRAMS.append(d)

rows=[]
for s in _DATA['lifecycle']['none']:
    values=[s['parent'],', '.join(s['privateObjects']) or 'частных объектов нет',
            (s['child'] or 'ещё нет')+'; '+s['stage'],s['image'] or 'не загружен',
            str(s['result']) if s['result'] is not None else 'результата нет']
    rows.append((s['title'],s['explanation'],('P1' if s['stage'] in ['исполняется','завершён, результат ждёт'] else 'P0 / операция создания'),['creation','child'],(['publish'] if s['stage']=='готов' else ['load'] if s['stage']=='исполняется' else ['wait'] if s['stage']=='результат получен' else ['create'] if s['stage']=='подготовка' else []),values,
                 [('Владение','частная подготовка',', '.join(s['publicObjects']) or 'публичных удержаний нет',s['explanation'])]))
DIAGRAMS.append(make('os-exec-process-lifetime','os-06-process-lifecycle','<h2 id="os-life-multithreaded-create">',
 'Один ребёнок: создание, замена образа и получение результата',
 'Проверьте, когда появляется P1 и почему замена программы не создаёт P2.',
 'Объяснительная Unix-подобная модель; точный интерфейс Windows имеет другой договор создания/ожидания.',
 [('parent','P0','Создатель'),('creation','Операция создания','Частные объекты'),('child','P1/T1','Жизненный цикл'),('image','Образ','Команды и данные'),('result','Результат','Получается отдельно')],
 [('create','parent','creation','подготовить'),('publish','creation','child','опубликовать'),('load','image','child','загрузить'),('wait','child','result','завершить и получить')],rows))

rows=[]
for row in _DATA['scheduling']['rr']['timeline']:
    state=row['after'];values=[' → '.join(row['ready']) or 'пусто',row['running'] or 'простой']+[f"CPU={state[j]['cpu']}; очередь={state[j]['readyWait']}; "+state[j]['status'] for j in ['A','B','C']]
    rows.append((f"[{row['time']},{row['end']}) мс",'; '.join(row['events']) or 'Продолжает прежний выбор.',
                 'Планировщик и '+str(row['running']),['queue','cpu'],[],values,
                 [('Работа на интервале',str(row['time']),str(row['end']),row['running'] or 'CPU не получил полезной работы.'),('Готовые','входы в данном моменте',' → '.join(row['ready']) or 'нет','Выполняющийся поток не является элементом этой очереди.')]))
DIAGRAMS.append(make('os-exec-rr-queue','os-08-scheduling','<h2 id="os-sched-fairness">',
 'Очередь RR по каждому миллисекундному интервалу',
 'Короткая работа получает шанс раньше, а полное завершение A отодвигается. Сопоставьте счётчики CPU и ожидания.',
 'Один CPU; A поступает в 0 и требует 8 мс; B — в 1 с потребностью 2 мс; C — в 2 с потребностью 1 мс. Квант 2 мс, затраты управления 0. Поступления раньше вставки исчерпавшей квант работы. Выбранная работа и очередь показаны для начала интервала; счётчики и состояния A/B/C — после его конца. Это не симулятор Linux.',
 [('queue','Готовые','Оставшиеся после выбора в начале интервала'),('cpu','CPU','Выбранная работа'),('A','A','Счётчики к концу интервала; нужно 8 мс'),('B','B','К концу интервала; нужно 2 мс'),('C','C','К концу интервала; нужно 1 мс')],
 [('take','queue','cpu','выбрать'),('a','cpu','A','учесть A'),('b','cpu','B','учесть B'),('c','cpu','C','учесть C')],rows))

rows=[]
for s in _DATA['service']['normal']:
    values=[s['process'],'да' if s['ready'] else 'нет','принимает' if s['accepting'] else 'закрыт',str(s['inflight']),'подтверждена' if s['durable'] else 'ещё не обещана']
    rows.append((s['title'],s['explanation'],'Менеджер/служба/хранение',['process','ready','work'],[],values,
                 [('Готовность', 'состояние процесса','да' if s['ready'] else 'нет', 'Существование процесса не заменяет договор обслуживания.'),('Сохранность','видимые байты','да' if s['durable'] else 'не подтверждена','Только условно успешный поддерживаемый sync/flush устанавливает выбранную точку.')]))
DIAGRAMS.append(make('os-exec-service-stop','os-29-boot-services-shutdown','<h2 id="os-boot-restart">',
 'Снять готовность раньше завершения старой работы',
 'Процесс, приём и сохранность меняются в разные моменты.',
 'Модель одной службы; старых запросов 2. Синхронизация успешна при явно исправном поддерживаемом пути. Не запускает менеджер служб хоста.',
 [('process','Процесс','Существует/работает/завершён'),('ready','Готовность','Прикладной договор'),('input','Новый вход','Приём запросов'),('work','Активная работа','Неоконченные обязательства'),('storage','Сохранность','Точка подтверждения')],
 [('start','process','ready','инициализировать'),('accept','ready','input','открыть'),('drain','input','work','прекратить приём'),('sync','work','storage','закончить и сохранить')],rows))

DIAGRAMS.append(make('os-exec-time-boundaries','os-30-cpu-observation','<h2 id="os-cpu-queue-law">',
 'Один запрос: 10 мс прошедшего времени, 2 CPU-мс',
 'Выберите интервал и проверьте, какой счётчик растёт и какую причину он различает.',
 'Один последовательный путь без перекрытия. Точки 0/2/3/8/9/10 мс заданы условием; не измерены на машине.',
 [('ready1','Очередь CPU','0–2 мс'),('run1','Исполнение','2–3 мс'),('io','Внешнее ожидание','3–8 мс'),('ready2','Готов после ввода','8–9 мс'),('run2','Завершение','9–10 мс')],
 [('a','ready1','run1','выдан CPU'),('b','run1','io','нужен ввод'),('c','io','ready2','событие готово'),('d','ready2','run2','снова выдан CPU')],
 [
 ('0→2','Готовый поток ждёт CPU.','Планировщик',['ready1'],[],['2 мс очереди','0','0','0','0'],[('Учёт','прошло 0 мс / CPU 0 мс','прошло 2 мс / CPU 0 мс','Ожидание CPU не является исполнением.')]),
 ('2→3','Полезное исполнение одной миллисекунды.','T1',['run1'],['a'],['2','1 мс CPU','0','0','0'],[('Учёт','прошло 2 мс / CPU 0 мс','прошло 3 мс / CPU 1 мс','Началась CPU-работа.')]),
 ('3→8','Поток ждёт внешнее событие.','Операция ввода',['io'],['b'],['2','1','5 мс ожидания','0','0'],[('Учёт','прошло 3 мс / CPU 1 мс','прошло 8 мс / CPU 1 мс','CPU-время T1 здесь не прибавляет 5 мс.')]),
 ('8→9','Событие завершено, но CPU пока не выделен.','Планировщик',['ready2'],['c'],['2','1','5','1 мс очереди','0'],[('Очередь','внешнее ожидание','готовое ожидание','Причина задержки изменилась, хотя поток ещё не исполняется.')]),
 ('9→10','Поток заканчивает результат.','T1',['run2'],['d'],['2','1','5','1','1 мс CPU'],[('Итог','промежуточные длительности','10 мс = 3 мс очереди + 5 мс ввода + 2 мс CPU','Сумма проверяет заданную последовательную модель.')]),
 ]))
