"""Ceph20.2.4 glossary and UI command cards; not installed CLI tests."""
GLOSSARY = [
  [
    "RADOS",
    "Основание Ceph: именованные объекты, операции над ними, размещение и согласование истории на OSD."
  ],
  [
    "OSD",
    "Процесс хранения, который обслуживает свою часть PG и локальный ObjectStore; здесь BlueStore на отдельном VM-диске."
  ],
  [
    "MON",
    "Участник согласования управляющего состояния и карт. Через MON не проходит каждый payload клиента."
  ],
  [
    "MGR",
    "Активный процесс управления модулями/наблюдением; standby может заменить его роль."
  ],
  [
    "MDS",
    "Процесс координации файловых метаданных и клиентских inode caps CephFS."
  ],
  [
    "RGW",
    "Шлюз S3/Swift, переводящий API-операции в собственные metadata/index/data структуры RADOS."
  ],
  [
    "FSID",
    "Идентификатор экземпляра Ceph-кластера. Одинаковые имена hosts/OSD не заменяют FSID."
  ],
  [
    "Epoch",
    "Номер версии конкретной карты. Это не wall-clock time и не номер версии S3."
  ],
  [
    "OSDMap",
    "Карта OSD, pools, состояний и дополнительных назначений; содержит CRUSH-представление."
  ],
  [
    "Pool",
    "Логическая область RADOS с параметрами размещения, защиты и PG."
  ],
  [
    "PG",
    "Группа объектов пула, чью историю и восстановление совместно ведут выбранные OSD."
  ],
  [
    "Primary",
    "OSD, координирующий клиентские операции конкретной PG в данном интервале."
  ],
  [
    "Up set",
    "Упорядоченное назначение PG после CRUSH и соответствующих преобразований карты."
  ],
  [
    "Acting set",
    "Текущий ответственный состав PG; может временно отличаться от up."
  ],
  [
    "CRUSH",
    "Детерминированный выбор устройств по seed, топологии, правилам, весам и параметрам алгоритма."
  ],
  [
    "Failure domain",
    "Группа размещения, один отказ которой способен затронуть несколько устройств: host,rack и т.п."
  ],
  [
    "Size",
    "Число полных копий replicated pool; в EC связано с числом shards, а не с копиями всего payload."
  ],
  [
    "Min_size",
    "Нижняя граница состава допуска IO при выполненных остальных условиях, не формула любых ACK."
  ],
  [
    "Peering",
    "Согласование истории PG и доступных данных до обслуживания нового интервала."
  ],
  [
    "PG log",
    "Упорядоченные недавние изменения PG, необходимые для истории/recovery; не архив всех тел объектов."
  ],
  [
    "Recovery",
    "Доставка требуемых недостающих/отставших данных после согласования истории."
  ],
  [
    "Backfill",
    "Сопоставление диапазонов объектов и перенос содержимого, когда обычной log-based истории недостаточно."
  ],
  [
    "BlueStore",
    "Локальный ObjectStore OSD, связывающий полезные области устройства с KV-метаданными."
  ],
  [
    "Onode",
    "Служебное описание объекта BlueStore, включая размер,идентификатор и представление его extents."
  ],
  [
    "Extent",
    "Диапазон адресов с началом и длиной; логический диапазон объекта отличается от физического устройства."
  ],
  [
    "Blob",
    "Внутреннее описание порции размещённых данных BlueStore, связанное с физическими extents."
  ],
  [
    "RocksDB",
    "Встроенная KV-база служебных данных BlueStore с memtable,WAL,SST и compaction."
  ],
  [
    "WAL",
    "Write-ahead log; журнал восстановления изменений. RocksDB WAL не равен PG log или MDS journal."
  ],
  [
    "BlueFS",
    "Файловый слой BlueStore для файлов RocksDB на устройствах OSD."
  ],
  [
    "Flush",
    "В контексте устройства — требуемая синхронизация; в RocksDB flush memtable — создание SST. Это разные операции."
  ],
  [
    "EC",
    "Erasure coding: K data shards и M parity shards с защитой и ценой реконструкции выбранного кода."
  ],
  [
    "mClock",
    "Планировщик ресурсов OSD с классами/профилями; классификация конкретного сообщения зависит от версии и priority."
  ],
  [
    "RBD image",
    "Именованное логическое блочное устройство, диапазоны которого librbd отображает в RADOS objects."
  ],
  [
    "Snapshot",
    "Выбранное состояние данных в том же хранилище; само по себе не независимый backup."
  ],
  [
    "Clone",
    "Image с зависимостью от снимка родителя до копирования нужных данных/flatten."
  ],
  [
    "Blocklist",
    "Запрет OSD обслуживать указанного клиента по карте; часть storage fencing."
  ],
  [
    "CephX caps",
    "Права удостоверения клиента/демона на сервисы Ceph, не разрешения кэша inode."
  ],
  [
    "Inode caps",
    "Временные разрешения MDS клиенту CephFS держать/изменять определённые данные и metadata inode."
  ],
  [
    "Bucket index",
    "Индекс RGW с записями API-объектов и pending transactions; может состоять из нескольких shards."
  ],
  [
    "OLH",
    "Object logical head RGW: косвенная ссылка текущей версии имени в versioned bucket."
  ],
  [
    "Realm",
    "Совокупность multisite-конфигурации RGW с zonegroups,zones и periods."
  ],
  [
    "RPO",
    "Допустимая потеря последних изменений при восстановлении выбранной точки."
  ],
  [
    "RTO",
    "Время до принятого восстановления сервиса, включая получение данных и прикладные проверки."
  ],
  [
    "Write amplification",
    "Отношение записанных байтов на указанной нижней границе к логическим байтам приложения."
  ],
  [
    "Digest",
    "Криптографический идентификатор содержимого образа; не замена доверия источнику ожидаемого значения."
  ],
  [
    "Квитанция этапа",
    "Сохранённый файл результата завершённых проверок. Attempted-квитанция не подтверждает успех."
  ]
]

