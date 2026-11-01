"""Independent technology volumes. Stable IDs preserve earlier chapter links."""
CONFIGS = {
 'git': dict(volume='VI',title='Git: от байтов объектов до совместной работы и восстановления',short='Git',
    description='Объекты, индекс, история, обмен, обслуживание и восстановление репозитория.',
    sections=[('Начало',['00-route']),('Устройство репозитория',['24-config-environment','01-repository-model','02-objects','03-index','04-history','25-revision-lab']),('Изменение и исследование истории',['05-branches','06-diffs','07-merge','08-rewrite','09-recovery','26-bisect-search']),('Обмен, правила и доверие',['10-remotes','11-collaboration','27-hooks-policy','12-attributes','31-signatures-trust']),('Состав и эксплуатация',['28-submodules','29-large-partial-sparse','30-bundles-server','32-history-migration','13-storage-performance','33-git-diagnostics']),('Практикум',['22-lab']),('Справочник',['99-glossary'])],
    term_modules=['git_deep_terms_a','git_deep_terms_b'],diagram_modules=['git_state_diagrams'],
    base_terms=list(range(73))+list(range(123,127))+[129,130,139],
    blurb='Объекты и точные байты → индекс и история → сложные операции → обмен → эксплуатация и восстановление.'),
 'go': dict(volume='VII',title='Go: сборка, компилятор и исполняемая программа',short='Go',
    description='Самостоятельный том Go. Книга о toolchain, модулях, компиляции, линковке, кэше и производительности.',
    sections=[('Начало тома',['00-route']),('Книга I · Сборка и компилятор',['91-build-book']),('Входы и получение результата',['14-build-process','15-dependencies','16-reproducibility','17-build-cache']),('От исходного текста к машинному коду',['46-go-front-end','47-go-types-generics','48-go-ir-escape-inline','49-go-ssa','50-go-machine-code','51-go-abi']),('Линковка и выполнение',['52-go-linker','53-go-elf-loader','54-go-memory-gc','55-go-pgo','56-go-cgo-toolchains']),('Проверка и инженерные решения',['20-checks-artifacts','21-measurement','57-go-optimization-cases','58-toolchain-flags','59-compiler-debug-lab','23-release']),('Справочник',['99-glossary'])],
    term_modules=['go_deep_reference','compiler_terms'],diagram_modules=['diagrams','compiler_diagrams'],
    base_terms=list(range(73,98))+list(range(111,115))+list(range(118,123))+list(range(127,132)),
    blurb='Модули и toolchain → компилятор и SSA → ABI и линковка → бинарник → кэш, измерения и работа программы.'),
 'jenkins': dict(volume='VIII',title='Jenkins: от установки и плагинов до устройства и эксплуатации Pipeline',short='Jenkins',
    description='Скачивание, установка, настройка, плагины, агенты, Pipeline, доверие, ресурсы и восстановление.',
    sections=[('Начало',['00-route']),('Установка и первоначальная настройка',['34-jenkins-install','35-jenkins-home-storage','36-jenkins-plugins-upgrade']),('Устройство системы',['18-jenkins-architecture','37-jenkins-agents-remoting','38-jenkins-pipeline-engine']),('Исполнение и данные',['19-jenkinsfile','39-jenkins-data-flow','40-jenkins-multibranch']),('Доверие и эксплуатация',['41-jenkins-trust','42-jenkins-concurrency','43-jenkins-recovery','44-jenkins-observability']),('Практикум',['45-jenkins-lab']),('Справочник',['99-glossary'])],
    term_modules=['jenkins_deep_terms'],diagram_modules=['diagrams'],
    base_terms=list(range(98,111))+list(range(114,118))+list(range(132,139)),
    blurb='Скачивание и установка → настройка и плагины → агенты → движок Pipeline → эксплуатация и восстановление.'),
}
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
from scripts.publication import MANAGED_VOLUMES
for slug in MANAGED_VOLUMES:
    if slug not in CONFIGS:
        spec = spec_from_file_location('handbook_config_'+slug,
                                      Path(__file__).resolve().parents[1]/slug/'volume_config.py')
        loaded = module_from_spec(spec)
        spec.loader.exec_module(loaded)
        config = loaded.CONFIG
        CONFIGS[slug] = {'revision': '1 ноября 2026', **config}
if set(CONFIGS) != set(MANAGED_VOLUMES):
    raise ValueError('Managed volume configuration and publication registry differ')
TARGETS = {identifier:slug for slug,cfg in CONFIGS.items() for _,ids in cfg['sections'] for identifier in ids if identifier not in {'00-route','99-glossary'}}
