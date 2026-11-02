# 敌人（Enemies）

给 `My World` 造的两种敌人：**蛮兵**（近战，KayKit Barbarian）和 **堕落法师**（远程外形，KayKit Mage 深紫染色）。
两者都满足 `Assets/Scripts/MyWorld/Enemy.cs` 的全部要求，可直接塞进 `MapBootstrap.enemyPrefab` 槽位。

所有产物都由菜单 **`Tools/My World/敌人/① 重建动画控制器与敌人 Prefab`** 生成，可反复执行（幂等：先删除后重建）。

---

## 一、敌人清单

| Prefab | 中文名 | 网格/材质 | 血量 | 巡逻/追击 | 攻击伤害 | 攻击距离 |
|---|---|---|---|---|---|---|
| `Prefabs/E_Barbarian.prefab` | 蛮兵（近战） | `Barbarian.fbx` + `M_Barbarian` | 90 | 2.7 / 4.6 m/s | 9 | 2.4 m |
| `Prefabs/E_FallenMage.prefab` | 堕落法师（远程外形） | `Mage.fbx` + `M_E_FallenMage`（`M_Mage` 深紫染色） | 55 | 2.3 / 3.8 m/s | 7 | 2.6 m |

两种敌人都带：

- `Animator`（controller 为下方六状态控制器，`applyRootMotion = false`，`cullingMode = AlwaysAnimate`）
- `CharacterController`（世界高度 1.9 m，按 prefab 缩放换算成局部尺寸）
- `Rigidbody`（`isKinematic = true`、`useGravity = false`、冻结旋转 —— 位移仍由 `CharacterController.Move` 负责，刚体只提供“有刚体”的物理身份，不抢位移）
- `Enemy`（`Enemy.cs`，`IDamageable`，血量/速度/伤害已写成 prefab 的序列化值）
- `HealthBar` 子物体（`HealthBar/Bar/BG` + `Bar/Fill`，和 `HealthBar.Attach(transform, 2.6f, …)` 完全同构，`HealthBar.Awake` 会按名字找回 `Bar`/`Fill`）
- 根节点缩放 0.68（和玩家同一个“KayKit 单位 → 世界米”换算）

> 说明：`Enemy.cs` 的 AI 是**近战**逻辑（追到 `attackRange` 内挥砍）。堕落法师用的是法术施放动画，外形/动画是远程法师，但命中判定仍按近战距离结算 —— 因为改 `Enemy.cs` 属于禁止改动范围。

---

## 二、动画从哪来

### 结论先说：新动画包和工程里的骨骼**不是同一套**，不能重定向

| 来源 | 骨架路径（实测） | Transform 数 |
|---|---|---|
| `kaykit-character-animations v1.2`（本次导入） | `KayKit Animated Character/Body/armLeft`、`/Body/armRight`、`/Body/Head`（**只有 7 条路径**） | 5 |
| 工程里的 `Barbarian.fbx` / `Mage.fbx`（KayKit Adventurers） | `Rig/root/hips/spine/chest/upperarm.l/hand.r/...` | 56 / 55 |

新包是“Body + 两条手臂 + 头”的**简化傀儡骨架**，Adventurers 是完整 30+ 骨骼人形骨架。把新包的 clip 塞给蛮兵，动画绑不上（全部曲线丢失）。
证据：`WorkQC/enemy_data.md` 的“骨骼对照”一节，由菜单 ② 自动导出。

**因此动画改用 Adventurers 两个 FBX 自带的动画库**（同一个 `Rig` 骨架，clips 直接可用，路径 `Rig/...`）：

| 敌人 | 状态 | 源 clip（FBX 内） | 时长 | 帧数 | 循环 |
|---|---|---|---|---|---|
| 蛮兵 | Idle | `Idle` | 1.067 s | 32 | 是 |
| 蛮兵 | Walk | `Walking_A` | 1.067 s | 32 | 是 |
| 蛮兵 | Run | `Running_A` | 0.800 s | 24 | 是 |
| 蛮兵 | Attack | `1H_Melee_Attack_Chop` | 1.067 s | 32 | 否 |
| 蛮兵 | Hit | `Hit_A` | 0.667 s | 20 | 否 |
| 蛮兵 | Death | `Death_A` | 0.800 s | 24 | 否 |
| 堕落法师 | Idle | `Idle` | 1.067 s | 32 | 是 |
| 堕落法师 | Walk | `Walking_A` | 1.067 s | 32 | 是 |
| 堕落法师 | Run | `Running_A` | 0.800 s | 24 | 是 |
| 堕落法师 | Attack | `Spellcast_Raise` | 2.100 s | 63 | 否 |
| 堕落法师 | Hit | `Hit_A` | 0.667 s | 20 | 否 |
| 堕落法师 | Death | `Death_A` | 0.800 s | 24 | 否 |

`Barbarian.fbx` 自带 80 个 clip（`1H_Melee_Attack_*`、`2H_Melee_Attack_*`、`Spellcast_*`、`Hit_A/B`、`Death_A/B`、`Walking_A/B/C`、`Running_A/B`…），`Mage.fbx` 自带 76 个，够后续扩招。

