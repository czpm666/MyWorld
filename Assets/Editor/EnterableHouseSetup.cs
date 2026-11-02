using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using MyWorld;

namespace MyWorldEditorTools
{
    /// <summary>
    /// 把一栋已经摆好的房子变成"能直接走进去"的房子。
    ///
    /// 装配内容：
    ///   1. 房根节点上挂 EnterableHouse（已有就复用，不叠加）；
    ///   2. 子物体里找 Roof / Roof_* 当屋顶根，找 DoorPivot / Door 当门轴；
    ///   3. 按**除屋顶和门以外**的所有渲染器包围盒算室内空间，生成一个略小于墙内空腔的
    ///      InteriorTrigger（BoxCollider + isTrigger），挂在房子下面；
    ///   4. 把三个引用写进组件。
    ///
    /// 幂等：重复点只更新尺寸/引用，不会多出第二个组件、第二个触发体。
    /// 预制体阶段（Prefab Mode）里也能用，改完直接写回 prefab 资产。
    /// </summary>
    public static class EnterableHouseSetup
    {
        private const string MenuSetup = "Tools/My World/把选中房屋设为可进入";
        private const string MenuCheck = "Tools/My World/检查可进入房屋装配";
        private const string MenuPlaceholder = "Tools/My World/生成可进入房屋占位 Prefab";

        private const string InteriorFolder = "Assets/Generated/Interiors";
        private const string PlaceholderPrefabPath = InteriorFolder + "/interior_house_a_placeholder.prefab";
        private const string TriggerChildName = "InteriorTrigger";

        // ------------------------------------------------------------------ 菜单

        [MenuItem(MenuSetup, false, 71)]
        public static void SetupSelected()
        {
            var root = Selection.activeGameObject;
            if (root == null)
            {
                EditorUtility.DisplayDialog("设为可进入房屋", "先在 Hierarchy 里选中房屋的根节点。", "好");
                return;
            }

            if (Application.isPlaying)
            {
                EditorUtility.DisplayDialog("设为可进入房屋", "Play 模式下不装配，请先退出 Play。", "好");
                return;
            }

            if (PrefabUtility.IsPartOfPrefabAsset(root))
            {
                EditorUtility.DisplayDialog("设为可进入房屋",
                    "这是 Project 窗口里的 prefab 资产。请双击进入 Prefab Mode 再选根节点，或在场景里选它的实例。", "好");
                return;
            }

            if (!SetupHouse(root, true))
            {
                EditorUtility.DisplayDialog("设为可进入房屋", "装配失败，看 Console 的报错。", "好");
                return;
            }

            RepaintViews();
        }

        [MenuItem(MenuCheck, false, 72)]
        public static void CheckAll()
        {
            var sb = new StringBuilder();
            var houses = Object.FindObjectsByType<EnterableHouse>(FindObjectsSortMode.None);
            sb.AppendLine("[可进入房屋] 找到 " + houses.Length + " 栋");

            int ok = 0, bad = 0;
            for (int i = 0; i < houses.Length; i++)
            {
                var h = houses[i];
                if (h == null) continue;

                bool hasRoof = h.RoofRoot != null;
                bool hasDoor = h.DoorPivot != null;
                bool hasTrigger = h.InteriorTrigger != null;

                if (hasRoof && hasDoor && hasTrigger)
                {
                    ok++;
                    sb.AppendFormat("  [ok]   {0}  室内体: {1}\n", h.name, h.InteriorTrigger.bounds.size);
                }
                else
                {
                    bad++;
                    sb.AppendFormat("  [缺]   {0}  Roof={1} DoorPivot={2} Trigger={3}\n",
                        h.name, hasRoof, hasDoor, hasTrigger);
                }
            }

            sb.AppendFormat("通过 {0} / 缺件 {1}\n", ok, bad);
            if (bad > 0) Debug.LogError(sb.ToString());
            else Debug.Log(sb.ToString());
            // 不弹模态对话框：这条菜单会被批处理/CI 直接 ExecuteMenuItem 调用，
            // 弹窗会卡住 Editor 主线程。
        }

