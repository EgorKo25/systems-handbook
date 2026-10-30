POSTGRESQL: АВТОНОМНЫЕ ОПЫТЫ

Эти файлы не используют рабочую базу ДО и не устанавливают системные службы.

1. Без работающего PostgreSQL

  python3 inspect-storage.py --bundled

Читаются только приложенные файлы observed/page-0.bin, wal-insert.bin и
wal-commit.bin. Проверяются размеры, границы и CRC32C записей WAL.
Разбор относится к реальной little-endian сборке PostgreSQL 18.6.
Это не универсальный читатель всех сегментов и всех версий формата.

В общей сборке учебника дополнительно добавляется каталог byte-check:

  python3 byte-check/byte-check.py --demo

Он независимо проверяет также 16-битную контрольную сумму страницы по
исходному алгоритму PostgreSQL. См. byte-check/README.txt.

2. Настоящий частный кластер

  python3 postgres-lab.py --help
  python3 postgres-lab.py --run --pg-bin /абсолютный/путь/PostgreSQL18/bin --keep

Нужен обычный пользователь Linux/Unix, Python 3, подготовленная установка
PostgreSQL 18 с postgres, initdb, pg_ctl, psql, pg_dump, pg_restore,
pg_basebackup, pg_waldump и расширением pageinspect той же сборки.
pg_verifybackup используется, если присутствует.

Серверные бинарники не включены в этот набор: они зависят от платформы
и библиотек. Исследовать сохранённые результаты можно без них.

Без --run программа показывает справку и ничего не создаёт.
Кластер создаётся в новом /tmp/pgbook-..., TCP отключён.
Используются только собственные Unix-сокеты и собственные базы.
Перед завершением все запущенные экземпляры останавливаются.
С --keep остаются остановленные файлы и результаты. Без --keep они удаляются.

16 проверок: NULL; ограничения/ROLLBACK; JOIN/окна; каталоги; роли/RLS;
RR-снимок; RC-снимки; SSI/40001; lock_timeout/55P03; deadlock/40P01;
VACUUM/ctid; EXPLAIN; страница; WAL; pg_dump/restore;
pg_basebackup/pg_verifybackup/PITR/аварийный перезапуск.

3. Сохранённые наблюдения

observed/results.json          Настоящий запуск всех 16 опытов: PASS.
observed/page-0.bin            Страница 8192 байта собственной таблицы.
observed/page-header.json      Поля, подтверждённые pageinspect и чтением файла.
observed/wal-records.txt       Настоящий вывод pg_waldump.
observed/wal-insert.bin        Собранная запись WAL INSERT, 194 байта.
observed/wal-commit.bin        Собранная запись WAL COMMIT, 34 байта.
observed/wal-crc-verification.json  Независимая проверка двух CRC32C.
observed/decoded-storage.json  Вывод приложенного читающего декодера.
observed/explain.json          Настоящий план с ANALYZE/BUFFERS.
observed/aio-settings.txt      SHOW/pg_stat_io отдельного собственного кластера.
observed/btree-pages.txt       Настоящие bt_metap и bt_page_stats.
observed/restore-server.log    Достижение именованной точки восстановления.
observed/server-after-crash.log  Аварийное восстановление после immediate stop.

LSN, OID, PID, время и план относятся к конкретному запуску и могут отличаться.
Все проверки проводились на PostgreSQL 18.6. PostgreSQL 11/Astra в опытах не
запускался; различия описаны в тексте и требуют проверки конкретной поставки.
