using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace MyWorld
{
    /// <summary>
    /// 打击特效的**程序化贴图 / 材质缓存**。
    ///
    /// 为什么要自己生成：
    ///   * 工程里没有任何特效美术资源（PlaceholderArt 只有纯色块）；
    ///   * 新地图是运行时用 C# 生成的，**不能依赖旧场景里序列化的材质引用**；
    ///   * 这里所有东西都是 `Resources` 级别的运行时对象，进 Play 才会创建，随 [VfxHub] 跨场景保留。
    ///
    /// 贴图是 2 的幂、RGBA32、不写盘（避免 AssetDatabase 依赖）；材质按「贴图 + 混合模式」缓存，
    /// 每个池只拿一份，粒子颜色走 `ParticleSystem.EmitParams.startColor`，**不按粒子上色而是按粒子调色**。
    /// </summary>
    public static class VfxMaterials
    {
        static Texture2D dot;
        static Texture2D streak;
        static Texture2D ring;
        static Texture2D dust;
        static Texture2D star;
        static Texture2D rune;

        static readonly Dictionary<string, Material> cache = new Dictionary<string, Material>(16);
        static Shader particleShader;

        // ---------------- 贴图 ----------------

        /// <summary>柔和圆点（80% 粒子的基础贴图）。</summary>
        public static Texture2D Dot
        {
            get
            {
                if (dot == null) dot = MakeDot(64);
                return dot;
            }
        }

        /// <summary>拉长的火花条（配合 `ParticleSystemRenderMode.Stretch`）。</summary>
        public static Texture2D Streak
        {
            get
            {
                if (streak == null) streak = MakeStreak(32, 128);
                return streak;
            }
        }

        /// <summary>细圆环（冲击环 / 光晕）。</summary>
        public static Texture2D Ring
        {
            get
            {
                if (ring == null) ring = MakeRing(128);
                return ring;
            }
        }

        /// <summary>有噪声的尘团（尘土 / 烟）。</summary>
        public static Texture2D Dust
        {
            get
            {
                if (dust == null) dust = MakeDust(96);
                return dust;
            }
        }

        /// <summary>四芒星闪光（命中瞬间的高光 / 拾取）。</summary>
        public static Texture2D Star
        {
            get
            {
                if (star == null) star = MakeStar(128);
                return star;
            }
        }

        /// <summary>符文圆环（法杖施法阵列 / 魔法阵）。</summary>
        public static Texture2D Rune
        {
            get
            {
                if (rune == null) rune = MakeRune(256);
                return rune;
            }
        }

        // ---------------- 材质 ----------------

        /// <summary>
        /// 粒子材质（URP Particles/Unlit；取不到时回退到工程里已验证可用的 Unlit 自发光材质）。
        /// additive=true 走「SrcAlpha / One」叠加，适合火花；false 走常规透明，适合尘土。
        /// </summary>
        public static Material GetParticleMaterial(Texture2D texture, bool additive)
        {
            if (texture == null) texture = Dot;
            string key = "vfx_" + texture.GetInstanceID() + (additive ? "_add" : "_alpha");
            Material m;
            if (cache.TryGetValue(key, out m) && m != null) return m;

            m = TryBuildParticleMaterial(texture, additive);
            if (m == null)
            {
                // 兜底：PlaceholderArt 的 Unlit 自发光（颜色靠粒子 startColor 会失效，但至少有东西渲染）
                m = PlaceholderArt.GetGlowMaterial();
            }
            m.name = "M_Vfx_" + texture.name + (additive ? "_Add" : "_Alpha");
            cache[key] = m;
            return m;
        }

        static Material TryBuildParticleMaterial(Texture2D texture, bool additive)
        {
            Shader sh = FindParticleShader();
            if (sh == null) return null;

            var m = new Material(sh);
            if (m.HasProperty("_BaseMap")) m.SetTexture("_BaseMap", texture);
            if (m.HasProperty("_MainTex")) m.SetTexture("_MainTex", texture);
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", Color.white);
            if (m.HasProperty("_Color")) m.SetColor("_Color", Color.white);
            if (m.HasProperty("_Cutoff")) m.SetFloat("_Cutoff", 0f);

            // 透明 + 混合模式：URP 的 shader GUI 改的就是这几个属性
            if (m.HasProperty("_Surface")) m.SetFloat("_Surface", 1f);          // 1 = Transparent
            if (m.HasProperty("_Blend")) m.SetFloat("_Blend", additive ? 2f : 0f); // 2 = Additive, 0 = Alpha
            if (m.HasProperty("_SrcBlend")) m.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha);
            if (m.HasProperty("_DstBlend"))
                m.SetFloat("_DstBlend", additive ? (float)BlendMode.One : (float)BlendMode.OneMinusSrcAlpha);
            if (m.HasProperty("_ZWrite")) m.SetFloat("_ZWrite", 0f);
            if (m.HasProperty("_Cull")) m.SetFloat("_Cull", (float)CullMode.Off);
            if (m.HasProperty("_AlphaClip")) m.SetFloat("_AlphaClip", 0f);

            m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            if (additive) m.EnableKeyword("_ALPHAMODULATE_ON");
            m.SetOverrideTag("RenderType", "Transparent");
            m.renderQueue = (int)RenderQueue.Transparent;
            return m;
        }

        static Shader FindParticleShader()
        {
            if (particleShader != null) return particleShader;
            particleShader = Shader.Find("Universal Render Pipeline/Particles/Unlit");
            if (particleShader == null) particleShader = Shader.Find("Particles/Standard Unlit");
            if (particleShader == null) particleShader = Shader.Find("Sprites/Default");
            return particleShader;
        }

        // ---------------- 贴图生成 ----------------

        static Texture2D NewTex(int w, int h, string name)
        {
            var t = new Texture2D(w, h, TextureFormat.RGBA32, false, true);
            t.name = name;
            t.wrapMode = TextureWrapMode.Clamp;
            t.filterMode = FilterMode.Bilinear;
            return t;
        }

        static Texture2D MakeDot(int size)
        {
            var t = NewTex(size, size, "T_VfxDot");
            var px = new Color[size * size];
            float half = size * 0.5f;
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float dx = (x + 0.5f - half) / half;
                    float dy = (y + 0.5f - half) / half;
                    float r = Mathf.Sqrt(dx * dx + dy * dy);
                    float a = Mathf.Clamp01(1f - r);
                    a = a * a * (3f - 2f * a);       // smoothstep
                    a = Mathf.Pow(a, 1.6f);
                    px[y * size + x] = new Color(1f, 1f, 1f, a);
                }
            }
            t.SetPixels(px);
            t.Apply(false, false);
            return t;
        }

        static Texture2D MakeStreak(int w, int h)
        {
            var t = NewTex(w, h, "T_VfxStreak");
            var px = new Color[w * h];
            float cx = w * 0.5f, ch = h * 0.5f;
            for (int y = 0; y < h; y++)
            {
                float u = (y + 0.5f - ch) / ch;                 // -1..1 沿线
                float along = Mathf.Clamp01(1f - Mathf.Abs(u));
                along = Mathf.Pow(along, 1.3f);
                for (int x = 0; x < w; x++)
                {
                    float ax = Mathf.Abs(x + 0.5f - cx) / cx;
                    float across = Mathf.Clamp01(1f - ax);
                    across = Mathf.Pow(across, 2.2f);
                    px[y * w + x] = new Color(1f, 1f, 1f, along * across);
                }
            }
            t.SetPixels(px);
            t.Apply(false, false);
            return t;
        }

        static Texture2D MakeRing(int size)
        {
            var t = NewTex(size, size, "T_VfxRing");
            var px = new Color[size * size];
            float half = size * 0.5f;
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float dx = (x + 0.5f - half) / half;
                    float dy = (y + 0.5f - half) / half;
                    float r = Mathf.Sqrt(dx * dx + dy * dy);
                    float a = Mathf.Exp(-Mathf.Pow((r - 0.78f) / 0.075f, 2f));
                    a += 0.25f * Mathf.Exp(-Mathf.Pow((r - 0.62f) / 0.22f, 2f));
                    px[y * size + x] = new Color(1f, 1f, 1f, Mathf.Clamp01(a));
                }
            }
            t.SetPixels(px);
            t.Apply(false, false);
            return t;
        }

        static Texture2D MakeDust(int size)
        {
            var t = NewTex(size, size, "T_VfxDust");
            var px = new Color[size * size];
            float half = size * 0.5f;
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float dx = (x + 0.5f - half) / half;
                    float dy = (y + 0.5f - half) / half;
                    float r = Mathf.Sqrt(dx * dx + dy * dy);
                    float soft = Mathf.Clamp01(1f - r);
                    soft = soft * soft;
                    // 便宜的"云"噪声：几个正弦叠加（确定性，不用 Random）
                    float n = 0.55f + 0.45f * Mathf.Sin(dx * 9.1f + dy * 3.7f) * Mathf.Sin(dy * 8.3f - dx * 2.9f);
                    px[y * size + x] = new Color(1f, 1f, 1f, Mathf.Clamp01(soft * n));
                }
            }
            t.SetPixels(px);
            t.Apply(false, false);
            return t;
        }

        static Texture2D MakeStar(int size)
        {
            var t = NewTex(size, size, "T_VfxStar");
            var px = new Color[size * size];
            float half = size * 0.5f;
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float dx = (x + 0.5f - half) / half;
                    float dy = (y + 0.5f - half) / half;
                    float r = Mathf.Sqrt(dx * dx + dy * dy);
                    float core = Mathf.Exp(-r * r / 0.035f);
                    float flareX = Mathf.Exp(-Mathf.Abs(dx) * 9f) * Mathf.Clamp01(1f - Mathf.Abs(dy) * 1.15f);
                    float flareY = Mathf.Exp(-Mathf.Abs(dy) * 9f) * Mathf.Clamp01(1f - Mathf.Abs(dx) * 1.15f);
                    float a = Mathf.Clamp01(core + 0.55f * (flareX + flareY));
                    px[y * size + x] = new Color(1f, 1f, 1f, a);
                }
            }
            t.SetPixels(px);
            t.Apply(false, false);
            return t;
        }

        static Texture2D MakeRune(int size)
        {
            var t = NewTex(size, size, "T_VfxRune");
            var px = new Color[size * size];
            float half = size * 0.5f;
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float dx = (x + 0.5f - half) / half;
                    float dy = (y + 0.5f - half) / half;
                    float r = Mathf.Sqrt(dx * dx + dy * dy);
                    float ang = Mathf.Atan2(dy, dx);
                    float a = 0f;
                    // 外环 / 内环
                    a += Mathf.Exp(-Mathf.Pow((r - 0.90f) / 0.030f, 2f));
                    a += 0.75f * Mathf.Exp(-Mathf.Pow((r - 0.74f) / 0.022f, 2f));
                    a += 0.55f * Mathf.Exp(-Mathf.Pow((r - 0.40f) / 0.020f, 2f));
                    // 12 条刻度
                    float tick = Mathf.Abs(Mathf.Sin(ang * 6f));
                    if (r > 0.40f && r < 0.74f) a += 0.55f * Mathf.Pow(tick, 18f) * Mathf.Clamp01((r - 0.40f) * 6f);
                    // 内圈 6 个"符文点"
                    float runes = Mathf.Abs(Mathf.Cos(ang * 3f));
                    if (r > 0.52f && r < 0.66f) a += 0.5f * Mathf.Pow(runes, 34f);
                    // 中心微光
                    a += 0.35f * Mathf.Exp(-r * r / 0.02f);
                    px[y * size + x] = new Color(1f, 1f, 1f, Mathf.Clamp01(a));
                }
            }
            t.SetPixels(px);
            t.Apply(false, false);
            return t;
        }

        /// <summary>进 Play 前清掉缓存（编辑器里改贴图参数时用；正常流程不需要调用）。</summary>
        public static void ClearCache()
        {
            cache.Clear();
        }
    }
}
