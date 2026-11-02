# 按“类型”重新组织 Kenney 素材，方便人工翻看
# 只复制模型（.glb 一份即可，原包里有 fbx/obj/glb 三份同样的模型）+ 音频 + 界面图
# 原 kenney\ 目录不动，随时可重跑

$src  = "E:\My World\AssetCandidates\kenney"
$dst  = "E:\My World\AssetCandidates\分类"
$keepSrc = $true

# 人工看图后确认整包风格不符的包：角色/怪物类模型一律进 09
$modernPacks = @(
  "mini-characters","animated-characters-protagonists","animated-characters-retro",
  "animated-characters-survivors","blocky-characters","mini-market","tower-defense-kit"
)

# 编号 + 中文名，顺序即你翻看的顺序
$cats = [ordered]@{
  "01-角色-人物"     = @()
  "02-怪物-野兽"     = @()
  "03-建筑-墙体屋顶" = @()
  "04-地牢-洞穴"     = @()
  "05-道具-家具"     = @()
  "06-自然-植被"     = @()
  "07-界面图标"      = @()
  "08-音效"          = @()
  "09-风格不符"      = @()
  "10-原型积木"      = @()
  "99-未分类"        = @()
}

# 规则：有序，先匹配先赢。注意 ASCII 里用 -like 匹配小写文件名
$rules = @(
  # --- 现代 / 恐怖 / 科幻：直接隔离 ---
  @{ cat="09-风格不符"; pat = @("*zombie*","*vampire*","*werewolf*","*mummy*","*franken*","*ghoul*","*robot*","*mech*","*scifi*","*sci-fi*","*space*","*alien*","*gun*","*pistol*","*rifle*","*cash-register*","*atm*","*credit-card*","*defibrillator*","*hospital*","*modern*","*traffic*","*vending*","*office*","*toilet*","*bathroom*","*sink*","*mirror*","*wheelchair*") }
  # --- 地牢 / 洞穴（先于建筑，因为 corridor / room 也算建筑）---
  @{ cat="04-地牢-洞穴"; pat = @("*corridor*","*cave*","*dungeon*","*crypt*","*tomb*","*grave*","*coffin*","*sarcophagus*","*altar*","*skull*","*bone*","*candle*","*torch*","*rubble*") }
  # --- 角色 ---
  @{ cat="01-角色-人物"; pat = @("*character*","*knight*","*mage*","*wizard*","*villager*","*blacksmith*","*merchant*","*human*","*guard*","*soldier*","*archer*","*rogue*","*ranger*","*king*","*queen*","*prince*","*princess*","*monk*","*cleric*","*bard*","*noble*","*farmer*","*miner*","*cook*","*smith*","*adventurer*","*hero*","*viking*","*samurai*","*worker*","*employee*","*person*","*npc*") }
  # --- 怪物 / 动物 ---
  @{ cat="02-怪物-野兽"; pat = @("*orc*","*goblin*","*troll*","*skeleton*","*ghost*","*wraith*","*slime*","*dragon*","*wyvern*","*bat*","*spider*","*rat*","*boar*","*wolf*","*bear*","*animal*","*pet*","*cat*","*dog*","*bee*","*bunny*","*horse*","*cow*","*sheep*","*pig*","*frog*","*snake*","*lizard*","*bird*","*fish*","*crab*","*deer*","*bison*","*monster*","*demon*","*imp*","*devil*","*lich*","*beetle*","*caterpillar*") }
  # --- 建筑 / 墙体 ---
  @{ cat="03-建筑-墙体屋顶"; pat = @("*wall*","*roof*","*tower*","*battlement*","*balcony*","*building*","*door*","*window*","*floor*","*stair*","*bridge*","*gate*","*fence*","*pillar*","*column*","*chimney*","*awning*","*shutter*","*beam*","*plank*","*deck*","*dock*","*corner*","*block*","*platform*","*frame*","*arch*","*porch*","*brick*","*stone*") }
  # --- 自然 ---
  @{ cat="06-自然-植被"; pat = @("*tree*","*bush*","*grass*","*plant*","*flower*","*log*","*stump*","*mushroom*","*crystal*","*hill*","*cliff*","*dirt*","*leaf*","*rock*","*cloud*","*cactus*","*fern*","*vine*") }
  # --- 道具 / 家具（最泛，放后面）---
  @{ cat="05-道具-家具"; pat = @("*barrel*","*crate*","*chest*","*table*","*chair*","*bed*","*shelf*","*cabinet*","*bottle*","*pot*","*jar*","*food*","*apple*","*bread*","*fruit*","*basket*","*coin*","*key*","*weapon*","*sword*","*axe*","*shield*","*bow*","*arrow*","*banner*","*flag*","*lantern*","*lamp*","*bucket*","*rope*","*bag*","*sack*","*book*","*scroll*","*anvil*","*cauldron*","*furniture*","*desk*","*stool*","*cart*","*wagon*","*wheel*","*vase*","*candle*","*crown*","*ring*","*hammer*","*pickaxe*","*bucket*","*broom*","*sled*","*boat*","*sign*","*plaque*","*statue*","*fountain*","*well*") }
  # --- 补充：地块/结构件（六边形、塔防、生存包）---
  @{ cat="03-建筑-墙体屋顶"; pat = @("*tile*","*snow*","*structure*","*room-*","*ladder*","*gutter*","*panel*","*trim*","*curb*","*tube*","*pipe*","*path*","*road*","*ground*","*terrain*","*platform*") }
  # --- 补充：敌人与生物 ---
  @{ cat="02-怪物-野兽"; pat = @("*enemy*","*ufo*","*boss*","*creature*","*dragon*") }
  # --- 补充：工具与攻城器械 ---
  @{ cat="05-道具-家具"; pat = @("*tool-*","*shovel*","*pick*","*number-*","*digit*","*target*","*turret*","*siege*","*trebuchet*","*ballista*","*catapult*","*pennant*","*hanging*","*hook*") }
  # --- 补充：现代生活用品，剑与魔法世界观用不上 ---
  @{ cat="09-风格不符"; pat = @("*laptop*","*fridge*","*stove*","*microwave*","*television*","*soda*","*can-*","*styrofoam*","*ice-cream*","*lollypop*","*frappe*","*cash*","*aid-*","*defibrillator*") }
  # --- 补充：地形水系 ---
  @{ cat="06-自然-植被"; pat = @("*pine*","*river*","*water*","*sand*","*desert*","*crop*","*canoe*","*paddle*","*field*","*bush*") }
  # --- 补充：食物与杂项 ---
  @{ cat="05-道具-家具"; pat = @("*bacon*","*banana*","*celery*","*corn*","*meat*","*onion*","*plate*","*cup*","*saucer*","*rug*","*spawn*","*lever*","*lightpost*","*food*","*fruit*","*vegetable*","*cheese*","*bread*","*potato*","*tomato*","*cabbage*","*pumpkin*","*egg*","*milk*","*wine*","*ale*") }
  # --- 补充：纯几何原型件 ---
  @{ cat="10-原型积木"; pat = @("*shape-*","*prototype*","*primitive*") }
)

