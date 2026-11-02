"""S3 source configuration; managed registry integration belongs to main."""
CONFIG = {
  "volume": "XXVI",
  "title": "S3: именованные байты, запросы и история объектов",
  "short": "S3",
  "description": "Объектная модель, HTTP/TLS, SigV4, условные операции, версии, multipart, проверка данных и восстановление.",
  "revision": "2 ноября 2026",
  "sections": [
    [
      "Начало",
      [
        "00-route"
      ]
    ],
    [
      "Книга I · Объект и подключение",
      [
        "s3-01-object-model",
        "s3-02-http-addressing",
        "s3-03-delivery-acceptance",
        "s3-04-access-profiles",
        "s3-05-checksums"
      ]
    ],
    [
      "Книга II · Запросы и состояния",
      [
        "s3-06-signature",
        "s3-07-object-operations",
        "s3-08-conditions-ranges",
        "s3-09-version-history",
        "s3-10-multipart",
        "s3-11-listing-pagination"
      ]
    ],
    [
      "Книга III · Эксплуатация приложения",
      [
        "s3-12-policies",
        "s3-13-durability-backup",
        "s3-14-cost-performance",
        "s3-15-errors-reconciliation",
        "s3-16-exercises"
      ]
    ],
    [
      "Справочник",
      [
        "99-glossary"
      ]
    ]
  ],
  "base_terms": [],
  "term_modules": [
    "reference"
  ],
  "command_modules": [
    "reference"
  ],
  "diagram_modules": [
    "signature_diagrams"
  ],
  "illustration_links": [
    {
      "id": "s3-sigv4-bytes",
      "title": "От HTTP-байтов к подписываемым строкам",
      "label": "разбор байтов"
    }
  ],
  "blurb": "Один 14-байтовый объект проходит путь от локального источника до принятой копии; затем разберём конкуренцию, версии, части и неизвестный результат."
}
