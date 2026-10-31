"""Refresh book reports from current generated files and actual test reports."""
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,s):p.write_text(s.strip()+'\n',encoding='utf-8')
stats=read(HERE/'book-stats.json')
browser=read(ROOT/'checks/cache-browser.json')
static=read(ROOT/'checks/cache-static.json')
art=read(ROOT/'checks/cache-artwork.json')
reports={name:read(HERE/'labs'/file) for name,file in {
    'basic':'live-results.json','advanced':'advanced-results.json',
    'redis_semantics':'redis-semantics-results.json',
    'memcached_semantics':'memcached-semantics-results.json',
    'persistence':'persistence-results.json'}.items()}
for report in [browser,static,art,*reports.values()]:assert report['status']=='PASS'
digest=hashlib.sha256((HERE/'index.html').read_bytes()).hexdigest()
assert browser['book_sha256']==static['book_sha256']==digest, 'Checks refer to a different build'
assert browser['chapters']==len(stats)
terms=sum(bool(line.strip()) for line in (HERE/'sources/glossary.tsv').read_text(encoding='utf-8').splitlines())
words=sum(x['words'] for x in stats)
counts={name:len(report['cases']) for name,report in reports.items()}
total_cases=sum(counts.values())
illustrations=len(art['assets'])
eviction=read(HERE/'labs/eviction-results.json')
resources=read(HERE/'labs/resource-results.json')
assert eviction['status']==resources['status']=='PASS'
write(HERE/'ПРОВЕРКИ.txt',f'''
Том V — проверенная редакция 31 октября 2026

{len(stats)} глав с вводной и словарём; {words} слов; {terms} терминов.
Три части: Кэширование / Redis / Memcached.
{illustrations} авторских SVG; четыре пошаговые схемы с 24 шагами;
временная диаграмма репликации — три сценария по семь шагов;
тренажёр вытеснения, калькулятор нагрузки, расчёт границ TTL
и интерактивная модель памяти slab-класса.

PASS — {static['links']} локальных ссылок, {static['anchors']} якорей, общий словарь пяти томов.
PASS — Chrome через file://, все {len(stats)} глав на ширинах 1440 и 390:
навигация, изображения, таблицы, отсутствие переполнения страницы,
{browser['diagramStates']} состояний пошаговых схем, три сценария репликации,
пять политик вытеснения, TTL/память, калькулятор, поиск, карточки,
заметки, темы, меню и печать. Нет ошибок JS и внешних активных запросов.
Проверки привязаны к SHA256 текущей сборки: {digest}.
PASS — границы текста {illustrations} SVG; снимки checks/cache-art-*.png.
PASS — {eviction['cases']} проверок моделей вытеснения и {resources['cases']}
проверок расчётов TTL/памяти. Это арифметика моделей, не benchmark.

Реальные серверы: {total_cases} проверок суммарно:
  {counts['basic']} — базовые команды обоих продуктов;
  {counts['advanced']} — ACL, mTLS, WAIT, Sentinel и Redis Cluster;
  {counts['redis_semantics']} — транзакции, WATCH, списки, Streams и ротация ACL;
  {counts['memcached_semantics']} — байтовые кадры, CAS, TTL, multiget и счётчики;
  {counts['persistence']} — RDB/AOF и восстановление после переписывания AOF.
Проверенные версии: Redis 6.0.16, Memcached 1.6.14, Ubuntu 22.04 / WSL.
Это версии опытов, а не рекомендация для нового развёртывания.
Стенды запускают свои временные процессы на loopback.
Команды, требования и отчёты: labs/README.txt, labs/*-results.json.

При редакционной проверке исправлены: общие главы в чужой части,
необъяснённые расчёты и короткие эксплуатационные описания, повреждённый
текст, cmd_get при multiget, неполная проверка переписанного AOF,
область прав ACL, путь к proxy-бинарнику и пересекающиеся порты.

Границы: production benchmark, потеря питания, сетевой раздел,
Memcached SASL и современный встроенный proxy не выполнялись.
TLS и кластер проверены отдельно, не как одна защищённая топология.
Возврат прежнего узла после Sentinel и клиентский RTO не измерялись.
Учебные расчёты и рисунки не выдаются за измерения производительности.
Успешные проверки не означают независимую экспертизу каждого утверждения.
''')
readme=(HERE/'README.txt').read_text(encoding='utf-8')
readme=re.sub(r'\d+ глав вместе с вводной и словарём;.*',f'{len(stats)} глав вместе с вводной и словарём; {words:,} слов; {terms} терминов.'.replace(',',' '),readme)
readme=re.sub(r'… \d+-\*\.html','… 38-*.html',readme)
readme=re.sub(r'\(\d+ локальных SVG\)',f'({illustrations} локальных SVG)',readme)
if 'Границы TTL и память slab-класса:' not in readme:
    readme=readme.replace('Калькулятор: calculator.js; тренажёр вытеснения: eviction.js.',
        'Калькулятор: calculator.js; тренажёр вытеснения: eviction.js.\nГраницы TTL и память slab-класса: resource-labs.js.')
