Практикум тома V

Из корня библиотеки:
  python cache/labs/models.py
Модель работает в Windows и Linux без сторонних пакетов. model-results.json
содержит детерминированную арифметику и сценарии, не измерения серверов.

В Linux с Python 3 и установленными redis-server, redis-cli, memcached:
  python3 cache/labs/live.py
Сценарий сам создаёт временные экземпляры на loopback, проверяет команды,
завершает только созданные им процессы и удаляет их временные каталоги.
Результат — live-results.json. Параметры --redis-server, --redis-cli,
--memcached позволяют указать другой исполняемый файл.

Ручная практика:
  python3 cache/labs/live.py --manual
Redis: 127.0.0.1:16379; Memcached: 127.0.0.1:11222.
Сценарий ждёт Enter. Выполняйте команды книги в другом терминале.
Если порт занят, стенд не должен использовать действующую службу.

Расширенный стенд (Linux, OpenSSL и те же серверные программы):
  python3 cache/labs/advanced.py
Создаёт временный CA и сертификаты, проверяет ACL, mTLS, репликацию,
WAIT, переключение Sentinel и плановое переключение Redis Cluster.
Результат: advanced-results.json. Все процессы принадлежат стенду.
Порты Cluster выбираются из свободных шестёрок диапазона 17400–17895,
плюс шина со смещением 10000. Учебные пароли не предназначены для сервиса.

Алгоритмы вытеснения (Node.js, без зависимостей):
  node cache/labs/test-eviction.cjs
Результат: eviction-results.json. Это проверка моделей, не Redis/Memcached.

Границы TTL и память slab-классов (Node.js):
  node cache/labs/test-resources.cjs
Результат: resource-results.json. Проверяются подстановка границы в формулу
нагрузки и сохранение суммы байтов при округлении к блокам.

Новые самостоятельные серверные практикумы:
  python3 cache/labs/redis-semantics.py
  python3 cache/labs/memcached-semantics.py
  python3 cache/labs/persistence.py
Они требуют только свой продукт; принимают --redis-server или --memcached.
Результаты: redis-semantics-results.json, memcached-semantics-results.json,
persistence-results.json. Семантика Redis: транзакции, WATCH, списки,
Streams и ротация ACL. Memcached: байты, CAS, счётчики, срок и multiget.
Persistence: RDB и AOF, аварийная остановка собственного процесса,
восстановление из копий, включая заново прочитанный переписанный AOF.
Последний опыт не равен потере питания: ОС и накопитель остаются работающими.

Это не нагрузочный тест. Сохранность при потере питания, сетевые разделы,
SASL и встроенный прокси Memcached здесь не проверяются.
Примеры времени и объёма в тексте — отдельно обозначенные учебные условия.
