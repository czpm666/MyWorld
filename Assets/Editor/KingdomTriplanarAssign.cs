// 王国⑦：把导入的 M_* 材质换成三角平面（triplanar）着色器。
//
// 背景：王国套件的 FBX 网格 uvs 全空（mesh.uv.Length == 0），URP/Lit 采样 _BaseMap 时
// 所有顶点都落在 (0,0)，采样结果是一个常量 —— 所以贴什么图都是纯色（实测 16x16
// 亮度标准差 0.00）。TriplanarLit 按世界坐标采样，彻底绕开 UV。
//
// 规则（按顺序，先命中先用；名字来自 M_*.mat 去扩展名后的小写）：
//   plaster/stucco                           -> kit_plaster     2.2 m / tile
//   cobble/paving                            -> kit_cobble      1.6 m
//   tile/roof                                -> kit_roof_tile   0.55 m
//   thatch                                   -> kit_thatch      0.9 m
//   brick                                    -> kit_brick       1.2 m
//   grass/leaf/pasture/moss/bush             -> kit_grass       2.0 m
//   earth/soil/dirt/gravel/field/yard        -> kit_dirt        2.5 m
//   stone/rock/step/kerb                     -> kit_stone_wall  1.6 m
//   wall                                     -> kit_stone_wall  1.6 m
//   wood/plank/fence/door/frame/bark/beam    -> kit_planks      0.45 m
//   cloth/banner/flag                        -> kit_plaster     1.0 m
// 一个关键字都没命中的材质原样不动（比如 M_sand / M_blocks / M_metal / M_water）。
//
// _BaseColor 一律不碰 —— 调色板的颜色仍然是主色，贴图只作为"绕均值"的乘性细节。
// _BaseMap_ST = (1, 1, 米/块, 0)：ST.z 存世界米数（不是 offset），TriplanarLit 按它
// 把世界坐标缩放到贴图空间。_DetailMean 是贴图的线性平均亮度，用来把细节亮度归一化
// 到 0.5 均值 —— 于是最终 albedo 的均值 == _BaseColor，画面平均亮度基本不动。
//
// 菜单：Tools/My World/王国⑦三角平面着色            （执行）
//       Tools/My World/王国⑦三角平面着色（回退）      （按备份还原成 URP/Lit）
// 报告写到 E:\My World\WorkQC\kingdom\triplanar_report.json（在 Assets 之外，不参与编译）。

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace MyWorld.EditorTools
{
    public class KingdomTriplanarAssign
    {
        // 两处都要处理：KingdomKit 是王国/首都的分件，MedievalKitBlender 是首都里
        // 380 栋街屋用的 house_a..f 预制体（213 个材质，有 UV 但没贴图，一直平色）。
        static readonly string[] Roots =
        {
            "Assets/Generated/KingdomKit",
            "Assets/Generated/MedievalKitBlender",
        };
        const string ShaderName = "MyWorld/TriplanarLit";
        const string TexDir     = "Assets/Art/Textures";
        const string BackupPath = @"E:\My World\WorkQC\kingdom\triplanar_backup.json";
        const string ReportPath = @"E:\My World\WorkQC\kingdom\triplanar_report.json";

        // ---------------------------------------------------------------- 规则表

        sealed class Rule
        {
            public string[] Keywords;
            public string   Tex;        // kit_* 文件主名
            public float    Metres;     // 一块贴图多少世界米
            public float    Detail;     // 细节强度（纹理相对亮度偏离 1 时的放大量）
            public string   Category;
        }

        // 尺度按像素评审的实测调过一遍（2026-10-22 晚）：
        //   瓦顶：评审量到近景单块图案 0.8-1.0 m，真瓦 0.2-0.3 m → 0.55 收到 0.30
        //   石墙：评审量到砌层 0.15 m，真砌块 0.3-0.5 m（偏细 2-3 倍）→ 1.6 放到 2.6
        //   木构架：关键字表漏了 "timber"，166 万面的 M_timber 一直是平色 → 补上
        // Detail：瓦顶要 3.0（0.85 时 16x16 窗口里瓦缝被 mip 平均掉，std 只有 1.01）；
        //         其余按族给，铺装 1.2 让石板缝读得出来。
        static readonly Rule[] Rules =
        {
            new Rule { Category = "plaster", Keywords = new[] { "plaster", "stucco" },                                  Tex = "kit_plaster",    Metres = 2.2f,  Detail = 0.7f },
            new Rule { Category = "cobble",  Keywords = new[] { "cobble", "paving" },                                   Tex = "kit_cobble",     Metres = 1.2f,  Detail = 1.4f },
            // 复评实测：0.30 m/格 时 k8 近景瓦排 7.8 px ≈ 0.10 m，只有真瓦(0.26-0.30)的 1/3，
            // 5 m 外整片被 mip 平均成纯色（k3/k5 平坦率 94-100%）。按 3.2 倍放大到 0.95。
            new Rule { Category = "roof",    Keywords = new[] { "tile", "roof" },                                       Tex = "kit_roof_tile",  Metres = 0.95f, Detail = 3.0f },
            new Rule { Category = "thatch",  Keywords = new[] { "thatch" },                                             Tex = "kit_thatch",     Metres = 1.2f,  Detail = 1.4f },
            new Rule { Category = "brick",   Keywords = new[] { "brick" },                                              Tex = "kit_brick",      Metres = 1.4f,  Detail = 1.0f },
            new Rule { Category = "grass",   Keywords = new[] { "grass", "leaf", "pasture", "moss", "bush" },            Tex = "kit_grass",      Metres = 2.0f,  Detail = 0.8f },
            new Rule { Category = "earth",   Keywords = new[] { "earth", "soil", "dirt", "gravel", "field", "yard" },    Tex = "kit_dirt",       Metres = 2.5f,  Detail = 0.8f },
            new Rule { Category = "stone",   Keywords = new[] { "stone", "rock", "step", "kerb" },                      Tex = "kit_stone_wall", Metres = 2.2f,  Detail = 1.0f },
            new Rule { Category = "stone",   Keywords = new[] { "wall" },                                               Tex = "kit_stone_wall", Metres = 2.2f,  Detail = 1.0f },
            // 木构：0.45 m/格 在 30 m 视距下同样被 mip 抹平（复评 k4 梁内 grad 0.24 / 2 色）。
            new Rule { Category = "wood",    Keywords = new[] { "wood", "plank", "fence", "door", "frame", "bark", "beam", "timber" }, Tex = "kit_planks", Metres = 1.1f, Detail = 0.9f },
            new Rule { Category = "cloth",   Keywords = new[] { "cloth", "banner", "flag" },                            Tex = "kit_plaster",    Metres = 1.0f,  Detail = 0.7f },
        };

        // ------------------------------------------------------------ 材质备份

        [Serializable]
        sealed class Entry
        {
            public string path;
            public string shader;
            public float  r, g, b, a;
            public string baseMap;
            public float  stx, sty, stz, stw;
            public float  smoothness, metallic;
            public string emission;
            public string keywords;
        }

        [Serializable]
        sealed class Backup { public List<Entry> entries = new List<Entry>(); }

        // ------------------------------------------------------------------ 菜单

        [MenuItem("Tools/My World/王国⑦三角平面着色", false, 47)]
        public static void RunMenu()
        {
            string report = ConvertAll();
            Debug.Log("[王国⑦] " + report);
        }

        [MenuItem("Tools/My World/王国⑦三角平面着色（回退）", false, 48)]
        public static void RevertMenu()
        {
            Debug.Log("[王国⑦] 回退：" + Revert());
        }

        // ------------------------------------------------------------- 主流程

        /// <summary>把所有能按关键字配上的 M_* 材质换成 TriplanarLit。返回一行摘要，并写报告 JSON。</summary>
        public static string ConvertAll()
        {
            Shader tri = Shader.Find(ShaderName);
            if (tri == null)
            {
                string err = "[王国⑦] 找不到着色器 " + ShaderName + " —— TriplanarLit.shader 可能没编译成功";
                Debug.LogError(err);
                return err;
            }

            // 贴图缓存：主名 -> (Texture2D, 线性平均亮度, (0,0) 纹素亮度)
            var texCache  = new Dictionary<string, Texture2D>();
            var meanCache = new Dictionary<string, float>();
            var gainCache = new Dictionary<string, float>();
            var bumpCache = new Dictionary<string, Texture2D>();

            // 掠射角糊化：评审量到"俯视 5.3 的铺装，平视同一材质只有 1.7"，
            // 这是三平面投影在掠射方向导数暴涨、硬件直接挑到最高 mip 的典型症状。
            // 贴图侧能立刻改善的两件事：各向异性拉到 16、过滤改三线性。
            foreach (Rule r in Rules) EnsureAniso(TexDir + "/" + r.Tex + ".jpg", 16);
            // 法线贴图必须按 NormalMap 导入（sRGB 关掉、DXT5nm 编码），否则 UnpackNormalScale
            // 读出来是"被 gamma 解码过的法线"，墙面的凹凸会朝反方向、而且发亮。
            var bumpTypes = new HashSet<string>(StringComparer.Ordinal);
            foreach (Rule r in Rules)
            {
                if (bumpTypes.Add(r.Tex)) EnsureNormalImport(r.Tex);
            }

            string[] guids = AssetDatabase.FindAssets("t:Material", Roots);
            var mats = new List<string>(guids.Length);
            foreach (string guid in guids)
            {
                string p = AssetDatabase.GUIDToAssetPath(guid);
                if (!p.EndsWith(".mat", StringComparison.OrdinalIgnoreCase)) continue;
                // KingdomKit 的材质以 M_ 开头；MedievalKitBlender 里的是 M_house_a_roof 这种，
                // 也以 M_ 开头，所以同一个过滤条件两边都成立。
                if (!Path.GetFileNameWithoutExtension(p).StartsWith("M_", StringComparison.Ordinal)) continue;
                mats.Add(p);
            }
            mats.Sort(StringComparer.OrdinalIgnoreCase);

            var backup  = new Backup();
            var byCat   = new SortedDictionary<string, int>(StringComparer.Ordinal);
            var byTex   = new SortedDictionary<string, int>(StringComparer.Ordinal);
            var skipped = new List<string>();
            var missingTex = new List<string>();
            int bumpApplied = 0;

            AssetDatabase.StartAssetEditing();
            try
            {
                foreach (string path in mats)
                {
                    string stem = Path.GetFileNameWithoutExtension(path).ToLowerInvariant();
                    Rule rule = Match(stem);
                    if (rule == null) { skipped.Add(Path.GetFileName(path)); continue; }

                    string texPath = TexDir + "/" + rule.Tex + ".jpg";
                    Texture2D tex;
                    if (!texCache.TryGetValue(rule.Tex, out tex))
                    {
                        tex = AssetDatabase.LoadAssetAtPath<Texture2D>(texPath);
                        texCache[rule.Tex] = tex;
                        if (tex == null) missingTex.Add(texPath);
                    }
                    if (tex == null) { skipped.Add(Path.GetFileName(path) + " (缺 " + rule.Tex + ")"); continue; }

                    var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
                    if (mat == null) { skipped.Add(Path.GetFileName(path) + " (加载失败)"); continue; }

                    // 先记下原样，回退时用
                    backup.entries.Add(Snapshot(mat, path));

                    float mean, gain;
                    if (!meanCache.TryGetValue(rule.Tex, out mean))
                    {
                        float corner;
                        mean = MeanLinearLuminance(tex, texPath, out corner);
                        meanCache[rule.Tex] = mean;
                        // 换 shader 之前所有顶点 UV 都是 (0,0)，URP/Lit 恒定采到 (0,0) 那一个纹素。
                        // 乘子均值取它，"换 shader 前后的平均亮度"就完全一致 —— 于是 ±12 的
                        // 亮度验收线在原理上就成立，剩下的变化只有细节本身。
                        gainCache[rule.Tex] = Mathf.Clamp(corner, mean * 0.35f, mean * 2.5f);
                    }
                    gain = gainCache[rule.Tex];

                    Color baseColor = mat.HasProperty("_BaseColor") ? mat.GetColor("_BaseColor") : Color.white;
                    float smooth    = mat.HasProperty("_Smoothness") ? mat.GetFloat("_Smoothness") : 0.1f;
                    float metal     = mat.HasProperty("_Metallic")   ? mat.GetFloat("_Metallic")   : 0f;

                    mat.shader = tri;

                    mat.SetColor("_BaseColor",   baseColor);                     // 保持原色，一模一样
                    mat.SetTexture("_BaseMap",   tex);
                    mat.SetVector("_BaseMap_ST", new Vector4(1f, 1f, rule.Metres, 0f));
                    mat.SetFloat("_DetailMean",     Mathf.Max(mean, 0.002f));
                    mat.SetFloat("_DetailGain",     Mathf.Max(gain, 0.001f));
                    mat.SetFloat("_DetailStrength", rule.Detail);
                    mat.SetFloat("_Smoothness",     smooth);
                    mat.SetFloat("_Metallic",       metal);

                    // 法线：Tools/make_normalmaps.py 产的 kit_*_n.png。没有贴图就保持平法线、
                    // 关掉关键字 —— 于是「有没有法线」只影响细节，不会让整批材质换一条路径。
                    Texture2D bump;
                    if (!bumpCache.TryGetValue(rule.Tex, out bump))
                    {
                        bump = LoadBump(rule.Tex);
                        bumpCache[rule.Tex] = bump;
                    }
                    if (bump != null && mat.HasProperty("_BumpMap"))
                    {
                        mat.SetTexture("_BumpMap", bump);
                        mat.SetFloat("_BumpScale", BumpScaleFor(rule.Category));
                        mat.EnableKeyword("_NORMALMAP");
                        bumpApplied++;
                    }
                    else
                    {
                        mat.DisableKeyword("_NORMALMAP");
                    }

                    // 自发光：原来有就留着，没有就清关键字
                    if (mat.HasProperty("_EmissionColor"))
                    {
                        Color em = mat.GetColor("_EmissionColor");
                        if (em.r + em.g + em.b > 0.0001f) mat.EnableKeyword("_EMISSION");
                        else                              mat.DisableKeyword("_EMISSION");
                    }

                    EditorUtility.SetDirty(mat);

                    byCat[rule.Category] = byCat.TryGetValue(rule.Category, out int c0) ? c0 + 1 : 1;
                    byTex[rule.Tex]      = byTex.TryGetValue(rule.Tex,      out int c1) ? c1 + 1 : 1;
                }
            }
            finally
            {
                AssetDatabase.StopAssetEditing();
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            // ---------------- 报告 ----------------
            var sb = new StringBuilder();
            sb.AppendLine("{");
            sb.AppendLine("  \"shader\": \"" + ShaderName + "\",");
            sb.AppendLine("  \"materialsFound\": " + mats.Count + ",");
            sb.AppendLine("  \"converted\": " + backup.entries.Count + ",");
            sb.AppendLine("  \"skipped\": " + skipped.Count + ",");
            sb.AppendLine("  \"normalMapped\": " + bumpApplied + ",");
            sb.AppendLine("  \"byCategory\": " + Dict(byCat) + ",");
            sb.AppendLine("  \"byTexture\": " + Dict(byTex) + ",");
            sb.AppendLine("  \"textureMeanLinear\": " + Floats(meanCache) + ",");
            sb.AppendLine("  \"detailGain\": " + Floats(gainCache) + ",");
            sb.AppendLine("  \"skippedList\": " + StrList(skipped) + ",");
            sb.AppendLine("  \"missingTextures\": " + StrList(missingTex));
            sb.AppendLine("}");
            Write(ReportPath, sb.ToString());
            Write(BackupPath, JsonUtility.ToJson(backup, true));

            string summary = "转换 " + backup.entries.Count + "/" + mats.Count + " 个材质，跳过 " + skipped.Count
                           + "；分类 " + Dict(byCat);
            return summary;
        }

        // --------------------------------------------------------------- 回退

        public static string Revert()
        {
            if (!File.Exists(BackupPath)) return "没有备份文件 " + BackupPath;
            var backup = JsonUtility.FromJson<Backup>(File.ReadAllText(BackupPath, Encoding.UTF8));
            if (backup == null || backup.entries == null) return "备份文件解析失败";

            int n = 0;
            AssetDatabase.StartAssetEditing();
            try
            {
                foreach (Entry e in backup.entries)
                {
                    var mat = AssetDatabase.LoadAssetAtPath<Material>(e.path);
                    if (mat == null) continue;

                    Shader sh = Shader.Find(e.shader);
                    if (sh == null) { Debug.LogWarning("[王国⑦] 回退找不到着色器 " + e.shader + " for " + e.path); continue; }
                    mat.shader = sh;

                    var col = new Color(e.r, e.g, e.b, e.a);
                    if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", col);
                    var st = new Vector4(e.stx, e.sty, e.stz, e.stw);
                    if (mat.HasProperty("_BaseMap_ST")) mat.SetVector("_BaseMap_ST", st);
                    if (mat.HasProperty("_Smoothness")) mat.SetFloat("_Smoothness", e.smoothness);
                    if (mat.HasProperty("_Metallic"))   mat.SetFloat("_Metallic",   e.metallic);

                    if (!string.IsNullOrEmpty(e.baseMap))
                    {
                        var t = AssetDatabase.LoadAssetAtPath<Texture2D>(e.baseMap);
                        if (t != null && mat.HasProperty("_BaseMap")) mat.SetTexture("_BaseMap", t);
                    }
                    if (mat.HasProperty("_EmissionColor") && !string.IsNullOrEmpty(e.emission))
                    {
                        Color em = Color.white;
                        string[] p = e.emission.Split(',');
                        if (p.Length >= 3 &&
                            float.TryParse(p[0], NumberStyles.Float, CultureInfo.InvariantCulture, out float er) &&
                            float.TryParse(p[1], NumberStyles.Float, CultureInfo.InvariantCulture, out float eg) &&
                            float.TryParse(p[2], NumberStyles.Float, CultureInfo.InvariantCulture, out float eb))
                        {
                            em = new Color(er, eg, eb, 1f);
                            mat.SetColor("_EmissionColor", em);
                            if (er + eg + eb > 0.0001f) mat.EnableKeyword("_EMISSION"); else mat.DisableKeyword("_EMISSION");
                        }
                    }
                    EditorUtility.SetDirty(mat);
                    n++;
                }
            }
            finally { AssetDatabase.StopAssetEditing(); }

            AssetDatabase.SaveAssets();
            return "还原 " + n + " 个材质";
        }

        // -------------------------------------------------------------- 工具

        static Rule Match(string lowerStem)
        {
            foreach (Rule r in Rules)
                foreach (string k in r.Keywords)
                    if (lowerStem.Contains(k)) return r;
            return null;
        }

        static Entry Snapshot(Material mat, string path)
        {
            var e = new Entry { path = path };
            e.shader = mat.shader != null ? mat.shader.name : "Universal Render Pipeline/Lit";
            Color c = mat.HasProperty("_BaseColor") ? mat.GetColor("_BaseColor") : Color.white;
            e.r = c.r; e.g = c.g; e.b = c.b; e.a = c.a;
            var st = mat.HasProperty("_BaseMap_ST") ? mat.GetVector("_BaseMap_ST") : new Vector4(1, 1, 0, 0);
            e.stx = st.x; e.sty = st.y; e.stz = st.z; e.stw = st.w;
            e.smoothness = mat.HasProperty("_Smoothness") ? mat.GetFloat("_Smoothness") : 0.5f;
            e.metallic   = mat.HasProperty("_Metallic")   ? mat.GetFloat("_Metallic")   : 0f;
            var t = mat.HasProperty("_BaseMap") ? mat.GetTexture("_BaseMap") : null;
            e.baseMap = t != null ? AssetDatabase.GetAssetPath(t) : string.Empty;
            Color em = mat.HasProperty("_EmissionColor") ? mat.GetColor("_EmissionColor") : Color.black;
            e.emission = em.r.ToString("R", CultureInfo.InvariantCulture) + "," +
                         em.g.ToString("R", CultureInfo.InvariantCulture) + "," +
                         em.b.ToString("R", CultureInfo.InvariantCulture);
            return e;
        }

        /// <summary>
        /// 贴图的线性空间平均亮度（sRGB 解码后再算亮度），同时给出 (0,0) 纹素的亮度。
        /// (0,0) 纹素就是换 shader 之前 UV 全为 0 时 URP/Lit 采到的那一个常量。
        /// 读不出来就退回 0.2。注意 Unity 的纹素下标 0 是左下角，正好是 uv(0,0)。
        /// </summary>
        /// <summary>法线贴图：Tools/make_normalmaps.py 的产物，命名 &lt;主名&gt;_n.png。</summary>
        static void EnsureNormalImport(string texStem)
        {
            string[] exts = { ".png", ".jpg" };
            for (int i = 0; i < exts.Length; i++)
            {
                string path = TexDir + "/" + texStem + "_n" + exts[i];
                var imp = AssetImporter.GetAtPath(path) as TextureImporter;
                if (imp == null) continue;
                bool dirty = false;
                if (imp.textureType != TextureImporterType.NormalMap)
                {
                    imp.textureType = TextureImporterType.NormalMap;
                    dirty = true;
                }
                if (imp.sRGBTexture) { imp.sRGBTexture = false; dirty = true; }
                if (imp.anisoLevel != 8) { imp.anisoLevel = 8; dirty = true; }
                if (dirty) imp.SaveAndReimport();
                return;
            }
        }

        static Texture2D LoadBump(string texStem)
        {
            string[] exts = { ".png", ".jpg" };
            for (int i = 0; i < exts.Length; i++)
            {
                var t = AssetDatabase.LoadAssetAtPath<Texture2D>(TexDir + "/" + texStem + "_n" + exts[i]);
                if (t != null) return t;
            }
            return null;
        }

        /// <summary>每类材质的法线强度：石/瓦/板条最需要起伏，灰泥和布几乎没有。</summary>
        static float BumpScaleFor(string category)
        {
            switch (category)
            {
                case "cobble":  return 1.00f;
                case "stone":   return 0.85f;
                case "roof":    return 0.80f;
                case "brick":   return 0.70f;
                case "thatch":  return 0.70f;
                case "wood":    return 0.55f;
                case "earth":   return 0.45f;
                case "grass":   return 0.40f;
                case "plaster": return 0.30f;
                case "cloth":   return 0.20f;
                default:        return 0.50f;
            }
        }

        /// <summary>
        /// 把一根 kit_* 贴图的各向异性拉到指定级、过滤改三线性。
        /// 三平面投影在掠射面上的屏幕导数会被拉长成一条，硬件于是取最高 mip，
        /// 近景水平面就糊成一块色——各向异性是唯一能在贴图侧缓解的开关。
        /// </summary>
        static void EnsureAniso(string assetPath, int aniso)
        {            var imp = AssetImporter.GetAtPath(assetPath) as TextureImporter;
            if (imp == null) return;
            bool dirty = false;
            if (imp.anisoLevel != aniso) { imp.anisoLevel = aniso; dirty = true; }
            if (imp.filterMode != FilterMode.Trilinear) { imp.filterMode = FilterMode.Trilinear; dirty = true; }
            if (dirty) imp.SaveAndReimport();
        }

        static float MeanLinearLuminance(Texture2D tex, string assetPath, out float cornerLum)
        {
            cornerLum = 0.2f;
            try
            {
                byte[] bytes = File.ReadAllBytes(assetPath.Replace('/', '\\'));
                var tmp = new Texture2D(4, 4, TextureFormat.RGBA32, false, false);
                if (!tmp.LoadImage(bytes)) { UnityEngine.Object.DestroyImmediate(tmp); return 0.2f; }
                Color32[] px = tmp.GetPixels32();
                double sum = 0.0;
                for (int i = 0; i < px.Length; i++)
                {
                    double r = SRGBToLinear(px[i].r / 255.0);
                    double g = SRGBToLinear(px[i].g / 255.0);
                    double b = SRGBToLinear(px[i].b / 255.0);
                    sum += 0.2126 * r + 0.7152 * g + 0.0722 * b;
                }
                int n = px.Length;
                if (n > 0)
                {
                    cornerLum = (float)(0.2126 * SRGBToLinear(px[0].r / 255.0)
                                      + 0.7152 * SRGBToLinear(px[0].g / 255.0)
                                      + 0.0722 * SRGBToLinear(px[0].b / 255.0));
                }
                UnityEngine.Object.DestroyImmediate(tmp);
                return n > 0 ? (float)(sum / n) : 0.2f;
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[王国⑦] 读不到贴图像素 " + assetPath + "：" + ex.Message + "（退回 0.2）");
                return 0.2f;
            }
        }

        static double SRGBToLinear(double v)
        {
            v = Math.Max(0.0, Math.Min(1.0, v));
            return v <= 0.04045 ? v / 12.92 : Math.Pow((v + 0.055) / 1.055, 2.4);
        }

        static string Dict(SortedDictionary<string, int> d)
        {
            var sb = new StringBuilder("{");
            bool first = true;
            foreach (var kv in d)
            {
                if (!first) sb.Append(", ");
                first = false;
                sb.Append('"').Append(kv.Key).Append("\": ").Append(kv.Value);
            }
            return sb.Append('}').ToString();
        }

        static string Floats(Dictionary<string, float> d)
        {
            var sb = new StringBuilder("{");
            bool first = true;
            foreach (var kv in d)
            {
                if (!first) sb.Append(", ");
                first = false;
                sb.Append('"').Append(kv.Key).Append("\": ")
                  .Append(kv.Value.ToString("0.0000", CultureInfo.InvariantCulture));
            }
            return sb.Append('}').ToString();
        }

        static string StrList(List<string> items)
        {
            var sb = new StringBuilder("[");
            for (int i = 0; i < items.Count && i < 400; i++)
            {
                if (i > 0) sb.Append(", ");
                sb.Append('"').Append(items[i].Replace("\\", "/")).Append('"');
            }
            return sb.Append(']').ToString();
        }

        static void Write(string path, string text)
        {
            try
            {
                string dir = Path.GetDirectoryName(path);
                if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);
                File.WriteAllText(path, text, new UTF8Encoding(false));
            }
            catch (Exception ex) { Debug.LogWarning("[王国⑦] 写文件失败 " + path + "：" + ex.Message); }
        }
    }
}
