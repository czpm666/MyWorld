using System.Collections.Generic;
using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 武器使用入口：把输入分发到主手/副手的武器行为上。
    ///
    /// 左键 = 用**当前手**的武器
    /// 右键 = 用**副手**武器（按住持续，抓钩靠松手保留动量）
    /// **`Q`** = 锁定（在 `PlayerLockOn` 里处理）
    ///
    /// ⚠️ **T-051 订正（原文两处都是错的）**：
    ///  * 原写"**C 切换**的是当前操作哪只手" —— **全工程没有 C 键绑定**。
    ///    `WeaponLoadout.SwitchHand()` 是**预留的扩展点，当前零调用者**
    ///    （**保留不删** —— 这是早前裁定过的；但别再把它当成"已有功能"来写文档或做测试）。
    ///  * 原写"**中键** = 锁定" —— 实际绑定是 `Q`（`MyWorldInput.cs:91`）。
    ///    右键是**副手武器**，不是锁定。
    /// 照旧文案写测试会去测一个**不存在的输入**（`charter-qa` 已踩过同一坑）。
    /// </summary>
    [DisallowMultipleComponent]
    public class PlayerCombat : MonoBehaviour
    {
        [Header("施法点")]
        [SerializeField] private float castHeight = 1.05f;
        [SerializeField] private float castForward = 0.6f;

        [Header("挥砍")]
        [Tooltip("挥砍检测的中心高度")]
        [SerializeField] private float meleeHeight = 1.0f;

        [Header("出手时转向鼠标")]
        [Tooltip("出手后这段时间内朝向交给鼠标，过了就回到 WASD 控制")]
        [SerializeField] private float aimTurnDuration = 0.45f;

        private WeaponLoadout loadout;
        private WeaponMount mount;
        private GrappleWeapon grapple;
        private PlayerMage mage;
        private MyWorldInput input;
        private PlayerLockOn lockOn;
        private PlayerAim aim;
        private PlayerController8Dir movement;
        private float cooldown;
        private float aimTurnTimer;

        /// <summary>是否正处于"出手转向鼠标"的窗口内（PlayerAim 靠它决定要不要接管朝向）。</summary>
        public bool AimingAtMouse => aimTurnTimer > 0f;

        /// <summary>
        /// T-079 §⑨ 片 4（空手组）：**主手是不是空的**（= 被缴械）。
        /// 唯一缴械路径是 `WeaponLoadout.DropMainHand()`（敌人盾击 `KnockOffMainHand`）。
        ///
        /// ⚠️ **写成派生属性、不缓存**：`Update` 里有两条 early-return（缺引用 / 僵直），
        ///    若在这里缓存赋值，那几帧就会留下**陈旧值**（静默）→ 空手待机会闪回持械待机。
        /// ⚠️ `PlayerMage.Update` 每帧把它搬给 Animator 的 `Unarmed` 参数（与 `IsBlocking` 同一个地方）。
        /// </summary>
        public bool IsUnarmed => loadout != null && loadout.MainHand == null;

        // 挥砍刀光的颜色与形状参数已迁到 `SkillVfx`（T-010）：
        // 参数长在判定文件里，每次调刀光都要动这里，容易误伤判定。本文件不再持有视觉参数。

        [Header("连招")]
        [Tooltip("一套连招共 4 段：横劈 → 下劈 → 斜劈 → 突刺。" +
                 "这是两刀之间的最大间隔，超时后再按就从第一段重新开始")]
        [SerializeField] private float comboResetTime = 1.1f;

        /// <summary>已经起手、但还没到命中帧的那一刀。命中帧由动画事件回调消费。</summary>
        private WeaponDefinition pendingSwing;

        /// <summary>
        /// 那一刀是哪一段连招。必须在起手时**快照**下来：
        /// 命中帧是 0.2 秒后才回调的，若那时才读 comboStep，中途又按了一下就已经变成下一段了
        /// （击退会挂到错的那一刀上）。
        /// </summary>
        private int pendingStep = -1;

        /// <summary>当前连招推进到第几段（0..3）。</summary>
        private int comboStep;

        /// <summary>连招窗口剩余时间；归零后再出手就从第一段重来。</summary>
        private float comboWindow;

        private readonly Collider[] meleeHits = new Collider[24];
        private readonly HashSet<IDamageable> meleeDamaged = new HashSet<IDamageable>();

        /// <summary>
        /// 惰性补引用，而不是只在 Awake 里取一次。
        /// 这个组件是烘焙时 AddComponent 上去的，Awake 的调用时机不可靠
        /// （被 enabled=false 过、或烘焙/重载时序问题都可能让它没跑），
        /// 一旦没跑，所有 GetComponent 引用就全是 null，抓钩/攻击会静默失效。
        /// </summary>
        private void EnsureRefs()
        {
            if (loadout == null) loadout = GetComponent<WeaponLoadout>();
            if (mount == null) mount = GetComponentInChildren<WeaponMount>();
            if (grapple == null) grapple = GetComponent<GrappleWeapon>();
            if (mage == null) mage = GetComponent<PlayerMage>();
            if (input == null) input = GetComponent<MyWorldInput>();
            if (lockOn == null) lockOn = GetComponent<PlayerLockOn>();
            if (aim == null) aim = GetComponent<PlayerAim>();
            if (movement == null) movement = GetComponent<PlayerController8Dir>();
        }

        private void Start()
        {
            EnsureRefs();
            if (mount != null && loadout != null) mount.Refresh(loadout);
            if (grapple != null)
                grapple.Configure(GetComponent<PlayerController8Dir>(),
                    mount != null ? mount.OffHandSlot : null);
        }

        private void Update()
        {
            if (cooldown > 0f) cooldown -= Time.deltaTime;
            if (aimTurnTimer > 0f) aimTurnTimer -= Time.deltaTime;
            if (comboWindow > 0f) comboWindow -= Time.deltaTime;
            UpdateArrowTimeout();   // 弓的事件兜底（T-050）

            EnsureRefs();
            if (input == null || loadout == null) return;

            // 受击僵直期间不能出手，但抓钩该松还是要松（否则会一直挂着）
            bool stunned = movement != null && movement.IsStunned;
            if (grapple != null && grapple.IsBusy && (!input.OffHandHeld || stunned)) grapple.Release();
            if (stunned) return;

            var off = loadout.OffHand;
            bool shieldUp = off != null && off.kind == WeaponKind.Shield && input.OffHandHeld;
            IsBlocking = shieldUp;

            // 右键 = 副手。盾是"长按举盾"，不主动出手；其余副手按住即持续（抓钩）
            if (input.OffHandPressed && !shieldUp) Use(off);

            // 左键 = 主手。举盾时左键改成放盾击（用户规则：按住右键举盾 + 按左键 = 盾击）
            if (input.AttackHeld)
            {
                if (shieldUp)
                {
                    if (input.AttackPressed && cooldown <= 0f) ShieldBash(off);
                }
                else
                {
                    Use(loadout.MainHand);
                }
            }
        }

        /// <summary>使用一件武器。**被缴械（主手空着）时走空手出拳**；其余空手/冷却中直接忽略。</summary>
        public void Use(WeaponDefinition weapon)
        {
            EnsureRefs();

            // ================= T-079 §⑨ 片 4：**空手出拳必须在这里明写** =================
            // 🔴 为什么非加这一支不可：`Update` 里左键走的是 `Use(loadout.MainHand)`，
            //    而**缴械后那个实参就是 `null`** → 原先这一行直接 `return`（下一行），
            //    **"空手能出拳"永远不会发生，而且不报错**。
            // ⚠️ **不能只判 `weapon == null`**：`Update` 的右键那条也调 `Use(loadout.OffHand)`，
            //    副手为空时同样是 `null` —— 那在**持械时是既有行为 = 什么都不做**，
            //    不该被本片变成出拳（§⑨ I2：已装备任何武器时行为一字不变）。
            //    → **再钉一条"主手确实空着"**，于是两支互不干扰。
            // 🔴 本支**不落任何伤害、不生成任何弹道**（§⑨ I4）—— 见 `UnarmedPunch`。
            if (weapon == null)
            {
                if (loadout != null && loadout.MainHand == null) UnarmedPunch(loadout.Unarmed);
                return;
            }

            switch (weapon.kind)
            {
                case WeaponKind.Staff:
                case WeaponKind.Gauntlet:
                    if (cooldown <= 0f) CastSpell(weapon);
                    break;

                case WeaponKind.Sword:
                    if (cooldown <= 0f) SwingSword(weapon);
                    break;

                case WeaponKind.Grapple:
                    // 🔴 T-080①：**补上"判 + 写"冷却** —— 与 `Staff/Gauntlet/Sword/Bow/Shield` 同一套语义。
                    // 改前这里**既不判也不写**（实测：`Use` 之后 `PlayerCombat.cooldown` 仍是 **0.000**），
                    // 于是 `WeaponDefinition.cooldown = 0.3` 对抓钩**是死数据**（定义了却被绕过）。
                    //
                    // ⚠️ **真正的限速一直是** `GrappleWeapon.Fire` 开头的 `if (state != State.Idle) return false;`
                    //    实测：钩索从出手回到 Idle = **25 帧 ≈ 0.500 s**（3 次一致）。
                    //    → **打满全程时这道 0.3 s 冷却几乎不 binding（0.5 > 0.3）**；
                    //      **只有玩家提前 `Release()`（松右键）时，才会真的多一道 0.3 s 的门。**
                    //      —— 这句量化描述是给用户判"0.3 s 合不合适"用的，别删。
                    if (cooldown <= 0f)
                    {
                        // 出手时也要转向鼠标，否则钩子会朝着"角色还没转过去的旧朝向"飞
                        aimTurnTimer = aimTurnDuration;
                        if (grapple != null)
                        {
                            // T-075① 的**第二处**（同一条铁律："你瞄的地方"与"东西飞出去的方向"必须同源）。
                            //
                            // 抓钩的发射点是 `GrappleWeapon.MuzzlePosition()`（= 副手挂点 `mount.OffHandSlot`），
                            // 而 `CurrentAimDirection()` 的锁定分支是从 `transform.position`（**脚底**）算的
                            // → 与弓箭 T-075① 是**同一类缺陷**（实测：muzzle 高出脚底 **0.4209 m**，
                            //    到目标距离 24.01 m 处比 `AimPoint` **高 0.4211 m**）。
                            //
                            // 统一到本工程**已经存在的正确写法**（施法那条用的是 `AimPoint - CastOrigin`）——
                            // 也就是说"正确的那一种"本来就在工程里，弓箭与抓钩是两处**没跟上**的。
                            //
                            // ⛔ 同样**不动 `CurrentAimDirection()` 本体**：弓（`ShootArrow`）也共用它，
                            //    在共享函数里改起点会同时改掉另一条链。
                            // ⚠️ 鼠标分支与朝向分支**一字不改**（`PlayerAim` 的 `0f` 是另一件事，见下）。
                            Vector3 gdir = CurrentAimDirection();
                            if (lockOn != null && lockOn.IsLocked)
                            {
                                // muzzle 为空时用 `CastOrigin` 兜底：`GrappleWeapon.MuzzlePosition()` 的兜底公式
                                // 与 `CastOrigin` **逐字相同**（`pos + up*1.05 + forward*0.6`），所以不必抄一遍魔数。
                                Vector3 muzzle = grapple.Muzzle != null ? grapple.Muzzle.position : CastOrigin;
                                Vector3 toAim = lockOn.AimPoint - muzzle;
                                if (toAim.sqrMagnitude > 0.0001f) gdir = toAim;
                            }
                            // 只在**真的把钩子放出去了**才写冷却（`Fire` 被 `state != Idle` 拒时不该罚冷却）
                            if (grapple.Fire(weapon, gdir)) cooldown = weapon.cooldown;
                        }
                    }
                    break;

                case WeaponKind.Bow:
                    if (cooldown <= 0f) ShootArrow(weapon);
                    break;

                case WeaponKind.Shield:
                    // 盾的主动技能是盾击；平时右键是"举盾格挡"（见 Update）
                    if (cooldown <= 0f) ShieldBash(weapon);
                    break;

                case WeaponKind.Unarmed:
                    // T-079 §⑨ 片 4：空手载体**若被直接喂进来**（`Use(loadout.Unarmed)`），语义与
                    // 上面的 `weapon == null` 支**完全一致**（同一个 `UnarmedPunch`）。
                    // ⚠️ 加这一支是为了"没有任何 `kind` 会落进无分支" —— 缺 case 时 switch 会**静默什么都不做**
                    //    （与"空手永不生效"是同一种静默失败）。
                    UnarmedPunch(weapon);
                    break;
            }
        }

        /// <summary>
        /// T-079 §⑨ 片 4：**空手出拳** —— 只有「动作 + 冷却」，**不造成伤害、不生成弹道**。
        ///
        /// 🔴 **为什么故意不接伤害**（判据 §⑨ I4 的明文要求）：要真的打出 `damage = 8f`，
        /// 就必须先定"打哪、多远、多大角度、判定发生在哪一帧"—— 那些是**玩法数值、属用户领域**。
        /// 本片是接线，**不该由我们发明命中几何**。
        /// ⚠️ 所以 `8f` 目前**只是空手载体上的一个暂定数据**（§⑨ I3 要求它"来源单一"），
        /// **没有任何代码读它**；要启用它 = 先定命中几何 + 改 I4。
        ///
        /// 表现侧：`PlayerMage.PlayUnarmedAttack()` → `Animator.Play(状态名)` 直接寻址
        /// （0 帧延迟、确定性，**不与既有 `Hit`/`Slash`/`BowShot` 抢 AnyState** —— 见陷阱 22）。
        /// </summary>
        private void UnarmedPunch(WeaponDefinition empty)
        {
            if (empty == null || cooldown > 0f) return;
            cooldown = empty.cooldown;      // 0.45f（暂定值；单一来源 = WeaponLoadout.unarmed，由生成器写）
            if (mage != null) mage.PlayUnarmedAttack();
        }

        // ---------------- 法术 ----------------

        private Vector3 CastOrigin => transform.position
                                      + Vector3.up * castHeight
                                      + transform.forward * castForward;

        /// <summary>当前该打的方向：锁定目标 > 鼠标 > 角色朝向。</summary>
        /// <remarks>
        /// 🔴 **T-075 反复确认的两件事，改它之前必须知道**：
        /// 1. **本函数有三个调用方**：抓钩（`Use` 里）、弓（`ShootArrow`）、以及它自己。
        ///    ⚠️ **不要在函数里把锁定分支的起点从 `transform.position` 改成枪口** ——
        ///    各兵器的枪口**不是同一个点**（弓是 `CastOrigin`、抓钩是 `MuzzlePosition()`/副手挂点），
        ///    在共享函数里改会连带改错另一条链。**正确做法是在各自调用点按自己的枪口算**（两处都已如此改）。
        /// 2. 🟠 **鼠标分支（就是下面 `aim.MouseDirection` 那条）没有竖直瞄准能力** ——
        ///    `PlayerAim.cs:60` 把鼠标方向的 `y` **显式置 0**（它瞄的是"过角色原点的水平面"上的一点）。
        ///    所以鼠标射击恒为水平、且因无重力而**永不收敛到瞄准点**。
        ///    **这是弓箭与抓钩共有的同一个问题**（不是各自独立的）→
        ///    **一旦用户同意"给真实三维瞄准"，这两处必须一起改，别只改弓箭。**
        ///    ⚠️ **用户尚未同意**，属**手感变更**，别自行改。
        /// </remarks>
        private Vector3 CurrentAimDirection()
        {
            if (lockOn != null && lockOn.IsLocked)
                return (lockOn.AimPoint - transform.position).normalized;
            if (aim != null && aim.HasMouseDirection)
                return aim.MouseDirection.normalized;
            return transform.forward;
        }

        private void CastSpell(WeaponDefinition weapon)
        {
            float cd = weapon.cooldown;
            float damage = weapon.damage;

            // 副手装魔法护手：施法更快，但伤害大幅降低
            if (loadout.HasGauntlet)
            {
                var g = loadout.OffHand;
                cd /= Mathf.Max(g.castSpeedMultiplier, 0.01f);
                damage *= g.castDamageMultiplier;
            }

            cooldown = cd;
            aimTurnTimer = aimTurnDuration;   // 出手瞬间把朝向交给鼠标
            mage?.PlayCast();
            GameAudio.PlayCast();             // ④ 施法音（T-063；槽位空则静默跳过）

            // 弹道方向：锁定 > 鼠标 > 角色朝向。
            // 用鼠标方向而不是 transform.forward，是因为朝向要经过 Lerp 吸附，
            // 出手那一帧还没转到，照 forward 打会偏。
            Vector3 dir;
            if (lockOn != null && lockOn.IsLocked)
                dir = lockOn.AimPoint - CastOrigin;
            else if (aim != null && aim.HasMouseDirection)
                dir = aim.MouseDirection;
            else
                dir = transform.forward;
            if (dir.sqrMagnitude < 0.0001f) dir = transform.forward;

            SpellProjectile.Spawn(CastOrigin, dir.normalized, transform, damage);
        }

        // ---------------- 弓 ----------------

        /// <summary>
        /// 已起手、但还没到"离弦帧"的那一箭（T-050）。与 `pendingSwing`/`pendingStep` 同一套约定：
        /// 起手时**快照**、事件回调里**消费并清空**、每次出手**覆盖**。
        /// </summary>
        private WeaponDefinition pendingShot;

        /// <summary>起手那一刻就定死的弹道。不能在离弦帧才取方向 —— 那 0.45s 里玩家可能已经转身了。</summary>
        private Vector3 pendingShotDir;
        private Vector3 pendingShotOrigin;

        /// <summary>兜底计时，见 UpdateArrowTimeout()。</summary>
        private float pendingShotTimer;
        private bool warnedArrowTimeout;

        /// <summary>
        /// `OnArrowRelease` 事件的兜底超时。取剪辑长度 + 余量；正常路径事件约 0.45s 到达，不会走这里。
        /// </summary>
        private const float ArrowReleaseTimeout = 1.2f;

        /// <summary>
        /// 兜底：事件**没派发**时（relay 挂错物体 / 事件名不一致 / 剪辑被换掉……）箭矢会
        /// **永远不出来，而且 Console 一条错都没有** —— 本项目最典型的静默失败形状。
        /// 所以到点就照原样把箭放出去，并**明确警告一次**，让"事件丢了"这件事可见而不是无声。
        /// </summary>
        private void UpdateArrowTimeout()
        {
            if (pendingShot == null) return;

            pendingShotTimer -= Time.deltaTime;
            if (pendingShotTimer > 0f) return;

            var weapon = pendingShot;
            Vector3 dir = pendingShotDir;
            Vector3 origin = pendingShotOrigin;
            ClearPendingShot();

            if (!warnedArrowTimeout)
            {
                warnedArrowTimeout = true;
                Debug.LogWarning("[My World] 弓箭的 OnArrowRelease 动画事件没有在 "
                                 + ArrowReleaseTimeout.ToString("F2") + "s 内派发 —— 本次是**兜底补发**的"
                                 + "（箭已射出，但时机是猜的）。请检查：① Ranged_Shoot.anim 上是否还有该事件；"
                                 + "② AnimEventRelay 是否挂在 Animator 所在物体上；③ 事件名是否一致。");
            }

            ArrowProjectile.Spawn(origin, dir, transform,
                weapon.damage, weapon.arrowSpeed, weapon.arrowLifeTime, weapon.arrowRadius);
        }

        private void ClearPendingShot()
        {
            pendingShot = null;
            pendingShotTimer = 0f;
        }

        /// <summary>
        /// 起手：只广播动作、记录快照，**不生成箭矢**（T-050）。
        ///
        /// 改前它在**当帧**就 `ArrowProjectile.Spawn(...)`，而动画还在抬弓 → "箭比动作先出"。
        /// 现在箭只在剪辑的 `OnArrowRelease` 事件回调里生成，与剑的 `OnSlashImpact@0.200` 完全同构
        /// （HANDOFF 6.1：判定由动画事件驱动，所以动作与判定天然同步）。
        /// </summary>
        private void ShootArrow(WeaponDefinition weapon)
        {
            cooldown = weapon.cooldown;
            aimTurnTimer = aimTurnDuration;   // 出手时转向鼠标

            // 快照：方向在**起手这一刻**定死，离弦帧只负责拿去用
            pendingShot = weapon;
            pendingShotOrigin = CastOrigin;

            // T-075①（总控批准的 bug 修复）：**锁定分支必须用「枪口」`CastOrigin` 当起点**。
            //
            // `CurrentAimDirection()`（:181）的锁定分支是 `AimPoint - **transform.position**`（脚底），
            // 而箭从 `CastOrigin`（比脚底高 `castHeight = 1.05`）射出 —— **方向与起点不同源**，
            // 于是整条弹道是**平行的上移**（不是"越远偏得越多"：平行线间距不随距离变，**近距离也会打高**）。
            //
            // 实测（改前，T-079 §1 口径）：锁定一个 base y=0.044 的矮敌人时
            //   `dir.y = +0.083098`（噪声底 ±0.02 之外，且 > 判据 A-4 的 +0.05 红线）；
            //   到目标水平距离 14.04 m 处 y = 2.251，而 `AimPoint.y = 1.2441` → **恒定高 1.05 m**。
            //
            // ⛔ **只在弓的调用点修，绝不动 `CurrentAimDirection()` 本体** ——
            //    它还被**抓钩**（`:160` `grapple.Fire(weapon, CurrentAimDirection())`）共用，
            //    在共享函数里改起点会**连带打坏抓钩的瞄准**（那是另一条链，见 T-075③）。
            // ⚠️ **鼠标分支与「角色朝向」分支保持原样**（总控约束 b）：
            //    `PlayerAim.cs:60` 把鼠标方向显式置 `y=0` 是**另一件事**；
            //    要不要让鼠标能上下瞄属**手感变更**，**未获批准，等用户**。
            pendingShotDir = CurrentAimDirection();
            if (lockOn != null && lockOn.IsLocked)
            {
                pendingShotDir = lockOn.AimPoint - pendingShotOrigin;
                if (pendingShotDir.sqrMagnitude < 0.0001f) pendingShotDir = transform.forward;
                pendingShotDir = pendingShotDir.normalized;
            }
            pendingShotTimer = ArrowReleaseTimeout;

            mage?.PlayBowShot();              // 弓自己的 Trigger，绝不碰 Slash/ComboStep
        }

        /// <summary>
        /// 离弦帧回调。由 `Ranged_Shoot.anim` 上的 `OnArrowRelease` 动画事件驱动，
        /// 经 `AnimEventRelay` 从 Animator 所在物体转发上来。
        /// </summary>
        public void OnArrowRelease()
        {
            var weapon = pendingShot;
            Vector3 dir = pendingShotDir;
            Vector3 origin = pendingShotOrigin;
            ClearPendingShot();

            if (weapon == null) return;   // 没有待发的箭（例如事件重放）→ 什么都不做

            GameAudio.PlayBowShot();      // ③ 放箭音（T-063）—— 与箭生成同一帧（离弦那一刻）

            ArrowProjectile.Spawn(origin, dir, transform,
                weapon.damage, weapon.arrowSpeed, weapon.arrowLifeTime, weapon.arrowRadius);
        }

        // ---------------- 盾 ----------------

        /// <summary>举盾格挡中（右键按住 + 副手是盾）。PlayerHealth 用它减伤。</summary>
        public bool IsBlocking { get; private set; }

        /// <summary>盾击：把正面的敌人击退 + 造成伤害。</summary>
        private void ShieldBash(WeaponDefinition weapon)
        {
            cooldown = weapon.cooldown;
            aimTurnTimer = aimTurnDuration;
            mage?.PlayAttack();

            Vector3 center = transform.position + Vector3.up * meleeHeight;
            int count = Physics.OverlapSphereNonAlloc(
                center, weapon.shieldBashRange, meleeHits, ~0, QueryTriggerInteraction.Ignore);

            meleeDamaged.Clear();
            for (int i = 0; i < count; i++)
            {
                var col = meleeHits[i];
                if (col == null || col.transform.IsChildOf(transform)) continue;

                Vector3 to = col.transform.position - center;
                to.y = 0f;
                if (Vector3.Angle(transform.forward, to) > 80f) continue;   // 只打正面

                var target = col.GetComponentInParent<IDamageable>();
                if (target == null || !target.IsAlive) continue;
                if (!meleeDamaged.Add(target)) continue;

                target.TakeDamage(weapon.shieldBashDamage, col.ClosestPoint(center), Vector3.up);

                // 敌人自己负责被击退；这里直接推动它的位移
                var cc = col.GetComponentInParent<CharacterController>();
                if (cc != null && to.sqrMagnitude > 0.0001f)
                    cc.Move(to.normalized * (weapon.shieldBashKnockbackGrids * 2f) * 0.35f);
            }

            ArcaneBurst.Spawn(center + transform.forward * (weapon.shieldBashRange * 0.5f),
                transform.forward, 0.8f, new Color(0.8f, 0.85f, 0.95f));
            Debug.Log("[My World] 盾击");
        }

        // ---------------- 剑 ----------------

        private void SwingSword(WeaponDefinition weapon)
        {
            cooldown = weapon.cooldown;
            aimTurnTimer = aimTurnDuration;   // 挥砍同样先转向鼠标

            // 连招推进：在窗口内接着下一段，超时了就从第一段重来。
            // 用 % ComboLength 绕回来，所以第四段之后再按会回到横劈，循环成套。
            comboStep = comboWindow > 0f ? (comboStep + 1) % PlayerMage.ComboLength : 0;
            comboWindow = comboResetTime;

            pendingSwing = weapon;            // 伤害与特效推迟到命中帧，见 OnSlashImpact
            pendingStep = comboStep;          // 快照段位：命中帧回调时 comboStep 可能已经变了
            mage?.PlayAttack(comboStep);
            GameAudio.PlaySwing();            // ① 挥砍音（T-063）—— 起手就响，挥空也有声
        }

        /// <summary>
        /// 挥砍命中帧的回调。由攻击剪辑上的 AnimationEvent 触发
        /// （四段各自的时间不同，都是采样手臂角速度量出来的峰值帧），
        /// 经 `AnimEventRelay` 从 Animator 所在物体转发上来。
        ///
        /// **为什么挪到这里**：原先按键当帧就结算伤害并生成爆花，所以表现是
        /// "人还没挥、特效先炸出来"。现在按键只负责起手，命中帧才真正出手。
        /// </summary>
        public void OnSlashImpact()
        {
            var weapon = pendingSwing;
            int step = pendingStep;
            pendingSwing = null;
            pendingStep = -1;
            if (weapon == null) return;

            Vector3 center = transform.position + Vector3.up * meleeHeight;
            int count = Physics.OverlapSphereNonAlloc(
                center, weapon.meleeRange, meleeHits, ~0, QueryTriggerInteraction.Ignore);

            // 最后一段是突刺：命中的敌人要被打飞。先收集，扫完再推，免得边改位置边判定。
            bool finisher = step == PlayerMage.ComboLength - 1 && weapon.stabKnockbackGrids > 0f;

            meleeDamaged.Clear();
            for (int i = 0; i < count; i++)
            {
                var col = meleeHits[i];
                if (col == null || col.transform.IsChildOf(transform)) continue;

                Vector3 to = col.transform.position - center;
                to.y = 0f;
                if (Vector3.Angle(transform.forward, to) > weapon.meleeHalfAngle) continue;

                var target = col.GetComponentInParent<IDamageable>();
                if (target == null || !target.IsAlive) continue;
                if (!meleeDamaged.Add(target)) continue;   // 同一目标只打一次

                target.TakeDamage(weapon.damage, col.ClosestPoint(center), Vector3.up);

                if (finisher)
                {
                    var enemy = col.GetComponentInParent<Enemy>();
                    if (enemy != null)
                        enemy.ApplyKnockback(to.sqrMagnitude > 0.0001f ? to : transform.forward,
                                             weapon.stabKnockbackGrids * 2f);   // 1 格 = 2 米，和敌人技能同一套换算
                }
            }

            // ② 命中音（T-063）：**只在真的打中目标时才响** —— `meleeDamaged` 非空即"打到了"。
            // ⚠️ 不要挪到循环外面无条件播：那样"挥空也响命中音"会误导玩家以为自己打中了。
            if (meleeDamaged.Count > 0) GameAudio.PlayHit();

            // 挥砍刀光：一段有厚度的弧带，形状／朝向／层宽／颜色全部在 SkillVfx 里。
            // 这里只把**判定**用的半径和半张角原样递过去，视觉参数一概不写在本文件。
            // ⚠️ 判定条件、范围、伤害、击退都不在这里动。
            // T-011：把**段位**传下去（1..4）→ 四段的形状/朝向/尺寸/颜色由 SkillVfx 的分段表决定。
            //   用的是 `step`（命中帧回调里已快照的段位），不是当前 `comboStep` —— 后者可能已经变了。
            SkillVfx.SwordSlash(center, transform.forward, weapon.meleeRange, weapon.meleeHalfAngle, step + 1);

            // T-012：刀尖拖尾。颜色 = **当段刀光的颜色**（规格 §2.3：同色以强化该段的颜色维度）。
            // ⚠️ 发射门控在 `WeaponMount` 内部（0.30s 后自动停）—— 这样"平时没有拖尾"（判据 F7）
            //    不依赖调用方每帧调用。
            if (mount != null)
                mount.EmitSlashTrail(SkillVfx.SwordSegmentColor(step + 1), SkillVfx.SlashTrailEmitSeconds);
        }

        // ---------------- 掉武器 / 拾取 ----------------

        /// <summary>
        /// 主手武器被打掉（被抓钩命中、被盾击时由敌人调用）。
        /// 武器落在原地，谁都能捡，但捡到只进背包、不会自动装备。
        /// </summary>
        public void KnockOffMainHand()
        {
            if (loadout == null) return;

            var dropped = loadout.DropMainHand();
            if (dropped == null) return;

            if (mount != null) mount.Refresh(loadout);

            // 甩到侧后方足够远：必须超过 WeaponPickup 的拾取半径(1.6)，
            // 否则掉在脚下会被自己立刻吸走，别人根本没机会捡。
            Vector3 pos = transform.position + Vector3.up * 0.6f
                          + (transform.right * 1.7f) + (-transform.forward * 2.2f);
            WeaponPickup.Spawn(dropped, pos);
            Debug.Log($"[My World] 主手武器被打掉：{dropped.displayName}");
        }

        /// <summary>
        /// 拾取一件武器（**不装备**）。⚠️ **T-076 分支 B**：武器**不再进背包** ——
        /// 它的归属只看 `owned`（被打掉时 `owned` 也没减，所以它本来就在里面）；
        /// 拾取只是把它"标为可再次装备"并**通知 UI**（否则拾取会无声发生，见 `WeaponLoadout.NotifyPickedUp`）。
        /// </summary>
        public void PickUp(WeaponDefinition weapon)
        {
            if (loadout == null || weapon == null) return;
            loadout.NotifyPickedUp(weapon);
            Debug.Log($"[My World] 拾取 {weapon.displayName} → 武器页（未装备；背包不再承载武器）");
        }
    }
}
