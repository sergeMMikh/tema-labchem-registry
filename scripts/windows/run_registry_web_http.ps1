$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $repo "venv\Scripts\python.exe"
Set-Location $repo
& $python "manage.py" "runserver" "0.0.0.0:8080" "--noreload" "--insecure" "--settings=config.settings_local_http"