        // ------------------------------------------------------------------ 装配

        /// <summary>对一个房根节点做全套装配。translateUndo 只在菜单路径下为 true。</summary>
        public static bool SetupHouse(GameObject root, bool useUndo)
        {
            if (root == null) return false;

            var roof = FindChild(root.transform, "Roof", "Roof_");
            var door = FindChild(root.transform, "DoorPivot", "Door");
            if (door != null && door == roof) door = null;

            if (roof == null)
                Debug.LogWarning("[可进入房屋] " + root.name + " 下没找到 Roof / Roof_* 子物体：进屋时不会有屋顶淡出。", root);
            if (door == null)
                Debug.LogWarning("[可进入房屋] " + root.name + " 下没找到 DoorPivot / Door 子物体：门不会自己开。", root);

            // 室内空腔：排除屋顶和门之后的渲染器包围盒。
            Bounds shell;
            if (!TryComputeShellBounds(root, roof, door, out shell))
            {
                Debug.LogError("[可进入房屋] " + root.name + " 下没有可用的 Renderer，算不出室内空间。", root);
                return false;
            }

            var box = BuildInteriorTrigger(root, shell, useUndo);
            if (box == null) return false;

            var house = root.GetComponent<EnterableHouse>();
            if (house == null)
            {
                if (useUndo) house = Undo.AddComponent<EnterableHouse>(root);
                else house = root.AddComponent<EnterableHouse>();
            }

            if (house == null)
            {
                Debug.LogError("[可进入房屋] EnterableHouse 挂不上去（脚本没编译？）。", root);
                return false;
            }


            if (useUndo) Undo.RecordObject(house, "配置可进入房屋");
            house.Configure(roof, door, box);
            EditorUtility.SetDirty(house);

            if (useUndo) MarkDirty(root);

            Debug.Log(string.Format(
                "[可进入房屋] {0}\n  Roof = {1}\n  DoorPivot = {2}\n  InteriorTrigger: center {3}, size {4}\n  （屋顶淡出 / 门自动开由 EnterableHouse 运行时驱动）",
                root.name,
                roof != null ? roof.name : "<无>",
                door != null ? door.name : "<无>",
                box.center.ToString("F2"),
                box.size.ToString("F2")), root);

            return true;
        }

        /// <summary>按名字找子物体：先精确，再前缀，最后包含（都大小写不敏感）。</summary>
        private static Transform FindChild(Transform root, string exact, string prefix)
        {
            Transform prefixHit = null;
            var all = root.GetComponentsInChildren<Transform>(true);

            for (int i = 0; i < all.Length; i++)
            {
                var t = all[i];
                if (t == null || t == root) continue;
                if (string.Equals(t.name, exact, System.StringComparison.OrdinalIgnoreCase))
                    return t;
                if (prefixHit == null && t.name.StartsWith(prefix, System.StringComparison.OrdinalIgnoreCase))
                    prefixHit = t;
            }
            return prefixHit;
        }

        /// <summary>除屋顶/门以外所有启用渲染器的世界包围盒。</summary>
        private static bool TryComputeShellBounds(GameObject root, Transform roof, Transform door, out Bounds bounds)
        {
            bounds = new Bounds(root.transform.position, Vector3.zero);
            bool any = false;

            var renderers = root.GetComponentsInChildren<Renderer>(true);
            for (int i = 0; i < renderers.Length; i++)
            {
                var r = renderers[i];
                if (r == null || !r.enabled) continue;
                if (!r.gameObject.activeInHierarchy) continue;
                if (roof != null && r.transform.IsChildOf(roof)) continue;
                if (door != null && r.transform.IsChildOf(door)) continue;
                // 纯特效/文字不进包围盒
                if (r is ParticleSystemRenderer || r is LineRenderer || r is TrailRenderer) continue;

                if (!any) { bounds = r.bounds; any = true; }
                else bounds.Encapsulate(r.bounds);
            }

            if (!any) return false;

            // 高度取墙身：屋顶虽然排除了，但屋檐可能被算进来；用地面到最大值的 92% 兜一下
            return true;
        }

