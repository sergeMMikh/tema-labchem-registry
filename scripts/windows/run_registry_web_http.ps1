$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $repo "venv\Scripts\python.exe"
Set-Location $repo
& $python "manage.py" "runserver" "192.168.1.7:8080" "--noreload" "--insecure" "--settings=config.settings_local_http"
