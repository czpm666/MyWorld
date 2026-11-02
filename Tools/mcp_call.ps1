# mcp_call.ps1 — minimal MCP (streamable HTTP) client for the Unity MCP bridge.
# Usage:  pwsh -NoProfile -File .\Tools\mcp_call.ps1 -Tool read_console -ArgsJson '{"action":"get","types":["error"],"count":"40","format":"plain"}'
#         pwsh -NoProfile -File .\Tools\mcp_call.ps1 -Tool execute_code -ArgsJson '{"action":"execute","code":"return 1+1;"}'
#         pwsh -NoProfile -File .\Tools\mcp_call.ps1 -ListTools
param(
    [string]$Tool,
    [string]$ArgsJson = '{}',
    [string]$Url = 'http://127.0.0.1:8080/mcp',
    [switch]$ListTools,
    [switch]$Raw,
    # Tool groups are enabled PER MCP SESSION, and every invocation of this
    # script negotiates a fresh session.  Pass the groups the call needs so the
    # activation happens in the same session as the call itself:
    #   -Activate scripting_ext -Tool execute_code -ArgsJson '...'
    [string[]]$Activate = @(),
    [int]$TimeoutSec = 300
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Net.Http | Out-Null

$handler = New-Object System.Net.Http.HttpClientHandler
$handler.UseProxy = $false
$client = New-Object System.Net.Http.HttpClient($handler)
$client.Timeout = [TimeSpan]::FromSeconds($TimeoutSec)

function New-McpRequest([string]$Json, [string]$SessionId) {
    $req = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::Post, $Url)
    $req.Headers.TryAddWithoutValidation('Accept', 'application/json, text/event-stream') | Out-Null
    if ($SessionId) { $req.Headers.TryAddWithoutValidation('Mcp-Session-Id', $SessionId) | Out-Null }
    $content = New-Object System.Net.Http.StringContent($Json, [System.Text.Encoding]::UTF8, 'application/json')
    $req.Content = $content
    return $req
}

function Read-SseText($resp) {
    $stream = $resp.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
    $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8)
    $sb = New-Object System.Text.StringBuilder
    while (-not $reader.EndOfStream) {
        $line = $reader.ReadLine()
        if ($line -like 'data:*') { [void]$sb.AppendLine($line.Substring(5).Trim()) }
    }
    $reader.Dispose()
    return $sb.ToString()
}

# ---- 1) initialize ----
$init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"dsh-lead","version":"1.0"}}}'
$resp = $client.SendAsync((New-McpRequest $init $null)).GetAwaiter().GetResult()
$session = $null
$vals = $null
if ($resp.Headers.TryGetValues('Mcp-Session-Id', [ref]$vals)) { $session = @($vals)[0] }
$initText = Read-SseText $resp
if (-not $resp.IsSuccessStatusCode) { Write-Output "INIT HTTP $([int]$resp.StatusCode): $initText"; exit 1 }
if ($Raw) { Write-Output "SESSION=$session"; Write-Output $initText }

# ---- 2) initialized notification ----
$note = '{"jsonrpc":"2.0","method":"notifications/initialized"}'
$client.SendAsync((New-McpRequest $note $session)).GetAwaiter().GetResult() | Out-Null

# ---- 2b) enable the tool groups this call needs, inside THIS session ----
$ai = 90
foreach ($g in @($Activate)) {
    if (-not $g) { continue }
    $act = @{ jsonrpc = '2.0'; id = $ai; method = 'tools/call'
              params = @{ name = 'manage_tools'; arguments = @{ action = 'activate'; group = $g } } } |
           ConvertTo-Json -Depth 10 -Compress
    $ra = $client.SendAsync((New-McpRequest $act $session)).GetAwaiter().GetResult()
    $ta = Read-SseText $ra
    if ($Raw) { Write-Output ("[activate $g] " + (($ta -replace "`r?`n", ' '))) }
    $ai++
}

if ($ListTools) {
    $lt = '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
    $r2 = $client.SendAsync((New-McpRequest $lt $session)).GetAwaiter().GetResult()
    $t2 = Read-SseText $r2
    $obj = $t2 | ConvertFrom-Json
    $obj.result.tools | ForEach-Object { "{0}  ::  {1}" -f $_.name, ($_.description -replace '\s+', ' ').Substring(0, [Math]::Min(90, ($_.description -replace '\s+', ' ').Length)) }
    exit 0
}

# ---- 3) tools/call ----
$argsObj = $ArgsJson | ConvertFrom-Json
$call = @{ jsonrpc = '2.0'; id = 3; method = 'tools/call'; params = @{ name = $Tool; arguments = $argsObj } } | ConvertTo-Json -Depth 40 -Compress
$r3 = $client.SendAsync((New-McpRequest $call $session)).GetAwaiter().GetResult()
$t3 = Read-SseText $r3
if ($Raw) { Write-Output $t3; exit 0 }

# Some SSE payloads come back with embedded newlines and break ConvertFrom-Json.
# That must never abort a call: the tool already ran, so fall back to raw output.
$obj3 = $null
try { $obj3 = $t3 | ConvertFrom-Json } catch { $obj3 = $null }
if ($null -eq $obj3) {
    Write-Output "RAW (json parse failed):"
    Write-Output $t3
    exit 0
}
if ($obj3.error) { Write-Output ("RPC ERROR: " + ($obj3.error | ConvertTo-Json -Depth 10)); exit 0 }
foreach ($c in $obj3.result.content) {
    if ($c.type -eq 'text') { Write-Output $c.text }
    elseif ($c.type -eq 'image') { Write-Output ("[image " + $c.mimeType + " " + $c.data.Length + " b64 chars]") }
}
if ($obj3.result.structuredContent -and -not $obj3.result.content) {
    Write-Output ($obj3.result.structuredContent | ConvertTo-Json -Depth 10 -Compress)
}
