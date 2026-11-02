using System.IO;
using MyWorld.Maps;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// 布局目视验收：把 `Assets/StreamingAssets/medieval_layout.json` 摆进一个**临时 additive 场景**，
    /// 离屏渲染两张图到 `Temp/`：
    ///   1. `town_top.png`   俯视（正交）——看四条城门大道与两圈街道有没有被房子压住；
    ///   2. `town_doors.png` 环 A 街道近景（透视）——看门是不是朝街（而不是朝城墙）。
    ///
    /// 全程不写 `Assets/`、不碰当前场景（RoaTown 是 village-dev 的工作场景，一个脏标记都可能害他误存）。
    /// 门朝向的**硬证据**不在这两张图里，而在 `Temp/make_medieval_layout.py` 打印的
    /// `door-facing: min dot` 上 —— 图只用来确认"看起来也对"。
    /// </summary>
    public static class MedievalLayoutPreview
    {
        private const string LayoutFile = "medieval_layout.json";
        private const string OutDir = "Temp/MedievalLayout";

        // 环 A 外侧一排房子的中心半径：RA(17) + SHW(3.8) + HOUSE_D/2(3.255)
        private const float RingAHouseRadius = 24.055f;

        // 和游戏里同一套机位（TopDownCameraRig 默认值），用来看 2.5D 下的观感
        private const float GamePitch = 52f;
        private const float GameFov = 30f;

        /// <summary>并排拍这一组 prefab（换组合就改这个数组）。</summary>
        private static readonly string[] PieceRow =
        {
            "tree_broad", "tree_conifer", "tree_poplar", "tree_dead"
        };

        [MenuItem("Tools/My World/拍并排件图（4 棵树，改代码里的数组）", false, 51)]
        public static void CapturePieceRow()
        {
            if (EditorApplication.isPlaying || EditorApplication.isPlayingOrWillChangePlaymode)
            {
                Debug.LogWarning("[LayoutPreview] 当前在 Play 模式，已跳过。请先停止 Play。");
                return;
            }

            var catalog = BlenderKitCatalog.Load();
            if (catalog == null) { Debug.LogError("[LayoutPreview] 目录资源缺失，先跑一次导入。"); return; }

            var prevScene = SceneManager.GetActiveScene();
            var previewScene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
            SceneManager.SetActiveScene(previewScene);
            var holder = new GameObject("__PieceRow");
            var placed = new System.Collections.Generic.List<GameObject>();

            try
            {
                const float gap = 3.5f;
                for (int i = 0; i < PieceRow.Length; i++)
                {
                    var prefab = catalog.Find(PieceRow[i]);
                    if (prefab == null)
                    {
                        Debug.LogWarning("[LayoutPreview] 目录里没有 " + PieceRow[i] + "（先跑一次导入）。");
                        continue;
                    }
                    var go = Object.Instantiate(prefab, holder.transform);
                    go.name = PieceRow[i];
                    go.transform.localPosition = new Vector3((i - (PieceRow.Length - 1) * 0.5f) * gap, 0f, 0f);
                    placed.Add(go);
                }
                if (placed.Count == 0) { Debug.LogWarning("[LayoutPreview] 一件都没摆上。"); return; }

                var names = new System.Text.StringBuilder();
                for (int i = 0; i < placed.Count; i++)
                {
                    if (i > 0) names.Append(" / ");
                    names.Append(placed[i].name);
                }

                var bounds = BoundsOf(holder);
                // 地面：之前四棵树飘在蓝色虚空里，加一块地板才有落地感，也方便判断有没有悬空
                var ground = MakeGround(bounds, 60f);
                ground.transform.SetParent(holder.transform, true);

                // **正交**：一排物体用广角透视拍，两端的物体会外倾，看起来像模型自己是歪的
                // （Lead 反馈：白杨/枯树像向右歪了 30~45°）。正交没有透视收敛，能暴露真实姿态。
                const int W = 1600, H = 900;
                float orthoSize = Mathf.Max(bounds.extents.y, bounds.extents.x / ((float)W / H)) * 1.35f;
                Vector3 offset = Quaternion.Euler(28f, 0f, 0f) * Vector3.back * 150f;
                RenderOrtho(bounds.center + offset, bounds.center, orthoSize,
                            Path.Combine(OutDir, "pieces_row.png"), W, H, "并排件图（正交+地面）");

                Debug.Log("[LayoutPreview] 并排图（" + names + "）：" + Path.Combine(OutDir, "pieces_row.png")
                          + "，正交 orthoSize=" + orthoSize.ToString("0.##") + " 俯角 28°"
                          + "，整体包围盒 " + bounds.size.ToString("0.##") + " 米。");
            }
            finally
            {
                Object.DestroyImmediate(holder);
                if (prevScene.IsValid()) SceneManager.SetActiveScene(prevScene);
                EditorSceneManager.CloseScene(previewScene, true);
            }
        }

        [MenuItem("Tools/My World/布局目视验收（俯视 + 门朝街）", false, 50)]
        public static void CaptureBoth()
        {
            if (EditorApplication.isPlaying || EditorApplication.isPlayingOrWillChangePlaymode)
            {
                Debug.LogWarning("[LayoutPreview] 当前在 Play 模式，已跳过 —— 建场景 / 渲染 / 写 Assets "
                                 + "都可能打断 Play 会话。请先停止 Play。");
                return;
            }

            string layoutPath = BlenderKitMapBuilder.LayoutPath(LayoutFile);
            if (!File.Exists(layoutPath))
            {
                Debug.LogError("[LayoutPreview] 找不到布局文件：" + layoutPath);
                return;
            }

            var prevScene = SceneManager.GetActiveScene();
            var previewScene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
            SceneManager.SetActiveScene(previewScene);
            var holder = new GameObject("__LayoutPreview");

            try
            {
                var root = BlenderKitMapBuilder.Build(holder.transform, LayoutFile, "LayoutPreview");
                if (root == null) { Debug.LogError("[LayoutPreview] 生成失败，没有可拍的内容。"); return; }

                BlenderKitMapBuilder.LogPlacements(root, 6);

                var bounds = BoundsOf(root);
                if (bounds.size == Vector3.zero) { Debug.LogWarning("[LayoutPreview] 内容为空，跳过截图。"); return; }

                // 1) 俯视：只拍城墙以内（半径 45），这样 7.6 米宽的街道在图上还有 ~100 px
                var core = new Bounds(Vector3.zero, new Vector3(90f, bounds.size.y, 90f));
                RenderTopDown(core, Path.Combine(OutDir, "town_top.png"), 1400);

                // 2) 环 A 街道近景：站在广场一侧往回看，正对 45° 那排房子的门面
                float rad = RingAHouseRadius * Mathf.Cos(45f * Mathf.Deg2Rad);
                Vector3 housePos = BlenderKitMapBuilder.BlenderPosToUnity(rad, rad, 0f);
                Vector3 inward = (Vector3.zero - housePos).normalized;
                RenderFrom(housePos + inward * 24f + Vector3.up * 10f,
                           housePos + Vector3.up * 3f,
                           Path.Combine(OutDir, "town_doors.png"), 1400, 900, 38f);

                Debug.Log("[LayoutPreview] 两张图已写到 " + Path.GetFullPath(OutDir)
                          + "（Temp/，不进 Assets）。整体包围盒 " + bounds.size.ToString("0.##") + " 米。");
            }
            finally
            {
                Object.DestroyImmediate(holder);
                if (prevScene.IsValid()) SceneManager.SetActiveScene(prevScene);
                EditorSceneManager.CloseScene(previewScene, true);   // 不保存，直接扔掉
            }
        }

        // ------------------------------------------------------------------ 单件双角度（图集实验）

        private const string PieceViewName = "house_a";

        /// <summary>
        /// 图集实验专用：单件两个角度 —— 3/4 俯视（看得见屋顶）+ 正面（看得见墙和门）。
        /// 结论看的是**屋顶是红棕瓦还是白/灰/米色**，不是构图好不好看。
        /// </summary>
        [MenuItem("Tools/My World/拍单件双角度（house_a 图集实验）", false, 52)]
        public static void CapturePieceViews()
        {
            if (EditorApplication.isPlaying || EditorApplication.isPlayingOrWillChangePlaymode)
            {
                Debug.LogWarning("[LayoutPreview] 当前在 Play 模式，已跳过。请先停止 Play。");
                return;
            }

            var catalog = BlenderKitCatalog.Load();
            if (catalog == null) { Debug.LogError("[LayoutPreview] 目录资源缺失，先跑一次导入。"); return; }
            var prefab = catalog.Find(PieceViewName);
            if (prefab == null) { Debug.LogError("[LayoutPreview] 目录里没有 " + PieceViewName + "。"); return; }

            var prevScene = SceneManager.GetActiveScene();
            var previewScene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
            SceneManager.SetActiveScene(previewScene);
            var holder = new GameObject("__PieceViews");

            try
            {
                var go = Object.Instantiate(prefab, holder.transform);
                go.name = PieceViewName;
                go.transform.localPosition = Vector3.zero;

                var bounds = BoundsOf(go);
                var ground = MakeGround(bounds, 40f);
                ground.transform.SetParent(holder.transform, true);

                float dist = bounds.extents.magnitude / Mathf.Tan(35f * 0.5f * Mathf.Deg2Rad) * 1.15f;

                // 1) 3/4 俯视：右上方向、俯角 40° —— 屋顶占画面主体
                Vector3 roofEye = bounds.center + Quaternion.Euler(40f, 35f, 0f) * Vector3.back * dist;
                RenderFrom(roofEye, bounds.center, Path.Combine(OutDir, "house_a_roof.png"), 1400, 1000, 35f);

                // 2) 正面：门朝 −Z（实测），所以相机站在 −Z 侧、镜头抬到门头高度
                var frontEye = new Vector3(bounds.center.x, 2.6f, bounds.min.z - dist * 0.6f);
                var frontLook = new Vector3(bounds.center.x, 3.4f, bounds.center.z);
                RenderFrom(frontEye, frontLook, Path.Combine(OutDir, "house_a_front.png"), 1400, 1000, 35f);

                Debug.Log("[LayoutPreview] " + PieceViewName + " 双角度写出：house_a_roof.png / house_a_front.png"
                          + "，包围盒 " + bounds.size.ToString("0.##") + " 米。");
            }
            finally
            {
                Object.DestroyImmediate(holder);
                if (prevScene.IsValid()) SceneManager.SetActiveScene(prevScene);
                EditorSceneManager.CloseScene(previewScene, true);
            }
        }

        // ------------------------------------------------------------------ 渲染

        private static void RenderOrtho(Vector3 eye, Vector3 lookAt, float orthoSize,
                                        string outPath, int width, int height, string label)
        {
            var camGo = new GameObject("__OrthoCam");
            var lightGo = MakeLight();
            try
            {
                var cam = camGo.AddComponent<Camera>();
                cam.orthographic = true;
                cam.orthographicSize = orthoSize;
                cam.nearClipPlane = 0.3f;
                cam.farClipPlane = 2000f;
                Configure(cam);
                camGo.transform.position = eye;
                camGo.transform.LookAt(lookAt);

                Shoot(cam, eye, lookAt, outPath, width, height, label);
            }
            finally
            {
                Object.DestroyImmediate(lightGo);
                Object.DestroyImmediate(camGo);
            }
        }

        /// <summary>一块没有碰撞体的地板（Plane 默认 10×10 米，靠 localScale 撑大）。</summary>
        private static GameObject MakeGround(Bounds area, float size)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Plane);
            go.name = "__Ground";
            go.transform.localScale = new Vector3(size / 10f, 1f, size / 10f);
            go.transform.position = new Vector3(area.center.x, -0.012f, area.center.z);

            var col = go.GetComponent<Collider>();
            if (col != null) Object.DestroyImmediate(col);

            var r = go.GetComponent<MeshRenderer>();
            if (r != null)
            {
                var sh = Shader.Find("Universal Render Pipeline/Lit");
                if (sh == null) sh = Shader.Find("Standard");
                var m = new Material(sh);
                var c = new Color(0.42f, 0.46f, 0.31f);      // 暗草绿：有地面感但不抢件本身的颜色
                if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
                if (m.HasProperty("_Color")) m.SetColor("_Color", c);
                r.sharedMaterial = m;
            }
            return go;
        }

        private static void RenderTopDown(Bounds bounds, string outPath, int size)
        {
            var camGo = new GameObject("__LayoutTopCam");
            var lightGo = MakeLight();
            try
            {
                var cam = camGo.AddComponent<Camera>();
                cam.orthographic = true;
                cam.orthographicSize = Mathf.Max(bounds.extents.x, bounds.extents.z) * 1.05f;
                cam.nearClipPlane = 0.3f;
                cam.farClipPlane = 500f;
                Configure(cam);
                camGo.transform.position = bounds.center + Vector3.up * 200f;
                camGo.transform.rotation = Quaternion.Euler(90f, 0f, 0f);

                Shoot(cam, camGo.transform.position, bounds.center, outPath, size, size, "俯视");
            }
            finally
            {
                Object.DestroyImmediate(lightGo);
                Object.DestroyImmediate(camGo);
            }
        }

        private static void RenderFrom(Vector3 eye, Vector3 lookAt, string outPath, int width, int height, float fov)
        {
            var camGo = new GameObject("__LayoutDoorCam");
            var lightGo = MakeLight();
            try
            {
                var cam = camGo.AddComponent<Camera>();
                cam.orthographic = false;
                cam.fieldOfView = fov;
                cam.nearClipPlane = 0.3f;
                cam.farClipPlane = 2000f;
                Configure(cam);
                camGo.transform.position = eye;
                camGo.transform.LookAt(lookAt);

                Shoot(cam, eye, lookAt, outPath, width, height, "门朝街近景");
            }
            finally
            {
                Object.DestroyImmediate(lightGo);
                Object.DestroyImmediate(camGo);
            }
        }

        private static void Configure(Camera cam)
        {
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.53f, 0.72f, 0.83f);
            cam.allowHDR = false;
            cam.allowMSAA = false;
        }

        private static GameObject MakeLight()
        {
            var lightGo = new GameObject("__LayoutLight");
            var light = lightGo.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.15f;
            light.color = new Color(1f, 0.96f, 0.9f);
            lightGo.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            return lightGo;
        }

        private static void Shoot(Camera cam, Vector3 eye, Vector3 lookAt, string outPath,
                                  int width, int height, string label)
        {
            int liveRenderers = 0;
            foreach (var r in Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None))
                if (r.enabled && r.gameObject.activeInHierarchy && r.bounds.size != Vector3.zero) liveRenderers++;

            Debug.Log("[LayoutPreview] " + label + " 自检：cam=" + eye.ToString("0.##")
                      + " 看向=" + lookAt.ToString("0.##")
                      + " 视野坐标=" + cam.WorldToViewportPoint(lookAt).ToString("0.###")
                      + " 活 renderer=" + liveRenderers);

            var rt = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32);
            var prevActive = RenderTexture.active;
            cam.targetTexture = rt;
            // **渲染两次**：域重载/资源导入后的第一次 Camera.Render() 会出一张纯背景空图（已在导入器里实测过）
            cam.Render();
            cam.Render();
            RenderTexture.active = rt;
            var tex = new Texture2D(width, height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0f, 0f, width, height), 0, 0);
            tex.Apply();
            RenderTexture.active = prevActive;
            cam.targetTexture = null;

            string dir = Path.GetDirectoryName(outPath);
            if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir)) Directory.CreateDirectory(dir);
            File.WriteAllBytes(outPath, tex.EncodeToPNG());

            Object.DestroyImmediate(tex);
            rt.Release();
            Object.DestroyImmediate(rt);
        }

        private static Bounds BoundsOf(GameObject root)
        {
            var renderers = root.GetComponentsInChildren<Renderer>();
            bool any = false;
            var bounds = new Bounds(root.transform.position, Vector3.zero);
            foreach (var r in renderers)
            {
                if (r == null) continue;
                if (!any) { bounds = r.bounds; any = true; }
                else bounds.Encapsulate(r.bounds);
            }
            return bounds;
        }
    }
}
