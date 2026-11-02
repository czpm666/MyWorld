using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace MyWorld
{
    /// <summary>
    /// 地图材质库（运行期程序化生成，不依赖任何磁盘资产）。
    /// 新地图是运行时 C# 生成的，所以所有材质都从这里按名字取；
    /// 缓存保证同一名字只建一次，避免每次生成都新建材质造成内存泄漏。
    /// 颜色统一走中世纪色板（羊皮纸、赤陶屋顶、深色木筋、黄铜、布幔）。
    ///
    /// 2026-10 贴图化：具名材质（Get("plaster_warm") 这类）从纯色升级为
    /// URP/Lit + `Assets/Art/Textures/kit_*.jpg`。做法是**用原调色板色乘贴图**：
    /// 先把贴图的平均色归一化掉，再把 `_BaseColor` 调成"贴图均值 × 调色板色"，
    /// 于是整体色调/明度仍是原来的设计色板，只是多了瓦缝、石缝、抹灰颗粒。
    /// 贴图只在编辑器里通过 AssetDatabase 取；打包后的纯运行时建图会退回纯色，
    /// 但烘焙进 .unity 的材质本身带贴图引用（MapSceneBaker 保存的是真实引用）。
    /// </summary>
    public static class MapMaterials
    {
        // ---------- 玩家可用的调色板（外部可直接引用） ----------
        public static readonly Color PlasterWarm   = Hex("#D9C7A3");
        public static readonly Color PlasterCream  = Hex("#E8DCC0");
        public static readonly Color PlasterOchre  = Hex("#C9A66B");
        public static readonly Color PlasterGrey   = Hex("#C4BCAE");
        public static readonly Color PlasterSalmon = Hex("#D8A98A");
        public static readonly Color PlasterWhite  = Hex("#EFE8D8");

        public static readonly Color TimberDark    = Hex("#4A3020");
        public static readonly Color TimberMid     = Hex("#6B4A2E");
        public static readonly Color TimberLight   = Hex("#8B643D");

        public static readonly Color RoofTerracotta = Hex("#A34A2A");
        public static readonly Color RoofSlate      = Hex("#4A5A66");
        public static readonly Color RoofTeal       = Hex("#2F6B63");
        public static readonly Color RoofBurgundy   = Hex("#7A2E2E");
        public static readonly Color RoofThatch     = Hex("#B08A4A");
        public static readonly Color RoofBlue       = Hex("#3E5C8A");

        public static readonly Color StoneWall     = Hex("#B8A88F");
        public static readonly Color StoneDark     = Hex("#6E6A63");
        public static readonly Color StoneLight    = Hex("#D5CCBB");
        public static readonly Color Cobble        = Hex("#9C9488");
        public static readonly Color Brick         = Hex("#9A5B44");
        public static readonly Color Marble        = Hex("#E6E0D2");

        public static readonly Color WoodPlank     = Hex("#8A643C");
        public static readonly Color WoodDark      = Hex("#3F2A1B");
        public static readonly Color WoodBarrel    = Hex("#7A5230");
        public static readonly Color WoodLight     = Hex("#B08954");

        public static readonly Color IronDark      = Hex("#33363B");
        public static readonly Color IronGrey      = Hex("#5A5F66");
        public static readonly Color Steel         = Hex("#C8CDD4");
        public static readonly Color Gold           = Hex("#D4AF37");
        public static readonly Color Bronze        = Hex("#A9713D");
        public static readonly Color Copper        = Hex("#B87333");

        public static readonly Color ClothRed      = Hex("#A3262B");
        public static readonly Color ClothBlue     = Hex("#2E4A8A");
        public static readonly Color ClothGreen    = Hex("#3F6B3A");
        public static readonly Color ClothPurple   = Hex("#5B3A7A");
        public static readonly Color ClothCream    = Hex("#E8DCC0");
        public static readonly Color ClothTeal     = Hex("#2E7D74");
        public static readonly Color ClothOrange   = Hex("#C06A2A");

        public static readonly Color Grass          = Hex("#5A7A3F");
        public static readonly Color GrassDark      = Hex("#466132");
        public static readonly Color GrassDry       = Hex("#8A8A4A");
        public static readonly Color FoliageGreen  = Hex("#3F6B3F");
        public static readonly Color FoliageDark   = Hex("#2E5232");
        public static readonly Color FoliageAutumn = Hex("#B5762A");
        public static readonly Color Dirt           = Hex("#6B5740");
        public static readonly Color DirtDark       = Hex("#4F4130");
        public static readonly Color Sand           = Hex("#C9B58A");
        public static readonly Color Water          = Hex("#3A6B8A");
        public static readonly Color WaterDeep      = Hex("#26506B");

        public static readonly Color GlowAmber     = Hex("#FFB347");
        public static readonly Color GlowWarm      = Hex("#FFD9A0");
        public static readonly Color GlowCyan      = Hex("#7FE8F0");
        public static readonly Color GlowViolet    = Hex("#B07FE8");
        public static readonly Color GlowGold      = Hex("#FFD24A");

        static readonly Dictionary<string, Material> Cache = new Dictionary<string, Material>(128);
        static readonly Dictionary<string, Texture2D> BumpCache = new Dictionary<string, Texture2D>(16);
        static Shader _lit;
        static Shader _unlit;
        static Shader _tri;

        /// <summary>已建材质数量（只读，给编辑器自检/预览用）。</summary>
        public static int CacheCount { get { return Cache.Count; } }

        // ---------- 贴图表 ----------
        // MeanLinear = 整张贴图在**线性空间**的平均色（离线统计，见 CREDITS.md）。
        // 用它把贴图归一化到"平均 1.0"，再乘调色板色，贴图明暗对比就完整保留。
        // Exposure = 额外的曝光补偿：深色贴图（粗石墙、茅草）提亮后高光容易过曝，
        // 给 0.7~0.9 压一点；亮贴图（抹灰、木板）给 1.0。
        sealed class TexDef
        {
            public string Path;
            public Color MeanLinear;
            public float Exposure;
        }

        static readonly Dictionary<string, TexDef> Textures = new Dictionary<string, TexDef>(16)
        {
            { "cobble",
              new TexDef { Path = "Assets/Art/Textures/kit_cobble.jpg",    MeanLinear = new Color(0.2044f, 0.1679f, 0.1118f), Exposure = 0.92f } },
            { "stone_wall",
              new TexDef { Path = "Assets/Art/Textures/kit_stone_wall.jpg", MeanLinear = new Color(0.1092f, 0.0746f, 0.0428f), Exposure = 0.72f } },
            { "blocks",
              new TexDef { Path = "Assets/Art/Textures/kit_blocks.jpg",     MeanLinear = new Color(0.1850f, 0.1455f, 0.0980f), Exposure = 0.95f } },
            { "roof_tile",
              new TexDef { Path = "Assets/Art/Textures/kit_roof_tile.jpg",  MeanLinear = new Color(0.2423f, 0.1048f, 0.0599f), Exposure = 0.95f } },
            { "plaster",
              new TexDef { Path = "Assets/Art/Textures/kit_plaster.jpg",    MeanLinear = new Color(0.5217f, 0.5158f, 0.4718f), Exposure = 1.00f } },
            { "planks",
              new TexDef { Path = "Assets/Art/Textures/kit_planks.jpg",     MeanLinear = new Color(0.4961f, 0.3238f, 0.1451f), Exposure = 0.92f } },
            { "thatch",
              new TexDef { Path = "Assets/Art/Textures/kit_thatch.jpg",     MeanLinear = new Color(0.0899f, 0.0804f, 0.0673f), Exposure = 0.88f } },
            { "barrel",
              new TexDef { Path = "Assets/Art/Textures/kit_barrel.jpg",     MeanLinear = new Color(0.0533f, 0.0339f, 0.0249f), Exposure = 0.90f } },
            { "grass",
              new TexDef { Path = "Assets/Art/Textures/kit_grass.jpg",      MeanLinear = new Color(0.0582f, 0.1061f, 0.0216f), Exposure = 1.00f } },
            { "dirt",
              new TexDef { Path = "Assets/Art/Textures/kit_dirt.jpg",       MeanLinear = new Color(0.1322f, 0.1081f, 0.0825f), Exposure = 0.95f } },
            { "sand",
              new TexDef { Path = "Assets/Art/Textures/kit_sand.jpg",       MeanLinear = new Color(0.2881f, 0.1905f, 0.1257f), Exposure = 0.95f } },
            { "brick",
              new TexDef { Path = "Assets/Art/Textures/kit_brick.jpg",      MeanLinear = new Color(0.1850f, 0.0816f, 0.0391f), Exposure = 0.90f } },
            { "wood_dark",
              new TexDef { Path = "Assets/Art/Textures/kit_wood_dark.jpg",  MeanLinear = new Color(0.1769f, 0.1419f, 0.1116f), Exposure = 1.00f } },
        };

        static readonly Dictionary<string, Texture2D> TexCache = new Dictionary<string, Texture2D>(16);

        // ---------- 按名字取“标准色板”材质 ----------
        public static Material Get(string key)
        {
            if (string.IsNullOrEmpty(key)) key = "stone_wall";
            Material m;
            if (Cache.TryGetValue(key, out m) && m != null) return m;
            m = BuildNamed(key);
            Cache[key] = m;
            return m;
        }

        // ---------- 自定义纯色材质（会被缓存，key 建议带色值） ----------
        public static Material Solid(string key, Color color, float smoothness = 0.18f, float metallic = 0f)
        {
            Material m;
            if (Cache.TryGetValue(key, out m) && m != null) return m;
            m = NewLit();
            SetColor(m, color);
            SetFloat(m, "_Smoothness", smoothness);
            SetFloat(m, "_Metallic", metallic);
            m.name = "MapMat_" + key;
            Cache[key] = m;
            return m;
        }

        /// <summary>自发光材质（灯、魔法符文、传送门、熔炉）。</summary>
        public static Material Emissive(string key, Color color, float intensity = 1.6f)
        {
            Material m;
            if (Cache.TryGetValue(key, out m) && m != null) return m;
            m = NewLit();
            SetColor(m, color);
            SetFloat(m, "_Smoothness", 0.4f);
            var lit = new Color(color.r * intensity, color.g * intensity, color.b * intensity, 1f);
            if (m.HasProperty("_EmissionColor"))
            {
                m.SetColor("_EmissionColor", lit);
                m.EnableKeyword("_EMISSION");
                m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
            }
            m.name = "MapMatEmi_" + key;
            Cache[key] = m;
            return m;
        }

        /// <summary>半透明材质（水面、玻璃、魔法屏障、雾）。</summary>
        public static Material Transparent(string key, Color color, float alpha = 0.6f, float smoothness = 0.6f)
        {
            Material m;
            if (Cache.TryGetValue(key, out m) && m != null) return m;
            m = NewLit();
            color.a = alpha;
            SetColor(m, color);
            SetFloat(m, "_Smoothness", smoothness);
            SetupTransparent(m);
            m.name = "MapMatTr_" + key;
            Cache[key] = m;
            return m;
        }

        /// <summary>无光照纯色（布幔、旗面、贴花、UI 世界文字底板）。</summary>
        public static Material Unlit(string key, Color color)
        {
            Material m;
            if (Cache.TryGetValue(key, out m) && m != null) return m;
            m = new Material(UnlitShader()) { name = "MapMatUnlit_" + key };
            SetColor(m, color);
            Cache[key] = m;
            return m;
        }

        /// <summary>运行时改色（只对自己新建的材质用，别改共享缓存，除非有意）。</summary>
        public static void SetColor(Material m, Color c)
        {
            if (m == null) return;
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
            if (m.HasProperty("_Color")) m.SetColor("_Color", c);
        }

        static void SetFloat(Material m, string prop, float v)
        {
            if (m != null && m.HasProperty(prop)) m.SetFloat(prop, v);
        }

        static void SetupTransparent(Material m)
        {
            SetFloat(m, "_Surface", 1f);      // URP: 1 = Transparent
            SetFloat(m, "_Blend", 0f);        // URP: 0 = Alpha
            SetFloat(m, "_ZWrite", 0f);
            SetFloat(m, "_SrcBlend", (float)BlendMode.SrcAlpha);
            SetFloat(m, "_DstBlend", (float)BlendMode.OneMinusSrcAlpha);
            m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            m.DisableKeyword("_ALPHATEST_ON");
            m.renderQueue = (int)RenderQueue.Transparent;
        }

        static Material NewLit()
        {
            return new Material(LitShader());
        }

        static Shader LitShader()
        {
            if (_lit == null)
            {
                _lit = Shader.Find("Universal Render Pipeline/Lit");
                if (_lit == null) _lit = Shader.Find("Universal Render Pipeline/Simple Lit");
                if (_lit == null) _lit = Shader.Find("Standard");
                if (_lit == null) _lit = Shader.Find("Legacy Shaders/Diffuse");
            }
            return _lit;
        }

        static Shader UnlitShader()
        {
            if (_unlit == null)
            {
                _unlit = Shader.Find("Universal Render Pipeline/Unlit");
                if (_unlit == null) _unlit = Shader.Find("Unlit/Color");
                if (_unlit == null) _unlit = LitShader();
            }
            return _unlit;
        }

        // ---------- 具名材质表（地图生成器用 MapMaterials.Get("roof_teal") 这种名字） ----------
        //
        // 贴图 tiling = 每个 UV 单位里重复几次。地图里有两套 UV 空间，必须分开给：
        //   • 米制 UV：Kit.Slab / Kit.Mesh / Kit.GableRoofMesh / Kit.PyramidRoofMesh /
        //     RoaKit.FloorDisc —— 1 个 UV 单位 = 1 米。屋顶 0.55 ≈ 1.8 米一循环；
        //     地面石板 1.0 ≈ 1 米一循环；土路 1.0。
        //   • 0..1 UV：Kit.Box / Kit.BoxRot / Kit.Cyl / GameObject.CreatePrimitive（Cube）
        //     —— 整面墙只有一个 UV 单位，只能按"典型构件尺寸"取折中值。
        //     墙面 1.5（6 米墙 ≈ 4 米一循环）、木构件 3.0、粗石墙 5.0、铺装 10.0。
        // 已知代价：共用 0..1 UV 材质、但尺寸差很远的物件（罗亚市 6×76 的巷道、
        // 92×6 的集市巷、20×73 的主街；学园 20×12 的建筑主体）会看到明显各向异性拉伸。
        // 要彻底修，得把这些盒子改成 Kit.Slab（米制 UV），那属于地图脚本，不在本次修改范围。
        // 亮石材（stone_light / 抹灰）在 1.2~1.4 的日光下会被冲成白纸，Textured() 的
        // exposure 参数负责把 albedo 压到 0.3~0.45，石缝/砖缝才留得住（见各 case）。
        static Material BuildNamed(string key)
        {
            switch (key)
            {
                // 墙面：抹灰颗粒，tiling 按 4~8 米的盒子墙折中
                case "plaster_warm":   return Textured("plaster_warm",   "plaster", PlasterWarm,   1.5f, 0.10f, 0f, 0.80f);
                case "plaster_cream":  return Textured("plaster_cream",  "plaster", PlasterCream,  1.5f, 0.10f, 0f, 0.80f);
                case "plaster_ochre":  return Textured("plaster_ochre",  "plaster", PlasterOchre,  1.5f, 0.10f, 0f, 0.80f);
                case "plaster_grey":   return Textured("plaster_grey",   "plaster", PlasterGrey,   1.5f, 0.10f, 0f, 0.80f);
                case "plaster_salmon": return Textured("plaster_salmon", "plaster", PlasterSalmon, 1.5f, 0.10f, 0f, 0.80f);
                case "plaster_white":  return Textured("plaster_white",  "plaster", PlasterWhite,  1.5f, 0.10f, 0f, 0.80f);
                // 木筋：木板纹理
                case "timber_dark":    return Textured("timber_dark",  "wood_dark", TimberDark,  3.0f, 0.1f);
                case "timber_mid":     return Textured("timber_mid",   "planks",    TimberMid,   3.0f, 0.1f);
                case "timber_light":   return Textured("timber_light", "planks",    TimberLight, 3.0f, 0.1f);
                // 屋顶：米制 UV，瓦片 1.8 米一循环（缝清楚又不过密）；茅草更疏
                case "roof_terracotta": return Textured("roof_terracotta", "roof_tile", RoofTerracotta, 0.55f, 0.14f);
                case "roof_slate":      return Textured("roof_slate",      "roof_tile", RoofSlate,      0.55f, 0.18f);
                case "roof_teal":       return Textured("roof_teal",       "roof_tile", RoofTeal,       0.55f, 0.14f);
                case "roof_burgundy":   return Textured("roof_burgundy",   "roof_tile", RoofBurgundy,   0.55f, 0.14f);
                case "roof_thatch":     return Textured("roof_thatch",     "thatch",    RoofThatch,     0.70f, 0.06f);
                case "roof_blue":       return Textured("roof_blue",       "roof_tile", RoofBlue,       0.55f, 0.14f);
                // 石：粗石墙走碎石纹理；方石用于台基/柱础/广场石板
                // stone_wall 同时用于 0..1 UV 的 6m 铺装 / 1.7m 扶壁，以及米制 UV 的 92m 长街
                // （铺装合批后 92 UV 铺 168m），5.0 偏向大石板；小块构件纹理会偏大，属已知折中
                case "stone_wall":  return Textured("stone_wall",  "stone_wall", StoneWall,  5.0f, 0.10f);
                case "stone_dark":  return Textured("stone_dark",  "blocks",     StoneDark,  1.4f, 0.14f);
                case "stone_light": return Textured("stone_light", "blocks",     StoneLight, 2.0f, 0.10f, 0f, 0.52f);
                case "cobble":      return Textured("cobble",      "cobble",     Cobble,     10.0f, 0.12f, 0f, 0.95f);
                case "brick":       return Textured("brick",       "brick",      Brick,      6.0f, 0.12f);
                case "marble":      return Solid("marble", Marble, 0.35f);   // 没有大理石贴图，保持纯色
                // 木
                case "wood_plank":  return Textured("wood_plank",  "planks",    WoodPlank,  3.0f, 0.12f);
                case "wood_dark":   return Textured("wood_dark",   "wood_dark", WoodDark,   3.0f, 0.12f);
                case "wood_barrel": return Textured("wood_barrel", "barrel",    WoodBarrel, 1.2f, 0.15f);
                case "wood_light":  return Textured("wood_light",  "planks",    WoodLight,  3.0f, 0.15f);
                // 金属
                case "iron":    return Solid("iron", IronDark, 0.45f, 0.85f);
                case "iron_grey": return Solid("iron_grey", IronGrey, 0.4f, 0.8f);
                case "steel":   return Solid("steel", Steel, 0.55f, 0.9f);
                case "gold":    return Solid("gold", Gold, 0.6f, 0.9f);
                case "bronze":  return Solid("bronze", Bronze, 0.5f, 0.85f);
                case "copper":  return Solid("copper", Copper, 0.5f, 0.85f);
                // 布
                case "cloth_red":    return Solid("cloth_red", ClothRed, 0.05f);
                case "cloth_blue":   return Solid("cloth_blue", ClothBlue, 0.05f);
                case "cloth_green":  return Solid("cloth_green", ClothGreen, 0.05f);
                case "cloth_purple": return Solid("cloth_purple", ClothPurple, 0.05f);
                case "cloth_cream":  return Solid("cloth_cream", ClothCream, 0.05f);
                case "cloth_teal":   return Solid("cloth_teal", ClothTeal, 0.05f);
                case "cloth_orange": return Solid("cloth_orange", ClothOrange, 0.05f);
                // 自然：草地 24 次/UV（120 米地面 ≈ 5 米一循环）；土/沙是米制路网，1 次/米
                case "grass":         return Textured("grass",     "grass", Grass,     24.0f, 0.05f);
                case "grass_dark":    return Textured("grass_dark","grass", GrassDark, 2.0f, 0.05f);
                case "grass_dry":     return Textured("grass_dry", "grass", GrassDry,  2.0f, 0.05f);
                case "foliage":       return Solid("foliage", FoliageGreen, 0.08f);
                case "foliage_dark":  return Solid("foliage_dark", FoliageDark, 0.08f);
                case "foliage_autumn": return Solid("foliage_autumn", FoliageAutumn, 0.08f);
                case "dirt":          return Textured("dirt",      "dirt", Dirt,     1.0f, 0.05f);
                case "dirt_dark":     return Textured("dirt_dark", "dirt", DirtDark, 1.0f, 0.05f);
                // 乡道不必和翻过的裸土一样深：真实土路是被踩实的浅灰黄，比田土亮一档。
                // 原来直接用 dirt(#6B5740)，远看是一条深褐色伤疤。
                case "road":          return Textured("road",      "dirt", Hex("#9C8C6E"), 1.0f, 0.06f, 0f, 1.28f);
                case "sand":          return Textured("sand",      "sand", Sand,     1.0f, 0.1f);
                case "water":         return Transparent("water", Water, 0.72f, 0.85f);
                case "water_deep":    return Transparent("water_deep", WaterDeep, 0.85f, 0.9f);
                // 发光
                case "glow_amber":  return Emissive("glow_amber", GlowAmber, 1.8f);
                case "glow_warm":   return Emissive("glow_warm", GlowWarm, 1.6f);
                case "glow_cyan":   return Emissive("glow_cyan", GlowCyan, 1.8f);
                case "glow_violet": return Emissive("glow_violet", GlowViolet, 1.8f);
                case "glow_gold":   return Emissive("glow_gold", GlowGold, 1.9f);
                case "glass":       return Transparent("glass", new Color(0.72f, 0.86f, 0.92f), 0.35f, 0.9f);
                case "black":       return Solid("black", Color.black, 0.05f);
                case "white":       return Solid("white", Color.white, 0.1f);
                default:
                    // 未登记的名字：给个中性石色，避免生成器静默产生洋红色
                    Debug.LogWarning("[MapMaterials] 未登记材质名: " + key + "，回退为 stone_wall");
                    return Get("stone_wall");
            }
        }

        // ---------- 贴图材质 ----------

        /// <summary>建一个"调色板色 × 贴图"的 Lit 材质（缓存，key 同名只建一次）。</summary>
        /// <param name="exposure">在贴图默认曝光上再乘的系数。亮石/亮灰泥在正午太阳下会糊成一片白，
        /// 给 0.7~0.8 把 albedo 压到 0.4 左右，砖缝/石缝才看得见（色相不变，只是整体略暗）。</param>
        static Material Textured(string key, string texKey, Color tone, float tiling,
                                 float smoothness, float metallic = 0f, float exposure = 1f)
        {
            Material m;
            if (Cache.TryGetValue(key, out m) && m != null) return m;

            Texture2D tex = LoadTexture(texKey);

            // 地图脚本建出来的网格有两套 UV 空间（米制 1UV=1m 和 0..1 整面墙），同一个 tiling
            // 参数不可能两头都对 —— 罗亚市 92 米长的巷道拉伸就是老账。TriplanarLit 按世界坐标
            // 采样，UV 空间彻底不影响结果，所以有它就优先用：铺装、街道、广场这些"大面积纯色板"
            // 的观感全押在它身上。没有它（打包/回退）才走 URP Lit + palette tint。
            if (tex != null && TriShader() != null)
            {
                var def = Textures[texKey];
                m = new Material(TriShader());
                m.name = "MapMat_" + key;
                SetFloat(m, "_Smoothness", smoothness);
                SetFloat(m, "_Metallic", metallic);

                // albedo = _BaseColor * _DetailGain * clamp(1 + str*(rel-1))
                // rel 的均值是 1，所以平均 albedo = _BaseColor * _DetailGain。
                // 令 _DetailGain = 1、_BaseColor = tone*mean-exposure，平均亮度和原来 URP Lit
                // 的 tex * PaletteTint 完全一致，但保留贴图本身的对比（原来也是全套对比）。
                Color lin = tone.linear;
                m.SetColor("_BaseColor", new Color(lin.r * def.Exposure * exposure,
                                                  lin.g * def.Exposure * exposure,
                                                  lin.b * def.Exposure * exposure, 1f));
                m.SetFloat("_DetailMean", Mathf.Max(0.02f, Luma(def.MeanLinear)));
                m.SetFloat("_DetailGain", 1f);
                m.SetFloat("_DetailStrength", 0.70f);
                m.SetTexture("_BaseMap", tex);
                m.SetVector("_BaseMap_ST", new Vector4(1f, 1f, MetresFor(texKey), 0f));

                Texture2D bump = BumpFor(texKey);
                if (bump != null)
                {
                    m.SetTexture("_BumpMap", bump);
                    m.SetFloat("_BumpScale", BumpForScale(texKey));
                    m.EnableKeyword("_NORMALMAP");
                }
                else
                {
                    m.DisableKeyword("_NORMALMAP");
                }
            }
            else
            {
                m = NewLit();
                SetFloat(m, "_Smoothness", smoothness);
                SetFloat(m, "_Metallic", metallic);

                if (tex != null)
                {
                    var def = Textures[texKey];
                    SetColor(m, PaletteTint(tone, def.MeanLinear, def.Exposure * exposure));
                    SetTexture(m, "_BaseMap", tex, tiling);
                    SetTexture(m, "_MainTex", tex, tiling);   // Standard/Unlit 回退用
                    m.name = "MapMat_" + key;
                }
                else
                {
                    // 打包后的运行时建图：没有 AssetDatabase，退回纯色（至少不紫）
                    SetColor(m, tone);
                    m.name = "MapMat_" + key;
                }
            }

            Cache[key] = m;
            return m;
        }

        static float Luma(Color linear)
        {
            return 0.2126f * linear.r + 0.7152f * linear.g + 0.0722f * linear.b;
        }

        static Shader TriShader()
        {
            if (_tri == null) _tri = Shader.Find("MyWorld/TriplanarLit");
            return _tri;
        }

        /// <summary>贴图在世界空间里循环多少米。跟 UV 空间无关，是"一块石头/一片瓦多大"的唯一来源。</summary>
        static float MetresFor(string texKey)
        {
            switch (texKey)
            {
                // kit_cobble 一张 1024 宽里约 30 块石 → 12 m 一循环 = 40 cm 一块。
                // 评审要 0.6 m：1600x900 下 20 m 处约 14 px，够读出石缝；再大就只剩格子。
                case "cobble":     return 12.0f;
                case "stone_wall": return 3.0f;
                case "blocks":     return 2.0f;
                case "brick":      return 0.9f;
                case "roof_tile":  return 1.6f;
                case "thatch":     return 1.4f;
                case "plaster":    return 4.0f;
                case "planks":     return 3.0f;
                case "barrel":     return 1.2f;
                case "wood_dark":  return 3.0f;
                case "grass":      return 5.0f;
                case "dirt":       return 2.2f;
                case "sand":       return 2.2f;
                default:           return 3.0f;
            }
        }

        /// <summary>法线强度。地面最需要（石缝的接触阴影），灰泥这种几乎没有起伏的给很小。</summary>
        static float BumpForScale(string texKey)
        {
            switch (texKey)
            {
                case "cobble":     return 1.30f;
                case "stone_wall": return 0.95f;
                case "blocks":     return 0.85f;
                case "brick":      return 0.75f;
                case "roof_tile":  return 0.85f;
                case "thatch":     return 0.65f;
                case "planks":     return 0.65f;
                default:           return 0.40f;
            }
        }

        /// <summary>法线贴图在 Resources/MapTextures/kit_&lt;key&gt;_n.png（运行时建图也要拿到）。</summary>
        static Texture2D BumpFor(string texKey)
        {
            Texture2D t;
            if (BumpCache.TryGetValue(texKey, out t)) return t;
            t = Resources.Load<Texture2D>("MapTextures/kit_" + texKey + "_n");
            BumpCache[texKey] = t;
            return t;
        }

        /// <summary>
        /// 把贴图平均色归一到调色板色：结果 albedo 的均值 = tone，同时完整保留贴图对比。
        /// tint = toneLinear / meanLinear * exposure（线性空间；URP 项目是 Linear 色彩空间）。
        /// </summary>
        static Color PaletteTint(Color tone, Color meanLinear, float exposure)
        {
            Color lin = tone.linear;
            return new Color(
                lin.r / Mathf.Max(0.004f, meanLinear.r) * exposure,
                lin.g / Mathf.Max(0.004f, meanLinear.g) * exposure,
                lin.b / Mathf.Max(0.004f, meanLinear.b) * exposure,
                1f);
        }

        static void SetTexture(Material m, string prop, Texture2D tex, float tiling)
        {
            if (m == null || !m.HasProperty(prop)) return;
            m.SetTexture(prop, tex);
            m.SetTextureScale(prop, new Vector2(tiling, tiling));
            m.SetTextureOffset(prop, Vector2.zero);
        }

        static Texture2D LoadTexture(string texKey)
        {
            Texture2D tex;
            if (TexCache.TryGetValue(texKey, out tex) && tex != null) return tex;

            TexDef def;
            if (!Textures.TryGetValue(texKey, out def)) return null;

            tex = null;
#if UNITY_EDITOR
            tex = UnityEditor.AssetDatabase.LoadAssetAtPath<Texture2D>(def.Path);
#endif
            // 打包后没有 AssetDatabase：同一批贴图在 Assets/Resources/MapTextures/ 里也存了一份，
            // 用 Resources 兜底，这样运行时建图（以及真机包）也能拿到贴图而不是退回纯色。
            if (tex == null)
            {
                string file = System.IO.Path.GetFileNameWithoutExtension(def.Path);
                tex = Resources.Load<Texture2D>("MapTextures/" + file);
            }
#if UNITY_EDITOR
            if (tex == null)
                Debug.LogWarning("[MapMaterials] 贴图缺失: " + def.Path + "，该材质退回纯色。");
#endif
            if (tex == null) return null;

            // 心里没底就再兜一次：项目里的 .meta 已经设成 Repeat + sRGB + Default
            if (tex.wrapMode != TextureWrapMode.Repeat) tex.wrapMode = TextureWrapMode.Repeat;
            if (tex.anisoLevel < 4) tex.anisoLevel = 4;
            TexCache[texKey] = tex;
            return tex;
        }

        /// <summary>#RRGGBB 转 Color（程序化生成用，比手写 float 清楚）。</summary>
        public static Color Hex(string hex)
        {
            if (string.IsNullOrEmpty(hex)) return Color.magenta;
            if (hex[0] == '#') hex = hex.Substring(1);
            if (hex.Length < 6) return Color.magenta;
            int r = System.Convert.ToInt32(hex.Substring(0, 2), 16);
            int g = System.Convert.ToInt32(hex.Substring(2, 2), 16);
            int b = System.Convert.ToInt32(hex.Substring(4, 2), 16);
            float a = 1f;
            if (hex.Length >= 8) a = System.Convert.ToInt32(hex.Substring(6, 2), 16) / 255f;
            return new Color(r / 255f, g / 255f, b / 255f, a);
        }
    }
}
