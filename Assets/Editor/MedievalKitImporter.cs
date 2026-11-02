using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// 中世纪低模道具包导入器。
    ///
    /// Blender 侧脚本：E:\GameProject\art\build_kit.py（16 件道具，单位米，pivot 在底面中心，+Z 朝前）。
    /// 本工具负责：
    ///   1. 扫描 Assets/Generated/MedievalKit/*.fbx，统一设置导入参数（缩放 1、无动画、无碰撞体）；
    ///   2. 把 FBX 里的 Blender 材质（M_Medieval_*）按调色板重建成 URP/Lit 材质资源，
    ///      避免 URP 下 Standard 材质渲染成洋红；
    ///   3. 生成 Assets/Resources/MedievalKit/&lt;key&gt;.prefab：根节点名字 = key，
    ///      网格顶点沿用 Blender 空间（底面 y=0、XZ 居中），所以预制体根变换归零即可直接落在地面上。
    ///
    /// 菜单：Tools → My World → 导入中世纪道具包
    /// 运行时用法：Resources.Load&lt;GameObject&gt;("MedievalKit/barrel")
    /// </summary>
    public static class MedievalKitImporter
    {
        public const string FbxDir = "Assets/Generated/MedievalKit";
        public const string PrefabDir = "Assets/Resources/MedievalKit";
        public const string MatDir = "Assets/Generated/MedievalKit/Materials";
        public const string ResourcesPrefix = "MedievalKit/";

        /// <summary>
        /// 调色板（sRGB），必须与 E:\GameProject\art\build_kit.py 里的 PALETTE 保持一致。
        /// 键名是去掉 "M_Medieval_" 前缀后的短名；FBX 里的材质全名是 "M_Medieval_" + 短名。
        /// </summary>
        private static readonly Dictionary<string, Color> Palette = new Dictionary<string, Color>
        {
            { "Wood",      new Color(0.52f, 0.36f, 0.21f) },
            { "WoodDark",  new Color(0.31f, 0.20f, 0.12f) },
            { "WoodLight", new Color(0.66f, 0.50f, 0.31f) },
            { "Metal",     new Color(0.45f, 0.47f, 0.52f) },
            { "MetalDark", new Color(0.22f, 0.23f, 0.27f) },
            { "Stone",     new Color(0.63f, 0.61f, 0.56f) },
            { "StoneDark", new Color(0.45f, 0.44f, 0.40f) },
            { "ClothRed",  new Color(0.62f, 0.22f, 0.18f) },
            { "ClothBlue", new Color(0.24f, 0.34f, 0.52f) },
            { "Leather",   new Color(0.36f, 0.24f, 0.16f) },
            { "Hay",       new Color(0.80f, 0.66f, 0.34f) },
            { "Water",     new Color(0.29f, 0.52f, 0.63f) },
            { "Glow",      new Color(1.00f, 0.78f, 0.42f) },
            { "Gold",      new Color(0.78f, 0.60f, 0.22f) },
            { "Clay",      new Color(0.66f, 0.38f, 0.26f) },
        };

        /// <summary>按短名长度倒序缓存，保证 "WoodDark" 先于 "Wood" 匹配。</summary>
        private static List<string> _paletteOrder;

        [MenuItem("Tools/My World/导入中世纪道具包")]
        public static void ImportAll()
        {
            if (!AssetDatabase.IsValidFolder(FbxDir))
            {
                Debug.LogError($"[MedievalKit] 找不到 FBX 目录 {FbxDir}，请先在 Blender 里跑 art/build_kit.py。");
                return;
            }
            EnsureFolder(PrefabDir);
            EnsureFolder(MatDir);

            string[] fbxFiles = Directory.GetFiles(Path.GetFullPath(FbxDir), "*.fbx");
            System.Array.Sort(fbxFiles, System.StringComparer.OrdinalIgnoreCase);

            int ok = 0;
            var errors = new List<string>();
            foreach (string fbxAbs in fbxFiles)
            {
                string key = Path.GetFileNameWithoutExtension(fbxAbs);
                string fbxAsset = FbxDir + "/" + key + ".fbx";
                try
                {
                    if (ImportOne(key, fbxAsset)) ok++;
                    else errors.Add(key);
                }
                catch (System.Exception e)
                {
                    errors.Add(key + " (" + e.GetType().Name + ")");
                    Debug.LogException(e);
                }
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            if (errors.Count == 0)
                Debug.Log($"[MedievalKit] 导入完成：{ok} 个预制体 → {PrefabDir}/<key>.prefab");
            else
                Debug.LogError($"[MedievalKit] 导入完成但有问题：成功 {ok} / 失败 {errors.Count}：" +
                               string.Join(", ", errors));
        }

        /// <summary>导入单个 FBX 并生成预制体。返回 true 表示成功。</summary>
        private static bool ImportOne(string key, string fbxAsset)
        {
            ConfigureImporter(fbxAsset);

            var model = AssetDatabase.LoadAssetAtPath<GameObject>(fbxAsset);
            if (model == null)
            {
                Debug.LogError($"[MedievalKit] {key}: FBX 加载失败 {fbxAsset}");
                return false;
            }

            // 取模型里的第一个网格：Blender 每件道具正好导出一个合并后的网格对象
            MeshFilter mf = null;
            foreach (var f in model.GetComponentsInChildren<MeshFilter>(true))
            {
                if (f.sharedMesh != null) { mf = f; break; }
            }
            if (mf == null)
            {
                Debug.LogError($"[MedievalKit] {key}: FBX 里没有网格");
                return false;
            }
            var srcRenderer = mf.GetComponent<MeshRenderer>();
            var mesh = mf.sharedMesh;

            // 材质：按名字映射到调色板重建 URP/Lit 资源（FBX 自带材质在 URP 下是洋红）
            Material[] srcMats = srcRenderer != null ? srcRenderer.sharedMaterials : new Material[0];
            var mats = new Material[srcMats.Length];
            for (int i = 0; i < srcMats.Length; i++)
                mats[i] = ResolveKitMaterial(srcMats[i] != null ? srcMats[i].name : null);

            // 根节点 = key，变换归零（Blender 网格已是底面 y=0、XZ 居中，pivot 在底面中心）
            var root = new GameObject(key);
            try
            {
                var filter = root.AddComponent<MeshFilter>();
                filter.sharedMesh = mesh;
                var renderer = root.AddComponent<MeshRenderer>();
                renderer.sharedMaterials = mats;
                renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
                renderer.receiveShadows = true;
                renderer.lightProbeUsage = UnityEngine.Rendering.LightProbeUsage.BlendProbes;
                renderer.reflectionProbeUsage = UnityEngine.Rendering.ReflectionProbeUsage.BlendProbes;

                string prefabPath = PrefabDir + "/" + key + ".prefab";
                PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
                Validate(key, mesh, prefabPath);
                return true;
            }
            finally
            {
                Object.DestroyImmediate(root);
            }
        }

        /// <summary>统一 FBX 导入参数：米制、无动画、无骨骼、无碰撞体、提取材质。</summary>
        private static void ConfigureImporter(string fbxAsset)
        {
            var importer = AssetImporter.GetAtPath(fbxAsset) as ModelImporter;
            if (importer == null)
            {
                Debug.LogError($"[MedievalKit] 找不到 ModelImporter：{fbxAsset}");
                return;
            }
            importer.globalScale = 1f;
            importer.useFileScale = true;
            importer.animationType = ModelImporterAnimationType.None;
            importer.importAnimation = false;
            importer.importBlendShapes = false;
            importer.importCameras = false;
            importer.importLights = false;
            importer.addCollider = false;
            importer.importVisibility = false;
            importer.bakeAxisConversion = false;
            importer.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            importer.materialSearch = ModelImporterMaterialSearch.Everywhere;
            importer.SaveAndReimport();
        }

        /// <summary>把 FBX 材质名映射成 URP/Lit 材质资源；未知名字退回白灰色并警告。</summary>
        private static Material ResolveKitMaterial(string sourceName)
        {
            string shortName = sourceName;
            if (!string.IsNullOrEmpty(shortName) && shortName.StartsWith("M_Medieval_"))
                shortName = shortName.Substring("M_Medieval_".Length);
            if (string.IsNullOrEmpty(shortName)) shortName = "Stone";

            if (_paletteOrder == null)
            {
                _paletteOrder = new List<string>(Palette.Keys);
                _paletteOrder.Sort((a, b) => b.Length.CompareTo(a.Length));
            }

            string matched = null;
            foreach (string candidate in _paletteOrder)
            {
                if (shortName == candidate) { matched = candidate; break; }
            }
            if (matched == null)
            {
                foreach (string candidate in _paletteOrder)
                {
                    if (shortName.EndsWith(candidate)) { matched = candidate; break; }
                }
            }
            if (matched == null)
            {
                Debug.LogWarning($"[MedievalKit] 未知材质名 '{sourceName}'，退回 Stone 色，请检查调色板。");
                matched = "Stone";
            }

            string matName = "M_MedievalKit_" + matched;
            string matPath = MatDir + "/" + matName + ".mat";
            Color color = Palette[matched];
            bool metallic = matched == "Metal" || matched == "MetalDark" || matched == "Gold";
            float metal = matched == "Gold" ? 0.65f : (metallic ? 0.25f : 0.0f);
            float smooth = matched == "Glow" ? 0.1f : 0.28f;

            var shader = Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null) shader = Shader.Find("Universal Render Pipeline/Simple Lit");
            if (shader == null)
            {
                Debug.LogError("[MedievalKit] 找不到 URP/Lit shader，材质会是洋红。请检查 URP 配置。");
                return null;
            }

            var mat = AssetDatabase.LoadAssetAtPath<Material>(matPath);
            if (mat == null)
            {
                mat = new Material(shader) { name = matName };
                AssetDatabase.CreateAsset(mat, matPath);
            }
            mat.shader = shader;
            if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", color);
            mat.color = color;
            mat.SetFloat("_Metallic", metal);
            mat.SetFloat("_Smoothness", smooth);
            if (matched == "Glow")
            {
                mat.EnableKeyword("_EMISSION");
                if (mat.HasProperty("_EmissionColor")) mat.SetColor("_EmissionColor", color * 1.6f);
                mat.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
            }
            EditorUtility.SetDirty(mat);
            return mat;
        }

        /// <summary>烘焙后的自检：三角面、底面 pivot、尺寸是否合理。</summary>
        private static void Validate(string key, Mesh mesh, string prefabPath)
        {
            int tris = mesh.triangles.Length / 3;
            Bounds b = mesh.bounds;
            Vector3 size = b.size;
            float bottom = b.center.y - b.extents.y;
            float maxDim = Mathf.Max(size.x, Mathf.Max(size.y, size.z));

            bool triOk = tris >= 300 && tris <= 2000;
            bool pivotOk = Mathf.Abs(bottom) < 0.01f;
            bool scaleOk = maxDim > 0.2f && maxDim < 6f;

            string msg = $"[MedievalKit] {key}: tris={tris}, size=({size.x:F2},{size.y:F2},{size.z:F2})m, " +
                         $"bottomY={bottom:F3} → {prefabPath}";
            if (triOk && pivotOk && scaleOk) Debug.Log(msg);
            else Debug.LogWarning(msg + "  ⚠ " +
                                  (!triOk ? "三角面数超出 300~2000；" : "") +
                                  (!pivotOk ? "底面不在 y=0（pivot 不是底面中心）；" : "") +
                                  (!scaleOk ? "尺寸不在 0.2~6m，FBX 缩放可能不对；" : ""));
        }

        /// <summary>预制体的 Resources 路径（不含扩展名），给运行时 Resources.Load 用。</summary>
        public static string PrefabResourcePath(string key)
        {
            return ResourcesPrefix + key;
        }

        private static void EnsureFolder(string folder)
        {
            if (AssetDatabase.IsValidFolder(folder)) return;
            string parent = Path.GetDirectoryName(folder).Replace('\\', '/');
            string leaf = Path.GetFileName(folder);
            if (!AssetDatabase.IsValidFolder(parent)) EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, leaf);
        }
    }
}
