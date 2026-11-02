"""Original terms and command cards for the S3 volume."""
GLOSSARY = [
  [
    "S3 API",
    "Семейство сетевых операций над корзинами и именованными объектами. Amazon S3 — конкретная облачная служба; совместимость API не переносит все её гарантии."
  ],
  [
    "Bucket / корзина",
    "Именованный контейнер объектов с отдельными настройками доступа, versioning и жизненного цикла."
  ],
  [
    "Key / ключ объекта",
    "Полное имя объекта внутри корзины; слеши могут группировать префиксы, но не создают каталогов POSIX."
  ],
  [
    "Body / тело",
    "Последовательность байтов объекта или HTTP-сообщения; Content-Length описывает байты, а не число печатных символов."
  ],
  [
    "Payload",
    "Полезное содержимое сообщения. В SigV4 хешируется именно выбранное тело, либо используется предусмотренный маркер."
  ],
  [
    "Metadata",
    "Сведения об объекте, включая системные поля и пользовательские x-amz-meta-*; не являются частью байтов его тела."
  ],
  [
    "Version ID",
    "Непрозрачный ID версии. Строка null отличается от JSON null; null-version AWS при Suspended может заменяться."
  ],
  [
    "Delete marker",
    "Версия-метка отсутствия текущего объекта; не содержит прежнее тело и не обязательно удаляет старые data versions."
  ],
  [
    "Endpoint",
    "Адрес API службы, включающий схему, имя/адрес узла и при необходимости порт."
  ],
  [
    "Region",
    "Регион выбранной службы; в SigV4 входит в scope и производный ключ подписывания."
  ],
  [
    "DNS",
    "Система получения адресов по имени; ответ зависит от сетевого окружения и может кэшироваться."
  ],
  [
    "TLS",
    "Протокол защиты соединения и проверки сервера по сертификату; не выдаёт прав на операцию S3."
  ],
  [
    "CA",
    "Удостоверяющий центр, сертификату которого доверяет клиент при проверке цепочки сервера."
  ],
  [
    "Loopback",
    "Адрес самого сетевого окружения клиента, например 127.0.0.1; не означает другую VM."
  ],
  [
    "HTTP header",
    "Именованное поле метаданных HTTP-сообщения; имена не чувствительны к регистру, значения имеют собственные правила."
  ],
  [
    "URI",
    "Идентификатор ресурса. Percent-encoding кодирует байты, а не выполняет очистку пути S3."
  ],
  [
    "UTF-8",
    "Кодирование символов Unicode в последовательности байтов; перед percent-encoding сначала выбираются эти байты."
  ],
  [
    "ASCII",
    "Таблица кодирования однобайтовых символов; используемые латинские символы и управляющий LF имеют точные значения байтов."
  ],
  [
    "LF / CRLF",
    "LF — байт 0A. CRLF — пара 0D 0A. В HTTP/1 поля заканчиваются CRLF, в canonical request SigV4 разделители LF."
  ],
  [
    "Percent-encoding",
    "Представление байта как % и двух шестнадцатеричных цифр. Пробел %20 не равен плюсу %2B и буквальной строке %20."
  ],
  [
    "SHA-256",
    "Хеш-функция с 32-байтовым результатом; hex-представление занимает 64 ASCII-символа."
  ],
  [
    "Hex",
    "Шестнадцатеричная запись байтов двумя цифрами на байт; не равна самим бинарным байтам ключа HMAC."
  ],
  [
    "Base64",
    "Кодирование бинарных данных текстом; S3 checksum-поля часто используют Base64, а payload hash SigV4 — hex."
  ],
  [
    "HMAC",
    "Код аутентификации сообщения на общем секретном ключе. В SigV4 HMAC-SHA256 используется в производных ключах и финальном значении."
  ],
  [
    "SigV4",
    "Подписывание выбранных частей запроса через canonical request, string-to-sign и HMAC с производным ключом."
  ],
  [
    "Canonical request",
    "Точная строка из method, canonical URI/query/headers, SignedHeaders и payload hash или маркера; её SHA-256 входит в string-to-sign."
  ],
  [
    "SignedHeaders",
    "Отсортированный список нормализованных имён полей, включённых в canonical headers."
  ],
  [
    "Scope",
    "Дата/регион/служба/aws4_request в SigV4; связывает подпись с назначением производного ключа."
  ],
  [
    "Presigned URL",
    "URL с параметрами авторизации SigV4; срок ограничен не только X-Amz-Expires, но и действием доступа. Helper v1 его не создаёт."
  ],
  [
    "Credentials",
    "Идентификатор доступа, общий секрет и при временном доступе session token со сроком. В receipt не выводятся."
  ],
  [
    "SDK",
    "Набор библиотек для API; наш helper использует AWS SDK for Go v2 для построения, подписи, повторов и разбора запросов."
  ],
  [
    "Receipt",
    "Очищенная JSON-квитанция одной операции: исход, выбранные сведения ответа, локальные байты/хеш и счётчик Do."
  ],
  [
    "Fixture",
    "Заранее заданные тестовые байты с известным ожидаемым результатом; hello-v1 содержит 14 байтов."
  ],
  [
    "Dispatch",
    "В helper передача запроса HTTP-клиенту через Do со стороны SDK; не подтверждение приёма сервером."
  ],
  [
    "Retry",
    "Повторная попытка после ошибки. Одинаковое текущее тело не означает одинаковую историю версий."
  ],
  [
    "Unknown outcome",
    "Клиент не имеет достаточного подтверждения результата. Timeout после возможного PUT не доказывает отсутствия записи."
  ],
  [
    "Reconciliation",
    "Сопоставление сохранённого намерения с наблюдаемыми версиями, metadata, длиной и хешем после неизвестного результата."
  ],
  [
    "Operation ID",
    "Выбранный клиентом идентификатор прикладной операции, сохраняемый в metadata между внутренними повторами."
  ],
  [
    "ETag",
    "Непрозрачная метка представления, используемая предусмотренными условиями; не безусловный MD5, checksum или уникальный ID истории."
  ],
  [
    "Validator",
    "Значение для проверки состояния представления; strong и weak сравнения имеют разные правила HTTP."
  ],
  [
    "Checksum",
    "Контрольная сумма с указанными алгоритмом, кодировкой и областью: full object и composite не взаимозаменяемы."
  ],
  [
    "EOF",
    "Признак завершения потока; Go Read может вернуть последние n байтов одновременно с EOF."
  ],
  [
    "Range",
    "Один выбранный интервал байтов ответа; bytes=0-5 содержит шесть байтов."
  ],
  [
    "Multipart upload",
    "Загрузка частей под upload ID с последующим Complete; незавершённые parts ещё не являются текущим объектом."
  ],
  [
    "ContinuationToken",
    "Непрозрачный маркер продолжения страницы ListObjectsV2; не равен последнему ключу и не даёт общего снимка."
  ],
  [
    "Principal",
    "Субъект доступа, например IAM role или её сеанс; policy определяет разрешения действий над ресурсами."
  ],
  [
    "ARN",
    "Имя ресурса AWS. ARN корзины и ARN множества объектов с /prefix/* относятся к разным действиям."
  ],
  [
    "Lifecycle",
    "Правила переходов и удаления по условиям времени; удаление noncurrent versions может окончательно уничтожить историю."
  ],
  [
    "Object Lock",
    "Защита выбранных версий AWS от предусмотренного удаления/изменения по retention или legal hold; не запрещает новые версии над ними."
  ],
  [
    "RPO / RTO",
    "Допустимая потеря свежести данных при восстановлении и допустимое время возвращения работы соответственно."
  ],
  [
    "Durability / availability",
    "Удержание принятых данных при отказах и возможность обращения в нужный момент; разные свойства."
  ],
  [
    "MVS / go.sum",
    "Go выбирает build list через minimal version selection; go.sum хранит контрольные суммы модулей, а не самостоятельный lock."
  ]
]

