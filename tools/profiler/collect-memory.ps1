# Memory and handle curve of a running DayZ server, one line a minute.
#
# For the question "does something accumulate over uptime": a server that
# lags late in every restart cycle regardless of player count is not busy,
# it is growing. This records what a process can be seen growing in from the
# outside -- private bytes, working set, handles, threads, CPU seconds -- so
# the curve can be laid next to the restart cycle and the player count.
#
#   .\collect-memory.ps1                          # DayZServer_x64.exe, every 60 s, until the process exits
#   .\collect-memory.ps1 -Exe DayZDiag_x64.exe -Every 30 -Out soak.csv
#
# Reads only; nothing is attached to the process and nothing is suspended.
# Stops on its own when the process is gone, so it can be left running across
# a restart cycle and read afterwards.

[CmdletBinding()]
param(
    [int]$ProcessIdToWatch = 0,
    [string]$Exe = "DayZServer_x64.exe",
    [int]$Every = 60,
    [string]$Out = "memory-curve.csv"
)

$ErrorActionPreference = 'Stop'

if ($ProcessIdToWatch -eq 0) {
    # Same rule as collect-samples.ps1: on a diag stand the client is the same
    # executable, so prefer the process launched with -server.
    $all = @(Get-CimInstance Win32_Process -Filter "Name='$Exe'")
    if ($all.Count -eq 0) { throw "$Exe is not running; pass -ProcessIdToWatch" }
    $p = $all | Where-Object { $_.CommandLine -match '(^|\s)-server(\s|$)' } | Select-Object -First 1
    if (-not $p) { $p = $all | Select-Object -First 1 }
    $ProcessIdToWatch = [int]$p.ProcessId
}

$start = Get-Date
if (-not (Test-Path $Out)) {
    "time,uptime_min,private_mb,working_set_mb,virtual_mb,handles,threads,cpu_s" | Set-Content -Path $Out -Encoding UTF8
}
Write-Host ("watching pid {0} ({1}) every {2} s -> {3}" -f $ProcessIdToWatch, $Exe, $Every, $Out)

while ($true) {
    $proc = Get-Process -Id $ProcessIdToWatch -ErrorAction SilentlyContinue
    if (-not $proc) {
        "{0},{1:N1},gone,,,,," -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), ((Get-Date) - $start).TotalMinutes | Add-Content -Path $Out -Encoding UTF8
        Write-Host "process gone; done"
        break
    }
    # Invariant culture and F1, not N1: N1 writes thousands separators, which
    # on a 10 GB server turn "10,255.8" into two CSV fields. Learned from the
    # first live curve, 2026-09-15.
    $inv = [Globalization.CultureInfo]::InvariantCulture
    $line = "{0},{1},{2},{3},{4},{5},{6},{7}" -f `
        (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'),
        ((Get-Date) - $proc.StartTime).TotalMinutes.ToString("F1", $inv),
        ($proc.PrivateMemorySize64 / 1MB).ToString("F1", $inv),
        ($proc.WorkingSet64 / 1MB).ToString("F1", $inv),
        ($proc.VirtualMemorySize64 / 1MB).ToString("F1", $inv),
        $proc.HandleCount,
        $proc.Threads.Count,
        ([double]$proc.CPU).ToString("F1", $inv)
    $line | Add-Content -Path $Out -Encoding UTF8
    Start-Sleep -Seconds $Every
}
