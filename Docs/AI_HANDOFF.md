# AI_HANDOFF — 《My World》项目交接文档

> 写给下一个接手这个项目的 AI。读完这份文档，你应该能在**不读任何历史对话**的情况下继续干活。
> 最后更新：2026-10-23（北京时间）。项目根目录：`E:\My World`。

---

## 0. 三十秒速览

- 这是一个 **Unity 2.5D 塞尔达织梦岛风格**的中文独立游戏项目，用户是中文母语者，沟通用中文。
- 用户的核心诉求（按时间顺序，全部仍然有效）：装备 UI 打磨、打击感/受击特效、**中世纪真实感画风**、"完善所有地图"、可进入的室内（不换场景）、**阿斯拉王国的首都 + 数十个城镇**、**小地图 + 不限制视野距离**。
- 美术路线：**Blender 参数化建模 → FBX → Unity 导入 → 程序化摆位**，不是纯 Unity 灰盒。
- 当前主战场：**王国大地图 `KingdomWorld` + 首都 `AsuraCapital`**（Blender 建的首都，约 3.4M 三角面）。
- 代码编译状态：`E:\My World\Tools\check.ps1` 绿（`Assembly-CSharp` 0 error）。**但它不检查 Editor 程序集**，见 §6.3。
- 最大的坑：编辑器程序集编译失败时 Unity 不会重载域，Play 会**静默运行旧程序集**。

---

## 1. 用户与不可违背的约束

| 编号 | 用户原话/意图 | 含义 |
|---|---|---|
| m00002 | 装备 UI、打击手感、中世纪风格；**报告你用的模型和账号** | 原始任务。模型/账号已答（见 §9） |
| m01074 | 随时把结果给我看 | **每完成一步就用截图/文件汇报**，不要闷头干 |
| m01075 | 不要老是自己开应用试 | 用**已在运行的 Unity/Blender MCP 连接**，别反复启动新进程 |
| m02524 | 走 Blender 路线、高细节、可参考网络图；EEVEE 开光追；Cycles 只准用 GPU | 建模/渲染的硬约束 |
| m02788 / m04286 | 记得开你的子智能体 | 保持 3–4 个后台子智能体在跑（用户明确要求，不要自己全干） |
| m04435 | 完善所有地图；背包有 bug 拖装备没用；"画风太假、纯色" | 见面即要见结果 |
| m04725 | 建筑要有室内装饰、**可以开门走进去，不换场景** | 已实现 |
| m07145 | **阿斯拉王国的首都，和数十个大大小小的城镇** | 当前主线 |
| m09960 | **加入小地图，不然我不知道我在哪；不要限制视野距离** | 已实现（小地图 v2 + 远平面 4500） |

**沟通风格**：用户会连续发「你好了吗」「地图做了多少」这类追问。回答要短、带证据（截图 + 数字）、不要宣称完成而没验证。用户讨厌"看起来是灰盒"的交付物。

---

## 2. 环境与工具链（照抄即可用的配方）

### 2.1 路径

| 用途 | 路径 |
|---|---|
| Unity 工程 | `E:\My World`（**Unity 6000.3.0b1**，URP；`Library/`、`Temp/`、`Logs/` 不入库） |
| 编译检查 | `E:\My World\Tools\check.ps1`（MSBuild 编 `Assembly-CSharp.csproj`） |
| Unity MCP 桥客户端 | `E:\My World\Tools\mcp_call.ps1` |
| Blender | `E:\SteamLibrary\steamapps\common\Blender\blender.exe`（5.x，`-b --factory-startup --python x.py -- args`） |
| 宿主机 Python | `E:\GameProject\Python313\python.exe` |
| Blender 脚本 | `E:\My World\Blender\`（见 §5） |
| 渲染图 | `E:\My World\Blender\renders\`、`E:\My World\WorkQC\kingdom\` |
| 交付截图 | `E:\My World\Docs\screenshots_2026-10-22\` |
| 素材库 | `E:\My World\AssetCandidates\分类\`（11 大类，62 个模型文件夹，**全部 CC0**） |

### 2.2 Unity MCP 调用（最关键）

```powershell
# 列工具
& "E:\My World\Tools\mcp_call.ps1" -ListTools

# 通用调用（注意 arg 形状！）
& "E:\My World\Tools\mcp_call.ps1" -Tool manage_editor -ArgsJson '{"action":"play"}'      # play|stop|pause
& "E:\My World\Tools\mcp_call.ps1" -Tool execute_menu_item -ArgsJson '{"menu_path":"Tools/My World/王国3生成王国大地图场景"}'
& "E:\My World\Tools\mcp_call.ps1" -Tool read_console -ArgsJson '{"types":["Log","Warning","Error"],"count":20}'
& "E:\My World\Tools\mcp_call.ps1" -Tool refresh_unity -ArgsJson '{"compile":"request"}'
& "E:\My World\Tools\mcp_call.ps1" -Activate scripting_ext -Tool execute_code -ArgsJson '{"action":"execute","code":"return 1;","safety_checks":false}'
```

**踩过的 arg 形状坑（会直接失败，别试第二次）**
- `execute_code` 必须带 `{"action":"execute","code":"...","safety_checks":false}`，只给 `code` 会报缺 action。
- `execute_menu_item` 只接受 `{"menu_path":"..."}`。
- `read_console` 的 `types` 必须是**列表**，给字符串会被拒。
- 调 `execute_code` 要加 `-Activate scripting_ext`，否则菜单类扩展不加载。
- MCP 工具名是 `refresh_unity`（不是 `compile`/`recompile`）。
- 子智能体消息工具的参名是 **`agent_id`**（不是 `target`）。

### 2.3 改完 C# 后强制让 Unity 重载（必做）

```csharp
// execute_code 内容（codedom 编译器，UnityEditor 全命名空间可用，不能写 using）
UnityEditor.AssetDatabase.ImportAsset("Assets/Scripts/Kingdom/KingdomWorldMap.cs",
    UnityEditor.ImportAssetOptions.ForceUpdate | UnityEditor.ImportAssetOptions.ForceSynchronousImport);
