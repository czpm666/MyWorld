using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 命中分级。**打击感的所有强度都由它索引** —— 顿帧、震屏、粒子量、击退、
    /// 受击闪色、飘字大小，全部查同一张表，所以"重击比轻击狠"是**结构性保证**，
    /// 不是一堆各自硬编码的数字恰好凑出来的。
    /// </summary>
    public enum HitGrade
    {
        Light = 0,   // 轻击：蹭到 / 小伤害
        Heavy = 1,   // 重击：实打实的一下
        Crit = 2,    // 暴击：会心一击，最狠
    }

    /// <summary>
    /// **打击感集中调参处**（打击特效 T-0xx）。
    ///
    /// 设计约定（改代码前先读这三条）：
    ///   1. **"这次打得多狠"只由 <see cref="Grade(float)"/> 回答**。业务代码不该出现
    ///      `if (damage > 20f) 震 0.3f` 这种散落的阈值 —— 那样调一次手感要改五个文件。
    ///   2. **表是 3 元的，下标就是 <see cref="HitGrade"/>**。加一档（比如"处决"）只改表长，
    ///      不用改任何调用点。
    ///   3. **暴击默认不改伤害**（<see cref="CritDamageMultiplier"/> = 1）。分级在这里
    ///      是**表现层**的事；要不要让暴击真的多掉血是**平衡**的事，需要单独批准。
    ///      想开启就把倍率调到 > 1，逻辑侧不需要改一行。
    ///
    /// 调参方式：Play 模式下选中 `[VfxHub]` 物体上的 `VfxFeelSettings` 组件改数值，
    /// 它的 `OnValidate` 会把值写回这里 —— **不需要重启 Play**。
    /// </summary>
    public static class VfxFeel
    {
        // ================= 分级阈值（伤害值） =================

        /// <summary>伤害 ≥ 这个值算重击。</summary>
        public static float HeavyDamage = 18f;

        /// <summary>伤害 ≥ 这个值直接算暴击（不用掷骰）。</summary>
        public static float CritDamage = 34f;

        /// <summary>每次命中的暴击概率。设 0 = 关闭随机暴击，分级完全由伤害决定（QA 喜欢这个）。</summary>
        public static float CritChance = 0.12f;

        /// <summary>暴击的伤害倍率。**1 = 不改伤害**（默认，纯表现分级）。</summary>
        public static float CritDamageMultiplier = 1f;

        /// <summary>QA 用：≥0 时**强制**返回该档（0/1/2），忽略伤害与骰子。-1 = 自动。</summary>
        public static int ForceGradeIndex = -1;

        // ================= 顿帧（秒） =================

        /// <summary>总开关。关掉后 <see cref="VfxHub.HitStop"/> 直接返回，其它表现不受影响。</summary>
        public static bool HitStopEnabled = true;

        /// <summary>[轻/重/暴] 顿帧时长。`VfxHub.HitStop` 内部上限 0.12s，超过会被夹。</summary>
        public static readonly float[] HitStopSeconds = { 0.035f, 0.065f, 0.095f };

        /// <summary>
        /// [轻/重/暴] 顿帧**深度**：`Time.timeScale` 被压到多少。**越小顿得越死**。
        /// 上面那张表只决定"顿多久"，这张表决定"顿多深" —— 只有时长分级等于白分级
        /// （三档都冻到同一个倍速，手感一模一样，QA 的 `MinTimeScale` 也分不出来）。
        /// 暴击 0.035 ≈ 轻击的 3 倍深，读出来就是"整个世界一顿"。
        /// ⚠️ 声明顺序：`HitStopDepth` 的初始化依赖它，这里不能挪到下面。
        /// </summary>
        public static readonly float[] HitStopDepthDefault = { 0.10f, 0.06f, 0.035f };

        /// <summary>运行时表（`VfxFeelSettings.Apply()` 会把 Inspector 的值整体写进这里）。</summary>
        public static readonly float[] HitStopDepth = (float[])HitStopDepthDefault.Clone();

        // ================= 相机震动（幅度：米 / 时长：秒） =================

        public static readonly float[] ShakeAmplitude = { 0.14f, 0.30f, 0.46f };
        public static readonly float[] ShakeSeconds = { 0.10f, 0.16f, 0.22f };

        // ================= 粒子 / 光效倍率 =================

        /// <summary>[轻/重/暴] 粒子数量与尺寸的统一倍率。</summary>
        public static readonly float[] EffectScale = { 1.00f, 1.55f, 2.20f };

        // ================= 受击方反馈 =================

        /// <summary>[轻/重/暴] 受击闪色。轻=白，重=暖橙，暴=赤红 —— 和 Bloom 阈值配合。</summary>
        public static readonly Color[] FlashColor =
        {
            new Color(1.00f, 1.00f, 1.00f),
            new Color(1.00f, 0.78f, 0.42f),
            new Color(1.00f, 0.42f, 0.30f),
        };

        /// <summary>[轻/重/暴] 闪色持续时间。</summary>
        public static readonly float[] FlashSeconds = { 0.10f, 0.15f, 0.22f };

        /// <summary>[轻/重/暴] 受击僵直倍率（乘在 Enemy 自己的 hitStunDuration 上）。</summary>
        public static readonly float[] StunScale = { 1.00f, 1.25f, 1.50f };

        /// <summary>
        /// [轻/重/暴] 每档的击退"格数"（1 格 = 2 米，和敌人技能同一套换算）。
        ///
        /// ⚠️ 这几档**刻意做得很小**（轻 0.18 格 = 0.36 m，重约 0.5~0.6 m）。
        ///    它们是"挨了一下往后一挫"的**踉跄**，不是"被打飞" ——
        ///    真正的打飞是第四段突刺的 `stabKnockbackGrids`（2 格 = 4 m，有硬契约）。
        ///    分级击退一旦调大，普通连招就会把敌人一路顶出近战范围，
        ///    手感变成"追着打"，那是**玩法改动**、需要单独批准。
        /// </summary>
        public static readonly float[] KnockbackGridsDefault = { 0.18f, 0.45f, 0.85f };

        /// <summary>运行期实际生效的击退格数（由 <see cref="KnockbackGridsDefault"/> 起步，可被 Inspector 覆盖）。</summary>
        public static readonly float[] KnockbackGrids = (float[])KnockbackGridsDefault.Clone();

        // ================= 飘字 =================

        public static bool DamageTextEnabled = true;

        /// <summary>[轻/重/暴] 飘字的世界高度（米）。</summary>
        public static readonly float[] TextScale = { 0.42f, 0.58f, 0.78f };

        /// <summary>[轻/重/暴] 飘字颜色。</summary>
        public static readonly Color[] TextColor =
        {
            new Color(0.95f, 0.93f, 0.86f),   // 羊皮纸白
            new Color(1.00f, 0.84f, 0.32f),   // 金
            new Color(1.00f, 0.45f, 0.22f),   // 橙红
        };

        /// <summary>飘字存活时间（秒）。</summary>
        public static float TextLife = 0.85f;

        // ================= 性能安全阀 =================

        /// <summary>
        /// 每帧最多允许新建多少个"一次性特效物体"（月牙/盾弧/感叹号这类必须 new GameObject 的）。
        /// 超过就直接跳过 —— 同屏二十个敌人同时命中时，宁可少几个月牙也不要卡帧。
        /// **粒子本身永远走池，不受这个限制。**
        /// </summary>
        public static int MaxTransientPerFrame = 6;

        // ================= 查询接口 =================

        // 同一次命中会被**三个地方**问档位：受击方（闪色/僵直）、特效层（粒子/顿帧/震屏）、
        // 音频层（轻响还是暴击叠层）。如果每次都重新掷骰，三方会得到**不同**的答案 ——
        // 于是"敌人闪了暴击的赤红、却只播了轻击音"。所以同一帧内、同一伤害值只掷一次。
        private static int gradeFrame = -1;
        private static float gradeDamage;
        private static HitGrade gradeCached;
        private static bool gradeCachedCrit;

        /// <summary>
        /// 这次命中算哪一档。`crit` 输出"是不是掷骰掷出来的暴击"（飘字要不要带 `!`）。
        ///
        /// 顺序：QA 强制 &gt; 本帧缓存 &gt; 掷骰 &gt; 伤害阈值。伤害阈值放最后，所以一个 50 伤害的
        /// 普通攻击**也**是暴击档 —— "这一下很重"和"这一下会心"在观感上是同一件事。
        ///
        /// ⚠️ **本帧缓存是刻意的**，见字段上方的注释。注意它按 (帧号, 伤害值) 命中，
        /// 所以同帧两个不同伤害的敌人各掷各的。
        /// </summary>
        public static HitGrade Grade(float damage, out bool crit)
        {
            crit = false;

            if (ForceGradeIndex >= 0)
            {
                HitGrade forced = (HitGrade)Mathf.Clamp(ForceGradeIndex, 0, 2);
                crit = forced == HitGrade.Crit;
                return forced;
            }

            int frame = Time.frameCount;
            if (frame == gradeFrame && Mathf.Approximately(damage, gradeDamage))
            {
                crit = gradeCachedCrit;
                return gradeCached;
            }

            HitGrade g = Roll(damage, out bool rolledCrit);
            gradeFrame = frame;
            gradeDamage = damage;
            gradeCached = g;
            gradeCachedCrit = rolledCrit;

            crit = rolledCrit;
            return g;
        }

        private static HitGrade Roll(float damage, out bool crit)
        {
            if (CritChance > 0f && Random.value < CritChance)
            {
                crit = true;
                return HitGrade.Crit;
            }

            crit = false;
            return DeterministicGrade(damage);
        }

        /// <summary>
        /// **不掷骰**的档位，只看伤害阈值。给"不能引入随机性"的场合用：
        /// 击退距离、QA 断言、以及同一次命中里被问第二次的地方。
        /// </summary>
        public static HitGrade DeterministicGrade(float damage)
        {
            if (ForceGradeIndex >= 0) return (HitGrade)Mathf.Clamp(ForceGradeIndex, 0, 2);
            if (damage >= CritDamage) return HitGrade.Crit;
            if (damage >= HeavyDamage) return HitGrade.Heavy;
            return HitGrade.Light;
        }

        /// <summary>只要档位，不要暴击标记。</summary>
        public static HitGrade Grade(float damage)
        {
            bool ignored;
            return Grade(damage, out ignored);
        }

        /// <summary>档位下标安全取值（表长变了也不会越界）。</summary>
        public static int Index(HitGrade grade)
        {
            return Mathf.Clamp((int)grade, 0, 2);
        }

        public static float HitStopFor(HitGrade grade) => HitStopSeconds[Index(grade)];
        /// <summary>[轻/重/暴] 顿帧深度（timeScale 压到多少，越小顿得越死）。</summary>
        public static float HitStopDepthFor(HitGrade grade) => HitStopDepth[Index(grade)];
        public static float ShakeAmpFor(HitGrade grade) => ShakeAmplitude[Index(grade)];
        public static float ShakeTimeFor(HitGrade grade) => ShakeSeconds[Index(grade)];
        public static float EffectScaleFor(HitGrade grade) => EffectScale[Index(grade)];
        public static Color FlashColorFor(HitGrade grade) => FlashColor[Index(grade)];
        public static float FlashSecondsFor(HitGrade grade) => FlashSeconds[Index(grade)];
        public static float StunScaleFor(HitGrade grade) => StunScale[Index(grade)];
        public static Color TextColorFor(HitGrade grade) => TextColor[Index(grade)];
        public static float TextScaleFor(HitGrade grade) => TextScale[Index(grade)];

        /// <summary>
        /// 按伤害算**击退格数**（1 格 = 2 米）。和 <see cref="KnockbackGrids"/> 的关系：
        /// 表给的是"每档的基础格数"，这里再按伤害在档内插值，所以
        /// "25 伤害" 会比 "20 伤害" 推得远一点，而不是两下一样。
        ///
        /// ⚠️ 用 <see cref="DeterministicGrade"/> 而不是 <see cref="Grade(float)"/>：
        ///    击退是**位移**，不能被一次骰子决定 —— 否则同样的伤害一会儿推得远一会儿推得近。
        /// </summary>
        public static float KnockbackGridsFor(float damage)
        {
            int i = Index(DeterministicGrade(damage));
            float baseGrids = KnockbackGrids[i];

            // 档内微调：以本档阈值为基准，最多再 +50%
            float reference = i == 0 ? HeavyDamage : (i == 1 ? CritDamage : CritDamage * 1.5f);
            float extra = Mathf.Clamp01(damage / Mathf.Max(1f, reference)) * 0.5f;
            return baseGrids * (1f + extra);
        }

        /// <summary>按伤害算击退**距离（米）**。调用方直接把它交给 ApplyKnockback。</summary>
        public static float KnockbackDistance(float damage)
        {
            return KnockbackGridsFor(damage) * 2f;
        }

        /// <summary>
        /// 一发命中的**顿帧 + 震屏 + 飘字**三件套的唯一入口。
        /// `damage &lt; 0`（默认）表示只做顿帧和震屏、不飘字 —— 格挡、打墙、抓钩命中
        /// 这些"没有伤害数字"的场合走这条路。
        /// </summary>
        public static void ApplyImpactFeel(HitGrade grade, Vector3 point, float damage = -1f)
        {
            if (HitStopEnabled) VfxHub.HitStop(HitStopFor(grade), HitStopDepthFor(grade));

            VfxHub hub = VfxHub.Instance;
            if (hub != null) hub.AddShake(ShakeAmpFor(grade), ShakeTimeFor(grade));

            if (damage >= 0f) VfxTextPool.Damage(point, damage, grade);
        }

        /// <summary>只飘字、不顿帧不震屏（例如持续伤害的每跳）。</summary>
        public static void ApplyTextOnly(float damage, HitGrade grade, Vector3 point)
        {
            if (damage >= 0f) VfxTextPool.Damage(point, damage, grade);
        }

        /// <summary>把表恢复到出厂值。`VfxFeelSettings.ResetToDefaults()` 会调它。</summary>
        public static void ResetToDefaults()
        {
            HeavyDamage = 18f;
            CritDamage = 34f;
            CritChance = 0.12f;
            CritDamageMultiplier = 1f;
            ForceGradeIndex = -1;

            HitStopEnabled = true;
            Set(HitStopSeconds, 0.035f, 0.065f, 0.095f);
            Set(HitStopDepth, HitStopDepthDefault[0], HitStopDepthDefault[1], HitStopDepthDefault[2]);

            Set(ShakeAmplitude, 0.14f, 0.30f, 0.46f);
            Set(ShakeSeconds, 0.10f, 0.16f, 0.22f);
            Set(EffectScale, 1.00f, 1.55f, 2.20f);

            Set(FlashSeconds, 0.10f, 0.15f, 0.22f);
            Set(StunScale, 1.00f, 1.25f, 1.50f);
            Set(KnockbackGrids, KnockbackGridsDefault[0], KnockbackGridsDefault[1], KnockbackGridsDefault[2]);

            DamageTextEnabled = true;
            Set(TextScale, 0.42f, 0.58f, 0.78f);
            TextLife = 0.85f;

            MaxTransientPerFrame = 6;
        }

        private static void Set(float[] table, float a, float b, float c)
        {
            if (table == null || table.Length < 3) return;
            table[0] = a; table[1] = b; table[2] = c;
        }
    }

    /// <summary>
    /// 把 <see cref="VfxFeel"/> 的静态表暴露到 Inspector。挂在 `[VfxHub]` 上（由 VfxHub 自己加）。
    ///
    /// **为什么用组件而不是纯常量**：手感是要"边打边拧"的。做成组件后，Play 模式下
    /// 改一个数就立刻生效（`OnValidate` 写回静态表），不用改代码、不用退出 Play。
    /// 出厂值仍然写在 <see cref="VfxFeel"/> 里，所以就算这个组件没被创建，游戏也是对的。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class VfxFeelSettings : MonoBehaviour
    {
        [Header("分级阈值（伤害）")]
        [Tooltip("伤害 ≥ 这个值算重击")]
        public float heavyDamage = 18f;
        [Tooltip("伤害 ≥ 这个值直接算暴击")]
        public float critDamage = 34f;
        [Range(0f, 1f)]
        [Tooltip("每次命中的暴击概率。0 = 关闭随机，分级只由伤害决定")]
        public float critChance = 0.12f;
        [Tooltip("暴击伤害倍率。1 = 不改伤害（默认：分级只是表现）")]
        public float critDamageMultiplier = 1f;

        [Header("顿帧（秒）轻/重/暴")]
        public bool hitStopEnabled = true;
        public float[] hitStopSeconds = { 0.035f, 0.065f, 0.095f };
        [Header("顿帧深度（timeScale 压到多少）轻/重/暴 —— 越小顿得越死")]
        [Tooltip("初值取自 VfxFeel.HitStopDepthDefault —— 出厂值只有那一个真源，别再往这里抄一份数字")]
        public float[] hitStopDepth = (float[])VfxFeel.HitStopDepthDefault.Clone();

        [Header("震屏（幅度米）轻/重/暴")]
        public float[] shakeAmplitude = { 0.14f, 0.30f, 0.46f };
        [Header("震屏（时长秒）轻/重/暴")]
        public float[] shakeSeconds = { 0.10f, 0.16f, 0.22f };

        [Header("粒子/光效倍率 轻/重/暴")]
        public float[] effectScale = { 1.00f, 1.55f, 2.20f };

        [Header("受击闪色时长 轻/重/暴")]
        public float[] flashSeconds = { 0.10f, 0.15f, 0.22f };
        [Header("受击僵直倍率 轻/重/暴")]
        public float[] stunScale = { 1.00f, 1.25f, 1.50f };
        [Header("击退格数 轻/重/暴（1 格 = 2 米）")]
        [Tooltip("初值取自 VfxFeel.KnockbackGridsDefault —— 出厂值只有那一个真源，别再往这里抄一份数字")]
        public float[] knockbackGrids = (float[])VfxFeel.KnockbackGridsDefault.Clone();

        [Header("伤害飘字")]
        public bool damageTextEnabled = true;
        [Tooltip("飘字世界高度（米）轻/重/暴")]
        public float[] textScale = { 0.42f, 0.58f, 0.78f };
        public float textLife = 0.85f;

        [Header("性能安全阀")]
        [Tooltip("每帧最多新建多少个一次性特效物体（月牙/盾弧/感叹号）。粒子永远走池，不受限")]
        public int maxTransientPerFrame = 6;

        [Header("QA")]
        [Tooltip("强制档位：-1=自动，0=轻，1=重，2=暴击")]
        public int forceGradeIndex = -1;

        private void Awake()
        {
            Apply();
        }

        private void OnValidate()
        {
            Apply();
        }

        /// <summary>把 Inspector 的值写回 <see cref="VfxFeel"/> 的静态表。</summary>
        public void Apply()
        {
            VfxFeel.HeavyDamage = heavyDamage;
            VfxFeel.CritDamage = critDamage;
            VfxFeel.CritChance = critChance;
            VfxFeel.CritDamageMultiplier = critDamageMultiplier;
            VfxFeel.ForceGradeIndex = forceGradeIndex;

            VfxFeel.HitStopEnabled = hitStopEnabled;
            Copy(hitStopSeconds, VfxFeel.HitStopSeconds);
            Copy(hitStopDepth, VfxFeel.HitStopDepth);

            Copy(shakeAmplitude, VfxFeel.ShakeAmplitude);
            Copy(shakeSeconds, VfxFeel.ShakeSeconds);
            Copy(effectScale, VfxFeel.EffectScale);

            Copy(flashSeconds, VfxFeel.FlashSeconds);
            Copy(stunScale, VfxFeel.StunScale);
            Copy(knockbackGrids, VfxFeel.KnockbackGrids);

            VfxFeel.DamageTextEnabled = damageTextEnabled;
            Copy(textScale, VfxFeel.TextScale);
            VfxFeel.TextLife = textLife;

            VfxFeel.MaxTransientPerFrame = Mathf.Max(0, maxTransientPerFrame);
        }

        /// <summary>回到出厂值（也把 Inspector 里的字段一起刷回来）。</summary>
        public void ResetToDefaults()
        {
            VfxFeel.ResetToDefaults();

            heavyDamage = VfxFeel.HeavyDamage;
            critDamage = VfxFeel.CritDamage;
            critChance = VfxFeel.CritChance;
            critDamageMultiplier = VfxFeel.CritDamageMultiplier;
            forceGradeIndex = VfxFeel.ForceGradeIndex;

            hitStopEnabled = VfxFeel.HitStopEnabled;
            hitStopSeconds = (float[])VfxFeel.HitStopSeconds.Clone();
            hitStopDepth = (float[])VfxFeel.HitStopDepth.Clone();
            shakeAmplitude = (float[])VfxFeel.ShakeAmplitude.Clone();
            shakeSeconds = (float[])VfxFeel.ShakeSeconds.Clone();
            effectScale = (float[])VfxFeel.EffectScale.Clone();
            flashSeconds = (float[])VfxFeel.FlashSeconds.Clone();
            stunScale = (float[])VfxFeel.StunScale.Clone();
            knockbackGrids = (float[])VfxFeel.KnockbackGrids.Clone();

            damageTextEnabled = VfxFeel.DamageTextEnabled;
            textScale = (float[])VfxFeel.TextScale.Clone();
            textLife = VfxFeel.TextLife;

            maxTransientPerFrame = VfxFeel.MaxTransientPerFrame;
        }

        private static void Copy(float[] from, float[] to)
        {
            if (from == null || to == null) return;
            int n = Mathf.Min(from.Length, to.Length);
            for (int i = 0; i < n; i++) to[i] = from[i];
        }
    }
}
