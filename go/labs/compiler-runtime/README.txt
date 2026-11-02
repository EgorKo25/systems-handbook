Постоянный стенд оставшегося compiler/runtime/release маршрута Go.
Профиль: существующий Go 1.27.3 linux/amd64, GOAMD64=v1, обычный пользователь,
Python 3; Bash нужен для env.sh. В исходниках только стандартная библиотека.
Никаких установок или go env -w. Cgo — отдельный опыт с уже имеющимся GCC.

Из корня клона библиотеки, где существует go/labs/compiler-runtime/:
  GO=$(command -v go) || exit 1
  VOLUME="$PWD/go"
  python3 "$VOLUME/labs/compiler-runtime/prepare.py" --go "$GO" --root "$HOME/handbook-lab/go-runtime" || exit 1
  . "$HOME/handbook-lab/go-runtime/env.sh" || exit 1
При другом существующем bin/go задайте GO его абсолютным путём.
Prepare проверяет точную версию до создания root и отказывает при существующем
root, включая symlink. Ненулевой код — остановиться, прочитать stderr.
Повторный запуск не сбрасывает стенд. Продолжение: source собственного env.sh.
VOLUME при новой оболочке надо снова задать из корня клона.

Структура:
  projects/compilerlab — Ptr/Use/Borrow/Save, SSA Select/SumIndex/Mem, Mix/Ten/
    Across, AddAsm ABI0, Publish, PointerBatch/ValueBatch, ограниченная cmd/gc.
  projects/pgolab — Hot/Cold/Apply, skew99:1 и balanced1:1, TestBoth.
  projects/cgolab — C.int, []C.int, byte-buffer+len, CString/free, Handle callback;
    badpointer — отдельный намеренно отклоняемый путь, не проверка всех ошибок.
  projects/flaglab — прямой compile/link, Version и TestVersion для -X.
  projects/vetold — намеренно несовместимый maps.All при go1.22.
  projects/ch48…ch58 — отдельные полные варианты из листингов глав;
    ch54/barrier — маленький Published; ch58-asm/ch58-cgo изолированы от main.
  service — личная копия HTTP-службы с дополнительным BenchmarkGreet.
  projects/timed.py — один ограниченный процесс go test из cwd service.
  out/reports/cache/tmp/work — выходы и ускорители внутри личного root.

Главы48–59 указывают cwd, входы, флаги и код результата каждого опыта.
Блоки package/func/IR/XML — листинги/форматы, а не команды оболочки.
Существующие исходники не надо вставлять второй раз в один пакет.
Дополнительные холодные компиляции используют новые имена GOCACHE внутри root;
старые кэши и журналы сохраняются. -count=1 не делает build-кэш холодным.

observe.py — только чтение:
  python3 "$VOLUME/labs/compiler-runtime/observe.py" elf "$LABROOT/out/compiler"
Проверяет ELF64 LE, границы program headers, PT_LOAD и печатает числа/хеш.
  python3 "$VOLUME/labs/compiler-runtime/observe.py" events "$LABROOT/reports/selected.jsonl" --require 'example.org/handbook-service/internal/httpapp/TestHandler/name'
Требует run+pass имени и package pass. Код0 тестового процесса сохраняется
отдельно и тоже обязателен. Ноль выбранных тестов не удовлетворяет require.
  python3 "$VOLUME/labs/compiler-runtime/observe.py" stats "$LABROOT/reports/handler-bench.txt"
Печатает N, ns/op, median, inclusive Q1/Q3, nearest-rank p95. При N=5 p95=max;
это не промышленный latency percentile и не статистическая значимость.

release.py --root "$LABROOT" — конечный Linux-опыт без Git/служб/контейнеров:
собирает две версии, хранит SHA/manifest с revision=null,dirty=true, проверяет
отказ неверного SHA и занятого порта, переключает собственный current symlink,
показывает независимость живого процесса и имени, затем завершает своих детей.
Linux /proc нужен для сверки собственного fd socket inode с LISTEN-строкой
своего loopback-порта; неизвестный владелец ответа не принимается. Выбор порта
bind→close оставляет гонку, которая ведёт к отказу/тайм-ауту, а не ложной готовности.
Локальный HTTP-opener отключает наследование HTTP_PROXY/NO_PROXY.
Повтор при существующем releases отказывает, сохраняя отчёт. Выход0 означает
успех механизма этого опыта, а не готовность production rollout/DB restore.

Контроль исходников и runtime1.27.3: SOURCES.txt. Бинарники, кэши, профили,
WORK и фактические журналы принадлежат вашему стенду, в поставку не входят.
Снимки help старой полной справки остаются в ../toolchain-reference/.
