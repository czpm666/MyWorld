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
        /// 弧面相对水平面的仰角（度）。0 = 纯水平，90 = 纯竖直。
        /// 相机俯角 52°，纯竖直的斩击面在俯视下会被压成一条线（用户否决过线状效果），
        /// 所以只做小幅仰起：让外缘露出来，同时保留"横扫"的读法。
        /// </summary>
        public static float SlashPitchDegrees = 20f;

        /// <summary>弧带中点高出判定中心的高度（米）。判定中心本身已是胸口高度，这里只小幅抬高。</summary>
        public static float SlashLift = 0.25f;

        /// <summary>挥砍月牙的颜色：偏白的冷色，和敌人的橙/品红拉开区分。（原 PlayerCombat.SlashColor）</summary>
        public static readonly Color SwordSlashColor = new Color(0.86f, 0.95f, 1f, 1f);

        /// <summary>突刺（连招最后一段）的颜色，更亮更暖，让收招看得出来。（原 PlayerCombat.FinisherColor）</summary>
        public static readonly Color SwordFinisherColor = new Color(1f, 0.94f, 0.72f, 1f);

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

        /// <summary>
        /// 玩家剑的挥砍刀光。**这是玩家挥砍唯一的视觉入口**，
        /// 由 `PlayerCombat.OnSlashImpact()` 在动画命中帧调用。
        /// </summary>
        /// <param name="center">判定中心（已是胸口高度）</param>
        /// <param name="forward">出手朝向</param>
        /// <param name="hitRange">判定近战半径。只用来换算视觉尺寸，判定本身仍在 PlayerCombat</param>
        /// <param name="hitHalfAngleDegrees">判定半张角。只用来换算视觉弧角</param>
        /// <param name="finisher">是否连招最后一段（突刺），决定颜色</param>
        public static void SwordSlash(Vector3 center, Vector3 forward, float hitRange,
                                      float hitHalfAngleDegrees, bool finisher)
        {
            Vector3 f = Flatten(forward);

            // 弧心前移到身前，弧带才不会绕回来压住角色
            float d = hitRange * SlashCenterForwardScale;
            Vector3 origin = center + new Vector3(f.x * d, 0f, f.z * d);

            var go = new GameObject("Vfx_SwordSlash");
            go.transform.position = origin;

            var style = new CrescentStyle();
            style.radiusMul = SwordRadiusMul;
            style.widths = SwordLayerWidth;
            style.alphas = SwordLayerAlpha;
            style.pitchDegrees = SlashPitchDegrees;
            style.lift = SlashLift;
            style.capVertices = 1;

            var v = go.AddComponent<CrescentSlash>();
            v.InitStyled(origin, f,
                hitRange * SlashRadiusScale,     // 视觉弧半径
                // ⚠️ T-051 订正：原注释写"视觉弧角 = 判定弧角，**视觉不撒谎**" —— **只对角度成立，对半径不成立。**
                // 角度这一项确实一致（判定半张角 ×2）；但**半径另有 `SlashRadiusScale = 0.85` 系数**
                // （本文件 :32），所以视觉弧半径 = 判定半径 × 0.85 —— **弧带内缘 < 判定半径、外缘 > 判定半径**，
                // 两者并不重合。写"不撒谎"会让后来的人以为视觉与判定对齐，从而**不去核这件事**。
                hitHalfAngleDegrees * 2f,        // 视觉弧角 = 判定弧角（角度一致；半径见上一行）
                finisher ? SwordFinisherColor : SwordSlashColor,
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

            if (lineMode)
            {
                if (line == null) return;
                Vector3 up = Vector3.up * style.lift;
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
                    Vector3 p = origin + dir * radius;
                    lr.SetPosition(s, new Vector3(p.x, p.y + style.lift - rise, p.z));
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
}