### 生成的资源

- `Assets/Generated/CharacterAnimations/Clips/CL_<敌人>_<状态>.anim` —— 从源 clip **克隆**出来的独立 `.anim`（这样循环/夹持设置只影响敌人，不动第三方 FBX 的导入设置）。
- `Assets/Generated/CharacterAnimations/Controllers/AC_<敌人>.controller` —— 六状态控制器（Idle/Walk/Run/Attack/Hit/Death）。
- `Assets/Generated/Enemies/Prefabs/E_<敌人>.prefab`
- `Assets/Generated/Enemies/Materials/M_E_FallenMage.mat`（URP/Lit，`_BaseColor` = 深紫）

---

## 三、AnimatorController

参数和 `Enemy.cs` 完全对齐（`Enemy.cs` 里只认这四个）：

| 参数 | 类型 | 谁写 |
|---|---|---|
| `Speed` | Float | `Enemy.SetAnimSpeed()`：0=停，0.5=走，1=跑 |
| `Attack` | Trigger | `Enemy` 每次出招前 `SetTrigger("Attack")` |
| `Hit` | Trigger | 受击 / 被钩索拉扯时 `SetTrigger("Hit")` |
| `Dead` | Bool | 死亡时 `SetBool("Dead", true)` |

状态机（单层）：

```
        Speed > 0.15              Speed > 0.75                 AnyState --Attack & !Dead--> Attack --exitTime .9--> Idle
Idle ──────────────► Walk ──────────────────► Run               AnyState --Hit    & !Dead--> Hit    --exitTime .9--> Idle
     ◄──────────────      ◄──────────────────                     AnyState --Dead = true ----> Death（无出口，停在末帧）
        Speed < 0.15              Speed < 0.75
```

- `Idle` 是默认状态；`Idle`/`Walk`/`Run` 的 clip 为 Loop。
- 阈值 0.15 / 0.75 与 `Enemy.SetAnimSpeed()` 写出的 0 / 0.5 / 1 一一对应（0=停、0.5=走、1=跑）。
- `Attack`/`Hit`/`Death` 的 clip 为 ClampForever，死亡会停在倒地姿势。
- `AnyState` 过渡都关闭了 `canTransitionToSelf`，`Attack`/`Hit` 都带 `Dead == false` 条件，防止死后还出招。
- 过渡时长 0.06–0.12 s，避免动画硬切。

---

## 四、怎么用

### 1) 改进地图（推荐）

> 现状：5 个场景（BlenderKitTown / BuenaVillage / RoaTown / RanoaAcademy / MyWorld）里的 `enemyPrefab` 槽位**仍然指向老的 `Assets/ThirdParty/KayKit_Adventurers/Enemies/EnemyBarbarian.prefab`** ——
> 那个 prefab 只有 Transform + Animator，**没有 `Enemy` / `CharacterController`**，所以进 Play 只会站着播 Idle（雕像）。要换成新敌人，跑一次菜单 ③。

1. 打开地图场景（`Assets/Scenes/BuenaVillage.unity` —— 只有这个地图脚本调用了 `SpawnEnemy`）。
2. 菜单 `Tools/My World/敌人/③ 把蛮兵接进当前地图的 enemyPrefab 槽位`。
   它把场景里所有 `MapBootstrap` / `MyWorldBootstrap` 的 `enemyPrefab` 指向 `E_Barbarian.prefab`，**不会自动保存场景**，确认后手动 Ctrl+S。
3. 想换堕落法师：把 `E_FallenMage.prefab` 拖进同一个槽位即可（两者接口一致）。

### 2) 手搓测试场景

把 `E_Barbarian.prefab` / `E_FallenMage.prefab` 拖进场景任意位置，直接 Play：

- 它们会找 `PlayerCombat`，进入 `aggroRange`（默认 10 m）后开始追击；
- 走近后每 3 s 挑一个招式出招（`Enemy.cs` 的决策逻辑）；
- 打它会闪白 + 掉血，血量归零播放 `Death` 并停在倒地姿势。

> 注意：`MyWorldBootstrap.BuildEnemies()` 那条老路径会在实例上**再补一次** `Enemy`/`CharacterController`
> （它有 `GetComponent == null` 判断，不会重复加）。用这套 prefab 时建议走 `MapBootstrap.SpawnEnemy` 或手动摆放。

### 3) 重新生成

菜单 ① 会删掉并重建 `Clips/`、`Controllers/`、`Prefabs/`、`Materials/` 下所有本工具产物。
改配方（换 clip、调血量、加第三种敌人）请改 `Assets/Editor/EnemyFactory.cs` 里的 `GetSpecs()`。

---

## 五、验证（都是实测，不是“导入成功”）

### 1) 状态机 —— 用 `Enemy.cs` 真正写的那四个参数驱动

Play 模式下实例化 prefab，按 `Enemy.cs` 的写法改 `Speed` / 触发 `Attack` / `Hit` / `Dead`，记录当前状态（`WorkQC/EnemyQA/state_machine_log.txt`）：

