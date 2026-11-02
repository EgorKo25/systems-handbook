"""Independent Vault volume; publication is a separate coordinator decision."""
CONFIG = dict(
    volume='XXII', short='Vault',
    title='HashiCorp Vault: от доверенной поставки до отзыва и восстановления',
    description='Сохраняемый TLS/Raft-сервер, ключи, путь запроса, ACL, KV, leases, AppRole, PostgreSQL, PKI, Agent, Go, аудит и восстановление.',
    revision='2 ноября 2026',
    sections=[
        ('Начало', ['00-route']),
        ('Книга I · Свой экземпляр и доверие', ['vault-01-model','vault-02-supply','vault-03-server','vault-04-keys']),
        ('Книга II · Запрос и полномочия', ['vault-05-request','vault-06-acl','vault-07-kv','vault-08-leases','vault-09-auth']),
        ('Книга III · Секрет у приложения', ['vault-10-postgresql','vault-11-pki','vault-12-agent-go']),
        ('Книга IV · Состояние и отказ', ['vault-13-raft','vault-14-audit','vault-15-recovery','vault-16-measure','vault-17-lab']),
        ('Справочник', ['99-glossary']),
    ],
    base_terms=[], term_modules=['reference'], command_modules=['reference'], diagram_modules=['diagrams'],
    blurb='Подпись поставки → TLS и Raft → init/unseal → запрос и ACL → KV/leases → AppRole/PG/PKI → Agent/Go → аудит, резерв и отказ.',
)
