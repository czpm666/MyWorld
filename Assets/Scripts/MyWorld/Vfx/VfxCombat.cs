using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// **打击特效的语义层**：把"发生了什么"翻译成"视觉/听觉表现"。
    ///
    /// 所有方法都是 static、零 GC（粒子走池、环走池、音效走 SfxLibrary 固定声部），
    /// 业务代码（PlayerCombat / 投射物 / VfxDirector）只调这一层，不直接碰粒子系统。
    /// 颜色约定：
    ///   * 剑：暖白/月牙色，第三、四段偏紫金（SkillVfx.SwordSegmentColor 决定）
    ///   * 法杖：紫青符文
    ///   * 盾/格挡：春绿（SkillVfx.BlockColor）
    ///   * 敌人受击：暗红；治疗：绿；金币：金；传送门：紫
    /// </summary>
    public static class VfxCombat
    {
        // ---------------- 调色板 ----------------
        public static readonly Color SwordColor = new Color(1f, 0.88f, 0.62f);
        public static readonly Color HeavyColor = new Color(1f, 0.55f, 0.22f);
        public static readonly Color MagicColor = new Color(0.55f, 0.85f, 1f);
        public static readonly Color RuneColor = new Color(0.72f, 0.45f, 1f);
        public static readonly Color HealColor = new Color(0.45f, 1f, 0.62f);
        public static readonly Color GoldColor = new Color(1f, 0.84f, 0.28f);
        public static readonly Color BlockColor = SkillVfx.BlockColor;
        public static readonly Color EnemyColor = new Color(1f, 0.34f, 0.26f);
        public static readonly Color BloodColor = new Color(0.62f, 0.17f, 0.13f);
        public static readonly Color DustColor = new Color(0.80f, 0.74f, 0.63f);
        public static readonly Color SteelColor = new Color(0.85f, 0.92f, 1f);

        // ================= QA 观测点（不参与任何表现决策） =================

        /// <summary>命中特效的种类。</summary>
        public enum ImpactKind { None = 0, Melee = 1, Spell = 2, Arrow = 3, Block = 4 }

        /// <summary>
        /// **最近一次命中特效的输入快照**。
        ///
        /// 它存在的唯一目的，是让 `Tools/VFX QA` 能**客观断言**验收标准里的两条：
        ///   ① "位置用真实碰撞点" —— 比对 `Point` 与敌人 `transform.position` 的关系，
        ///      证明命中的是**朝攻击者那一侧的表面**，而不是身体中轴；
        ///   ② "方向沿攻击方向" —— 比对 `Direction` 与攻击/弹道方向的点积。
        /// 没有它就只能靠人眼看截图猜，那不是可复现的证据。
        ///
        /// ⚠️ 只写不读：表现逻辑里**没有任何分支**读它，所以它不影响手感、也不参与判定。
        /// </summary>
        public struct ImpactRecord
        {
            public ImpactKind Kind;
            public Vector3 Point;          // 真实碰撞点
            public Vector3 Direction;      // 攻击/弹道方向
            public Vector3 SurfaceNormal;  // 受击表面法线
            public HitGrade Grade;
            public float Damage;
            public int Frame;
        }

        public static ImpactRecord LastImpact { get; private set; }

        static void NoteImpact(ImpactKind kind, Vector3 point, Vector3 dir, Vector3 normal,
            HitGrade grade, float damage)
        {
            LastImpact = new ImpactRecord
            {
                Kind = kind,
                Point = point,
                Direction = dir,
                SurfaceNormal = normal,
                Grade = grade,
                Damage = damage,
                Frame = Time.frameCount,
            };
        }

        // ================= 近战 =================

        /// <summary>
        /// 近战**刀风**：沿挥砍扫过的方向拉出一小束风线。每次挥砍都放（挥空也有反馈）。
        /// `didHit == false` 且是重击段时，额外补一圈地面尘，强调"砸空了"。
        ///
        /// ⚠️ 这里**不再自己扫 `DamageableRegistry` 猜命中点**。旧版把命中点算成
        ///    `敌人.position + Vector3.up * 0.85`（≈ 身体中轴），于是火花**永远从身体正中冒出来**，
        ///    哪怕是从背后砍的也炸在正中间 —— 位置对不上，方向也无从谈起。
        ///    现在真实碰撞点由攻击方传进来（`PlayerCombat.OnSlashImpact` 的 `Collider.ClosestPoint`）。
        /// </summary>
        public static void SwordSwing(Vector3 center, Vector3 forward, float hitRange, int segment, bool didHit)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return;

            Vector3 f = Flatten(forward);
            if (f.sqrMagnitude < 1e-4f) f = Vector3.forward;
            f.Normalize();

            bool heavy = segment >= 3;
            Color color = SkillVfx.SwordSegmentColor(segment);

            // 刀风：沿**横扫**方向（奇偶段反向），不是沿角色朝向 —— 朝向是"打哪边"，横扫是"怎么扫"
            Vector3 right = Vector3.Cross(Vector3.up, f);
            float sweepSign = (segment % 2 == 0) ? -1f : 1f;
            Vector3 sweep = right * sweepSign;
            hub.Burst(hub.Streak, center + f * (hitRange * 0.55f) + Vector3.up * 0.15f, sweep,
                heavy ? 8 : 5, 2.5f, 5.5f, 25f, WithAlpha(Color.Lerp(color, Color.white, 0.25f), 0.8f),
                0.05f, 0.10f, 0.10f, 0.22f, 0f, 0.22f);

            if (!didHit && heavy)
            {
                hub.Burst(hub.Dust, center + f * (hitRange * 0.7f) + Vector3.up * 0.05f, Vector3.up,
                    4, 0.4f, 1.2f, 50f, WithAlpha(DustColor, 0.55f), 0.10f, 0.18f, 0.20f, 0.35f, 0.2f);
            }
        }

        /// <summary>
        /// **近战命中叠层**：打击感三件套（顿帧 + 震屏 + 飘字）+ 火花 + 高光 + 冲击环。
        ///
        /// 三条"方向/位置"契约（验收标准②）：
        ///   * `point`        = **真实碰撞点**（`Collider.ClosestPoint(攻击中心)` 或射线 `hit.point`），
        ///                      不是 `敌人.position` —— 所以打在肩膀和打在脚上是两个位置；
        ///   * `attackDir`    = **攻击方向**。火花沿它喷，冲击环**垂直于它**立起来；
        ///   * `surfaceNormal`= 受击表面的法线。沿它补一小撮火花，让"被砍的那个面"也亮。
        ///
        /// 强度全部由 `damage` 经 <see cref="VfxFeel.Grade"/> 分档查出。
        /// </summary>
        /// <returns>本次命中的档位（调用方可以拿去决定音效/击退）。</returns>
        public static HitGrade MeleeImpact(Vector3 point, Vector3 attackDir, Vector3 surfaceNormal,
            float damage, Color? accent = null)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return HitGrade.Light;

            bool crit;
            HitGrade grade = VfxFeel.Grade(damage, out crit);
            int index = VfxFeel.Index(grade);
            float k = VfxFeel.EffectScaleFor(grade);
            Color color = accent ?? SwordColor;

            Vector3 dir = attackDir.sqrMagnitude > 1e-4f ? attackDir.normalized : Vector3.up;
            Vector3 normal = surfaceNormal.sqrMagnitude > 1e-4f ? surfaceNormal.normalized : Vector3.up;

            // 档位越高，"散开"的锥角越大 —— 轻击是一条线，暴击是一整片扇面
            float cone = grade == HitGrade.Light ? 60f : (grade == HitGrade.Heavy ? 78f : 95f);

            // 1) 火花：**沿攻击方向**喷（"从哪边打过来"一眼可读），带重力下坠
            hub.Burst(hub.Spark, point, dir, Mathf.RoundToInt(12f * k), 2.5f, 7f * k, cone,
                color, 0.05f, 0.13f * k, 0.15f, 0.38f, 1.2f, 0.05f);

            // 2) 沿表面法线再补一小撮，让"贴着被打的那个面"也亮起来
            hub.Burst(hub.Spark, point, normal, Mathf.RoundToInt(5f * k), 1.5f, 4f * k, 45f,
                Color.Lerp(color, Color.white, 0.35f), 0.04f, 0.10f, 0.12f, 0.28f, 0.4f, 0.04f);

            // 2b) **扇形爆散**（重击起）：横向铺开的条状粒子，读作"被劈开的气流"。
            //     逐颗给方向而不是加大锥角 —— 锥角是三维乱散，扇形才是一条横扫的带。
            if (grade != HitGrade.Light)
            {
                Vector3 side = Vector3.Cross(Vector3.up, dir).normalized;
                if (side.sqrMagnitude < 1e-4f) side = Vector3.right;
                int fan = grade == HitGrade.Crit ? 12 : 8;
                for (int i = 0; i < fan; i++)
                {
                    float s = (i / (float)Mathf.Max(1, fan - 1)) * 2f - 1f;   // -1..1 横向铺开
                    Vector3 fd = (dir + side * (s * 0.85f) + Vector3.up * 0.12f).normalized;
                    hub.Burst(hub.Streak, point, fd, 1, 3.0f, 6.5f * k, 8f,
                        WithAlpha(Color.Lerp(color, Color.white, 0.3f), 0.85f),
                        0.05f, 0.12f, 0.14f, 0.26f, 0.1f, 0.02f);
                }
            }

            // 3) 四芒星高光 + 柔光球
            hub.FlareBurst(hub.Flare, point, Color.Lerp(color, Color.white, 0.55f), 1.0f * k, 0.12f + 0.03f * index);
            hub.Flash(point, WithAlpha(Color.Lerp(color, Color.white, 0.4f), 0.6f), 0.8f * k, 0.10f);

            // 4) 冲击环：**垂直于攻击方向**立起来（像撞在刀口那个面上），不是摊在地上
            hub.Ring(point, dir, 0.15f, 1.35f * k, WithAlpha(color, 0.92f),
                0.20f + 0.03f * index, 0.075f * k);

            // 4b) **暴击专属：一圈径向光晕**。环法线取**视线方向**，于是屏幕上是一个正圆
            //     （垂直于攻击方向的那个环是"斜着看"的，形状随镜头变，读不出"光晕"）。
            if (grade == HitGrade.Crit)
            {
                Camera cam = Camera.main;
                Vector3 toCam = cam != null ? cam.transform.forward : -dir;
                hub.Ring(point, toCam, 0.30f, 2.60f,
                    WithAlpha(Color.Lerp(color, Color.white, 0.45f), 0.85f), 0.34f, 0.11f);
                hub.FlareBurst(hub.Flare, point, Color.Lerp(color, Color.white, 0.6f), 2.3f, 0.24f);
            }

            // 5) 重击以上：脚下扬起**尘环 + 尘爆** —— 大伤害要"连地都震一下"。
            //    尘点用**射线打到真实地面**（斜坡/台阶上不会飘在半空），打不到才退回命中点下方。
            if (grade != HitGrade.Light)
            {
                Vector3 ground = GroundUnder(point);
                hub.Ring(ground, Vector3.up, 0.20f, 1.9f * k, WithAlpha(DustColor, 0.75f), 0.32f, 0.075f);
                hub.Burst(hub.Dust, ground + Vector3.up * 0.06f, Vector3.up,
                    Mathf.RoundToInt(14f * k), 1.2f, 3.6f, 24f,
                    WithAlpha(DustColor, 0.7f), 0.14f, 0.30f, 0.32f, 0.58f, 0.18f, 0.10f);
            }

            // 5b) 镜头推近：轻击不推（推了反而显得"打得重"），重击/暴击怼一下
            if (grade != HitGrade.Light)
                hub.AddPushIn(grade == HitGrade.Heavy ? 1.1f : 1.8f, 0.13f);

            // 6) 打击感三件套：顿帧 + 震屏 + 飘字。强度只查 VfxFeel 一张表。
            VfxFeel.ApplyImpactFeel(grade, point, damage);

            // 7) 音效（命中 + 暴击两层）
            Sfx(grade == HitGrade.Light ? "hit_light" : "hit_heavy", point,
                grade == HitGrade.Light ? 0.6f : 0.85f, JitterPitch());
            if (grade == HitGrade.Crit) SfxCritLayer(point);

            NoteImpact(ImpactKind.Melee, point, dir, normal, grade, damage);
            return grade;
        }

        /// <summary>
        /// **近战刀光 + 命中叠层的组合入口**，给没有真实碰撞点的调用方用
        /// （QA 探针、以及将来任何"知道打中了但拿不到 collider"的场合）。
        /// 有碰撞点的真实战斗路径请直接调 <see cref="MeleeImpact"/>。
        /// </summary>
        public static HitGrade MeleeImpactAtRange(Vector3 center, Vector3 forward, float hitRange,
            float damage, Color? accent = null)
        {
            // 没有碰撞点时退化成"沿攻击方向、在射程一半处"的一个点 —— 位置是估的，但**方向是真的**
            Vector3 dir = Flatten(forward);
            if (dir.sqrMagnitude < 1e-4f) dir = Vector3.forward;
            dir.Normalize();
            Vector3 point = center + dir * (hitRange * 0.8f) + Vector3.up * 0.1f;
            return MeleeImpact(point, dir, -dir, damage, accent);
        }

        /// <summary>
        /// **盾牌格挡**：在既有"春绿盾弧"上增强 —— 定向火花 + 冲击环 + 震屏 + 金属音 + `BLOCK` 飘字。
        ///
        /// 方向契约：`toAttacker` 是**攻击来向**（从受击者指向攻击者）。火花沿它往外蹦
        /// （"挡回去了"），冲击环**垂直于它**立起来（正好是盾面），所以从哪个方向打过来都能看出来。
        ///
        /// `blockedDamage` 是**被挡掉的伤害**（用来分级："挡住一记重击"要比"挡住一记轻击"更响）。
        /// 格挡不飘伤害数字（没掉血），改用 `BLOCK` 文字标签。
        /// </summary>
        public static HitGrade BlockSpark(Vector3 anchor, Vector3 toAttacker, float blockedDamage = -1f)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return HitGrade.Light;

            Vector3 dir = toAttacker.sqrMagnitude > 1e-4f ? toAttacker.normalized : Vector3.up;

            HitGrade grade = blockedDamage >= 0f
                ? VfxFeel.DeterministicGrade(blockedDamage * 2f)   // "挡住大伤害"本身就该更响，×2 让阈值对齐
                : HitGrade.Light;
            int index = VfxFeel.Index(grade);
            float k = VfxFeel.EffectScaleFor(grade);

            // 火花沿**攻击来向**蹦出去
            hub.Burst(hub.Spark, anchor, dir, Mathf.RoundToInt(16f * k), 2.5f, 6f * k, 40f, BlockColor,
                0.05f, 0.13f, 0.18f, 0.42f, 0.6f, 0.04f);
            hub.FlareBurst(hub.Flare, anchor, Color.Lerp(BlockColor, Color.white, 0.4f), 1.0f * k, 0.13f);
            hub.Flash(anchor, WithAlpha(BlockColor, 0.55f), 1.1f * k, 0.10f);

            // 冲击环垂直于攻击来向 = 正好贴着盾面
            hub.Ring(anchor, dir, 0.12f, 0.85f * k, WithAlpha(BlockColor, 0.85f), 0.18f + 0.03f * index, 0.06f);

            VfxFeel.ApplyImpactFeel(grade, anchor);   // 不传伤害 → 顿帧 + 震屏，但不飘数字
            VfxTextPool.Label(anchor + Vector3.up * 0.5f, "BLOCK", BlockColor, 0.34f);

            Sfx("hit_block", anchor, 0.8f, JitterPitch());
            if (grade != HitGrade.Light) Sfx("hit_block", anchor, 0.45f, JitterPitch() * 1.25f);

            NoteImpact(ImpactKind.Block, anchor, dir, -dir, grade, blockedDamage);
            return grade;
        }

        /// <summary>盾击（ShieldBash）：正面光弧 + 冲击环 + 震屏。</summary>
        public static void ShieldBash(Vector3 center, Vector3 forward, float range)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return;

            Vector3 f = Flatten(forward);
            if (f.sqrMagnitude < 1e-4f) f = Vector3.forward;
            f.Normalize();
            Vector3 point = center + f * Mathf.Max(0.6f, range * 0.5f);

            Color steel = new Color(0.82f, 0.88f, 1f, 0.92f);
            hub.Arc(point, f, 1.7f, 120f, steel, 0.22f, 0.10f);
            hub.Ring(point, f, 0.2f, 2.1f, WithAlpha(steel, 0.85f), 0.25f, 0.10f);
            hub.Burst(hub.Spark, point, f, 20, 2.5f, 6.5f, 55f, SteelColor,
                0.05f, 0.13f, 0.16f, 0.40f, 0.8f, 0.08f);
            hub.FlareBurst(hub.Flare, point, Color.white, 1.6f, 0.14f);

            VfxHub.HitStop(0.05f);
            hub.AddShake(0.28f, 0.15f);
            Sfx("hit_block", point, 0.85f, JitterPitch());
        }

        /// <summary>空手/护手出拳：拳风（尘土 + 白色风线），不产生命中伤害。</summary>
        public static void Punch(Vector3 center, Vector3 forward)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return;

            Vector3 f = Flatten(forward);
            if (f.sqrMagnitude < 1e-4f) f = Vector3.forward;
            f.Normalize();
            Vector3 point = center + f * 0.85f + Vector3.up * 0.1f;

            hub.Burst(hub.Streak, point, f, 5, 3f, 6f, 18f, new Color(0.95f, 0.97f, 1f, 0.7f),
                0.04f, 0.08f, 0.08f, 0.16f, 0f, 0.03f);
            hub.Burst(hub.Dust, point + Vector3.up * 0.15f, f, 5, 0.8f, 2.0f, 55f,
                WithAlpha(DustColor, 0.6f), 0.10f, 0.20f, 0.18f, 0.35f, 0.4f);
            hub.FlareBurst(hub.Flare, point, new Color(1f, 0.95f, 0.85f, 0.6f), 0.5f, 0.07f);
            hub.AddShake(0.07f, 0.08f);
            Sfx("swing", point, 0.45f, JitterPitch());
        }

        // ================= 法术 =================

        /// <summary>法杖施法起手：脚下的紫青符文环 + 正面小环 + 光斑（法杖辨识度）。</summary>
        public static void CastFormation(Vector3 origin, Vector3 direction, Color color)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return;

            Vector3 dir = direction.sqrMagnitude > 1e-4f ? direction.normalized : Vector3.forward;

            // 脚下符文环（水平，扩散）
            hub.Ring(origin + Vector3.down * 0.85f, Vector3.up, 0.35f, 1.5f,
                WithAlpha(RuneColor, 0.9f), 0.50f, 0.075f);
            // 正面小环（法术方向）
            hub.Ring(origin, dir, 0.15f, 0.85f,
                WithAlpha(Color.Lerp(color, Color.white, 0.35f), 0.85f), 0.32f, 0.055f);

            // 上升的光点
            hub.Burst(hub.Glow, origin, dir, 10, 0.8f, 2.6f, 55f, Color.Lerp(color, RuneColor, 0.4f),
                0.08f, 0.20f, 0.35f, 0.70f, 0.9f, 0.12f);
            hub.Burst(hub.Flare, origin + Vector3.up * 0.2f, dir, 3, 0.4f, 1.2f, 40f,
                Color.Lerp(color, Color.white, 0.4f), 0.5f, 0.9f, 0.10f, 0.20f, 0.4f);
            hub.FlareBurst(hub.Flare, origin, Color.Lerp(color, Color.white, 0.5f), 1.3f, 0.14f);

            hub.AddShake(0.05f, 0.08f);
        }

        /// <summary>
        /// 法术弹命中/落地。**位置 = 真实碰撞点（射线 `hit.point`）、方向沿弹道**，强度按伤害分级。
        /// </summary>
        /// <param name="position">真实碰撞点（`hit.point`）</param>
        /// <param name="normal">受击表面法线</param>
        /// <param name="travelDir">弹道方向（法术飞过来的方向）</param>
        /// <param name="damage">伤害 → 分级；**`&lt; 0` = 没打中目标**（打墙/落地），只放特效不飘字</param>
        /// <param name="hitEnemy">打的是不是敌人（决定配色偏紫青还是偏红）</param>
        public static HitGrade SpellImpact(Vector3 position, Vector3 normal, Vector3 travelDir,
            float damage, bool hitEnemy)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return HitGrade.Light;

            Vector3 n = normal.sqrMagnitude > 1e-4f ? normal.normalized : Vector3.up;
            Vector3 dir = travelDir.sqrMagnitude > 1e-4f ? travelDir.normalized : -n;

            bool graded = damage >= 0f;
            bool crit;
            HitGrade grade = graded ? VfxFeel.Grade(damage, out crit) : HitGrade.Light;
            int index = VfxFeel.Index(grade);
            float k = VfxFeel.EffectScaleFor(grade);

            Color accent = hitEnemy ? new Color(1f, 0.45f, 0.35f) : MagicColor;

            // 火花**沿弹道方向继续往前冲**（"打进去了"）
            hub.Burst(hub.Spark, position, dir, Mathf.RoundToInt((hitEnemy ? 18f : 14f) * k),
                2.5f, 7f * k, 60f, accent, 0.06f, 0.14f * k, 0.18f, 0.45f, 1.2f, 0.05f);
            // 再沿表面法线补一撮（"贴着被打的那个面炸开"）
            hub.Burst(hub.Spark, position, n, Mathf.RoundToInt(6f * k), 1.5f, 4f, 55f,
                Color.Lerp(RuneColor, MagicColor, 0.5f), 0.05f, 0.12f, 0.14f, 0.32f, 0.5f);
            hub.Burst(hub.Glow, position, dir, Mathf.RoundToInt(8f * k), 0.5f, 2.2f, 80f,
                Color.Lerp(RuneColor, MagicColor, 0.5f), 0.12f, 0.30f * k, 0.28f, 0.55f, 0.8f);
            hub.FlareBurst(hub.Flare, position, Color.Lerp(Color.white, accent, 0.35f), 1.7f * k, 0.13f);

            // 冲击环：**垂直于弹道方向**（弹头撞出来的那一圈），不是摊在地上
            hub.Ring(position, dir, 0.2f, (hitEnemy ? 1.9f : 1.5f) * k,
                WithAlpha(RuneColor, 0.9f), 0.24f + 0.03f * index, 0.09f);

            if (hitEnemy)
            {
                hub.Ring(position + Vector3.down * 0.6f, Vector3.up, 0.3f, 1.4f * k,
                    WithAlpha(MagicColor, 0.7f), 0.30f, 0.06f);
            }

            // 打击感三件套：真打中才顿帧/震屏/飘字；打墙只轻震一下
            if (graded)
            {
                VfxFeel.ApplyImpactFeel(grade, position, damage);
            }
            else
            {
                if (VfxFeel.HitStopEnabled && hitEnemy) VfxHub.HitStop(VfxFeel.HitStopFor(HitGrade.Light));
                hub.AddShake(hitEnemy ? 0.14f : 0.08f, 0.12f);
            }

            Sfx("spell_impact", position, hitEnemy ? 0.8f : 0.6f, JitterPitch());
            if (grade == HitGrade.Crit) SfxCritLayer(position);

            NoteImpact(ImpactKind.Spell, position, dir, n, grade, damage);
            return grade;
        }

        /// <summary>兼容入口（不知道伤害的调用方：QA 探针 / 纯视觉回放）。</summary>
        public static HitGrade SpellImpact(Vector3 position, Vector3 normal, bool hitEnemy)
        {
            return SpellImpact(position, normal, -normal, -1f, hitEnemy);
        }

        // ================= 弓 =================

        /// <summary>射箭瞬间：弦风 + 一点光。</summary>
        public static void ArrowRelease(Vector3 position, Vector3 direction)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return;

            Vector3 dir = direction.sqrMagnitude > 1e-4f ? direction.normalized : Vector3.forward;
            hub.Burst(hub.Streak, position, dir, 5, 4f, 9f, 12f, new Color(0.92f, 0.96f, 1f, 0.55f),
                0.03f, 0.07f, 0.08f, 0.16f, 0f, 0.02f);
            hub.FlareBurst(hub.Flare, position, new Color(1f, 0.95f, 0.82f, 0.6f), 0.5f, 0.08f);
            Sfx("bow_release", position, 0.45f, JitterPitch());
        }

        /// <summary>
        /// 箭矢命中：落点尘 + 木屑/血花 + 冲击环。**位置 = 真实碰撞点，方向沿弹道**，按伤害分级。
        /// </summary>
        /// <param name="position">真实碰撞点（`hit.point`）</param>
        /// <param name="normal">受击表面法线（尘沿它腾起）</param>
        /// <param name="travelDir">箭的飞行方向（木屑沿它往前钻）</param>
        /// <param name="damage">伤害 → 分级；**`&lt; 0` = 打墙/落地**（只放特效，不顿帧不飘字）</param>
        /// <param name="hitEnemy">打的是不是敌人</param>
        public static HitGrade ArrowImpact(Vector3 position, Vector3 normal, Vector3 travelDir,
            float damage, bool hitEnemy)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return HitGrade.Light;

            Vector3 n = normal.sqrMagnitude > 1e-4f ? normal.normalized : Vector3.up;
            Vector3 dir = travelDir.sqrMagnitude > 1e-4f ? travelDir.normalized : -n;

            bool graded = damage >= 0f;
            bool crit;
            HitGrade grade = graded ? VfxFeel.Grade(damage, out crit) : HitGrade.Light;
            int index = VfxFeel.Index(grade);
            float k = VfxFeel.EffectScaleFor(grade);

            // 尘：沿**表面法线**腾起（被打的那个面上扬起来）
            hub.Burst(hub.Dust, position, n, Mathf.RoundToInt(9f * k), 0.8f, 2.4f, 55f,
                WithAlpha(DustColor, 0.8f), 0.12f, 0.26f, 0.25f, 0.50f, 0.5f);

            // 木屑 / 血花：沿**弹道方向**继续往前钻（箭是"钻进去"的，不是"拍上去"的）
            hub.Burst(hub.Spark, position, dir, Mathf.RoundToInt((hitEnemy ? 11f : 7f) * k),
                2f, 5.5f * k, 50f, hitEnemy ? EnemyColor : new Color(0.92f, 0.86f, 0.70f),
                0.04f, 0.10f, 0.15f, 0.35f, 0.8f);

            // 冲击环：垂直于弹道
            hub.Ring(position, dir, 0.10f, (hitEnemy ? 0.95f : 0.7f) * k,
                WithAlpha(hitEnemy ? EnemyColor : Color.white, 0.75f), 0.18f + 0.02f * index, 0.055f);

            if (graded)
            {
                VfxFeel.ApplyImpactFeel(grade, position, damage);
            }
            else
            {
                hub.AddShake(hitEnemy ? 0.10f : 0.045f, 0.09f);
            }

            Sfx("arrow_impact", position, 0.7f, JitterPitch());
            if (grade == HitGrade.Crit) SfxCritLayer(position);

            NoteImpact(ImpactKind.Arrow, position, dir, n, grade, damage);
            return grade;
        }

        /// <summary>兼容入口（不知道伤害的调用方）。</summary>
        public static HitGrade ArrowImpact(Vector3 position, Vector3 normal, bool hitEnemy)
        {
            return ArrowImpact(position, normal, -normal, -1f, hitEnemy);
        }

        // ================= 抓钩 =================

        /// <summary>抓钩发射：钩头风线。</summary>
        public static void GrappleFire(Vector3 position, Vector3 direction)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return;
            Vector3 dir = direction.sqrMagnitude > 1e-4f ? direction.normalized : Vector3.forward;
            hub.Burst(hub.Streak, position, dir, 4, 3f, 7f, 15f, new Color(0.9f, 0.9f, 0.85f, 0.5f),
                0.03f, 0.06f, 0.08f, 0.16f, 0f, 0.02f);
            Sfx("grapple_fire", position, 0.5f, JitterPitch());
        }

        /// <summary>钩爪咬住：金属火花 + 尘环（锚点命中反馈）。</summary>
        public static void GrappleHit(Vector3 position, Vector3 normal)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return;
            if (normal.sqrMagnitude < 1e-4f) normal = Vector3.up;
            normal.Normalize();
            hub.Burst(hub.Spark, position, normal, 10, 2f, 5f, 65f,
                new Color(1f, 0.85f, 0.55f), 0.04f, 0.10f, 0.15f, 0.32f, 0.6f);
            hub.Burst(hub.Dust, position, normal, 6, 0.6f, 1.8f, 60f, WithAlpha(DustColor, 0.6f),
                0.10f, 0.20f, 0.22f, 0.42f, 0.3f);
            hub.Ring(position, normal, 0.08f, 0.7f, new Color(1f, 0.85f, 0.55f, 0.7f), 0.18f, 0.05f);
            Sfx("grapple_hit", position, 0.6f, JitterPitch());
        }

        /// <summary>拉拽过程：玩家脚下扬尘 + 轻微震屏。</summary>
        public static void GrapplePull(Vector3 playerPosition)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return;
            Vector3 feet = playerPosition + Vector3.up * 0.08f;
            hub.Burst(hub.Dust, feet, Vector3.up, 4, 0.5f, 1.8f, 70f, WithAlpha(DustColor, 0.55f),
                0.10f, 0.22f, 0.22f, 0.40f, 0.3f);
            hub.AddShake(0.035f, 0.10f);
            Sfx("grapple_pull", playerPosition, 0.35f, JitterPitch());
        }

        /// <summary>松钩/落地：小尘团。</summary>
        public static void GrappleRelease(Vector3 position)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return;
            hub.Burst(hub.Dust, position + Vector3.up * 0.08f, Vector3.up, 5, 0.5f, 1.6f, 75f,
                WithAlpha(DustColor, 0.5f), 0.09f, 0.20f, 0.20f, 0.38f, 0.3f);
        }

        /// <summary>给抓钩对象挂可视化装饰组件（只在没有时挂一次）。</summary>
        public static void DecorateGrapple(GameObject grappleRoot)
        {
            if (grappleRoot == null) return;
            if (grappleRoot.GetComponent<VfxGrappleDecorator>() != null) return;
            grappleRoot.AddComponent<VfxGrappleDecorator>();
        }

        // ================= 受击 / 死亡 =================

        /// <summary>
        /// 敌人受击的**血肉层**（由 `VfxDirector` 订阅 `Enemy.AnyDamaged` 调用）。
        ///
        /// ⚠️ 这一层是**补充**，不是主反馈：顿帧 / 震屏 / 飘字 / 分级命中音都由具体命中类型
        ///    （`MeleeImpact` / `ArrowImpact` / `SpellImpact`）负责。
        ///    所以这里**不顿帧、不飘字** —— 否则一次命中会冒出两个伤害数字、顿两次帧。
        ///    它只负责"血花 + 红光"这层**无论什么伤害来源都该有**的反馈，大小跟着 `grade`。
        /// </summary>
        public static void EnemyHit(Vector3 point, Vector3 normal, HitGrade grade = HitGrade.Light)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return;
            if (normal.sqrMagnitude < 1e-4f) normal = Vector3.up;
            normal.Normalize();

            int index = VfxFeel.Index(grade);
            float k = VfxFeel.EffectScaleFor(grade);

            hub.Burst(hub.Spark, point, normal, Mathf.RoundToInt(7f * k), 2f, 5f * k, 70f, EnemyColor,
                0.04f, 0.10f * k, 0.14f, 0.30f, 0.9f, 0.04f);
            hub.FlareBurst(hub.Flare, point, new Color(1f, 0.5f, 0.42f, 0.75f), 0.7f * k, 0.10f);
            hub.Flash(point, WithAlpha(BloodColor, 0.35f + 0.12f * index), 0.55f * k, 0.08f);

            // 音效：只有**轻击**补一声很轻的血肉闷响。
            // 重击/暴击那边已经被分级的命中音 + 暴击叠层占满了，再叠只会糊
            //（资源库里也只有 hit_light / hit_heavy 两个现成的）。
            if (grade == HitGrade.Light) Sfx("hit_light", point, 0.3f, JitterPitch());
        }

        /// <summary>敌人死亡：尘土 + 火花 + 烟 + 地面环 + 顿帧（击杀确认感）。</summary>
        public static void EnemyDeath(Vector3 position)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return;

            Vector3 chest = position + Vector3.up * 0.9f;

            hub.Burst(hub.Dust, position + Vector3.up * 0.2f, Vector3.up, 24, 1.2f, 3.2f, 90f,
                WithAlpha(DustColor, 0.85f), 0.25f, 0.50f, 0.50f, 0.90f, 0.5f, 0.15f);
            hub.Burst(hub.Spark, chest, Vector3.up, 14, 2f, 4.5f, 80f,
                new Color(0.9f, 0.6f, 0.45f), 0.05f, 0.12f, 0.25f, 0.50f, 2.2f);
            hub.Burst(hub.Smoke, chest, Vector3.up, 5, 0.4f, 1.2f, 60f,
                new Color(0.52f, 0.50f, 0.47f, 0.55f), 0.50f, 0.90f, 0.60f, 1.10f, 0.7f);
            hub.FlareBurst(hub.Flare, chest, new Color(1f, 0.82f, 0.55f, 0.9f), 1.8f, 0.18f);
            hub.Ring(position + Vector3.up * 0.12f, Vector3.up, 0.30f, 2.30f,
                new Color(0.95f, 0.76f, 0.48f, 0.8f), 0.35f, 0.10f);

            VfxHub.HitStop(0.055f);
            hub.AddShake(0.22f, 0.14f);
            Sfx("death", position, 0.8f, JitterPitch());
        }

        /// <summary>
        /// 玩家受击：红闪光 + 火花 + 顿帧/震屏 + **红色伤害数字**（伤害值大的还能看出来"这一下很疼"）。
        /// 不额外播声音 —— `PlayerHealth.TakeDamage` 已经调过 `GameAudio.PlayHurt()`。
        /// </summary>
        /// <param name="damage">这一跳扣了多少血 → 分级；`&lt; 0` = 不知道（只做轻击观感）</param>
        public static HitGrade PlayerHurt(Vector3 position, float damage = -1f)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return HitGrade.Light;

            bool graded = damage >= 0f;
            bool crit;
            HitGrade grade = graded ? VfxFeel.Grade(damage, out crit) : HitGrade.Light;
            float k = VfxFeel.EffectScaleFor(grade);

            Vector3 chest = position + Vector3.up * 1.0f;
            hub.Burst(hub.Spark, chest, Vector3.up, Mathf.RoundToInt(9f * k), 1.5f, 3.2f * k, 70f,
                new Color(1f, 0.32f, 0.24f), 0.04f, 0.09f, 0.15f, 0.30f, 1.2f);
            hub.Flash(chest, new Color(1f, 0.22f, 0.18f, 0.45f), 1.3f * k, 0.12f);

            if (grade == HitGrade.Light)
            {
                // ⚠️ **轻击刻意不顿帧**：流血是每 0.5 秒结算一次的，如果每跳都顿帧，
                //    画面就变成"每半秒冻一下"，玩家会以为是掉帧而不是反馈。
                //    轻击只给震屏 + 数字，重击/暴击才上全套。
                hub.AddShake(VfxFeel.ShakeAmpFor(grade), VfxFeel.ShakeTimeFor(grade));
                if (graded) VfxTextPool.Damage(chest, damage, grade);
            }
            else
            {
                VfxFeel.ApplyImpactFeel(grade, chest, graded ? damage : -1f);
            }

            return grade;
        }

        /// <summary>玩家治疗：上升绿光 + 地面治疗环 + 绿色 `+N` 数字。</summary>
        public static void PlayerHeal(Vector3 position, float amount = -1f)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return;

            hub.Burst(hub.Glow, position + Vector3.up * 0.4f, Vector3.up, 12, 0.6f, 2.2f, 55f,
                HealColor, 0.08f, 0.20f, 0.50f, 1.00f, 1.0f, 0.25f);
            hub.Ring(position + Vector3.up * 0.05f, Vector3.up, 0.30f, 1.60f,
                WithAlpha(HealColor, 0.9f), 0.50f, 0.075f);
            hub.FlareBurst(hub.Flare, position + Vector3.up * 1.2f, HealColor, 1.0f, 0.30f);
            if (amount >= 0f) VfxTextPool.Heal(position + Vector3.up * 1.5f, amount);
            Sfx("heal", position, 0.7f, JitterPitch());
        }

        // ================= 拾取 / 场景事件 =================

        /// <summary>拾取金币：金色光点 + 小环。</summary>
        public static void PickupGold(Vector3 position)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return;

            Vector3 pos = position + Vector3.up * 0.7f;
            hub.Burst(hub.Flare, pos, Vector3.up, 3, 0.8f, 2.4f, 45f, GoldColor,
                0.30f, 0.60f, 0.20f, 0.40f, 1.2f, 0.15f);
            hub.Burst(hub.Glow, pos, Vector3.up, 6, 0.5f, 1.8f, 60f, GoldColor,
                0.06f, 0.14f, 0.25f, 0.50f, 1.0f, 0.10f);
            hub.Ring(pos, Vector3.up, 0.08f, 0.55f, WithAlpha(GoldColor, 0.9f), 0.22f, 0.045f);
            Sfx("coin", position, 0.55f, JitterPitch());
        }

        /// <summary>拾取物品（草药/水晶/装备）：白+彩光。</summary>
        public static void PickupItem(Vector3 position)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return;

            Vector3 pos = position + Vector3.up * 0.7f;
            hub.Burst(hub.Glow, pos, Vector3.up, 8, 0.5f, 2.0f, 60f, new Color(0.9f, 1f, 0.95f),
                0.06f, 0.14f, 0.25f, 0.50f, 1.0f, 0.10f);
            hub.FlareBurst(hub.Flare, pos, new Color(1f, 1f, 0.9f, 0.8f), 0.8f, 0.16f);
            Sfx("pickup", position, 0.55f, JitterPitch());
        }

        /// <summary>传送门（场景切换处）：紫色漩涡 + 双环。</summary>
        public static void PortalAt(Vector3 position)
        {
            VfxHub hub = VfxHub.Ensure();
            if (hub == null) return;

            Vector3 center = position + Vector3.up * 1.0f;
            hub.Burst(hub.Glow, center, Vector3.up, 22, 1.0f, 3.6f, 85f,
                Color.Lerp(RuneColor, MagicColor, 0.4f), 0.10f, 0.30f, 0.60f, 1.20f, 1.6f, 0.45f);
            hub.FlareBurst(hub.Flare, center, Color.Lerp(RuneColor, Color.white, 0.4f), 2.0f, 0.24f);
            hub.Ring(position + Vector3.up * 0.06f, Vector3.up, 0.50f, 2.60f,
                WithAlpha(MagicColor, 0.9f), 0.60f, 0.10f);
            hub.Ring(center, Vector3.forward, 0.30f, 1.80f,
                WithAlpha(RuneColor, 0.8f), 0.50f, 0.08f);
            hub.AddShake(0.10f, 0.20f);
            Sfx("portal", position, 0.8f, JitterPitch());
        }

        // ================= 工具 =================

        /// <summary>
        /// **暴击音的第二层**。
        ///
        /// ⚠️ `Assets/Resources/Audio/` 里**没有** `hit_crit` 这个文件（已核 24 个 wav 的清单），
        ///    所以暴击不是"换一个音效文件"，而是**两层叠出来**：
        ///    低八度的重击当"闷响"，高八度的金属音当"叮" —— 单层怎么调都出不来"会心一击"。
        ///    真实采样那一路由 `GameAudio.PlayCrit()` 负责（它播的是用户提供的命中音）。
        /// </summary>
        static void SfxCritLayer(Vector3 point)
        {
            SfxLibrary.Play("hit_heavy", point, 0.55f, 0.82f);   // 低八度垫底
            SfxLibrary.Play("hit_block", point, 0.60f, 1.45f);   // 高八度金属"叮"
        }

        static void Sfx(string name, Vector3 position, float volume, float pitch = 1f)
        {
            SfxLibrary.Play(name, position, volume, pitch);
        }

        static float JitterPitch()
        {
            return Random.Range(0.94f, 1.07f);
        }

        static Color WithAlpha(Color c, float alpha)
        {
            c.a = alpha;
            return c;
        }

        static Vector3 Flatten(Vector3 v)
        {
            v.y = 0f;
            return v;
        }

        /// <summary>
        /// 把命中点垂到**真实地面**上（重击尘环/尘爆用）。
        /// 打射线而不是硬减 `0.75m`：斜坡、台阶、箱子上命中时，硬减出来的点会飘在半空或陷进地里。
        /// 射线打不到（空中连击、地形没碰撞体）才退回命中点下方 0.75m —— 批量命中时也只是少一圈尘。
        /// </summary>
        static Vector3 GroundUnder(Vector3 point)
        {
            RaycastHit hit;
            if (Physics.Raycast(point + Vector3.up * 0.25f, Vector3.down, out hit, 4f,
                                ~0, QueryTriggerInteraction.Ignore))
                return hit.point;
            return point + Vector3.down * 0.75f;
        }
    }
}
