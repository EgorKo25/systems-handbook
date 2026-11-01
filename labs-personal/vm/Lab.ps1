# Windows PowerShell5.1. Run only where the existing execution policy permits.
$ErrorActionPreference = 'Stop'
$taskPython = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $taskPython) { throw 'setup-required: existing Python3.10+ is required; nothing installed.' }
& $taskPython.Source -B (Join-Path $PSScriptRoot 'lab.py') @args
exit $LASTEXITCODE
