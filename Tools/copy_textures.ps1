$A   = "E:\My World\AssetCandidates"
$src = Join-Path $A "kenney"
$dst = Join-Path $A "分类"
$texRoot = Join-Path $dst "_贴图"
New-Item -ItemType Directory -Force -Path $texRoot | Out-Null
$packs = 0; $files = 0
foreach ($packDir in (Get-ChildItem $src -Directory)) {
  $name = $packDir.Name
  $hit = @(Get-ChildItem $dst -Directory | Where-Object { Test-Path (Join-Path $_.FullName $name) })
  if ($hit.Count -eq 0) { continue }
  $tds = @(Get-ChildItem $packDir.FullName -Recurse -Directory -Filter "Textures" -ErrorAction SilentlyContinue)
  if ($tds.Count -eq 0) { continue }
  $packs++
  foreach ($td in $tds) {
    $rel = $td.FullName.Substring($packDir.FullName.Length + 1)
    $outDir = Join-Path (Join-Path $texRoot $name) $rel
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    foreach ($f in @(Get-ChildItem $td.FullName -File -Recurse)) {
      Copy-Item $f.FullName -Destination (Join-Path $outDir $f.Name) -Force
      $files++
    }
  }
}
"贴图：$packs 个包 / $files 个文件"
