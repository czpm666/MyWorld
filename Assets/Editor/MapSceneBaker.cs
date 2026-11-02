using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// 把「运行时生成的地图」烘焙成场景里的真实物体。
    ///
    /// 背景：`MapBootstrap` 是在 Awake 里用 C# 现场生成整张地图的，所以 .unity 文件只有 6 KB，
    /// 打开场景是空的、必须按 Play 才看得见。这样没法手工微调（挪一个酒桶都要改代码）。
    ///
    /// 烘焙后：
    ///   · 地图变成场景里真实的 GameObject，打开场景就能看见、能拖、能删
    ///   · `bakedIntoScene = true`，进 Play 不会再生成第二份（否则会和老地图重叠）
    ///   · 想回到"改常数重生成"的模式，用菜单「还原为程序化生成」
    /// </summary>
    public static class MapSceneBaker
    {
        private const string WorldName = "World";
        private const string PlayerName = "Player";

        // ==================== 烘焙 ====================

        [MenuItem("Tools/My World/烘焙地图进场景", false, 41)]
        public static void Bake()
        {
            if (EditorApplication.isPlaying)
            {
                Debug.LogError("[MapSceneBaker] 请先退出 Play 模式再烘焙。");
                return;
            }

            var scene = EditorSceneManager.GetActiveScene();
            var boots = Object.FindObjectsByType<MapBootstrap>(FindObjectsSortMode.None);
            if (boots.Length == 0)
            {
                Debug.LogError("[MapSceneBaker] 当前场景（" + scene.name +
                               "）里没有 MapBootstrap 组件。请先打开 RoaTown / BuenaVillage / RanoaAcademy 之一。");
                return;
            }
            if (boots.Length > 1)
            {
                Debug.LogError("[MapSceneBaker] 场景里有 " + boots.Length + " 个 MapBootstrap，不知道该烘焙哪个。");
                return;
            }

            var boot = boots[0];
            string bootName = boot.gameObject.name;

            try
            {
                EditorUtility.DisplayProgressBar("烘焙地图", "正在生成地图内容…", 0.35f);

                // BuildAll 内部会先 ClearGenerated()，所以重复烘焙不会叠加
                boot.BuildAll();

                EditorUtility.DisplayProgressBar("烘焙地图", "正在统计并持久化…", 0.7f);

                var world = boot.transform.Find(WorldName);
                int renderers = world ? world.GetComponentsInChildren<Renderer>(true).Length : 0;
                int colliders = world ? world.GetComponentsInChildren<Collider>(true).Length : 0;
                int transforms = world ? world.GetComponentsInChildren<Transform>(true).Length : 0;

                // 运行时 new 出来的 Mesh / Material 不是资源，但 Unity 在保存场景时会把它们
                // 内嵌进 .unity 文件里（savedObjects），所以这里只需要记数，不需要 CreateAsset。
                var meshes = new HashSet<Mesh>();
                var mats = new HashSet<Material>();
                if (world)
                {
                    foreach (var r in world.GetComponentsInChildren<Renderer>(true))
                    {
                        foreach (var m in r.sharedMaterials) if (m) mats.Add(m);
                        var mf = r.GetComponent<MeshFilter>();
                        if (mf && mf.sharedMesh) meshes.Add(mf.sharedMesh);
                        var smr = r as SkinnedMeshRenderer;
                        if (smr && smr.sharedMesh) meshes.Add(smr.sharedMesh);
                    }
                    foreach (var mc in world.GetComponentsInChildren<MeshCollider>(true))
                        if (mc.sharedMesh) meshes.Add(mc.sharedMesh);
                }

                // 标记已烘焙 → Awake 不再重建
                var so = new SerializedObject(boot);
                var prop = so.FindProperty("bakedIntoScene");
                if (prop != null)
                {
                    prop.boolValue = true;
                    so.ApplyModifiedPropertiesWithoutUndo();
                }
                EditorUtility.SetDirty(boot);

                EditorUtility.DisplayProgressBar("烘焙地图", "正在保存场景…", 0.9f);
                EditorSceneManager.MarkSceneDirty(scene);
                bool ok = EditorSceneManager.SaveScene(scene);

                long bytes = 0;
                string path = scene.path;
                if (!string.IsNullOrEmpty(path) && System.IO.File.Exists(path))
                    bytes = new System.IO.FileInfo(path).Length;

                Debug.Log(string.Format(
                    "[MapSceneBaker] 烘焙完成：场景={0} 引导物={1} renderer={2} collider={3} transform={4} " +
                    "mesh={5} material={6} 场景体积={7:F1} KB 保存={8}",
                    scene.name, bootName, renderers, colliders, transforms, meshes.Count, mats.Count, bytes / 1024f, ok));

                // 不弹窗（弹窗会阻塞 MCP 调用），结果看 Console 日志
            }
            finally
            {
                EditorUtility.ClearProgressBar();
            }
        }

        // ==================== 还原 ====================

        [MenuItem("Tools/My World/还原为程序化生成", false, 42)]
        public static void Unbake()
        {
            if (EditorApplication.isPlaying)
            {
                Debug.LogError("[MapSceneBaker] 请先退出 Play 模式。");
                return;
            }

            var scene = EditorSceneManager.GetActiveScene();
            var boots = Object.FindObjectsByType<MapBootstrap>(FindObjectsSortMode.None);
            if (boots.Length == 0)
            {
                Debug.LogError("[MapSceneBaker] 当前场景里没有 MapBootstrap。");
                return;
            }

            // 不做确认弹窗（会阻塞 MCP）；删了也能重新烘焙回来

            int removed = 0;
            var boot = boots[0];

            var world = boot.transform.Find(WorldName);
            if (world) { Object.DestroyImmediate(world.gameObject); removed++; }

            // Player 是场景根对象（ClearGenerated 用 GameObject.Find 找它）
            var roots = scene.GetRootGameObjects();
            foreach (var go in roots)
            {
                if (go == null) continue;
                if (go == boot.gameObject) continue;
                if (go.name == WorldName || go.name == PlayerName)
                {
                    Object.DestroyImmediate(go);
                    removed++;
                }
            }

            var so = new SerializedObject(boot);
            var prop = so.FindProperty("bakedIntoScene");
            if (prop != null)
            {
                prop.boolValue = false;
                so.ApplyModifiedPropertiesWithoutUndo();
            }
            EditorUtility.SetDirty(boot);

            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene);
            Debug.Log("[MapSceneBaker] 已还原为程序化生成，移除对象 " + removed + " 个。");
        }

        // ==================== 查询状态 ====================

        [MenuItem("Tools/My World/当前场景是否已烘焙", false, 43)]
        public static void ReportState()
        {
            var scene = EditorSceneManager.GetActiveScene();
            var boots = Object.FindObjectsByType<MapBootstrap>(FindObjectsSortMode.None);
            if (boots.Length == 0)
            {
                Debug.Log("[MapSceneBaker] 场景 " + scene.name + " 里没有 MapBootstrap。");
                return;
            }
            var boot = boots[0];
            var so = new SerializedObject(boot);
            var baked = so.FindProperty("bakedIntoScene");
            var onPlay = so.FindProperty("buildOnPlay");
            var world = boot.transform.Find(WorldName);
            int count = world ? world.GetComponentsInChildren<Transform>(true).Length : 0;
            Debug.Log(string.Format("[MapSceneBaker] 场景={0} bakedIntoScene={1} buildOnPlay={2} World子物体={3}",
                scene.name, baked != null && baked.boolValue, onPlay != null && onPlay.boolValue, count));
        }
    }
}
