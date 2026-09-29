using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// 生成可游玩场景。
    ///
    /// 流程：新建空场景 → 放一个挂 MyWorldBootstrap 的物体 → 立刻烘焙
    /// （在编辑期就把世界生成成真实对象 + 真实资源）→ 保存 → 设为构建首场景。
    ///
    /// 烘焙后 Hierarchy 里能看到 World / Sun / Player / Main Camera / DioramaPostFx，
    /// 都是可选中、可拖动、可删除的普通物体；buildOnPlay 为 false，Play 时不会再生成一遍。
    ///
    /// 手工点：菜单 Tools → My World → 生成世界场景 / 重建世界内容
    /// 批处理：Unity.exe -batchmode -quit -executeMethod MyWorld.EditorTools.MyWorldSceneSetup.GenerateFromBatch
    /// </summary>
    public static class MyWorldSceneSetup
    {
        private const string SceneFolder = "Assets/Scenes";
        private const string ScenePath = "Assets/Scenes/MyWorld.unity";

        /// <summary>新建场景并烘焙出整套世界内容。</summary>
        [MenuItem("Tools/My World/生成世界场景 %#g")]
        public static void Generate()
        {
            // 交互执行时先给用户一次保存改动的机会；批处理下没有 UI，直接跳过。
            if (!Application.isBatchMode)
                EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo();

            EnsureFolder("Assets", "Scenes");

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            var go = new GameObject("MyWorld");
            var bootstrap = go.AddComponent<MyWorldBootstrap>();

            MyWorldBaker.Bake(bootstrap);

            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene, ScenePath))
                Debug.LogError($"[My World] 场景保存失败: {ScenePath}");

            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            Debug.Log($"[My World] 场景已生成并烘焙: {ScenePath} —— 按 Play 即可游玩。");
        }

        /// <summary>只重建当前打开场景里的世界内容（保留场景本身和 bootstrap）。</summary>
        [MenuItem("Tools/My World/重建世界内容")]
        public static void RebuildCurrent()
        {
            var bootstrap = Object.FindFirstObjectByType<MyWorldBootstrap>();
            if (bootstrap == null)
            {
                EditorUtility.DisplayDialog(
                    "My World",
                    "当前场景里没有 MyWorldBootstrap。\n请先执行 Tools → My World → 生成世界场景。",
                    "OK");
                return;
            }

            MyWorldBaker.Bake(bootstrap);

            EditorSceneManager.MarkSceneDirty(bootstrap.gameObject.scene);
            EditorSceneManager.SaveOpenScenes();
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            Debug.Log("[My World] 世界内容已重建并烘焙。");
        }

        /// <summary>批处理入口，不带对话框。</summary>
        public static void GenerateFromBatch()
        {
            Generate();
        }

        private static void EnsureFolder(string parent, string leaf)
        {
            if (!AssetDatabase.IsValidFolder($"{parent}/{leaf}"))
                AssetDatabase.CreateFolder(parent, leaf);
        }
    }
}