        /// <summary>
        /// 生成/更新室内触发体：
        ///   水平方向比墙内空腔再收 0.12 m，避免玩家刚踩上门槛就判"在屋里"；
        ///   竖直方向从地面上方一点点到墙高的 90%，跳起来也不会掉出判定。
        /// </summary>
        private static BoxCollider BuildInteriorTrigger(GameObject root, Bounds shell, bool useUndo)
        {
            float inset = Mathf.Min(0.3f, Mathf.Min(shell.size.x, shell.size.z) * 0.12f);

            // 包围盒里可能含门槛/台阶，地面取包围盒底部；最高点是墙顶。
            float floorY = shell.min.y;
            float topY = shell.max.y;
            float height = Mathf.Clamp(topY - floorY - 0.15f, 1.2f, 2.6f);

            Vector3 worldCenter = new Vector3(shell.center.x, floorY + height * 0.5f, shell.center.z);
            Vector3 worldSize = new Vector3(
                Mathf.Max(0.6f, shell.size.x - inset * 2f),
                height,
                Mathf.Max(0.6f, shell.size.z - inset * 2f));

            // 复用已有的触发体（幂等），没有才建。
            Transform existing = null;
            var kids = root.GetComponentsInChildren<Transform>(true);
            for (int i = 0; i < kids.Length; i++)
            {
                if (kids[i] != null && string.Equals(kids[i].name, TriggerChildName, System.StringComparison.OrdinalIgnoreCase))
                {
                    existing = kids[i];
                    break;
                }
            }

            GameObject go;
            if (existing != null)
            {
                go = existing.gameObject;
                go.transform.SetParent(root.transform, true);
                if (useUndo) Undo.RecordObject(go.transform, "更新 InteriorTrigger");
            }
            else
            {
                go = new GameObject(TriggerChildName);
                if (useUndo) Undo.RegisterCreatedObjectUndo(go, "创建 InteriorTrigger");
                go.transform.SetParent(root.transform, false);
            }

            go.layer = root.layer;
            go.transform.localRotation = Quaternion.identity;

            Vector3 scale = root.transform.lossyScale;
            Vector3 inv = new Vector3(
                Mathf.Abs(scale.x) > 0.0001f ? 1f / Mathf.Abs(scale.x) : 1f,
                Mathf.Abs(scale.y) > 0.0001f ? 1f / Mathf.Abs(scale.y) : 1f,
                Mathf.Abs(scale.z) > 0.0001f ? 1f / Mathf.Abs(scale.z) : 1f);

            go.transform.position = worldCenter;
            go.transform.localScale = Vector3.one;
            go.transform.position = worldCenter;   // SetParent 之后再落一次，防止被父级偏移带走

            var box = go.GetComponent<BoxCollider>();
            if (box == null) box = go.AddComponent<BoxCollider>();
            box.isTrigger = true;
            box.center = Vector3.zero;
            box.size = Vector3.Scale(worldSize, inv);

            // 顺手把多余碰撞体去掉：触发体上多一个实心碰撞体会把玩家挡在门口外面
            var colliders = go.GetComponents<Collider>();
            for (int i = 0; i < colliders.Length; i++)
            {
                if (colliders[i] == null || colliders[i] == box) continue;
                if (useUndo) Undo.DestroyObjectImmediate(colliders[i]);
                else Object.DestroyImmediate(colliders[i]);
            }

            if (useUndo) EditorUtility.SetDirty(go);
            return box;
        }

