using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// NPC 一键安装：生成/修复 NPC 动画资产，然后把地图接到 NPC 预制体上。
    ///
    /// 背景：<see cref="NpcSetup.Install"/> 会生成 NpcAnimator.controller + NpcCharacter 预制体，
    /// 但**没有**任何东西把地图指向它 —— 各场景里 MapBootstrap.npcPrefab 目前指的是玩家预制体
    /// （MageCharacter），于是 18 个 NPC 套着玩家的控制器、同相位同步呼吸，看起来像雕像。
    /// 本文件负责补上这最后一跳，全部步骤幂等：重复点不叠加、没有变化就不写盘。
    ///
    /// 只做数据接线，不改任何场景文本文件，也不碰别人的脚本。
    /// </summary>
    public static class NpcInstallWiring
    {
        private const string NpcPrefabFolder = "Assets/ThirdParty/KayKit_Adventurers";
        private const string NpcPrefabNamePrefix = "NpcCharacter";
        private const string NpcPrefabPath = NpcPrefabFolder + "/NpcCharacter.prefab";
        private const string SceneFolder = "Assets/Scenes";
        private const string NpcPrefabField = "npcPrefab";

        [MenuItem("Tools/My World/NPC 一键安装（预制体 + 接入地图）", priority = 21)]
        public static void InstallAndWire()
        {
            if (!GuardEditMode()) return;

            Debug.Log("[NPC 安装] 第 1 步：生成/修复 NPC 动画资产（走 NpcSetup.Install）。");
            NpcSetup.Install();

            int attached = AttachIdleLife();
            int wired = WireScenes();

            Debug.Log($"[NPC 安装] 完成：给 {attached} 个 NPC 预制体补上 NpcIdleLife，把 {wired} 个 MapBootstrap 的 npcPrefab 接到 {NpcPrefabPath}。" +
                      " 若要立刻验证：打开 Assets/Scenes/RoaTown.unity 进 Play，18 个 NPC 应该各呼吸各的、偶尔抬手比划。");
        }

        [MenuItem("Tools/My World/NPC 只接入地图（不重新生成）", priority = 22)]
        public static void WireOnly()
        {
            if (!GuardEditMode()) return;
            if (AssetDatabase.LoadAssetAtPath<GameObject>(NpcPrefabPath) == null)
            {
                Debug.LogError($"[NPC 接入] 找不到 {NpcPrefabPath}，先跑「Tools/My World/NPC 一键安装（预制体 + 接入地图）」。");
                return;
            }
            int wired = WireScenes();
            Debug.Log($"[NPC 接入] 完成：{wired} 个 MapBootstrap 已指向 NPC 预制体。");
        }

        // ── 第 1.5 步：把 NpcIdleLife 挂到 NPC 预制体上 ──────────────
        // 为什么放在这里而不是改 NpcSetup.cs：NpcSetup.cs 是 Lead 点名的生成入口，
        // 少改一处就少一处撞车风险；这个组件是"接线"性质，本来就属于本文件。

        private static int AttachIdleLife()
        {
            List<string> paths = FindNpcPrefabs();
            int changed = 0;
            foreach (string path in paths)
            {
                GameObject root = PrefabUtility.LoadPrefabContents(path);
                if (root == null) continue;
                try
                {
                    if (root.GetComponent<NpcIdleLife>() != null) continue;

                    root.AddComponent<NpcIdleLife>();
                    PrefabUtility.SaveAsPrefabAsset(root, path);
                    changed++;
                    Debug.Log($"[NPC 安装] 给 {path} 挂上 NpcIdleLife。");
                }
                finally
                {
                    PrefabUtility.UnloadPrefabContents(root);
                }
            }
            return changed;
        }

        private static List<string> FindNpcPrefabs()
        {
            var result = new List<string>();
            string[] guids = AssetDatabase.FindAssets(NpcPrefabNamePrefix + " t:Prefab", new[] { NpcPrefabFolder });
            foreach (string guid in guids)
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                if (System.IO.Path.GetFileNameWithoutExtension(path).StartsWith(NpcPrefabNamePrefix))
                {
                    result.Add(path);
                }
            }
            return result;
        }

        // ── 第 2 步：把各场景的 npcPrefab 指向 NPC 预制体 ────────────

        private static int WireScenes()
        {
            var target = AssetDatabase.LoadAssetAtPath<GameObject>(NpcPrefabPath);
            if (target == null)
            {
                Debug.LogError($"[NPC 接入] 找不到 {NpcPrefabPath}，先跑「Tools/My World/安装 NPC 角色」生成它。");
                return 0;
            }

            int total = 0;
            foreach (string scenePath in CollectScenePaths())
            {
                total += WireScene(scenePath, target);
            }
            return total;
        }

        private static int WireScene(string scenePath, GameObject target)
        {
            Scene scene = SceneManager.GetSceneByPath(scenePath);
            bool openedByUs = false;

            if (!scene.IsValid() || !scene.isLoaded)
            {
                scene = EditorSceneManager.OpenScene(scenePath, OpenSceneMode.Additive);
                openedByUs = true;
            }

            int changed = 0;
            try
            {
                foreach (GameObject root in scene.GetRootGameObjects())
                {
                    foreach (MapBootstrap bootstrap in root.GetComponentsInChildren<MapBootstrap>(true))
                    {
                        var so = new SerializedObject(bootstrap);
                        SerializedProperty prop = so.FindProperty(NpcPrefabField);
                        if (prop == null)
                        {
                            Debug.LogWarning($"[NPC 接入] {scenePath} 的 {bootstrap.GetType().Name} 上找不到字段 {NpcPrefabField}，跳过。");
                            continue;
                        }

                        var current = prop.objectReferenceValue as GameObject;
                        if (current == target) continue;   // 幂等：已经是目标值就什么都不做

                        prop.objectReferenceValue = target;
                        so.ApplyModifiedPropertiesWithoutUndo();
                        EditorSceneManager.MarkSceneDirty(scene);
                        changed++;
                        Debug.Log($"[NPC 接入] {scenePath} / {bootstrap.GetType().Name}：npcPrefab " +
                                  $"{Describe(current)} → {NpcPrefabPath}");
                    }
                }

                if (changed > 0) EditorSceneManager.SaveScene(scene);
                else if (DiskDisagrees(scenePath, target))
                {
                    // 实战踩到的坑：内存里的场景已经是正确值，但磁盘上的 .unity 还是旧值
                    // （RoaTown 被别的进程在 08:37 写回旧 guid，而编辑器内存没变）。
                    // 这时只按 changed>0 判断就会"什么都没做"，Play 起来 NPC 依旧是玩家预制体。
                    // 内存是权威（上面刚读的就是它），所以这里强制回写一次。
                    Debug.LogWarning($"[NPC 接入] {scenePath}：内存里已指向 NPC 预制体，但磁盘上还是旧值" +
                                     "（有别的进程写过这个场景文件），已按内存里的值重新保存。");
                    EditorSceneManager.MarkSceneDirty(scene);
                    EditorSceneManager.SaveScene(scene);
                }
            }
            finally
            {
                if (openedByUs) EditorSceneManager.CloseScene(scene, true);
            }
            return changed;
        }

        /// <summary>只读地扫场景文本，看磁盘上的 npcPrefab 是不是已经指向目标预制体。</summary>
        private static bool DiskDisagrees(string scenePath, GameObject target)
        {
            string targetGuid = AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(target));
            if (string.IsNullOrEmpty(targetGuid)) return false;
            try
            {
                string text = System.IO.File.ReadAllText(scenePath);
                var m = System.Text.RegularExpressions.Regex.Match(
                    text, @"npcPrefab:\s*\{fileID:\s*-?\d+,\s*guid:\s*([0-9a-f]{32})");
                // 没有该字段的场景（比如 MyWorld/SampleScene）不碰。
                return m.Success && m.Groups[1].Value != targetGuid;
            }
            catch (System.Exception e)
            {
                Debug.LogWarning($"[NPC 接入] 读不了 {scenePath} 的文本，跳过磁盘一致性检查：{e.Message}");
                return false;
            }
        }

        private static string Describe(GameObject go)
        {
            if (go == null) return "<空>";
            string path = AssetDatabase.GetAssetPath(go);
            return string.IsNullOrEmpty(path) ? go.name : path;
        }

        /// <summary>Build Settings 里的场景 + Assets/Scenes 下所有场景，去掉重复。</summary>
        private static List<string> CollectScenePaths()
        {
            var paths = new List<string>();

            foreach (EditorBuildSettingsScene s in EditorBuildSettings.scenes)
            {
                if (s != null && s.enabled && !paths.Contains(s.path)) paths.Add(s.path);
            }

            foreach (string guid in AssetDatabase.FindAssets("t:Scene", new[] { SceneFolder }))
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                if (!paths.Contains(path)) paths.Add(path);
            }

            if (paths.Count == 0) Debug.LogWarning($"[NPC 接入] {SceneFolder} 下没找到任何场景。");
            return paths;
        }

        private static bool GuardEditMode()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                Debug.LogError("[NPC 安装] 现在在 Play 模式（或正在切换），先退出 Play 再跑，免得改到运行中的实例。");
                return false;
            }
            return true;
        }
    }
}
