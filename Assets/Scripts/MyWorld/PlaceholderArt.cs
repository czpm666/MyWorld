using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace MyWorld
{
    /// <summary>
    /// 占位美术：全部用 Unity 内置图元 + 运行时生成的材质/贴图拼出来，不依赖任何美术资源。
    /// 等真正的模型和贴图到位后，替换这里的生成逻辑即可，上层（世界搭建、玩家、相机）不用动。
    /// </summary>
    public static class PlaceholderArt
    {
        private static Shader litShader;

        private static Shader LitShader
        {
            get
            {
                if (litShader == null)
                {
                    litShader = Shader.Find("Universal Render Pipeline/Lit");
                    if (litShader == null) litShader = Shader.Find("Standard");
                }
                return litShader;
            }
        }

        private static Material _glowMat;
        private static readonly Dictionary<Color, Material> glowCache = new Dictionary<Color, Material>();

        /// <summary>默认的青色奥术发光材质。</summary>
        public static Material GetGlowMaterial()
        {
            return GetGlowMaterial(new Color(0.55f, 0.85f, 1f, 1f));
        }

        /// <summary>
        /// 按颜色取自发光材质，**同一颜色共用一份**（按颜色缓存）。
        /// 不缓存的话每次命中都要 new 一个材质，打一会儿就泄漏一堆。
        /// </summary>
        public static Material GetGlowMaterial(Color color)
        {
            if (glowCache.TryGetValue(color, out var cached) && cached != null) return cached;

            var shader = Shader.Find("Universal Render Pipeline/Unlit");
            if (shader == null) shader = Shader.Find("Unlit/Color");

            var m = new Material(shader) { name = "M_Glow_" + ColorUtility.ToHtmlStringRGB(color) };
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", color);
            m.color = color;
            glowCache[color] = m;
            return m;
        }

        private static Material _vertexColorMat;

        /// <summary>
        /// 支持**顶点色**的材质，给 LineRenderer 做渐变/粗细变化用。
        /// 普通 Unlit 不吃顶点色，LineRenderer 的 colorGradient 会失效；
        /// 用 Sprites/Default 才能让每条线的颜色渐变生效。
        /// </summary>
        public static Material GetVertexColorMaterial()
        {
            if (_vertexColorMat != null) return _vertexColorMat;

            var shader = Shader.Find("Sprites/Default");
            if (shader == null) shader = Shader.Find("Universal Render Pipeline/2D/Sprite-Unlit-Default");
            if (shader == null) shader = Shader.Find("Unlit/Color");

            _vertexColorMat = new Material(shader) { name = "M_VertexColor", color = Color.white };

            // 必须给 _MainTex 一张白图！
            // Sprites/Default 会采样 _MainTex，且用的是预乘混合 Blend One OneMinusSrcAlpha。
            // 不给贴图时采到的是空纹理(≈0)，结果就是 0 + 背景×(1-0) = 背景 —— 整个网格"完全看不见"。
            var white = new Texture2D(1, 1, TextureFormat.RGBA32, false);
            white.SetPixel(0, 0, Color.white);
            white.Apply();
            white.name = "T_White";
            _vertexColorMat.mainTexture = white;
            if (_vertexColorMat.HasProperty("_BaseMap")) _vertexColorMat.SetTexture("_BaseMap", white);

            return _vertexColorMat;
        }

        /// <summary>给 LineRenderer 用的纯色材质（Unlit，不受光照影响）。</summary>
        public static Material NewColoredMaterial(Color color)
        {
            var shader = Shader.Find("Universal Render Pipeline/Unlit");
            if (shader == null) shader = Shader.Find("Unlit/Color");

            var m = new Material(shader) { name = "M_Line" };
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", color);
            m.color = color;
            return m;
        }

        /// <summary>新建一个 URP/Lit 不透明材质。</summary>
        public static Material NewLit(Color color, float smoothness = 0.06f, float metallic = 0f)
        {
            var m = new Material(LitShader);
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", color);
            m.color = color;
            if (m.HasProperty("_Smoothness")) m.SetFloat("_Smoothness", smoothness);
            if (m.HasProperty("_Metallic")) m.SetFloat("_Metallic", metallic);
            return m;
        }

        /// <summary>带网格贴图的地面材质。tiling 是贴图在地面上重复的次数。</summary>
        public static Material NewGridMaterial(Color bg, Color line, float tiling)
        {
            var m = NewLit(Color.white, 0.03f);
            var tex = NewGridTexture(256, 8, bg, line);
            var scale = new Vector2(tiling, tiling);
            if (m.HasProperty("_BaseMap"))
            {
                m.SetTexture("_BaseMap", tex);
                m.SetTextureScale("_BaseMap", scale);
            }
            m.mainTexture = tex;
            m.mainTextureScale = scale;
            // 着色靠贴图本身，基色保持白色，免得把贴图颜色再乘一遍变暗。
            m.color = Color.white;
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", Color.white);
            return m;
        }

        /// <summary>
        /// 生成一张方格贴图，给俯视视角提供运动参照（没有参照物时人会感觉不到自己在走）。
        /// </summary>
        public static Texture2D NewGridTexture(int size, int cells, Color bg, Color line)
        {
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, true)
            {
                wrapMode = TextureWrapMode.Repeat,
                filterMode = FilterMode.Bilinear,
                anisoLevel = 4,
                name = "PlaceholderGrid"
            };

            float pxPerCell = (float)size / cells;
            var px = new Color[size * size];
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float fx = Mathf.Repeat(x + 0.5f, pxPerCell);
                    float fy = Mathf.Repeat(y + 0.5f, pxPerCell);
                    px[y * size + x] = (fx < 1f || fy < 1f) ? line : bg;
                }
            }
            tex.SetPixels(px);
            tex.Apply();
            return tex;
        }

        /// <summary>
        /// 由不透明材质复制出一份半透明版本，用于"挡住玩家时淡出"。
        /// URP/Lit 要真正变透明需要成套地改 _Surface/_Blend/混合因子/关键字，缺一项就会渲染成黑块或不透明。
        /// </summary>
        public static Material NewTransparentVariant(Material src, float alpha)
        {
            var m = new Material(src);
            m.SetOverrideTag("RenderType", "Transparent");
            if (m.HasProperty("_Surface")) m.SetFloat("_Surface", 1f);   // 0=Opaque, 1=Transparent
            if (m.HasProperty("_Blend")) m.SetFloat("_Blend", 0f);       // 0=Alpha
            if (m.HasProperty("_AlphaClip")) m.SetFloat("_AlphaClip", 0f);
            if (m.HasProperty("_SrcBlend")) m.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha);
            if (m.HasProperty("_DstBlend")) m.SetFloat("_DstBlend", (float)BlendMode.OneMinusSrcAlpha);
            if (m.HasProperty("_ZWrite")) m.SetFloat("_ZWrite", 0f);
            m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            m.DisableKeyword("_ALPHATEST_ON");
            m.renderQueue = (int)RenderQueue.Transparent;

            Color c = m.HasProperty("_BaseColor") ? m.GetColor("_BaseColor") : Color.white;
            c.a = alpha;
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
            m.color = c;
            return m;
        }

        /// <summary>生成一个图元并套上材质。图元自带碰撞体，需要无碰撞体时自行 Destroy。</summary>
        public static GameObject Primitive(
            PrimitiveType type, Transform parent, string name,
            Vector3 position, Vector3 scale, Material mat)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = position;
            go.transform.localScale = scale;
            go.transform.localRotation = Quaternion.identity;

            if (mat != null)
            {
                var r = go.GetComponent<Renderer>();
                if (r != null) r.sharedMaterial = mat;
            }
            return go;
        }

        /// <summary>去掉图元自带的碰撞体（用于纯装饰或由 CharacterController 接管的角色）。</summary>
        public static void StripCollider(GameObject go)
        {
            var c = go.GetComponent<Collider>();
            if (c == null) return;

            // 先 enabled=false：Destroy 要到帧末才真正移除，中间那一帧残留的碰撞体
            // 和 CharacterController 完全重叠，会让角色第一帧动不了。
            c.enabled = false;
            if (Application.isPlaying) Object.Destroy(c);
            else Object.DestroyImmediate(c);   // 编辑期 Destroy 不生效且会报错
        }

        /// <summary>给物体挂上可淡出组件，返回它。</summary>
        public static FadeableObject MakeFadeable(GameObject go, float fadedAlpha = 0.25f)
        {
            var f = go.GetComponent<FadeableObject>();
            if (f == null) f = go.AddComponent<FadeableObject>();
            f.Configure(fadedAlpha);
            return f;
        }
    }
}
