# Первичные источники блока исполнения

Сверка 1 ноября 2026 года. Тексты и числовые упражнения написаны заново.
Реальные интерфейсы привязаны к системе; собственные браузерные состояния
не приписываются настоящему ядру.

- Linux man-pages 6.19: [syscall](https://man7.org/linux/man-pages/man2/syscall.2.html),
  [read](https://man7.org/linux/man-pages/man2/read.2.html),
  [write](https://man7.org/linux/man-pages/man2/write.2.html),
  [fork](https://man7.org/linux/man-pages/man2/fork.2.html),
  [execve](https://man7.org/linux/man-pages/man2/execve.2.html),
  [wait](https://man7.org/linux/man-pages/man2/waitpid.2.html),
  [CPU affinity](https://man7.org/linux/man-pages/man2/sched_setaffinity.2.html),
  [fsync](https://man7.org/linux/man-pages/man2/fsync.2.html).
  Проверены соглашения и возвращаемые состояния, не все возможные платформенные
  ограничения этих интерфейсов. Страницы man7 сообщают свою версию в colophon.
- Linux v6.12: [entry/exit](https://docs.kernel.org/6.12/core-api/entry.html),
  [scheduling domains](https://docs.kernel.org/6.12/scheduler/sched-domains.html),
  [CFS и переход к EEVDF](https://docs.kernel.org/6.12/scheduler/sched-design-CFS.html),
  [таблица x86-64 syscall](https://github.com/torvalds/linux/blob/v6.12/arch/x86/entry/syscalls/syscall_64.tbl).
  Это названные примеры реализации. Модель PC/SP из `models.js` использует свой
  условный 32-разрядный ABI и общую защищённую область ядра, не трассу этого кода.
- [seL4: официальное введение](https://docs.sel4.systems/projects/sel4/).
  Прочитан доступный обзор границы микроядра/компонентов и ссылки на руководства.
  Полное доказательство, все конфигурации или весь reference manual не заявлены
  прочитанными; реальные seL4-приложения не запускались.
- Microsoft: [processes/threads](https://learn.microsoft.com/en-us/windows/win32/procthread/about-processes-and-threads),
  [user/kernel mode](https://learn.microsoft.com/en-us/windows-hardware/drivers/gettingstarted/user-mode-and-kernel-mode),
  [CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw),
  [context switch](https://learn.microsoft.com/en-us/windows/win32/procthread/context-switches),
  [priorities](https://learn.microsoft.com/en-us/windows/win32/procthread/scheduling-priorities),
  [multiple processors](https://learn.microsoft.com/en-us/windows/win32/procthread/multiple-processors).
  Сверены названные различия модели объектов и создания. Версия Windows для
  лаборатории не выбиралась, Windows API нативно не исполнялись.
- systemd 262, доступная редакция официальных [service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)
  и [unit](https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html).
  Нужны для отличия запуска/готовности/порядка/включения зависимостей.
  Ни один unit не установлен или запущен этой работой. При выборе другой версии
  свойства проверяются по её документации, `latest` не является закреплением.
- [clock_gettime](https://man7.org/linux/man-pages/man3/clock_gettime.3.html) и
  [Python time](https://docs.python.org/3/library/time.html): границы календарных,
  монотонных и процессорных часов. Веб-страница Python при сверке обозначала 3.15.2;
  нативный контроль использует фактический локальный Python, его версия записывается
  в отчёт. Короткий `clocks` — функциональный контраст, не аппаратный бенчмарк.

Недоступное не считается прочитанным: POSIX.1-2024 `read` по адресу
`https://pubs.opengroup.org/onlinepubs/9799919799/functions/read.html` вернул 403.
В тексте вместо ложного заявления о прочтении этого стандарта используется
доступный первичный Linux man-pages и отдельно указанные учебные допущения.

Пределы источников и проверки: нет реальной загрузки/выключения ОС, аппаратного
fault/IRQ-трассирования, KPTI/ASID/FPU-бенчмарка или проверки всех классов планирования.
Статический текст, детерминированная модель, нативный опыт и наблюдение браузера —
разные свидетельства. Конкретные фактически выполненные проверки фиксируются
в отчёте автора после стадии углубления и независимого чтения.

При углублении повторно сверены fork/execve/wait: отдельные результаты fork,
close-on-exec и редкий отказ exec после необратимого разрушения образа.
32-байтный кадр, номер READ=7 и код ошибки −14 — собственное соглашение модели;
не приписываются Linux, Windows или конкретному процессору.
