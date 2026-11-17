$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$serverPath = Join-Path $projectRoot 'venv\Scripts\waitress-serve.exe'
$logDirectory = Join-Path $env:LOCALAPPDATA 'TEMA Labchem\Logs'
$logPath = Join-Path $logDirectory 'whatsapp-webhook.log'
$mutex = [System.Threading.Mutex]::new($false, 'Local\TEMA_Labchem_WhatsApp_Webhook')

if (-not $mutex.WaitOne(0)) {
    $mutex.Dispose()
    exit 0
}

try {
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    Set-Location -LiteralPath $projectRoot
    while ($true) {
        try {
            "$(Get-Date -Format o) Starting WhatsApp webhook on 127.0.0.1:8766" | Add-Content -LiteralPath $logPath
            & $serverPath --listen=127.0.0.1:8766 --threads=4 `
                --trusted-proxy=127.0.0.1 --trusted-proxy-headers=x-forwarded-proto `
                config.wsgi:application 2>> $logPath
            "$(Get-Date -Format o) Waitress exited with code $LASTEXITCODE" | Add-Content -LiteralPath $logPath
        }
        catch {
            "$(Get-Date -Format o) $($_.Exception.Message)" | Add-Content -LiteralPath $logPath
        }
        Start-Sleep -Seconds 5
    }
}
finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
