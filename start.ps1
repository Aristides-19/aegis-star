# Windows PowerShell 5.1+; no tmux required.
[CmdletBinding()]
param([Alias('k')][switch]$Stop)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$statePath = Join-Path $root '.aegis-processes.json'

function Stop-Aegis {
    if (!(Test-Path -LiteralPath $statePath)) { return }
    $entries = @(Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json)
    foreach ($entry in $entries) {
        $process = Get-Process -Id $entry.Id -ErrorAction SilentlyContinue
        # Do not terminate a different process that reused an old PID.
        if ($process -and $process.StartTime.ToUniversalTime().Ticks.ToString() -eq $entry.StartTicks) {
            & taskkill.exe /PID $entry.Id /T /F 2>$null | Out-Null
        }
    }
    Remove-Item -LiteralPath $statePath -Force
}

if ($Stop) {
    Stop-Aegis
    Write-Host 'Procesos de esta sesion detenidos.'
    return
}
if (!(Test-Path -LiteralPath $python)) {
    throw 'Falta .venv\Scripts\python.exe. Ejecuta uv sync primero.'
}
$terminal = Get-Command wt.exe -ErrorAction SilentlyContinue
if (!$terminal) { throw 'Se necesita Windows Terminal (wt.exe) para abrir pestanas.' }
Stop-Aegis

# Check the port before opening nine consoles. Never kill an unrelated server.
$port = if ($env:AEGIS_PORT) { [int]$env:AEGIS_PORT } else { 5000 }
$address = if ($env:AEGIS_SHIP_HOST) { $env:AEGIS_SHIP_HOST } else { '0.0.0.0' }
$probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse($address), $port)
try { $probe.Start() } finally { $probe.Stop() }

$oldSeed = $env:AEGIS_SEED
$entries = @()
try {
    if (!$env:AEGIS_SEED) {
        Push-Location -LiteralPath $root
        try {
            $env:AEGIS_SEED = & $python -c 'from common.rng import new_seed; print(new_seed())'
            if ($LASTEXITCODE -ne 0) { throw 'No se pudo generar la semilla.' }
        } finally { Pop-Location }
    }
    Write-Host "Semilla PRNG: $env:AEGIS_SEED"
    $windowName = 'aegis-' + [Guid]::NewGuid().ToString('N')
    # Terminal may reuse its own environment; pass the current AEGIS settings explicitly.
    $environmentSetup = (@(Get-ChildItem Env: | Where-Object { $_.Name -like 'AEGIS_*' } | ForEach-Object {
        "`$env:$($_.Name) = '$($_.Value.Replace("'", "''"))'"
    }) -join '; ') + '; '
    $jobs = @(@{ Title = 'Nave'; Args = '-m ship.main' })
    foreach ($sector in @('NO','N','NE','E','SE','S','SO','O')) {
        $jobs += @{ Title = "Sensor $sector"; Args = "-m sensor.main $sector" }
    }
    foreach ($job in $jobs) {
        # Encode the script to preserve spaces and special characters in paths.
        $quotedRoot = $root.Replace("'", "''")
        $quotedPython = $python.Replace("'", "''")
        $command = $environmentSetup + "Set-Location -LiteralPath '$quotedRoot'; `$Host.UI.RawUI.WindowTitle = 'Aegis - $($job.Title)'; & '$quotedPython' -u $($job.Args)"
        $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
        $title = 'Aegis-' + $job.Title.Replace(' ', '-')
        & $terminal.Source -w $windowName new-tab --title $title --suppressApplicationTitle powershell.exe -NoProfile -EncodedCommand $encoded
        # wt.exe is only the launcher. Track the actual shell inside the tab.
        $tabDeadline = [DateTime]::UtcNow.AddSeconds(15)
        $tabProcess = $null
        do {
            Start-Sleep -Milliseconds 200
            $tabProcess = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" |
                Where-Object { $_.CommandLine -like "*$encoded*" } | Select-Object -First 1
        } while (!$tabProcess -and [DateTime]::UtcNow -lt $tabDeadline)
        if (!$tabProcess) { throw "No se pudo abrir la pestana $title." }
        $process = Get-Process -Id $tabProcess.ProcessId
        $entries += @{ Id = $process.Id; StartTicks = $process.StartTime.ToUniversalTime().Ticks.ToString() }
        ConvertTo-Json -InputObject @($entries) | Set-Content -LiteralPath $statePath -Encoding UTF8
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    $ready = $false
    do {
        Start-Sleep -Milliseconds 250
        $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        $ready = $null -ne $listener
    } while (!$ready -and [DateTime]::UtcNow -lt $deadline)
    if (!$ready) { throw 'La nave no abrio el puerto dentro de 20 segundos.' }
    foreach ($entry in $entries) {
        if (!(Get-Process -Id $entry.Id -ErrorAction SilentlyContinue)) {
            throw 'Un proceso termino durante el arranque. Revisa las dependencias y la configuracion.'
        }
    }
    & $terminal.Source -w $windowName focus-tab -t 0
    Write-Host 'Nave y 8 sensores iniciados en nueve pestanas de Windows Terminal.'
    Write-Host 'Detener todos: .\start.ps1 -Stop'
} catch {
    Stop-Aegis
    throw
} finally {
    $env:AEGIS_SEED = $oldSeed
}
