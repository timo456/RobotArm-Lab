param([switch]$AllowSourceBuild)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
New-Item -ItemType Directory -Force .tmp, .cache\pip | Out-Null
$env:TEMP = Join-Path $projectRoot '.tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $projectRoot '.cache\pip'
if (-not (Test-Path .venv\Scripts\python.exe)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 venv creation failed' }
}
& .venv\Scripts\python.exe -m pip install --only-binary=:all: packaging==26.3
if ($LASTEXITCODE -ne 0) { throw 'Cannot install wheel tag validator' }
if ($AllowSourceBuild) {
    & .venv\Scripts\python.exe scripts\prepare_wheelhouse.py --allow-source-build
} else {
    & .venv\Scripts\python.exe scripts\prepare_wheelhouse.py
}
if ($LASTEXITCODE -ne 0) { throw 'Wheel preparation failed; see README for explicit source-build option' }
& .venv\Scripts\python.exe -m pip install --no-index --only-binary=:all: --find-links .cache\wheelhouse -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Offline dependency install failed' }
& .venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
if ($LASTEXITCODE -ne 0) { throw 'Project installation failed' }
Write-Host 'Ready: .\.venv\Scripts\python.exe -m robotarm_lab gui'
