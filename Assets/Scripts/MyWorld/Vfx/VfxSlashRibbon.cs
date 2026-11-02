using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// **刀光残影条带（剑影）** —— 沿刀刃扫过的弧线拉出一条带 alpha 衰减与宽度收尖的飘带。
    ///
    /// 与既有的 <see cref="SkillVfx.CrescentSlash"/> 的区别（两者是叠加关系，不是替代）：
    ///   * CrescentSlash = 一条**静态月牙**，整体统一膨胀 + 统一淡出。它像"贴在身前的一张图"，不跟刀走。
    ///   * 本类 = **扫掠残影**。刀刃在 `sweepSeconds` 内从弧的一端扫到另一端，条带上的
    ///     每个采样点保留的是它**被刀扫过那一刻**的角度 / 高度 / 亮度，于是尾巴自然落后于刀锋、
    ///     亮度自刀锋向尾巴递减、宽度自中段向两端收尖 —— 这才是"剑影"，不是"光环"。
    ///
    /// ⚠️ **几何必须自己点亮的地方**（本项目已经有前车之鉴）：
    ///   1. `SkillVfx.cs` 旧注释记录：程序生成的月牙网格"几何全对（52 顶点 / 150 三角 / bounds 正常）但就是不渲染"。
    ///      最可能的两个原因都在这里被显式处理：**材质强制 `_Cull = Off`**（绕序错了也照样可见）、
    ///      **顶点色按预乘写**（`rgb = color.rgb * a`，配合 `Sprites/Default` 的 `Blend One OneMinusSrcAlpha`；
    ///      若只写 alpha 而 rgb 不乘，会得到"透明却发亮"的底色或干脆看不见）。
    ///   2. 动态网格必须**自己报 bounds**，否则顶点一更新就被视锥剔除（`VfxTextPool` 同款坑）。
    ///   3. 材质是**静态缓存**的（全局一份），不是每次挥砍 `new Material` —— 避免泄漏。
    ///
    /// 时间用 `Time.deltaTime`（不是 unscaled）：顿帧时刀光应该跟着世界一起冻住，
    /// 否则 hitstop 的 0.035~0.095 s 里刀光还在飞，反而削弱打击感。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class VfxSlashRibbon : MonoBehaviour
    {
        /// <summary>沿条带的采样数。22 段在 1280×720 下已经看不出折线，且只有 46 顶点。</summary>
        public const int Segments = 22;

        // ---- 几何参数（Init 写入）----
        private Vector3 origin;
        private Vector3 axis;        // 弧面纵轴（a=0 的方向，受 pitch 影响，与 CrescentSlash 同一套约定）
        private Vector3 right;       // 弧面横轴
        private float radius;        // 条带中心线的弧半径
        private float arcDegrees;    // 弧张角
        private float halfWidth;     // 条带的最大径向半宽
        private float riseGain;      // 逐采样点的**高度差**：>0 上挑、<0 下劈（这是"上下两段弧"的实现）
        private bool invert;         // 扫掠方向反向（同一段的左右手差异）

        // ---- 时间参数 ----
        private float sweepSeconds = 0.10f;   // 刀锋扫完整段弧的时长
        private float trailSeconds = 0.13f;   // 刀锋身后还留着多长的历史（= 残影长度）
        private float fadeSeconds = 0.10f;    // 扫完之后整体淡出的时长
        private float life;
        private float age;

        private Color color = Color.white;

        // ---- 网格 ----
        private Mesh mesh;
        private Vector3[] verts;
        private Vector2[] uvs;
        private Color32[] cols;
        private int[] tris;
        private bool ready;

        /// <summary>
        /// 初始化。参数语义见字段注释；`pitchDegrees` / `rollDegrees` 与
        /// <see cref="SkillVfx.CrescentStyle"/> 完全一致，保证残影和月牙**同一个弧面**。
        /// </summary>
        public void Init(Vector3 origin, Vector3 forward, float radius, float arcDegrees, Color color,
                         float sweepSeconds, float trailSeconds,
                         float pitchDegrees, float rollDegrees, float riseGain, bool invert)
        {
            this.origin = origin;
            this.radius = Mathf.Max(0.05f, radius);
            this.arcDegrees = Mathf.Clamp(arcDegrees, 8f, 340f);
            this.color = color;
            this.sweepSeconds = Mathf.Max(0.02f, sweepSeconds);
            this.trailSeconds = Mathf.Clamp(trailSeconds, 0.02f, 0.5f);
            this.riseGain = riseGain;
            this.invert = invert;

            // 半径越大条带越宽：2.4m 的判定弧上给 ~0.30m 半宽，手感上"有厚度"但不糊
            this.halfWidth = Mathf.Clamp(this.radius * 0.13f, 0.10f, 0.42f);

            Vector3 f = SkillVfx.Flatten(forward);
            right = Vector3.Cross(Vector3.up, f).normalized;
            float p = pitchDegrees * Mathf.Deg2Rad;
            axis = new Vector3(f.x * Mathf.Cos(p), Mathf.Sin(p), f.z * Mathf.Cos(p)).normalized;

            if (Mathf.Abs(rollDegrees) > 0.0001f)
            {
                var rollRot = Quaternion.AngleAxis(rollDegrees, f);
                right = rollRot * right;
                axis = rollRot * axis;
            }

            // 扫掠 + 残影 + 淡出，最后再留一帧余量
            life = this.sweepSeconds + this.trailSeconds + this.fadeSeconds + 0.02f;

            Build();
            Apply();   // 立刻画一帧，避免第一帧停在原点
        }

        private void Build()
        {
            int vcount = 2 * (Segments + 1);
            verts = new Vector3[vcount];
            uvs = new Vector2[vcount];
            cols = new Color32[vcount];
            tris = new int[Segments * 6];

            for (int i = 0; i < Segments; i++)
            {
                int b = i * 2;
                int t = i * 6;
                // 每个四边形两个三角；绕序无所谓（材质 _Cull = Off），但保持一致便于排查
                tris[t + 0] = b + 0; tris[t + 1] = b + 2; tris[t + 2] = b + 1;
                tris[t + 3] = b + 2; tris[t + 4] = b + 3; tris[t + 5] = b + 1;
            }

            var mf = gameObject.AddComponent<MeshFilter>();
            var mr = gameObject.AddComponent<MeshRenderer>();

            mesh = new Mesh { name = "M_VfxSlashRibbon" };
            mesh.MarkDynamic();
            mesh.vertices = verts;
            mesh.uv = uvs;
            mesh.triangles = tris;
            mesh.bounds = new Bounds(origin, Vector3.one * (radius * 2f + 1f));

            mf.sharedMesh = mesh;

            mr.sharedMaterial = RibbonMaterial();
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            mr.receiveShadows = false;
            mr.lightProbeUsage = UnityEngine.Rendering.LightProbeUsage.Off;
            mr.reflectionProbeUsage = UnityEngine.Rendering.ReflectionProbeUsage.Off;
            mr.sortingOrder = 31;   // 粒子是 30、飘字是 40；刀光夹在中间

            ready = true;
        }

        private void Update()
        {
            if (!ready) return;
            age += Time.deltaTime;
            if (age >= life)
            {
                // 不在这里记 NoteTransientDestroyed：OnDestroy 里已经统一记一次，
                // 两处都记会把计数减两次（QA 的"一次性物体归零"会假红）。
                Destroy(gameObject);
                return;
            }
            Apply();
        }

        /// <summary>重建顶点。核心是"每个采样点取它**历史时刻**的扫掠进度"，尾巴才会落后于刀锋。</summary>
        private void Apply()
        {
            float halfArc = arcDegrees * 0.5f;

            // 整体淡出：扫掠期间为 1（开头 15% 快速淡入），扫完后线性到 0
            float fade;
            if (age < sweepSeconds)
                fade = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(age / (sweepSeconds * 0.15f)));
            else
                fade = Mathf.Clamp01(1f - (age - sweepSeconds) / fadeSeconds);

            float alphaMul = Mathf.Clamp01(color.a) * fade;

            for (int i = 0; i <= Segments; i++)
            {
                float u = i / (float)Segments;                 // 0 = 刀锋，1 = 尾巴
                float tau = age - u * trailSeconds;            // 这个采样点被扫过的时刻
                float swept = Mathf.Clamp01(tau / sweepSeconds);

                // 这条采样带的"年龄"：越靠尾巴越老 → 越暗
                float tail = Mathf.Clamp01(u);
                float a = Mathf.Pow(1f - tail, 1.6f) * alphaMul;

                // 宽度：中段最厚、刀锋与尾巴两端收尖（收尖是"像刀"而不是"像扇面"的关键）
                float w = Mathf.Pow(1f - tail, 1.1f) * Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(u / 0.12f));

                // 高度：使用各自历史进度，于是上挑/下劈会自然形成"上下两段弧"
                float h = riseGain * (swept - 0.5f);

                float ang = Mathf.Lerp(-halfArc, halfArc, invert ? 1f - swept : swept) * Mathf.Deg2Rad;
                Vector3 radial = (axis * Mathf.Cos(ang) + right * Mathf.Sin(ang)).normalized;

                float rIn = radius - halfWidth * w;
                float rOut = radius + halfWidth * w;
                Vector3 lift = Vector3.up * h;

                int b = i * 2;
                verts[b + 0] = origin + radial * rIn + lift;
                verts[b + 1] = origin + radial * rOut + lift;

                uvs[b + 0] = new Vector2(u, 0f);
                uvs[b + 1] = new Vector2(u, 1f);

                // 预乘：rgb 先乘 alpha，再交给 Sprite/Default 的 Blend One OneMinusSrcAlpha
                byte r = (byte)(Mathf.Clamp01(color.r * a) * 255f);
                byte g = (byte)(Mathf.Clamp01(color.g * a) * 255f);
                byte bl = (byte)(Mathf.Clamp01(color.b * a) * 255f);
                byte ab = (byte)(Mathf.Clamp01(a) * 255f);
                var c = new Color32(r, g, bl, ab);
                cols[b + 0] = c;
                cols[b + 1] = c;
            }

            if (mesh == null) return;
            mesh.vertices = verts;
            mesh.uv = uvs;
            mesh.colors32 = cols;

            // 动态网格必须自己报包围盒，否则会被视锥剔除
            mesh.bounds = new Bounds(origin, Vector3.one * (radius * 2f + Mathf.Abs(riseGain) + 1f));
        }