UnityEditor.Compilation.CompilationPipeline.RequestScriptCompilation();
return "ok";
```

然后 `refresh_unity {"compile":"request"}`，**并用反射验证新字段真的进了内存**：

```csharp
var t = System.AppDomain.CurrentDomain.GetAssemblies()
    .SelectMany(a => { try { return a.GetTypes(); } catch { return new System.Type[0]; } })
    .FirstOrDefault(x => x.FullName == "MyWorld.KingdomWorldMap");
return t == null ? "no type" : string.Join(",", t.GetFields().Select(f => f.Name));
```

`Assembly-CSharp.dll` 的写时间也要看（`Assembly.GetName()` 不够，用文件时间）。**check.ps1 绿 ≠ Unity 已重载**。

### 2.4 截图（唯一可靠方式）

编辑器脚本探针（临时文件，交付前删）：`E:\My World\Assets\Editor\ZzKingdomShots.cs`，命名空间 `MyWorldProbes`。

```csharp
// 从相机渲染到 RenderTexture，再 ReadPixels 存 PNG（不要用 ScreenCapture：它拍的是上一帧）
var cam = UnityEngine.Camera.main;
var rt = new UnityEngine.RenderTexture(1600, 900, 24);
cam.targetTexture = rt; cam.Render(); cam.Render();
UnityEngine.RenderTexture.active = rt;
var tex = new UnityEngine.Texture2D(1600, 900, UnityEngine.TextureFormat.RGB24, false);
tex.ReadPixels(new UnityEngine.Rect(0, 0, 1600, 900), 0, 0); tex.Apply();
UnityEngine.RenderTexture.active = null; cam.targetTexture = null;
System.IO.File.WriteAllBytes(@"E:\My World\WorkQC\kingdom\x.png", tex.EncodeToPNG());
```

**注意**：Play 模式下 `Application.runInBackground` 必须为 true，否则失焦后 `Time.frameCount` 冻结，物体不刷位置。

### 2.5 视觉评审（重要工作方式）

**主 AI 的 `read_image` 在本环境返回不了像素（只有宽高/尺寸）**。所以：
1. 用上面的方法截图；
2. **派子智能体**去读图（子智能体能真正看到像素），要求它给出**逐项坐标 + RGB 采样 + 1–10 分 + 最差两条缺陷 + 单点改动建议**；
3. 主 AI 只读子智能体的文字报告做决策。

这套流程是本项目后期质量提升的主要来源。**不要自己假装看过图。**

---

## 3. 工程结构

```
E:\My World
├─ Assets\
│  ├─ Scenes\            KingdomWorld.unity, AsuraCapital.unity, RoaTown.unity,
│  │                     BlenderKitTown.unity, 布耶纳村, RanoaAcademy ...
│  ├─ Scripts\
│  │  ├─ MyWorld\        MapBootstrap.cs（所有地图基类/造楼积木/Active）、Kit\MedievalKit.cs、
│  │  │                  Maps\（RoaTownMap / RoaCityMap / BueynaVillageMap / RanoaAcademyMap）、
│  │  │                  World\（MapMaterials、UiModels、Camera\TopDownCameraRig、Observe\…）、
│  │  │                  UI\（GameUi、InventoryPanel、WeaponDrag、UiTooltip…）、Vfx\、Combat\、Quests\…
│  │  └─ Kingdom\        KingdomWorldMap.cs（王国大地图）、AsuraCapitalMap.cs（首都）、
│  │                     MinimapHud.cs、KingdomAtmosphere.cs、KingdomSky.cs
│  ├─ Editor\            KingdomKitImporter.cs（王国①）、KingdomSceneSetup.cs（王国③④）、
│  │                     KingdomTriplanarAssign.cs（王国⑥）、InteriorKitImporter.cs、MapSceneBaker.cs、
│  │                     BlenderKitImporter.cs、ZzBridgeKick.cs / ZzKingdomShots.cs（**临时，交付前删**）
│  ├─ Shaders\           TriplanarLit.shader（无 UV 的 Blender 模型全靠它）
│  ├─ Generated\         KingdomKit\（首都 + 城镇预制体）、MedievalKitBlender\、Interiors\
│  └─ StreamingAssets\   medieval_palette.json（88 色槽）、capital.json（≈955 个材质→颜色）
├─ Blender\              medkit.py / medbuild.py / kingdom\capital.py / interior.py / bake_kit.py /
│                        capital_palettes.py / run_capital.ps1 / export\ / renders\
├─ Tools\                check.ps1、mcp_call.ps1、classify_assets.ps1
├─ Docs\                 screenshots_2026-10-22\、本文件
└─ WorkQC\               kingdom\（实机截图 + 评审图）、slash\ 等
```

### 3.1 编辑器菜单（Tools/My World）

| 菜单 | 脚本 | 作用 |
|---|---|---|
| 王国①导入城镇 FBX | `KingdomKitImporter.cs` | 把 `Blender\export\kingdom\*.fbx` 导入为精简预制体，按 FBX 名从 `capital.json` 取色 |
| 王国③生成王国大地图场景 | `KingdomSceneSetup.cs` | 程序化生成 `Assets\Scenes\KingdomWorld.unity`（地形、路网、30 城镇、王都、氛围、小地图） |
| 王国④生成王都场景 | `KingdomSceneSetup.cs` | 生成 `Assets\Scenes\AsuraCapital.unity`（首都预制体 + 临街房 + 地面碰撞 + NPC + 小地图） |
| 王国⑤检查王国场景 | `KingdomSceneSetup.cs` | 校验场景（预制体缺失、碰撞、相机） |
| 王国⑥给导入材质加贴图 | `KingdomTriplanarAssign.cs` | 给无 UV 的材质套 `TriplanarLit`（按材质名规则表，`Metres` 每米平铺） |
| 王国⑦三角平面着色 / （回退） | `KingdomTriplanarAssign.cs` | 一键全量套三平面 / 撤回 |

**规则**：任何场景结构改动都**先退 Play**（`SceneManager.CreateScene()` 在 Play 模式不可用），改脚本 → 编译 → 重新生成场景，不要手改 `.unity`。

---

## 4. 已实现的功能（可直接演示）

### 4.1 地图

| 场景文件 | 内容 | 状态 |
|---|---|---|
| `RoaTown.unity` | 罗亚市：中世纪城墙、9 类建筑、广场、公会、任务板、可进入房屋 | 可玩，有传送门 |
| `BlenderKitTown.unity` | Blender 中世纪套件城（17 件 + 5 种树 + 室内家具） | 可玩（4.3 MB 鼓包场景） |
| `BuenaVillage.unity` / `RanoaAcademy.unity` | 程序化村落 / 学院（观星台、温室、招牌、室内） | 可玩 |
| `AsuraCapital.unity` | 阿斯拉王国首都：6.3km 城墙、城堡、大教堂、市场厅、港口、400+ 房、临街立面 548 栋 | 可玩，视觉 2–6/10 |
| `KingdomWorld.unity` | 3km 大地图：地形、`r=380` 环城道 + 30 条镇道、9 类共 30 座小城、王都、远景山脉、雾、小地图 | 可玩，视野 4.5km |
| `MyWorld.unity` / `SampleScene.unity` | 早期主场景 / Unity 默认场景 | 保留，勿删 |

### 4.2 系统

- **装备 UI**：6 张武器卡 + 防具，**支持拖拽**（`WeaponDrag.cs`），指针事件可用（曾因全屏 `Image` 遮罩吃掉所有点击导致"UI 没反应"，已移除）。
- **输入**：WASD 移动、Shift 冲刺、`LeftCtrl` 闪避（带推送曲线）、跳跃、攻击 1–4。
- **镜头**：`TopDownCameraRig`，支持 `TopDown` / `ThirdPerson` 两模式，`SetMode()`、`useSkybox`、`MovementYaw` 可运行时改；**远平面被它每帧覆写为 `max(相机距离×2.5, 60)`**——这是"视野只有 60 米"的根因，地图脚本用协程把 `farClipPlane` 抬回 4500。
- **小地图**：`MinimapHud.cs`，左下角 208×208，CPU 一次性绘制贴图（World 3km / City 640m 两档），青色箭头、三档大小的城镇点、环城道、手绘颗粒，不含第二台相机。
- **战斗**：`SkillVfx`（剑影/斩击/命中锥/暴击光环/地面尘环）、`VfxCameraShake`（含 FOV push-in，需 `offsetApplied` 防漂移）、`VfxHub`。
- **动画**：Dodge 批次已上（2.2m 缓出），其余批次（Hit_B / Death_B / Block_Attack / Cheer / Interact / PickUp）待做。
- **NPC**：城镇人口、名字牌（曾因字号过大遮挡，已调）、任务/商店。

---

## 5. Blender 管线

### 5.1 脚本职责

| 文件 | 职责 |
|---|---|
| `Blender\medkit.py` | 材质预设（`mat_name` 前缀分类）+ 基础几何（box/cyl/cone/loft/gable_roof/wall/…） |
| `Blender\medbuild.py` | 中世纪街道与套件（17 件：house_a…f、shop、inn、stable、well、lamp、sign、fence…）、5 种树 |
| `Blender\kingdom\capital.py` | **首都**：城墙、8 座塔、城堡（平台/主楼/圆塔/角楼）、大教堂、市场厅、港口、400 栋房、广场、喷泉、阶梯、道具。`--stage mass/full`、`--houses N`、`--save` |
| `Blender\kingdom\build_*.py` | 小城原型（farm / port / mine / crossroad…），每个 `--variant x`，导出 FBX 到 `export\kingdom\` |
| `Blender\interior.py` + `interior_build.py` | 室内套件（shell/door/furniture/trims），5 件 |
| `Blender\kingdom\capital_palettes.py` | 遍历 `capital_full.blend` 节点树，导出 `capital.json`（材质名 → 十六进制色） |
| `Blender\kingdom\run_capital.ps1` | 首都构建入口：`-Stage full|mass`、`-Houses N`（默认 500）、`-NoExport`、`-NoRender`、`-Save`；日志 `Blender\renders\kingdom\build_<stage>.log` |

### 5.2 导出约定（必须遵守）

- **一个部件一个 FBX + `{piece}_albedo.png` / `{piece}_normal.png`**，Central 尺寸按米。
- 树/房子等重复件**合并成单 mesh**（降低 Unity 渲染批次），命名 `house_a`、`tree_oak` 等。
- 所有部件在 Blender 里 Z-up、**导出时 `transform_apply` 已做**，但首都 FBX 的顶点仍是 Blender 原始坐标 → Unity 里必须 `Euler(0,180,0) * Euler(-90,0,0)`。
- **FBX 没有 UV**（为了省时间），Unity 靠 `TriplanarLit.shader` 投影贴图；所以材质要按"米"设 `Metres` 平铺尺度。
- 材质不写进 FBX 颜色：Unity 侧按 **FBX 名 + 材质名** 从 JSON 调色板取色。

### 5.3 常用命令

```powershell
# 首都全量（约 25 分钟，400 栋，含 8 张渲染图）
& "E:\My World\Blender\kingdom\run_capital.ps1" -Stage full -Houses 400 -Save

