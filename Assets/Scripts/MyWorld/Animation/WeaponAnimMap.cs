using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 攻击动作的**动画分类**（与 <see cref="WeaponKind"/> 解耦）。
    /// 运行时脚本只用它决定"播哪类动作"；动画状态与剪辑由 <c>Assets/Editor/MageSetup.cs</c> 生成。
    /// </summary>
    public enum AttackAnimKind
    {
        /// <summary>没有攻击动画（抓钩这类只靠特效/弹道的兵器）。</summary>
        None = 0,
        /// <summary>法杖：施法（`Cast` 状态，`Attack` 触发器）。</summary>
        Cast,
        /// <summary>剑：四段连招（`Attack1..4` 状态，`Slash` + `ComboStep` 驱动）。</summary>
        SwordCombo,
        /// <summary>弓：射击（`BowShot` 状态，`BowShot` 触发器 + `OnArrowRelease` 事件）。</summary>
        BowShot,
        /// <summary>护手：**左手**拳击（`GauntletPunch_A/B` 状态，镜像自右手 `Punch_A/B`）。</summary>
        Punch,
        /// <summary>盾：**左手**盾击（`Shield_Bash` 状态，镜像自 `Punch_A` 的短窗口）。</summary>
        ShieldBash,
        /// <summary>空手：拳/踢循环（`Punch_A`/`Punch_B`/`Kick` 状态，直接寻址）。</summary>
        UnarmedCombo,
    }

    /// <summary>
    /// 武器类型 → 攻击动画的**唯一映射表**（动画层的真值源之一，另一处是 `MageSetup` 生成的控制器）。
    ///
    /// 用户诉求（本轮改造）：法杖=施法动作、剑=四段连招、弓=射击、护手=拳击、盾=盾击、空手=拳脚。
    /// ⚠️ 本表**只影响动作**：伤害、冷却、判定距离、弹道全部留在 `PlayerCombat` 里，一处没动。
    ///
    /// ⚠️ 下面三个镜像动作的**状态名必须与 `MageSetup.cs` 生成的状态逐字一致** ——
    ///    运行时程序集与 Editor 程序集不能互相反向引用，名字不匹配**不会报错、只会静默不动**（陷阱 20/21）。
    ///    `MageSetup` 生成时直接用这里的常量，单一来源，不会漂移。
    /// </summary>
    public static class WeaponAnimMap
    {
        /// <summary>护手拳击第一拳（左手镜像 <c>Punch_A</c>）的状态名。</summary>
        public const string StateGauntletPunchA = "GauntletPunch_A";

        /// <summary>护手拳击第二拳（左手镜像 <c>Punch_B</c>）的状态名。</summary>
        public const string StateGauntletPunchB = "GauntletPunch_B";

        /// <summary>盾击（左手镜像 <c>Punch_A</c> 短窗口）的状态名。</summary>
        public const string StateShieldBash = "Shield_Bash";

        // =====================================================================
        // 降级动作（**镜像状态不存在时**用的原生状态名）
        // =====================================================================
        // 🔴 **为什么需要降级**：上面三个镜像状态是 `MageSetup` 后来加的，而工程里那份
        //    `Assets/ThirdParty/KayKit_Adventurers/MageAnimator.controller` **还没重新生成过**
        //    （实测：26 个状态里没有 `GauntletPunch_A` / `GauntletPunch_B` / `Shield_Bash`）。
        //    原实现在状态缺失时直接 `return` → **护手/盾牌按攻击键完全没有动作**。
        //
        //    降级播的是**右手**的原生拳击 → 手部左右会错位（护手挂在副手/左手）。
        //    这是个**小瑕疵**，而"按键完全没反应"在玩家那里是**操作坏了** —— 两害相权，
        //    宁可错位也要有动作。重跑「Tools/My World/安装法师角色」后这三个常量就再也用不到。
        //
        // ⚠️ 这三个名字必须与控制器里**原生**的状态名逐字一致（`MageSetup.Wanted[]` 的首列）。

        /// <summary>降级：护手第一拳 → 原生右手 <c>Punch_A</c>。</summary>
        public const string FallbackGauntletPunchA = "Punch_A";

        /// <summary>降级：护手第二拳 → 原生右手 <c>Punch_B</c>。</summary>
        public const string FallbackGauntletPunchB = "Punch_B";

        /// <summary>降级：盾击 → 原生 <c>Punch_A</c>（现有剪辑里最接近"向前短促推击"的一条）。</summary>
        public const string FallbackShieldBash = "Punch_A";

        /// <summary>主手/副手武器用哪种攻击动画。</summary>
        public static AttackAnimKind AttackOf(WeaponKind kind)
        {
            switch (kind)
            {
                case WeaponKind.Staff: return AttackAnimKind.Cast;
                case WeaponKind.Sword: return AttackAnimKind.SwordCombo;
                case WeaponKind.Bow: return AttackAnimKind.BowShot;
                case WeaponKind.Gauntlet: return AttackAnimKind.Punch;
                case WeaponKind.Shield: return AttackAnimKind.ShieldBash;
                case WeaponKind.Unarmed: return AttackAnimKind.UnarmedCombo;
                default: return AttackAnimKind.None;   // 抓钩等：无动作
            }
        }

        /// <summary>这件武器有没有"攻击动作"（抓钩返回 false —— 它只走特效/位移）。</summary>
        public static bool HasAttackAnim(WeaponKind kind)
        {
            return AttackOf(kind) != AttackAnimKind.None;
        }
    }
}
