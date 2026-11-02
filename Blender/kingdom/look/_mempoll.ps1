$out = 'E:\My World\Blender\kingdom\look\_mem.txt'
$max = 0
$seen = $false
$t0 = Get-Date
while (((Get-Date) - $t0).TotalSeconds -lt 1500) {
    $p = @(Get-Process blender -ErrorAction SilentlyContinue)
    if ($p.Count -gt 0) {
        $seen = $true
        foreach ($q in $p) {
            if ($q.PeakWorkingSet64 -gt $max) { $max = $q.PeakWorkingSet64 }
        }
    } elseif ($seen) {
        break
    }
    Start-Sleep -Milliseconds 800
}
'{0:N1} MB' -f ($max / 1MB) | Out-File -FilePath $out -Encoding utf8
