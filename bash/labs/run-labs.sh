#!/usr/bin/env bash
# Запуск только автономных опытов из этой папки.
# Никаких сетевых соединений, прав root или системных изменений.
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || exit 1
exec python3 "$script_dir/labs.py" "$@"
