using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// 给 FBX 导入生成的那些"纯色"材质补上贴图。
    ///
    /// 背景：Blender 里 albedo 是节点图（Noise/Mix/ColorRamp），FBX 只能带出一个
    /// 平坦基色 0.8/0.8/0.8，导入器再按调色板 JSON 把它换成纯色。
    ///
    /// 关键教训（2026-10-23 实机验证）：早期版本只是把 kit_*.jpg 接进 URP/Lit 的
    /// _BaseMap，结果「调色板颜色 × 贴图」双重相乘 —— 树的绿 0.29/0.48/0.22 乘上
    /// 草地贴图直接变成黑疙瘩，整座城镇在引擎里比 Blender 渲染暗一大截。而且城镇
    /// 是单个 100 m 大网格，靠 EstimateSpan 猜出来的 tiling 也根本对不上。
    ///
    /// 现在改走和 MapMaterials 一样的路线：换 MyWorld/TriplanarLit，_BaseColor 保
    /// 留调色板颜色，_BaseMap_ST.z 存"每块世界米"，贴图只作为绕均值的乘性细节
    /// （_DetailMean = 贴图平均亮度），于是最终 albedo 的均值 == 调色板颜色，
    /// 画面平均亮度不变，只多出细节和法线。
    /// </summary>
    public static class KingdomMaterialDetail
    {
        const string MatRoot = "Assets/Generated/KingdomKit";
        const string TexDir = "Assets/Art/Textures/";

        static readonly Dictionary<string, float> MeanCache = new Dictionary<string, float>();

        /// <summary>材质名片段 → (贴图, 每块世界米)。匹配用小写、按顺序先命中先用。</summary>
        struct Rule
        {
            public string[] Keys;
            public string Tex;
            public float TileMeters;
            public float Detail;
            public Rule(string[] k, string t, float m, float d) { Keys = k; Tex = t; TileMeters = m; Detail = d; }
        }

        static readonly Rule[] Rules =
        {
            // 铺装：kit_cobble 里约 26 块石一排 → 3.4 m/贴图 = 13 cm 一块，石板路真实尺寸
            new Rule(new[] { "cobble", "paving", "flag", "plaza", "lane", "street", "road" }, "kit_cobble", 3.4f, 1.10f),
            // 砌石墙：约 8 块一排 → 2.2 m = 27 cm 一块。dressed/ashlar/chisel 这些是矿镇的
            // 方整石，名字里没有 stone，之前整批漏掉（矿镇 18 个材质还是 URP/Lit 纯色）。
            new Rule(new[] { "stone", "ashlar", "riser", "kerb", "curb", "step", "boulder", "rock", "cliff", "quay", "dock", "plinth", "dressed", "slab", "coping", "wall_cap" }, "kit_stone_wall", 2.2f, 0.85f),
            // 瓦：kit_roof_tile 里约 10 列 → 3.0 m = 30 cm 一片瓦（旧值 0.55 m = 5.5 cm，远处全糊成平色，是屋顶"没纹理"的真因）
            new Rule(new[] { "tile", "roof", "roofing", "slate", "shingle", "shingled", "thack" }, "kit_roof_tile", 3.0f, 0.95f),
            new Rule(new[] { "thatch" }, "kit_thatch", 2.6f, 0.70f),
            // 木：kit_planks 是三块板一张图 → 0.9 m = 30 cm 一块板
            new Rule(new[] { "wood", "plank", "fence", "door", "frame", "beam", "trunk", "bark", "balcony", "shutter", "cart", "barrel", "crate", "deck", "hull", "mast", "timber", "log", "sleeper", "post" }, "kit_planks", 0.9f, 0.55f),
            // 灰泥墙：大面平涂，靠低频脏化
            new Rule(new[] { "plaster", "stucco", "daub", "wall" }, "kit_plaster", 3.0f, 0.30f),
            // 土
            new Rule(new[] { "earth", "soil", "dirt", "gravel", "mud", "sand", "yard", "plot", "field", "terra", "rammed", "clay" }, "kit_dirt", 3.0f, 0.45f),
            // 草/叶
            new Rule(new[] { "grass", "leaf", "leaves", "pasture", "moss", "hedge", "bush", "crop", "wheat", "pine", "fir", "spruce", "needle" }, "kit_grass", 3.0f, 0.40f),
            // 布：用木纹做织纹，密度高一点
            new Rule(new[] { "cloth", "banner", "flag", "awning", "sail", "curtain", "carpet", "tapestry" }, "kit_plaster", 1.2f, 0.20f),
            // 砖
            new Rule(new[] { "brick" }, "kit_brick", 1.4f, 0.70f),
        };

        static readonly Dictionary<string, float> BumpScale = new Dictionary<string, float>
        {
            { "kit_cobble", 1.30f },
            { "kit_stone_wall", 0.95f },
            { "kit_roof_tile", 1.00f },
            { "kit_thatch", 0.70f },
            { "kit_planks", 0.65f },
            { "kit_plaster", 0.35f },
            { "kit_dirt", 0.50f },
            { "kit_grass", 0.45f },
            { "kit_brick", 0.75f },
        };

        [MenuItem("Tools/My World/王国⑥给导入材质加贴图", false, 76)]
        public static void ApplyTextures()
        {
            var tri = Shader.Find("MyWorld/TriplanarLit");
            if (tri == null)
            {
                Debug.LogError("[KingdomDetail] 找不到 MyWorld/TriplanarLit，中止。");
                return;
            }

            string[] mats = Directory.GetFiles(MatRoot, "M_*.mat", SearchOption.AllDirectories);
            int touched = 0, skipped = 0, untouched = 0, bumpApplied = 0;
            var log = new List<string>();

            foreach (string path in mats)
            {
                string p = path.Replace('\\', '/');
                var mat = AssetDatabase.LoadAssetAtPath<Material>(p);
                if (mat == null) continue;

                Rule r = Match(Path.GetFileNameWithoutExtension(p));
                if (r.Tex == null) { untouched++; continue; }

                var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(TexDir + r.Tex + ".jpg");
                if (tex == null) { skipped++; continue; }
                if (!mat.HasProperty("_BaseMap")) { skipped++; continue; }

                // 换 shader 之前把调色板颜色/光滑度读出来（URP Lit 和 TriplanarLit 都有这些属性）
                Color baseColor = mat.HasProperty("_BaseColor") ? mat.GetColor("_BaseColor") : Color.white;
                float smooth = mat.HasProperty("_Smoothness") ? mat.GetFloat("_Smoothness") : 0.2f;
                float metal = mat.HasProperty("_Metallic") ? mat.GetFloat("_Metallic") : 0f;

                float mean = TextureMean(tex);

                mat.shader = tri;
                mat.SetColor("_BaseColor", baseColor);                 // 调色板颜色是主色，不乘贴图
                mat.SetTexture("_BaseMap", tex);
                mat.SetVector("_BaseMap_ST", new Vector4(1f, 1f, r.TileMeters, 0f));
                mat.SetFloat("_DetailMean", mean);
                mat.SetFloat("_DetailGain", 1f);
                mat.SetFloat("_DetailStrength", r.Detail);
                mat.SetFloat("_Smoothness", smooth);
                mat.SetFloat("_Metallic", metal);

                var bump = AssetDatabase.LoadAssetAtPath<Texture2D>(TexDir + r.Tex + "_n.png");
                if (bump != null && mat.HasProperty("_BumpMap"))
                {
                    mat.SetTexture("_BumpMap", bump);
                    float bs;
                    if (!BumpScale.TryGetValue(r.Tex, out bs)) bs = 0.6f;
                    mat.SetFloat("_BumpScale", bs);
                    mat.EnableKeyword("_NORMALMAP");
                    bumpApplied++;
                }
                else
                {
                    mat.DisableKeyword("_NORMALMAP");
                }

                if (mat.HasProperty("_EmissionColor"))
                {
                    var em = mat.GetColor("_EmissionColor");
                    if (em.r + em.g + em.b > 0.0001f) mat.EnableKeyword("_EMISSION");
                    else mat.DisableKeyword("_EMISSION");
                }

                EditorUtility.SetDirty(mat);
                touched++;
                if (log.Count < 12) log.Add(mat.name + " <- " + r.Tex + " @" + r.TileMeters.ToString("0.##") + "m ds=" + r.Detail.ToString("0.##"));
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log("[KingdomDetail] 三角平面材质 " + touched + " 个（法线 " + bumpApplied + "），无贴图 " + untouched + "，跳过 " + skipped + "。\n" + string.Join("\n", log));
        }

        /// <summary>贴图平均亮度（线性）。用 Blit+ReadPixels，绕开 jpg 不可读的问题。</summary>
        static float TextureMean(Texture2D tex)
        {
            float cached;
            if (MeanCache.TryGetValue(tex.name, out cached)) return cached;

            var rt = RenderTexture.GetTemporary(32, 32, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
            var prev = RenderTexture.active;
            Graphics.Blit(tex, rt);
            RenderTexture.active = rt;
            var tmp = new Texture2D(32, 32, TextureFormat.RGBA32, false, true);
            tmp.ReadPixels(new Rect(0, 0, 32, 32), 0, 0);
            tmp.Apply();
            RenderTexture.active = prev;
            RenderTexture.ReleaseTemporary(rt);

            var px = tmp.GetPixels();
            float sum = 0f;
            for (int i = 0; i < px.Length; i++)
                sum += 0.2126f * px[i].r + 0.7152f * px[i].g + 0.0722f * px[i].b;
            Object.DestroyImmediate(tmp);

            float mean = Mathf.Max(sum / Mathf.Max(1, px.Length), 0.004f);
            MeanCache[tex.name] = mean;
            return mean;
        }

        static Rule Match(string matName)
        {
            string n = matName.ToLowerInvariant();
            foreach (var r in Rules)
                foreach (string k in r.Keys)
                    if (n.Contains(k)) return r;
            return default(Rule);
        }
    }
}
