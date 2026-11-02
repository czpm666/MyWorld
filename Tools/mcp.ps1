# mcp.ps1 — 便捷包装：把 $env:ARGS_JSON 传给 mcp_call.ps1（已实测可用的 MCP 桥客户端）。
# 存在的理由：直接在命令行拼 -ArgsJson '{"code":"...多行 C#..."}' 会被 PowerShell 的参数传递弄坏，
# 而从环境变量取字符串是可靠的（环境变量赋值不做引号解析）。
#
# 用法：
#   $env:ARGS_JSON = '{"action":"get","types":["error"],"count":20,"format":"plain"}'
#   & "E:\My World\Tools\mcp.ps1" -Tool read_console
#
#   $env:ARGS_JSON = (@{ action='execute'; code=$code } | ConvertTo-Json -Compress)
#   & "E:\My World\Tools\mcp.ps1" -Tool execute_code
param(
    [Parameter(Mandatory = $true)][string]$Tool,
    [switch]$Raw
)
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($env:ARGS_JSON)) { $env:ARGS_JSON = '{}' }
$common = "E:\My World\Tools\mcp_call.ps1"
if ($Raw) { & $common -Tool $Tool -ArgsJson $env:ARGS_JSON -Raw }
else      { & $common -Tool $Tool -ArgsJson $env:ARGS_JSON }
