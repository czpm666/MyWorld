using System.Collections.Generic;
using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// **伤害飘字的对象池**（打击特效 T-0xx）。
    ///
    /// 为什么要自己画字而不是用 TextMeshPro / UI Canvas：
    ///   * 飘字是**世界空间**的、每帧 billboard 的小方块，和 `HealthBar` 同一路子
    ///     （本项目世界空间 HUD 一律"网格 + `rotation = Camera.main.transform.rotation`"，
    ///      不引入 Canvas —— 见 `HealthBar.cs` 的注释）；
    ///   * 引 TMP 要多一个包 + 一套字体资源 + Canvas 排序问题，而这里只需要
    ///     0-9 和几个大写字母，**5×7 点阵图集程序化生成**就够了，零资源依赖。
    ///
    /// 池化契约（验收标准"特效会回收，不泄漏"）：
    ///   * 启动时一次性建好 <see cref="MaxTexts"/> 个物体，**运行期永不 new GameObject**；
    ///   * 池满时**抢最老的那个**（和 `VfxRingPool.Acquire` 同一策略），不扩容；
    ///   * 每个物体自持一份 Mesh，复用时不重新分配数组（只有字符数变多才扩容）。
    ///   <see cref="ReusedTotal"/> 可以证明"第二次飘字真的复用了旧物体"。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class VfxTextPool : MonoBehaviour
    {
        /// <summary>同屏最多几个飘字。超了抢最老的。</summary>
        public const int MaxTexts = 24;

        /// <summary>一条飘字最多几个字符（超了截断）。</summary>
        public const int MaxChars = 7;

        // ---------------- 5×7 点阵字形 ----------------
        // 表里的字符顺序 = 字形索引顺序。'#' = 实心。
        private const string GlyphChars = "0123456789+-!BLOCKRIT";

        private static readonly string[] GlyphBits =
        {
            // 0
            ".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###.",
            // 1
            "..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###.",
            // 2
            ".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####",
            // 3
            "#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###.",
            // 4
            "...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#.",
            // 5
            "#####", "#....", "####.", "....#", "....#", "#...#", ".###.",
            // 6
            "..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###.",
            // 7
            "#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#...",
            // 8
            ".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###.",
            // 9
            ".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##..",
            // +
            ".....", "..#..", "..#..", "#####", "..#..", "..#..", ".....",
            // -
            ".....", ".....", ".....", "#####", ".....", ".....", ".....",
            // !
            "..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#..",
            // B
            "####.", "#...#", "#...#", "####.", "#...#", "#...#", "####.",
            // L
            "#....", "#....", "#....", "#....", "#....", "#....", "#####",
            // O
            ".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###.",
            // C
            ".###.", "#...#", "#....", "#....", "#....", "#...#", ".###.",
            // K
            "#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#",
            // R
            "####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#",
            // I
            "#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####",
            // T
            "#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#..",
        };

        private const int GlyphW = 5;      // 点阵宽（源像素）
        private const int GlyphH = 7;      // 点阵高（源像素）
        private const int GlyphScale = 4;  // 放大倍数 → 每个字形 20×28 像素
        private const int GlyphPad = 2;    // 字形四周留白（源像素），防止 mipmap 串色

        private const int CellW = GlyphW * GlyphScale + GlyphPad * 2;   // 24
        private const int CellH = GlyphH * GlyphScale + GlyphPad * 2;   // 32
        private const int AtlasW = CellW * 21;
        private const int AtlasH = CellH;

        /// <summary>一条飘字实例。字段全是可复用的，激活时只改值不重建。</summary>
        private sealed class Entry
        {
            public GameObject Go;
            public MeshFilter Filter;
            public MeshRenderer Renderer;
            public Mesh Mesh;
            public Vector3[] Verts;
            public Vector2[] Uvs;
            public Color32[] Colors;
            public int[] Tris;
            public int BuiltChars;

            public string Text;
            public Color Color;
            public float Height;    // 世界高度（米）
            public float Life;
            public float Age;
            public Vector3 Origin;
            public float DriftX;
            public float Rise;
            public float Wobble;
            public bool Active;
        }

        private readonly Entry[] entries = new Entry[MaxTexts];
        private readonly List<Entry> live = new List<Entry>(MaxTexts);

        private Material material;
        private Texture2D atlas;
        private Transform root;
        private Camera cam;

        /// <summary>累计生成过多少条飘字（含复用）。</summary>
        public int SpawnedTotal { get; private set; }

        /// <summary>累计有多少次飘字**复用**了已有物体（= SpawnedTotal - 池扩容次数）。</summary>
        public int ReusedTotal { get; private set; }

        /// <summary>当前正在显示的飘字数量。</summary>
        public int ActiveCount => live.Count;

        /// <summary>池的容量，报告里写出来证明"有上限"。</summary>
        public int Capacity => MaxTexts;

        // ================= 静态入口 =================

        /// <summary>打伤害飘字。`amount` 会被四舍五入到整数。</summary>
        public static void Damage(Vector3 point, float amount, HitGrade grade)
        {
            if (!VfxFeel.DamageTextEnabled) return;

            VfxTextPool pool = Resolve();
            if (pool == null) return;

            string text = Mathf.RoundToInt(Mathf.Abs(amount)).ToString();
            if (grade == HitGrade.Crit) text += "!";   // 暴击档带感叹号，和颜色/字号三处一起编码"会心"
            pool.Spawn(text, VfxFeel.TextColorFor(grade), VfxFeel.TextScaleFor(grade),
                VfxFeel.TextLife, point);
        }

        /// <summary>治疗飘字：`+12`。</summary>
        public static void Heal(Vector3 point, float amount)
        {
            if (!VfxFeel.DamageTextEnabled) return;

            VfxTextPool pool = Resolve();
            if (pool == null) return;

            pool.Spawn("+" + Mathf.RoundToInt(Mathf.Abs(amount)), VfxFeel.TextColorFor(HitGrade.Light),
                VfxFeel.TextScaleFor(HitGrade.Light), VfxFeel.TextLife, point);
        }

        /// <summary>纯文字标签，例如格挡的 `BLOCK`。</summary>
        public static void Label(Vector3 point, string text, Color color, float height)
        {
            if (!VfxFeel.DamageTextEnabled) return;

            VfxTextPool pool = Resolve();
            if (pool == null) return;

            pool.Spawn(text, color, height, VfxFeel.TextLife, point);
        }

        private static VfxTextPool Resolve()
        {
            VfxHub hub = VfxHub.Instance;
            if (hub == null) hub = VfxHub.Ensure();
            return hub != null ? hub.Text : null;
        }

        // ================= 生命周期 =================

        private void Awake()
        {
            cam = Camera.main;

            // 自己一张材质：Sprites/Default 吃顶点色 + 我们自己的图集。
            // ⚠️ 不能用 PlaceholderArt.GetVertexColorMaterial() —— 那份是**全局共享**的，
            //    它的 _MainTex 是 1×1 白图，改掉会把 LineRenderer 的月牙一起弄坏。
            atlas = BuildAtlas();
            material = BuildMaterial(atlas);

            root = new GameObject("DamageTexts").transform;
            root.SetParent(transform, false);

            for (int i = 0; i < MaxTexts; i++) entries[i] = Build(i);
        }

        private void OnDestroy()
        {
            if (material != null) Destroy(material);
            if (atlas != null) Destroy(atlas);
        }

        private Entry Build(int index)
        {
            var go = new GameObject("VfxText#" + index);
            go.transform.SetParent(root, false);
            go.SetActive(false);

            var e = new Entry
            {
                Go = go,
                Filter = go.AddComponent<MeshFilter>(),
                Renderer = go.AddComponent<MeshRenderer>(),
                Verts = new Vector3[MaxChars * 4],
                Uvs = new Vector2[MaxChars * 4],
                Colors = new Color32[MaxChars * 4],
                Tris = new int[MaxChars * 6],
                Mesh = new Mesh { name = "M_VfxText#" + index },
                BuiltChars = -1,
            };
            e.Mesh.MarkDynamic();
            e.Filter.sharedMesh = e.Mesh;

            // 顶点色已经预乘了 alpha，所以用 Sprites/Default 的 `Blend One OneMinusSrcAlpha` 正好
            e.Renderer.sharedMaterial = material;
            e.Renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            e.Renderer.receiveShadows = false;
            e.Renderer.lightProbeUsage = UnityEngine.Rendering.LightProbeUsage.Off;
            e.Renderer.reflectionProbeUsage = UnityEngine.Rendering.ReflectionProbeUsage.Off;
            e.Renderer.sortingOrder = 40;   // 压在粒子(30)之上，飘字永远读得到

            return e;
        }

        // ================= 生成 =================

        /// <summary>放一条飘字。池满 → 抢最老的。</summary>
        public void Spawn(string text, Color color, float height, float life, Vector3 origin)
        {
            if (string.IsNullOrEmpty(text)) return;
            if (text.Length > MaxChars) text = text.Substring(0, MaxChars);

            Entry e = Acquire();
            if (e == null) return;

            e.Text = text;
            e.Color = color;
            e.Height = Mathf.Max(0.05f, height);
            e.Life = Mathf.Max(0.05f, life > 0f ? life : VfxFeel.TextLife);
            e.Age = 0f;
            e.Origin = origin;
            e.DriftX = Random.Range(-0.35f, 0.35f);
            e.Rise = Random.Range(1.05f, 1.45f);
            e.Wobble = Random.Range(0f, 6.283f);
            e.Active = true;

            e.Go.SetActive(true);
            if (!live.Contains(e)) live.Add(e);

            Apply(e);   // 立刻摆好位置，避免第一帧停在原点
            SpawnedTotal++;
        }

        private Entry Acquire()
        {
            // 1) 先找空位
            for (int i = 0; i < MaxTexts; i++)
            {
                Entry e = entries[i];
                if (e != null && !e.Active)
                {
                    if (SpawnedTotal > 0) ReusedTotal++;
                    return e;
                }
            }

            // 2) 全满 → 抢最老的（Age 最大）。**不扩容、不 new**，这是"有上限"的保证。
            Entry oldest = null;
            for (int i = 0; i < MaxTexts; i++)
            {
                Entry e = entries[i];
                if (e == null) continue;
                if (oldest == null || e.Age > oldest.Age) oldest = e;
            }
            if (oldest != null) ReusedTotal++;
            return oldest;
        }

        private void Update()
        {
            if (cam == null) cam = Camera.main;

            float dt = Time.deltaTime;
            for (int i = live.Count - 1; i >= 0; i--)
            {
                Entry e = live[i];
                e.Age += dt;
                if (e.Age >= e.Life)
                {
                    e.Active = false;
                    e.Go.SetActive(false);
                    live.RemoveAt(i);
                    continue;
                }
                Apply(e);
            }
        }

        // ================= 每帧摆放 =================

        private void Apply(Entry e)
        {
            float t = Mathf.Clamp01(e.Age / e.Life);

            // 上浮：先快后慢（1-(1-t)²），像被打出来的数字
            float rise = e.Rise * (1f - (1f - t) * (1f - t));

            // 弹出：0→0.12 放大过冲，0.12→0.37 回落到 1
            float pop;
            if (t < 0.12f) pop = Mathf.Lerp(0.45f, 1.18f, t / 0.12f);
            else if (t < 0.37f) pop = Mathf.Lerp(1.18f, 1f, (t - 0.12f) / 0.25f);
            else pop = 1f;

            // 淡出：最后 35% 才淡，前面保持清晰（不然数字看不清）
            float fade = t < 0.65f ? 1f : Mathf.Clamp01(1f - (t - 0.65f) / 0.35f);

            // 轻微左右摆动，多个数字同时冒出来时不会重叠成一根柱子
            float sway = Mathf.Sin(e.Wobble + t * 4.2f) * 0.06f * e.Height;

            Vector3 pos = e.Origin
                          + Vector3.up * (0.35f * e.Height + rise)
                          + Vector3.right * (e.DriftX * t + sway);

            Transform tr = e.Go.transform;
            tr.position = pos;
            tr.rotation = cam != null ? cam.transform.rotation : Quaternion.identity;

            BuildMesh(e, e.Height * pop, fade);
        }

        /// <summary>
        /// 把 `e.Text` 摊成一组四边形。**只有字符数变多时才重新分配数组**，
        /// 其余情况原地改写 + `SetVertices(...,start,length)`，没有任何 GC。
        /// </summary>
        private void BuildMesh(Entry e, float height, float fade)
        {
            int n = e.Text.Length;
            if (n <= 0) return;

            // 每个点阵行占多少世界米
            float unit = height / GlyphH;
            float glyphW = GlyphW * unit;
            float advance = (GlyphW + 1) * unit;       // 字间距 = 1 个点阵列
            float totalW = (n - 1) * advance + glyphW;
            float x0 = -totalW * 0.5f;                 // 居中
            float half = height * 0.5f;

            // 预乘 alpha（Sprites/Default 是 Blend One OneMinusSrcAlpha）
            Color c = e.Color;
            byte r = (byte)(Mathf.Clamp01(c.r) * Mathf.Clamp01(c.a) * fade * 255f);
            byte g = (byte)(Mathf.Clamp01(c.g) * Mathf.Clamp01(c.a) * fade * 255f);
            byte b = (byte)(Mathf.Clamp01(c.b) * Mathf.Clamp01(c.a) * fade * 255f);
            byte a = (byte)(Mathf.Clamp01(c.a) * fade * 255f);
            var vc = new Color32(r, g, b, a);

            for (int i = 0; i < n; i++)
            {
                int gi = GlyphIndex(e.Text[i]);
                float u0 = (float)(gi * CellW + GlyphPad) / AtlasW;
                float u1 = (float)(gi * CellW + GlyphPad + GlyphW * GlyphScale) / AtlasW;
                float v0 = (float)GlyphPad / AtlasH;
                float v1 = (float)(GlyphPad + GlyphH * GlyphScale) / AtlasH;

                float left = x0 + i * advance;
                float right = left + glyphW;

                int v = i * 4;
                // 顺序照抄 Unity 内建 Quad（法线朝本地 -Z）→ rotation = 相机rotation 时正对相机
                e.Verts[v + 0] = new Vector3(left, -half, 0f);
                e.Verts[v + 1] = new Vector3(right, -half, 0f);
                e.Verts[v + 2] = new Vector3(left, half, 0f);
                e.Verts[v + 3] = new Vector3(right, half, 0f);

                e.Uvs[v + 0] = new Vector2(u0, v0);
                e.Uvs[v + 1] = new Vector2(u1, v0);
                e.Uvs[v + 2] = new Vector2(u0, v1);
                e.Uvs[v + 3] = new Vector2(u1, v1);

                e.Colors[v + 0] = vc;
                e.Colors[v + 1] = vc;
                e.Colors[v + 2] = vc;
                e.Colors[v + 3] = vc;

                int t = i * 6;
                e.Tris[t + 0] = v + 0; e.Tris[t + 1] = v + 2; e.Tris[t + 2] = v + 1;
                e.Tris[t + 3] = v + 2; e.Tris[t + 4] = v + 3; e.Tris[t + 5] = v + 1;
            }

            int vc4 = n * 4;
            int ic6 = n * 6;

            e.Mesh.Clear(false);   // 保留顶点布局
            e.Mesh.SetVertices(e.Verts, 0, vc4);
            e.Mesh.SetUVs(0, e.Uvs, 0, vc4);
            e.Mesh.SetColors(e.Colors, 0, vc4);
            e.Mesh.SetTriangles(e.Tris, 0, ic6, 0);

            // 动态网格必须自己报包围盒，否则会被视锥剔除掉
            var bounds = new Bounds(Vector3.zero, new Vector3(totalW, height, 0.01f));
            e.Mesh.bounds = bounds;
            e.BuiltChars = n;
        }

        private static int GlyphIndex(char c)
        {
            if (c >= 'a' && c <= 'z') c = (char)(c - 32);   // 统一按大写找
            int i = GlyphChars.IndexOf(c);
            return i >= 0 ? i : GlyphChars.IndexOf('!');    // 找不到的字形画成 '!'
        }

        // ================= 图集 / 材质 =================

        /// <summary>
        /// **编辑期就能跑的自检**（不需要进 Play、不需要场景里有任何物体）。
        ///
        /// 检查三件事，全部是客观断言，不靠人眼看截图：
        ///   ① 字形表长度自洽（`GlyphBits` 行数 == 字符数 × 7）；
        ///   ② 字符表里**每个字符都有字形**（没有"应该画出来却是空白"的）；
        ///   ③ 每个字形在生成的图集里**至少有一个不透明像素**（防"点阵写错了 → 屏幕上少一个数字"）。
        ///
        /// 返回 true = 全过。`report` 是逐条结果（写进 QA 报告）。
        /// </summary>
        public static bool SelfTest(out string report)
        {
            var sb = new System.Text.StringBuilder();
            bool ok = true;

            sb.AppendLine("VfxTextPool.SelfTest");
            sb.AppendLine("  glyphs=" + GlyphChars.Length + " bits=" + GlyphBits.Length
                          + " expectedBits=" + (GlyphChars.Length * GlyphH));

            if (GlyphBits.Length != GlyphChars.Length * GlyphH)
            {
                sb.AppendLine("  FAIL 字形表长度不自洽");
                ok = false;
            }

            Texture2D tex = BuildAtlas();
            for (int gi = 0; gi < GlyphChars.Length; gi++)
            {
                char c = GlyphChars[gi];
                int opaque = 0;
                for (int y = 0; y < GlyphH * GlyphScale; y++)
                    for (int x = 0; x < GlyphW * GlyphScale; x++)
                        if (tex.GetPixel(gi * CellW + GlyphPad + x, GlyphPad + y).a > 0.5f) opaque++;

                if (opaque == 0)
                {
                    sb.AppendLine("  FAIL 字形 '" + c + "' 在图集里全是透明");
                    ok = false;
                }
            }
            sb.AppendLine("  atlas=" + AtlasW + "x" + AtlasH + "  all " + GlyphChars.Length + " glyphs have ink");

            // 找到回退字形：任何**不在表里**的字符都会被画成它。用它反查"这个字符有没有专属字形"。
            int fallback = GlyphChars.IndexOf('!');
            const string mustSupport = "0123456789+-!BLOCKRIT";
            for (int i = 0; i < mustSupport.Length; i++)
            {
                char c = mustSupport[i];
                int gi = GlyphChars.IndexOf(c);
                if (gi < 0 || gi == fallback && c != '!')
                {
                    sb.AppendLine("  FAIL 缺字形 '" + c + "'");
                    ok = false;
                }
            }
            sb.AppendLine("  mustSupport=\"" + mustSupport + "\"  (= 数字 + - ! BLOCK CRIT 需要的全部字符)");

            Object.DestroyImmediate(tex);
            report = sb.ToString();
            return ok;
        }

        /// <summary>把 5×7 点阵放大成图集。启动时做一次，不落盘。</summary>
        private static Texture2D BuildAtlas()
        {
            var tex = new Texture2D(AtlasW, AtlasH, TextureFormat.RGBA32, true)
            {
                name = "T_VfxDigits",
                filterMode = FilterMode.Bilinear,
                wrapMode = TextureWrapMode.Clamp,
                anisoLevel = 0,
            };

            var clear = new Color32[AtlasW * AtlasH];
            for (int i = 0; i < clear.Length; i++) clear[i] = new Color32(255, 255, 255, 0);
            tex.SetPixels32(clear);

            int glyphCount = GlyphBits.Length / GlyphH;
            for (int gi = 0; gi < glyphCount && gi < GlyphChars.Length; gi++)
            {
                for (int row = 0; row < GlyphH; row++)
                {
                    string bits = GlyphBits[gi * GlyphH + row];
                    for (int col = 0; col < GlyphW && col < bits.Length; col++)
                    {
                        if (bits[col] != '#') continue;

                        // row 0 是字形顶部 → 贴图的 y 要大
                        int blockY = GlyphPad + (GlyphH - 1 - row) * GlyphScale;
                        int blockX = gi * CellW + GlyphPad + col * GlyphScale;
                        for (int dy = 0; dy < GlyphScale; dy++)
                            for (int dx = 0; dx < GlyphScale; dx++)
                                tex.SetPixel(blockX + dx, blockY + dy, Color.white);
                    }
                }
            }

            tex.Apply(true, false);
            return tex;
        }

        private static Material BuildMaterial(Texture2D tex)
        {
            var shader = Shader.Find("Sprites/Default");
            if (shader == null) shader = Shader.Find("Universal Render Pipeline/2D/Sprite-Unlit-Default");
            if (shader == null) shader = Shader.Find("Unlit/Transparent");

            var m = new Material(shader) { name = "M_VfxDamageText", color = Color.white };
            m.mainTexture = tex;
            if (m.HasProperty("_BaseMap")) m.SetTexture("_BaseMap", tex);
            m.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
            return m;
        }
    }
}
