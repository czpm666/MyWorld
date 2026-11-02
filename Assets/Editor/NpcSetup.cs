using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// 一键安装 KayKit 村民 NPC：抽 NPC 用剪辑 → 建 NPC 动画控制器 → 建换色材质 → 建 NPC 预制体。
    ///
    /// 为什么单独一份而不是复用 `MageSetup`：玩家角色和 NPC 的**动作集合不同**（NPC 不需要
    /// 四段连招/跳跃/格挡，只需要 Idle/Walk/Run/Talk），而且 NPC 预制体**不能**带玩家那套
    /// 攻击参数与事件中继 —— 两者共用一个控制器会让参数契约互相污染。
    ///
    /// 运行时契约（`NpcActor` 侧，名字不匹配不会报错、只会静默不动，见陷阱 20/21）：
    ///   * `Animator.SetFloat("Speed", 0..1)`：0=站住、0.5=走、1=跑（与玩家同一套语义与阈值）；
    ///   * `Animator.SetTrigger("Talk")`：说一句话时抬手比一下（**可选**，参数不存在时对方有保护）。
    ///
    /// 预制体形态（与 Lead 约定）：root 空物体（pivot = 脚底、朝向 +Z）+ 子物体 `NpcVisual`
    /// （Animator + 网格）。**不带** CharacterController / Collider / 交互脚本 —— 由 NpcFactory 在
    /// 实例化时补。尺寸按 `MageCharacter.prefab` 的未缩放原尺寸（运行时由工厂统一套 0.68）。
    ///
    /// 菜单：Tools → My World → 安装 NPC 角色
    /// </summary>
    public static class NpcSetup
    {
        private const string Root = "Assets/ThirdParty/KayKit_Adventurers";
        private const string FbxPath = Root + "/Mage.fbx";
        private const string BaseMatPath = Root + "/M_Mage.mat";
        private const string ClipDir = Root + "/NpcClips";
        private const string MatDir = Root + "/NpcMaterials";
        private const string CtrlPath = Root + "/NpcAnimator.controller";

        /// <summary>基础 NPC 预制体（NpcFactory / MapSceneSetup 指向它）。</summary>
        public const string PrefabPath = Root + "/NpcCharacter.prefab";

        /// <summary>参数名（NpcActor 侧必须逐字一致）。</summary>
        public const string SpeedParam = "Speed";
        public const string TalkTrigger = "Talk";

        /// <summary>视觉子物体名（NpcFactory 按名字找它来套缩放/换色）。</summary>
        public const string VisualName = "NpcVisual";

        /// <summary>
        /// 换色变体（后缀, 基色）。URP Lit 会把贴图乘 `_BaseColor`，所以乘一个近白的色相就能整身换色。
        /// 第一个变体同时作为基础预制体 `NpcCharacter.prefab` 的材质。
        /// </summary>
        private static readonly (string suffix, Color tint)[] Variants =
        {
            ("Villager", new Color(1.00f, 0.97f, 0.92f)),
            ("Blue",     new Color(0.72f, 0.82f, 1.00f)),
            ("Green",    new Color(0.74f, 0.92f, 0.72f)),
            ("Red",      new Color(1.00f, 0.74f, 0.72f)),
            ("Tan",      new Color(1.00f, 0.88f, 0.72f)),
        };

        /// <summary>
        /// 要抽的剪辑：(目标资产名, 是否循环, 源剪辑名)。
        /// `Talk` 复用 `Spellcast_Shoot`：这是这套 KayKit 动作里**唯一**的"抬手比划"类动作
        /// （没有专门的说话/挥手剪辑）；单次播放，抬手→停留→放下，读起来就是说话手势。
        /// 源名必须与 FBX 内实际剪辑名逐字一致（错名会抽出错的剪辑且日志看起来仍是成功）。
        /// </summary>
        private static readonly (string name, bool loop, string expectSource)[] Wanted =
        {
            ("Idle", true,  "Idle"),
            ("Walk", true,  "Walking_A"),
            ("Run",  true,  "Running_A"),
            ("Talk", false, "Spellcast_Shoot"),
        };

        /// <summary>换色变体预制体的路径（例如 `.../NpcCharacter_Blue.prefab`）。</summary>
        public static string VariantPrefabPath(string suffix)
        {
            return Root + "/NpcCharacter_" + suffix + ".prefab";
        }

        [MenuItem("Tools/My World/安装 NPC 角色")]
        public static void Install()
        {
            ConfigureImporter();
            EnsureFolder(ClipDir);
            EnsureFolder(MatDir);

            var clips = ExtractNpcClips();
            var ctrl = BuildNpcAnimator(clips);
            BuildNpcPrefabs(ctrl);

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log($"[My World] NPC 角色安装完成：{PrefabPath}（变体 {Variants.Length - 1} 个）。");
        }

        // ---------------- 导入器 ----------------

        /// <summary>
        /// 与 `MageSetup.ConfigureImporter` 同一套设置（Generic / 导入动画 / 外部材质）。
        /// 已经正确时**不重导**（19.5MB 的 FBX 重导一次十几秒，NPC 安装器常被单独重跑）。
        /// </summary>
        private static void ConfigureImporter()
        {
            var importer = AssetImporter.GetAtPath(FbxPath) as ModelImporter;
            if (importer == null)
            {
                Debug.LogError($"[My World] 找不到 {FbxPath} 的 ModelImporter。");
                return;
            }

            bool dirty = importer.animationType != ModelImporterAnimationType.Generic
                         || !importer.importAnimation
                         || importer.materialLocation != ModelImporterMaterialLocation.External;
            if (!dirty) return;

            importer.animationType = ModelImporterAnimationType.Generic;
            importer.importAnimation = true;
            importer.materialLocation = ModelImporterMaterialLocation.External;
            importer.SaveAndReimport();
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            string parent = System.IO.Path.GetDirectoryName(path)?.Replace('\\', '/');
            AssetDatabase.CreateFolder(parent, System.IO.Path.GetFileName(path));
        }

        // ---------------- 剪辑 ----------------

        private static Dictionary<string, AnimationClip> ExtractNpcClips()
        {
            var result = new Dictionary<string, AnimationClip>(StringComparer.OrdinalIgnoreCase);
            var sources = AssetDatabase.LoadAllAssetsAtPath(FbxPath)
                .OfType<AnimationClip>()
                .Where(c => !c.name.StartsWith("__preview__", StringComparison.Ordinal))
                .ToArray();

            for (int i = 0; i < Wanted.Length; i++)
            {
                var w = Wanted[i];
                var found = sources.FirstOrDefault(c => string.Equals(c.name, w.expectSource, StringComparison.OrdinalIgnoreCase))
                            ?? sources.FirstOrDefault(c => c.name.IndexOf(w.expectSource, StringComparison.OrdinalIgnoreCase) >= 0);

                if (found == null)
                {
                    Debug.LogError($"[My World] FBX 里找不到 NPC 剪辑源 {w.expectSource}（目标 {w.name}），已跳过。");
                    continue;
                }
                if (!string.Equals(found.name, w.expectSource, StringComparison.Ordinal))
                    Debug.LogError($"[My World] NPC 剪辑源名不匹配：{w.name} ← {found.name}（期望 {w.expectSource}）");

                // 复制成独立剪辑（与 MageSetup.ExtractClips 同一套路：改资产名 + loopTime）
                var copy = UnityEngine.Object.Instantiate(found) as AnimationClip;
                if (copy == null)
                {
                    Debug.LogError($"[My World] 复制 NPC 剪辑失败：{found.name}");
                    continue;
                }
                copy.name = w.name;
                var settings = AnimationUtility.GetAnimationClipSettings(copy);
                settings.loopTime = w.loop;
                AnimationUtility.SetAnimationClipSettings(copy, settings);

                string path = ClipDir + "/" + w.name + ".anim";
                AssetDatabase.DeleteAsset(path);
                AssetDatabase.CreateAsset(copy, path);
                var saved = AssetDatabase.LoadAssetAtPath<AnimationClip>(path) ?? copy;
                result[w.name] = saved;
                Debug.Log($"[My World] NPC 剪辑 {w.name} ← {found.name}（{(w.loop ? "循环" : "单次")}，{saved.length:F2}s）");
            }
            return result;
        }

        // ---------------- 控制器 ----------------

        private static AnimatorController BuildNpcAnimator(Dictionary<string, AnimationClip> clips)
        {
            AssetDatabase.DeleteAsset(CtrlPath);
            var ctrl = AnimatorController.CreateAnimatorControllerAtPath(CtrlPath);

            ctrl.AddParameter(SpeedParam, AnimatorControllerParameterType.Float);
            // Talk 是 Trigger：说一句话按一下，播一次手势就回 locomotion。
            ctrl.AddParameter(TalkTrigger, AnimatorControllerParameterType.Trigger);

            clips.TryGetValue("Idle", out var cIdle);
            clips.TryGetValue("Walk", out var cWalk);
            clips.TryGetValue("Run", out var cRun);
            clips.TryGetValue("Talk", out var cTalk);

            var sm = ctrl.layers[0].stateMachine;
            var idle = AddState(sm, "Idle", cIdle);
            var walk = AddState(sm, "Walk", cWalk);
            var run = AddState(sm, "Run", cRun);
            var talk = AddState(sm, "Talk", cTalk);
            sm.defaultState = idle;      // 有默认状态 → 不会出现 T-pose

            // locomotion：Speed 语义与玩家一致（0 站 / 0.5 走 / 1 跑），阈值取同一组 0.15 / 0.75。
            FloatTransition(idle, walk, AnimatorConditionMode.Greater, 0.15f);
            FloatTransition(walk, idle, AnimatorConditionMode.Less, 0.15f);
            FloatTransition(walk, run, AnimatorConditionMode.Greater, 0.75f);
            FloatTransition(run, walk, AnimatorConditionMode.Less, 0.75f);
            FloatTransition(idle, run, AnimatorConditionMode.Greater, 0.75f);

            // 说话手势：任何站/走/跑状态下都能被 Talk 触发打断一次（说完回 locomotion）。
            var tt = sm.AddAnyStateTransition(talk);
            tt.hasExitTime = false;
            tt.duration = 0.10f;
            tt.canTransitionToSelf = false;    // 连按不说得越来越快，等这一句说完
            tt.AddCondition(AnimatorConditionMode.If, 0f, TalkTrigger);

            // 出边：说完按当前速度回 Run/Walk/Idle（顺序见 AddMoveExit 的说明：
            // 先加带条件的边、后加 Idle 无条件边，Unity 按转移表顺序取第一条满足的）。
            AddMoveExit(talk, walk, run);
            BackToIdle(talk, idle);

            return ctrl;
        }

        private static AnimatorState AddState(AnimatorStateMachine sm, string name, AnimationClip clip)
        {
            var s = sm.AddState(name);
            s.motion = clip;
            // 与 MageSetup 同：不吃剪辑里没有的默认值，避免"某根骨被默认值拽回 T-pose"
            s.writeDefaultValues = false;
            return s;
        }

        private static void FloatTransition(AnimatorState from, AnimatorState to, AnimatorConditionMode mode, float v)
        {
            var t = from.AddTransition(to);
            t.hasExitTime = false;
            t.duration = 0.12f;
            t.AddCondition(mode, v, SpeedParam);
        }

        /// <summary>一次性动作播完按移动速度直接回 Walk/Run（先加带条件边，再加 Idle 边）。</summary>
        private static void AddMoveExit(AnimatorState from, AnimatorState walk, AnimatorState run)
        {
            var tRun = from.AddTransition(run);
            tRun.hasExitTime = true;
            tRun.exitTime = 0.90f;
            tRun.duration = 0.12f;
            tRun.AddCondition(AnimatorConditionMode.Greater, 0.75f, SpeedParam);

            var tWalk = from.AddTransition(walk);
            tWalk.hasExitTime = true;
            tWalk.exitTime = 0.90f;
            tWalk.duration = 0.12f;
            tWalk.AddCondition(AnimatorConditionMode.Greater, 0.15f, SpeedParam);
        }

        private static void BackToIdle(AnimatorState from, AnimatorState idle)
        {
            var t = from.AddTransition(idle);
            t.hasExitTime = true;
            t.exitTime = 0.90f;
            t.duration = 0.12f;
        }

        // ---------------- 材质与预制体 ----------------

        private static Material BuildVariantMaterial(string suffix, Color tint)
        {
            string path = MatDir + "/M_Npc_" + suffix + ".mat";
            if (AssetDatabase.LoadAssetAtPath<Material>(path) == null)
            {
                if (!AssetDatabase.CopyAsset(BaseMatPath, path))
                {
                    Debug.LogError($"[My World] 复制材质失败：{BaseMatPath} → {path}");
                    return AssetDatabase.LoadAssetAtPath<Material>(BaseMatPath);
                }
            }

            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null) return null;

            // URP Lit：_BaseColor 带 [MainColor]，会乘贴图；_Color 是旧 shader 别名，一起写保险。
            mat.SetColor("_BaseColor", tint);
            if (mat.HasProperty("_Color")) mat.SetColor("_Color", tint);
            EditorUtility.SetDirty(mat);
            return mat;
        }

        private static void BuildNpcPrefabs(AnimatorController ctrl)
        {
            for (int i = 0; i < Variants.Length; i++)
            {
                var variant = Variants[i];
                var mat = BuildVariantMaterial(variant.suffix, variant.tint);
                string prefabPath = i == 0 ? PrefabPath : VariantPrefabPath(variant.suffix);
                BuildNpcPrefab(ctrl, mat, prefabPath, "NpcCharacter" + (i == 0 ? string.Empty : "_" + variant.suffix));
            }
            AssetDatabase.SaveAssets();
        }

        private static void BuildNpcPrefab(AnimatorController ctrl, Material mat, string prefabPath, string rootName)
        {
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(FbxPath);
            if (model == null)
            {
                Debug.LogError($"[My World] 找不到 {FbxPath}，NPC 预制体生成被跳过。");
                return;
            }

            // root = 空物体（pivot 在脚底、朝向 +Z），视觉在子物体 NpcVisual —— 与 Lead 的 NpcFactory 约定。
            var root = new GameObject(rootName);
            try
            {
                var inst = PrefabUtility.InstantiatePrefab(model) as GameObject;
                if (inst == null)
                {
                    Debug.LogError("[My World] 实例化 Mage.fbx 失败。");
                    return;
                }

                inst.name = VisualName;
                inst.transform.SetParent(root.transform, false);

                var bodyRends = new List<Renderer>();
                foreach (var r in inst.GetComponentsInChildren<Renderer>(true))
                {
                    if (mat != null) r.sharedMaterial = mat;

                    // 与玩家同样的隐藏规则：模型自带的武器/法术书附件不显示（NPC 空手）。
                    bool isWeapon = r.name == "1H_Wand" || r.name == "2H_Staff"
                                    || r.name.StartsWith("Spellbook", StringComparison.Ordinal);
                    if (isWeapon) r.enabled = false;
                    else bodyRends.Add(r);
                }

                // 脚底对齐：把视觉最低点抬到 root 的 y=0（与 MageCharacter.prefab 同一做法）。
                if (bodyRends.Count > 0)
                {
                    float minY = bodyRends.Min(r => r.bounds.min.y);
                    var p = inst.transform.position;
                    p.y -= minY;
                    inst.transform.position = p;
                }

                var animator = inst.GetComponent<Animator>();
                if (animator == null) animator = inst.AddComponent<Animator>();
                animator.runtimeAnimatorController = ctrl;
                animator.avatar = null;                  // Generic rig：没有 avatar
                animator.applyRootMotion = false;        // 位移由 NpcActor/CharacterController 负责
                animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;

                PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
                Debug.Log($"[My World] NPC 预制体 {prefabPath}（root={rootName}，visual={VisualName}，"
                          + $"材质 {(mat != null ? mat.name : "<null>")}，网格 {bodyRends.Count} 个）");
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(root);
            }
        }
    }
}