COMMANDS = [
  {
    "name": "object-study",
    "purpose": "Одна проверяемая операция над подготовленной целью.",
    "syntax": "object-study --config FILE --target ID [--timeout 30s] COMMAND",
    "volume": "s3",
    "chapter": "s3-04-access-profiles",
    "aliases": [],
    "flags": [
      {
        "flag": "--config FILE",
        "action": "Выбрать targets.json.",
        "when": "До команды; абсолютный путь упрощает повтор.",
        "example": "--config /home/learner/object-study-lab/config/targets.json",
        "result": "Загрузка только указанного собственного формата."
      },
      {
        "flag": "--target ID",
        "action": "Выбрать запись targets, затем её profile.",
        "when": "До команды, ровно один раз.",
        "example": "--target study",
        "result": "Endpoint и credentials не угадываются."
      },
      {
        "flag": "--timeout DURATION",
        "action": "Конечный срок одной операции, включая Body.",
        "when": "По умолчанию 30s, больше нуля, не более 15m.",
        "example": "--timeout 30s",
        "result": "Deadline, не команда отката сервера."
      }
    ],
    "situations": [],
    "source": "#s3-04-access-profiles",
    "sources": [
      {
        "title": "Описание и первичный источник",
        "url": "#s3-04-access-profiles"
      }
    ]
  },
  {
    "name": "object-study put",
    "purpose": "Создать объект или заменить ожидаемое состояние.",
    "syntax": "object-study --config FILE --target ID put --source FILE (--create-only|--if-match ETAG) -- KEY",
    "volume": "s3",
    "chapter": "s3-04-access-profiles",
    "aliases": [],
    "flags": [
      {
        "flag": "--source FILE",
        "action": "Открыть обычный локальный неизменяемый источник.",
        "when": "До -- KEY; предел helper 64 MiB.",
        "example": "--source /home/learner/object-study-lab/fixtures/hello-v1.bin",
        "result": "Prehash, затем явный checksum SHA256."
      },
      {
        "flag": "--create-only",
        "action": "Требовать отсутствия текущего тела.",
        "when": "Ровно одно из двух условий.",
        "example": "--create-only",
        "result": "If-None-Match: *."
      },
      {
        "flag": "--if-match ETAG",
        "action": "Заменять при совпадении непрозрачного ETag.",
        "when": "Вместо create-only, с сохранёнными кавычками.",
        "example": "--if-match '\"E1\"'",
        "result": "If-Match; при отказе условие не снимают."
      },
      {
        "flag": "-- KEY",
        "action": "Закончить параметры и передать исходный ключ.",
        "when": "Последние два аргумента, без URL-кодирования.",
        "example": "-- 'lessons/2026-11/hello +%.txt'",
        "result": "SDK кодирует выбранные байты."
      }
    ],
    "situations": [],
    "source": "#s3-08-conditions-ranges",
    "sources": [
      {
        "title": "Описание и первичный источник",
        "url": "#s3-08-conditions-ranges"
      }
    ]
  },
  {
    "name": "object-study get",
    "purpose": "Принять полную копию в новое локальное имя.",
    "syntax": "object-study --config FILE --target ID get --output NEWFILE --max-bytes N [--version-id ID] -- KEY",
    "volume": "s3",
    "chapter": "s3-04-access-profiles",
    "aliases": [],
    "flags": [
      {
        "flag": "--output NEWFILE",
        "action": "Публиковать только новое имя в приватном каталоге.",
        "when": "Существующее имя не перезаписывается.",
        "example": "--output /home/learner/object-study-lab/outputs/hello-copy.bin",
        "result": "До принятия используется собственный .part."
      },
      {
        "flag": "--max-bytes N",
        "action": "Задать верхний предел тела.",
        "when": "Не заменяет ожидаемый размер и хеш.",
        "example": "--max-bytes 14",
        "result": "Известная длина и EOF проверяются отдельно."
      },
      {
        "flag": "--version-id ID",
        "action": "Выбрать предусмотренную сохранённую версию.",
        "when": "До --, не превращать строку null в отсутствие.",
        "example": "--version-id v-example",
        "result": "Обычная версия не равна mutable null-version."
      },
      {
        "flag": "-- KEY",
        "action": "Передать исходный ключ.",
        "when": "Последние два аргумента.",
        "example": "-- 'lessons/2026-11/hello +%.txt'",
        "result": "Полный GET без Range."
      }
    ],
    "situations": [],
    "source": "#s3-07-local-copy",
    "sources": [
      {
        "title": "Описание и первичный источник",
        "url": "#s3-07-local-copy"
      }
    ]
  },
  {
    "name": "object-study head",
    "purpose": "Получить сведения выбранного состояния без тела.",
    "syntax": "object-study --config FILE --target ID head [--version-id ID] -- KEY",
    "volume": "s3",
    "chapter": "s3-04-access-profiles",
    "aliases": [],
    "flags": [
      {
        "flag": "--version-id ID",
        "action": "Выбрать версию.",
        "when": "До -- KEY.",
        "example": "--version-id v-example",
        "result": "Не скачивает и не хеширует тело."
      },
      {
        "flag": "-- KEY",
        "action": "Передать исходный ключ.",
        "when": "Последние два аргумента.",
        "example": "-- 'lessons/2026-11/hello +%.txt'",
        "result": "ETag/version/checksum из ответа, не проверка всех байтов."
      }
    ],
    "situations": [],
    "source": "#s3-07-read",
    "sources": [
      {
        "title": "Описание и первичный источник",
        "url": "#s3-07-read"
      }
    ]
  },
  {
    "name": "python3 s3/labs/storage_models.py",
    "purpose": "Выполнить синтетические модели без сети.",
    "syntax": "python3 -B s3/labs/storage_models.py COMMAND",
    "volume": "s3",
    "chapter": "s3-16-exercises",
    "aliases": [],
    "flags": [],
    "situations": [],
    "source": "#s3-16-tools",
    "sources": [
      {
        "title": "Описание и первичный источник",
        "url": "#s3-16-tools"
      }
    ]
  },
  {
    "name": "python3 s3/labs/storage_models.py state-init",
    "purpose": "Создать JSON модели одного ключа.",
    "syntax": "python3 -B s3/labs/storage_models.py state-init --mode MODE",
    "volume": "s3",
    "chapter": "s3-16-exercises",
    "aliases": [],
    "flags": [
      {
        "flag": "--mode MODE",
        "action": "Выбрать unversioned, enabled или suspended.",
        "when": "Новое состояние для отдельного опыта.",
        "example": "--mode enabled",
        "result": "Пустая history и next_id=1."
      }
    ],
    "situations": [],
    "source": "#s3-16-save",
    "sources": [
      {
        "title": "Описание и первичный источник",
        "url": "#s3-16-save"
      }
    ]
  },
  {
    "name": "python3 s3/labs/storage_models.py state-step",
    "purpose": "Прочитать предыдущее состояние из stdin и вывести новое.",
    "syntax": "python3 -B s3/labs/storage_models.py state-step --event JSON",
    "volume": "s3",
    "chapter": "s3-16-exercises",
    "aliases": [],
    "flags": [
      {
        "flag": "--event JSON",
        "action": "Передать синтетическое действие put/get/delete.",
        "when": "Никаких credentials; JSON в кавычках shell.",
        "example": "--event '{\"op\":\"get\"}'",
        "result": "Результат одного модельного запроса, не receipt SDK."
      }
    ],
    "situations": [],
    "source": "#s3-16-save",
    "sources": [
      {
        "title": "Описание и первичный источник",
        "url": "#s3-16-save"
      }
    ]
  },
  {
    "name": "python3 s3/labs/storage_models.py check",
    "purpose": "Воспроизвести группу check на фиксированных входах.",
    "syntax": "python3 -B s3/labs/storage_models.py check",
    "volume": "s3",
    "chapter": "s3-16-exercises",
    "aliases": [],
    "flags": [],
    "situations": [],
    "source": "#s3-16-tools",
    "sources": [
      {
        "title": "Описание и первичный источник",
        "url": "#s3-16-tools"
      }
    ]
  },
  {
    "name": "python3 s3/labs/storage_models.py checksums",
    "purpose": "Воспроизвести группу checksums на фиксированных входах.",
    "syntax": "python3 -B s3/labs/storage_models.py checksums",
    "volume": "s3",
    "chapter": "s3-16-exercises",
    "aliases": [],
    "flags": [],
    "situations": [],
    "source": "#s3-16-tools",
    "sources": [
      {
        "title": "Описание и первичный источник",
        "url": "#s3-16-tools"
      }
    ]
  },
  {
    "name": "python3 s3/labs/storage_models.py ranges",
    "purpose": "Воспроизвести группу ranges на фиксированных входах.",
    "syntax": "python3 -B s3/labs/storage_models.py ranges",
    "volume": "s3",
    "chapter": "s3-16-exercises",
    "aliases": [],
    "flags": [],
    "situations": [],
    "source": "#s3-16-tools",
    "sources": [
      {
        "title": "Описание и первичный источник",
        "url": "#s3-16-tools"
      }
    ]
  },
  {
    "name": "python3 s3/labs/storage_models.py multipart",
    "purpose": "Воспроизвести группу multipart на фиксированных входах.",
    "syntax": "python3 -B s3/labs/storage_models.py multipart",
    "volume": "s3",
    "chapter": "s3-16-exercises",
    "aliases": [],
    "flags": [],
    "situations": [],
    "source": "#s3-16-tools",
    "sources": [
      {
        "title": "Описание и первичный источник",
        "url": "#s3-16-tools"
      }
    ]
  },
  {
    "name": "python3 s3/labs/storage_models.py listing",
    "purpose": "Воспроизвести группу listing на фиксированных входах.",
    "syntax": "python3 -B s3/labs/storage_models.py listing",
    "volume": "s3",
    "chapter": "s3-16-exercises",
    "aliases": [],
    "flags": [],
    "situations": [],
    "source": "#s3-16-tools",
    "sources": [
      {
        "title": "Описание и первичный источник",
        "url": "#s3-16-tools"
      }
    ]
  },
  {
    "name": "python3 s3/labs/storage_models.py budget",
    "purpose": "Воспроизвести группу budget на фиксированных входах.",
    "syntax": "python3 -B s3/labs/storage_models.py budget",
    "volume": "s3",
    "chapter": "s3-16-exercises",
    "aliases": [],
    "flags": [],
    "situations": [],
    "source": "#s3-16-tools",
    "sources": [
      {
        "title": "Описание и первичный источник",
        "url": "#s3-16-tools"
      }
    ]
  },
  {
    "name": "python3 s3/labs/storage_models.py scenarios",
    "purpose": "Воспроизвести группу scenarios на фиксированных входах.",
    "syntax": "python3 -B s3/labs/storage_models.py scenarios",
    "volume": "s3",
    "chapter": "s3-16-exercises",
    "aliases": [],
    "flags": [],
    "situations": [],
    "source": "#s3-16-tools",
    "sources": [
      {
        "title": "Описание и первичный источник",
        "url": "#s3-16-tools"
      }
    ]
  },
  {
    "name": "python3 s3/labs/sigv4_vectors.py",
    "purpose": "Пересчитать публичные вымышленные SigV4-векторы.",
    "syntax": "python3 -B s3/labs/sigv4_vectors.py",
    "volume": "s3",
    "chapter": "s3-06-signature",
    "aliases": [],
    "flags": [],
    "situations": [],
    "source": "#s3-06-signature",
    "sources": [
      {
        "title": "Описание и первичный источник",
        "url": "#s3-06-signature"
      }
    ]
  },
  {
    "name": "python3 s3/labs/object_operations.py",
    "purpose": "Проверить модель версий и принятой копии главы07.",
    "syntax": "python3 -B s3/labs/object_operations.py",
    "volume": "s3",
    "chapter": "s3-07-object-operations",
    "aliases": [],
    "flags": [],
    "situations": [],
    "source": "#s3-07-object-operations",
    "sources": [
      {
        "title": "Описание и первичный источник",
        "url": "#s3-07-object-operations"
      }
    ]
  }
]
