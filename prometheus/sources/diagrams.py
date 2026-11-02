"""Two offline state machines; sample/time graphs are inline in chapters 08 and 09."""


def step(title, explanation, actor, focus, active, states, field):
    name, before, after, why = field
    return dict(title=title, explanation=explanation, actor=actor, focus=focus,
                active=active, states=states,
                fields=[dict(name=name, before=before, after=after, why=why)],
                bands=[dict(label=name, value=after, detail=why)])


def diagram(identifier, chapter, title, intro, assumptions, nodes, edges, steps):
    return dict(id=identifier, volume='prometheus', chapter=chapter, anchor=chapter,
                title=title, intro=intro, assumptions=assumptions,
                nodes=[dict(id=i, label=l, sub=s) for i, l, s in nodes],
                edges=[dict(id=i, **{'from': a, 'to': b}, label=l) for i, a, b, l in edges],
                steps=steps)


DIAGRAMS = [diagram(
    'prom-metric-path', 'prom-04-tsdb', 'Один запрос становится sample, затем доступной историей',
    'Инициаторы и состояние меняются на каждой границе. Существование числа в Go не равно его сохранению в TSDB.',
    'Фиксированная модель обычного in-order float пути3.13.5: route=/work, counter41→42, scrape15s; ref17 условная. Нет OOO, exemplars и сетевого протокола remote storage. WAL flush не объявляется fsync каждого sample.',
    [('app','Go-сервис','Событие и counter'),('http','/metrics','HTTP exposition'),('scrape','Scraper','GET и parsing'),('head','Head','Appender, series, chunks'),('disk','WAL / blocks','Файлы TSDB'),('query','Query','Выборка на T')],
    [('event','app','http','читать counter'),('get','scrape','http','GET /metrics'),('response','http','scrape','body + Content-Type'),('append','scrape','head','labels, t, value'),('wal','head','disk','series/sample records'),('read','disk','query','index/chunks'),('recent','head','query','последние samples')],
    [step('Завершился /work','Обработчик увеличил counter с41 до42; HTTP-сбор ещё не происходил.','Go handler',['app'],[],{'app':'counter42','http':'ответ ещё нет','scrape':'ожидает interval','head':'старое41','disk':'старые данные','query':'42 пока недоступно'},('Место','counter41','counter42 в процессе','Увеличение памяти приложения не пишет TSDB.')),
     step('Scraper запросил endpoint','GET инициирует Prometheus; exporter читает collectors и сериализует ответ.','Scrape loop',['scrape','http'],['get','event','response'],{'app':'counter42','http':'sample без явного t','scrape':'парсер принял','head':'ещё41','disk':'без нового sample','query':'ещё прежнее'},('Сеть','нет нового ответа','body42 и корректный формат','Успех HTTP и append проверяются отдельно.')),
     step('Appender связал series','Labels определили идентичность; существующая ref17 ускорила lookup.','TSDB appender',['scrape','head'],['append'],{'app':'42','http':'ответ завершён','scrape':'append pending','head':'batch(ref17,t,42)','disk':'ещё прежний WAL','query':'pending не доказательство'},('Batch','нет нового','sample(ref17,t,42)','Новый label set потребовал бы создания series и postings.')),
     step('Commit прошёл журнал','WAL log записывает records, затем sample добавляется в chunk head.','Commit',['head','disk'],['wal'],{'app':'42','http':'готов к новому GET','scrape':'успех','head':'committed42','disk':'WAL sample42','query':'42 доступно'},('Состояние','batch pending','committed sample','Log error возвращает отказ; flush не обещает power-loss гарантию.')),
     step('Query выбрал историю','Selector получает refs из postings и samples из head/blocks на нужное T.','Query engine',['head','disk','query'],['recent','read'],{'app':'может уже43','http':'не участвует','scrape':'следующий interval','head':'42 при t','disk':'WAL, позже block','query':'42 на выбранное T'},('Время','новейшее состояние приложения','последний sample ≤T','Запрос не вызывает новый HTTP scrape.'))]
), diagram(
    'prom-histogram', 'prom-13-histogram-queries', 'Cumulative buckets теряют положение внутри интервала',
    'Сначала считаем наблюдения, затем находим ранг и интерполируем значение.',
    'Четыре заданные длительности0.04,0.08,0.24,0.7s. Classic buckets0.1,0.3,1,+Inf. Это фиксированная модель линейной интерполяции, не native exponential layout.',
    [('events','Наблюдения','Четыре durations'),('buckets','Buckets','Cumulative counts'),('rank','Ранг','φ×N'),('interval','Интервал','Границы и count'),('estimate','Оценка','p90≈0.72s')],
    [('observe','events','buckets','увеличить все подходящие'),('find','buckets','rank','N=4,φ=.9'),('locate','rank','interval','3<3.6≤4'),('interpolate','interval','estimate','линейное предположение')],
    [step('Наблюдения обновили buckets','Каждое значение попадает во все cumulative buckets с подходящей верхней границей.','Go Observe',['events','buckets'],['observe'],{'events':'.04,.08,.24,.7s','buckets':'2,3,4,4','rank':'нет','interval':'нет','estimate':'нет'},('Count','0','4 observations','Нельзя сложить cumulative counts2+3+4+4 как13 событий.')),
     step('Вычислен ранг3.6','0.9×4=3.6 лежит после первых3 и до4 наблюдений.','histogram_quantile',['rank','interval'],['find','locate'],{'events':'точные места забыты','buckets':'0.3→3;1→4','rank':'3.6','interval':'(0.3,1]','estimate':'впереди'},('Выбор','все buckets','корзина(0.3,1]','Это не значение существующего sample.')),
     step('Интерполяция дала0.72','0.3+(1−0.3)×(3.6−3)/(4−3)=0.72s.','Classic interpolation',['interval','estimate'],['interpolate'],{'events':'фактический максимум.7','buckets':'не знают точное место','rank':'3.6','interval':'доля.6','estimate':'.72s'},('Точность','известны границы','оценка внутри','Четыре наблюдения не делают устойчивый p99.')),
     step('Выбор детализации имеет цену','Граница0.3 позволяет точно считать долю≤0.3; дополнительные classic buckets создают series.','Автор instrumentation',['buckets','estimate'],[],{'events':'тот же traffic','buckets':'B+3 series наlabel set','rank':'зависит отN','interval':'точность ограничена','estimate':'проверять count рядом'},('Компромисс','больше деталей','больше CPU/network/storage','Native sample меняет layout, а не создаёт бесконечную точность бесплатно.'))]
)]
