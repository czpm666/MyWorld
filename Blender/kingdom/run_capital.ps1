# Headless build of the Asura capital. ASCII only on purpose (PS 5.1 ANSI trap).
# Examples:
#   powershell -File run_capital.ps1 -Stage full -Houses 500
#   powershell -File run_capital.ps1 -Stage mass -NoExport -NoRender
param(
    [string]$Stage = "full",
    [int]$Houses = 500,
    [switch]$NoExport,
    [switch]$NoRender,
    [switch]$Save
)
$blender = "E:\SteamLibrary\steamapps\common\Blender\blender.exe"
$script  = "E:\My World\Blender\kingdom\capital.py"
$log     = "E:\My World\Blender\renders\kingdom\build_$Stage.log"
$a = @("-b", "--factory-startup", "--python", $script, "--",
       "--stage", $Stage, "--houses", "$Houses")
if ($NoExport) { $a += "--no-export" }
if ($NoRender) { $a += "--no-render" }
if ($Save)     { $a += "--save" }
$t0 = Get-Date
& $blender $a *> $log
$code = $LASTEXITCODE
$el = ((Get-Date) - $t0).TotalSeconds
Write-Output ("exit=" + $code + " elapsed=" + [int]$el + "s")
