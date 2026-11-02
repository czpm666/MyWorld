<#
    Tools/check.ps1 - compile the project and show only real C# errors/warnings.

    Uses the standalone VS2022 MSBuild/Roslyn toolchain against the csproj files that
    Unity generates, so it needs NO editor round-trip and can run while teammates work.
    Fallback: -ViaUnity recompiles through the live Editor over the MCP bridge instead
    (use that when you need Unity's own importer/asset diagnostics, not just C#).

    Usage:
      & "E:\My World\Tools\check.ps1"                 # Assembly-CSharp (runtime scripts)
      & "E:\My World\Tools\check.ps1" -Editor         # Assembly-CSharp-Editor (Editor/ scripts)
      & "E:\My World\Tools\check.ps1" -All            # both
      & "E:\My World\Tools\check.ps1" -ViaUnity       # old path: refresh + read console
      & "E:\My World\Tools\check.ps1" -Filter Tooltip # only lines matching a substring

    Exit code: 0 = no errors, 1 = errors present.
#>
param(
    [switch]$Editor,
    [switch]$All,
    [switch]$ViaUnity,
    [string]$Filter = '',
    [int]$WaitSeconds = 30
)

$ErrorActionPreference = 'Continue'
$root    = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$msbuild = 'E:\GameProject\VS2022\MSBuild\Current\Bin\MSBuild.exe'

# ---------------------------------------------------------------- Unity fallback
if ($ViaUnity) {
    $mcp = Join-Path $root 'Tools\mcp_call.ps1'
    if (-not (Test-Path $mcp)) { Write-Error "missing $mcp"; exit 2 }
    $null = & $mcp -Tool 'refresh_unity' -Args '{"compile":"request"}' 2>&1
    Start-Sleep -Seconds $WaitSeconds
    $raw = & $mcp -Tool 'read_console' -Args '{"action":"get","types":["error","warning"],"count":60,"format":"plain"}' 2>&1
    $json = $null
    foreach ($line in $raw) { $t = "$line".Trim(); if ($t.StartsWith('{')) { $json = $t; break } }
    if (-not $json) { Write-Host "[check] no console output" -ForegroundColor Yellow; exit 3 }
    $entries  = @(($json | ConvertFrom-Json).data)
    $errors   = @($entries | Where-Object { $_ -match 'error CS' })
    $warnings = @($entries | Where-Object { $_ -match 'warning CS' })
    $errors   | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    $warnings | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkYellow }
    if ($errors.Count -eq 0) { Write-Host "[check] OK (via Unity) - 0 errors" -ForegroundColor Green; exit 0 }
    Write-Host "[check] FAIL (via Unity) - $($errors.Count) error(s)" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------- MSBuild path
if (-not (Test-Path $msbuild)) {
    Write-Host "[check] MSBuild not found at $msbuild - falling back to -ViaUnity" -ForegroundColor Yellow
    & $MyInvocation.MyCommand.Path -ViaUnity -WaitSeconds $WaitSeconds
    exit $LASTEXITCODE
}

$projects = @()
if ($All)          { $projects = @('Assembly-CSharp.csproj', 'Assembly-CSharp-Editor.csproj') }
elseif ($Editor)   { $projects = @('Assembly-CSharp-Editor.csproj') }
else               { $projects = @('Assembly-CSharp.csproj') }

$totalErrors = 0
$totalWarn   = 0

foreach ($proj in $projects) {
    $projPath = Join-Path $root $proj
    if (-not (Test-Path $projPath)) {
        Write-Host "[check] $proj not found (has Unity generated it yet?)" -ForegroundColor Yellow
        continue
    }

    # Informational coverage line: Unity regenerates these csproj files itself,
    # and a .cs created since the last regeneration is not referenced by any of
    # them -- MSBuild then compiles happily and reports a FALSE GREEN.  We do
    # not fail on the mismatch (legitimate exclusions exist), but printing both
    # counts makes the trap visible instead of silent.
    $diskCount = @(Get-ChildItem -Path (Join-Path $root 'Assets') -Filter *.cs -Recurse -ErrorAction SilentlyContinue).Count
    $projCount = 0
    foreach ($q in @('Assembly-CSharp.csproj', 'Assembly-CSharp-Editor.csproj')) {
        $qp = Join-Path $root $q
        if (-not (Test-Path $qp)) { continue }
        try {
            $xml = [xml](Get-Content $qp -Raw)
            $projCount += @($xml.Project.ItemGroup.Compile | Where-Object { $_.Include }).Count
        } catch { }
    }
    Write-Host "[check] cs on disk: $diskCount / referenced by csproj: $projCount" -ForegroundColor DarkGray

    Write-Host "[check] building $proj ..." -ForegroundColor Cyan

    # MSBuild localizes diagnostics; match on the stable 'error CS' / 'warning CS' codes.
    $out = & $msbuild $projPath /t:Build /p:Configuration=Debug /nologo /v:minimal /m 2>&1

    $diag = @($out | Select-String -Pattern '(error|warning) CS\d+' | ForEach-Object { $_.Line.Trim() })

    $errs = @($diag | Where-Object { $_ -match 'error CS\d+' })
    $warns = @($diag | Where-Object { $_ -match 'warning CS\d+' })

    if ($Filter -ne '') {
        $errs  = @($errs  | Where-Object { $_ -match [regex]::Escape($Filter) })
        $warns = @($warns | Where-Object { $_ -match [regex]::Escape($Filter) })
    }

    $totalErrors += $errs.Count
    $totalWarn   += $warns.Count

    if ($errs.Count -gt 0) {
        Write-Host "  --- errors: $($errs.Count) ---" -ForegroundColor Red
        $errs | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    }
    if ($warns.Count -gt 0) {
        Write-Host "  --- warnings: $($warns.Count) ---" -ForegroundColor DarkYellow
        $warns | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkYellow }
    }

    if ($errs.Count -eq 0) { Write-Host "  OK - $proj compiled, 0 errors" -ForegroundColor Green }
}

if ($totalErrors -eq 0) {
    Write-Host "[check] OK - 0 errors ($totalWarn warning(s))" -ForegroundColor Green
    exit 0
}
Write-Host "[check] FAIL - $totalErrors error(s)" -ForegroundColor Red
exit 1
