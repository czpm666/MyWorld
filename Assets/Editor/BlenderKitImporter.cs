using System.Collections.Generic;
using System.IO;
using MyWorld.Maps;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// Blender 中世纪 kit → Unity prefab 的导入管线（编辑期）。
    ///
    /// 数据流：
    ///   `Assets/Generated/MedievalKitBlender/*.fbx`   （Blender 侧导出，Y-up 已经烧进网格）
    ///        ↓ 两遍：先采样颜色，再建 prefab
    ///   `Assets/Generated/MedievalKitBlender/Prefabs/<件名>.prefab`
    ///        ↓ 汇总
    ///   `Assets/Resources/MedievalKitBlender/BlenderKitCatalog.asset`  （运行时名字 → prefab）
    ///
    /// 设计要点：
    /// 1. **两遍**。第一遍只配置 FBX 导入参数并采样材质颜色（颜色只能从 Unity 自动导入的
    ///    Standard 材质里读到）；第二遍才建 prefab，并把材质换成 `Materials/` 下的**共享** URP/Lit 资源。
    ///    为什么非要共享：FBX 是逐件导出的，同一块木头在 30 个 FBX 里会出现 30 次；
    ///    若各用各的材质，批处理全废。按"材质名"归一化之后，整座城的木材是同一个 Material。
    ///    ⚠️ 2026-10-19 口径更新：**albedo 图集不挂**（`UseAlbedoAtlas = false`）。实测 house_a 的 `tile_0`
    ///    屋顶面在 Unity 里按 UV 质心采到的是奶油白（烤箱 UV 岛打包串味，见 Temp/kit_slot_material_report.md），
    ///    而**调色板是作者值、不依赖 UV**，所以 BaseColor 一律走调色板 / FBX 常色。
    ///    normal 图集照挂（`UseNormalMap = true`，`{件}_normal.png` → `_BumpMap` + 开 `_NORMALMAP`）。
    ///    材质粒度 = **每件 × 每槽位**（`M_BlenderKit_` + 件名 + `_` + 槽位名 + `.mat`）：槽位材质本来跨件共享
    ///    （`M_BlenderKit_plaster_0.mat` 同时给 house_a / house_f 用），而 normal 图集是逐件的，共享名装不下。
    /// 2. 合并网格与碰撞体**复用运行时那套** <see cref="Kit.Optimize"/>（它 edit 期走 DestroyImmediate，
    ///    是安全的），不另写一份合并逻辑 —— 少一份会走样的代码。
    /// 3. 每个件都打一行客观数据（三角面/包围盒米数/材质/shader/碰撞体），
    ///    因为"Blender 导出的尺寸对不对"只能靠量，不能靠看。
    /// </summary>
    public static class BlenderKitImporter
    {
        // ---------------------------------------------------------------- 路径
        public const string KitRoot = "Assets/Generated/MedievalKitBlender";
        public const string PrefabDir = KitRoot + "/Prefabs";
        public const string MaterialDir = KitRoot + "/Materials";
        public const string ScratchDir = KitRoot + "/_smoke";
        public const string CatalogDir = "Assets/Resources/MedievalKitBlender";
        public const string CatalogPath = CatalogDir + "/BlenderKitCatalog.asset";
        public const string PalettePath = KitRoot + "/kit_palette.json";
        public const string PreviewShotPath = "Temp/BlenderKit/blender_kit_preview.png";

        /// <summary>材质统一参数（与 `Docs/Rudeus/交付说明.md` 的 Rudeus 配方同源：URP/Lit、Metallic 0）。</summary>
        private const float KitSmoothness = 0.35f;
        private const float KitMetallic = 0f;
        private const string UrpLitShader = "Universal Render Pipeline/Lit";

        /// <summary>Blender 侧烘焙出来的贴图名后缀（图就放在 FBX 同目录 `E:\My World\Blender\export\`）。</summary>
        private const string AlbedoSuffix = "_albedo";
        private const string NormalSuffix = "_normal";

        /// <summary>贴图复制进工程后的落脚点（Unity 只认 `Assets/` 下的资源，工程外的 png 加载不了）。</summary>
        public const string TextureDir = KitRoot + "/Textures";

        /// <summary>
        /// 是否把按件的 albedo 图集挂到 `_BaseMap`。
        ///
        /// **默认 false —— 这是 Lead 定的口径**：整套烘焙图集的 UV 岛与材质对应不可靠。
        /// 证据：单独一块铺满的 `mat_tile` 烘出来是 `#81402D` 深砖红（正确），但 house_a 整件图集里
        /// `tile_0` 那两个 40° 屋顶斜面的 UV 质心采到的是 `#D4C8AF` 奶油白（≈ `plaster_0`），
        /// 这就是屋顶发白的根因（`smart_project` 的岛打包，既不是材质也不是 DIFFUSE/EMIT 路径）。
        /// 调色板的颜色是**作者值、完全不依赖 UV**，所以 BaseColor 一律走调色板；albedo 图集留在
        /// `Textures/` 里不入材质（Lead 要留作后续排查，别删）。
        /// </summary>
        /// <summary>
        /// 是否把按件的 albedo 图集挂到 `_BaseMap`。
        /// ⚠️ 2026-10-19 实测（house_a 双角度截图）：**图集在屋顶那块是错的** —— 屋顶渲染成米白/
        /// 奶油色（≈#EDE3C8），不是 tile_0 的红棕 #8F4632；墙面颗粒、木构架、绿百叶、木门、石裙
        /// 在图集里倒是对的。所以维持"调色板纯色"口径，图集只作**实验**用途：
        /// 把这里改成 true（配合 AlbedoAtlasPieces 白名单）再跑一次导入即可复现。
        /// </summary>
        private static readonly bool UseAlbedoAtlas = false;

        /// <summary>只对这些件挂 albedo 图集（图集实验白名单）。空数组 = 全部件都挂。</summary>
        private static readonly string[] AlbedoAtlasPieces = { "house_a" };

        private static bool WantAlbedoAtlas(string pieceKey)
        {
            if (!UseAlbedoAtlas) return false;
            if (AlbedoAtlasPieces == null || AlbedoAtlasPieces.Length == 0) return true;
            for (int i = 0; i < AlbedoAtlasPieces.Length; i++)
                if (string.Equals(AlbedoAtlasPieces[i], pieceKey, System.StringComparison.OrdinalIgnoreCase)) return true;
            return false;
        }

        /// <summary>
        /// 是否把按件的 normal 图集挂到 `_BumpMap`（并打开 `_NORMALMAP`）。
        ///
        /// **默认 true，法线图是本轮硬验收项**：normal 图集不参与颜色判定，UV 岛错位只影响凹凸细节
        /// 落在哪，不会让整块面变成错的颜色，所以照挂。
        /// </summary>
        private static readonly bool UseNormalMap = true;

        /// <summary>
        /// 合并同材质网格（走 <see cref="Kit.Optimize"/>）。
        ///
        /// **默认关，而且是多材质件的硬性要求**：Blender 导出的房子已经是「1 个 mesh + N 个材质槽」，
        /// 而 `Kit.Optimize` 只按 `renderer.sharedMaterial`（= 第 0 个槽）分组，再调
        /// `CombineMeshes(mergeSubMeshes: true)` 把所有 submesh 并成一个 —— 后果是整栋房子
        /// 只剩第 0 个材质，木头/瓦片/玻璃/百叶的槽全部丢掉（= 一片白墙）。
        /// 单材质件（barrel/crate/…）想省 draw call 时可以临时切成 true。
        /// </summary>
        // 注意是 `static readonly` 而不是 `const`：`const false` 会让编译器把上面的 `Kit.Optimize` 调用
        // 判成"无法访问的代码"（CS0162），而这行本来就是留给单材质件临时切 true 的开关。
        private static readonly bool MergeMeshes = false;

        /// <summary>这些名字里带的关键词**不加**碰撞体（软东西：布、树、草、烟）。其余一律加。</summary>
        private static readonly string[] NoColliderTokens =
        {
            "awning", "cloth", "banner", "flag", "pennant", "bunting", "curtain", "drape",
            "rope", "vine", "tree", "bush", "shrub", "foliage", "grass", "leaf", "flower", "tuft",
            "smoke", "lantern", "candle", "chimney",
        };

        // ---------------------------------------------------------------- 菜单

        [MenuItem("Tools/My World/导入 Blender Kit", false, 40)]
        public static void ImportAll()
        {
            PlayModeWarn("导入 Blender Kit");
            EnsureFolders();
            ResetColorStats();
            string[] fbx = FindFbx(KitRoot);
            if (fbx.Length == 0)
            {
                Debug.LogWarning("[BlenderKit] " + KitRoot + " 下没有 .fbx —— 等 Blender 侧导出后重跑本菜单。"
                                 + "（可以先用 `冒烟测试（借旧 FBX）` 验证管线本身。）");
                return;
            }

            var colors = new Dictionary<string, Color>();
            var ok = new List<string>();
            var fail = new List<string>();

            // 第一遍：配置导入参数 + 采样颜色
            foreach (string path in fbx)
            {
                if (!ConfigureImporter(path)) { fail.Add(Key(path)); continue; }
                var model = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                if (model == null) { fail.Add(Key(path)); continue; }
                CollectColors(model, colors);
                if (BuildPrefab(path, model, PrefabDir, colors) != null) ok.Add(Key(path));
                else fail.Add(Key(path));
            }

            AssetDatabase.SaveAssets();
            RefreshCatalog();

            Debug.Log("[BlenderKit] 导入完成：成功 " + ok.Count + " / 失败 " + fail.Count
                      + "（材质 " + colors.Count + " 种）。"
                      + (fail.Count > 0 ? " 失败：" + string.Join(", ", fail) : ""));

            var unmatched = new List<string>(UnmatchedSlots);
            unmatched.Sort(System.StringComparer.OrdinalIgnoreCase);
            Debug.Log("[BlenderKit] 配色来源：调色板 " + SlotsFromPalette + " 槽 / FBX 常色 " + SlotsFromFbx
                      + " 槽 / 白兜底 " + SlotsFromWhite + " 槽"
                      + (unmatched.Count > 0
                          ? "；未命中调色板的槽位名：" + string.Join(", ", unmatched)
                          : "；所有槽位都命中调色板。"));
        }

        [MenuItem("Tools/My World/导入 Blender Kit（仅选中的 FBX）", false, 41)]
        public static void ImportSelected()
        {
            EnsureFolders();
            var colors = new Dictionary<string, Color>();
            int done = 0;
            foreach (var obj in Selection.objects)
            {
                string path = AssetDatabase.GetAssetPath(obj);
                if (string.IsNullOrEmpty(path) || !path.ToLowerInvariant().EndsWith(".fbx")) continue;
                if (!ConfigureImporter(path)) continue;
                var model = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                if (model == null) continue;
                CollectColors(model, colors);
                if (BuildPrefab(path, model, PrefabDir, colors) != null) done++;
            }
            AssetDatabase.SaveAssets();
            RefreshCatalog();
            Debug.Log("[BlenderKit] 选中导入完成：" + done + " 个。");
        }

        [MenuItem("Tools/My World/验证 Blender Kit（尺寸/朝向/碰撞/材质）", false, 42)]
        public static void VerifyAll()
        {
            string[] prefabs = FindPrefabs(PrefabDir);
            if (prefabs.Length == 0) { Debug.LogWarning("[BlenderKit] " + PrefabDir + " 里还没有 prefab。"); return; }

            var problems = new List<string>();
            foreach (string path in prefabs)
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                if (prefab == null) { problems.Add(Key(path) + "：加载失败"); continue; }
                var msgs = Inspect(prefab);
                problems.AddRange(msgs);
            }

            if (problems.Count == 0)
                Debug.Log("[BlenderKit] 验证通过：" + prefabs.Length + " 个 prefab，没有发现问题。");
            else
                Debug.LogWarning("[BlenderKit] 验证发现 " + problems.Count + " 处可疑：\n  " + string.Join("\n  ", problems));
        }

        [MenuItem("Tools/My World/Blender Kit 轴换算自检（纯数学）", false, 43)]
        public static void AxisSelfTest()
        {
            int fails = 0;
            fails += Check("Blender +X → Unity +X", BlenderKitMapBuilder.BlenderPosToUnity(1f, 0f, 0f), new Vector3(1f, 0f, 0f));
            fails += Check("Blender +Y → Unity -Z", BlenderKitMapBuilder.BlenderPosToUnity(0f, 1f, 0f), new Vector3(0f, 0f, -1f));
            fails += Check("Blender +Z → Unity +Y", BlenderKitMapBuilder.BlenderPosToUnity(0f, 0f, 1f), new Vector3(0f, 1f, 0f));
            fails += Check("Blender (2,3,4) → Unity (2,4,-3)", BlenderKitMapBuilder.BlenderPosToUnity(2f, 3f, 4f), new Vector3(2f, 4f, -3f));

            // 朝向：Blender 里绕 +Z 转 90°，件的局部 +X 指向 Blender +Y → 映射到 Unity -Z。
            // Unity 侧 `Quaternion.Euler(0, 90, 0)` 作用在 +X 上必须得到同一个方向，否则就是朝向反了。
            Vector3 unityYaw90 = Quaternion.Euler(0f, BlenderKitMapBuilder.BlenderYawToUnity(90f), 0f) * Vector3.right;
            fails += Check("Blender rot_z=90 的局部 +X → Unity -Z", unityYaw90, new Vector3(0f, 0f, -1f));

            Vector3 unityYaw0 = Quaternion.Euler(0f, BlenderKitMapBuilder.BlenderYawToUnity(0f), 0f) * Vector3.forward;
            fails += Check("rot_z=0 的局部 +Z → Unity +Z（不转）", unityYaw0, new Vector3(0f, 0f, 1f));

            if (fails == 0) Debug.Log("[BlenderKit] 轴换算自检：6/6 通过。");
            else Debug.LogError("[BlenderKit] 轴换算自检：有 " + fails + " 项不通过 —— 先别信版面，改 BlenderKitMapBuilder 里的换算。");
        }

        /// <summary>
        /// Play 模式硬守卫：进了 Play 之后 `EditorSceneManager.NewScene` 会直接抛
        /// `InvalidOperationException: This cannot be used during play mode`（08:5x 就这么炸过一次）。
        /// 返回 true = 调用方应当立刻 return。
        /// </summary>
        private static bool PlayModeBlock(string what)
        {
            if (!EditorApplication.isPlaying && !EditorApplication.isPlayingOrWillChangePlaymode) return false;
            Debug.LogWarning("[BlenderKit] " + what + "：当前在 Play 模式，已跳过。"
                             + "进 Play 时建场景 / 写 Assets / 触发域重载都会打断 Play 会话，请先停止 Play。");
            return true;
        }

        /// <summary>Play 模式下只警告不拦：导入是显式操作，但要说清代价（写 Assets 必然触发域重载）。</summary>
        private static void PlayModeWarn(string what)
        {
            if (!EditorApplication.isPlaying) return;
            Debug.LogWarning("[BlenderKit] " + what + "：当前在 Play 模式，导入会写 Assets 并触发域重载，"
                             + "可能打断正在跑的 Play 会话（预览截图已被禁用）。");
        }

        [MenuItem("Tools/My World/Blender Kit 预览截图", false, 44)]
        public static void CapturePreview()
        {
            if (PlayModeBlock("预览截图")) return;
            EnsureFolders();
            string layoutPath = BlenderKitMapBuilder.LayoutPath(BlenderKitMapBuilder.DefaultLayoutFile);

            // 全程在**临时 additive 场景**里搭预览：直接在当前场景 new GameObject 会把当前场景标脏，
            // 而现在 RoaTown 是 village-dev 的工作场景，一个脏标记就可能害他误存。
            var prevScene = SceneManager.GetActiveScene();
            var previewScene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
            SceneManager.SetActiveScene(previewScene);

            var temp = new GameObject("__BlenderKitPreview");
            // 摆到 10km 外：独立场景里本来也不会互相拍，但留着这层保险无害
            temp.transform.position = new Vector3(10000f, 0f, 10000f);

            string label;
            try
            {
                if (File.Exists(layoutPath))
                {
                    label = "layout JSON（" + Path.GetFileName(layoutPath) + "）";
                    BlenderKitMapBuilder.Build(temp.transform);
                }
                else if (AssetDatabase.LoadAssetAtPath<BlenderKitCatalog>(CatalogPath) != null
                         || FindPrefabs(PrefabDir).Length > 0)
                {
                    label = "网格排布（还没有 layout JSON，退化成全部 prefab 铺开）";
                    BuildGrid(temp.transform);
                }
                else
                {
                    Debug.LogWarning("[BlenderKit] 既没有 " + layoutPath + "，也没有 prefab，没东西可拍。");
                    return;
                }

                BlenderKitMapBuilder.LogPlacements(temp, 12);

                var bounds = BoundsOf(temp);
                if (bounds.size == Vector3.zero) { Debug.LogWarning("[BlenderKit] 预览内容为空，跳过截图。"); return; }

                RenderToPng(bounds, PreviewShotPath, 1024);
                // Temp/ 不用刷新：白白触发一次导入扫描没必要（截图也不该进 Assets，见 Play 纪律）
                if (PreviewShotPath.StartsWith("Assets/")) AssetDatabase.Refresh();
                Debug.Log("[BlenderKit] 预览截图（" + label + "）：" + PreviewShotPath
                          + "，包围盒 " + bounds.size.ToString("0.##") + " 米");
            }
            finally
            {
                Object.DestroyImmediate(temp);
                if (prevScene.IsValid()) SceneManager.SetActiveScene(prevScene);
                EditorSceneManager.CloseScene(previewScene, true);   // 不保存，直接扔掉
            }
        }

        [MenuItem("Tools/My World/刷新 Blender Kit 目录资源", false, 45)]
        public static void RefreshCatalogMenu()
        {
            EnsureFolders();
            RefreshCatalog();
            Debug.Log("[BlenderKit] 目录已刷新：" + CatalogPath);
        }

        [MenuItem("Tools/My World/冒烟测试：借旧 MedievalKit FBX 跑新管线", false, 46)]
        public static void SmokeTestLegacy()
        {
            EnsureFolders();
            string src = "Assets/Generated/MedievalKit/barrel.fbx";
            if (!File.Exists(src)) src = (FindFbx("Assets/Generated/MedievalKit").Length > 0)
                ? FindFbx("Assets/Generated/MedievalKit")[0] : null;
            if (src == null) { Debug.LogError("[BlenderKit] 找不到可借用的旧 FBX。"); return; }

            if (!ConfigureImporter(src)) { Debug.LogError("[BlenderKit] 冒烟测试：导入参数配置失败。"); return; }
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(src);
            if (model == null) { Debug.LogError("[BlenderKit] 冒烟测试：加载失败 " + src); return; }

            var colors = new Dictionary<string, Color>();
            CollectColors(model, colors);
            var prefab = BuildPrefab(src, model, ScratchDir, colors);
            AssetDatabase.SaveAssets();
            if (prefab == null) { Debug.LogError("[BlenderKit] 冒烟测试：建 prefab 失败。"); return; }

            var problems = Inspect(prefab);
            Debug.Log("[BlenderKit] 冒烟测试完成：源 " + src + " → " + AssetDatabase.GetAssetPath(prefab)
                      + (problems.Count == 0 ? "，各项检查通过。" : "，可疑 " + problems.Count + " 处：\n  " + string.Join("\n  ", problems))
                      + "\n（产物在 " + ScratchDir + "，确认后可跑 `清理 Blender Kit 冒烟产物` 删掉。）");
        }

        [MenuItem("Tools/My World/清理 Blender Kit 冒烟产物", false, 47)]
        public static void CleanScratch()
        {
            if (AssetDatabase.IsValidFolder(ScratchDir))
            {
                AssetDatabase.DeleteAsset(ScratchDir);
                AssetDatabase.Refresh();
                Debug.Log("[BlenderKit] 已删除冒烟产物：" + ScratchDir);
            }
            else Debug.Log("[BlenderKit] 没有冒烟产物可删。");
        }

        // ---------------------------------------------------------------- 导入

        /// <summary>统一 FBX 导入参数。返回 false 表示配置失败（会让上层记一次失败）。</summary>
        private static bool ConfigureImporter(string fbxPath)
        {
            var importer = AssetImporter.GetAtPath(fbxPath) as ModelImporter;
            if (importer == null)
            {
                Debug.LogError("[BlenderKit] 找不到 ModelImporter：" + fbxPath);
                return false;
            }

            importer.globalScale = 1f;              // Blender 侧就是米，绝不缩放
            importer.useFileScale = true;
            importer.animationType = ModelImporterAnimationType.None;
            importer.importAnimation = false;
            importer.importBlendShapes = false;
            importer.importCameras = false;
            importer.importLights = false;
            importer.addCollider = false;           // 碰撞体由本管线按名字策略加
            importer.importVisibility = false;
            importer.bakeAxisConversion = false;    // 轴转换由 Blender 的 FBX 导出器负责，这里重复转就会转两次
            importer.isReadable = true;             // Kit.Optimize 要读顶点来合并
            importer.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            importer.materialSearch = ModelImporterMaterialSearch.Everywhere;
            importer.materialLocation = ModelImporterMaterialLocation.External;   // 颜色来源：可读的 .mat 资产
            importer.SaveAndReimport();
            return true;
        }

        /// <summary>
        /// 从 FBX 的自动导入材质里采颜色。**只取第一次出现的**：同一个材质名在多个 FBX 里重复时，
        /// 先导入的那个说了算（这样颜色是确定的，不会因为导入顺序不同而变）。
        /// </summary>
        private static void CollectColors(GameObject model, Dictionary<string, Color> colors)
        {
            foreach (var r in model.GetComponentsInChildren<Renderer>(true))
            {
                foreach (var m in r.sharedMaterials)
                {
                    if (m == null) continue;
                    string name = SanitizeName(m.name);
                    if (colors.ContainsKey(name)) continue;
                    colors[name] = ReadColor(m);
                }
            }
        }

        private static Color ReadColor(Material m)
        {
            if (m.HasProperty("_BaseColor")) return m.GetColor("_BaseColor");
            if (m.HasProperty("_Color")) return m.GetColor("_Color");
            return m.color;
        }

        /// <summary>建 prefab：克隆 FBX 层级 → 换共享材质 → 合并 → 存盘。返回存下来的 prefab。</summary>
        private static GameObject BuildPrefab(string fbxPath, GameObject model, string outDir, Dictionary<string, Color> colors)
        {
            string key = Key(fbxPath);
            if (!AssetDatabase.IsValidFolder(outDir))
            {
                Debug.LogError("[BlenderKit] 输出目录不存在：" + outDir);
                return null;
            }

            // 新根挂在原点，FBX 自带的根变换原样保留在 `Model` 子节点下 ——
            // 万一导出器在根上带了旋转/缩放，这里不会把它抹掉（抹掉就变成"朝向不对"了）。
            var root = new GameObject(key);
            var inner = Object.Instantiate(model, root.transform);
            inner.name = "Model";
            // 根上的旋转/缩放是 Blender 导出的标准 Z-up→Y-up 换算 + 单位换算：
            // 实测尺寸/朝向都对（门朝 −Z、底面 y=0、7.53×8.95×6.51），所以**刻意不动它** ——
            // 抹掉它反而会变成"朝向/尺寸不对"。这里只留一行中性事实日志，不是告警。
            if (inner.transform.localRotation != Quaternion.identity || inner.transform.localScale != Vector3.one)
                Debug.Log("[BlenderKit] " + key + "：FBX 模型节点带标准 Z-up→Y-up 变换（rot "
                          + inner.transform.localRotation.eulerAngles.ToString("0.##")
                          + " / scale " + inner.transform.localScale.ToString("0.###")
                          + "），已由导入器归一化，无需处理。");

            AssignSharedMaterials(root, colors);

            bool wantCollider = ColliderPolicy(key);
            if (MergeMeshes) Kit.Optimize(root, wantCollider);
            else if (wantCollider) AddBoxCollider(root);

            string prefabPath = outDir + "/" + key + ".prefab";
            var prefab = PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
            Object.DestroyImmediate(root);

            if (prefab == null) { Debug.LogError("[BlenderKit] " + key + "：prefab 存盘失败 " + prefabPath); return null; }
            Report(key, prefab, wantCollider);
            return prefab;
        }

        /// <summary>
        /// 把 renderer 上的材质换成共享资源。
        ///
        /// **当前口径（Lead 决策）**：按件的 albedo 图集**不挂** `_BaseMap`（UV 岛与材质的对应不可靠，
        /// 屋顶会采到奶油白），可见色改用调色板的「作者值」；按件的 **normal 图集继续挂** `_BumpMap`
        /// 并打开 `_NORMALMAP`。
        ///
        /// 材质粒度 = 「件 + 槽位」：`M_BlenderKit_&lt;件名&gt;_&lt;槽位名&gt;.mat`。为什么不直接共用
        /// `M_BlenderKit_&lt;槽位名&gt;.mat`：槽位名**跨件重名**（house_a 和 house_f 都有 `plaster_0`），
        /// 而 normal 图是按件烘的 —— 共用一条材质就只能挂其中一件的法线图，另一件必错。
        /// 没解析出 normal 图的件退回跨件共享的槽位调色板材质（13 条 `M_BlenderKit_*.mat` 仍在用）。
        /// </summary>
        // ---------------------------------------------------------------- 调色板查找 / 配色统计
        // 作者值只写在 kit_palette.json 里，而槽位名是 Blender 给的（`glass.022`、`stone_step`、`plaster_0`），
        // 所以按**大小写无关的最长前缀**匹配：`stone_step` 先于 `stone`，`cloth_bloom` 先于（将来的）`cloth`。
        private static int SlotsFromPalette, SlotsFromFbx, SlotsFromWhite;
        private static readonly HashSet<string> UnmatchedSlots = new HashSet<string>(System.StringComparer.OrdinalIgnoreCase);

        private static void ResetColorStats()
        {
            SlotsFromPalette = SlotsFromFbx = SlotsFromWhite = 0;
            UnmatchedSlots.Clear();
        }

        /// <summary>去掉 Blender 的去重后缀：`glass.022` / `glass_022` → `glass`，`plaster_0` → `plaster`。</summary>
        private static string StripBlenderDedup(string name)
        {
            if (string.IsNullOrEmpty(name)) return "";
            int cut = name.Length;
            while (cut > 0 && char.IsDigit(name[cut - 1])) cut--;
            if (cut > 0 && cut < name.Length && (name[cut - 1] == '.' || name[cut - 1] == '_')) cut--;
            return name.Substring(0, cut);
        }

        /// <summary>
        /// 调色板查找：大小写无关、**最长前缀优先**。返回 null = 没命中（调用方继续用 FBX 常色），
        /// 同时把没命中的槽位名记进 `UnmatchedSlots` —— 报告里据此告诉 Lead 该补哪些色。
        /// </summary>
        private static Color? PaletteLookup(Dictionary<string, Color> palette, string slotName)
        {
            if (palette == null || palette.Count == 0) return null;
            string stem = StripBlenderDedup(slotName);
            if (stem.Length == 0) return null;

            Color best = default(Color);
            int bestLen = 0;
            foreach (var kv in palette)
            {
                string k = kv.Key;
                if (string.IsNullOrEmpty(k) || k.Length <= bestLen) continue;
                if (stem.StartsWith(k, System.StringComparison.OrdinalIgnoreCase))
                {
                    best = kv.Value;
                    bestLen = k.Length;
                }
            }
            if (bestLen > 0) return best;

            UnmatchedSlots.Add(stem);
            return null;
        }

        /// <summary>
        /// 可见色优先级：`kit_palette.json` 作者值 &gt; FBX 常色 &gt; **白**。
        /// 明确**不再退 0.7 中灰** —— 灰色挨着奶油墙和砖红瓦太扎眼（2026-10-19 口径）。
        /// </summary>
        private static Color ResolveColor(Dictionary<string, Color> colors, Dictionary<string, Color> palette, string slotName)
        {
            var fromJson = PaletteLookup(palette, slotName);
            if (fromJson.HasValue) { SlotsFromPalette++; return fromJson.Value; }

            Color fromFbx;
            if (colors != null && colors.TryGetValue(slotName, out fromFbx)) { SlotsFromFbx++; return fromFbx; }

            SlotsFromWhite++;
            return Color.white;
        }

        private static void AssignSharedMaterials(GameObject root, Dictionary<string, Color> colors)
        {
            var cache = new Dictionary<string, Material>();
            var palette = LoadPalette();
            var missing = new List<string>();

            // normal 图是按件烘的：一件只解析一次，这件所有槽位共用同一张法线图。
            var normal = UseNormalMap ? EnsureTexture(root.name, NormalSuffix, true) : null;

            int slots = 0, textured = 0;
            foreach (var r in root.GetComponentsInChildren<Renderer>(true))
            {
                var src = r.sharedMaterials;
                if (src == null || src.Length == 0) continue;
                slots += src.Length;

                var dst = new Material[src.Length];
                for (int i = 0; i < src.Length; i++)
                {
                    if (src[i] == null) continue;
                    string slot = SanitizeName(src[i].name);

                    // 1) 有 normal 图 → 按「件 + 槽位」建/更新专属材质（色走调色板，法线挂本件的图）。
                    if (normal != null)
                    {
                        string key = root.name + "|" + slot;
                        if (!cache.TryGetValue(key, out var pieceSlot))
                        {
                            pieceSlot = ResolvePieceSlotMaterial(root.name, slot, normal, colors, palette);
                            cache[key] = pieceSlot;
                        }
                        if (pieceSlot != null)
                        {
                            dst[i] = pieceSlot;
                            textured++;
                            continue;
                        }
                    }

                    // 2) 兜底 → 跨件共享的槽位调色板材质。
                    if (!cache.TryGetValue(slot, out var shared))
                    {
                        shared = ResolveSharedMaterial(slot, colors, palette);
                        cache[slot] = shared;
                    }
                    if (shared == null) missing.Add(slot);
                    dst[i] = shared;
                }
                r.sharedMaterials = dst;
            }

            Debug.Log("[BlenderKit] " + root.name + "：槽位 " + slots + " 个，其中 " + textured
                      + " 个用本件材质（normal " + (normal != null ? "✓" : "—")
                      + "；BaseColor 走调色板作者值，albedo 图集不挂）。");

            if (missing.Count > 0)
                Debug.LogWarning("[BlenderKit] 有 " + missing.Count + " 个材质没解析出来（已留空）："
                                 + string.Join(", ", missing));
        }

        /// <summary>
        /// 按「件 + 槽位」建/更新材质：可见色 = `_BaseColor`（优先级与槽位材质一致：kit_palette.json
        /// &gt; FBX 自带 &gt; 中灰），`_BumpMap` = 本件的 `&lt;件&gt;_normal.png` 并打开 `_NORMALMAP`。
        /// `_BaseMap` 按当前口径留空（`UseAlbedoAtlas` 打开时才挂 albedo 图集）。
        /// </summary>
        private static Material ResolvePieceSlotMaterial(string pieceKey, string slotKey, Texture2D normal,
                                                         Dictionary<string, Color> colors, Dictionary<string, Color> palette)
        {
            var shader = Shader.Find(UrpLitShader);
            if (shader == null)
            {
                Debug.LogError("[BlenderKit] 找不到 shader `" + UrpLitShader + "` —— 这个工程不是 URP？材质无法转换。");
                return null;
            }

            string path = MaterialDir + "/M_BlenderKit_" + pieceKey + "_" + slotKey + ".mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            bool created = mat == null;
            if (created) mat = new Material(shader);
            if (mat.shader != shader) mat.shader = shader;

            // 颜色优先级：kit_palette.json 作者值（大小写无关最长前缀）> FBX 自带 > 白
            Color color = ResolveColor(colors, palette, slotKey);

            if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", color);
            if (mat.HasProperty("_Color")) mat.SetColor("_Color", color);

            if (mat.HasProperty("_BaseMap"))
            {
                if (WantAlbedoAtlas(pieceKey))
                {
                    var albedo = EnsureTexture(pieceKey, AlbedoSuffix, false);
                    if (albedo != null)
                    {
                        mat.SetTexture("_BaseMap", albedo);
                        // 颜色已经在贴图里，base color 必须回白 —— 否则会被调色板的颜色再乘一遍。
                        if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", Color.white);
                        if (mat.HasProperty("_Color")) mat.SetColor("_Color", Color.white);
                    }
                }
                else
                {
                    // 显式置空：改口径后要把上一版留下的贴图引用清掉。
                    mat.SetTexture("_BaseMap", null);
                }
            }

            if (UseNormalMap && normal != null)
            {
                if (mat.HasProperty("_BumpMap")) mat.SetTexture("_BumpMap", normal);
                if (mat.HasProperty("_BumpScale")) mat.SetFloat("_BumpScale", 1f);
                mat.EnableKeyword("_NORMALMAP");
            }

            if (mat.HasProperty("_Metallic")) mat.SetFloat("_Metallic", KitMetallic);
            if (mat.HasProperty("_Smoothness")) mat.SetFloat("_Smoothness", KitSmoothness);

            // 半透明：布幔/遮阳棚这类 FBX 里 alpha < 1 的按 URP 透明表面走（和槽位材质同规则）。
            bool transparent = color.a < 0.999f;
            if (mat.HasProperty("_Surface")) mat.SetFloat("_Surface", transparent ? 1f : 0f);
            if (transparent)
            {
                if (mat.HasProperty("_Blend")) mat.SetFloat("_Blend", 0f);
                if (mat.HasProperty("_ZWrite")) mat.SetFloat("_ZWrite", 0f);
                mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
                mat.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
            }
            else
            {
                mat.DisableKeyword("_SURFACE_TYPE_TRANSPARENT");
                mat.renderQueue = -1;
            }

            if (created) AssetDatabase.CreateAsset(mat, path);
            EditorUtility.SetDirty(mat);
            return mat;
        }

        /// <summary>
        /// 把 `&lt;件&gt;&lt;后缀&gt;.png` 从 Blender 的导出目录复制进 `Assets/Generated/MedievalKitBlender/Textures/`
        /// 并设好导入参数（法线图 = NormalMap / 非 sRGB；反照率 = sRGB，两张都开 mipmap）。
        /// 返回 null = 没有这张图（不是每件都烤了图，这是正常情况）。
        ///
        /// 为什么要复制：Unity 只能引用 `Assets/` 或 `Packages/` 下的资源，而 `E:\My World\Blender\export\`
        /// 在工程外，`AssetDatabase` 根本看不见。复制是单向的：只读 Blender 的图，绝不写那边。
        /// </summary>
        private static Texture2D EnsureTexture(string pieceKey, string suffix, bool isNormal)
        {
            string fileName = pieceKey + suffix + ".png";
            string src = Path.Combine(BlenderExportDir(), fileName);
            if (!File.Exists(src)) return null;

            EnsureFolder(TextureDir);
            string dest = TextureDir + "/" + fileName;
            string projectRoot = Directory.GetParent(Application.dataPath).FullName;
            string destAbs = Path.Combine(projectRoot, dest.Replace('/', Path.DirectorySeparatorChar));

            bool copied = false;
            if (!File.Exists(destAbs) || File.GetLastWriteTimeUtc(destAbs) < File.GetLastWriteTimeUtc(src))
            {
                File.Copy(src, destAbs, true);
                copied = true;
            }

            var importer = AssetImporter.GetAtPath(dest) as TextureImporter;
            if (importer == null || copied)
            {
                AssetDatabase.ImportAsset(dest, ImportAssetOptions.ForceUpdate);
                importer = AssetImporter.GetAtPath(dest) as TextureImporter;
            }
            if (importer == null)
            {
                Debug.LogWarning("[BlenderKit] 贴图导入失败：" + dest);
                return null;
            }

            // 只在参数不对时才 SaveAndReimport —— 每次重导都会让全工程重新加载这张图。
            var wantType = isNormal ? TextureImporterType.NormalMap : TextureImporterType.Default;
            bool dirty = importer.textureType != wantType
                         || importer.sRGBTexture != !isNormal
                         || !importer.mipmapEnabled
                         || importer.wrapMode != TextureWrapMode.Repeat
                         || importer.maxTextureSize != 2048
                         || importer.textureCompression != TextureImporterCompression.Compressed;
            if (dirty)
            {
                importer.textureType = wantType;
                importer.sRGBTexture = !isNormal;             // 法线图必须线性采样
                importer.mipmapEnabled = true;
                importer.wrapMode = TextureWrapMode.Repeat;   // 墙/瓦按 UV 平铺，别留接缝
                importer.filterMode = FilterMode.Bilinear;
                importer.anisoLevel = 4;
                importer.maxTextureSize = 2048;
                importer.textureCompression = TextureImporterCompression.Compressed;
                importer.npotScale = TextureImporterNPOTScale.None;
                importer.alphaIsTransparency = false;
                importer.SaveAndReimport();
            }

            return AssetDatabase.LoadAssetAtPath<Texture2D>(dest);
        }

        /// <summary>Blender 的导出目录（在工程根下：`Blender/export`）。只读，不写。</summary>
        private static string BlenderExportDir()
        {
            string root = Directory.GetParent(Application.dataPath).FullName;
            return Path.Combine(root, "Blender", "export");
        }

        private static Material ResolveSharedMaterial(string key, Dictionary<string, Color> colors, Dictionary<string, Color> palette)
        {
            var shader = Shader.Find(UrpLitShader);
            if (shader == null)
            {
                Debug.LogError("[BlenderKit] 找不到 shader `" + UrpLitShader + "` —— 这个工程不是 URP？材质无法转换。");
                return null;
            }

            string path = MaterialDir + "/M_BlenderKit_" + key + ".mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            bool created = mat == null;
            if (created) mat = new Material(shader);
            if (mat.shader != shader) mat.shader = shader;

            // 颜色优先级：kit_palette.json 作者值（大小写无关最长前缀）> FBX 自带 > 白
            Color color = ResolveColor(colors, palette, key);

            if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", color);
            if (mat.HasProperty("_Color")) mat.SetColor("_Color", color);
            if (mat.HasProperty("_Metallic")) mat.SetFloat("_Metallic", KitMetallic);
            if (mat.HasProperty("_Smoothness")) mat.SetFloat("_Smoothness", KitSmoothness);

            // 半透明：布幔这类 FBX 里 alpha < 1 的，按 URP 的透明表面走
            bool transparent = color.a < 0.999f;
            if (mat.HasProperty("_Surface")) mat.SetFloat("_Surface", transparent ? 1f : 0f);
            if (transparent)
            {
                if (mat.HasProperty("_Blend")) mat.SetFloat("_Blend", 0f);
                if (mat.HasProperty("_ZWrite")) mat.SetFloat("_ZWrite", 0f);
                mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
                mat.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
            }
            else
            {
                mat.DisableKeyword("_SURFACE_TYPE_TRANSPARENT");
                mat.renderQueue = -1;
            }

            if (created) AssetDatabase.CreateAsset(mat, path);
            EditorUtility.SetDirty(mat);
            return mat;
        }

        /// <summary>可选色表覆盖：`Assets/Generated/MedievalKitBlender/kit_palette.json`。</summary>
        private static Dictionary<string, Color> LoadPalette()
        {
            var dict = new Dictionary<string, Color>();
            if (!File.Exists(PalettePath)) return dict;
            try
            {
                var doc = JsonUtility.FromJson<PaletteDoc>(File.ReadAllText(PalettePath, System.Text.Encoding.UTF8));
                if (doc != null && doc.colors != null)
                {
                    foreach (var e in doc.colors)
                    {
                        if (e == null || string.IsNullOrEmpty(e.name) || string.IsNullOrEmpty(e.hex)) continue;
                        Color c;
                        if (ColorUtility.TryParseHtmlString(e.hex, out c)) dict[SanitizeName(e.name)] = c;
                        else Debug.LogWarning("[BlenderKit] kit_palette.json 里 \"" + e.name + "\" 的 hex 不合法：" + e.hex);
                    }
                    Debug.Log("[BlenderKit] 读到色表 " + PalettePath + "：" + dict.Count + " 条（会覆盖 FBX 自带颜色）。");
                }
            }
            catch (System.Exception e)
            {
                Debug.LogWarning("[BlenderKit] 读色表失败（忽略）：" + e.Message);
            }
            return dict;
        }

        [System.Serializable]
        private class PaletteDoc
        {
            // 显式初始化只是为了消掉 CS0649 —— JsonUtility 反序列化时照样会覆盖这些字段。
            public PaletteEntry[] colors = new PaletteEntry[0];
        }

        [System.Serializable]
        private class PaletteEntry
        {
            public string name = "";
            public string hex = "";
        }

        // ---------------------------------------------------------------- 碰撞 / 报告 / 校验

        private static bool ColliderPolicy(string key)
        {
            string k = key.ToLowerInvariant();
            foreach (string token in NoColliderTokens)
                if (k.Contains(token)) return false;
            return true;
        }

        private static void AddBoxCollider(GameObject root)
        {
            var bounds = BoundsOf(root);
            if (bounds.size == Vector3.zero) return;
            var bc = root.AddComponent<BoxCollider>();
            bc.center = root.transform.InverseTransformPoint(bounds.center);
            bc.size = bounds.size;
        }

        private static void Report(string key, GameObject prefab, bool collider)
        {
            int tris = 0;
            int renderers = 0;
            foreach (var mf in prefab.GetComponentsInChildren<MeshFilter>(true))
            {
                if (mf.sharedMesh == null) continue;
                tris += mf.sharedMesh.triangles.Length / 3;
                renderers++;
            }
            var bounds = BoundsOf(prefab);
            var shaders = new HashSet<string>();
            foreach (var r in prefab.GetComponentsInChildren<Renderer>(true))
                foreach (var m in r.sharedMaterials)
                    if (m != null) shaders.Add(m.shader != null ? m.shader.name : "<null>");

            Debug.Log("[BlenderKit] " + key + "：面 " + tris + "，块 " + renderers
                      + "，尺寸 " + bounds.size.ToString("0.###") + " 米"
                      + "，底面 y=" + bounds.min.y.ToString("0.###")
                      + "，碰撞体 " + (collider ? "有" : "无")
                      + "，shader [" + string.Join(", ", shaders) + "]");
        }

        /// <summary>检查一个 prefab，返回可疑点列表（空 = 干净）。</summary>
        private static List<string> Inspect(GameObject prefab)
        {
            var problems = new List<string>();
            string name = prefab.name;

            int tris = 0;
            int renderers = 0;
            foreach (var mf in prefab.GetComponentsInChildren<MeshFilter>(true))
            {
                if (mf.sharedMesh == null) { problems.Add(name + "：有 MeshFilter 但网格为空"); continue; }
                tris += mf.sharedMesh.triangles.Length / 3;
                if (!mf.sharedMesh.isReadable) problems.Add(name + "：网格不可读（isReadable=false）");
                renderers++;
            }
            if (renderers == 0) problems.Add(name + "：一个网格都没有");

            var bounds = BoundsOf(prefab);
            if (bounds.size == Vector3.zero) problems.Add(name + "：包围盒是 0");
            else
            {
                float maxDim = Mathf.Max(bounds.size.x, Mathf.Max(bounds.size.y, bounds.size.z));
                if (maxDim < 0.2f) problems.Add(name + "：最大边只有 " + maxDim.ToString("0.###") + " 米，疑似缩放过小");
                if (maxDim > 40f) problems.Add(name + "：最大边 " + maxDim.ToString("0.###") + " 米，疑似缩放过大（Blender 单位/导出缩放？）");
                if (bounds.min.y < -0.05f) problems.Add(name + "：底面 y=" + bounds.min.y.ToString("0.###") + " 低于 0，pivot 不在底面上");
                if (bounds.min.y > 1.0f) problems.Add(name + "：底面 y=" + bounds.min.y.ToString("0.###") + " 悬空，pivot 可能不在底面");
            }
            if (tris < 12) problems.Add(name + "：只有 " + tris + " 个面，疑似空壳");

            foreach (var r in prefab.GetComponentsInChildren<Renderer>(true))
            {
                foreach (var m in r.sharedMaterials)
                {
                    if (m == null) { problems.Add(name + "：有空的材质槽"); continue; }
                    if (m.shader == null || m.shader.name != UrpLitShader)
                        problems.Add(name + "：材质 " + m.name + " 用的 shader 是 `" + (m.shader != null ? m.shader.name : "<null>")
                                     + "`，不是 URP/Lit（在 URP 下会显示成洋红）");
                }
            }

            bool hasCollider = prefab.GetComponentInChildren<Collider>(true) != null;
            if (!hasCollider && ColliderPolicy(name))
                problems.Add(name + "：按名字策略应该有碰撞体，但没有");

            return problems;
        }

        // ---------------------------------------------------------------- 目录 / 工具

        /// <summary>扫描 prefab 目录，重建运行时目录资源。</summary>
        private static void RefreshCatalog()
        {
            string[] prefabPaths = FindPrefabs(PrefabDir);
            var catalog = AssetDatabase.LoadAssetAtPath<BlenderKitCatalog>(CatalogPath);
            bool created = catalog == null;
            if (created) catalog = ScriptableObject.CreateInstance<BlenderKitCatalog>();

            var entries = new List<BlenderKitCatalog.Entry>();
            foreach (string path in prefabPaths)
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                if (prefab == null) continue;
                entries.Add(new BlenderKitCatalog.Entry { name = prefab.name, prefab = prefab });
            }
            entries.Sort((a, b) => string.CompareOrdinal(a.name, b.name));
            catalog.entries = entries.ToArray();

            if (created) AssetDatabase.CreateAsset(catalog, CatalogPath);
            EditorUtility.SetDirty(catalog);
            AssetDatabase.SaveAssets();
            BlenderKitCatalog.ClearCache();
            Debug.Log("[BlenderKit] 目录刷新：" + entries.Count + " 件 → " + CatalogPath);
        }

        private static void EnsureFolders()
        {
            EnsureFolder("Assets/Generated");
            EnsureFolder(KitRoot);
            EnsureFolder(PrefabDir);
            EnsureFolder(MaterialDir);
            EnsureFolder("Assets/Resources");
            EnsureFolder(CatalogDir);
            EnsureFolder("Assets/StreamingAssets");
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            string parent = Path.GetDirectoryName(path).Replace('\\', '/');
            string leaf = Path.GetFileName(path);
            if (!AssetDatabase.IsValidFolder(parent)) EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, leaf);
        }

        private static string[] FindFbx(string dir)
        {
            if (!AssetDatabase.IsValidFolder(dir)) return new string[0];
            string[] guids = AssetDatabase.FindAssets("t:Model", new[] { dir });
            var list = new List<string>();
            foreach (string g in guids)
            {
                string path = AssetDatabase.GUIDToAssetPath(g);
                if (path.ToLowerInvariant().EndsWith(".fbx") && Path.GetDirectoryName(path).Replace('\\', '/') == dir)
                    list.Add(path);
            }
            list.Sort(System.StringComparer.OrdinalIgnoreCase);
            return list.ToArray();
        }

        private static string[] FindPrefabs(string dir)
        {
            if (!AssetDatabase.IsValidFolder(dir)) return new string[0];
            string[] guids = AssetDatabase.FindAssets("t:Prefab", new[] { dir });
            var list = new List<string>();
            foreach (string g in guids) list.Add(AssetDatabase.GUIDToAssetPath(g));
            list.Sort(System.StringComparer.OrdinalIgnoreCase);
            return list.ToArray();
        }

        /// <summary>把全部 prefab 铺成一个网格（没有 layout JSON 时的退路）。</summary>
        private static void BuildGrid(Transform parent)
        {
            string[] paths = FindPrefabs(PrefabDir);
            int n = paths.Length;
            if (n == 0) return;
            int cols = Mathf.CeilToInt(Mathf.Sqrt(n));
            const float cell = 8f;
            for (int i = 0; i < n; i++)
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(paths[i]);
                if (prefab == null) continue;
                var go = Object.Instantiate(prefab, parent);
                go.name = prefab.name;
                go.transform.localPosition = new Vector3((i % cols) * cell, 0f, (i / cols) * cell);
            }
        }

        private static Bounds BoundsOf(GameObject root)
        {
            var renderers = root.GetComponentsInChildren<Renderer>(true);
            bool has = false;
            var bounds = new Bounds(root.transform.position, Vector3.zero);
            foreach (var r in renderers)
            {
                if (r == null) continue;
                if (!has) { bounds = r.bounds; has = true; }
                else bounds.Encapsulate(r.bounds);
            }
            return bounds;
        }

        private static void RenderToPng(Bounds bounds, string outPath, int size)
        {
            var camGo = new GameObject("__BlenderKitPreviewCam");
            try
            {
                var cam = camGo.AddComponent<Camera>();
                cam.orthographic = false;
                cam.fieldOfView = 30f;
                cam.nearClipPlane = 0.1f;
                cam.farClipPlane = bounds.size.magnitude * 4f + 200f;
                cam.clearFlags = CameraClearFlags.SolidColor;
                cam.backgroundColor = new Color(0.53f, 0.72f, 0.83f);

                Vector3 dir = new Vector3(0.75f, 0.5f, -0.75f).normalized;   // 右上前方：能同时看出体量和正面
                float dist = bounds.extents.magnitude / Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad) * 1.2f;
                camGo.transform.position = bounds.center + dir * dist;
                camGo.transform.LookAt(bounds.center);

                var lightGo = new GameObject("__BlenderKitPreviewLight");
                var light = lightGo.AddComponent<Light>();
                light.type = LightType.Directional;
                light.intensity = 1.1f;
                light.color = new Color(1f, 0.96f, 0.9f);
                lightGo.transform.rotation = Quaternion.Euler(50f, -30f, 0f);

                // 自检：把「相机在哪 / 东西在不在视野内 / 有几个活 renderer」打出来。
                // 09:0x 出现过一次截图全是背景色：相机参数算得没错，画面里却什么都没有。只有这几个数字
                // 加场景名才能区分「场景里真的没东西」和「有东西但没拍到」，光看 PNG 是分不出来的。
                int liveRenderers = 0;
                foreach (var r in Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None))
                    if (r.enabled && r.gameObject.activeInHierarchy && r.bounds.size != Vector3.zero) liveRenderers++;
                Vector3 viewport = cam.WorldToViewportPoint(bounds.center);
                bool blocked = Physics.Raycast(camGo.transform.position,
                                               (bounds.center - camGo.transform.position).normalized,
                                               out var hit, dist * 4f);
                Debug.Log("[BlenderKit] 截图自检：cam=" + camGo.transform.position.ToString("0.##")
                          + " 看向=" + bounds.center.ToString("0.##") + " dist=" + dist.ToString("0.#")
                          + " 视野坐标=" + viewport.ToString("0.###")
                          + " 活 renderer=" + liveRenderers
                          + " cam 场景=" + camGo.scene.name
                          + " 射线命中=" + (blocked ? hit.collider.name : "无"));

                var rt = new RenderTexture(size, size, 24, RenderTextureFormat.ARGB32);
                var prevActive = RenderTexture.active;
                cam.targetTexture = rt;
                // **渲染两次**：刚经历域重载 / 资源导入后，第一次 `Camera.Render()` 会出一张纯背景色的空图
                // （09:0x 实测：几何、相机、射线全对，「视野坐标=(0.5,0.5,36.7)」「射线命中=house_a」，
                //  第一张仍只有背景色，再调一次就正常）。第二次是幂等的，白渲染一帧换掉这个偶发空图很划算。
                cam.Render();
                cam.Render();
                RenderTexture.active = rt;
                var tex = new Texture2D(size, size, TextureFormat.RGB24, false);
                tex.ReadPixels(new Rect(0f, 0f, size, size), 0, 0);
                tex.Apply();
                RenderTexture.active = prevActive;
                cam.targetTexture = null;

                string dirPath = Path.GetDirectoryName(outPath);
                if (!string.IsNullOrEmpty(dirPath) && !Directory.Exists(dirPath)) Directory.CreateDirectory(dirPath);
                File.WriteAllBytes(outPath, tex.EncodeToPNG());

                Object.DestroyImmediate(tex);
                rt.Release();
                Object.DestroyImmediate(rt);
                Object.DestroyImmediate(lightGo);
            }
            finally
            {
                Object.DestroyImmediate(camGo);
            }
        }

        private static int Check(string label, Vector3 actual, Vector3 expected)
        {
            bool ok = (actual - expected).sqrMagnitude < 1e-6f;
            if (!ok)
                Debug.LogError("[BlenderKit] 自检不通过 " + label + "：实际 " + actual.ToString("0.###")
                               + "，期望 " + expected.ToString("0.###"));
            return ok ? 0 : 1;
        }

        private static string Key(string path)
        {
            return Path.GetFileNameWithoutExtension(path);
        }

        /// <summary>材质名 → 文件名安全的键。去掉 Blender 导出的 `M_` 前缀和 Unity 的 `.001` 去重后缀。</summary>
        private static string SanitizeName(string raw)
        {
            if (string.IsNullOrEmpty(raw)) return "unnamed";
            string s = raw.Trim();
            int dot = s.LastIndexOf(".00", System.StringComparison.Ordinal);
            if (dot > 0 && dot == s.Length - 4) s = s.Substring(0, dot);
            var sb = new System.Text.StringBuilder(s.Length);
            foreach (char c in s)
                sb.Append(char.IsLetterOrDigit(c) || c == '_' || c == '-' ? c : '_');
            return sb.ToString();
        }
    }
}
