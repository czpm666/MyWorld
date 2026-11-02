using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// 材质贴图化的目视验收：在一个临时附加场景里摆几组样板（墙 / 屋顶 / 地面 / 特写），
    /// 用离屏 Camera.Render() 拍 PNG 到 E:\My World\WorkQC\。
    ///
    /// 只写 WorkQC（不在 Assets 里落 PNG，避免 import + 域重载）；拍完立即关掉临时场景并
    /// 恢复原场景。Play 模式下拒绝执行（编辑器是共享的）。
    /// </summary>
    public static class MapMaterialPreview
    {
        const string OutDir = @"E:\My World\WorkQC";

        [MenuItem("Tools/My World/材质贴图预览/渲染 WorkQC 对比图（墙/顶/地/特写）", false, 60)]
        public static void RenderAll()
        {
            if (EditorApplication.isPlaying || EditorApplication.isPlayingOrWillChangePlaymode)
            {
                Debug.LogWarning("[MapMatPreview] 当前在 Play 模式，已跳过。请先停止 Play。");
                return;
            }

            LogMaterialState();

            // 用单场景模式拍：附加场景会和已打开的地图重叠（相机能看到所有已加载场景），
            // 拍完再从磁盘把原场景开回来。所以要求原场景只有一个、已存盘、未修改。
            var prevScene = SceneManager.GetActiveScene();
            string prevPath = prevScene.path;
            if (SceneManager.sceneCount != 1 || string.IsNullOrEmpty(prevPath) || prevScene.isDirty)
            {
                Debug.LogWarning("[MapMatPreview] 需要恰好一个未修改的已存盘场景才能拍预览（当前 "
                                 + SceneManager.sceneCount + " 个，dirty=" + prevScene.isDirty
                                 + "，path=" + prevPath + "），已跳过。");
                return;
            }

            var previewScene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            SceneManager.SetActiveScene(previewScene);
            var holder = new GameObject("__MapMatPreview");

            try
            {
                RenderSettings.skybox = null;
                RenderSettings.ambientMode = AmbientMode.Flat;
                RenderSettings.ambientLight = new Color(0.30f, 0.30f, 0.29f);
                RenderSettings.ambientIntensity = 1.10f;
                RenderSettings.fog = false;

                AddLight(holder.transform, "Key", 1.25f, new Color(1f, 0.95f, 0.86f), Quaternion.Euler(48f, -32f, 0f), true);
                AddLight(holder.transform, "Fill", 0.28f, new Color(0.72f, 0.80f, 0.95f), Quaternion.Euler(35f, 150f, 0f), false);

                BuildWallRow(holder.transform);
                BuildRoofRow(holder.transform);
                BuildGround(holder.transform);
                BuildDetail(holder.transform);
                BuildRoofClose(holder.transform);

                Directory.CreateDirectory(OutDir);

                // 1) 5 块墙板（宽景，看配色是否还是原设计色板）
                Render(new Vector3(0f, 7.0f, 36f), new Vector3(0f, 2.2f, 0f), 32f, 1600, 900,
                       Path.Combine(OutDir, "mapmat_walls_wide.png"));
                // 2) 4 块屋顶板（赤陶 / 石板 / 青绿 / 茅草）
                Render(new Vector3(0f, 13f, -18f), new Vector3(0f, 0.7f, -30f), 42f, 1600, 900,
                       Path.Combine(OutDir, "mapmat_roofs.png"));
                // 3) 地面：草 / 土 / 铺石 / 粗石
                Render(new Vector3(0f, 30f, -44f), new Vector3(0f, 0f, -62f), 46f, 1600, 900,
                       Path.Combine(OutDir, "mapmat_ground.png"));
                // 4) 墙面特写：正对 5 块墙板中的中间两块（抹灰颗粒 / 石缝）
                Render(new Vector3(0f, 2.6f, 9.5f), new Vector3(0f, 2.4f, 0f), 46f, 1600, 900,
                       Path.Combine(OutDir, "mapmat_detail_wall.png"));
                // 5) 瓦片特写：看瓦缝
                Render(new Vector3(0f, 3.0f, -105.6f), new Vector3(0f, 1.0f, -110f), 34f, 1600, 900,
                       Path.Combine(OutDir, "mapmat_roof_close.png"));

                Debug.Log("[MapMatPreview] 5 张图写到 " + OutDir);
            }
            finally
            {
                Object.DestroyImmediate(holder);
                // 预览场景不存盘，直接从磁盘把同事原来打开的地图场景开回来
                EditorSceneManager.OpenScene(prevPath, OpenSceneMode.Single);
            }
        }

        // ------------------------------------------------------------------ 真实地图实测
        // 打开地图场景 → 编辑期调 BuildAll() 从零重建整张图 → 打光拍 3 张 →
        // CloseScene(不存盘) → 把同事原来打开的场景开回来。

        [MenuItem("Tools/My World/材质贴图预览/渲染罗亚市实测图（从零重建）", false, 61)]
        public static void RenderRoaTown() { RenderMap("Assets/Scenes/RoaTown.unity", "roa"); }

        [MenuItem("Tools/My World/材质贴图预览/渲染布耶纳村实测图（从零重建）", false, 62)]
        public static void RenderBuenaVillage() { RenderMap("Assets/Scenes/BuenaVillage.unity", "buena"); }

        [MenuItem("Tools/My World/材质贴图预览/渲染拉诺亚学园实测图（从零重建）", false, 63)]
        public static void RenderRanoaAcademy() { RenderMap("Assets/Scenes/RanoaAcademy.unity", "ranoa"); }

        public static void RenderMap(string mapScenePath, string tag)
        {
            if (GuardIdle()) return;

            var origin = SceneManager.GetActiveScene();
            if (SceneManager.sceneCount != 1 || string.IsNullOrEmpty(origin.path) || origin.isDirty)
            {
                Debug.LogWarning("[MapMatPreview] 需要恰好一个未修改的已存盘场景（当前 " + SceneManager.sceneCount
                                 + " 个，dirty=" + origin.isDirty + "，path=" + origin.path + "），已跳过。");
                return;
            }
            string restorePath = origin.path;
            Scene mapScene = default;
            GameObject rig = null;

            try
            {
                mapScene = EditorSceneManager.OpenScene(mapScenePath, OpenSceneMode.Single);
                var boot = Object.FindFirstObjectByType<MapBootstrap>();
                if (boot == null)
                {
                    Debug.LogWarning("[MapMatPreview] " + mapScenePath + " 里没有 MapBootstrap。");
                    return;
                }

                double t0 = EditorApplication.timeSinceStartup;
                boot.BuildAll();
                int renderers = Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None).Length;
                Debug.Log("[MapMatPreview] " + tag + " BuildAll 用时 "
                          + (EditorApplication.timeSinceStartup - t0).ToString("0.0") + "s，renderer=" + renderers
                          + "，材质缓存=" + MapMaterials.CacheCount);

                // 关掉地图自带灯，避免与预览灯叠加（场景不存盘，随改随扔）
                foreach (var l in Object.FindObjectsByType<Light>(FindObjectsSortMode.None)) l.enabled = false;

                rig = new GameObject("__MapMatRig");
                RenderSettings.ambientMode = AmbientMode.Flat;
                RenderSettings.ambientLight = new Color(0.30f, 0.30f, 0.29f);
                RenderSettings.ambientIntensity = 1.05f;
                RenderSettings.fog = false;
                AddLight(rig.transform, "Key", 1.35f, new Color(1f, 0.95f, 0.86f), Quaternion.Euler(52f, -38f, 0f), true);
                AddLight(rig.transform, "Fill", 0.25f, new Color(0.72f, 0.80f, 0.95f), Quaternion.Euler(30f, 150f, 0f), false);

                Bounds b = MapBounds(mapScene);
                Vector3 c = b.center;
                float radius = Mathf.Max(8f, b.extents.magnitude);
                Directory.CreateDirectory(OutDir);

                // 1) 全景（俯视 ≈50°）
                float d = radius * 1.9f;
                Render(c + new Vector3(0f, d * 0.95f, -d * 0.62f), c, 40f, 1600, 900,
                       Path.Combine(OutDir, "mapmat_" + tag + "_overview.png"));

                // 2) 低机位铺装：贴地看广场石板（合批后 "Avenue"/"PlazaFloor" 节点已销毁，
                //    全部回退到包围盒中心；机位压低让地面占满画面下 2/3，专门验证石板缝）
                Vector3 ave = NamedCenter(mapScene, "Avenue", c);
                Render(new Vector3(ave.x, 1.9f, ave.z - 6f), new Vector3(ave.x, 0.0f, ave.z - 17f),
                       58f, 1600, 900, Path.Combine(OutDir, "mapmat_" + tag + "_street.png"));

                // 3) 广场铺装特写
                Vector3 plaza = NamedCenter(mapScene, "PlazaFloor", c + new Vector3(0f, 0f, 6f));
                Render(plaza + new Vector3(0f, 12f, 16f), plaza, 50f, 1600, 900,
                       Path.Combine(OutDir, "mapmat_" + tag + "_plaza.png"));

                Debug.Log("[MapMatPreview] " + tag + " 3 张实测图写到 " + OutDir);
            }
            catch (System.Exception e)
            {
                Debug.LogError("[MapMatPreview] " + tag + " 渲染失败: " + e);
            }
            finally
            {
                if (rig != null) Object.DestroyImmediate(rig);
                if (mapScene.IsValid()) EditorSceneManager.CloseScene(mapScene, true);
                EditorSceneManager.OpenScene(restorePath, OpenSceneMode.Single);
            }
        }

        static bool GuardIdle()
        {
            if (EditorApplication.isPlaying || EditorApplication.isPlayingOrWillChangePlaymode)
            {
                Debug.LogWarning("[MapMatPreview] 当前在 Play 模式，已跳过。");
                return true;
            }
            return false;
        }

        static Bounds MapBounds(Scene scene)
        {
            bool any = false;
            var b = new Bounds(Vector3.zero, Vector3.zero);
            foreach (var root in scene.GetRootGameObjects())
            {
                foreach (var r in root.GetComponentsInChildren<Renderer>(true))
                {
                    if (!r.enabled || r is ParticleSystemRenderer || r is TrailRenderer || r is LineRenderer) continue;
                    if (!any) { b = r.bounds; any = true; }
                    else b.Encapsulate(r.bounds);
                }
            }
            return b;
        }

        static Vector3 NamedCenter(Scene scene, string name, Vector3 fallback)
        {
            foreach (var root in scene.GetRootGameObjects())
            {
                foreach (var t in root.GetComponentsInChildren<Transform>(true))
                    if (t.name == name) return t.position;
            }
            return fallback;
        }

        // ------------------------------------------------------------------ 样板搭建

        static void BuildWallRow(Transform root)
        {
            // 每块 5 米宽 × 3.6 米高，模拟 Kit.Box 的 0..1 UV 墙
            string[] keys = { "plaster_warm", "plaster_cream", "stone_wall", "stone_light", "brick" };
            for (int i = 0; i < keys.Length; i++)
            {
                float x = -11.2f + i * 5.6f;
                var panel = Box(root, keys[i], new Vector3(5f, 3.6f, 0.4f), new Vector3(x, 1.9f, 0f),
                                MapMaterials.Get(keys[i]));
                panel.transform.localPosition = new Vector3(x, 1.9f, 0f);
            }

            // 两根木梁贴在中间墙板前，看木纹
            Box(root, "beam_dark", new Vector3(0.32f, 3.6f, 0.32f), new Vector3(-6.0f, 1.9f, 0.45f),
                MapMaterials.Get("timber_dark"));
            Box(root, "beam_light", new Vector3(0.32f, 3.6f, 0.32f), new Vector3(-5.2f, 1.9f, 0.45f),
                MapMaterials.Get("timber_light"));
        }

        static void BuildRoofRow(Transform root)
        {
            // 米制 UV（Kit.Slab = KitGeo.BoxMesh），和真正的屋顶网格一致
            string[] keys = { "roof_terracotta", "roof_slate", "roof_teal", "roof_thatch" };
            for (int i = 0; i < keys.Length; i++)
            {
                float x = -9f + i * 6f;
                var slab = Kit.Slab(root, keys[i], new Vector3(5f, 0.25f, 3.5f),
                                    new Vector3(x, 0.65f, -30f), MapMaterials.Get(keys[i]));
                slab.transform.localRotation = Quaternion.Euler(-18f, 0f, 0f);   // 微微朝相机掀一点
            }
        }

        static void BuildGround(Transform root)
        {
            // 0..1 UV 的大地/铺装（模拟地图里的 Box 地面）
            Box(root, "grass", new Vector3(16f, 0.1f, 16f), new Vector3(-14f, 0f, -62f),
                MapMaterials.Get("grass"));
            Box(root, "dirt", new Vector3(16f, 0.1f, 7f), new Vector3(-14f, 0.02f, -51f),
                MapMaterials.Get("dirt"));
            Box(root, "cobble", new Vector3(20f, 0.1f, 10f), new Vector3(9f, 0f, -58f),
                MapMaterials.Get("cobble"));
            Box(root, "stone_wall_lane", new Vector3(10f, 0.1f, 10f), new Vector3(9f, 0.02f, -70f),
                MapMaterials.Get("stone_wall"));
            Box(root, "sand", new Vector3(8f, 0.1f, 8f), new Vector3(19f, 0f, -70f),
                MapMaterials.Get("sand"));
        }

        static void BuildDetail(Transform root)
        {
            Box(root, "plaster_detail", new Vector3(3.2f, 3.2f, 0.3f), new Vector3(-4.4f, 1.6f, -95f),
                MapMaterials.Get("plaster_warm"));
            Box(root, "stone_detail", new Vector3(3.2f, 3.2f, 0.3f), new Vector3(-1.0f, 1.6f, -95f),
                MapMaterials.Get("stone_wall"));
            Box(root, "cobble_detail", new Vector3(3.2f, 0.1f, 3.2f), new Vector3(2.6f, 0.6f, -95f),
                MapMaterials.Get("cobble"));
            Box(root, "door", new Vector3(1.3f, 2.7f, 0.16f), new Vector3(5.3f, 1.35f, -95f),
                MapMaterials.Get("wood_dark"));
            Box(root, "door_frame", new Vector3(1.8f, 0.22f, 0.3f), new Vector3(5.3f, 2.8f, -95f),
                MapMaterials.Get("timber_mid"));
        }

        static void BuildRoofClose(Transform root)
        {
            var slab = Kit.Slab(root, "roof_close", new Vector3(3.2f, 0.2f, 2.6f),
                                new Vector3(0f, 1.0f, -110f), MapMaterials.Get("roof_terracotta"));
            slab.transform.localRotation = Quaternion.Euler(-12f, 0f, 0f);
        }

        static GameObject Box(Transform parent, string name, Vector3 size, Vector3 pos, Material mat)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localScale = size;
            var col = go.GetComponent<Collider>();
            if (col != null) Object.DestroyImmediate(col);
            var mr = go.GetComponent<MeshRenderer>();
            if (mr != null) mr.sharedMaterial = mat;
            return go;
        }

        static void AddLight(Transform root, string name, float intensity, Color color, Quaternion rot, bool shadows)
        {
            var go = new GameObject("__Light_" + name);
            go.transform.SetParent(root, false);
            go.transform.localRotation = rot;
            var l = go.AddComponent<Light>();
            l.type = LightType.Directional;
            l.intensity = intensity;
            l.color = color;
            l.shadows = shadows ? LightShadows.Soft : LightShadows.None;
            l.shadowStrength = 0.75f;
        }

        // ------------------------------------------------------------------ 渲染

        static void Render(Vector3 eye, Vector3 target, float fov, int width, int height, string outPath)
        {
            var camGo = new GameObject("__PreviewCam");
            try
            {
                var cam = camGo.AddComponent<Camera>();
                cam.orthographic = false;
                cam.fieldOfView = fov;
                cam.nearClipPlane = 0.1f;
                cam.farClipPlane = 400f;
                cam.clearFlags = CameraClearFlags.SolidColor;
                cam.backgroundColor = new Color(0.42f, 0.50f, 0.58f);
                cam.allowHDR = false;
                cam.allowMSAA = true;
                camGo.transform.position = eye;
                camGo.transform.LookAt(target);

                var rt = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32);
                var prevActive = RenderTexture.active;
                cam.targetTexture = rt;
                // 第一次 Camera.Render() 在域重载后可能出空图，连拍两张（项目里已验证过）
                cam.Render();
                cam.Render();
                RenderTexture.active = rt;
                var tex = new Texture2D(width, height, TextureFormat.RGB24, false);
                tex.ReadPixels(new Rect(0f, 0f, width, height), 0, 0);
                tex.Apply();
                RenderTexture.active = prevActive;
                cam.targetTexture = null;

                File.WriteAllBytes(outPath, tex.EncodeToPNG());
                Object.DestroyImmediate(tex);
                rt.Release();
                Object.DestroyImmediate(rt);

                Debug.Log("[MapMatPreview] 写出 " + outPath + " (" + width + "x" + height + ") cam="
                          + eye.ToString("0.##") + " -> " + target.ToString("0.##"));
            }
            finally
            {
                Object.DestroyImmediate(camGo);
            }
        }

        // ------------------------------------------------------------------ 自检日志

        static void LogMaterialState()
        {
            var sb = new StringBuilder("[MapMatPreview] 材质自检：");
            string[] keys =
            {
                "plaster_warm", "stone_wall", "stone_light", "cobble", "brick",
                "roof_terracotta", "roof_teal", "roof_thatch",
                "timber_dark", "wood_dark", "wood_plank", "wood_barrel",
                "grass", "dirt", "sand",
            };
            foreach (var k in keys)
            {
                var m = MapMaterials.Get(k);
                if (m == null) { sb.Append("\n  " + k + " = NULL"); continue; }
                var tex = m.HasProperty("_BaseMap") ? m.GetTexture("_BaseMap") : null;
                var st = m.HasProperty("_BaseMap_ST") ? m.GetVector("_BaseMap_ST") : Vector4.zero;
                sb.Append("\n  " + k + " mat=" + m.name
                          + " tex=" + (tex != null ? tex.name : "NULL")
                          + " tiling=" + st.x.ToString("0.###")
                          + " tint=" + m.GetColor("_BaseColor").ToString("0.##"));
            }
            // 共享语义
            sb.Append("\n  共享语义: Get(x)==Get(x) -> "
                      + (ReferenceEquals(MapMaterials.Get("stone_wall"), MapMaterials.Get("stone_wall")))
                      + "；Solid 仍纯色: " + (MapMaterials.Solid("__probe_solid", Color.red)
                          .GetTexture("_BaseMap") == null));
            Debug.Log(sb.ToString());
        }
    }
}
