"""Original standalone MongoDB volume; publication remains a separate decision."""
CONFIG = dict(
 volume='XXI', short='MongoDB',
 title='MongoDB: документ, путь запроса и границы сохранности',
 description='От официальной поставки и первого документа до BSON, Go-драйвера, WiredTiger, согласования, репликации и восстановления.',
 revision='2 ноября 2026',
 sections=[
 ('Начало', ['00-route']),
 ('Книга I · Свой экземпляр и данные', ['mongodb-model','mongodb-install','mongodb-access','mongodb-bson','mongodb-crud']),
 ('Книга II · Как выполняется запрос', ['mongodb-driver-wire','mongodb-storage','mongodb-query-index','mongodb-aggregation']),
 ('Книга III · Сохранность и распределение', ['mongodb-concerns','mongodb-transactions','mongodb-replication','mongodb-sharding']),
 ('Книга IV · Работающий Go-сервис', ['mongodb-service','mongodb-backup-upgrade','mongodb-measure']),
 ('Справочник', ['mongodb-sources','99-glossary'])],
 base_terms=[], term_modules=['reference'], command_modules=['reference'],diagram_modules=['diagrams'],
 blurb='Документ → официальный экземпляр → Go и BSON → OP_MSG → WiredTiger → согласование → репликация → восстановление.',
)
