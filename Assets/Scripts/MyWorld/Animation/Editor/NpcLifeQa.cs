using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// NPC 动画自检：不需要进 Play 模式，点一下就知道「NPC 会不会动」这条链路上哪一环断了。
    ///
    /// 链路是：NpcAnimator.controller（Idle/Talk 等状态）→ NpcCharacter.prefab（Animator + NpcIdleLife）
    /// → 各场景里 MapBootstrap.npcPrefab 指向它。任何一环断了，NPC 就会像雕像。
    /// 场景检查走**文本扫描**（只读 .unity 里的 npcPrefab guid），不开场景、不改任何东西。
    /// </summary>
    public static class NpcLifeQa
    {
        private const string Root = "Assets/ThirdParty/KayKit_Adventurers";
        private const string CtrlPath = Root + "/NpcAnimator.controller";
        private const string PrefabPath = Root + "/NpcCharacter.prefab";
        private const string SceneFolder = "Assets/Scenes";

        // 注意：菜单名里**不能出现 `/`**。Unity 会把 `/` 当成子菜单层级，含多个 `/` 的菜单会注册不上，
        // ExecuteMenuItem 直接报 no menu named（实测：`预制体 / 控制器 / 地图接线` 就是点不到，换 `·` 立刻可用）。
        [MenuItem("Tools/My World/NPC 自检（预制体 · 控制器 · 地图接线）", priority = 23)]
        public static void Run()
        {
            var sb = new StringBuilder();
            sb.AppendLine("[NPC 自检] NPC 会不会动？");
            bool allGood = true;

            // ---- 1) 控制器 ----
            sb.AppendLine();
            sb.AppendLine("① 控制器 " + CtrlPath);
            var ac = AssetDatabase.LoadAssetAtPath<AnimatorController>(CtrlPath);
            if (ac == null)
            {
                sb.AppendLine("   ** 不存在 → 先跑「Tools/My World/NPC 一键安装（预制体 + 接入地图）」");
                allGood = false;
            }
            else
            {
                allGood &= CheckParam(sb, ac, "Speed", AnimatorControllerParameterType.Float);
                allGood &= CheckParam(sb, ac, "Talk", AnimatorControllerParameterType.Trigger);
                allGood &= CheckState(sb, ac, "Idle");
                CheckState(sb, ac, "Walk");   // 这两个是"以后想加巡逻"用的，缺了不算失败
                CheckState(sb, ac, "Run");
                sb.AppendLine("   参数 " + ac.parameters.Length + " 个，状态 " + ac.layers[0].stateMachine.states.Length + " 个");
            }

            // ---- 2) 预制体 ----
            sb.AppendLine();
            sb.AppendLine("② 预制体 " + PrefabPath);
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
            if (prefab == null)
            {
                sb.AppendLine("   ** 不存在 → 同上，先跑一键安装");
                allGood = false;
            }
            else
            {
                var animator = prefab.GetComponentInChildren<Animator>(true);
                if (animator == null)
                {
                    sb.AppendLine("   ** 预制体上没有 Animator");
                    allGood = false;
                }
                else
                {
                    bool wired = animator.runtimeAnimatorController != null;
                    sb.AppendLine("   Animator 控制器：" + (wired ? animator.runtimeAnimatorController.name : "** 空（NPC 完全静止）**"));
                    allGood &= wired;
                    if (wired && ac != null && animator.runtimeAnimatorController != ac)
                    {
                        sb.AppendLine("   ⚠ 指向的不是 " + CtrlPath + "，而是 " + animator.runtimeAnimatorController.name);
                    }
                }

                bool hasLife = prefab.GetComponent<NpcIdleLife>() != null;
                sb.AppendLine("   NpcIdleLife：" + (hasLife ? "有（随机相位/张望/手势）" : "** 没有（18 个 NPC 会同相位同步呼吸）**"));
                allGood &= hasLife;
            }

            int variantCount = CountVariants();
            sb.AppendLine("   变体预制体：" + variantCount + " 个（每个都会自动带上 NpcIdleLife）");

            // ---- 3) 地图接线 ----
            sb.AppendLine();
            sb.AppendLine("③ 各场景的 MapBootstrap.npcPrefab");
            string npcGuid = AssetDatabase.AssetPathToGUID(PrefabPath);
            string playerGuid = AssetDatabase.AssetPathToGUID(MageSetup.PrefabPath);
            int wiredScenes = 0;
            foreach (string scenePath in Directory.GetFiles(SceneFolder, "*.unity", SearchOption.AllDirectories))
            {
                string unityPath = scenePath.Replace('\\', '/');
                string text;
                try { text = File.ReadAllText(scenePath); }
                catch (IOException e) { sb.AppendLine("   " + unityPath + "：读取失败 " + e.Message); continue; }

                var guids = new List<string>();
                foreach (System.Text.RegularExpressions.Match m in
                         System.Text.RegularExpressions.Regex.Matches(text, @"npcPrefab:\s*\{fileID:\s*-?\d+,\s*guid:\s*([0-9a-f]{32})"))
                {
                    string g = m.Groups[1].Value;
                    if (!guids.Contains(g)) guids.Add(g);
                }

                if (guids.Count == 0)
                {
                    sb.AppendLine("   " + unityPath + "：没有 npcPrefab 字段（应该不是地图场景，跳过）");
                    continue;
                }

                foreach (string g in guids)
                {
                    string path = AssetDatabase.GUIDToAssetPath(g);
                    bool isNpc = g == npcGuid;
                    bool isPlayer = g == playerGuid;
                    string label = isNpc ? "✅ NPC 预制体"
                                 : isPlayer ? "** 还是玩家预制体（NPC 会套着法师控制器、不会说话）**"
                                 : "? " + (string.IsNullOrEmpty(path) ? g : path);
                    sb.AppendLine("   " + unityPath + "：" + label);
                    if (isNpc) wiredScenes++;
                    else allGood = false;
                }
            }
            if (wiredScenes == 0)
            {
                sb.AppendLine("   ** 没有任何场景接上 NPC 预制体 → 跑「Tools/My World/NPC 只接入地图（不重新生成）」");
            }

            // ---- 4) 结论 ----
            sb.AppendLine();
            sb.AppendLine(allGood
                ? "[NPC 自检] 通过：控制器 / 预制体 / 地图接线都到位。进 Play 应该能看到 NPC 各呼吸各的、偶尔抬手比划；" +
                  "这一条是静态检查，**观感没验证过**，请自己看一眼。"
                : "[NPC 自检] **有不通过项**，见上面标 ** 的行。");

            if (allGood) Debug.Log(sb.ToString());
            else Debug.LogWarning(sb.ToString());
        }

        private static bool CheckParam(StringBuilder sb, AnimatorController ac, string name, AnimatorControllerParameterType type)
        {
            foreach (AnimatorControllerParameter p in ac.parameters)
            {
                if (p.name != name) continue;
                if (p.type == type)
                {
                    sb.AppendLine("   参数 " + name + "：" + p.type + " ✅");
                    return true;
                }
                sb.AppendLine("   ** 参数 " + name + " 类型是 " + p.type + "，应为 " + type);
                return false;
            }
            sb.AppendLine("   ** 缺少参数 " + name);
            return false;
        }

        private static bool CheckState(StringBuilder sb, AnimatorController ac, string name)
        {
            foreach (ChildAnimatorState cs in ac.layers[0].stateMachine.states)
            {
                if (cs.state.name == name)
                {
                    sb.AppendLine("   状态 " + name + "：" + cs.state.motion?.name + " ✅");
                    return true;
                }
            }
            sb.AppendLine("   ** 缺少状态 " + name);
            return false;
        }

        private static int CountVariants()
        {
            int n = 0;
            foreach (string guid in AssetDatabase.FindAssets("NpcCharacter t:Prefab", new[] { Root }))
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                if (Path.GetFileNameWithoutExtension(path).StartsWith("NpcCharacter")) n++;
            }
            return n;
        }
    }
}