        /// <summary>场景实例 / Prefab Mode / 普通 Scene 三种情况分别标脏。</summary>
        private static void MarkDirty(GameObject root)
        {
            var stage = PrefabStageUtility.GetCurrentPrefabStage();
            if (stage != null && stage.prefabContentsRoot != null &&
                (root == stage.prefabContentsRoot || root.transform.IsChildOf(stage.prefabContentsRoot.transform)))
            {
                EditorUtility.SetDirty(stage.prefabContentsRoot);
                AssetDatabase.SaveAssets();
                return;
            }

            if (PrefabUtility.IsPartOfPrefabInstance(root))
                PrefabUtility.RecordPrefabInstancePropertyModifications(root);

            EditorSceneManager.MarkSceneDirty(root.scene);
        }

        private static void RepaintViews()
        {
            SceneView.RepaintAll();
            UnityEditorInternal.InternalEditorUtility.RepaintAllViews();
        }

        // ------------------------------------------------------------------ 占位房子

        /// <summary>
        /// 用 Cube 拼一栋带门洞的方盒子房子：墙体 + 室内地板 + 几件家具 + 平板屋顶 + 一扇门板。
        /// 目的是在没有真模型的时候验证 EnterableHouse：名字严格用 Roof / DoorPivot，
        /// 门板铰链在 DoorPivot 本地原点、向 +X 伸出去，和 Blender 契约一致。
        /// </summary>
        [MenuItem(MenuPlaceholder, false, 73)]
        public static void BuildPlaceholderPrefab()
        {
            if (Application.isPlaying)
            {
                EditorUtility.DisplayDialog("占位房子", "Play 模式下不生成，请先退出 Play。", "好");
                return;
            }

            EnsureFolder(InteriorFolder);
            EnsureFolder(InteriorFolder + "/Materials");

            var matWall = EnsureLitMaterial(InteriorFolder + "/Materials/M_InteriorWall.mat", new Color(0.86f, 0.81f, 0.72f), 0.05f);
            var matFloor = EnsureLitMaterial(InteriorFolder + "/Materials/M_InteriorFloor.mat", new Color(0.42f, 0.29f, 0.18f), 0.12f);
            var matRoof = EnsureLitMaterial(InteriorFolder + "/Materials/M_InteriorRoof.mat", new Color(0.46f, 0.16f, 0.13f), 0.08f);
            var matDoor = EnsureLitMaterial(InteriorFolder + "/Materials/M_InteriorDoor.mat", new Color(0.30f, 0.18f, 0.09f), 0.15f);
            var matFurn = EnsureLitMaterial(InteriorFolder + "/Materials/M_InteriorFurniture.mat", new Color(0.52f, 0.36f, 0.20f), 0.12f);
            var matCloth = EnsureLitMaterial(InteriorFolder + "/Materials/M_InteriorCloth.mat", new Color(0.62f, 0.22f, 0.20f), 0.05f);

            var root = new GameObject("interior_house_a_placeholder");
            try
            {
                // ---- 地板 ----
                var floor = AddBox(root.transform, "Floor", matFloor, new Vector3(0f, -0.1f, 0f), new Vector3(6f, 0.2f, 5f));
                // 地板要能站人：保留图元自带的 BoxCollider（顶面正好在 y = 0）
                if (floor.GetComponent<Collider>() == null)
                {
                    var floorCol = floor.AddComponent<BoxCollider>();
                    floorCol.size = Vector3.one;
                }

                // ---- 墙体 ----
                var walls = new GameObject("Walls");
                walls.transform.SetParent(root.transform, false);
                AddBox(walls.transform, "Wall_Back", matWall, new Vector3(0f, 1.35f, -2.4f), new Vector3(6f, 2.7f, 0.2f));
                AddBox(walls.transform, "Wall_Left", matWall, new Vector3(-2.9f, 1.35f, 0f), new Vector3(0.2f, 2.7f, 4.6f));
                AddBox(walls.transform, "Wall_Right", matWall, new Vector3(2.9f, 1.35f, 0f), new Vector3(0.2f, 2.7f, 4.6f));
                // 正面（+Z）：中间留 1.2 m 宽、2.1 m 高的门洞
                AddBox(walls.transform, "Wall_Front_Left", matWall, new Vector3(-1.8f, 1.35f, 2.4f), new Vector3(2.4f, 2.7f, 0.2f));
                AddBox(walls.transform, "Wall_Front_Right", matWall, new Vector3(1.8f, 1.35f, 2.4f), new Vector3(2.4f, 2.7f, 0.2f));
                AddBox(walls.transform, "Wall_Front_Lintel", matWall, new Vector3(0f, 2.4f, 2.4f), new Vector3(1.2f, 0.6f, 0.2f));

                // ---- 门（铰链在本地原点，门板向 +X 伸出去）----
                var pivotGo = new GameObject("DoorPivot");
                pivotGo.transform.SetParent(root.transform, false);
                // 门洞左沿（从屋外 +Z 看向 -Z 时的左手边 = -X 侧）
                pivotGo.transform.localPosition = new Vector3(-0.6f, 0f, 2.4f);
                AddBox(pivotGo.transform, "Door_Leaf", matDoor, new Vector3(0.575f, 1.05f, 0f), new Vector3(1.15f, 2.1f, 0.08f));

                // ---- 屋顶（唯一被 EnterableHouse 淡出的部分）----
                var roof = new GameObject("Roof");
                roof.transform.SetParent(root.transform, false);
                roof.transform.localPosition = new Vector3(0f, 2.7f, 0f);
                var roofSlab = AddBox(roof.transform, "Roof_Slab", matRoof, new Vector3(0f, 0.12f, 0f), new Vector3(6.4f, 0.24f, 5.4f));
                StripColliderKeep(roofSlab);
                AddBox(roof.transform, "Roof_Ridge", matRoof, new Vector3(0f, 0.34f, 0f), new Vector3(6.5f, 0.2f, 0.5f));

                // ---- 家具 ----
                var furn = new GameObject("Furniture");
                furn.transform.SetParent(root.transform, false);
                AddBox(furn.transform, "Table", matFurn, new Vector3(0.9f, 0.74f, 0.2f), new Vector3(1.4f, 0.08f, 0.9f));
                AddBox(furn.transform, "Table_LegA", matFurn, new Vector3(0.35f, 0.36f, -0.1f), new Vector3(0.1f, 0.72f, 0.1f));
                AddBox(furn.transform, "Table_LegB", matFurn, new Vector3(1.45f, 0.36f, -0.1f), new Vector3(0.1f, 0.72f, 0.1f));
                AddBox(furn.transform, "Table_LegC", matFurn, new Vector3(0.35f, 0.36f, 0.5f), new Vector3(0.1f, 0.72f, 0.1f));
                AddBox(furn.transform, "Table_LegD", matFurn, new Vector3(1.45f, 0.36f, 0.5f), new Vector3(0.1f, 0.72f, 0.1f));
                AddBox(furn.transform, "Stool_A", matFurn, new Vector3(0.25f, 0.23f, 0.85f), new Vector3(0.42f, 0.46f, 0.42f));
                AddBox(furn.transform, "Stool_B", matFurn, new Vector3(1.55f, 0.23f, 0.85f), new Vector3(0.42f, 0.46f, 0.42f));
                AddBox(furn.transform, "Bed_Frame", matFurn, new Vector3(-1.9f, 0.24f, -1.4f), new Vector3(1.2f, 0.4f, 2f));
                AddBox(furn.transform, "Bed_Sheet", matCloth, new Vector3(-1.9f, 0.5f, -1.4f), new Vector3(1.14f, 0.14f, 1.94f));
                AddBox(furn.transform, "Shelf", matFurn, new Vector3(-2.55f, 0.95f, 0.6f), new Vector3(0.35f, 1.9f, 1.6f));
                AddBox(furn.transform, "Chest", matFurn, new Vector3(2.3f, 0.3f, -1.7f), new Vector3(0.9f, 0.6f, 0.55f));
                AddBox(furn.transform, "Rug", matCloth, new Vector3(0.9f, 0.012f, 0.2f), new Vector3(2.2f, 0.024f, 1.8f));
                var rug = furn.transform.Find("Rug");
                if (rug != null) StripColliderKeep(rug.gameObject);

                // ---- 室内触发体 ----
                var trigGo = new GameObject(TriggerChildName);
                trigGo.transform.SetParent(root.transform, false);
                trigGo.transform.localPosition = new Vector3(0f, 1.2f, 0f);
                var box = trigGo.AddComponent<BoxCollider>();
                box.isTrigger = true;
                box.size = new Vector3(4.9f, 2.3f, 4.1f);

                // ---- 组件 ----
                var house = root.AddComponent<EnterableHouse>();
                house.Configure(roof.transform, pivotGo.transform, box);

                // ---- 存成 prefab ----
                EnsureFolder(InteriorFolder);
                var saved = PrefabUtility.SaveAsPrefabAsset(root, PlaceholderPrefabPath);
                if (saved == null)
                {
                    Debug.LogError("[占位房子] 保存 prefab 失败：" + PlaceholderPrefabPath);
                    return;
                }

                AssetDatabase.SaveAssets();
                EditorGUIUtility.PingObject(saved);
                Selection.activeObject = saved;

                Debug.Log("[占位房子] 已生成 " + PlaceholderPrefabPath +
                          "\n  结构：Floor / Walls / DoorPivot(Door_Leaf) / Roof(Roof_Slab,Roof_Ridge) / Furniture / InteriorTrigger" +
                          "\n  EnterableHouse 已装配（Roof=Roof, DoorPivot=DoorPivot, InteriorTrigger 已接）");
            }
            finally
            {
                Object.DestroyImmediate(root);
            }
        }

