using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// 一键安装 KayKit 法师角色：配置 FBX 导入器 → 建 URP 材质 → 抽出需要的动画剪辑
    /// → 建动画状态机 → 打包成角色预制体。
    ///
    /// 为什么用 Generic 而不是 Humanoid：KayKit 这套骨架用的是自己一套命名（`.l`/`.r` 后缀、
    /// `handslot.*`、`control-*`、`IK-*`），并且**没有手指骨**；本项目实测导入就是 Generic
    /// （`avatar == null`、`isHuman == false`），Generic 直接播原动画最稳。
    ///
    /// ⚠️ 本文原先写"这套骨架**只有 8 根**（root/hips/spine/chest/head + 单段手臂腿），缺少 Humanoid
    /// 必需的上下段手臂、手、脚等骨骼" —— **那个数字和那条理由都是错的**（T-026 订正）。
    /// 实测骨骼 **41 根 = 23 根身体骨 + 18 根 IK/控制骨**：
    ///   身体 23 = root / hips / spine / chest / head
    ///             + 双臂 5×2（upperarm / lowerarm / wrist / hand / handslot）
    ///             + 双腿 4×2（upperleg / lowerleg / foot / toes）
    ///   IK 18   = kneeIK / heelIK / IK-foot / IK-toe / control-toe-roll / control-heel-roll /
    ///             control-foot-roll / elbowIK / handIK（左右各半）
    /// 也就是说 upperarm / lowerarm / hand / upperleg / lowerleg / foot **全都在**。
    /// 「用 Generic」这个**结论不变**，只是理由要按实测写，别拿错的骨骼数当依据。
    ///
    /// 菜单：Tools → My World → 安装法师角色
    /// </summary>
    public static class MageSetup
    {
        private const string Root = "Assets/ThirdParty/KayKit_Adventurers";
        private const string FbxPath = Root + "/Mage.fbx";
        private const string TexPath = Root + "/mage_texture.png";
        private const string MatPath = Root + "/M_Mage.mat";
        private const string ClipDir = Root + "/Clips";
        private const string CtrlPath = Root + "/MageAnimator.controller";

        /// <summary>角色预制体路径。世界生成器要拿它做玩家外观，所以是 public。</summary>
        public const string PrefabPath = Root + "/MageCharacter.prefab";

        /// <summary>要抽出来的剪辑：源名匹配关键词 → (目标名, 是否循环)。</summary>
        private static readonly (string name, bool loop, string[] keys)[] Wanted =
        {
            ("Idle",   true,  new[] { "idle" }),
            ("Walk",   true,  new[] { "walking_a", "walking", "walk" }),
            ("Run",    true,  new[] { "running_a", "running", "run" }),
            ("Cast",   false, new[] { "spellcast_shoot", "spellcast", "spellcasting", "cast" }),
            ("Hit",    false, new[] { "hit_a", "hit" }),
            ("Death",  false, new[] { "death_a", "death", "die" }),
            // 剑的一套四段连招：横劈 → 下劈 → 斜劈 → 突刺。
            // FBX 里本来就有这四个单手攻击，当初只抽了上面 6 个，所以挥剑时没有动作可播。
            ("Attack_1", false, new[] { "1H_Melee_Attack_Slice_Horizontal" }),  // 横劈
            ("Attack_2", false, new[] { "1H_Melee_Attack_Chop" }),              // 下劈
            ("Attack_3", false, new[] { "1H_Melee_Attack_Slice_Diagonal" }),    // 斜劈
            ("Attack_4", false, new[] { "1H_Melee_Attack_Stab" }),              // 突刺（收招，带击退）
        };

        /// <summary>连招用的四个剪辑，顺序就是出招顺序。</summary>
        private static readonly string[] ComboClips = { "Attack_1", "Attack_2", "Attack_3", "Attack_4" };

        /// <summary>每段攻击的命中帧上要打的动画事件名。AnimEventRelay 上有同名方法。</summary>
        private const string SlashImpactEvent = "OnSlashImpact";

        /// <summary>
        /// 连招每一段的裁剪目标，三个数决定手感：
        ///   ComboLeadIn       —— 从剪辑开头到命中帧的时间（起势，太短会显得没有预备动作）
        ///   ComboClipLength   —— 每段总时长（四段必须一致，连招才连得顺）
        ///   ComboTrimTailMin  —— 命中之后至少留多少秒收招，不留会切得很生硬
        ///
        /// 为什么不用"动作包络自动找区间"：四个原始剪辑里到处都有超过 5% 阈值的小动作
        /// （站姿微调），包络几乎覆盖全长，实测裁出来还是 1.03s / 1.57s，等于没裁。
        /// 改成"以峰值帧为锚点、取固定长度的窗口"，四段节奏才统一。
        /// </summary>
        private const float ComboLeadIn = 0.20f;
        private const float ComboClipLength = 0.62f;
        private const float ComboTrimTailMin = 0.18f;

        /// <summary>
        /// 本脚本会**整个重建** controller 和角色预制体（见 BuildAnimator / BuildPrefab）。
        /// 所以任何手工加进去的东西——参数、状态、预制体上的组件——都必须写在这里，
        /// 否则重跑一次「安装法师角色」就会静默丢掉，症状是"挥剑又没动作了"。
        /// </summary>

        [MenuItem("Tools/My World/安装法师角色")]
        public static void Install()
        {
            ConfigureImporter();
            BuildTextureAndMaterial();
            var clips = ExtractClips();
            var ctrl = BuildAnimator(clips);
            BuildPrefab(ctrl);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            // 必须在这一步之后：见 PostProcessClips 的注释（Refresh 会冲掉未落盘的改动）
            PostProcessClips();

            // 也必须在这里：controller 是新建的资源、GUID 变了，场景里的旧引用会悬空
            RelinkSceneAnimators(ctrl);

            Debug.Log("[My World] 法师角色安装完成。");
        }

        // ---------------- 导入器 ----------------

        private static void ConfigureImporter()
        {
            var importer = AssetImporter.GetAtPath(FbxPath) as ModelImporter;
            if (importer == null)
            {
                Debug.LogError($"[My World] 找不到 {FbxPath}，先把 Mage.fbx 放进项目。");
                return;
            }

            importer.animationType = ModelImporterAnimationType.Generic;
            importer.importAnimation = true;
            // Unity 6 里 importMaterials 已移除，改用 materialImportMode。
            importer.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            // 交付的 FBX 已是 Y-up、正面 +Z，不需要再烘轴转换（重复转换会让角色躺倒/转 90°）。
            importer.bakeAxisConversion = false;
            importer.useFileScale = true;
            importer.globalScale = 1f;
            // 贴图用裸文件名引用，放同目录 + 全局搜索即可找到。
            importer.materialSearch = ModelImporterMaterialSearch.Everywhere;
            importer.materialLocation = ModelImporterMaterialLocation.External;

            importer.SaveAndReimport();
        }

        private static List<AnimationClip> SourceClips()
        {
            return AssetDatabase.LoadAllAssetsAtPath(FbxPath)
                .OfType<AnimationClip>()
                .Where(c => !c.name.StartsWith("__preview__"))
                .ToList();
        }

        // ---------------- 材质 ----------------

        private static void BuildTextureAndMaterial()
        {
            var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(TexPath);
            if (tex != null)
            {
                var ti = AssetImporter.GetAtPath(TexPath) as TextureImporter;
                if (ti != null)
                {
                    // 低多边形色块贴图用点采样更"脆"，也贴合这套美术风格。
                    ti.filterMode = FilterMode.Point;
                    ti.mipmapEnabled = false;
                    ti.SaveAndReimport();
                }
            }

            var shader = Shader.Find("Universal Render Pipeline/Lit");
            var mat = AssetDatabase.LoadAssetAtPath<Material>(MatPath);
            if (mat == null)
            {
                mat = new Material(shader) { name = "M_Mage" };
                AssetDatabase.CreateAsset(mat, MatPath);
            }
            mat.shader = shader;
            if (tex != null)
            {
                mat.SetTexture("_BaseMap", tex);
                mat.SetColor("_BaseColor", Color.white);
            }
            mat.SetFloat("_Metallic", 0f);
            mat.SetFloat("_Smoothness", 0.15f);
            EditorUtility.SetDirty(mat);
        }

        // ---------------- 抽剪辑 ----------------

        /// <summary>
        /// 把需要的动画从 FBX 里复制成独立的 .anim 资源。
        /// 为什么要复制：FBX 内的剪辑是只读子资源，改不了"是否循环"；而循环与否必须在这里定下来，
        /// 否则 Idle/Walk/Run 播一遍就停住，Cast/Hit/Death 又会鬼畜循环。
        /// 顺带只保留用得到的几个，不必把 **76** 个剪辑全塞进工程。
        /// （订正 R-003(a)：这里原先写 **78**，实测 `Mage.fbx` 是 **76** 个内嵌剪辑；78 无出处。）
        /// </summary>
        private static Dictionary<string, AnimationClip> ExtractClips()
        {
            if (!AssetDatabase.IsValidFolder(ClipDir))
                AssetDatabase.CreateFolder(Root, "Clips");

            var src = SourceClips();
            var result = new Dictionary<string, AnimationClip>();

            foreach (var (name, loop, keys) in Wanted)
            {
                AnimationClip found = null;
                foreach (var k in keys)
                {
                    // 先要求完全同名：FBX 里有一堆 2H_Melee_Idle / Jump_Idle 之类，
                    // 只按子串找会先撞上它们，把真正的 "Idle" 挤掉。
                    found = src.FirstOrDefault(c => string.Equals(c.name, k, System.StringComparison.OrdinalIgnoreCase));
                    if (found != null) break;
                }
                if (found == null)
                {
                    foreach (var k in keys)
                    {
                        found = src.FirstOrDefault(c => c.name.IndexOf(k, System.StringComparison.OrdinalIgnoreCase) >= 0);
                        if (found != null) break;
                    }
                }

                if (found == null)
                {
                    Debug.LogWarning($"[My World] 没找到动画 '{name}'（关键词 {string.Join("/", keys)}）");
                    continue;
                }

                string path = $"{ClipDir}/{name}.anim";
                AssetDatabase.DeleteAsset(path);

                var copy = Object.Instantiate(found);
                copy.name = name;
                var settings = AnimationUtility.GetAnimationClipSettings(copy);
                settings.loopTime = loop;
                AnimationUtility.SetAnimationClipSettings(copy, settings);

                AssetDatabase.CreateAsset(copy, path);
                result[name] = AssetDatabase.LoadAssetAtPath<AnimationClip>(path);
                Debug.Log($"[My World] 剪辑 {name} ← {found.name}（{(loop ? "循环" : "单次")}，{found.length:F2}s）");
            }

            return result;
        }

        /// <summary>
        /// 抽完、存盘、刷新**之后**再回头改剪辑内容（裁帧 + 打命中事件）。
        ///
        /// 为什么必须单独一遍：`Install()` 结尾会 `AssetDatabase.Refresh()`，而 Refresh 会从磁盘
        /// 重新导入 .anim，把"已经改过但还没落盘"的内存版本冲掉 —— 实测第一次跑时裁剪明明执行了
        /// （日志里有），读回来却还是 1.000s 且没有事件。放到存盘之后再改、再存一次就稳了。
        /// </summary>
        private static void PostProcessClips()
        {
            foreach (var name in ComboClips)
            {
                var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>($"{ClipDir}/{name}.anim");
                if (clip == null)
                {
                    Debug.LogWarning($"[My World] 后处理找不到剪辑 {name}");
                    continue;
                }

                // 顺序不能反：事件时间是相对剪辑自身的，裁完再测峰值才对。
                var range = ComboTrimRange(clip);
                TrimClip(clip, range.from, range.to);
                AddImpactEvent(clip);

                EditorUtility.SetDirty(clip);
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
        }

        /// <summary>
        /// 手臂链上的逐帧位移量。四个剪辑共用这一份测量，裁剪和命中帧都靠它。
        ///
        /// 只看 `.r` 侧（右手挥剑），并且把 upperarm / lowerarm / hand 三段都算进去 ——
        /// 单看手腕会漏掉"整条手臂抡起来"那种发力。
        /// </summary>
        private static float[] MotionProfile(AnimationClip clip, out int fps, out int frames)
        {
            fps = Mathf.Max(1, Mathf.RoundToInt(clip.frameRate));
            frames = Mathf.Max(2, Mathf.RoundToInt(clip.length * fps));
            var motion = new float[frames];

            foreach (var b in AnimationUtility.GetCurveBindings(clip))
            {
                var p = b.path.ToLowerInvariant();
                if (p.IndexOf("lowerarm.r") < 0 && p.IndexOf("hand.r") < 0 && p.IndexOf("upperarm.r") < 0)
                    continue;
                var curve = AnimationUtility.GetEditorCurve(clip, b);
                if (curve == null) continue;

                float prev = curve.Evaluate(0f);
                for (int i = 1; i < frames; i++)
                {
                    float v = curve.Evaluate(i / (float)fps);
                    motion[i] += Mathf.Abs(v - prev);
                    prev = v;
                }
            }
            return motion;
        }

        /// <summary>动作包络的峰值帧 —— 挥得最快的那一帧。</summary>
        private static int PeakFrame(float[] motion, int frames)
        {
            int peak = 1;
            for (int i = 1; i < frames; i++)
                if (motion[i] > motion[peak]) peak = i;
            return peak;
        }

        /// <summary>
        /// 以峰值帧为锚点，取一个固定长度的窗口：命中帧落在开头 ComboLeadIn 秒处，
        /// 总长 ComboClipLength 秒。四段用同一套参数，所以节奏一致。
        ///
        /// 越界时优先挪窗口而不是缩窗口 —— 缩了节奏就不齐了。
        /// </summary>
        private static (int from, int to) ComboTrimRange(AnimationClip clip)
        {
            int fps, frames;
            var motion = MotionProfile(clip, out fps, out frames);
            int peak = PeakFrame(motion, frames);

            int span = Mathf.Max(4, Mathf.RoundToInt(ComboClipLength * fps));
            int lead = Mathf.RoundToInt(ComboLeadIn * fps);
            int tail = Mathf.RoundToInt(ComboTrimTailMin * fps);
            span = Mathf.Max(span, lead + tail + 1);

            int from = peak - lead;
            int to = from + span - 1;

            if (to > frames - 1) { to = frames - 1; from = Mathf.Max(0, to - span + 1); }
            if (from < 0) { from = 0; to = Mathf.Min(frames - 1, span - 1); }
            if (to <= from) return (0, frames - 1);
            return (from, to);
        }

        /// <summary>
        /// 按帧区间裁剪剪辑：把每条曲线在 [from, to] 上重采样，并把时间轴平移回 0。
        ///
        /// 做法是"重采样"而不是"删掉范围外的关键帧"：后者会让那些在该区间内本来没有关键帧的
        /// 曲线（常量通道）整条变空，姿态就塌了。
        /// </summary>
        private static void TrimClip(AnimationClip clip, int fromFrame, int toFrame)
        {
            if (clip == null || toFrame <= fromFrame) return;

            float fps = clip.frameRate > 0f ? clip.frameRate : 30f;
            float start = fromFrame / fps;
            int count = Mathf.Max(2, toFrame - fromFrame + 1);

            int trimmed = 0;
            foreach (var b in AnimationUtility.GetCurveBindings(clip))
            {
                var curve = AnimationUtility.GetEditorCurve(clip, b);
                if (curve == null || curve.length == 0) continue;

                var keys = new Keyframe[count];
                for (int i = 0; i < count; i++)
                {
                    float src = start + i / fps;
                    keys[i] = new Keyframe(i / fps, curve.Evaluate(src));
                }
                var rebuilt = new AnimationCurve(keys);
                for (int i = 0; i < count; i++) rebuilt.SmoothTangents(i, 0f);

                AnimationUtility.SetEditorCurve(clip, b, rebuilt);
                trimmed++;
            }

            EditorUtility.SetDirty(clip);
            Debug.Log($"[My World] 裁剪 {clip.name}: 第 {fromFrame}..{toFrame} 帧，" +
                      $"新时长 {clip.length:F3}s（{trimmed} 条曲线重采样）");
        }

        /// <summary>
        /// 在剪辑上打命中帧事件。帧位**不写死**：取手臂链逐帧位移量的峰值帧 —— 挥得最快的那一帧，
        /// 也就是视觉上的命中点。裁剪之后重新测，所以时间始终是相对裁好的剪辑。
        ///
        /// 注意这只是启发式：角速度峰值通常略早于真正的接触帧，最终该按手感微调。
        /// </summary>
        private static void AddImpactEvent(AnimationClip clip)
        {
            if (clip == null) return;

            int fps, frames;
            var motion = MotionProfile(clip, out fps, out frames);

            int peak = 1;
            for (int i = 1; i < frames; i++)
                if (motion[i] > motion[peak]) peak = i;
            float t = peak / (float)fps;

            var ev = new AnimationEvent
            {
                functionName = SlashImpactEvent,
                time = t,
                messageOptions = SendMessageOptions.DontRequireReceiver,
            };
            AnimationUtility.SetAnimationEvents(clip, new[] { ev });
            EditorUtility.SetDirty(clip);
            Debug.Log($"[My World] 挥砍命中事件 {SlashImpactEvent} @ {t:F3}s" +
                      $"（第 {peak} 帧 / 共 {frames} 帧，实测角速度峰值）");
        }

        // ---------------- 动画状态机 ----------------

        private static AnimatorController BuildAnimator(Dictionary<string, AnimationClip> clips)
        {
            AssetDatabase.DeleteAsset(CtrlPath);
            var ctrl = AnimatorController.CreateAnimatorControllerAtPath(CtrlPath);

            ctrl.AddParameter("Speed", AnimatorControllerParameterType.Float);
            ctrl.AddParameter("Attack", AnimatorControllerParameterType.Trigger);
            ctrl.AddParameter("Hit", AnimatorControllerParameterType.Trigger);
            ctrl.AddParameter("Dead", AnimatorControllerParameterType.Bool);
            // 近战挥砍用独立触发器，不能复用 Attack：Attack 已经接到 Cast（施法）上了，
            // 而 PlayerMage.PlayCast() / PlayAttack() 原先共用同一个 hash，
            // 结果挥剑播的是法师原地念咒的动作。
            ctrl.AddParameter("Slash", AnimatorControllerParameterType.Trigger);
            // 连招推进到第几段（0..3）。代码每挥一刀把它 +1，Animator 按它挑对应的状态。
            ctrl.AddParameter("ComboStep", AnimatorControllerParameterType.Int);

            clips.TryGetValue("Idle", out var cIdle);
            clips.TryGetValue("Walk", out var cWalk);
            clips.TryGetValue("Run", out var cRun);
            clips.TryGetValue("Cast", out var cCast);
            clips.TryGetValue("Hit", out var cHit);
            clips.TryGetValue("Death", out var cDead);

            var sm = ctrl.layers[0].stateMachine;

            var idle = AddState(sm, "Idle", cIdle);
            var walk = AddState(sm, "Walk", cWalk);
            var run = AddState(sm, "Run", cRun);
            var cast = AddState(sm, "Cast", cCast);
            var hit = AddState(sm, "Hit", cHit);
            var dead = AddState(sm, "Death", cDead);

            sm.defaultState = idle;

            //  locomotion：Speed 由 PlayerController8Dir 喂一个语义化的值
            //  0 = 站住、0.5 = 走、1 = 跑，所以阈值取 0.15 / 0.75 最稳。
            FloatTransition(idle, walk, AnimatorConditionMode.Greater, 0.15f);
            FloatTransition(walk, idle, AnimatorConditionMode.Less, 0.15f);
            FloatTransition(walk, run, AnimatorConditionMode.Greater, 0.75f);
            FloatTransition(run, walk, AnimatorConditionMode.Less, 0.75f);
            FloatTransition(idle, run, AnimatorConditionMode.Greater, 0.75f);

            // 施法 / 受击 / 死亡：由参数打断，播完回 Idle（死亡不回）
            AnyStateTo(sm, cast, "Attack", AnimatorConditionMode.If, alsoRequireAlive: true);
            AnyStateTo(sm, hit, "Hit", AnimatorConditionMode.If, alsoRequireAlive: true);
            AnyStateTo(sm, dead, "Dead", AnimatorConditionMode.If, alsoRequireAlive: false);

            // 四段连招：横劈 → 下劈 → 斜劈 → 突刺。
            // 每段一个状态、一个 "Slash + ComboStep == n" 的 AnyState 过渡。
            // 之所以用 Int 而不是四个独立 Trigger：参数少，且 ComboStep 只会等于其中一个值，
            // 所以不管过渡列表的顺序如何，命中的那条都是唯一的，不存在歧义。
            for (int i = 0; i < ComboClips.Length; i++)
            {
                clips.TryGetValue(ComboClips[i], out var comboClip);
                var state = AddState(sm, "Attack" + (i + 1), comboClip);

                var t = sm.AddAnyStateTransition(state);
                t.hasExitTime = false;
                t.duration = 0.07f;
                // 允许打断自己：连招就是要在上一刀还没播完时接上下一刀
                t.canTransitionToSelf = true;
                t.AddCondition(AnimatorConditionMode.If, 0f, "Slash");
                t.AddCondition(AnimatorConditionMode.Equals, i, "ComboStep");
                t.AddCondition(AnimatorConditionMode.IfNot, 0f, "Dead");

                BackToIdle(state, idle);
            }

            BackToIdle(cast, idle);
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

        private static void AnyStateTo(
            AnimatorStateMachine sm, AnimatorState target, string param,
            AnimatorConditionMode mode, bool alsoRequireAlive,
            bool canTransitionToSelf = false)
        {
            var t = sm.AddAnyStateTransition(target);
            t.hasExitTime = false;
            t.duration = 0.08f;
            t.canTransitionToSelf = canTransitionToSelf;
            t.AddCondition(mode, 0f, param);
            // 死了就别再被打断去施法/受击
            if (alsoRequireAlive) t.AddCondition(AnimatorConditionMode.IfNot, 0f, "Dead");
        }

        private static void BackToIdle(AnimatorState from, AnimatorState idle)
        {
            var t = from.AddTransition(idle);
            t.hasExitTime = true;
            t.exitTime = 0.92f;   // 接近播完才回，避免动作被截断
            t.duration = 0.12f;
        }

        // ---------------- 预制体 ----------------

        /// <summary>
        /// 把已打开场景里、属于本角色预制体的 Animator 重新接上新 controller。
        ///
        /// 为什么必须做：`BuildAnimator` 是 `DeleteAsset` + `CreateAnimatorControllerAtPath`，
        /// 重建之后**内存里**场景实例持有的还是被销毁的那个 controller 对象 ——
        /// 表现是 Inspector 里引用丢失、动画不播、`SetTrigger` 全部静默失效（不报错）。
        /// 预制体因为是重建的所以没事，但场景里的实例不会自动跟着换。
        ///
        /// ⚠️ **订正（T-020，2026-09-29 实测）**：本文原先写"新资源拿到的是**新的 GUID**，于是旧 GUID 引用悬空"。
        /// **那个机制是错的**：实测 `AssetDatabase.DeleteAsset` 之后立刻在同一路径重建，
        /// **GUID 会被保留**（抛一个临时 controller 实测：删前/删后/重建后 guid 三次完全相同；
        /// 真实执行「安装敌人」后 `BarbarianAnimator.controller.meta` 的 guid 也未变）。
        /// 所以这条 relink 修的**不是** GUID 失配，而是**内存中悬空的旧对象引用**；
        /// 是否需要它、以及它到底救过哪一次事故，**尚未被证据确认**。
        /// 结论：这段逻辑保留（成本极低、方向无害），但**别再拿"新 GUID"当理由**。
        /// </summary>
        private static void RelinkSceneAnimators(AnimatorController ctrl)
        {
            if (ctrl == null) return;

            int n = 0;
            for (int i = 0; i < UnityEngine.SceneManagement.SceneManager.sceneCount; i++)
            {
                var scene = UnityEngine.SceneManagement.SceneManager.GetSceneAt(i);
                if (!scene.isLoaded) continue;

                foreach (var root in scene.GetRootGameObjects())
                {
                    foreach (var a in root.GetComponentsInChildren<Animator>(true))
                    {
                        var src = PrefabUtility.GetCorrespondingObjectFromSource(a.gameObject);
                        var srcPath = src != null
                            ? PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(src)
                            : null;
                        if (srcPath != PrefabPath) continue;
                        if (a.runtimeAnimatorController == ctrl) continue;

                        a.runtimeAnimatorController = ctrl;
                        EditorUtility.SetDirty(a);
                        n++;
                    }
                }

                if (n > 0)
                    UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(scene);
            }

            if (n > 0)
            {
                UnityEditor.SceneManagement.EditorSceneManager.SaveOpenScenes();
                Debug.Log($"[My World] 重新接上场景里 {n} 个 Animator 的 controller");
            }
        }

        private static void BuildPrefab(AnimatorController ctrl)
        {
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(FbxPath);
            if (model == null)
            {
                Debug.LogError($"[My World] 找不到模型 {FbxPath}");
                return;
            }

            var mat = AssetDatabase.LoadAssetAtPath<Material>(MatPath);

            var inst = (GameObject)PrefabUtility.InstantiatePrefab(model);
            inst.name = "MageVisual";

            // 这套模型自带 法杖/魔杖/魔法书(合)/魔法书(开) 四个附件，会互相穿插。
            // 武器现在由 WeaponMount 挂到 handslot 上，所以内置附件**全部关掉**，
            // 否则会和挂上去的武器重叠（出现两把法杖）。
            var keepWeapons = new string[0];
            var bodyRends = new List<Renderer>();

            foreach (var r in inst.GetComponentsInChildren<Renderer>(true))
            {
                if (mat != null) r.sharedMaterial = mat;

                bool isWeapon = r.name == "1H_Wand" || r.name == "2H_Staff"
                                || r.name.StartsWith("Spellbook");
                if (isWeapon && !keepWeapons.Contains(r.name))
                    r.enabled = false;
                else if (!isWeapon)
                    bodyRends.Add(r);
            }

            // 原点不在脚底：把身体最低点抬到 local y=0，否则角色会陷进地里。
            float minY = float.MaxValue;
            foreach (var r in bodyRends) minY = Mathf.Min(minY, r.bounds.min.y);
            if (minY < float.MaxValue && Mathf.Abs(minY) > 0.001f)
            {
                var p = inst.transform.localPosition;
                inst.transform.localPosition = new Vector3(p.x, p.y - minY, p.z);
                Debug.Log($"[My World] 脚底对齐：最低点 y={minY:F4} → 整体上移 {-minY:F4}");
            }

            var animator = inst.GetComponent<Animator>();
            if (animator == null) animator = inst.AddComponent<Animator>();
            animator.runtimeAnimatorController = ctrl;
            // 位移由 PlayerController8Dir 负责；动画带根位移会和 CharacterController 打架。
            animator.applyRootMotion = false;
            animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;

            // 动画事件转发器。**必须挂在这个物体上**：AnimationEvent 只在持有 Animator 的
            // GameObject 上找同名方法，不向上也不向下。而 PlayerCombat / PlayerMage 挂在
            // 父级 Player 上 —— 事件里直接写它们的方法名永远不会被调用，且不报错。
            if (inst.GetComponent<MyWorld.AnimEventRelay>() == null)
                inst.AddComponent<MyWorld.AnimEventRelay>();

            foreach (var r in inst.GetComponentsInChildren<Renderer>(true))
            {
                var b = r.bounds;
                Debug.Log($"[My World]   网格 {r.name,-18} 中心={b.center.ToString("F3")} 尺寸={b.size.ToString("F3")} " +
                          $"启用={r.enabled} 材质={(r.sharedMaterial != null ? r.sharedMaterial.name : "无")}");
            }

            PrefabUtility.SaveAsPrefabAsset(inst, PrefabPath);
            Object.DestroyImmediate(inst);
            Debug.Log($"[My World] 角色预制体: {PrefabPath}");
        }
    }
}
