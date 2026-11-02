"""Independent maintained Grafana volume; XXIII is provisional."""
CONFIG=dict(volume='XXIII',short='Grafana',title='Grafana: от вопроса к данным, графику и проверяемому сигналу',description='Установка и состояние, путь запроса панели, точность времени и единиц, provisioning, alerting, доступ и восстановление.',revision='2 ноября 2026',sections=[
 ('Начало',['00-route']),
 ('Книга I · Собственный экземпляр',['grafana-01-model','grafana-02-install','grafana-03-state','grafana-04-access-tls']),
 ('Книга II · От запроса к изображению',['grafana-05-query-path','grafana-06-time-step','grafana-07-samples','grafana-08-panels-units','grafana-09-transformations','grafana-10-variables-links']),
 ('Книга III · Сохраняемая доска',['grafana-11-provisioning','grafana-12-api-ownership']),
 ('Книга IV · Сигнал и доставка',['grafana-13-alert-evaluation','grafana-14-notifications']),
 ('Книга V · Доверие и эксплуатация',['grafana-15-security','grafana-16-plugins','grafana-17-performance','grafana-18-ha-backup-upgrade']),
 ('Продолжаемый практикум',['grafana-19-lab','grafana-20-sources']),('Справочник',['99-glossary'])],base_terms=[],term_modules=['reference'],command_modules=['reference'],diagram_modules=['diagrams'],blurb='Вопрос и установка → запрос и измерения → график и единицы → управляемая доска → alerting → безопасность, измерение и восстановление.')
