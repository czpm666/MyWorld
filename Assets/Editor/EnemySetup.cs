using System.Collections.Generic;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// 一键安装敌人（KayKit 蛮兵）：导入器 → 材质 → 抽动画 → 状态机 → 预制体。
    /// 和法师共用 KayKitCharacter 里的机械步骤，只有状态机不一样。
    ///
    /// 蛮兵自带斧和圆盾，正好对上"近战 + 盾击"的需求：
    /// 保留 1H_Axe（近战）和 Barbarian_Round_Shield（盾击），关掉 2H_Axe / Mug / 副手斧。
    ///
    /// 菜单：Tools → My World → 安装敌人
    /// </summary>
    public static class EnemySetup
    {
        private const string Root = "Assets/ThirdParty/KayKit_Adventurers";
        private const string Enemies = Root + "/Enemies";
        private const string Fbx = Enemies + "/Barbarian.fbx";
        private const string Tex = Enemies + "/barbarian_texture.png";
        private const string MatPath = Enemies + "/M_Barbarian.mat";
        private const string ClipDir = Enemies + "/Clips";
        private const string CtrlPath = Enemies + "/BarbarianAnimator.controller";

        public const string PrefabPath = Enemies + "/EnemyBarbarian.prefab";

        [MenuItem("Tools/My World/安装敌人")]
        public static void Install()
        {
            if (!KayKitCharacter.ConfigureImporter(Fbx)) return;

            var tex = KayKitCharacter.LoadPointTexture(Tex);
            var mat = KayKitCharacter.MakeLitAsset(MatPath, tex, 0.15f, "M_Barbarian");

            var clips = KayKitCharacter.ExtractClips(Fbx, ClipDir, Enemies, new[]
            {
                new KayKitCharacter.ClipSpec("Idle",   true,  "idle"),
                new KayKitCharacter.ClipSpec("Walk",   true,  "walking_a", "walking", "walk"),
                new KayKitCharacter.ClipSpec("Run",    true,  "running_a", "running", "run"),
                // 近战挥砍：用单手斧的横劈
                new KayKitCharacter.ClipSpec("Attack", false, "1H_Melee_Attack_Slice", "1H_Melee_Attack_Chop", "1H_Melee_Attack"),
                new KayKitCharacter.ClipSpec("Hit",    false, "hit_a", "hit"),
                new KayKitCharacter.ClipSpec("Death",  false, "death_a", "death"),
            });

            var ctrl = BuildAnimator(clips);

            // 保留斧 + 盾（近战和盾击要用），其余内置附件关掉。
            // 缩放 0.68 和玩家一致，两边身高才对得上。
            KayKitCharacter.BuildPrefab(Fbx, mat, ctrl, PrefabPath, "EnemyBarbarian",
                new[] { "1H_Axe", "Barbarian_Round_Shield" }, modelScale: 0.68f);

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            // 必须在这里：BuildAnimator 是 DeleteAsset + 新建 controller，**内存里**场景实例持有的
            // 还是被销毁的那个 controller 对象，重装后不会自动指向新建的那个（实测：3/3 敌人都是旧引用）。
            // 不重接的话，Inspector 里会显示为丢失引用，动画不播、SetTrigger 静默失效。
            // ⚠️ 注意**不要**再把原因写成"新 GUID" —— 实测（见下方注释）GUID 是保持不变的。
            RelinkSceneAnimators(ctrl);

            Debug.Log("[My World] 敌人安装完成。");
        }

        /// <summary>
        /// 把已打开场景里、属于敌人的 Animator 重新接上新 controller。
        ///
        /// ⚠️ **不能照抄 `MageSetup.RelinkSceneAnimators`**：那个版本是按"来源预制体路径"匹配的
        /// （`PrefabUtility.GetCorrespondingObjectFromSource` + `GetPrefabAssetPathOfNearestInstanceRoot`）。
        /// 而场景里的敌人是生成器用**普通 `Instantiate`** 造出来的副本
        /// （`MyWorldBootstrap.cs:211`），不是预制体实例 —— 实测场景 YAML 里它们的
        /// `m_PrefabInstance` / `m_CorrespondingSourceObject` **都是 `{fileID: 0}`**。
        /// 照抄的话 `GetCorrespondingObjectFromSource` 返回 null，一个都匹配不上，
        /// **静默重接 0 个** —— 正是要修的坑换了个地方复现。
        ///
        /// 所以这里改为**按组件找**：凡是挂着 `MyWorld.Enemy` 的物体，其自身和子物体上的 Animator
        /// 就是目标，不依赖任何预制体连接关系。
        ///
        /// 另外：无论重接几个都**一定打日志**（含 0 的情况）。查得到"0 个"才叫可诊断，查不到才是静默失败。
        /// </summary>
        private static void RelinkSceneAnimators(AnimatorController ctrl)
        {
            if (ctrl == null)
            {
                Debug.LogWarning("[My World] 敌人 controller 为 null，跳过场景重接。");
                return;
            }

            int enemies = 0;
            int relinked = 0;

            for (int i = 0; i < UnityEngine.SceneManagement.SceneManager.sceneCount; i++)
            {
                var scene = UnityEngine.SceneManagement.SceneManager.GetSceneAt(i);
                if (!scene.isLoaded) continue;

                int inScene = 0;
                foreach (var root in scene.GetRootGameObjects())
                {
                    foreach (var enemy in root.GetComponentsInChildren<MyWorld.Enemy>(true))
                    {
                        enemies++;
                        foreach (var a in enemy.GetComponentsInChildren<Animator>(true))
                        {
                            if (a.runtimeAnimatorController == ctrl) continue;
                            a.runtimeAnimatorController = ctrl;
                            EditorUtility.SetDirty(a);
                            inScene++;
                            relinked++;
                        }
                    }
                }

                if (inScene > 0)
                    UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(scene);
            }

            if (relinked > 0)
                UnityEditor.SceneManagement.EditorSceneManager.SaveOpenScenes();

            Debug.Log($"[My World] 敌人 Animator 重接：场景里找到 {enemies} 个 Enemy，重接 {relinked} 个 Animator"
                      + (relinked == 0 ? "（都已经是新 controller，或场景里没有敌人）" : ""));
        }

        /// <summary>敌人的状态机：Idle/Walk/Run 循环，Attack/Hit 单次，Death 常驻。</summary>
        private static AnimatorController BuildAnimator(Dictionary<string, AnimationClip> clips)
        {
            AssetDatabase.DeleteAsset(CtrlPath);
            var ctrl = AnimatorController.CreateAnimatorControllerAtPath(CtrlPath);

            ctrl.AddParameter("Speed", AnimatorControllerParameterType.Float);
            ctrl.AddParameter("Attack", AnimatorControllerParameterType.Trigger);
            ctrl.AddParameter("Hit", AnimatorControllerParameterType.Trigger);
            ctrl.AddParameter("Dead", AnimatorControllerParameterType.Bool);

            clips.TryGetValue("Idle", out var cIdle);
            clips.TryGetValue("Walk", out var cWalk);
            clips.TryGetValue("Run", out var cRun);
            clips.TryGetValue("Attack", out var cAttack);
            clips.TryGetValue("Hit", out var cHit);
            clips.TryGetValue("Death", out var cDead);

            var sm = ctrl.layers[0].stateMachine;

            var idle = AddState(sm, "Idle", cIdle);
            var walk = AddState(sm, "Walk", cWalk);
            var run = AddState(sm, "Run", cRun);
            var attack = AddState(sm, "Attack", cAttack);
            var hit = AddState(sm, "Hit", cHit);
            var dead = AddState(sm, "Death", cDead);

            sm.defaultState = idle;

            // Speed 语义和玩家一致：0=站住、0.5=走、1=跑
            FloatTransition(idle, walk, AnimatorConditionMode.Greater, 0.15f);
            FloatTransition(walk, idle, AnimatorConditionMode.Less, 0.15f);
            FloatTransition(walk, run, AnimatorConditionMode.Greater, 0.75f);
            FloatTransition(run, walk, AnimatorConditionMode.Less, 0.75f);
            FloatTransition(idle, run, AnimatorConditionMode.Greater, 0.75f);

            AnyStateTo(sm, attack, "Attack", alsoRequireAlive: true);
            AnyStateTo(sm, hit, "Hit", alsoRequireAlive: true);
            AnyStateTo(sm, dead, "Dead", alsoRequireAlive: false);

            BackToIdle(attack, idle);
            BackToIdle(hit, idle);

            return ctrl;
        }

        private static AnimatorState AddState(AnimatorStateMachine sm, string name, AnimationClip clip)
        {
            var s = sm.AddState(name);
            s.motion = clip;
            s.writeDefaultValues = false;
            return s;
        }

        private static void FloatTransition(AnimatorState from, AnimatorState to, AnimatorConditionMode mode, float v)
        {
            var t = from.AddTransition(to);
            t.hasExitTime = false;
            t.duration = 0.12f;
            t.AddCondition(mode, v, "Speed");
        }

        private static void AnyStateTo(AnimatorStateMachine sm, AnimatorState target, string param, bool alsoRequireAlive)
        {
            var t = sm.AddAnyStateTransition(target);
            t.hasExitTime = false;
            t.duration = 0.08f;
            t.canTransitionToSelf = false;
            t.AddCondition(AnimatorConditionMode.If, 0f, param);
            if (alsoRequireAlive) t.AddCondition(AnimatorConditionMode.IfNot, 0f, "Dead");
        }

        private static void BackToIdle(AnimatorState from, AnimatorState idle)
        {
            var t = from.AddTransition(idle);
            t.hasExitTime = true;
            t.exitTime = 0.9f;   // 接近播完才回，动作不会被截断
            t.duration = 0.12f;
        }
    }
}
