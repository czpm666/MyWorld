// Blender 阿斯拉王国城镇 FBX → Unity 预制体。
//
// 这些 FBX 是「整座城一个 mesh + 50~130 个材质槽」，和 MedievalKitBlender 那种
// 「一件一个小件、每件一张图集」完全不同：既没有贴图，也没有 albedo 图集可挂。
// 所以颜色走 **材质名 → 调色板 JSON**（dump_palette.py 从 .blend 里量出来的
// Principled 基色/金属度/粗糙度/自发光），一个 Blender 材质对应一个 Unity 材质资产，
// 这样同名的木头/石头/瓦片在九座城镇之间是共享的，不会炸成几百个材质。
//
// 菜单：Tools/My World/王国①导入城镇 FBX（复制 + 导入 + 建材质 + 出预制体）
//       Tools/My World/王国②城镇清单（只打印，不改资源）
//
// 关键设置（改错会毁掉整座城）：
//   * globalScale = 1、useFileScale = true —— FBX 已经是米，不要再乘 100/0.01
//   * materialImportMode = None —— 不让 Unity 自己生成一堆无名材质
//   * importCameras / importLights / animation = false —— Blender 相机灯光会跟着进来
//   * addCollider = false —— 20 万面一棵树都没必要，碰撞另外做
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace MyWorldEditorTools
{
    public static class KingdomKitImporter
    {
        private const string UrpLitShader = "Universal Render Pipeline/Lit";

        // Blender 侧（只读）
        // 小镇和王都分件都从 Blender 导出，两个根一起扫：kind 由上一级目录名决定，
        // 所以王都分件会落到 KingdomKit/capital/ 下面，调色板按 FBX 名逐个读。
        private static readonly string[] SrcRoots =
        {
            @"E:\My World\Blender\export\kingdom",
            @"E:\My World\Blender\export\capital",
        };
        private const string PaletteRoot = @"E:\My World\Blender\export\kingdom\palettes";

        // Unity 侧（写）
        private const string DestRoot = "Assets/Generated/KingdomKit";

        [Serializable]
        private class PaletteEntry
        {
            public string name;
            public string hex;
            public float metal;
            public float rough;
            public float emis;
            public string emisHex;
        }

        [Serializable]
        private class Palette
        {
            public List<PaletteEntry> colors = new List<PaletteEntry>();
        }

        [MenuItem("Tools/My World/王国①导入城镇 FBX", false, 70)]
        public static void ImportAll()
        {
            var fbxFiles = new List<string>();
            foreach (var root in SrcRoots)
            {
                if (!Directory.Exists(root))
                {
                    Debug.LogWarning("[Kingdom] 找不到 Blender 导出目录：" + root + "（跳过）");
                    continue;
                }
                fbxFiles.AddRange(Directory.GetFiles(root, "*.fbx", SearchOption.AllDirectories));
            }
            fbxFiles.Sort(StringComparer.OrdinalIgnoreCase);
            if (fbxFiles.Count == 0)
            {
                Debug.LogError("[Kingdom] 两个导出根下面都没有 .fbx");
                return;
            }

            int ok = 0, fail = 0;
            var report = new StringBuilder();
            report.AppendLine("[Kingdom] 导入 " + fbxFiles.Count + " 个城/镇/王都 FBX");

            foreach (var srcFbx in fbxFiles)
            {
                try
                {
                    var row = ImportOne(srcFbx);
                    if (row != null)
                    {
                        report.AppendLine(row);
                        ok++;
                    }
                    else
                    {
                        fail++;
                    }
                }
                catch (Exception e)
                {
                    fail++;
                    Debug.LogError("[Kingdom] 失败 " + srcFbx + "\n" + e);
                }
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            report.AppendLine("[Kingdom] 完成：成功 " + ok + " / 失败 " + fail);

            // 导入器会把这些共享材质强制切回 URP/Lit 并按调色板上色 —— 三角平面
            // 贴图/法线会被抹掉，所以每次导入后立刻重跑一遍细节化，保证"导完即可用"。
            try
            {
                MyWorld.EditorTools.KingdomMaterialDetail.ApplyTextures();
            }
            catch (Exception e)
            {
                report.AppendLine("[Kingdom] 材质细节化失败：" + e.Message);
            }

            Debug.Log(report.ToString());
        }

        [MenuItem("Tools/My World/王国②城镇清单", false, 71)]
        public static void ListTowns()
        {
            var dirs = Directory.Exists(DestRoot)
                ? Directory.GetDirectories(DestRoot)
                : new string[0];
            var sb = new StringBuilder("[Kingdom] 已导入的城镇：\n");
            foreach (var d in dirs)
            {
                string kind = Path.GetFileName(d);
                var prefabs = Directory.GetFiles(d, "*.prefab", SearchOption.AllDirectories);
                sb.AppendLine("  " + kind + " : " + prefabs.Length + " prefab");
                foreach (var p in prefabs)
                    sb.AppendLine("    " + p.Replace('\\', '/').Replace(
                        Directory.GetParent(Application.dataPath).FullName.Replace('\\', '/') + "/", ""));
            }
            Debug.Log(sb.ToString());
        }

        private static string ImportOne(string srcFbx)
        {
            string name = Path.GetFileNameWithoutExtension(srcFbx);
            string kind = Path.GetFileName(Path.GetDirectoryName(srcFbx));
            if (string.IsNullOrEmpty(kind)) kind = "misc";

            string destDir = DestRoot + "/" + kind;
            EnsureFolder("Assets/Generated");
            EnsureFolder(DestRoot);
            EnsureFolder(destDir);
            string destFbx = destDir + "/" + name + ".fbx";

            string projectRoot = Directory.GetParent(Application.dataPath).FullName;
            string destAbs = Path.Combine(projectRoot, destFbx.Replace('/', Path.DirectorySeparatorChar));
            bool copied = false;
            if (!File.Exists(destAbs) ||
                File.GetLastWriteTimeUtc(destAbs) < File.GetLastWriteTimeUtc(srcFbx))
            {
                File.Copy(srcFbx, destAbs, true);
                copied = true;
            }

            if (copied || AssetImporter.GetAtPath(destFbx) == null)
                AssetDatabase.ImportAsset(destFbx, ImportAssetOptions.ForceUpdate);

            var importer = AssetImporter.GetAtPath(destFbx) as ModelImporter;
            if (importer == null)
            {
                Debug.LogError("[Kingdom] 不是 ModelImporter：" + destFbx);
                return null;
            }

            bool dirty = false;
            if (!Mathf.Approximately(importer.globalScale, 1f)) { importer.globalScale = 1f; dirty = true; }
            if (!importer.useFileScale) { importer.useFileScale = true; dirty = true; }
            if (importer.importCameras) { importer.importCameras = false; dirty = true; }
            if (importer.importLights) { importer.importLights = false; dirty = true; }
            if (importer.importBlendShapes) { importer.importBlendShapes = false; dirty = true; }
            if (importer.importVisibility) { importer.importVisibility = false; dirty = true; }
            if (importer.addCollider) { importer.addCollider = false; dirty = true; }
            if (importer.meshCompression != ModelImporterMeshCompression.Off)
            {
                importer.meshCompression = ModelImporterMeshCompression.Off;
                dirty = true;
            }
            if (importer.animationType != ModelImporterAnimationType.None)
            {
                importer.animationType = ModelImporterAnimationType.None;
                dirty = true;
            }
            // 材质必须让 Unity 先按 FBX 材质名生成内嵌副本 —— 只有这样才能读到
            // 「第 i 个槽位叫什么名字」；然后我们把槽位换成自己的共享材质资产。
            // （试过 None：所有 renderer 的 sharedMaterials 全是 null，材质名彻底丢失，
            //  结果整座城只剩一个灰材质。）
            if (importer.materialImportMode != ModelImporterMaterialImportMode.ImportStandard)
            {
                importer.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
                dirty = true;
            }
            if (importer.materialLocation != ModelImporterMaterialLocation.InPrefab)
            {
                importer.materialLocation = ModelImporterMaterialLocation.InPrefab;
                dirty = true;
            }
            if (dirty) importer.SaveAndReimport();

            var palette = LoadPalette(name);
            var go = AssetDatabase.LoadAssetAtPath<GameObject>(destFbx);
            if (go == null)
            {
                Debug.LogError("[Kingdom] 载入失败：" + destFbx);
                return null;
            }

            var instance = (GameObject)UnityEngine.Object.Instantiate(go);
            instance.name = name;

            var renderers = instance.GetComponentsInChildren<MeshRenderer>(true);
            int slots = 0, matched = 0;
            var used = new HashSet<Material>();
            foreach (var r in renderers)
            {
                var mats = r.sharedMaterials;
                var next = new Material[mats.Length];
                for (int i = 0; i < mats.Length; i++)
                {
                    slots++;
                    string key = mats[i] != null ? CleanName(mats[i].name) : null;
                    var mat = ResolveMaterial(kind, key, palette);
                    if (mat != null) matched++;
                    next[i] = mat;
                }
                r.sharedMaterials = next;
                foreach (var m in next) if (m != null) used.Add(m);
            }

            // 阴影/受光：这些是实心建筑，Cast 开、Receive 开
            foreach (var r in renderers)
            {
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
                r.receiveShadows = true;
                r.lightProbeUsage = UnityEngine.Rendering.LightProbeUsage.BlendProbes;
            }

            string prefabDir = destDir + "/Prefabs";
            EnsureFolder(prefabDir);
            string prefabPath = prefabDir + "/" + name + ".prefab";
            PrefabUtility.SaveAsPrefabAsset(instance, prefabPath);
            UnityEngine.Object.DestroyImmediate(instance);

            long tris = 0;
            foreach (var mf in go.GetComponentsInChildren<MeshFilter>(true))
            {
                var mesh = mf.sharedMesh;
                if (mesh != null) tris += mesh.triangles.LongLength / 3L;
            }

            return string.Format(
                "  {0}/{1}: renderers={2} slots={3} matched={4} materials={5} tris={6:N0} " +
                "size={7:N1}MB prefab={8}",
                kind, name, renderers.Length, slots, matched, used.Count, tris,
                new FileInfo(destAbs).Length / 1048576.0, prefabPath);
        }

        /// <summary>Unity 会把 `plaster.001` 这种重名加后缀，去掉再找调色板。</summary>
        private static string CleanName(string n)
        {
            if (string.IsNullOrEmpty(n)) return null;
            int dot = n.IndexOf('.');
            if (dot > 0) n = n.Substring(0, dot);
            return n.Trim();
        }

        private static Palette LoadPalette(string name)
        {
            string json = Path.Combine(PaletteRoot, name + ".json");
            // 王都分件没有各自的调色板，统一退回 capital.json
            if (!File.Exists(json)) json = Path.Combine(PaletteRoot, "capital.json");
            if (!File.Exists(json))
            {
                Debug.LogWarning("[Kingdom] 没有调色板：" + json + "（颜色会退回中灰）");
                return new Palette();
            }
            try
            {
                return JsonUtility.FromJson<Palette>(File.ReadAllText(json)) ?? new Palette();
            }
            catch (Exception e)
            {
                Debug.LogWarning("[Kingdom] 调色板解析失败 " + json + " : " + e.Message);
                return new Palette();
            }
        }

        private static Material ResolveMaterial(string kind, string key, Palette palette)
        {
            var shader = Shader.Find(UrpLitShader);
            if (shader == null) return null;
            if (string.IsNullOrEmpty(key)) key = "unmatched";

            string matDir = DestRoot + "/" + kind + "/Materials";
            EnsureFolder(matDir);
            string safe = key.Replace('/', '_').Replace('\\', '_');
            string path = matDir + "/M_" + safe + ".mat";

            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            bool created = mat == null;
            if (created) mat = new Material(shader);
            if (mat.shader != shader) mat.shader = shader;

            PaletteEntry e = null;
            foreach (var c in palette.colors)
            {
                if (string.Equals(c.name, key, StringComparison.OrdinalIgnoreCase))
                {
                    e = c;
                    break;
                }
            }

            Color color = new Color(0.5f, 0.5f, 0.5f, 1f);
            if (e != null && !string.IsNullOrEmpty(e.hex) &&
                ColorUtility.TryParseHtmlString(e.hex, out var parsed))
                color = parsed;

            if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", color);
            if (mat.HasProperty("_Color")) mat.SetColor("_Color", color);
            if (mat.HasProperty("_Metallic")) mat.SetFloat("_Metallic", e != null ? e.metal : 0f);
            if (mat.HasProperty("_Smoothness"))
                mat.SetFloat("_Smoothness", e != null ? Mathf.Clamp01(1f - e.rough) : 0.25f);

            // 火把/炉口这种自发光：URP Lit 的 _EmissionColor + 开 _EMISSION
            bool emissive = e != null && e.emis > 0.01f && !string.IsNullOrEmpty(e.emisHex);
            if (mat.HasProperty("_EmissionColor"))
            {
                Color ec = Color.black;
                if (emissive && ColorUtility.TryParseHtmlString(e.emisHex, out var eh))
                    ec = eh * Mathf.Clamp(e.emis * 0.25f, 1f, 4f);
                mat.SetColor("_EmissionColor", ec);
                mat.globalIlluminationFlags = emissive
                    ? MaterialGlobalIlluminationFlags.RealtimeEmissive
                    : MaterialGlobalIlluminationFlags.EmissiveIsBlack;
                if (emissive) mat.EnableKeyword("_EMISSION");
                else mat.DisableKeyword("_EMISSION");
            }

            if (created) AssetDatabase.CreateAsset(mat, path);
            EditorUtility.SetDirty(mat);
            return mat;
        }

        private static void EnsureFolder(string assetPath)
        {
            if (AssetDatabase.IsValidFolder(assetPath)) return;
            string parent = Path.GetDirectoryName(assetPath)?.Replace('\\', '/');
            string leaf = Path.GetFileName(assetPath);
            if (string.IsNullOrEmpty(parent) || string.IsNullOrEmpty(leaf)) return;
            if (!AssetDatabase.IsValidFolder(parent)) EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, leaf);
        }
    }
}