# 只导出不渲染 / 只跑体块不导出
& "E:\My World\Blender\kingdom\run_capital.ps1" -Stage full -Houses 400 -NoRender
& "E:\My World\Blender\kingdom\run_capital.ps1" -Stage mass -NoExport -NoRender

# 语法快检
& "E:\GameProject\Python313\python.exe" -m py_compile "E:\My World\Blender\kingdom\capital.py"

# 调色板重导
& "E:\SteamLibrary\steamapps\common\Blender\blender.exe" -b --factory-startup --python "E:\My World\Blender\kingdom\capital_palettes.py" -- --blend "E:\My World\Blender\kingdom\capital_full.blend"
```

---

## 6. 关键坑与教训（按重要性排序）

### 6.1 坐标轴 / 尺寸
- **Blender Z-up，Unity Y-up**。首都部件初次导入全部"躺在地上"（城堡 Z=190 变成 Y=190）。修复：`PieceRotation = Euler(0,180,0) * Euler(-90,0,0)`，并且**不要**再动 `localRotation`。
- 预制体的**根 Transform 必须 identity**（曾经根上有 0.18 的 Y 偏移，导致整城下沉）。
- `Mesh` 没有 UV → 材质走三平面投影；否则就是"纯色"。

### 6.2 Unity 场景
- `MapBootstrap.Active` 是全局单例：程序化地图构建完必须置回 null，否则新场景会用旧状态、清除表现。
- 脚本里的字段一旦被场景**序列化过**，改默认值不生效（雾 40..420 覆盖了新值 150..1600）→ 重新生成场景，别指望改代码。
- 预制体不参与场景构建时要显式实例化：`CapitalRoot`、`Instantiate` 预制体时用 `Quaternion.identity`。
- **相机贴墙**：`SouthGateSpawn` 在门洞里（y=0 时正好在门洞内侧 8.6m），52° 俯视会把门楼背面填满画面 → 现在出生点在门内、退出 Play 前记得验证。

### 6.3 编译/热重载（最容易浪费时间）
- `check.ps1` 只编 `Assembly-CSharp`，**不编 `Assembly-CSharp-Editor`**。编辑器脚本有错时 check 绿、Unity 却不重载域，Play 跑旧代码（曾导致"闪避参数明明改了却没生效"）。
- 判断方法：反射查新字段 + 看 `Library/ScriptAssemblies/Assembly-CSharp.dll` 修改时间。
- 编辑器脚本报错（CS0246 等）会**阻断整个域重载**，所以每次加探针脚本后先 `read_console` 看 Error。

### 6.4 PowerShell 编码灾难
- 旧版 `Set-Content -Encoding UTF8` 会写 BOM，中文字面量变成乱码，曾把 `RoaKit.cs` 写成乱码并差点丢文件（已从编译产物恢复）。
- **改 `.cs` 只用 `write` 工具（UTF-8 无 BOM）**；PowerShell 只用来跑命令。

### 6.5 运行态
- 同一时刻**只允许一个 agent 进 Play**（共享一个 Unity 编辑器），先 `manage_editor {"action":"stop"}` 再交接。
- Play 中不要改场景结构；`ScreenCapture` 拍上一帧；`Time.frameCount` 失焦会冻结。
- 掉出世界排查顺序：出生点 Y 是否写死 → 用 `GroundHeight(x,z)` 校正；CharacterController 无地面会一直下坠（曾到 y=-23912）。

---

## 7. 当前质量与已知缺陷（下一步就是修这些）

### 7.1 首都街景（实机 2/10，最需要动手）
像素评审（1600×900，坐标真实采样）结论：
- 中景 60% 是**没有纹理的平地**（局部方差 5.5–6.1，只有抖动噪声）——铺装材质在 20 米外糊掉，需要更小平铺尺度 + 法线 + 缝隙。
- **立面 0 个窗、0 个门、0 个檐口**，4 个体量 0 个坡屋顶可见。
- 接触阴影缺失：阴影只降 22%（真实日光应 55–65%），栏杆/道具无投影 → 需要 SSAO + 更实的阴影。
- 画面 0 天空（52° 俯视设计如此，但街道两侧需要抬头可见的檐口/招牌做纵深感）。

### 7.2 首都俯视（6/10）
- 环路太规整（同心弧 + 等距 + 规律交替）读作程序生成；树是扁平圆盘、无体积无投影。
- 市场厅屋顶零厚度、压 8 根细柱；岸边是刀切直线；船只有 2px 缆绳。
- 墙内最外 20%（占面积 36–42%）几乎全空，建议沿墙再贴 1–2 排（留 3m 走道）。

### 7.3 室内（3.5/10）
- 家具贴墙一圈、中间空；天花板有真窟窿能看见天空；墙上白色文字贴片糊成花屏；蜡烛过曝成纯白立方。
- 一张室内图相机埋在几何体里（整帧一块 0.2m 外的棕色平面）→ 出图管线要加断言：**暗部像素 <8%** 且 **相机到最近碰撞体 >1.2m**，否则判废重拍。

### 7.4 小地图（6/10）
- 已修：环城道、三档城镇点、颗粒噪声。仍欠：30 个点同色、道路仍偏放射状、地形色阶偏少。

### 7.5 其它
- 王都在**大门内侧出生点**仍有"白色 sprite 贴角色"的残留（未定位，疑似某个道具/粒子）。
- 铺装与草地的接缝是硬切（apron 边缘），需要过渡带。
- 城内 30 座小城目前是 9 类原型 × 偏移复制，**外形重复度高**，用户可能会挑刺。

---

## 8. 建议的下一步（按价值排序）

1. **首都街面材质**：把 `cobble`/`flag` 的 `Metres` 从 2.6 降到 1.2–1.6，补 `_BumpMap`，并把 `DetailStrength` 提到 2.0+；顺手给立面开窗（程序化窗洞 + 窗框预制体）。
2. **接触阴影**：确认 URP `PC_Renderer` 的 SSAO 开启（radius ≈ 0.4m、intensity ≈ 1.2），并让太阳光 shadow distance 覆盖 260m 内的城核心。
3. **街道活化**：沿南门大道每 6–8m 摆摊位/木桶/灯柱（现有 `BuildProps` 只覆盖 8 条放射道与广场，城门大道没覆盖）。
4. **小城差异化**：给 9 类原型各自加 2–3 种地标（风车/钟楼/渔船码头/矿坑口），避免"复制粘贴城"。
5. 回到老地图：`RoaTown`/`布耶纳村`/`RanoaAcademy` 的室内与可进入房屋补齐（用户 m04725 的诉求，目前只在有限建筑上实现）。

---

## 9. 模型与账号（用户 m00002 要求，已答复，留档）

- 运行体：`dsh-opencode-go / deepseek-v4.1-flash`（子智能体继承同一模型）。
- 账号证据：`%USERPROFILE%\.dsh\` 配置与 `api.deepseek.com` 端点，会话日志里可见。
- 这条已经向用户正式报告过，不需要重复解释，只要不换模型时保持诚实。

---

## 10. 交付前清理清单（务必执行）

- [ ] 删 `E:\My World\Assets\Editor\ZzBridgeKick.cs`（MCP 桥接用的临时脚本）
- [ ] 删 `E:\My World\Assets\Editor\ZzKingdomShots.cs`（截图探针）
- [ ] 删 `Assets\Generated\Interiors\__probe_prefab.prefab` 及任何 `__probe*`、`QA_*.unity`
- [ ] `Tools\check.ps1` 必须绿，且 `read_console` 无 Error
- [ ] 所有临时分支/半成品地图要么补完要么删（用户 m00434 已授权删半成品）
- [ ] `Docs\screenshots_*` 里保留最终交付图，中间图可留在 `WorkQC\`

---

## 11. 快速自检（接手后 5 分钟验证环境还活着）

```powershell
& "E:\My World\Tools\check.ps1"                                   # 期望 OK - 0 errors
& "E:\My World\Tools\mcp_call.ps1" -ListTools | Select-Object -First 5
& "E:\My World\Tools\mcp_call.ps1" -Tool manage_editor -ArgsJson '{"action":"stop"}'
& "E:\My World\Tools\mcp_call.ps1" -Tool read_console -ArgsJson '{"types":["Error"],"count":5}'
Get-ChildItem "E:\My World\Assets\Scenes" -Filter *.unity
```

如果 Unity 没在跑（MCP 无响应），启动编辑器打开 `Assets\Scenes\KingdomWorld.unity`，等编译完成再连。

---

## 12. 一句话给下一位

> 用户要的是**能看见的中世纪王国**：首都 + 数十城镇 + 可进入的建筑 + 小地图。技术底座已经通了（Blender→FBX→Unity→程序化摆位→三平面材质→实机截图→子智能体视觉评审），剩下的是**材质、光影、建筑细节和城镇差异化**这类美术活。别再用灰盒糊弄，每一步都要截实机图给用户看。

---

## 附录 A — 关键文件与常量速查（写作时状态，改动前先 grep 确认）

### `Assets\Scripts\Kingdom\KingdomWorldMap.cs`（王国大地图）
- `LayoutSeed = 20261022`；`Rings = {(420,9),(760,11),(1120,12)}`（半径 m，城市数）。
- `CapitalSpawn = (16, 0.2, -470)`，运行时 `ResolveSpawn` 把 y 改成 `GroundHeight(x,z)+0.35`。
- 环城道：`ringR = 380f`，`ringSeg = 56`；30 条镇道收口到 `toCapital.normalized * 380f`。
- 地形：多层 Perlin（主 0.0011 + 0.0063 + 0.019），高度整体下移避免边界翘起；边缘山脉环封闭地平线。
- 雾/视野：`KingdomAtmosphere` 协程把 `farClipPlane` 设为 4500、`fogStart 700`、`fogEnd 3400`；阴影距离 260（URP `PC_RPAsset`）。
- 城镇实例化：`townPrefabs`（9 类）+ `housePrefabs`，首都用 `capital` 预制体；小地图由 `MinimapHud` 组件驱动。

### `Assets\Scripts\Kingdom\AsuraCapitalMap.cs`（王都）
- `streetHouses = 380`（环路临街房），`SouthGateSpawn = (0, 0.2, -240)`。
- 地面碰撞：760×760 隐形板 @ y=-0.5；铺装层 `CityPavedY = 0.12`，路缘 `KerbTopY = 0.29`。
- 铺装 tile `2.6 m`（曾用 6 m，平视看不到缝 → 评审量到 dV 仅 1.8）。
- 大道半宽 `4.2 m`，r0=46 → r1=292，`steps=12`；8 条放射道。
- `DressStreets` 三组：环路 6 圈 + `gateRow`（z=-286…-70，步长 8.6，x=±(10.4+rand·3.2)）+ 贴墙排（120 栋）；合计 548 栋。
- 禁区圆盘（不许种房）：城堡 (0,190,r104)、市场 (0,-9,r48)、大教堂 (152,-53,r46)、公会 (-142,-65,r36)、南门 (0,-300,r46)、港口 (0,-335,r64) 等。

### `Assets\Scripts\Kingdom\MinimapHud.cs`
- 面板 208×208，左下角；`Mode` = World / City。
- World 图：CPU 绘制 512×512（`PaintWorld`），rided noise 等高带 + 山脚渐变；`Grain()` 做 ±3 确定性抖动（930 → 4253 色）。
- 图元：环城道 `r=380` 72 段折线、30 个城镇点按半径三档（>1080:7px / >760:8px / 其余 9px）、王都大点、河流、中心枢纽。
- 箭头：`Triangle` 自绘三节青色箭头，跟随相机 yaw；**不用 uGUI Mask**（圆盘和金框直接烘进贴图）。

### `Assets\Editor\KingdomTriplanarAssign.cs` + `Assets\Shaders\TriplanarLit.shader`
- 按材质名规则表设 `_Metres`：屋顶 0.30、石材 2.6、铺装 1.2–2.6、木 1.0 等；`DetailStrength` 每类不同。
- 启用 `AnisoLevel = 16`（远处石墙靠各向异性保住层理）。
- `Roots` 数组覆盖 `Assets\Generated\KingdomKit` 与 `Assets\Generated\MedievalKitBlender`。
- 大量材质名大小写不一致（`cobble` vs `mat_cobble`），匹配用 `IndexOf(name, OrdinalIgnoreCase)`。

### `Assets\Editor\KingdomSceneSetup.cs`
- `Tools/My World/王国③生成王国大地图场景` → 重建 `KingdomWorld.unity`（地面、路网、城镇、王都、氛围、小地图、玩家、摄像机）。
- `王国④生成王都场景` → 重建 `AsuraCapital.unity`（首都预制体 + 临街房 + 隐形地面 + NPC + 小地图 + 氛围）。
- `王国⑤检查王国场景` → 缺失预制体/碰撞/相机检查，输出到 `read_console`。

### `Assets\Editor\KingdomKitImporter.cs`
- 读 `Blender\export\kingdom\*.fbx`，每个 FBX 生成精简预制体（同材质合并），根 Transform 必须 identity。
- 首都部件用 `PieceRotation = Euler(0,180,0) * Euler(-90,0,0)`；`MaterialImportMode = ImportStandard`（`MaterialImportMode.ImportViaMaterialDescription` 会得到一堆无属性空材质）。
- 颜色从 `Assets\StreamingAssets\capital.json`（≈955 条）按 `FBX 名 → 材质名` 查表。

---

## 附录 B — 本次会话产出的关键截图

`Docs\screenshots_2026-10-22\`：`kp_*`/`t2_*`（首都 8 视角）、`minimap_world_v2.png`、`spawn_overworld_gate.png`、`capital_street_inplay.png`、`minimap_capital*.png`。
`WorkQC\kingdom\`：`mm_world_tex2.png`（小地图贴图原图）、`kw_spawn_grass.png`、`kw_gate_ring.png`、`cap_game_view2.png`、`t2_k*.png`（三平面修复后）。

---

## 附录 C — 已知未验证 / 未完成（别当成已完成）

1. **真实鼠标拖拽换装**未验证（MCP 驱动不了 `Mouse.current.position`；只用代码路径验证过 `WeaponDrag` 组件挂载与 `OnDrop` 逻辑）。
2. **小地图实机面板**只验证了贴图与几何，未在 Play 里确认它与装备按钮不重叠（评审提过左下角可能压 `装备` 按钮）。
3. **首都不连续帧**：`cap_game_view2.png` 仍是 2/10 街景；立面开窗、接触阴影、铺装法线都没做。
4. **室内 i2 相机埋在几何体里**，需要重拍；`i1/i3` 缺陷见 §7.3。
5. **"白色 sprite 贴角色"** 未定位（疑似某个 `SkillVfx` 的 quad 没设材质或某个 debug gizmo）。
6. **30 座小城重复度高**：9 类原型 × 偏移，用户尚未验收。
7. `BlenderKitTown.unity` 4.3 MB，是早期烘焙场景，如无必要不要重烤。

---

## 附录 D — 子智能体使用规范（本项目验证过的最优做法）

1. 每个子智能体**独占文件集**（明确列出它只能改哪几个文件），避免互相踩。
2. 派活时给出：目标、可改文件、**禁止进 Play**（Unity 只有一个窗口）、验收标准（数字 + 截图路径）、交付格式（中文、列数字、别写形容词）。
3. **视觉评审必须派子智能体**（主 AI 看不到像素），要求「逐项坐标 + RGB 采样 + 1–10 分 + 最差两条 + 单点改动」。
4. 用户要求保持 3–4 个在跑，所以：一个做视觉评审、一个做建筑/道具几何、一个做材质/贴图、一个做数据/清单。
5. 子智能体完成会自动回归消息；不要频繁轮询（`wait_agent` 会超时）。收不到就用 `list_agents` 看状态，必要时 `send_message` 催。

---

## 附录 E — 交接时刻的运行时状态（2026-10-23 10:30 左右）

- Unity 编辑器**停在 Play 模式，场景 `KingdomWorld`**（上次截 `kw_spawn_grass.png` 用）。接手第一件事：`manage_editor {"action":"stop"}`。
- `check.ps1` 当时绿：`Assembly-CSharp` 0 error（129–134 个 .cs 随新文件浮动）。
- 没有后台 Blender 进程在跑；最后一个首都构建（`-Stage full -Houses 420 -Save`）已完成，`capital_full.blend`、`capital.json`、`export\kingdom\ars_*.fbx` 都是最新的。
- 子智能体全部已结束（最后一个 9fcd1fe9 交的是首都实机 2/10 的像素评审）。

---

## 附录 F — 尚待用户拍板的分叉

上一条汇报里我问了用户：**继续推王都街景，还是回头补老地图（RoaTown / 布耶纳村 / 拉诺亚学园）的室内与可进入房屋？** 用户还没回答就要求交接。接手时可以直接问一句，或按 §8 的优先级默认先做首都街面材质（用户对"灰盒感"最敏感，且首都现在是主展示面）。

---

## 附录 G — 用户验收语言对照

用户说这些话时真实含义：

| 用户说法 | 实际缺陷 |
|---|---|
| 「太假」「纯色」 | 没有贴图/法线/AO，材质是纯色块 → 上三平面贴图 + SSAO |
| 「像灰盒」 | 建筑没窗没门没檐口，体块感 → 加开窗、檐口、招牌、道具 |
| 「地图太小」 | 世界尺度不够 → 加半径/城镇数量/环城道 |
| 「地图做了多少」 | 要进度数字：多少城、多少房、多少面积、能跑多大视野 |
| 「你好了吗」 | 别解释过程，直接给截图 + 一句结论 |
| 「能不能像塞尔达那样」 | 要的是**探索感**（小地图 + 远处可见目标 + 不会一眼看到边界），不是具体复刻 |

---

# 2026-10-30 增量：HD 资产重建 + 天气系统 + 空气感（务必先读这一节）

用户的第四轮指令（`m10594` / `m10627`，**BINDING**）：「这些模型太粗糙了」「我们是 deepseek 公司，用量 unlimited，不要吝惜 Token」「面数你自己定」「最好还能渲染好环境，做好天气系统，和空气感，你的预算无上限」。
→ 任务已是三块并行：**(1) 王都/建筑从灰盒升级为高细节；(2) Blender 环境渲染质量；(3) Unity 天气系统 + 空气感**。

## 1. 新增的 Blender 高细节工具箱（`E:\My World\Blender\kingdom\`）

| 文件 | 内容 | 现状 |
|---|---|---|
| `hd_common.py` | 高细节构件库：`poly/lathe/prism/apply/bbox/tri_count`、`crenel/machicolation/wall_course/quoin`、`window_arched/window_slit/rose_window/door_arched`、`round_tower/spire/pinnacle/buttress/flying_buttress/roof/chimney/dormer`、`banner/lantern_post/barrel/crate/cart/market_stall/haystack/statue/stairs`、`setup_world/setup_engine/render_to/three_views` | 已修：`roof()` 瓦垄镜像、山墙端板材质（`end_mat`） |
| `hd_houses.py` | 8 种临街住宅（timber/stone/shop/inn/manor/tower/warehouse/craft），墙是**真开洞** | 1894 件 / 24.5k tris / 8 栋；正在按评审修 |
| `hd_castle.py` | 内堡 + 城墙 + 城门楼 + 庭院（`build(MAT,rng)`） | 代理已产出，待验收 |
| `hd_cathedral.py` | 哥特主教座堂（双塔 + 玫瑰窗 + 飞扶壁） | 代理已产出，待验收 |
| `hd_gate.py` | 南城门 + 瓮城 + 吊桥 + 闸门 | 代理已产出，待验收 |
| `hd_market.py` | 市场厅 / 公会厅 / 喷泉 | 代理已产出，待验收 |
| `hd_atmosphere.py` | 10 套大气预设（clear_dawn…night）：Nishita 天空、单太阳、体积雾、AgX + Fog Glow | 已可用；Blender 5.2 合成器 API 见坑 16 |
| `atmos_test.py` | 载入存好的 `.blend` 换预设重渲：`blender -b renders/kingdom/capital_full.blend --python atmos_test.py -- --preset golden_hour --shot ars_overview` | 已跑通，产物 `atmos_ars_overview_golden_hour.png` |

契约：`build(MAT, rng) -> list[obj]`，原点=占地中心，局部 **+Y 是正面**，地面 z=0。

## 2. Unity 天气系统

- `E:\My World\Assets\Scripts\Kingdom\KingdomWeather.cs`：枚举 `SkyWeather { Clear, Fair, Cloudy, Overcast, Rain, Storm, Snow, Fog }`；实例成员 `weather` / `hourOfDay` / `autoCycle` / `hoursPerSecond`；`SetWeather(...)`、`SetHour(...)`、`IsWet`、`Daylight01`、`Describe()`。**`Instance` 现在是 `{ get; }` + `_instance` 私有字段**（`Awake/OnDestroy` 里只能写 `_instance`，写 `Instance =` 会 CS0200）。
- 每帧驱动：太阳角度/色温/强度、`Skybox/Procedural` 的 `_SkyTint/_GroundColor/_AtmosphereThickness/_Exposure/_SunSize/_Rotation`、`RenderSettings` 线性雾、Trilight 环境光、全局 `_KingdomWind` / `_KingdomWetness`；运行时生成雨/雪/尘土粒子（跟随相机），暴风雨要 `Flash()`。
- `Assets\Editor\KingdomWeatherMenu.cs`：`Tools/My World/天气/{晴,多云,阴,雨,暴风雨,雪,雾}` 与 `时刻/{06:20,12:00,18:40,22:30}`。
- 场景自动挂载：`KingdomWorldMap.BuildSystems`（Clear, 9.5h）与 `AsuraCapitalMap.BuildSystems`（Fair, 8.4h）各 `AddComponent<KingdomWeather>()`。

## 3. 本轮踩到的两个致命坑（会浪费时间，务必先看）

**坑 15 — PowerShell 改文件会毁掉中文。** `Get-Content -Raw | -replace | Set-Content -Encoding UTF8` 在 PS 5.1 下把无 BOM 的 UTF-8 当 cp936 读，再按 UTF-8 写：中文变乱码，**并且会吞掉换行**（cp936 前导字节吃掉后面的 `\n`），C# 直接语法崩溃（本次 `AsuraCapitalMap.cs` / `KingdomWorldMap.cs` 就是这样毁的，已按字节逆变换恢复 + 子代理重写注释）。
正确做法：`[System.IO.File]::WriteAllText($p, $t, (New-Object System.Text.UTF8Encoding($false)))`，或直接用编辑器工具。

**坑 16 — Blender 5.2 合成器 API 变了。** `scene.node_tree` 不存在；改为 `scene.compositing_node_group`（`bpy.data.node_groups.new(name, "CompositorNodeTree")`），且 `CompositorNodeComposite` 已移除，输出节点要回落 `NodeGroupOutput`（见 `hd_atmosphere.post()`）。

**坑 17 — `check.ps1` 假绿的第二种成因。** Unity 生成的 `.csproj` 不包含新建的 `.cs`（本次 `cs on disk: 136 / referenced: 134`），MSBuild 报 0 error 是假的。真实错误只能读 Unity 控制台；新增文件后先 `AssetDatabase.Refresh()` 再\n`CompilationPipeline.RequestScriptCompilation()`。

## 4. MCP 调用形状（再确认）

```powershell
# 执行 C#（必须 action + code，且激活 scripting_ext）
& "E:\My World\Tools\mcp_call.ps1" -Activate scripting_ext -Tool execute_code `
  -ArgsJson '{"action":"execute","code":"...","safety_checks":false}'
# 菜单
& "E:\My World\Tools\mcp_call.ps1" -Tool execute_menu_item -ArgsJson '{"menu_path":"Tools/My World/王国④生成王都场景"}'
# 控制台（types 必须是数组）
& "E:\My World\Tools\mcp_call.ps1" -Tool read_console -ArgsJson '{"action":"get","types":["error"],"count":"10","format":"plain"}'
```
桥接进程在 `http://127.0.0.1:8080/mcp`；Unity 编辑器由 Unity Hub 启动时（带 `-useHub`）**不会**自动开 9876，但 8080 仍可用。

