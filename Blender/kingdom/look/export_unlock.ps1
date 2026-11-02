# UEXPORT: fleet lock watchdog.
#
# Two independent Blender runs (qa_diag 10:20, qa_probe 10:38) finished their
# work, wrote their logs, and then never exited -- each kept the shared
# E:\My World\Logs\_blender.lock for its full timeout while five other agents
# queued behind them.  _lock.py only evicts when the pid is DEAD, so a hung-but-
# alive process starves the fleet.
#
# This watchdog evicts only provably-stuck holders: the Blender child of the
# lock owner burns < 0.5 s CPU in 12 s AND its log has not grown for 120 s.
# Everything it does goes to Logs\ux_watch.log.
#
#   pwsh -File look\export_unlock.ps1 [-Minutes 25]

param([int]$Minutes = 25)

$ErrorActionPreference = "Continue"
$logFile = "E:\My World\Logs\ux_watch.log"
$lockDir = "E:\My World\Logs\_blender.lock"
$metaFile = Join-Path $lockDir "meta.json"

function Say([string]$msg) {
    $line = "{0} {1}" -f (Get-Date).ToString("HH:mm:ss"), $msg
    Add-Content -LiteralPath $logFile -Value $line -Encoding utf8
}

Say "watchdog start (minutes=$Minutes)"
$deadline = (Get-Date).AddMinutes($Minutes)
$killed = 0

while ((Get-Date) -lt $deadline) {
    if (Test-Path $metaFile) {
        try {
            $meta = Get-Content -LiteralPath $metaFile -Raw | ConvertFrom-Json
            $tag = $meta.tag
            $wp = Get-Process -Id $meta.pid -ErrorAction SilentlyContinue
            if ($wp) {
                $kids = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($meta.pid)" -ErrorAction SilentlyContinue |
                          Where-Object { $_.Name -eq "blender.exe" })
                foreach ($k in $kids) {
                    $bp = Get-Process -Id $k.ProcessId -ErrorAction SilentlyContinue
                    if (-not $bp) { continue }
                    $c1 = $bp.CPU
                    Start-Sleep -Seconds 12
                    $bp.Refresh()
                    $dcpu = [math]::Round($bp.CPU - $c1, 2)
                    $tagLog = "E:\My World\Logs\$tag.log"
                    $idle = 9999
                    if (Test-Path -LiteralPath $tagLog) {
                        $idle = [int]((Get-Date) - (Get-Item -LiteralPath $tagLog).LastWriteTime).TotalSeconds
                    }
                    $age = [int]((Get-Date) - $bp.StartTime).TotalSeconds
                    if ($dcpu -lt 0.5 -and $idle -gt 120 -and $age -gt 120) {
                        Say ("STUCK tag=$tag blender=$($k.ProcessId) cpu12s=$dcpu logidle=${idle}s age=${age}s -> killing")
                        Stop-Process -Id $k.ProcessId -Force -ErrorAction SilentlyContinue
                        $killed++
                    } else {
                        Say ("ok tag=$tag blender=$($k.ProcessId) cpu12s=$dcpu logidle=${idle}s age=${age}s")
                    }
                }
            }
        } catch {
            Say ("watchdog error: " + $_.Exception.Message)
        }
    }
    Start-Sleep -Seconds 8
}
Say "watchdog done, killed=$killed"
