using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace MyWorldEditorTools
{
    /// <summary>
    /// 室内套件（Blender 烘好的 FBX）导入与装配。
    ///
    /// 为什么要单独写一个导入器：这套 FBX 的材质是"整件烘焙一张图集"，
    /// 所以每个 piece 的所有材质槽必须共用同一个 M_Interior_&lt;piece&gt;.mat
    /// （_BaseMap = &lt;piece&gt;_albedo，_BumpMap = &lt;piece&gt;_normal）。
    /// 让 Unity 自己去推材质会得到一堆互相冲突的槽位材质。
    ///
    /// 菜单（路径里只有两个 "/"，多的 "/" 会让 Unity 当成更深一级子菜单而注册不上）：
    ///   Tools/My World/室内①导入 FBX 与材质
    ///   Tools/My World/室内②测量门洞与朝向
    /// </summary>
    public static class InteriorKitImporter
    {
        public const string SrcDir = @"E:\My World\Blender\export";
        public const string DstDir = "Assets/Generated/Interiors/FBX";
        public const string MatDir = "Assets/Generated/Interiors/Materials";

        /// <summary>屋子外壳（含门洞与窗洞）。同名规则：xxxx_a = 民居，xxxx_shop_a = 商铺。</summary>
        public static readonly string[] Pieces =
        {
            "interior_house_a",
            "interior_shop_a",
            "interior_inn_a",
            "interior_house_a_roof",
            "door_leaf",
        };

        [MenuItem("Tools/My World/室内①导入 FBX 与材质", priority = 65)]
        public static void ImportAll()
        {
            if (EditorApplication.isPlaying)
            {
                Debug.LogError("[InteriorKit] 先退出 Play 再导入。");
                return;
            }
            Directory.CreateDirectory(DstDir);
            Directory.CreateDirectory(MatDir);

            var copied = new List<string>();
            foreach (var piece in Pieces)
            {
                foreach (var suffix in new[] { ".fbx", "_albedo.png", "_normal.png" })
                {
                    string src = Path.Combine(SrcDir, piece + suffix);
                    string dst = Path.Combine(DstDir, piece + suffix);
                    if (!File.Exists(src))
                    {
                        Debug.LogWarning("[InteriorKit] 缺文件，跳过：" + src);
                        continue;
                    }
                    File.Copy(src, dst, true);
                    copied.Add(dst);
                }
            }
            AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate);

            // ---- 贴图导入设置 ----
            foreach (var piece in Pieces)
            {
                SetTexture(Path.Combine(DstDir, piece + "_albedo.png"), false);
                SetTexture(Path.Combine(DstDir, piece + "_normal.png"), true);
            }

            // ---- 模型导入设置：不要自动材质，外壳要 collider 用来测门洞 ----
            foreach (var piece in Pieces)
            {
                SetModel(Path.Combine(DstDir, piece + ".fbx"), piece == "interior_house_a" ||
                                                          piece == "interior_shop_a" ||
                                                          piece == "interior_inn_a");
            }
            AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate);

            // ---- 每件一条材质 ----
            foreach (var piece in Pieces)
            {
                EnsureMaterial(piece);
            }

            AssetDatabase.SaveAssets();
            Debug.Log("[InteriorKit] 导入完成：" + Pieces.Length + " 件，复制文件 " + copied.Count + " 个，材质 " + Pieces.Length + " 条。");
        }

        private static void SetTexture(string assetPath, bool normal)
        {
            var imp = AssetImporter.GetAtPath(assetPath) as TextureImporter;
            if (imp == null) return;
            imp.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
            imp.sRGBTexture = !normal;
            imp.mipmapEnabled = true;
            imp.maxTextureSize = 2048;
            imp.wrapMode = TextureWrapMode.Clamp;
            imp.filterMode = FilterMode.Trilinear;
            imp.SaveAndReimport();
        }

        private static void SetModel(string assetPath, bool addCollider)
        {
            var imp = AssetImporter.GetAtPath(assetPath) as ModelImporter;
            if (imp == null) return;
            // FBX 里根节点自带 scale 100（Blender 的厘米补偿），Unity 再用 fileScale 0.01 抵消，
            // 两者相乘正好 1 米。所以这里两个值都必须保持原样，不要"修正"。
            imp.globalScale = 1f;
            imp.useFileScale = true;
            imp.importAnimation = false;
            imp.importBlendShapes = false;
            imp.materialImportMode = ModelImporterMaterialImportMode.None;   // 材质由我们自己给（importMaterials 在 Unity 6 已移除）
            imp.meshCompression = ModelImporterMeshCompression.Off;
            imp.addCollider = addCollider;
            imp.isReadable = false;
            imp.animationType = ModelImporterAnimationType.None;
            imp.SaveAndReimport();
        }

        public static Material EnsureMaterial(string piece)
        {
            string path = MatDir + "/M_Interior_" + piece + ".mat";
            var albedo = AssetDatabase.LoadAssetAtPath<Texture2D>(DstDir + "/" + piece + "_albedo.png");
            var normal = AssetDatabase.LoadAssetAtPath<Texture2D>(DstDir + "/" + piece + "_normal.png");

            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                var shader = Shader.Find("Universal Render Pipeline/Lit");
                if (shader == null) shader = Shader.Find("Standard");
                mat = new Material(shader);
                AssetDatabase.CreateAsset(mat, path);
            }
            mat.SetTexture("_BaseMap", albedo);
            mat.SetTexture("_MainTex", albedo);
            mat.SetTexture("_BumpMap", normal);
            if (normal != null) mat.EnableKeyword("_NORMALMAP");
            else mat.DisableKeyword("_NORMALMAP");
            mat.SetFloat("_BumpScale", 1f);
            mat.SetFloat("_Metallic", 0f);
            mat.SetFloat("_Smoothness", 0.28f);
            mat.SetColor("_BaseColor", Color.white);
            EditorUtility.SetDirty(mat);
            return mat;
        }

        /// <summary>把一件 FBX 实例化到给定父物体下，所有槽位都指向它的图集材质。</summary>
        public static GameObject InstantiatePiece(string piece, Transform parent, string childName)
        {
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>(DstDir + "/" + piece + ".fbx");
            if (asset == null)
            {
                Debug.LogError("[InteriorKit] 找不到模型：" + piece + ".fbx（先跑 ① 导入）");
                return null;
            }
            var go = UnityEngine.Object.Instantiate(asset);
            go.name = childName;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = Vector3.zero;
            // 关键：**不要**碰 localRotation / localScale。
            // FBX 根节点自带 (270.02, 0, 0) 的 X 轴转换旋转和 scale=100 的厘米补偿，
            // 这两者合起来才把 Blender 的 Z-up 几何摆成 Unity 的 Y-up 米制。
            // 之前在这里写 localScale=one / localRotation=identity，导致整栋房子躺平（实测踩过两次）。
            // 注意：这里绝对不能把 localScale 设成 one。FBX 根节点带着 scale=100
            // （Blender 厘米补偿），压平它会让整座房子变成 6 厘米。实测过一次，记住。

            var mat = EnsureMaterial(piece);
            foreach (var r in go.GetComponentsInChildren<Renderer>(true))
            {
                var mats = new Material[r.sharedMaterials.Length];
                for (int i = 0; i < mats.Length; i++) mats[i] = mat;
                r.sharedMaterials = mats;
                r.shadowCastingMode = ShadowCastingMode.On;
            }
            return go;
        }

        [MenuItem("Tools/My World/室内②测量门洞与朝向", priority = 66)]
        public static void Measure()
        {
            if (EditorApplication.isPlaying)
            {
                Debug.LogError("[InteriorKit] 先退出 Play 再测量。");
                return;
            }
            var root = new GameObject("__InteriorMeasure");
            try
            {
                var shell = InstantiatePiece("interior_house_a", root.transform, "Shell");
                if (shell == null) return;
                Physics.SyncTransforms();

                // 从屋外 5 m 处朝屋心打射线：门洞那侧会一路穿到对面内墙，距离明显更大。
                var probes = new (string name, Vector3 from, Vector3 dir)[]
                {
                    ("+X", new Vector3(5f, 1f, 0f), new Vector3(-1f, 0f, 0f)),
                    ("-X", new Vector3(-5f, 1f, 0f), new Vector3(1f, 0f, 0f)),
                    ("+Z", new Vector3(0f, 1f, 5f), new Vector3(0f, 0f, -1f)),
                    ("-Z", new Vector3(0f, 1f, -5f), new Vector3(0f, 0f, 1f)),
                };
                var sb = new System.Text.StringBuilder();
                sb.Append("[InteriorKit] shell ").Append(DescribeBounds(shell)).Append("\n");
                foreach (var p in probes)
                {
                    RaycastHit h;
                    bool hit = Physics.Raycast(p.from, p.dir, out h, 12f);
                    sb.Append("  ").Append(p.name).Append(": ")
                      .Append(hit ? "hit@" + h.distance.ToString("F2") : "NO HIT").Append("\n");
                }
                Debug.Log(sb.ToString());
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(root);
            }
        }

        // ---- 实测出来的几何契约（interior_house_a，本工程单位：米）----
        // 外壳 6.30 x 5.24 x 2.92（含倒角/檐口），门在 +Z 面，门洞中心 (0, 0, 2.50)，宽 1.05。
        // 门板网格自身沿 -X 展开（Blender 轴转换后 X 反向），铰链在网格原点，
        // 所以 DoorPivot 必须放在门洞 +X 边沿：(0.525, 0, 2.50)，绕 Y 转 -95 度往屋里开。
        public const float DoorHingeX = 0.525f;
        public const float DoorHingeZ = 2.50f;
        public const float DoorOpenAngle = -95f;

        // 注意：带参数的公开方法**不能**挂 [MenuItem]——Unity 只允许 MenuCommand 作为可选参数，
        // 挂了会报 "has invalid parameters" 并且菜单不注册。所以这里拆成"带参实现 + 无参菜单壳"。
        [MenuItem("Tools/My World/室内③生成可进入房屋 Prefab", priority = 67)]
        public static void BuildPrefabMenu()
        {
            var go = BuildPrefab("interior_house_a", "InteriorHouse_A");
            if (go != null) Selection.activeObject = go;
        }

        [MenuItem("Tools/My World/室内③b 生成商铺与旅店 Prefab", priority = 67)]
        public static void BuildShopInnPrefabsMenu()
        {
            var shop = BuildPrefab("interior_shop_a", "InteriorShop_A");
            var inn = BuildPrefab("interior_inn_a", "InteriorInn_A");
            if (shop != null || inn != null)
                Selection.activeObject = shop != null ? (UnityEngine.Object)shop : inn;
        }

        /// <summary>
        /// 场景重建时用：prefab 已存在就复用，不存在才现场装配。
        /// 不弹窗、不依赖菜单，避免批处理/场景生成被模态框卡住。
        /// </summary>
        public static GameObject EnsurePrefab(string housePiece, string prefabName)
        {
            string path = "Assets/Generated/Interiors/" + prefabName + ".prefab";
            var existing = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (existing != null) return existing;
            return BuildPrefab(housePiece, prefabName);
        }

        public static GameObject BuildPrefab(string housePiece, string prefabName)
        {
            if (EditorApplication.isPlaying)
            {
                Debug.LogError("[InteriorKit] 先退出 Play 再生成 prefab。");
                return null;
            }
            var root = new GameObject(prefabName);
            try
            {
                var shell = InstantiatePiece(housePiece, root.transform, "Shell");
                if (shell == null) return null;
                var roof = InstantiatePiece("interior_house_a_roof", root.transform, "Roof");

                var pivot = new GameObject("DoorPivot");
                pivot.transform.SetParent(root.transform, false);
                pivot.transform.localPosition = new Vector3(DoorHingeX, 0f, DoorHingeZ);
                pivot.transform.localRotation = Quaternion.identity;
                InstantiatePiece("door_leaf", pivot.transform, "DoorLeaf");
                // 关着的门要能挡住人：碰撞盒挂在 DoorPivot（scale=1）上，跟着门一起转。
                // 门板网格沿 -X 展开 0.98、高 2.08、厚 0.19，所以中心在 x=-0.49。
                var doorCol = pivot.AddComponent<BoxCollider>();
                doorCol.center = new Vector3(-0.49f, 1.04f, 0.04f);
                doorCol.size = new Vector3(0.98f, 2.08f, 0.19f);

                string dir = "Assets/Generated/Interiors";
                Directory.CreateDirectory(dir);
                string path = dir + "/" + prefabName + ".prefab";

                // 组件由 EnterableHouseSetup 负责（那是 31b0c442 的模块，这里只按名字反射调用，
                // 避免两边互相引用；它挂组件 + 算内缩触发体，我们只保证 Robo/DoorPivot 名字对）。
                bool wired = WireEnterable(root);

                var saved = PrefabUtility.SaveAsPrefabAsset(root, path);
                Debug.Log("[InteriorKit] prefab 已保存：" + path +
                          "  shell=" + DescribeBounds(shell) +
                          "  roof=" + (roof != null ? DescribeBounds(roof) : "null") +
                          "  hinge=(" + DoorHingeX + ",0," + DoorHingeZ + ")  开门角=" + DoorOpenAngle +
                          "  组件已挂=" + wired);
                return saved;
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(root);
            }
        }

        /// <summary>
        /// 反射调用 31b0c442 的 EnterableHouseSetup.SetupHouse(root, verbose) 给房子挂组件。
        /// 那边挂了它们自己改签名也不会让我这边编译不过，只会返回 false。
        /// </summary>
        private static bool WireEnterable(GameObject root)
        {
            var t = System.Type.GetType("MyWorldEditorTools.EnterableHouseSetup, Assembly-CSharp-Editor");
            if (t == null)
            {
                Debug.LogWarning("[InteriorKit] 找不到 EnterableHouseSetup，先只存结构，稍后再挂组件。");
                return false;
            }
            foreach (var m in t.GetMethods(System.Reflection.BindingFlags.Public |
                                           System.Reflection.BindingFlags.NonPublic |
                                           System.Reflection.BindingFlags.Static))
            {
                if (m.Name != "SetupHouse") continue;
                var ps = m.GetParameters();
                if (ps.Length < 1 || ps[0].ParameterType != typeof(GameObject)) continue;
                var args = new object[ps.Length];
                args[0] = root;
                for (int i = 1; i < ps.Length; i++)
                    args[i] = ps[i].ParameterType == typeof(bool) ? (object)false : null;
                try
                {
                    m.Invoke(null, args);
                    return true;
                }
                catch (Exception e)
                {
                    Debug.LogWarning("[InteriorKit] SetupHouse 调用失败：" + e.Message);
                    return false;
                }
            }
            Debug.LogWarning("[InteriorKit] EnterableHouseSetup 里没有 SetupHouse(GameObject,...)。");
            return false;
        }

        [MenuItem("Tools/My World/室内④把房屋摆进当前场景", priority = 68)]
        public static void PlaceInCurrentScene()
        {
            if (EditorApplication.isPlaying)
            {
                Debug.LogError("[InteriorKit] 先退出 Play 再摆房子。");
                return;
            }
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Generated/Interiors/InteriorHouse_A.prefab");
            if (prefab == null)
            {
                Debug.LogError("[InteriorKit] 还没有 InteriorHouse_A.prefab，先跑 ③。");
                return;
            }
            var scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
            var root = new GameObject("InteriorHouse_A");
            UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(root, scene);
            // 摆在玩家出生点 (0,0.2,-11) 东侧一点，正对街道：面朝 -Z（门在 +Z，转 180 度让门朝街）
            root.transform.position = new Vector3(11.5f, 0f, -13.5f);
            root.transform.rotation = Quaternion.Euler(0f, 180f, 0f);

            var inst = PrefabUtility.InstantiatePrefab(prefab, scene) as GameObject;
            if (inst == null)
            {
                UnityEngine.Object.DestroyImmediate(root);
                Debug.LogError("[InteriorKit] prefab 实例化失败。");
                return;
            }
            inst.name = "InteriorHouse_A";
            inst.transform.position = root.transform.position;
            inst.transform.rotation = root.transform.rotation;
            UnityEngine.Object.DestroyImmediate(root);

            UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(scene);
            bool saved = UnityEditor.SceneManagement.EditorSceneManager.SaveScene(scene);
            Debug.Log("[InteriorKit] 已摆入 " + scene.name + " @ (11.5, 0, -13.5) rotY=180  保存=" + saved);
            Selection.activeGameObject = inst;
        }

        public static string DescribeBounds(GameObject go)
        {
            var renderers = go.GetComponentsInChildren<Renderer>(true);
            if (renderers.Length == 0) return "no renderer";
            var b = renderers[0].bounds;
            foreach (var r in renderers) b.Encapsulate(r.bounds);
            return string.Format("min=({0:F2},{1:F2},{2:F2}) max=({3:F2},{4:F2},{5:F2}) size=({6:F2},{7:F2},{8:F2})",
                b.min.x, b.min.y, b.min.z, b.max.x, b.max.y, b.max.z, b.size.x, b.size.y, b.size.z);
        }
    }
}