#if UNITY_EDITOR
        /// <summary>
        /// QA 自证 ①：材质是**运行时 `new Material(...)` 建出来的**，不是引用工程里的资源。
        /// `SkillVfx.cs` 里记过的"程序化网格不渲染"两个嫌疑之一是材质丢失
        /// （`ScriptedImporter` 导入的材质被删/引用断掉）；这条让那件事可证伪：
        /// 只要 `DebugMaterial` 非空、`renderQueue == 3000`、`_Cull == 0`、
        /// `mainTexture` 是我们自己生成的 4×64 渐变图，就说明渲染链路不依赖任何磁盘资源。
        /// </summary>
        public static Material DebugMaterial => RibbonMaterial();

        /// <summary>QA 自证 ②：包围盒非 0（另一个嫌疑是 bounds 为 0 被视锥整体剔除）。</summary>
        public Mesh DebugMesh => mesh;

        /// <summary>QA 用：网格顶点数（应当 = (Segments+1)*2）。</summary>
        public int DebugVertexCount => mesh != null ? mesh.vertexCount : 0;

        /// <summary>QA 用：当前顶点色里最大的 alpha（0 就说明这一帧画面里不可能有它）。</summary>
        public int DebugMaxAlpha
        {
            get
            {
                if (cols == null) return 0;
                int max = 0;
                for (int i = 0; i < cols.Length; i++) if (cols[i].a > max) max = cols[i].a;
                return max;
            }
        }
