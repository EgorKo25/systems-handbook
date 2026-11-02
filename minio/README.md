# MinIO: исходники самостоятельного тома

Читательский порядок задаёт volume_config.py: начало, устройство set,
получение Server/mc, TLS и сохраняемый single-endpoint стенд, первый объект,
ограниченный доступ, версии, object IO 08, healing/scanner 07,
pools/rebalance, резерв/восстановление, ёмкость/измерения и словарь.

Это оригинальные русские учебные материалы об архивном OSS Server
9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a и mc
7394ce0dd2a80935aded936b09fa12cbb3cb8096. Современная AIStor рассматривается
как отдельная поставка/лицензия; коммерческие возможности не обещаются
владельцу archival OSS или AIStor Free автоматически.

HTML fragments и local SVG читаются через общий offline reader библиотеки.
Новых внешних JS, CDN, шрифтов или fetch для рисунка нет. diagrams.py
сохраняет две ранее принятые пошаговые сцены; healing представлен предметным
inline SVG и его отдельным полным исходником. 07/08 не сокращены.

build.py только вызывает scripts.build_volume.build("minio").
Сам по себе он не регистрирует том: основной интегратор должен подключить
CONFIGS/TARGETS через принятую процедуру в isolated candidate, проверить
все anchors/reference/assets и лишь затем отдельно решать публикацию.
Скрипт не вызывает home()/refresh(). Автор не меняет registry, reader
или Pages. Запуск wrapper до интеграции CONFIGS не заявляется работающим.

Лаборатории:
- healing_scanner_model.py — прежняя чистая модель выбора/целей/IO;
- object_io_model.py — точная standalone копия учебного GF-примера из 08
  с завершающим LF; это не матрица klauspost/reedsolomon;
- capacity_model.py — новые округления, веса и синтетические quantiles;
- cold_copy.py — собственный helper полного приватного cold-copy
  остановленного single-endpoint LAB_ROOT, не общий distributed backup.

Все изменяющие команды книги предназначены для личной Linux guest с правом
записи и отдельным каталогом. При подготовке тома filesystem был read-only:
установка, сервис, TLS/account/restore и benchmark не выполнялись.
Секретов, runtime, бинарников, certificates/keys и пользовательских state
в source bundle нет. Публичный README описывает книгу, не личный стенд.
Подробные пределы и фактические проверки — в ПРОВЕРКИ.txt и READY.txt.
