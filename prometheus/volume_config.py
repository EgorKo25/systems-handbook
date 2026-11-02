"""Original independent Prometheus volume; integrator assigns the final number."""
CONFIG = dict(
    volume='XV',
    title='Prometheus и PromQL: измерение, вычисление и хранение',
    short='Prometheus',
    description='От установки и Go-инструментации до строгой семантики PromQL, TSDB, алертов и восстановления.',
    revision='1 ноября 2026',
    sections=[
        ('Начало', ['00-route']),
        ('Книга I · Измерение становится данными', ['prom-01-install', 'prom-02-model-and-time', 'prom-03-scrape-discovery', 'prom-04-tsdb', 'prom-05-instrumentation', 'prom-06-metric-types']),
        ('Книга II · Язык PromQL', ['prom-07-promql-types-selectors', 'prom-08-time-evaluation', 'prom-09-counters', 'prom-10-aggregation', 'prom-11-operators-matching', 'prom-12-missing-subqueries', 'prom-13-histogram-queries']),
        ('Книга III · Правила и эксплуатация', ['prom-14-rules', 'prom-15-slo', 'prom-16-capacity-diagnostics', 'prom-17-backup-upgrade', 'prom-18-ha-remote']),
        ('Сохраняемый практикум', ['prom-19-lab']),
        ('Источники и справочник', ['prom-20-sources', '99-glossary']),
    ],
    term_modules=['reference'],
    command_modules=['reference'],
    diagram_modules=['diagrams'],
    base_terms=[],
    blurb='HTTP и метрика → TSDB → PromQL с расчётами → правила → стоимость, восстановление и границы хранения.',
)