        // ------------------------------------------------------------------ 小工具

        private static GameObject AddBox(Transform parent, string name, Material mat, Vector3 localPos, Vector3 scale)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localRotation = Quaternion.identity;
            go.transform.localScale = scale;

            var r = go.GetComponent<Renderer>();
            if (r != null) r.sharedMaterial = mat;

            // 图元自带 Collider，保留（墙/家具要挡人），需要去掉时调用方自己 StripColliderKeep
            return go;
        }

        /// <summary>去掉图元自带的碰撞体。传 null 也安全。</summary>
        private static void StripColliderKeep(GameObject go)
        {
            if (go == null) return;
            var c = go.GetComponent<Collider>();
            if (c == null) return;
            Object.DestroyImmediate(c);
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;

            string[] parts = path.Split('/');
            string cur = parts[0];
            for (int i = 1; i < parts.Length; i++)
            {
                string next = cur + "/" + parts[i];
                if (!AssetDatabase.IsValidFolder(next))
                    AssetDatabase.CreateFolder(cur, parts[i]);
                cur = next;
            }
        }

        private static Material EnsureLitMaterial(string path, Color color, float smoothness)
        {
            var existing = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (existing != null)
            {
                existing.SetColor("_BaseColor", color);
                existing.color = color;
                EditorUtility.SetDirty(existing);
                return existing;
            }

            var shader = Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null) shader = Shader.Find("Standard");
            if (shader == null)
            {
                Debug.LogError("[占位房子] 找不到 URP/Lit 或 Standard shader。");
                return null;
            }

            var mat = new Material(shader);
            mat.name = System.IO.Path.GetFileNameWithoutExtension(path);
            if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", color);
            if (mat.HasProperty("_Smoothness")) mat.SetFloat("_Smoothness", smoothness);
            mat.color = color;

            AssetDatabase.CreateAsset(mat, path);
            return mat;
        }
    }
}