| 操作 | 蛮兵 | 堕落法师 |
|---|---|---|
| 初始 | `Idle` | `Idle` |
| `Speed = 0.5` | `Walk(0.33)` | `Walk(0.33)` |
| `Speed = 1.0` | `Run(0.56)` | `Run(0.56)` |
| `Speed = 0` | `Idle(0.23)` | `Idle(0.23)` |
| `SetTrigger("Attack")` | `Attack(0.28)` | `Attack(0.32)` |
| `SetTrigger("Hit")` | `Hit(0.30)` | `Hit(0.30)` |
| `TakeDamage(9999)` | `hp 90 → 0`、`IsAlive=false`、`Dead=true`、`Death(0.81)` | `hp 55 → 0`、同上 |

同一轮里 `CharacterController.isGrounded = True`、落地后 `y = 0.044`（加了运动学刚体后重力/落地仍正常）；血条 `Fill.localScale.x` 从 `1.248`（满）掉到 `0.000`（空），`Death` 状态 `normalizedTime = 1.69`（已停在末帧）。

> 坑：`Enemy.blockChance` 默认 0.3，单发 `TakeDamage(9999)` 有 30% 概率被格挡、血量不掉。截图 QA 里用反射把 `blockChance` 临时置 0 再打，保证一定能进 `Death`。

### 2) 看得见的截图（800×800，Play 模式离屏渲染 + 逐帧 `Camera.Render()`）

目录 `WorkQC/EnemyQA/`（**不写进 Assets/**，避免触发 import + 域重载）：

- `contact_sheet.png` —— 2 行 × 6 状态总览（蛮兵 / 法师 × Idle / Walk / Run / Attack / Hit / Death），素材为 `E_<敌人>_P_<状态>.png`。
- `attack_strip.png` —— 攻击动作 3 帧连拍（蛮兵 0.27 / 0.59 / 0.91 s，法师 0.74 / 1.37 / 1.93 s），素材为 `E_<敌人>_A1..A3.png`。
- `pose_log2.txt` / `death_log3.txt` / `attack_strip_log.txt` / `state_machine_log.txt` —— 每次截图时的状态名、`normalizedTime`、血条 `Fill.x`。

肉眼确认（本人逐张看过）：

- 蛮兵六状态姿态互不相同：Idle 垂手、Walk 抬腿迈步、Run 身体前倾、Attack 斧头高举过顶再挥下（连拍 3 帧可见起手→挥砍→收势）、Hit 后仰、Death 侧躺倒地且盾牌脱手。
- 法师六状态：Idle 站姿、Attack 帽檐后仰+俯身施法、Death 连人带帽倒地（`E_FallenMage_P_Death.png`）。
- 都不是纯白（贴图在），法师是深紫染色；无 T-pose 帧。

像素级“真的在动”证据（`Idle` 与其它状态逐像素比对，3 像素采样、阈值 24）：

| 对比 | 变化像素占比 | 平均色差 |
|---|---|---|
| 蛮兵 Idle vs Walk | 10.18 % | 13.3 |
| 蛮兵 Idle vs Attack | 14.91 % | 24.7 |
| 法师 Idle vs Walk | 2.58 % | 3.3 |
| 法师 Idle vs Attack | 10.93 % | 14.6 |
| 法师 Walk vs Run | 14.69 % | 22.9 |

> 法师 Idle/Walk 差异小是**动画本身幅度小**（宽袍大帽挡住躯干，`Walking_A` 里手臂摆幅不大），不是绑定失败：`CL_E_FallenMage_Attack.anim` 里 480 条曲线中有 140 条落在 `upperarm.*`/`lowerarm.*`、20 条在 `head`，路径全是 `Rig/root/hips/spine/chest/...`，与蛮兵的 150 条同构。

### 3) 编译

`& "E:\My World\Tools\check.ps1"` → `OK - 0 errors (0 warning(s))`。

### 4) 没验证的部分（诚实说明）

- **没有在真实地图里用玩家打过**：地图场景的 `enemyPrefab` 槽位还没接（需要你跑菜单 ③ 再 Ctrl+S），所以“敌人追着玩家跑、玩家砍它掉血”这条端到端链路没跑过。
- `Enemy.cs` 的 AI 会找 `PlayerCombat`；没玩家时只做重力/待机（这点已实测）。
- 远程只是**外形 + 施法动画**，没有真弹道：`Enemy.cs` 的招式全是近战判定。

---

## 六、授权

- KayKit Adventurers（Barbarian/Mage 网格、材质、动画）：CC0，`E:\My World\Assets\ThirdParty\KayKit_Adventurers\`。
- KayKit Character Animations v1.2（本次导入，仅作对照/备用）：CC0，见 `Assets/Generated/CharacterAnimations/LICENSE_KayKitAnimations.txt`。
- KayKit Spooktober（Jack/Witch，无骨骼，未用）：CC0，见 `LICENSE_KayKitSpooktober.txt`。
