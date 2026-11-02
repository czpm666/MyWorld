using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 法师角色的表现层：驱动 Animator，处理左键攻击并放出法术弹。
    /// 挂在 Player 根节点上，Animator 在子物体（KayKit 角色预制体）里自动找。
    ///
    /// 法术朝哪飞**不在这里决定**，由 `PlayerCombat.CastSpell()` 按优先级取：
    /// **锁定目标 > 鼠标方向 > 角色朝向**（`PlayerCombat.cs:198-208`）；未锁定时用
    /// `PlayerAim.MouseDirection`（每帧都写，`PlayerAim.cs:22-25,63-64`），
    /// 只有连鼠标方向都拿不到才回退 `transform.forward`。
    ///
    /// ⚠️ 本类原先写"法术朝角色当前朝向飞（transform.forward），**不做鼠标瞄准**" —— 那是**旧行为**，
    /// 已订正（R-003(a)）。相机的 yaw 仍恒为 0、朝向仍吸附 8 方向，这两条没变。
    /// </summary>
    [DisallowMultipleComponent]
    public class PlayerMage : MonoBehaviour
    {
        // ⚠️ `Speed` 参数**不在本类写**（原来写，本轮改掉）：唯一写入者是 `PlayerController8Dir`。
        //    两处写同一个参数不会报错，但**谁后写谁赢**，而脚本执行顺序不保证；
        //    一旦本类先跑，动画就慢一帧才拿到速度 —— 起步那一帧正好看得见。
        //    本类只写"状态类"参数：`IsBlocking` / `Unarmed`（都是"此刻是不是这个状态"的电平量）。
        private static readonly int AttackHash = Animator.StringToHash("Attack");
        private static readonly int SlashHash = Animator.StringToHash("Slash");
        private static readonly int ComboHash = Animator.StringToHash("ComboStep");
        private static readonly int HitHash = Animator.StringToHash("Hit");
        private static readonly int DeadHash = Animator.StringToHash("Dead");
        /// <summary>T-091 批次 1：翻滚触发器（边沿）。必须与 `MageSetup.DodgeTrigger` 逐字一致。</summary>
        private static readonly int DodgeHash = Animator.StringToHash("Dodge");
        /// <summary>T-091 批次 1：翻滚方向 0=前 1=后 2=左 3=右（Int）。见 <see cref="PlayDodge"/>。</summary>
        private static readonly int DodgeDirHash = Animator.StringToHash("DodgeDir");
        /// <summary>弓的**独立**触发器（T-050）。见 PlayBowShot 的说明。</summary>
        private static readonly int BowShotHash = Animator.StringToHash("BowShot");

        // ⚠️ 下面两个字符串**必须与 `MageSetup`（Editor 程序集）逐字一致** —— 两个程序集
        //    **不能互相引用**，只能各写一份；**名字不匹配不会报错，只会静默不动**（陷阱 20 / 21）。
        //    * 参数：`MageSetup.IsBlockingParam`（`MageSetup.cs`）
        //    * 状态：`MageSetup.Wanted[]` 的**首列**（**不是** `expectSource`！两者有 20/29 条不同名）
        /// <summary>T-079 §⑦ 片 2：格挡保持态的参数名（Bool）。</summary>
        private static readonly int IsBlockingHash = Animator.StringToHash("IsBlocking");

        /// <summary>T-079 §⑦ 片 2：格挡受击状态名（`Animator.Play` 用的是**状态名**）。</summary>
        private const string BlockHitStateName = "Block_Hit";

        // ================= T-079 §⑨ 片 4：空手组 =================
        // ⚠️ 下面**一个参数名 + 四个状态名**都必须与 `MageSetup`（Editor 程序集）**逐字一致** ——
        //    两个程序集不能互相引用，只能各写一份；**名字不匹配不会报错，只会静默不动**（陷阱 20 / 21）。
        //    * 参数：`MageSetup.UnarmedParam` = `"Unarmed"`（Bool，电平 = "主手空着"）
        //    * 状态：`MageSetup.Wanted[]` 的**首列** = `MageSetup.UnarmedStates` 的名字
        //      （**不是** `expectSource`：这四条**首列与源名全不同**
        //       —— `Idle_Unarmed`←`Unarmed_Idle`、`Punch_A/B`←`Unarmed_Melee_Attack_Punch_A/B`、
        //          `Kick`←`Unarmed_Melee_Attack_Kick`）

        /// <summary>T-079 §⑨ 片 4：空手保持态的参数名（Bool）。由本类 `Update` 每帧喂 `PlayerCombat.IsUnarmed`。</summary>
        private static readonly int UnarmedHash = Animator.StringToHash("Unarmed");

        /// <summary>
        /// T-079 §⑨ 片 4：三条空手出拳的**状态名**（`Animator.Play` 直接寻址用；顺序即循环顺序）。
        /// ⚠️ 出拳**不新增 Trigger 参数**：同帧若既有 `Hit`/`Slash`/`BowShot` 也成立，
        /// 谁赢取决于 AnyState 求值顺序（本项目未定义、未控制）→ 直接 `Play` 才是确定的。
        /// </summary>
        private static readonly string[] UnarmedAttackStateNames = { "Punch_A", "Punch_B", "Kick" };

        /// <summary>下一次空手出拳播第几条（0=拳A → 1=拳B → 2=踢，循环）。</summary>
        private int unarmedPunchIndex;

        /// <summary>下一次护手拳击播哪一只（0=GauntletPunch_A → 1=GauntletPunch_B，交替）。</summary>
        private int gauntletPunchIndex;

        // ================= 动画层扩展：护手拳击 / 盾击（左手镜像动作） =================
        // ⚠️ 三个状态名必须与 `MageSetup.cs` 生成的状态**逐字一致**（它直接引用 `WeaponAnimMap` 的常量，
        //    单一来源）。没重跑安装器时状态不存在 → `Animator.Play` 会刷警告，这里挡一次、只警告一次。
        private static readonly int GauntletPunchAHash = Animator.StringToHash(WeaponAnimMap.StateGauntletPunchA);
        private static readonly int GauntletPunchBHash = Animator.StringToHash(WeaponAnimMap.StateGauntletPunchB);
        private static readonly int ShieldBashHash = Animator.StringToHash(WeaponAnimMap.StateShieldBash);

        // ---- 降级动作（镜像状态不存在时用；哈希的单一来源同样在 `WeaponAnimMap`）----
        // 🔴 **为什么必须有降级**：本工程当前的 `MageAnimator.controller` 里**没有**
        //    `GauntletPunch_A/B` / `ShieldBash` 三个状态（生成器加过代码，但没重跑）。
        //    原实现在这里直接 `return` → **按键完全没有动作**。而"手部左右错位"和"按键没反应"
        //    对玩家的手感差别是**天壤之别**：前者是个小瑕疵，后者是"操作坏了"。
        //    所以宁可播右手拳，也不能什么都不播。
        private static readonly int FallbackGauntletAHash = Animator.StringToHash(WeaponAnimMap.FallbackGauntletPunchA);
        private static readonly int FallbackGauntletBHash = Animator.StringToHash(WeaponAnimMap.FallbackGauntletPunchB);
        private static readonly int FallbackShieldBashHash = Animator.StringToHash(WeaponAnimMap.FallbackShieldBash);

        /// <summary>镜像状态缺失时只警告一次（避免每帧刷屏）。</summary>
        private static bool warnedMissingMirrorStates;

        /// <summary>一套连招有几段。要和 MageSetup 里 ComboClips 的长度一致。</summary>
        public const int ComboLength = 4;

        private Animator animator;
        private PlayerCombat combat;

        private void Awake()
        {
            animator = GetComponentInChildren<Animator>();
            combat = GetComponent<PlayerCombat>();
        }

        private void Update()
        {
            // ⚠️ 这里原来把 `move.AnimSpeed` 写进 `Speed` 参数，本轮**移除** —— 见文件头那段说明：
            //    `Speed` 的唯一写入者是 `PlayerController8Dir`（它同时还要按速度算播放倍率）。
            // 攻击/施法由 PlayerCombat 驱动。

            // T-079 §⑦ 片 2：格挡保持态。**每帧喂**（与 `Speed` 同一个地方、同一种语义：
            // "此刻是不是这个状态"）。`PlayerCombat.IsBlocking` 在它自己的 `Update` 里逐帧赋值为
            // `shieldUp`（`PlayerCombat.cs:120-121`），本方法只做搬运，**不自己判定举盾**。
            if (animator != null)
            {
                // 烘焙场景里 Awake 的时序不可靠（同 PlayerHealth.Start 的兜底），拿不到就再取一次
                if (combat == null) combat = GetComponent<PlayerCombat>();
                animator.SetBool(IsBlockingHash, combat != null && combat.IsBlocking);

                // T-079 §⑨ 片 4：**空手保持态**。与 `IsBlocking` 逐字同形（每帧喂一个"此刻是不是"的电平量）。
                // ⚠️ 这里的搬运是**唯一**决定"能不能进 Idle_Unarmed"的地方：
                //    它真 → 控制器里 `Idle → Idle_Unarmed` 那条边才会成立（反向 = 装回武器就退回 Idle）。
                animator.SetBool(UnarmedHash, combat != null && combat.IsUnarmed);
            }
        }

        /// <summary>
        /// T-079 §⑨ 片 4：播**空手出拳**（`Punch_A` → `Punch_B` → `Kick` 循环，单次动作）。
        ///
        /// **谁调、什么时候调**：`PlayerCombat.UnarmedPunch`（`Use()` 的 `weapon == null` 那一支，
        /// 或 `case WeaponKind.Unarmed`）—— 也就是**左键**、且**主手确实空着**、且**冷却已过**时。
        /// 本方法**不判伤害**：空手不落伤害、不生成弹道（§⑨ I4）。
        ///
        /// ⚠️ **为什么用 `Animator.Play(状态名)` 而不是新增 Trigger 参数**：
        /// ① 同帧若 `Hit`（挨打）/`Slash`（挥剑）/`BowShot` 也成立，多条 AnyState 同时满足 →
        ///    **谁赢取决于 AnyState 的求值顺序（本项目既未定义也未控制）** → 出拳可能**永远播不出来且不报错**；
        /// ② 直接寻址是 0 帧延迟、确定的，且**不需要新增第二个参数**。
        /// ⚠️ 出边仍在控制器里（三条 exit-time 回 `Idle_Unarmed`）→ **不会卡在出拳动作里**。
        /// ⚠️ 用**状态名**寻址 —— 必须与 `MageSetup.UnarmedStates` 逐字一致（见上面的注释）。
        /// </summary>
        public void PlayUnarmedAttack()
        {
            if (animator == null) return;
            string stateName = UnarmedAttackStateNames[unarmedPunchIndex];
            unarmedPunchIndex = (unarmedPunchIndex + 1) % UnarmedAttackStateNames.Length;
            animator.Play(stateName, 0, 0f);
        }

        /// <summary>
        /// **武器 → 攻击动画的统一入口**。`PlayerCombat` 只把"用哪件武器"告诉这里，
        /// 播什么动作由 <see cref="WeaponAnimMap"/> 决定（动画层唯一映射点）。
        ///
        /// 映射（对应用户诉求）：
        ///   法杖 = 施法（Cast）、剑 = 四段连招（Attack1..4）、弓 = 射击（BowShot）、
        ///   护手 = 左手拳击（GauntletPunch_A/B）、盾 = 左手盾击（Shield_Bash）、空手 = 拳/踢循环。
        ///
        /// ⚠️ 本方法**只负责动画**：伤害 / 冷却 / 判定距离 / 弹道全在 `PlayerCombat` 里，一处没动。
        /// ⚠️ 护手 / 盾击走 `Animator.Play(状态名)` 直接寻址，理由与空手出拳完全相同：
        ///    同帧多条 AnyState 同时成立时谁赢未定义（陷阱 22），直接寻址才是确定的。
        /// </summary>
        /// <param name="kind">这次出手用的武器类型（主手或副手，由 <c>PlayerCombat.Use</c> 决定）。</param>
        /// <param name="comboStep">剑连招段位（0..3），其它武器忽略。</param>
        public void PlayWeaponAttack(WeaponKind kind, int comboStep = 0)
        {
            switch (WeaponAnimMap.AttackOf(kind))
            {
                case AttackAnimKind.Cast: PlayCast(); break;
                case AttackAnimKind.SwordCombo: PlayAttack(comboStep); break;
                case AttackAnimKind.BowShot: PlayBowShot(); break;
                case AttackAnimKind.Punch: PlayGauntletPunch(); break;
                case AttackAnimKind.ShieldBash: PlayShieldBash(); break;
                case AttackAnimKind.UnarmedCombo: PlayUnarmedAttack(); break;
                default: break;   // 抓钩等：没有动作
            }
        }

        /// <summary>
        /// 护手拳击：左手镜像的 `Punch_A` / `Punch_B` 交替播。
        /// （原生 `Punch_A/B` 是**右手**动作，装在副手——左手的护手直接播会左右手错位。）
        /// </summary>
        public void PlayGauntletPunch()
        {
            if (animator == null) return;
            bool left = (gauntletPunchIndex++ & 1) == 0;
            int hash = left ? GauntletPunchAHash : GauntletPunchBHash;
            if (HasMirrorState(hash, "护手拳击"))
            {
                animator.Play(hash, 0, 0f);
                return;
            }

            // 降级：左右手对不上 ≠ 没动作。右手原生拳击至少"打得出去"。
            animator.Play(left ? FallbackGauntletAHash : FallbackGauntletBHash, 0, 0f);
        }

        /// <summary>
        /// 盾击：左手镜像的短窗口推击（原来是误播剑的横劈 `Attack1`，和盾毫无关系）。
        /// 镜像状态不存在时降级到 `Punch_A`（向前短促推击，观感是现有剪辑里最接近盾撞的一条）。
        /// </summary>
        public void PlayShieldBash()
        {
            if (animator == null) return;
            if (HasMirrorState(ShieldBashHash, "盾击"))
            {
                animator.Play(ShieldBashHash, 0, 0f);
                return;
            }

            animator.Play(FallbackShieldBashHash, 0, 0f);
        }

        /// <summary>
        /// 控制器里是否真有这个镜像状态。没跑过「安装法师角色」时状态不存在，
        /// `Animator.Play` 会每帧刷警告 —— 这里挡一次并**只警告一次**。
        /// ⚠️ 警告文本要说清"已经降级"：否则日志看上去像"没事"，而真正的修复动作（重跑安装器）就没人做了。
        /// </summary>
        private bool HasMirrorState(int stateHash, string what)
        {
            if (animator.HasState(0, stateHash)) return true;
            if (!warnedMissingMirrorStates)
            {
                warnedMissingMirrorStates = true;
                Debug.LogWarning($"[My World] 控制器里没有「{what}」状态（装的是旧控制器）——"
                                 + "已降级到原生右手动作，观感会左右手错位。"
                                 + "修复：重跑「Tools/My World/安装法师角色」重新生成 AnimatorController。");
            }
            return false;
        }

        /// <summary>播放施法动作。实际的伤害/弹道由 PlayerCombat 负责。</summary>
        public void PlayCast()
        {
            if (animator != null) animator.SetTrigger(AttackHash);
        }

        /// <summary>
        /// 播放挥砍动作（剑/斧这类近战主手）。
        ///
        /// 用**独立的 `Slash` 触发器**，不能复用 `Attack`：那个参数（以及
        /// MageAnimator 里的 AnyState 过渡）是给施法用的，接到 Cast 状态上。
        /// 之前 `PlayAttack()` 和 `PlayCast()` 共用一个 trigger，所以挥剑播的是
        /// 法师原地念咒的动作 —— 也就是"挥砍时什么动作都没有"的直接原因。
        /// </summary>
        public void PlayAttack()
        {
            PlayAttack(0);
        }

        /// <summary>
        /// 播放连招的第 <paramref name="comboStep"/> 段（0=横劈 1=下劈 2=斜劈 3=突刺）。
        ///
        /// `ComboStep` 是整数参数，Animator 里每段状态挂一个 "Slash + ComboStep == n" 的
        /// AnyState 过渡。用整数而不是四个独立触发器，是为了参数少、而且同时只会命中一条过渡。
        /// </summary>
        public void PlayAttack(int comboStep)
        {
            if (animator == null) return;
            animator.SetInteger(ComboHash, Mathf.Clamp(comboStep, 0, ComboLength - 1));
            animator.SetTrigger(SlashHash);
        }

        /// <summary>
        /// 播放射箭动作（T-050）。用**独立的 `BowShot` 触发器**，理由与 `PlayAttack` 用 `Slash` 完全一致：
        /// 若改用 `PlayAttack()`，它会 `SetInteger(ComboStep, 0)` + `SetTrigger(Slash)` ——
        /// 结果是 **①射箭播横劈**、**②动到剑的连招段位**、**③Trigger 若当帧没被消费会残留**，
        /// 之后莫名再挥一刀。三个都是静默的。
        ///
        /// ⚠️ 本方法**只起手**；箭矢由剪辑上的 `OnArrowRelease` 事件经 `AnimEventRelay` 回调
        /// `PlayerCombat.OnArrowRelease()` 才生成。
        /// </summary>
        public void PlayBowShot()
        {
            if (animator != null) animator.SetTrigger(BowShotHash);
        }

        /// <summary>供木桩/敌人回调，播受击动作。</summary>
        public void PlayHit()
        {
            if (animator != null) animator.SetTrigger(HitHash);
        }

        /// <summary>
        /// T-079 §⑦ 片 2：播**格挡受击**（`Block_Hit`）。
        ///
        /// **谁调、什么时候调**：`PlayerHealth.TakeDamage` 在**真正减伤那一刻**调它 ——
        /// 落点在 80° 角检**内部**、与 `amount *= mult`（`PlayerHealth.cs:144-151`）**同一层**。
        /// **不是**"举着盾"那层（`:139`，那里只问有没有举盾、不看攻击来自哪个方向），
        /// **更不是**按键那一刻。**表现跟随事实，不跟随意图。**
        /// 侧后方挨打（角度 > 80°）**不该**播它 —— 由"调用点只在角检里"这一条保证（不是靠这里判方向）。
        ///
        /// ⚠️ **为什么用 `Animator.Play(状态名, 0, 0)`，而不是新增一个 Trigger 参数**：
        /// ① 新增 Trigger = **再新增一个参数**，而本片的预期新增只有 `IsBlocking` + 三个状态；
        /// ② `PlayHit()` 与本节在同一帧、同一方法里（`TakeDamage`）都会被调用到，
        ///    两个 Trigger 同帧成立时谁赢取决于 AnyState 的判定顺序 → **不确定**；
        ///    拆成**互斥两支**（挡住 → 本方法；没挡住 → `PlayHit`）+ 直接 `Play` 才是确定的。
        /// ③ 出边仍在控制器里（`Block_Hit` 的两条 exit time 出边）→ **不会卡在 `Block_Hit` 里**。
        /// ⚠️ 用**状态名**寻址 —— 必须与 `MageSetup.Wanted[]` 的**首列**逐字一致（见上面的注释）。
        /// </summary>
        public void PlayBlockHit()
        {
            if (animator != null) animator.Play(BlockHitStateName, 0, 0f);
        }

        /// <summary>死亡动作（留着给后面的战斗系统用）。</summary>
        public void PlayDeath()
        {
            if (animator != null) animator.SetBool(DeadHash, true);
        }

        // ================= T-091 批次 1：翻滚闪避 =================
        /// <summary>翻滚方向枚举值，**必须与 `MageSetup.DodgeClips` 的下标一致**。</summary>
        public enum DodgeDirection
        {
            Forward = 0,
            Backward = 1,
            Left = 2,
            Right = 3,
        }

        /// <summary>
        /// 播一次翻滚（四个方向共用 `Dodge` 触发器 + `DodgeDir` 整数）。
        ///
        /// **谁调**：`PlayerController8Dir` 的翻滚窗口起手那一刻（它同时负责位移推进）。
        ///
        /// ⚠️ **`Dodge` 是 Trigger（边沿）而不是 Bool（电平）**：翻滚是一次性动作，播完就该失效；
        ///    写成 Bool 的话，只要按住键就会每帧满足 AnyState 条件把状态机拽回去（格挡/空手
        ///    那两条电平参数踩过这个坑，见 `MageSetup` 里"为什么入口边不用 AnyState"的说明）。
        ///
        /// ⚠️ **本方法只起手，不产生位移**。prefab 上 `applyRootMotion=false`，剪辑自带的根位移
        ///    被 Unity 丢弃 —— 位移由调用方在同一翻滚窗口内推进，否则观感是「原地打个滚」。
        /// </summary>
        public void PlayDodge(DodgeDirection dir)
        {
            if (animator == null) return;
            animator.SetInteger(DodgeDirHash, (int)dir);
            animator.SetTrigger(DodgeHash);
        }
    }
}