#endif

        private void OnDestroy()
        {
            VfxHub.NoteTransientDestroyed();
            if (mesh != null) Destroy(mesh);
        }

#if UNITY_EDITOR
        /// <summary>
        /// QA 专用：把条带定格到指定年龄再渲染。
        ///
        /// 为什么需要它：抓一张 1280×720 的图（`cam.Render` + `ReadPixels` + `EncodeToPNG`）要 ~0.2s，
        /// 于是下一帧的 `deltaTime` 直接跳过条带 0.35s 的整个生命周期 —— 逐帧抓拍拿不到中间态。
        /// 冻结 `Time.timeScale` 后由这个接口显式驱动，出图才和帧率无关。
        /// </summary>
        public void DebugSetAge(float seconds)
        {
            if (!ready) return;
            age = Mathf.Clamp(seconds, 0f, Mathf.Max(0f, life - 0.001f));
            Apply();
        }

        /// <summary>QA 专用：条带的总寿命（秒），用来把"进度"换算成年龄。</summary>
        public float DebugLife => life;
#endif

        // ==================== 材质（静态缓存，全局一份） ====================

        private static Material cachedMaterial;
        private static Texture2D cachedGradient;

        private static Material RibbonMaterial()
        {
            if (cachedMaterial != null) return cachedMaterial;

            Shader sh = Shader.Find("Sprites/Default");
            if (sh == null) sh = Shader.Find("Universal Render Pipeline/2D/Sprite-Unlit-Default");
            if (sh == null) sh = Shader.Find("Unlit/Transparent");

            var m = new Material(sh) { name = "M_VfxSlashRibbon" };
            Texture2D tex = GradientTexture();
            m.mainTexture = tex;
            if (m.HasProperty("_BaseMap")) m.SetTexture("_BaseMap", tex);
            if (m.HasProperty("_Color")) m.SetColor("_Color", Color.white);
            // 强制不剔除：绕序万一写反了也照样可见（本项目踩过"网格不渲染"的坑）
            m.SetInt("_Cull", (int)UnityEngine.Rendering.CullMode.Off);
            m.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;

            cachedMaterial = m;
            return m;
        }

        /// <summary>
        /// 条带的横向剖面：一条"软边"的宽带（v=0/1 两端 alpha→0，中间最厚）。
        /// 有了它，加粗也不会出现硬边 —— 这正是旧月牙"三层粗线叠成一坨白斑"的反面。
        /// </summary>
        private static Texture2D GradientTexture()
        {
            if (cachedGradient != null) return cachedGradient;

            const int H = 64;
            var tex = new Texture2D(4, H, TextureFormat.RGBA32, false)
            {
                name = "T_VfxSlashRibbon",
                wrapMode = TextureWrapMode.Clamp,
                filterMode = FilterMode.Bilinear,
                anisoLevel = 0
            };

            var px = new Color32[4 * H];
            for (int y = 0; y < H; y++)
            {
                float v = y / (H - 1f);
                // 两端 0、中间 1 的对称剖面
                float edge = 1f - Mathf.Abs(v * 2f - 1f);
                float a = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(edge));
                a = Mathf.Pow(a, 0.75f);
                byte by = (byte)(Mathf.Clamp01(a) * 255f);
                var c = new Color32(255, 255, 255, by);
                for (int x = 0; x < 4; x++) px[y * 4 + x] = c;
            }

            tex.SetPixels32(px);
            tex.Apply(false, false);
            cachedGradient = tex;
            return tex;
        }
    }
}
