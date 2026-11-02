$A   = "E:\My World\AssetCandidates"
$src = Join-Path $A "kenney"
$dst = Join-Path $A "分类"
# 贴图：必须与 GLB 同目录（GLB 内引用 Textures\xxx.png）
$n = 0
foreach ($cat in @(Get-ChildItem $dst -Directory -ErrorAction SilentlyContinue)) {
  if ($cat.Name -like "_*") { continue }
  foreach ($packDir in @(Get-ChildItem $cat.FullName -Directory)) {
    $k = Join-Path $src $packDir.Name
    if (-not (Test-Path $k)) { continue }
    $g = Join-Path $k "Models\GLB format\Textures"
    if (-not (Test-Path $g)) {
      $cand = @(Get-ChildItem $k -Recurse -Directory -Filter "Textures" -ErrorAction SilentlyContinue)
      if ($cand.Count -eq 0) { continue }
      $g = $cand[0].FullName
    }
    $out = Join-Path $packDir.FullName "Textures"
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    foreach ($f in @(Get-ChildItem $g -File)) {
      Copy-Item $f.FullName -Destination (Join-Path $out $f.Name) -Force
      $n++
    }
  }
}
"[贴图] 随包复制 $n 个"

# 二次归类
$packRule = @{
  "food-kit"="05-道具-家具"; "furniture-kit"="05-道具-家具"; "mini-market"="05-道具-家具"
  "nature-kit"="06-自然-植被"; "mini-forest"="06-自然-植被"
  "building-kit"="03-建筑-墙体屋顶"; "modular-buildings"="03-建筑-墙体屋顶"
  "fantasy-town-kit"="03-建筑-墙体屋顶"; "castle-kit"="03-建筑-墙体屋顶"
  "tower-defense-kit"="03-建筑-墙体屋顶"; "hexagon-kit"="03-建筑-墙体屋顶"
  "prototype-kit"="10-原型积木"
}
$nameRule = @(
  @{ p='^(hedge|bush|tree|plant|flower|grass|log|stump|rock|stone|mushroom)'; d='06-自然-植被' },
  @{ p='^(stall|bench|table|chair|bed|shelf|barrel|crate|chest|pot|jar|bottle|candle|lamp|torch|blade|sword|axe|shield|bow|spear|banner|flag|coin|key|book)'; d='05-道具-家具' },
  @{ p='^(plating|border|pole|overhang|windmill|column|pillar|beam|roof|wall|floor|stairs|door|window|balcony|fence|gate|bridge)'; d='03-建筑-墙体屋顶' }
)
$left = Join-Path $dst "99-未分类"
$moved = 0
if (Test-Path $left) {
  foreach ($f in @(Get-ChildItem $left -Recurse -File -Filter *.glb)) {
    $pack = $f.Directory.Name
    $target = $null
    if ($packRule.ContainsKey($pack)) { $target = $packRule[$pack] }
    else { foreach ($r in $nameRule) { if ($f.BaseName -match $r.p) { $target = $r.d; break } } }
    if ($target) {
      $d = Join-Path (Join-Path $dst $target) $pack
      New-Item -ItemType Directory -Force -Path $d | Out-Null
      Move-Item $f.FullName -Destination (Join-Path $d $f.Name) -Force
      $moved++
    }
  }
}
"[二次归类] 迁移 $moved 个"
