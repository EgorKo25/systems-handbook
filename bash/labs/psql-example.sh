#!/usr/bin/env bash
# НЕ входит в автоматические опыты: нужен ваш PostgreSQL и явное подключение.
# Вызов: bash psql-example.sh 'произвольная строка'
if (( $# != 1 )); then
    printf 'Использование: %s ЗНАЧЕНИЕ\n' "$0" >&2
    exit 2
fi
person=$1
exec psql -X -v ON_ERROR_STOP=1 -v person="$person" <<'SQL'
SELECT :'person' AS supplied_value;
SQL
