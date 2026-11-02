# run_code.ps1 - send a C# snippet file to Unity MCP execute_code (scripting_ext).
# Usage: pwsh -NoProfile -File .\Tools\run_code.ps1 -File .\Tools\probe\foo.cs
# The snippet is compiled by CodeDom: no `using`, fully qualify types, `return` is optional.
param(
    [Parameter(Mandatory = $true)][string]$File,
    [int]$TimeoutSec = 300
)
$ErrorActionPreference = 'Stop'
# NOTE: cast to [string] is required - ConvertTo-Json in PS 5.1 wraps the raw
# Get-Content object into {"value":...} and the MCP bridge then rejects it.
[string]$code = Get-Content -Raw -Encoding UTF8 -LiteralPath $File
$argsJson = @{ action = 'execute'; code = $code; safety_checks = $false } | ConvertTo-Json -Compress
& (Join-Path $PSScriptRoot 'mcp_call.ps1') -Tool execute_code -ArgsJson $argsJson -Activate scripting_ext -TimeoutSec $TimeoutSec
