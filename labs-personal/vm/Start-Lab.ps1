# Does not change execution policy, install Python, enable Hyper-V or edit the registry.
$ErrorActionPreference = 'Stop'
$program = Join-Path $PSScriptRoot 'world.py'
$portablePython = Join-Path $PSScriptRoot '..\tools\python\python.exe'
if (Test-Path -LiteralPath $portablePython -PathType Leaf) {
    & $portablePython $program @args
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $program @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python $program @args
} else {
    throw 'Python 3.10+ is required. Prepare an approved portable interpreter at home; no installation is performed.'
}
exit $LASTEXITCODE
