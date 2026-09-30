using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 敌人技能用的几种特效，全部用图元/线段拼，不依赖美术资源：
    ///
    ///   Exclamation  头顶黄色感叹号（盾击的预警）
    ///   Charge       蓄力：脚下收缩的圆环 + 逐渐变亮的球
    ///   Crescent     月牙形范围斩击（冲刺斩）
    ///   Slash        向前劈砍的直线斩击（蓄力一击）
    ///   SwordSlash   玩家剑的挥砍刀光（T-010 从 PlayerCombat 迁入的视觉参数）
    ///
    /// 都用 unscaledDeltaTime 之外的普通 deltaTime，会随顿帧/暂停一起停，符合预期。
    /// </summary>
    public static class SkillVfx
    {
        public static readonly Color WarningColor = new Color(1f, 0.82f, 0.15f, 1f);   // 黄：预警
        public static readonly Color ChargeColor = new Color(1f, 0.55f, 0.12f, 1f);    // 橙：蓄力
        public static readonly Color HeavyColor = new Color(0.85f, 0.15f, 0.75f, 1f);  // 品红：重击/流血

        /// <summary>
        /// **春绿：格挡**（T-081）。
        ///
        /// 为什么是 145°：既有色里离它最近的是玩家刀光·冰青 **187.5°（差 42.5°）**、奥术青 **200.0°（差 55.0°）**、
        /// 旧的格挡蓝白 **220.0°（差 75.0°）** —— 全部 ≥ 42.5° > T-011 定的 **25°** 门槛；饱和度 **0.632 ≥ 0.40**。
        /// 🔴 **旧格挡色 `(0.75,0.8,0.9)` = 220.0°，与"法术打墙/地面"的冷青 200.0° 只差 20.0°** ——
        /// 那正是用户说"好像打到了敌人但是没打中"的现场（T-081 §0.2）。**这个常量就是为了把它从冷青槽里搬走。**
        ///
        /// ⚠️ 规格 §3：经 `PlaceholderArt.GlowGain = 1.7` 后是 `(0.595, 1.615, 1.02)`（真 >1）→ **会过 Bloom**。
        /// 这是**既有的全局行为**（与旧蓝白爆花同样会发光），**不是本片新增**；区分**不依赖亮度**。
        /// </summary>
        public static readonly Color BlockColor = new Color(0.35f, 0.95f, 0.60f, 1f);  // 春绿：格挡（T-081）

        /// <summary>
        /// T-081：**格挡表现** —— 一道朝攻击来向的春绿盾弧 + 一束定向火花。
        ///
        /// 与旧表现（`ArcaneBurst` 蓝白球壳 `scale 0.7`）的三处**结构性**差异：
        ///   ① **没有球壳**（F3 的失败线就是"球壳仍在"）→ 本方法**完全不碰 `ArcaneBurst`**；
        ///   ② **有方向** —— 弧点在"垂直于攻击来向"的平面内张开，火花沿来向飞出（F4 量质心位移方向）；
        ///   ③ **急停不缓散** —— 尺寸一次到位，之后只把 alpha 拉到 0（旧球壳是"边胀边散"，0.35 s）。
        ///
        /// ⚠️ **弧用 `LineAlignment.View`（billboard）**：若用世界朝向，攻击者位于敌人正前/正后时
        /// 弧面≈矢状面 → 屏幕上退化成一条竖线（T-011 §0 已证）。
        /// </summary>
        /// <param name="anchor">回退锚点（规格：敌人胸口高度 + 朝攻击者偏移 0.35 m）</param>
        /// <param name="toAttacker">攻击来向（由 `hitPoint` 或攻击者位置算出，**y 已置 0**）</param>
        /// <param name="shield">优先锚点：敌人的盾网格（取不到传 null）</param>
        public static void BlockArc(Vector3 anchor, Vector3 toAttacker, Transform shield)
        {
            var go = new GameObject("Vfx_BlockArc");
            var v = go.AddComponent<BlockArcVfx>();
            v.Init(anchor, toAttacker, shield);
        }

        // ==================== 玩家剑的挥砍刀光（T-010） ====================
        //
        // ⚠️ 下面这一组**只决定刀光长什么样**，不参与任何判定。
        //    判定用的 meleeRange / meleeHalfAngle 由 PlayerCombat 原样传进 SwordSlash()，
        //    这里只把"打哪儿"换算成"画成什么形状"。改这些数字**不会**改变打不打得到人。
        //
        // 为什么参数搬到这里：PlayerCombat 是判定代码，视觉参数混在里面，
        // 以后每次调刀光都要动判定文件，容易误伤。现在 PlayerCombat 只留一行转发调用。

        /// <summary>弧半径 = 判定半径 × 该值。</summary>
        public static float SlashRadiusScale = 0.85f;

        /// <summary>
        /// 弧心前移 = 判定半径 × 该值。
        /// 太小的话弧带内缘会绕回来压到角色身上（原来只有 0.35，弧贴着人）。
        /// </summary>
        public static float SlashCenterForwardScale = 0.50f;

        /// <summary>
        /// 剑四段各自的**表现层几何与颜色**（T-011）。**这是四段差异的唯一真相源** ——
        /// 原先四段几何完全相同、只靠 `finisher` 换一个近白色，所以"四段看起来一样"。
        ///
        /// 依据 `docs/artifacts/T-011/slash-vfx-spec.md` §1.1（四段靠**形状/朝向/尺寸/颜色/时机**区分）。
        /// ⚠️ **区分手段里没有"更亮/发光"** —— 月牙走 `Sprites/Default` 顶点色，**结构上被夹取**
        ///    （T-068 实测：增益 1.7 与 8.0 像素逐位相同），所以只能靠几何 + 颜色。
        ///
        /// ⚠️ **旧旋钮 `SlashPitchDegrees` / `SlashLift` 与两个旧色已删除**（T-011 前它们四段共用）。
        ///    它们全工程只有本文件用（已核）→ 删除不留双真相源。
        /// </summary>
        private struct SlashSeg
        {
            public float pitch;        // 弧面仰角（度）：0=水平横弧，90=正面竖拱
            public float roll;         // 绕前向轴滚（度）：只有第 3 段用（做出屏幕上真正的"斜"）
            public float arc;          // 视觉弧角（度）
            public float radiusScale;  // 视觉弧半径的额外倍率
            public float lift;         // 弧带中点抬高的**起点**
            public float liftDrift;    // 生命期内 lift 的**增量**（0 = 恒定）
            public float lateralDrift; // 生命期内沿横轴 `right` 的横向位移（0 = 不位移）
            public bool line;          // true = 走既有的 line 模式（第 4 段突刺，不是弧）
            public Color color;

            public SlashSeg(float pitch, float roll, float arc, float radiusScale,
                            float lift, float liftDrift, float lateralDrift, bool line, Color color)
            {
                this.pitch = pitch; this.roll = roll; this.arc = arc; this.radiusScale = radiusScale;
                this.lift = lift; this.liftDrift = liftDrift; this.lateralDrift = lateralDrift;
                this.line = line; this.color = color;
            }
        }

        /// <summary>
        /// 突刺（第 4 段）的线长倍率。规格 §1.1："长度 ×1.45（四段最长）" ——
        /// 弧段半径最大只有 `hitRange × SlashRadiusScale(0.85) × 1.00`，所以 1.45 让它明显最长。
        /// </summary>
        private const float StabLengthScale = 1.45f;

        /// <summary>
        /// 四段几何 + 颜色。**顺序 = 连招段位 1..4**（横劈 / 下劈 / 斜劈 / 突刺）。
        /// 颜色是 LDR（≤1.0）且**饱和度 0.40–0.65**：旧两色看着都像白光，根因是**饱和度只有 0.14/0.28**
        /// （**不是色相** —— 旧两色色相本来就相差 154.3°）。
        /// 规格 F4 判据：四色**色相两两 ≥25°** 且**饱和度 ≥0.40**（最小一对 1↔2 = 27.6°）。
        /// </summary>
        private static readonly SlashSeg[] SwordSegments =
        {
            new SlashSeg( 8f,   0f, 130f, 1.00f, 0.25f,  0.00f, 0f,    false, new Color(0.60f, 0.95f, 1.00f)), // 1 横劈 冰青
            new SlashSeg(82f,   0f,  70f, 0.80f, 0.55f, -0.70f, 0f,    false, new Color(0.35f, 0.62f, 1.00f)), // 2 下劈 蓝（下坠）
            new SlashSeg(45f, -40f,  95f, 0.92f, 0.45f, -0.40f, 0.35f, false, new Color(0.78f, 0.55f, 1.00f)), // 3 斜劈 紫（斜移）
            new SlashSeg( 0f,   0f,   0f, 0.00f, 0.25f,  0.00f, 0f,    true,  new Color(1.00f, 0.82f, 0.45f)), // 4 突刺 金（直线）
        };

        // 三层：内层细亮边 / 中层是"带"的主体 / 外层再收一道边。
        // 半径要拉开、线宽要窄 —— 线宽一旦接近或超过半径间距，三层就叠成一团实心扇面。
        // （原来 0.9/1.9/0.6 的线宽叠在半径 1.7m 的弧上：径向厚度 1.9m 比半径还大，
        //   内外层被完全吞掉 → 屏幕上就是一团白斑，见 vfx_T010_before.png）
        // 现在的三层线宽接近、但**半径拉开 0.22m/0.24m**，于是并成一条有厚度的弧带：
        // 三条亮线在中段并排、两端一起收尖，既有面又有丝。
        // 这组值是照着截图逐轮调出来的（先 0.34/0.42/0.26 太细，加粗到本组才够"有厚度"）。
        private static readonly float[] SwordRadiusMul = { 0.88f, 1.00f, 1.13f };
        private static readonly float[] SwordLayerWidth = { 0.40f, 0.54f, 0.30f };
        private static readonly float[] SwordLayerAlpha = { 0.50f, 1.00f, 0.38f };

        /// <summary>刀尖拖尾的发射时长（T-012，秒）。规格 §2.3："挥砍开始 → 开始后 0.30s"，
        /// 覆盖 0.20s 事件前后。**这是表现层常量，不是玩法数值。**</summary>
        public const float SlashTrailEmitSeconds = 0.30f;

        /// <summary>
        /// 取某一段刀光的颜色（段位 1..4，超范围夹紧）。**给拖尾用** ——
        /// 规格 §2.3 要求拖尾"与当段刀光同色"，所以颜色只能有一个来源（本表）。
        /// </summary>
        public static Color SwordSegmentColor(int segment)
        {
            int seg = Mathf.Clamp(segment, 1, SwordSegments.Length);
            return SwordSegments[seg - 1].color;
        }

        /// <summary>
        /// 玩家的剑的挥砍刀光。**这是玩家挥砍唯一的视觉入口**，
        /// 由 `PlayerCombat.OnSlashImpact()` 在动画命中帧调用。
        /// </summary>
        /// <param name="center">判定中心（已是胸口高度）</param>
        /// <param name="forward">出手朝向</param>
        /// <param name="hitRange">判定近战半径。只用来换算视觉尺寸，判定本身仍在 PlayerCombat</param>
        /// <param name="hitHalfAngleDegrees">判定半张角。只用来换算视觉弧角</param>
        /// <param name="segment">连招段位 **1..4**（T-011：四段几何/颜色各不相同；超范围会被夹到 1..4）</param>
        public static void SwordSlash(Vector3 center, Vector3 forward, float hitRange,
                                      float hitHalfAngleDegrees, int segment)
        {
            Vector3 f = Flatten(forward);

            // 弧心前移到身前，弧带才不会绕回来压住角色
            float d = hitRange * SlashCenterForwardScale;
            Vector3 origin = center + new Vector3(f.x * d, 0f, f.z * d);

            int seg = Mathf.Clamp(segment, 1, SwordSegments.Length);
            SlashSeg S = SwordSegments[seg - 1];

            var go = new GameObject("Vfx_SwordSlash");
            go.transform.position = origin;

            var v = go.AddComponent<CrescentSlash>();

            // ---- 第 4 段：突刺 ----
            // 复用**既有的 line 模式**（规格 §1.1："不是弧，是直线"），不新增模式。
            if (S.line)
            {
                v.InitLine(origin, f, hitRange * StabLengthScale, S.color);
                return;
            }

            // ---- 第 1..3 段：弧 ----
            var style = new CrescentStyle();
            style.radiusMul = SwordRadiusMul;
            style.widths = SwordLayerWidth;
            style.alphas = SwordLayerAlpha;
            style.pitchDegrees = S.pitch;
            style.rollDegrees = S.roll;          // T-011 新增（只有第 3 段非 0）
            style.lift = S.lift;
            style.liftDrift = S.liftDrift;       // 下坠/上抬
            style.lateralDrift = S.lateralDrift; // 斜移
            style.capVertices = 1;

            // ⚠️ **视觉半径/弧角与判定并不一一对应，这一条必须写在明处**（T-051 的教训：
            //    不要在注释里声称"视觉不撒谎"而实际存在系数）：
            //    * 半径：视觉 = 判定 × `SlashRadiusScale(0.85)` × **本段的 `radiusScale`（1.00/0.80/0.92）**
            //    * 弧角：第 1 段 = 判定弧角（×2）；**第 2/3 段故意收窄（70°/95°）** 用于形状区分
            //    → 即**第 2、3 段的视觉范围小于实际判定范围**，这是 T-011 为"四段可区分"**有意付出的代价**。
            //    依据：规格 §1.1 明确要求弧角 130/70/95。**不是疏漏，是取舍，故写在这里。**
            v.InitStyled(origin, f,
                hitRange * SlashRadiusScale * S.radiusScale,
                S.arc,
                S.color,
                style);
        }

        /// <summary>头顶冒一个黄色感叹号，duration 秒后自动消失。</summary>
        public static void Exclamation(Transform follow, float height, float duration)
        {
            var go = new GameObject("Vfx_Exclamation");
            go.transform.position = follow.position + Vector3.up * height;
            var v = go.AddComponent<ExclamationMark>();
            v.Init(follow, height, duration);
        }

        /// <summary>蓄力特效：跟着目标，半径收缩的圆环 + 中心球。</summary>
        public static void Charge(Transform follow, float height, float duration, Color color)
        {
            var go = new GameObject("Vfx_Charge");
            go.transform.position = follow.position + Vector3.up * height;
            var v = go.AddComponent<ChargeGlow>();
            v.Init(follow, height, duration, color);
        }

        /// <summary>月牙形范围斩击：在 origin 处朝 forward 张开的一段圆弧。</summary>
        public static void Crescent(Vector3 origin, Vector3 forward, float radius, float arcDegrees, Color color)
        {
            var go = new GameObject("Vfx_Crescent");
            go.transform.position = origin;
            var v = go.AddComponent<CrescentSlash>();
            v.Init(origin, forward, radius, arcDegrees, color);
        }

        /// <summary>向前劈砍：一条有厚度的直线斩击，快速淡出。</summary>
        public static void Slash(Vector3 origin, Vector3 forward, float length, Color color)
        {
            var go = new GameObject("Vfx_Slash");
            go.transform.position = origin;
            var v = go.AddComponent<CrescentSlash>();
            v.InitLine(origin, forward, length, color);
        }

        /// <summary>压平到水平面；朝向退化时退回 +Z。</summary>
        internal static Vector3 Flatten(Vector3 v)
        {
            v.y = 0f;
            if (v.sqrMagnitude < 0.0001f) v = Vector3.forward;
            return v.normalized;
        }
    }

    /// <summary>
    /// 月牙 / 斩击弧的造型参数。把"形状"和"调用点"解耦：
    /// 敌人冲刺斩（Enemy.cs）和玩家挥砍（PlayerCombat.cs）各用一套。
    /// </summary>
    public struct CrescentStyle
    {
        /// <summary>三层各自相对弧半径的倍率。必须拉开距离，否则叠成一团。</summary>
        public float[] radiusMul;
        /// <summary>三层各自的最大线宽（米）。</summary>
        public float[] widths;
        /// <summary>三层各自的透明度倍率。</summary>
        public float[] alphas;
        /// <summary>弧面相对水平面的仰角（度）。0 = 纯水平。</summary>
        public float pitchDegrees;
        /// <summary>弧带中点抬高（米）。</summary>
        public float lift;
        /// <summary>T-011 新增：绕**前向轴**滚（度）。0 = 不滚。
        /// 不加它，第 3 段只能是"pitch=45° 的斜拱"，在屏幕上仍是一条**弦为横**的弧，
        /// 与第 2 段的竖拱区分度不足（规格 §1.3）。</summary>
        public float rollDegrees;
        /// <summary>T-011 新增：生命期内 `lift` 的**增量**（弧带从 `lift` 线性移到 `lift + liftDrift`）。
        /// ⚠️ 用**增量**而不是"终点值"：终点值默认 0 会把没设置它的调用方的 `lift` 一起拉到 0（静默改变行为）。</summary>
        public float liftDrift;
        /// <summary>T-011 新增：生命期末沿横轴 `right` 的横向位移（米）。0 = 不位移。</summary>
        public float lateralDrift;
        /// <summary>端点圆角段数。</summary>
        public int capVertices;
    }

    /// <summary>头顶的黄色感叹号：一个竖条 + 一个点，始终面向相机。</summary>
    public class ExclamationMark : MonoBehaviour
    {
        private Transform follow;
        private float height;
        private float life;
        private float maxLife;
        private readonly Transform[] parts = new Transform[2];

        public void Init(Transform target, float h, float duration)
        {
            follow = target;
            height = h;
            life = maxLife = Mathf.Max(0.05f, duration);

            var mat = PlaceholderArt.GetGlowMaterial(SkillVfx.WarningColor);

            parts[0] = MakeBar(mat, "Stem", new Vector3(0f, 0.34f, 0f), new Vector3(0.16f, 0.42f, 0.16f));
            parts[1] = MakeBar(mat, "Dot", new Vector3(0f, 0.02f, 0f), new Vector3(0.16f, 0.16f, 0.16f));
        }

        private Transform MakeBar(Material mat, string name, Vector3 localPos, Vector3 scale)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            PlaceholderArt.StripCollider(go);
            go.transform.SetParent(transform, false);
            go.transform.localPosition = localPos;
            go.transform.localScale = scale;
            go.GetComponent<Renderer>().sharedMaterial = mat;
            return go.transform;
        }

        private void Update()
        {
            life -= Time.deltaTime;
            if (life <= 0f) { Destroy(gameObject); return; }

            if (follow != null) transform.position = follow.position + Vector3.up * height;

            // 跳一下更抓眼，同时始终面向相机
            float t = 1f - life / maxLife;
            float pop = 1f + Mathf.Sin(t * Mathf.PI) * 0.25f;
            transform.localScale = Vector3.one * pop;

            var cam = Camera.main;
            if (cam != null) transform.rotation = cam.transform.rotation;
        }
    }

    /// <summary>蓄力：跟着目标的一圈环（收缩）+ 中心光球。</summary>
    public class ChargeGlow : MonoBehaviour
    {
        private Transform follow;
        private float height;
        private float life;
        private float maxLife;
        private float ringRadius;
        private Transform ring;
        private Transform core;

        public void Init(Transform target, float h, float duration, Color color)
        {
            follow = target;
            height = h;
            life = maxLife = Mathf.Max(0.05f, duration);
            ringRadius = 1.6f;

            var mat = PlaceholderArt.GetGlowMaterial(color);

            // 环：用 LineRenderer 画个圆，随时间收缩（蓄力感）
            var ringGo = new GameObject("Ring");
            ringGo.transform.SetParent(transform, false);
            var lr = ringGo.AddComponent<LineRenderer>();
            lr.material = mat;
            lr.useWorldSpace = false;
            lr.loop = true;
            lr.widthMultiplier = 0.09f;
            lr.positionCount = 40;
            for (int i = 0; i < 40; i++)
            {
                float a = i / 40f * Mathf.PI * 2f;
                lr.SetPosition(i, new Vector3(Mathf.Cos(a) * ringRadius, 0f, Mathf.Sin(a) * ringRadius));
            }
            ring = ringGo.transform;

            // 核心球：逐渐变大
            var coreGo = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            coreGo.name = "Core";
            PlaceholderArt.StripCollider(coreGo);
            coreGo.transform.SetParent(transform, false);
            coreGo.GetComponent<Renderer>().sharedMaterial = mat;
            coreGo.transform.localScale = Vector3.one * 0.2f;
            core = coreGo.transform;
        }

        private void Update()
        {
            life -= Time.deltaTime;
            if (life <= 0f) { Destroy(gameObject); return; }

            if (follow != null) transform.position = follow.position;

            float t = 1f - life / maxLife;                 // 0 → 1
            if (ring != null)
            {
                float s = Mathf.Lerp(1f, 0.15f, t);        // 环往中心收
                ring.localScale = new Vector3(s, 1f, s);
                ring.localPosition = new Vector3(0f, height, 0f);
            }
            if (core != null)
            {
                core.localPosition = new Vector3(0f, height, 0f);
                core.localScale = Vector3.one * Mathf.Lerp(0.15f, 0.6f, t);
            }
        }
    }

    /// <summary>
    /// 斩击特效。
    ///
    /// **月牙是"面"不是"线"**：用粗 LineRenderer 做一条有厚度的弧带 ——
    /// 两端收尖（`widthCurve`）、中段最厚，读起来是刀光而不是一根细圆弧；
    /// 三层（内细边 / 中主体 / 外细边）叠出内外径差和边缘亮度。
    ///
    /// 弧面朝向：弧面绕水平横轴仰起 `CrescentStyle.pitchDegrees`，
    /// **中点高度被钉在 `lift` 上**（仰起带来的抬升在公式里扣掉了），
    /// 所以改仰角只改朝向，不会顺手把整条弧抬到头顶 ——
    /// 原来那个写死的 `+0.9m` 和调用方传进来的 `meleeHeight` 是叠加的，
    /// 结果刀光被顶到 1.9m、正好糊在巫师帽上（见 vfx_T010_before.png）。
    ///
    /// 直线劈砍保持原来的做法（一条粗细均匀的亮线，随时间收窄）。
    /// </summary>
    public class CrescentSlash : MonoBehaviour
    {
        private const float MaxLife = 0.3f;
        private const int Segments = 26;      // 月牙沿弧线的采样数

        private Vector3 origin;
        private Vector3 axis;                 // 弧面纵轴（a=0 的方向，受 pitch 影响）
        private Vector3 right;                // 弧面横轴（水平）
        private float baseRadius;
        private float arcDegrees;
        private float lineLength;
        private Color color;
        private bool lineMode;
        private float life;
        private bool ready;

        private CrescentStyle style;

        // 直线模式用
        private LineRenderer line;

        // 月牙模式用
        private LineRenderer[] layers;

        // ---- 敌人冲刺斩沿用的一套：**保持不变**（Enemy.cs:560 在用），别顺手改 ----
        private static readonly float[] LegacyRadiusMul = { 0.86f, 1.0f, 1.15f };
        private static readonly float[] LegacyLayerWidth = { 0.9f, 1.9f, 0.6f };
        private static readonly float[] LegacyLayerAlpha = { 0.55f, 1.0f, 0.4f };
        private const float LegacyLift = 0.9f;

        /// <summary>月牙形（旧签名）：以 origin 为心、forward 为中轴的月牙带。</summary>
        public void Init(Vector3 origin, Vector3 forward, float radius, float arcDegrees, Color color)
        {
            var legacy = new CrescentStyle();
            legacy.radiusMul = LegacyRadiusMul;
            legacy.widths = LegacyLayerWidth;
            legacy.alphas = LegacyLayerAlpha;
            legacy.pitchDegrees = 0f;
            legacy.lift = LegacyLift;
            legacy.capVertices = 3;
            InitStyled(origin, forward, radius, arcDegrees, color, legacy);
        }

        /// <summary>月牙形（带造型参数）：玩家挥砍走这条，形状／朝向／层宽都可控。</summary>
        public void InitStyled(Vector3 origin, Vector3 forward, float radius, float arcDegrees,
                               Color color, CrescentStyle style)
        {
            lineMode = false;
            this.origin = origin;
            this.baseRadius = radius;
            this.arcDegrees = arcDegrees;
            this.color = color;
            this.style = style;

            Vector3 f = SkillVfx.Flatten(forward);
            // 水平横轴：绕它仰起 = "弧面朝相机方向掀起来"
            right = Vector3.Cross(Vector3.up, f).normalized;
            // 纵轴：在"前"和"上"之间按仰角插值，远端抬起
            float p = style.pitchDegrees * Mathf.Deg2Rad;
            axis = new Vector3(f.x * Mathf.Cos(p), Mathf.Sin(p), f.z * Mathf.Cos(p)).normalized;

            // T-011：绕**前向轴**再滚一个角，把 `right` 与 `axis` 一起转。
            // 目的：做出屏幕上真正的"斜"（规格 §1.3）。roll = 0 时下面这段等价于什么都不做，
            // 所以**既有调用方（敌人冲刺斩等）行为一字不变**。
            if (Mathf.Abs(style.rollDegrees) > 0.0001f)
            {
                var rollRot = Quaternion.AngleAxis(style.rollDegrees, f);
                right = rollRot * right;
                axis = rollRot * axis;
            }

            Build();
        }

        /// <summary>直线劈砍。</summary>
        public void InitLine(Vector3 origin, Vector3 forward, float length, Color color)
        {
            lineMode = true;
            this.origin = origin;
            this.lineLength = length;
            this.color = color;
            this.style = new CrescentStyle { pitchDegrees = 0f, lift = LegacyLift, capVertices = 2 };
            this.axis = SkillVfx.Flatten(forward);
            this.right = Vector3.Cross(Vector3.up, this.axis).normalized;
            Build();
        }

        private void Build()
        {
            if (lineMode)
            {
                // 劈砍：一条粗细均匀的亮线（保持原来的样子）
                var go = new GameObject("SlashLine");
                go.transform.SetParent(transform, false);
                line = go.AddComponent<LineRenderer>();
                line.material = PlaceholderArt.GetGlowMaterial(color);
                line.useWorldSpace = true;
                line.positionCount = 2;
                line.numCapVertices = 2;
                line.numCornerVertices = 2;
                line.widthMultiplier = 0.34f;
                ready = true;
                ApplyShape(0f);
                return;
            }

            // 月牙：**用粗线而不是网格**。
            // 试过用程序生成的网格做填充月牙带，几何数据全对（52 顶点 / 150 三角 / bounds 正常）
            // 但就是不渲染，换了已知可用的材质也一样，没查出来。
            // LineRenderer 这条路是验证过能渲染的，所以改成"把线做粗 + 两端收尖"。
            var mat = PlaceholderArt.GetVertexColorMaterial();
            layers = new LineRenderer[style.radiusMul.Length];

            for (int i = 0; i < layers.Length; i++)
            {
                var go = new GameObject("CrescentLayer" + i);
                go.transform.SetParent(transform, false);
                var lr = go.AddComponent<LineRenderer>();
                lr.sharedMaterial = mat;
                lr.useWorldSpace = true;
                lr.positionCount = Segments;
                lr.numCapVertices = style.capVertices;
                lr.numCornerVertices = style.capVertices;
                lr.alignment = LineAlignment.View;   // 始终面向相机，粗线才像"面"
                lr.widthCurve = TaperCurve;          // 两端收尖、中间最厚
                lr.widthMultiplier = style.widths[i];
                layers[i] = lr;
            }

            ready = true;
            ApplyShape(0f);
        }

        /// <summary>中间粗、两端尖的粗细曲线 —— 形状感主要来自这条曲线。</summary>
        private static AnimationCurve taperCurve;

        private static AnimationCurve TaperCurve
        {
            get
            {
                if (taperCurve == null)
                {
                    taperCurve = new AnimationCurve(
                        new Keyframe(0f, 0.02f),
                        new Keyframe(0.5f, 1f),
                        new Keyframe(1f, 0.02f));
                    for (int i = 0; i < taperCurve.length; i++)
                        taperCurve.SmoothTangents(i, 0f);
                }
                return taperCurve;
            }
        }

        private void ApplyShape(float t)
        {
            if (!ready) return;

            float fade = 1f - t;

            // T-011：生命期内的"时机"维度（下坠 / 斜移）。二者默认 0 → 既有行为不变。
            float liftNow = style.lift + style.liftDrift * t;
            float driftNow = style.lateralDrift * t;

            if (lineMode)
            {
                if (line == null) return;
                Vector3 up = Vector3.up * liftNow;
                Vector3 a = origin - axis * (lineLength * 0.15f);
                Vector3 b = origin + axis * lineLength;
                line.SetPosition(0, a + up);
                line.SetPosition(1, b + up);
                line.widthMultiplier = 0.34f * Mathf.Lerp(1f, 0.15f, t);
                return;
            }

            if (layers == null) return;

            float spread = 1f + t * 0.22f;   // 播放期间整体推出去一点
            float half = arcDegrees * 0.5f;

            // 仰起会把整条弧抬高；这里把那份抬升扣掉，让**弧带中点**稳定落在 origin + lift：
            // 于是 pitch 只改变弧面朝向，不会顺手把刀光抬到头顶。
            float rise = baseRadius * Mathf.Sin(style.pitchDegrees * Mathf.Deg2Rad);

            for (int i = 0; i < layers.Length; i++)
            {
                var lr = layers[i];
                if (lr == null) continue;

                float radius = baseRadius * style.radiusMul[i] * spread;
                for (int s = 0; s < Segments; s++)
                {
                    float a = Mathf.Lerp(-half, half, s / (float)(Segments - 1)) * Mathf.Deg2Rad;
                    Vector3 dir = new Vector3(
                        axis.x * Mathf.Cos(a) + right.x * Mathf.Sin(a),
                        axis.y * Mathf.Cos(a) + right.y * Mathf.Sin(a),
                        axis.z * Mathf.Cos(a) + right.z * Mathf.Sin(a));
                    Vector3 p = origin + dir * radius + right * driftNow;
                    lr.SetPosition(s, new Vector3(p.x, p.y + liftNow - rise, p.z));
                }

                lr.widthMultiplier = style.widths[i] * Mathf.Lerp(0.5f, 1f, fade) * spread;
                lr.colorGradient = MakeGradient(color, style.alphas[i] * fade);
            }
        }

        /// <summary>两端透明、中间实 —— 端点不会有生硬截断。</summary>
        private static Gradient MakeGradient(Color c, float alphaMul)
        {
            var g = new Gradient();
            float a = Mathf.Clamp01(alphaMul);

            // ⛔ T-068 **方案 A 已实测证伪，已回退** —— 不要在这里乘 `GlowGain`。
            //
            // 试过的做法：把三色键各乘 `PlaceholderArt.GlowGain`，指望顶点色 >1 过 Bloom 阈值。
            // 实测（`tmp\t068_clamp_proof.py`，增益 1.0 / 1.7 / 8.0 三档同机位同构图）：
            //   月牙带 1.0→1.7 与 1.0→8.0 的像素结果**逐位相同**
            //   （均值 56.01→56.49、最亮 144→150、差异像素 25634 —— 两档数字完全一致）
            //   → 这是**夹取**的特征：>1 的部分被夹到 1，**增益再大也不起作用**。
            //   同一次对照里爆花（走 `GetGlowMaterial`）随增益单调剧变（12.88%→47.43%）→ Bloom 链路本身正常。
            //
            // 机制推断：`LineRenderer.colorGradient` 会被烘成一张 **8bit 贴图**，
            // 顶点色在到达片元着色器之前就已经被夹到 [0,1]。
            // 因此**任何**在顶点色上做文章的方案都不成立 —— 要发光只能改**材质侧**的 HDR 颜色（= 方案 B）。
            g.SetKeys(
                new[]
                {
                    new GradientColorKey(c, 0f),
                    new GradientColorKey(Color.Lerp(c, Color.white, 0.45f), 0.5f),
                    new GradientColorKey(c, 1f),
                },
                new[]
                {
                    new GradientAlphaKey(0f, 0f),
                    new GradientAlphaKey(a, 0.5f),
                    new GradientAlphaKey(0f, 1f),
                });
            return g;
        }

        private void Update()
        {
            life += Time.deltaTime;
            float t = life / MaxLife;
            if (t >= 1f) { Destroy(gameObject); return; }
            ApplyShape(t);
        }
    }

    /// <summary>
    /// T-081 **格挡表现**：一道盾弧 + 一束定向火花，总时长 `Life = 0.18 s`（旧爆花 0.35 s 的一半）。
    ///
    /// 🔴 **它刻意不生成任何球壳**（`ArcaneBurst` 会建一个 `Shell` 子物体）—— 规格 F3 的失败线就是"球壳仍在"。
    /// 🔴 **它有方向**：弧点在"垂直于攻击来向"的平面内张开；火花沿来向飞出 → 规格 F4 量的是
    ///    **火花群质心的位移方向 vs 攻击来向 ≤ 60°**（由探针独立测，不是自证）。
    /// 🔴 **急停不缓散**：尺寸在 0.045 s 内一次到位、0.10 s 保持，之后 0.08 s 内 alpha 归零；
    ///    **旧球壳是"边胀边散"** —— 那才是"被挡比打中还响"的根源。
    ///
    /// 渲染：`PlaceholderArt.GetGlowMaterial`（URP/Unlit，**不夹取**）→ 春绿 ×`GlowGain 1.7` 会过 Bloom。
    /// ⚠️ **不是** `LineRenderer.colorGradient` 那条被 8bit 夹取的顶点色路径（T-068 已证）：这里
    ///    **渐变保持白色、颜色由材质 `_BaseColor` 携带**，alpha 才走渐变。
    /// </summary>
    public class BlockArcVfx : MonoBehaviour
    {
        /// <summary>总存活（秒）。规格 F5：**≤ 0.20 s**。</summary>
        public const float Life = 0.18f;
        /// <summary>出现阶段结束时刻（此后只掉 alpha）。</summary>
        private const float SnapEnd = 0.10f;
        /// <summary>盾弧横向世界尺寸（规格 1.0–1.2 m ≈ 40–47 px）。</summary>
        private const float Span = 1.10f;
        private const int ArcPoints = 13;
        private const int SparkCount = 7;
        /// <summary>火花飞出距离（规格 ≈0.6 m）。</summary>
        private const float SparkFly = 0.60f;
        /// <summary>每条火花自身的长度（规格 0.3 m）。</summary>
        private const float SparkLen = 0.30f;

        private LineRenderer arc;
        private LineRenderer[] sparks;
        private Vector3[] sparkStart;
        private Vector3[] sparkDir;
        private Vector3 rightAxis;
        private float t;

        private static AnimationCurve Taper = new AnimationCurve(
            new Keyframe(0f, 0.12f), new Keyframe(0.5f, 1f), new Keyframe(1f, 0.12f));

        public void Init(Vector3 anchor, Vector3 toAttacker, Transform shield)
        {
            Vector3 dir = toAttacker;
            dir.y = 0f;
            if (dir.sqrMagnitude < 1e-6f) dir = transform.forward;
            dir.Normalize();
            rightAxis = Vector3.Cross(Vector3.up, dir);
            if (rightAxis.sqrMagnitude < 1e-6f) rightAxis = Vector3.right;
            rightAxis.Normalize();

            // 锚点：**优先盾网格**（"就是这面盾挡下的"，语义最强）；取不到用规格的回退（胸口 + 朝攻击者 0.35 m）
            Vector3 basePos = anchor;
            if (shield != null)
            {
                var rs = shield.GetComponentsInChildren<Renderer>(true);
                basePos = rs.Length > 0 ? rs[0].bounds.center : shield.position;
            }
            transform.position = basePos;

            var mat = PlaceholderArt.GetGlowMaterial(SkillVfx.BlockColor);
            PlaceholderArt.StripCollider(gameObject);

            // ---- 盾弧：垂直于来向的一段浅弧；**billboard 渲染**（永不退化，见类注释）----
            var arcGo = new GameObject("BlockArc");
            arcGo.transform.SetParent(transform, false);
            arc = arcGo.AddComponent<LineRenderer>();
            arc.material = mat;
            arc.useWorldSpace = true;
            arc.alignment = LineAlignment.View;
            arc.positionCount = ArcPoints;
            arc.widthMultiplier = 0.10f;
            arc.widthCurve = Taper;
            arc.numCapVertices = 2;
            for (int i = 0; i < ArcPoints; i++)
            {
                float u = -1f + 2f * i / (ArcPoints - 1);
                arc.SetPosition(i, basePos + rightAxis * (Span * 0.5f * u)
                                       + Vector3.up * (0.30f * (1f - u * u) - 0.15f));
            }

            // ---- 火花：沿**攻击来向**飞（质心位移方向 = F4 的被测量）----
            sparks = new LineRenderer[SparkCount];
            sparkStart = new Vector3[SparkCount];
            sparkDir = new Vector3[SparkCount];
            for (int i = 0; i < SparkCount; i++)
            {
                float u = SparkCount == 1 ? 0f : (-1f + 2f * i / (SparkCount - 1));
                var sgo = new GameObject("BlockSpark" + i);
                sgo.transform.SetParent(transform, false);
                var lr = sgo.AddComponent<LineRenderer>();
                lr.material = mat;
                lr.useWorldSpace = true;
                lr.alignment = LineAlignment.View;
                lr.positionCount = 2;
                lr.widthMultiplier = 0.035f;
                lr.numCapVertices = 0;
                sparkStart[i] = basePos + rightAxis * (Span * 0.42f * u)
                                         + Vector3.up * (0.26f * (1f - Mathf.Abs(u)) - 0.10f);
                // 沿来向飞；只给 12% 的横向散开（散太多会把质心方向拉偏，F4 就假了）
                sparkDir[i] = (dir + rightAxis * (0.12f * u)).normalized;
                sparks[i] = lr;
            }

            Apply(0f);
        }

        private void Update()
        {
            t += Time.deltaTime;
            if (t >= Life) { Destroy(gameObject); return; }
            Apply(t);
        }

        private void Apply(float time)
        {
            // **尺寸一次到位（急停）**：只有 alpha 在尾段掉下去 → 与旧球壳"边胀边散"相反
            float a = time <= SnapEnd
                ? Mathf.Clamp01(time / 0.045f)
                : Mathf.Clamp01(1f - (time - SnapEnd) / (Life - SnapEnd));
            var c = new Color(1f, 1f, 1f, a);
            if (arc != null) { arc.startColor = c; arc.endColor = c; }

            float fly = SparkFly * Mathf.Clamp01(time / Life);
            for (int i = 0; i < sparks.Length; i++)
            {
                if (sparks[i] == null) continue;
                var p0 = sparkStart[i] + sparkDir[i] * fly;
                sparks[i].SetPosition(0, p0);
                sparks[i].SetPosition(1, p0 + sparkDir[i] * SparkLen);
                sparks[i].startColor = c;
                sparks[i].endColor = c;
            }
        }
    }
}