# 每次重跑前先清空，保证结果与统计一致（防止上一次的旧文件残留）
if (Test-Path $dst) {
  if ($dst -notlike "*\分类") { throw "拒绝删除非预期路径: $dst" }
  Remove-Item $dst -Recurse -Force
}New-Item -ItemType Directory -Force -Path $dst | Out-Null
foreach ($c in $cats.Keys) { New-Item -ItemType Directory -Force -Path (Join-Path $dst $c) | Out-Null }

$stats = @{}
foreach ($c in $cats.Keys) { $stats[$c] = 0 }
$assigned = @{}
$unmatched = New-Object System.Collections.ArrayList

function Get-Cat([string]$name) {
  $n = $name.ToLower()
  foreach ($r in $rules) {
    foreach ($p in $r.pat) {
      if ($n -like $p) { return $r.cat }
    }
  }
  return $null
}

# ---- 1) 模型：每包只取 .glb（最通用、Unity/Blender 都认）----
$models = Get-ChildItem $src -Recurse -Filter *.glb -File
foreach ($m in $models) {
  $pack = $m.FullName.Substring($src.Length + 1).Split('\')[0]
  $cat  = Get-Cat $m.BaseName
  if ($cat -in @("01-角色-人物","02-怪物-野兽") -and ($modernPacks -contains $pack)) { $cat = "09-风格不符" }
  if (-not $cat) { $cat = "99-未分类"; [void]$unmatched.Add("$pack/$($m.BaseName)") }
  # 重名保护：包名做前缀
  $outName = if ($assigned.ContainsKey("$cat/$($m.BaseName)")) { "$pack`_$($m.BaseName).glb" } else { "$($m.BaseName).glb" }
  $assigned["$cat/$($m.BaseName)"] = $true
  $outDir = Join-Path $dst "$cat\$pack"
  New-Item -ItemType Directory -Force -Path $outDir | Out-Null
  Copy-Item $m.FullName -Destination (Join-Path $outDir $outName) -Force
  $stats[$cat]++
}

# ---- 2) 音频：.ogg 原样按包放 ----
$audios = Get-ChildItem $src -Recurse -Filter *.ogg -File
foreach ($a in $audios) {
  $pack = $a.FullName.Substring($src.Length + 1).Split('\')[0]
  $outDir = Join-Path $dst "08-音效\$pack"
  New-Item -ItemType Directory -Force -Path $outDir | Out-Null
  Copy-Item $a.FullName -Destination (Join-Path $outDir $a.Name) -Force
  $stats["08-音效"]++
}

# ---- 3) 界面：ui / icon 包里的 png+svg ----
$uiPacks = @("ui-pack","ui-pack-adventure","ui-pack-rpg-expansion","fantasy-ui-borders","game-icons","game-icons-expansion","board-game-icons")
foreach ($p in $uiPacks) {
  $dir = Join-Path $src $p
  if (-not (Test-Path $dir)) { continue }
  $files = Get-ChildItem $dir -Recurse -Include *.png,*.svg -File
  foreach ($f in $files) {
    $outDir = Join-Path $dst "07-界面图标\$p"
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    Copy-Item $f.FullName -Destination (Join-Path $outDir $f.Name) -Force
    $stats["07-界面图标"]++
  }
}

# ---- 4) 索引 ----
$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("# 素材分类索引（按用途）")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("> 由 ``Tools\classify_assets.ps1`` 生成，可重跑。")
[void]$sb.AppendLine("> 每类里的子文件夹是**原始包名**，方便你回溯出处。")
[void]$sb.AppendLine("> **想快速筛角色/怪物：先看 ``E:\My World\AssetCandidates\_contact_sheets\characters_RECOMMENDED.png``（一图 6 格，全部可用项）。**（原包里同样的模型还有 fbx/obj 两份，没复制，省 147 MB）。")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("| 分类 | 文件数 | 说明 |")
[void]$sb.AppendLine("|---|---:|---|")
$desc = @{
  "01-角色-人物"="骑士/法师/村民/商人等，能用"
  "02-怪物-野兽"="哥布林/兽人/骷髅 + 各种动物"
  "03-建筑-墙体屋顶"="墙、屋顶、塔、门窗、楼梯、桥"
  "04-地牢-洞穴"="走廊、地穴、墓、火把"
  "05-道具-家具"="桶、箱、桌椅、食物、武器、招牌"
  "06-自然-植被"="树、灌木、岩石、花草"
  "07-界面图标"="UI 面板图 + 图标（png/svg）"
  "08-音效"="ogg 音效与音乐"
  "09-风格不符"="现代/丧尸/吸血鬼/科幻 —— 已排除"
  "10-原型积木"="纯几何体，做占位/拼装用"
  "99-未分类"="关键词没命中，需人工看一眼"
}
foreach ($c in $cats.Keys) {
  [void]$sb.AppendLine("| ``$c`` | $($stats[$c]) | $($desc[$c]) |")
}
[void]$sb.AppendLine("")
if ($unmatched.Count -gt 0) {
  [void]$sb.AppendLine("## 未分类清单（$($unmatched.Count) 个）")
  [void]$sb.AppendLine("")
  $unmatched | Sort-Object | ForEach-Object { [void]$sb.AppendLine("- $_") }
}
Set-Content -Path (Join-Path $dst "索引.md") -Value $sb.ToString() -Encoding UTF8

"=== 分类结果 ==="
foreach ($c in $cats.Keys) { "{0,-18} {1,5}  {2}" -f $c, $stats[$c], $desc[$c] }
""
# ---- 5) 合并人工看图精选（来自角色接触表任务，原目录 _curated）----
$cur = "E:\My World\AssetCandidates\_curated"
$pairs = @(
  @{ src = "$cur\_精选-已确认中世纪风"; dst = "$dst\01-角色-人物\_精选-已确认中世纪风" },
  @{ src = "$cur\_精选-已确认中世纪风"; dst = "$dst\02-怪物-野兽\_精选-已确认中世纪风" },
  @{ src = "$cur\_动物-方块宠物";      dst = "$dst\02-怪物-野兽\_动物-方块宠物" },
  @{ src = "$cur\_已排除-现代丧尸科幻"; dst = "$dst\09-风格不符\_已排除-现代丧尸科幻" }
)
foreach ($x in $pairs) {
  if (Test-Path $x.src) {
    New-Item -ItemType Directory -Force -Path $x.dst | Out-Null
    Copy-Item "$($x.src)\*" $x.dst -Recurse -Force
    "  已并入精选: $($x.dst)"
  }
}

"未分类: $($unmatched.Count)"
