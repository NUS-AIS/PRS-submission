param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot '../.venv-prs-baseline/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $runtime)) { throw 'Baseline Python environment not found. Install requirements.txt and requirements-ui.txt in your environment.' }
Set-Location -LiteralPath $PSScriptRoot
Write-Host "PULMO AI: http://127.0.0.1:$Port"
& $runtime -m uvicorn pulmo_server:app --app-dir src --host 127.0.0.1 --port $Port
