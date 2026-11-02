"""Independent Kubernetes volume. The integrator assigns the final volume label."""
CONFIG = dict(
 volume='XVII', title='Kubernetes: от API до процесса, пакета и восстановления', short='Kubernetes',
 description='Сохраняемый кластер, согласование состояния, Go-нагрузка, сеть, данные, безопасность и эксплуатация.',
 sections=[
 ('Начало', ['00-route']),
 ('Книга I · Получить и сохранить кластер', ['01-k8s-distribution','02-k8s-kubeadm','03-k8s-kind']),
 ('Книга II · API и согласование', ['04-k8s-api','05-k8s-watch-apply','06-k8s-controllers','07-k8s-scheduling']),
 ('Книга III · Исполнение программы', ['08-k8s-node','09-k8s-lifecycle','10-k8s-workloads','11-k8s-configuration']),
 ('Книга IV · Путь пакета', ['12-k8s-addressing','13-k8s-packet','14-k8s-dns-policy','15-k8s-edge']),
 ('Книга V · Данные и доверие', ['16-k8s-storage','17-k8s-identity','18-k8s-isolation']),
 ('Книга VI · Эксплуатация и развитие', ['19-k8s-observe','20-k8s-capacity','21-k8s-upgrade-backup','22-k8s-failures']),
 ('Сквозной практикум', ['23-k8s-lab']),
 ('Источники и справочник', ['24-k8s-sources','99-glossary'])],
 term_modules=['reference'], command_modules=['reference'], diagram_modules=['diagrams'], base_terms=[],
 blurb='Дистрибутив и VM → API и controllers → kubelet и CRI → пакет и DNS → CSI и доверие → измерения и восстановление.',
)
