"""Original standalone Terraform volume; registration belongs to the integrator."""
CONFIG = dict(
    volume='XIV', title='Terraform: язык, граф исполнения и сохранённое состояние', short='Terraform',
    description='CLI и HCL, providers и модули, plan/apply, identity и state, блокировки, восстановление и измерения.',
    sections=[
        ('Начало', ['00-route', 'tf-01-install', 'tf-02-first-state']),
        ('Книга I · Язык HCL', ['tf-03-types', 'tf-04-expressions', 'tf-05-contracts', 'tf-06-instances']),
        ('Книга II · Как исполняется изменение', ['tf-07-init-provider', 'tf-08-graph-unknown', 'tf-09-plan-apply', 'tf-10-lifecycle']),
        ('Книга III · Модули и адреса', ['tf-11-module-interface', 'tf-12-module-providers', 'tf-13-module-evolution']),
        ('Книга IV · Состояние и команда', ['tf-14-state-identity', 'tf-15-drift-import', 'tf-16-backends-locks', 'tf-17-recovery-security']),
        ('Эксплуатация и практикум', ['tf-18-offline-upgrade', 'tf-19-performance', 'tf-20-vm-contract', 'tf-21-lab', 'tf-22-sources']),
        ('Справочник', ['99-glossary']),
    ],
    term_modules=['reference'], command_modules=['reference'], diagram_modules=['diagrams'], base_terms=[],
    revision='1 ноября 2026',
    blurb='Проверенный CLI → значения и типы → граф и provider → plan/apply → адреса модулей → state, команда и восстановление.',
)