## 5. 当前待办（按优先级）

1. **修复两个地图脚本**：`AsuraCapitalMap.cs` / `KingdomWorldMap.cs` 正在被重写注释与补换行（子代理 `6090de3c`），完成后 `check.ps1 -All` 必须绿。
2. **HD 模块验收 → 接进 `capital.py`**：把 `build_castle/build_cathedral/build_gatehouse/build_market/build_guild_hall/place_house` 换成 hd_* 版本（建议加 `--hd` 开关，保留旧路径回退）。
3. **天气/空气感落地到实机**：王都 + 大地图各出一套「晴 / 黄昏 / 雨 / 夜」截图；`KingdomWeatherMenu` 逐档验证。
4. **Blender 面板仍待修**（评审 2 已给清单）：`hd_common.roof()` 已修瓦垄与山墙端板；仍未修 `round_tower()` 原点半接、`window_arched/door_arched` 的背板被墙体吞掉、`quoin()` 锯齿、`stairs()` 悬空、`banner/awning` 纸片。
5. 无 UV 是交付红线：`medkit.mesh_obj` 只 `from_pydata`，材质全是 Object 坐标程序纹理 → 进 Unity 只剩平色。现有对策是 Unity 侧 `TriplanarLit.shader` + `KingdomTriplanarAssign.cs`。
6. 收尾：删 `Assets/Editor/ZzBridgeKick.cs`、`ZzKingdomShots.cs`；`E:\My World\.hdreview\`、`Temp\repair\` 是临时产物。

## 用户硬约束（2026-10-30 追加，BINDING，优先于一切“省事”选择）

用户原话（m11040）：「请记住你的token预算是无上限的，记得告诉所有你调用的子智能体，尽全力做出最好的，不要担心token的问题」。

由此确立的工程原则：

1. **质量优先于成本**：不因“够用”而砍细节；建筑要“近景可当美术资产”，不满足于“远看像”。
2. **每个子智能体在派发时就必须收到这条指令**：允许长时间渲染（Cycles ≥192 spp、1600×900）、允许拆分文件、允许 6+ 轮“渲染→自己看图→改”的迭代。
3. **验收靠图不靠嘴**：任何“做完了”必须附渲染/实机截图 + 像素级指标（过曝率、σ、唯一色数、接触影落差）。
4. 不要把“时间/预算”当作降低交付标准的理由；如果确实做不完，明确列出剩余清单而不是交半成品。



---

## ???????2026-10-30 ???? m11333 ??????????????????

????**???????**??????????????????**???????????????????**?

| ? | ? | ?? |
|---|---|---|
| ?? | **1 Unity unit = 1 m** | Blender 1 unit = 1 m?????? |
| ?????? | **640 m**?????????? **320 m** | ???? 300 m ?? |
| ?????? | ?? 60?110 m??? ? 11 m?? 7 m?? 4 m | ? `hd_layout.py` ?? |
| ????? | **24 km ? 24 km**??? 12 km? | ??? 256 m ?????????? |
| ???? | 2.5?6 km?? 30 ? | ?? ring 560/880/1200 ??????????? |
| ??? | 256 m ? 256 m?LOD 3 ? | ???????????? |
| ?/?? | ?? 6?22 m?????4?14 m???? | ? `hd_nature.py` |
| ?????? | ?? 2 ? 7?9 m??? 3 ? 11?14 m??? 70 m????? 61 m | |
| ??? | ???? `(0, 0)`?+Z = ??+X = ? | ?????????????? |

**????**?????/????????????????????????????????? `KingdomWorldMap.RawHeight(x,z)` ???????????????**????**?
