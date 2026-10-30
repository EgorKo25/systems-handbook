#!/usr/bin/env bash
# Учебный инструмент для собственного доверенного дерева.
# Не обещает согласованного снимка файлов, меняющихся во время обхода.
# Python создаёт JSON и выполняет устойчивую публикацию одного файла.
usage() {
    printf 'Использование: %s [--dry-run] КАТАЛОГ ОТЧЁТ.json\n' "$0"
}
dry_run=0
while (( $# )); do
    case $1 in
        --help) usage; exit 0 ;;
        --dry-run) dry_run=1; shift ;;
        --) shift; break ;;
        -*) printf 'Неизвестный параметр: %s\n' "$1" >&2; usage >&2; exit 2 ;;
        *) break ;;
    esac
done
if (( $# != 2 )); then usage >&2; exit 2; fi
input_dir=$1
output_file=$2
for tool in python3 flock; do
    command -v "$tool" >/dev/null 2>&1 || {
        printf 'Нужна программа: %s\n' "$tool" >&2
        exit 127
    }
done
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || exit 1
if [[ ! -d $input_dir ]]; then
    printf 'Нет входного каталога: %q\n' "$input_dir" >&2
    exit 1
fi
if (( dry_run )); then
    printf 'План: вход=%q отчёт=%q\n' "$input_dir" "$output_file"
    exit 0
fi
# Стабильный файл блокировки не удаляется после каждого запуска.
# Каталог назначения должен существовать и быть доверенным.
exec {lockfd}>"$output_file.lock" || exit 1
flock -x "$lockfd" || exit 1
if python3 "$script_dir/collect_report.py" "$input_dir" "$output_file"; then
    printf 'Отчёт опубликован: %q\n' "$output_file" >&2
else
    status=$?
    printf 'Обработка не завершилась успешно: статус %s\n' "$status" >&2
    exit "$status"
fi