COMMANDS = [
  {
    "name": "cephadm",
    "aliases": [],
    "purpose": "Управлять развёртыванием в принятой личной VM.",
    "syntax": "cephadm [ROOT FLAGS] COMMAND",
    "chapter": "ceph-03-vm-install",
    "volume": "ceph",
    "source": "https://github.com/ceph/ceph/tree/v20.2.4/doc",
    "sources": [
      {
        "title": "Ceph v20.2.4",
        "url": "https://github.com/ceph/ceph/tree/v20.2.4"
      }
    ],
    "flags": [
      {
        "flag": "--image IMAGE",
        "action": "Выбрать образ до подкоманды.",
        "when": "Использовать принятый digest.",
        "example": "cephadm --image \"$image\" inspect-image",
        "result": "Проверяется фактическая версия образа; имя не удостоверяет издателя."
      },
      {
        "flag": "--verbose",
        "action": "Включить root diagnostic logging.",
        "when": "Перед COMMAND; не JSON режима version.",
        "example": "cephadm --verbose check-host",
        "result": "Это другая область опции, чем version --verbose."
      }
    ],
    "situations": []
  },
  {
    "name": "cephadm version",
    "aliases": [],
    "purpose": "Прочитать версию установленного cephadm.",
    "syntax": "cephadm version [--verbose]",
    "chapter": "ceph-02-supply",
    "volume": "ceph",
    "source": "https://github.com/ceph/ceph/tree/v20.2.4/doc",
    "sources": [
      {
        "title": "Ceph v20.2.4",
        "url": "https://github.com/ceph/ceph/tree/v20.2.4"
      }
    ],
    "flags": [
      {
        "flag": "--verbose",
        "action": "Вернуть подробные сведения версии в JSON.",
        "when": "После version.",
        "example": "cephadm version --verbose",
        "result": "В20.2.4 root --verbose перед version не заменяет эту опцию."
      }
    ],
    "situations": []
  },
  {
    "name": "cephadm shell",
    "aliases": [],
    "purpose": "Запустить argv в выбранном Ceph-образе.",
    "syntax": "cephadm [ROOT FLAGS] shell [FLAGS] -- PROGRAM ARGS",
    "chapter": "ceph-09-rados-lab",
    "volume": "ceph",
    "source": "https://github.com/ceph/ceph/tree/v20.2.4/doc",
    "sources": [
      {
        "title": "Ceph v20.2.4",
        "url": "https://github.com/ceph/ceph/tree/v20.2.4"
      }
    ],
    "flags": [
      {
        "flag": "--fsid FSID",
        "action": "Адресовать принятый кластер.",
        "when": "При нескольких экземплярах/явном повторном входе.",
        "example": "cephadm --image \"$image\" shell --fsid \"$fsid\" -- ceph status",
        "result": "Не выбирает другой кластер по похожему имени."
      },
      {
        "flag": "--mount SRC:DST:OPTIONS",
        "action": "Смонтировать выбранный каталог.",
        "when": "Для входного файла ro; карточка показывает один mount.",
        "example": "cephadm shell --mount \"$PWD/input:/study-input:ro\" -- rados -p cephstudy put report /study-input/report.txt",
        "result": "В CLI nargs+; -- отделяет конец mount argv."
      },
      {
        "flag": "--",
        "action": "Завершить параметры оболочки.",
        "when": "Перед PROGRAM.",
        "example": "cephadm shell -- ceph -s",
        "result": "-s принадлежит ceph, не cephadm."
      }
    ],
    "situations": []
  },
  {
    "name": "cephadm bootstrap",
    "aliases": [],
    "purpose": "Создать первоначальный control plane один раз.",
    "syntax": "cephadm --image IMAGE bootstrap [FLAGS]",
    "chapter": "ceph-03-vm-install",
    "volume": "ceph",
    "source": "https://github.com/ceph/ceph/tree/v20.2.4/doc",
    "sources": [
      {
        "title": "Ceph v20.2.4",
        "url": "https://github.com/ceph/ceph/tree/v20.2.4"
      }
    ],
    "flags": [
      {
        "flag": "--mon-ip IP",
        "action": "Выбрать адрес первого MON.",
        "when": "Только после проверки VM и сети.",
        "example": "cephadm --image \"$image\" bootstrap --mon-ip 10.77.0.11",
        "result": "Полный рецепт также передаёт FSID/config/SSH keys и сохраняет попытку."
      },
      {
        "flag": "--config FILE",
        "action": "Прочитать выбранный initial config.",
        "when": "Из нового bootstrap generation.",
        "example": "cephadm bootstrap --mon-ip 10.77.0.11 --config initial-ceph.conf",
        "result": "Не разрешает перезаписать существующий кластер."
      }
    ],
    "situations": []
  },
  {
    "name": "ceph",
    "aliases": [],
    "purpose": "Запросить или изменить состояние принятого кластера.",
    "syntax": "ceph [FLAGS] COMMAND",
    "chapter": "ceph-21-observation",
    "volume": "ceph",
    "source": "https://github.com/ceph/ceph/tree/v20.2.4/doc",
    "sources": [
      {
        "title": "Ceph v20.2.4",
        "url": "https://github.com/ceph/ceph/tree/v20.2.4"
      }
    ],
    "flags": [
      {
        "flag": "--format FORMAT",
        "action": "Выбрать представление ответа.",
        "when": "Для сохраняемых JSON observations.",
        "example": "ceph status --format=json",
        "result": "Код0 status не означает HEALTH_OK."
      },
      {
        "flag": "-s",
        "action": "Запросить краткое состояние.",
        "when": "После принятия FSID.",
        "example": "ceph -s",
        "result": "Читать также health detail и PG состояния."
      }
    ],
    "situations": []
  },
  {
    "name": "ceph osd pool create",
    "aliases": [],
    "purpose": "Создать новый pool по принятому правилу.",
    "syntax": "ceph osd pool create POOL PG_NUM PGP_NUM replicated [FLAGS]",
    "chapter": "ceph-09-rados-lab",
    "volume": "ceph",
    "source": "https://github.com/ceph/ceph/tree/v20.2.4/doc",
    "sources": [
      {
        "title": "Ceph v20.2.4",
        "url": "https://github.com/ceph/ceph/tree/v20.2.4"
      }
    ],
    "flags": [
      {
        "flag": "--rule RULE",
        "action": "Выбрать существующее правило CRUSH.",
        "when": "После проверки отсутствия pool.",
        "example": "ceph osd pool create cephstudy 8 8 replicated --rule=cephstudy-host --autoscale-mode=off",
        "result": "Правило выбирает домены; свободные байты не заменяют домены."
      },
      {
        "flag": "--autoscale-mode MODE",
        "action": "Задать управление количеством PG.",
        "when": "Off для фиксированного малого опыта.",
        "example": "ceph osd pool create cephstudy 8 8 replicated --rule=cephstudy-host --autoscale-mode=off",
        "result": "Не универсальная настройка производительности."
      }
    ],
    "situations": []
  },
  {
    "name": "ceph osd pool set",
    "aliases": [],
    "purpose": "Изменить параметр выбранного pool.",
    "syntax": "ceph osd pool set POOL KEY VALUE [FLAGS]",
    "chapter": "ceph-09-rados-lab",
    "volume": "ceph",
    "source": "https://github.com/ceph/ceph/tree/v20.2.4/doc",
    "sources": [
      {
        "title": "Ceph v20.2.4",
        "url": "https://github.com/ceph/ceph/tree/v20.2.4"
      }
    ],
    "flags": [
      {
        "flag": "--yes-i-really-mean-it",
        "action": "Подтвердить опасный size1 вместе с MON guard.",
        "when": "Только для собственного одно-OSD пула.",
        "example": "ceph osd pool set cephstudy size 1 --yes-i-really-mean-it",
        "result": "Требуется mon_allow_pool_size_one; защита guard возвращается."
      }
    ],
    "situations": []
  },
  {
    "name": "rados",
    "aliases": [],
    "purpose": "Операции над внутренними объектами RADOS.",
    "syntax": "rados [FLAGS] COMMAND",
    "chapter": "ceph-09-rados-lab",
    "volume": "ceph",
    "source": "https://github.com/ceph/ceph/tree/v20.2.4/doc",
    "sources": [
      {
        "title": "Ceph v20.2.4",
        "url": "https://github.com/ceph/ceph/tree/v20.2.4"
      }
    ],
    "flags": [
      {
        "flag": "--pool POOL",
        "action": "Выбрать pool.",
        "when": "Перед операцией.",
        "example": "rados --pool cephstudy get report -",
        "result": "Знак- в get выбирает stdout; обычный filename может быть усечён программой."
      }
    ],
    "situations": []
  },
  {
    "name": "rbd create",
    "aliases": [],
    "purpose": "Создать новый логический image.",
    "syntax": "rbd create [FLAGS] POOL/IMAGE",
    "chapter": "ceph-10-rbd-path",
    "volume": "ceph",
    "source": "https://github.com/ceph/ceph/tree/v20.2.4/doc",
    "sources": [
      {
        "title": "Ceph v20.2.4",
        "url": "https://github.com/ceph/ceph/tree/v20.2.4"
      }
    ],
    "flags": [
      {
        "flag": "--size SIZE",
        "action": "Выбрать логический размер.",
        "when": "Проверить отсутствие имени.",
        "example": "rbd create --size 64M --object-size 4M --image-feature layering rbdstudy/report-disk",
        "result": "64M не означает немедленное выделение64MiB на каждом OSD."
      },
      {
        "flag": "--object-size SIZE",
        "action": "Задать размер data object.",
        "when": "Для разбора layout.",
        "example": "rbd create --size 64M --object-size 4M rbdstudy/report-disk",
        "result": "Для выбранного layout4MiB; сложное striping требует иных расчётов."
      }
    ],
    "situations": []
  },
  {
    "name": "rbd export",
    "aliases": [],
    "purpose": "Экспортировать выбранное содержимое image/snapshot.",
    "syntax": "rbd export IMAGE[@SNAP] DEST",
    "chapter": "ceph-12-rbd-backup-restore",
    "volume": "ceph",
    "source": "https://github.com/ceph/ceph/tree/v20.2.4/doc",
    "sources": [
      {
        "title": "Ceph v20.2.4",
        "url": "https://github.com/ceph/ceph/tree/v20.2.4"
      }
    ],
    "flags": [],
    "situations": []
  },
  {
    "name": "rbd import",
    "aliases": [],
    "purpose": "Создать новое image из принятого входа.",
    "syntax": "rbd import SOURCE POOL/NEWIMAGE",
    "chapter": "ceph-12-rbd-backup-restore",
    "volume": "ceph",
    "source": "https://github.com/ceph/ceph/tree/v20.2.4/doc",
    "sources": [
      {
        "title": "Ceph v20.2.4",
        "url": "https://github.com/ceph/ceph/tree/v20.2.4"
      }
    ],
    "flags": [],
    "situations": []
  },
  {
    "name": "ceph fs authorize",
    "aliases": [],
    "purpose": "Назначить права отдельному CephFS-клиенту.",
    "syntax": "ceph fs authorize FS CLIENT PATH ACCESS",
    "chapter": "ceph-15-cephfs-caps-layout",
    "volume": "ceph",
    "source": "https://github.com/ceph/ceph/tree/v20.2.4/doc",
    "sources": [
      {
        "title": "Ceph v20.2.4",
        "url": "https://github.com/ceph/ceph/tree/v20.2.4"
      }
    ],
    "flags": [],
    "situations": []
  },
  {
    "name": "rgw-adminbucket",
    "aliases": [],
    "purpose": "Создать/проверить bucket отдельным source-only helper.",
    "syntax": "rgw-adminbucket --config FILE --target ID [--timeout DURATION] create|head",
    "chapter": "ceph-19-rgw-s3-project",
    "volume": "ceph",
    "source": "https://github.com/ceph/ceph/tree/v20.2.4/doc",
    "sources": [
      {
        "title": "Ceph v20.2.4",
        "url": "https://github.com/ceph/ceph/tree/v20.2.4"
      }
    ],
    "flags": [
      {
        "flag": "--config FILE",
        "action": "Прочитать явные targets.",
        "when": "Перед командой после native build gate.",
        "example": "rgw-adminbucket --config config/targets.json --target rgw-study create",
        "result": "Нет ambient AWS chain; private credentials отдельно."
      },
      {
        "flag": "--timeout DURATION",
        "action": "Ограничить одну операцию.",
        "when": "Положительное время не более15m.",
        "example": "rgw-adminbucket --config config/targets.json --target rgw-study --timeout 30s head",
        "result": "Failed create может иметь unknown outcome."
      }
    ],
    "situations": []
  }
]
