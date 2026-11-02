# object-study v1

Учебный малый Go SDK v2 client, Linux. Не AWS CLI и не набор административных команд. Endpoint/bucket/CA/учётка должны быть уже подготовлены.

```text
object-study --config FILE --target ID [--timeout 30s] COMMAND
put --source FILE (--create-only|--if-match ETAG) -- KEY
get --output NEWFILE --max-bytes N [--version-id ID] -- KEY
head [--version-id ID] -- KEY
```

Root flags строго до command, значения отдельно, не --flag=value; известный флаг один раз. Alias/help/list/delete/multipart/presign не реализованы. KEY передаётся исходным UTF-8 после --, предел1024байта, без NUL. timeout по умолчанию30s, >0 и <=15m. PUT source — обычный неизменяемый файл <=64MiB. N — неотрицательный int64 и верхний предел GET, не ожидаемая длина.

Полные JSON приведены в главе04. targets.schema_version=1, targets.ID содержит backend,endpoint,region,bucket,addressing,profile,credentials_file,ca_file. Относительные пути от config directory. Профиль — schema_version=1, profiles.NAME с access_key_id/secret_access_key и парой session_token/expires_at для временного доступа. Права credentials0600, собственный владелец. AWS chain не вызывается. CA добавляется к системным корням; проверки имени сохраняются. HTTP только literal loopback, redirect запрещён, proxy из окружения не выбирается.

## SDK и сборка

go.mod: aws-sdk-go-v2 v1.47.1, service/s3 v1.114.0, smithy-go v1.28.1; snapshot release-2026-10-02. Документированный reader toolchain Go1.27.3 linux/amd64. Первый mod tidy получает полный граф и создаёт go.sum, может добавить indirect requirements. Сохраните go.mod/go.sum, go list -m all и лицензии; затем build -mod=readonly. Ни go.sum, ни native PASS не сфабрикованы. Точный изолированный путь в главе03; не меняйте HOME, очистите GOFLAGS, используйте GOTOOLCHAIN=local/GOWORK=off/GOENV=off и private caches. Offline требует подготовленного cache и повторной сборки с GOPROXY=off.

## Передача данных и квитанция

PUT prehash до dispatch, затем ChecksumSHA256 и Metadata operation-id, один из IfNoneMatch/IfMatch. Source не менять до завершения; checksum выявляет расхождение, но открытый fd не является снимком mutable файла. SDK Standard retry MaxAttempts=3; внешнего цикла нет.

GET включает checksum mode, принимает только полный200, проверяет max, известную ContentLength и EOF/SDK validation, закрывает Body. Сначала .part в приватном output directory, sync+close, hardlink в отсутствующее final name, sync каталога. Все компоненты пути под контролем пользователя. До link ошибка не публикует final; после link ошибка directory sync может оставить полный final при exit5. Это выбранная Linux-процедура, не универсальная гарантия всех filesystems.

Receipt JSON schema_version1: target,operation,operation_id,outcome,http_status,service_code,request_id,etag,version_id,checksums,local_bytes,local_sha256_hex,attempts. Nullable поля не угадываются. version_id:null отличается от version_id:"null". Checksum scope full-object/composite/unknown и encoding сохраняются явно. HEAD local_bytes=0 не является размером объекта. attempts — вызовы SDK HTTPClient.Do, не все wire transmissions. Auth headers, URLs и credentials не выводятся; сырой SDK error не печатается.

Exit0 success;2 input/config/profile;3 последний явный ответ службы;4 network/deadline/cancel;5 local I/O/body/checksum/publication/receipt. Outcome отдельный: failed PUT после возможного Do консервативно unknown, в том числе final412 после потерянного ответа. Prehash failure до Do rejected. Подтверждённый PUT с последующей ошибкой Close source — confirmed/5. Не снимайте условие и не считайте timeout откатом.

Нет durable intent: operation ID может потеряться при гибели процесса до сохранения receipt. HEAD/GET текущего ключа не устанавливают авторство при конкуренции; non-null saved version помогает, mutable suspended null-version — нет. Историю/reconciliation выполняет отдельный принятый инструмент.

## Pending native acceptance

Получить зависимости/checksums/licenses, проверить типы и собрать, затем own AWS/MinIO/RGW profiles отдельно: put/get/head; IfNone/IfMatch conflicts; max/known-length/truncated/checksum/BodyClose; existing final; source pre/post-dispatch failure; lost reply/retry412; cancel/timeout; post-link sync failure; stdout failure. Проверка gofmt — только синтаксический разбор/формат, не этот gate.
