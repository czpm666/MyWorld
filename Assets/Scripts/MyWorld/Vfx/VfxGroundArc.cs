using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// **贴地挥砍弧光**：沿挥砍方向在地面上铺开的一片扇形冲击波。
    ///
    /// 为什么要有它（而不是继续加强竖直的那条条带）：
    /// 本游戏默认是 52° 俯视。一条竖直扫过的薄片在这个角度近乎侧面，可见面积被压得很小，
    /// 玩家读到的是"一线"；而贴地的扇形是**正对相机**的，玩家一眼就能读出
    /// "我朝哪个方向、砍到了多大一片地"。俯视角下这才是应该用来表达挥砍的形状。
    ///
    /// 它和 <see cref="VfxSlashRibbon"/> 的分工：
    /// - ribbon  = 竖直的"刀影"，跟着刀走，第三人称/侧面看最漂亮；
    /// - groundArc = 贴地的"冲击弧"，俯视看最清楚，表达范围与朝向。
    /// 两者同时存在，互相补足，而不是谁替换谁。
    ///
    /// 几何技巧：网格只在 <see cref="Init"/> 里建一次（**静态**），
    /// 之后每个 Update 只改顶点色，不动顶点位置。扫掠感完全由 alpha 表达，
    /// 于是"扫过去"这件事既不重新分配数组、也不会因为顶点位置突变而闪烁。
    ///
    /// 渲染范式**照抄已经验证过能出图的 <see cref="VfxTextPool"/>**：
    /// 运行时自建 `Sprites/Default` 材质 + 预乘顶点色（rgb = color.rgb * a）+ 显式 mesh.bounds。
    /// 这三点合起来正好避开了 `SkillVfx.cs` 里记录过的"程序化网格不渲染"的两个已知嫌疑
    /// （材质引用丢失 / bounds 为 0 被视锥剔除）。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class VfxGroundArc : MonoBehaviour
    {
        /// <summary>沿弧方向的分段数。26 段对一片 1.6~2.2 m 的弧来说已经看不出折线。</summary>
        public const int Segments = 26;

        /// <summary>沿半径方向的环数：0 = 内缘（淡），2 = 外缘（亮）。"外侧亮内侧淡"就靠它。</summary>
        const int Rows = 3;

        /// <summary>内缘半径占外缘半径的比例（0.35 → 1.0 的径向铺展）。</summary>
        const float InnerRadiusScale = 0.35f;

        /// <summary>扫掠占生命期的比例，剩下的是淡出。</summary>
        const float SweepPortion = 0.45f;

        /// <summary>扫掠前沿的拖尾软度（0.30 = 前沿之后 30% 的角度范围内 alpha 渐变）。</summary>
        const float SweepSoftness = 0.30f;

        /// <summary>逐环的亮度权重：外侧亮、内侧淡。</summary>
        static readonly float[] RowGain = { 0.22f, 0.55f, 1.00f };

        static Material cachedMaterial;

        Vector3[] verts;
        Color32[] colors;
        Mesh mesh;
        MeshRenderer meshRenderer;

        Vector3 center;
        Vector3 forward;
        Vector3 right;
        float radius;
        float halfArcRadians;
        float life;
        float hoverHeight;
        float tiltHeight;
        float age;
        Color color;

        /// <summary>
        /// 生成一片贴地弧光。
        /// </summary>
        /// <param name="center">角色胸口附近的点（即战斗代码里的 `center`）；内部会自己向下找地面。</param>
        /// <param name="forward">挥砍方向（水平化）。弧以它为中心线左右对称展开。</param>
        /// <param name="radius">外缘半径（米），一般直接用武器的 meleeRange。</param>
        /// <param name="arcDegrees">扇形张角，一般直接用武器的 meleeHalfAngle * 2。</param>
        /// <param name="life">生命期，建议 0.28~0.34 秒。</param>
        /// <param name="hoverHeight">离地高度 0.10~0.18 m，避免和地砖 z-fight。</param>
        /// <param name="tiltHeight">外缘额外抬起的高度，让弧带"外侧上翘"而不是纯平面。</param>
        public static VfxGroundArc Spawn(Vector3 center, Vector3 forward, float radius, float arcDegrees,
            Color color, float life = 0.30f, float hoverHeight = 0.14f, float tiltHeight = 0.10f)
        {
            if (!VfxHub.RequestTransient()) return null;

            var go = new GameObject("Vfx_GroundArc");
            var arc = go.AddComponent<VfxGroundArc>();
            arc.Init(center, forward, radius, arcDegrees, color, life, hoverHeight, tiltHeight);
            return arc;
        }

        void Init(Vector3 origin, Vector3 direction, float arcRadius, float arcDegrees,
                  Color arcColor, float lifeSeconds, float hover, float tilt)
        {
            color = arcColor;
            life = Mathf.Max(0.05f, lifeSeconds);
            hoverHeight = hover;
            tiltHeight = tilt;
            radius = Mathf.Max(0.2f, arcRadius);
            halfArcRadians = Mathf.Max(5f, Mathf.Min(arcDegrees, 340f)) * 0.5f * Mathf.Deg2Rad;

            forward = new Vector3(direction.x, 0f, direction.z);
            if (forward.sqrMagnitude < 1e-6f) forward = Vector3.forward;
            forward.Normalize();
            right = Vector3.Cross(Vector3.up, forward);
            if (right.sqrMagnitude < 1e-6f) right = Vector3.right;
            right.Normalize();

            // 贴地：从角色胸口往下打一条射线找地面；打不到就退回"胸口下方 1 米"。
            // 不这么做的话，坡道/台阶上的玩家会让弧片悬空或埋进地里。
            float groundY = origin.y - 1.0f;
            if (Physics.Raycast(origin + Vector3.up * 2f, Vector3.down, out RaycastHit hit, 8f,
                                ~0, QueryTriggerInteraction.Ignore))
            {
                groundY = hit.point.y;
            }

            center = new Vector3(origin.x, groundY, origin.z);

            BuildMesh();
            Apply(0f);
        }

        void BuildMesh()
        {
            int count = Segments * Rows;
            verts = new Vector3[count];
            colors = new Color32[count];
            var uvs = new Vector2[count];
            var tris = new int[(Segments - 1) * (Rows - 1) * 6];

            int v = 0;
            for (int i = 0; i < Segments; i++)
            {
                float u = Segments > 1 ? (float)i / (Segments - 1) : 0f;
                float angle = Mathf.Lerp(-halfArcRadians, halfArcRadians, u);
                float sin = Mathf.Sin(angle);
                float cos = Mathf.Cos(angle);
                Vector3 dir = new Vector3(
                    forward.x * cos + right.x * sin,
                    0f,
                    forward.z * cos + right.z * sin);

                for (int row = 0; row < Rows; row++)
                {
                    float rv = (float)row / (Rows - 1);
                    float r = Mathf.Lerp(InnerRadiusScale, 1f, rv) * radius;
                    Vector3 p = center + dir * r;
                    p.y = center.y + hoverHeight + tiltHeight * rv;
                    verts[v] = p;
                    uvs[v] = new Vector2(u, rv);
                    v++;
                }
            }

            int t = 0;
            for (int i = 0; i < Segments - 1; i++)
            {
                for (int row = 0; row < Rows - 1; row++)
                {
                    int a = i * Rows + row;
                    int b = i * Rows + row + 1;
                    int c = (i + 1) * Rows + row;
                    int d = (i + 1) * Rows + row + 1;
                    tris[t++] = a; tris[t++] = b; tris[t++] = c;
                    tris[t++] = c; tris[t++] = b; tris[t++] = d;
                }
            }

            mesh = new Mesh { name = "M_VfxGroundArc" };
            mesh.MarkDynamic();
            mesh.SetVertices(verts);
            mesh.SetUVs(0, uvs);
            mesh.SetColors(colors);
            mesh.SetTriangles(tris, 0, true);
            // 显式包围盒：动态网格不自己报 bounds 会被视锥整体剔除（`SkillVfx.cs` 记过的坑之一）。
            mesh.bounds = new Bounds(
                new Vector3(center.x, center.y + hoverHeight, center.z),
                new Vector3(radius * 2f, tiltHeight + hoverHeight + 0.2f, radius * 2f));

            var filter = gameObject.AddComponent<MeshFilter>();
            filter.sharedMesh = mesh;

            meshRenderer = gameObject.AddComponent<MeshRenderer>();
            meshRenderer.sharedMaterial = ArcMaterial();
            meshRenderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            meshRenderer.receiveShadows = false;
            meshRenderer.lightProbeUsage = UnityEngine.Rendering.LightProbeUsage.Off;
            meshRenderer.reflectionProbeUsage = UnityEngine.Rendering.ReflectionProbeUsage.Off;
            meshRenderer.sortingOrder = 28;
        }

        void Update()
        {
            age += Time.deltaTime;      // 刻意用缩放时间：顿帧时这片弧要跟着冻住
            float t = life > 0f ? age / life : 1f;
            if (t >= 1f)
            {
                Destroy(gameObject);
                return;
            }
            Apply(t);
        }

        void Apply(float t)
        {
            if (mesh == null || colors == null) return;

            float leadU = Mathf.Clamp01(t / SweepPortion);
            float fade = 1f - Mathf.Clamp01((t - SweepPortion) / Mathf.Max(0.01f, 1f - SweepPortion));
            float baseAlpha = color.a;

            int v = 0;
            for (int i = 0; i < Segments; i++)
            {
                float u = Segments > 1 ? (float)i / (Segments - 1) : 0f;

                // 前沿扫过 u 之后才点亮，越靠后越晚 —— 这就是"扫"的观感。
                float reveal = Mathf.Clamp01((leadU - u) / SweepSoftness);

                // 前沿本身加一道高亮，让"刀走到哪儿了"一眼可读。
                float hot = 1f + 0.9f * Mathf.Clamp01(1f - Mathf.Abs(u - leadU) / 0.12f);

                for (int row = 0; row < Rows; row++)
                {
                    float a = reveal * fade * hot * RowGain[row] * baseAlpha;
                    a = Mathf.Clamp01(a);
                    // 预乘：rgb 也乘 alpha，配合 Sprites/Default 的预乘混合不会出现灰边。
                    colors[v] = new Color32(
                        (byte)(Mathf.Clamp01(color.r * a) * 255f),
                        (byte)(Mathf.Clamp01(color.g * a) * 255f),
                        (byte)(Mathf.Clamp01(color.b * a) * 255f),
                        (byte)(a * 255f));
                    v++;
                }
            }

            mesh.SetColors(colors);
        }

        static Material ArcMaterial()
        {
            if (cachedMaterial != null) return cachedMaterial;

            Shader shader = Shader.Find("Sprites/Default");
            if (shader == null) shader = Shader.Find("Universal Render Pipeline/2D/Sprite-Unlit-Default");
            if (shader == null) shader = Shader.Find("Unlit/Transparent");
            if (shader == null)
            {
                Debug.LogWarning("[VfxGroundArc] 找不到可用的 Sprite shader，贴地弧光不会显示");
                return null;
            }

            cachedMaterial = new Material(shader) { name = "M_VfxGroundArc" };
            cachedMaterial.mainTexture = BandTexture();
            cachedMaterial.color = Color.white;   // 颜色活在顶点色里，材质只负责混合
            cachedMaterial.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
            return cachedMaterial;
        }

        /// <summary>
        /// 沿半径方向的软边遮罩（4×64）：中间实、内外缘软。
        /// 没有它的话扇形边界会是硬直的一条线，俯视时特别假。
        /// </summary>
        static Texture2D BandTexture()
        {
            const int W = 4, H = 64;
            var tex = new Texture2D(W, H, TextureFormat.RGBA32, false)
            {
                name = "T_VfxGroundArcBand",
                wrapMode = TextureWrapMode.Clamp,
                filterMode = FilterMode.Bilinear,
                anisoLevel = 0
            };

            var px = new Color32[W * H];
            for (int y = 0; y < H; y++)
            {
                float v = (float)y / (H - 1);
                float a = 1f;
                if (v < 0.16f) a = Mathf.Lerp(0.15f, 1f, v / 0.16f);
                else if (v > 0.82f) a = Mathf.Lerp(1f, 0.10f, (v - 0.82f) / 0.18f);
                byte b = (byte)(Mathf.Clamp01(a) * 255f);
                for (int x = 0; x < W; x++) px[y * W + x] = new Color32(255, 255, 255, b);
            }
            tex.SetPixels32(px);
            tex.Apply(false, false);
            return tex;
        }

#if UNITY_EDITOR
        /// <summary>QA：把弧光定格到指定进度（0~1），配合 `Time.timeScale = 0` 做确定性出图。</summary>
        public void DebugSetProgress(float t) { age = Mathf.Clamp01(t) * life; Apply(Mathf.Clamp01(t)); }

        public float DebugLife => life;
        public int DebugVertexCount => mesh != null ? mesh.vertexCount : 0;
        public Mesh DebugMesh => mesh;
        public static Material DebugMaterial => ArcMaterial();

        /// <summary>QA：当前顶点色里最大的 alpha（0 就说明画面里不可能有它）。</summary>
        public int DebugMaxAlpha
        {
            get
            {
                if (colors == null) return 0;
                int max = 0;
                for (int i = 0; i < colors.Length; i++) if (colors[i].a > max) max = colors[i].a;
                return max;
            }
        }
#endif

        void OnDestroy()
        {
            if (mesh != null) Destroy(mesh);
            VfxHub.NoteTransientDestroyed();
        }
    }
}
