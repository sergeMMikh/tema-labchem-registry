$ErrorActionPreference = 'Stop'

$sshPath = Join-Path $env:WINDIR 'System32\OpenSSH\ssh.exe'
$logDirectory = Join-Path $env:LOCALAPPDATA 'TEMA Labchem\Logs'
$logPath = Join-Path $logDirectory 'whatsapp-reverse-ssh.log'
$mutex = [System.Threading.Mutex]::new($false, 'Local\TEMA_Labchem_WhatsApp_Reverse_SSH')

if (-not $mutex.WaitOne(0)) {
    $mutex.Dispose()
    exit 0
}

try {
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    while ($true) {
        try {
            "$(Get-Date -Format o) Connecting to XPStoLab-direct" | Add-Content -LiteralPath $logPath
            & $sshPath -N -T -o BatchMode=yes -o StrictHostKeyChecking=yes `
                -o ProxyJump=none -o ProxyCommand=none `
                -o ExitOnForwardFailure=yes -o ConnectTimeout=10 `
                -o ServerAliveInterval=30 -o ServerAliveCountMax=3 `
                -R 127.0.0.1:18081:127.0.0.1:8766 XPStoLab-direct 2>> $logPath
            "$(Get-Date -Format o) SSH exited with code $LASTEXITCODE" | Add-Content -LiteralPath $logPath
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