write(HERE/'README.txt',readme)
def replace_section(path,heading,body):
    text=path.read_text(encoding='utf-8')
    prefix=text.split('\n'+heading,1)[0].rstrip()
    write(path,prefix+'\n\n'+body)
replace_section(ROOT/'КАК-ЧИТАТЬ.txt','Том V:',f'''Том V: Кэш и базы в памяти
Откройте cache/index.html. Три части: Кэширование, Redis, Memcached.
{len(stats)} глав; {terms} терминов; {illustrations} иллюстраций.
Общие расчёты, распределение, испытания и внедрение находятся в теории.
Каждое продуктовое руководство заканчивается собственным практикумом.
Тренажёр сравнивает FIFO, LRU, LFU, CLOCK и OPT на своей трассе.
Дополнительные модели показывают границы TTL и состав slab-блоков.
Команды Bash и серверов доступны в словаре; серверы в браузере не запускаются.
Для переноса копируйте всю библиотеку, включая cache/assets/.
Проверки и их границы: cache/ПРОВЕРКИ.txt.''')
replace_section(ROOT/'ПРОВЕРКИ-БИБЛИОТЕКИ.txt','Обновление 31 октября 2026 — том V',f'''Обновление 31 октября 2026 — том V
Три части, {len(stats)} глав, {terms} терминов; общий словарь обновлён в пяти томах.
Подробные результаты: cache/ПРОВЕРКИ.txt и checks/cache-*.json.
{total_cases} реальных серверных проверок: базовая семантика, ACL, mTLS,
Sentinel, Redis Cluster, отдельные протоколы и RDB/AOF-восстановление.
SASL, современный proxy, сетевые разделы и потеря питания не исполнялись.
Исторические результаты предыдущих томов выше не являются новым прогоном.
SHA256SUMS обновлён для текущих файлов библиотеки.''')
delivery=dict(status='PASS',date='2026-10-31',volume='cache',book_sha256=digest,
 parts=3,chapters=len(stats),words=words,terms=terms,illustrations=illustrations,
 step_diagrams=4,steps=24,replication_scenarios=3,replication_steps=21,
 eviction_policies=5,interactive_calculators=['load','TTL bounds','slab memory'],
 live_cases=counts,total_live_cases=total_cases,browser_states=browser['diagramStates'],
 limits=reports['advanced']['limits']+reports['persistence']['limits'],
 manifest='SHA256SUMS excludes IDE/Git metadata, Python bytecode and itself')
write(ROOT/'checks/cache-delivery.json',json.dumps(delivery,ensure_ascii=False,indent=2))
paths=sorted(p for p in ROOT.rglob('*') if p.is_file()
             and not any(x in {'.git','.idea','__pycache__'} for x in p.relative_to(ROOT).parts)
             and p.name!='SHA256SUMS' and p.suffix!='.pyc')
write(ROOT/'SHA256SUMS','\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(ROOT).as_posix() for p in paths))
print(json.dumps({'delivery':'PASS','manifest_files':len(paths),'words':words,'terms':terms,'live_cases':total_cases}))
