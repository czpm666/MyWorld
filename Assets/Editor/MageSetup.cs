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

        /// <summary>
        /// 要抽出来的剪辑：(目标名, 是否循环, 匹配关键词, **期望的源剪辑名**)。
        ///
        /// ⚠️ `expectSource` 是 T-050 加的**白名单断言**（监察部要求）。
        /// 为什么需要：`剪辑 X ← 源名` 那条日志**只能证明"找到了某条"，证不了"找到的是对的那条"** ——
        /// 反例：日志打 `剪辑 Ranged_Shoot ← 1H_Ranged_Shooting` 也是"成功"的样子，但那是 48 帧的连射剪辑。
        /// 抽取后逐条断言 `found.name == expectSource`，不等即 LogError（见 ExtractClips）。
        /// 这里 11 条源名的值都来自 headless Blender 实测（`tools/list_fbx_clips.py`），不是猜的。
        /// </summary>
        private static readonly (string name, bool loop, string[] keys, string expectSource)[] Wanted =
        {
            ("Idle",   true,  new[] { "idle" }, "Idle"),
            ("Walk",   true,  new[] { "walking_a", "walking", "walk" }, "Walking_A"),
            ("Run",    true,  new[] { "running_a", "running", "run" }, "Running_A"),
            ("Cast",   false, new[] { "spellcast_shoot", "spellcast", "spellcasting", "cast" }, "Spellcast_Shoot"),
            ("Hit",    false, new[] { "hit_a", "hit" }, "Hit_A"),
            ("Death",  false, new[] { "death_a", "death", "die" }, "Death_A"),
            // 剑的一套四段连招：横劈 → 下劈 → 斜劈 → 突刺。
            // FBX 里本来就有这四个单手攻击，当初只抽了上面 6 个，所以挥剑时没有动作可播。
            ("Attack_1", false, new[] { "1H_Melee_Attack_Slice_Horizontal" }, "1H_Melee_Attack_Slice_Horizontal"),  // 横劈
            ("Attack_2", false, new[] { "1H_Melee_Attack_Chop" }, "1H_Melee_Attack_Chop"),                          // 下劈
            ("Attack_3", false, new[] { "1H_Melee_Attack_Slice_Diagonal" }, "1H_Melee_Attack_Slice_Diagonal"),      // 斜劈
            ("Attack_4", false, new[] { "1H_Melee_Attack_Stab" }, "1H_Melee_Attack_Stab"),                          // 突刺（带击退）
            // ---- T-050 弓：事件驱动（用户拍板）----
            // ⚠️ 取 `1H_Ranged_Shoot`（32 帧 / 1.0667s），**不是** `1H_Ranged_Shooting`（48 帧 / 1.600s，
            //    那是一条 0.4s 无缝循环的待机摇摆，按单次播会在末尾突然跳回起手位）。
            //    `"1H_Ranged_Shooting"` **包含** `"1H_Ranged_Shoot"` 这个子串，所以只靠"先全名后子串"的
            //    匹配有静默绑错的风险 —— 上面 expectSource 就是为这条加的保险。
            ("Ranged_Shoot", false, new[] { "1H_Ranged_Shoot" }, "1H_Ranged_Shoot"),
            // ---- T-058 第一批：跳跃组 5 条（用户已批准提取；施工底稿见 docs/artifacts/T-058/gap-spec.md §7）----
            // ⚠️ 关键词**一律用裸全名**：侦察部核实 Unity 侧的剪辑名**不带** `Rig|` 前缀
            //    （`Rig|` 只是 Blender 的 action 命名，见 gap-spec §3 R1）。
            //    照它初版（带前缀）写会**全部提取失败**。
            // ⚠️ loop 一栏是侦察部的**推断**（按命名/语义），不是实测 —— 所以本批**不据此改行为**，
            //    只把剪辑抽出来 + 建状态；**滞空/落地的实际衔接是后来的功能任务**。
            ("Jump_Start",      false, new[] { "Jump_Start" },      "Jump_Start"),
            ("Jump_Idle",       true,  new[] { "Jump_Idle" },       "Jump_Idle"),      // 实测(T-069 闭合比)：滞空保持 → 循环
            ("Jump_Land",       false, new[] { "Jump_Land" },       "Jump_Land"),
            ("Jump_Full_Short", false, new[] { "Jump_Full_Short" }, "Jump_Full_Short"),
            ("Jump_Full_Long",  false, new[] { "Jump_Full_Long" },  "Jump_Full_Long"),
            // ---- T-058 第二批：13 条（**只做提取，不碰表现层** —— 不加状态、不加参数）----
            // ⚠️ `loop` 一栏的权威来源是 **vfx/T-069 实测闭合比**，不是命名推断（见 gap-spec §7 表）。
            //    标「实测」的可信；标「未实测」的是**推断**，本批**不据此改行为**。
            // ⚠️ 全部用裸全名 → 走"先全名精确匹配"那条路，不会被子串抢先。
            //    `"Block"` 是 `"Blocking"`/`"Block_Hit"` 的子串，**靠的就是精确匹配这一层**兜住；
            //    再加 `expectSource` 断言（错绑会 `LogError`，不会静默）。
            ("Block",          false, new[] { "Block" },          "Block"),            // 实测：闭合比 76.93（单向）
            ("Blocking",       true,  new[] { "Blocking" },       "Blocking"),         // 实测：保持（循环）
            ("Block_Hit",      false, new[] { "Block_Hit" },      "Block_Hit"),        // 未实测
            // 🔴 本条是本批最贵的一处：`-ing` 命名推断为"循环"是**错的**。
            //    实测闭合比 **447.55**（回绕步长是普通帧的 447 倍）= 一条"进入瞄准位"的**过渡**。
            //    若填 true → **每次回绕剧烈跳变**。→ 必须 false。
            ("Ranged_Aiming",  false, new[] { "1H_Ranged_Aiming" },   "1H_Ranged_Aiming"),   // 实测 447.55 → 单向
            ("Ranged_Shooting",true,  new[] { "1H_Ranged_Shooting" }, "1H_Ranged_Shooting"), // 实测：保持（循环）
            ("Ranged_Reload",  false, new[] { "1H_Ranged_Reload" },   "1H_Ranged_Reload"),   // 未实测
            ("Walk_Back",      true,  new[] { "Walking_Backwards" },  "Walking_Backwards"),  // 沿用 Walk 循环
            ("Run_Strafe_L",   true,  new[] { "Running_Strafe_Left" }, "Running_Strafe_Left"),  // 沿用 Run 循环
            ("Run_Strafe_R",   true,  new[] { "Running_Strafe_Right" },"Running_Strafe_Right"), // 沿用 Run 循环
            ("Idle_Unarmed",   true,  new[] { "Unarmed_Idle" },   "Unarmed_Idle"),     // 实测：保持（循环）
            ("Punch_A",        false, new[] { "Unarmed_Melee_Attack_Punch_A" }, "Unarmed_Melee_Attack_Punch_A"),
            ("Punch_B",        false, new[] { "Unarmed_Melee_Attack_Punch_B" }, "Unarmed_Melee_Attack_Punch_B"),
            ("Kick",           false, new[] { "Unarmed_Melee_Attack_Kick" },    "Unarmed_Melee_Attack_Kick"),
        };

        /// <summary>
        /// T-058 第一批：跳跃组的**独立状态清单**（顺序即 AddState 顺序）。
        ///
        /// ⚠️ **为什么不放进 `ComboClips`**：`ComboClips` 只表示**剑的连招段位**语义 —---
        /// 它同时被 `BuildAnimator`（建连招状态与 `ComboStep` 转换）和玩家的 `comboStep` 逻辑引用。
        /// 把跳跃塞进去会给它凭空造出多余的"连招段位"，**且不报错**（与 T-050 对弓的处理同理）。
        /// </summary>
        private static readonly (string name, bool loop)[] JumpStates =
        {
            ("Jump_Start",      false),
            ("Jump_Idle",       true),    // 循环：**不给 BackToIdle**（§3 R4：BackToIdle 只用于非循环单次）
            ("Jump_Land",       false),
            ("Jump_Full_Short", false),
            ("Jump_Full_Long",  false),
        };

        /// <summary>
        /// 跳跃组的 Animator 触发器（T-058）。**新增参数必须被 Set**，否则是**静默失败**（§3 R6）——
        /// 本批只建"能被播到"的最小通路：`Jump` 触发 → `Jump_Start`；
        /// 其余 4 个状态**暂时只能由 `Animator.Play(name)` 直接寻址**（用于验收抽查）。
        /// **真正的滞空/落地衔接属于后续功能任务，不在本批范围内** —— 所以这里**故意不做**完整跳跃状态机。
        /// </summary>
        private const string JumpTrigger = "Jump";

        /// <summary>
        /// T-079 §⑥（跳跃接法二）：**滞空布尔量**的名字。
        /// 由 `PlayerController8Dir` **每帧**喂 `IsAirborne`（`:83`，`!cc.isGrounded`）。
        ///
        /// ⚠️ 它表达的是"**人是否离地**"，与 `Jump`(Trigger) 表达"按了跳"是**两件事**：
        /// Trigger 负责**进**起跳，Bool 负责**走完**滞空与落地。
        /// </summary>
        private const string AirborneParam = "Airborne";

        /// <summary>
        /// T-079 §⑦ 片 2（格挡组）：**格挡保持态**的布尔量名字。
        /// 由 `PlayerMage.Update` **每帧**喂 `PlayerCombat.IsBlocking`
        /// （`PlayerCombat.cs:120-121`：`bool shieldUp = off != null && off.kind == WeaponKind.Shield && input.OffHandHeld; IsBlocking = shieldUp;`）。
        ///
        /// ⚠️ 它表达的是"**盾举着**"，**不表示"这次挡住了"**（`PlayerCombat.cs:397` 的注释同义）。
        /// "这次真挡住"的判定是 `PlayerHealth.cs:144` 的 **80° 角检**（减伤在 `:148`）。
        /// → 所以**不能**拿它去播 `Block_Hit`：那会变成"只要举着盾就播"，**侧后方挨打也会播**。
        ///
        /// ⚠️ **必须与运行时侧逐字一致**：`PlayerMage.cs` 的 `IsBlockingHash` 用的就是这个字符串。
        /// 两侧各写一份（Editor 程序集 ↔ 运行时程序集不能互相引用）；
        /// **名字不匹配不会报错，只会让格挡动作静默不动**（陷阱 20 / 21）。
        /// </summary>
        private const string IsBlockingParam = "IsBlocking";

        /// <summary>
        /// T-079 §⑦ 片 2：格挡组的**独立状态清单**（顺序即 `AddState` 顺序）。
        ///
        /// ⚠️ **不放进 `ComboClips`** —— 理由与 `JumpStates` 完全相同：那会给剑**凭空造出连招段位**，
        /// 而且**不报错**。
        ///
        /// ⚠️ **这里刻意不带 `loop` 一栏**（与 `JumpStates` 的写法不同）：三条状态的出边**各不相同** ——
        /// `Blocking` 是循环（**不给 `BackToIdle`**，只给"`IsBlocking` 由真变假 → Idle"的条件边）；
        /// `Block` / `Block_Hit` 是单次，但**`Block_Hit` 绝不能拿 `BackToIdle`** ——
        /// 那会让"举着盾挨完一下"直接回 `Idle`，而不是回**保持态**（表现为"挡了一下就放下盾"）。
        /// → 出边**逐条显式写**在 `BuildAnimator` 里，**不让一个 `loop` 布尔去代劳**。
        /// </summary>
        private static readonly string[] BlockStates = { "Block", "Blocking", "Block_Hit" };

        /// <summary>连招用的四个剪辑，顺序就是出招顺序。**只表示剑的连招段位**。</summary>
        private static readonly string[] ComboClips = { "Attack_1", "Attack_2", "Attack_3", "Attack_4" };

        /// <summary>每段攻击的命中帧上要打的动画事件名。AnimEventRelay 上有同名方法。</summary>
        private const string SlashImpactEvent = "OnSlashImpact";

        /// <summary>弓的放箭剪辑（资产名）。T-050。</summary>
        private const string BowShootClip = "Ranged_Shoot";

        /// <summary>放箭那一刻要在剪辑上打的事件名。AnimEventRelay 上有同名方法。</summary>
        private const string ArrowReleaseEvent = "OnArrowRelease";

        /// <summary>
        /// 弓自己的 Animator Trigger。**绝不复用 `Slash` / `ComboStep`**：
        /// `PlayerMage.PlayAttack()` 会 `SetInteger(ComboStep, n)` + `SetTrigger(Slash)`，
        /// 拿它来播射箭会造成两个**静默** bug —— ①射箭播的是横劈；②Trigger 残留、之后又触发一次剑招。
        /// </summary>
        private const string BowShotTrigger = "BowShot";

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
        /// <summary>
        /// 弓（远程）自己的裁剪参数。**故意与剑的 `Combo*` 常量分开**（T-050，监察部口径）：
        /// 两者当前数值相同（0.20 / 0.62 / 0.18），但语义不同 —— 剑的那组是"连招四段的手感"，
        /// 弓这组是"抬起→保持→放箭的节奏"。**若共用一组，以后调剑的连招手感会连带改到弓的放箭时机**，
        /// 而且这种连带**不会报错**。数值归用户，所以更不能让两个手感绑死在一个常量上。
        /// </summary>
        private const float RangedLeadIn = 0.20f;
        private const float RangedClipLength = 0.62f;
        private const float RangedTrimTailMin = 0.18f;

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

            foreach (var (name, loop, keys, expectSource) in Wanted)
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
                    Debug.LogError($"[My World] 没找到动画 '{name}'（关键词 {string.Join("/", keys)}）");
                    continue;
                }

                // ✅ T-050 白名单断言：找到的名字必须**正好**是期望的那条。
                // 只报错、**不跳过** —— 断言是为了让人看见，不是为了把安装搞坏。
                // 这条专治"日志看起来成功、其实绑到了错的剪辑"（如绑到 1H_Ranged_Shooting）。
                string verdict = string.Equals(found.name, expectSource, System.StringComparison.Ordinal)
                    ? "OK"
                    : "MISMATCH";
                if (verdict == "MISMATCH")
                    Debug.LogError($"[My World] ❌ 剪辑 '{name}' 源名不匹配：期望 '{expectSource}'，实际拿到 '{found.name}'。"
                                   + "（可能被同名子串抢先匹配，请检查 Wanted 的关键词顺序）");

                string path = $"{ClipDir}/{name}.anim";
                AssetDatabase.DeleteAsset(path);

                var copy = Object.Instantiate(found);
                copy.name = name;
                var settings = AnimationUtility.GetAnimationClipSettings(copy);
                settings.loopTime = loop;
                AnimationUtility.SetAnimationClipSettings(copy, settings);

                AssetDatabase.CreateAsset(copy, path);
                result[name] = AssetDatabase.LoadAssetAtPath<AnimationClip>(path);
                Debug.Log($"[My World] 剪辑 {name} ← {found.name}（{(loop ? "循环" : "单次")}，"
                          + $"{found.length:F2}s，expectSource={verdict}）");
            }

            return result;
        }

        /// <summary>
        /// 后处理清单的一项：裁哪个剪辑、打什么事件、事件钉在哪。
        ///
        /// 为什么单开一个清单、**不把弓塞进 `ComboClips`**（T-050 设计判断）：
        /// `ComboClips` 现在身兼两义 —— ①`BuildAnimator` 用它建**连招状态与 AnyState 转换**，
        /// ②`PostProcessClips` 用它当裁剪清单。把弓加进去会给它凭空造出"第 5 段连招"的状态与
        /// `ComboStep==4` 转换，而 `PlayerMage.ComboLength = 4` 与 `Mathf.Clamp(comboStep, 0, 3)`
        /// 都是写死的 → 弓会污染剑的连招段位语义（且不报错）。
        /// 所以：`ComboClips` **只表示剑的连招段位**；"要裁要打事件的剪辑"由本清单表示，两者解耦。
        /// </summary>
        private struct ImpactSpec
        {
            public string clip;
            public string eventName;
            /// <summary>false = 钉在**峰值帧**（挥砍：动作最快那一刻就是命中点）；
            /// true = 钉在**末尾收势前**（放箭：峰值在"抬弓"段，命中点却在"举弓保持"段，不能靠峰值找）。</summary>
            public bool eventNearEnd;

            public ImpactSpec(string clip, string eventName, bool eventNearEnd)
            {
                this.clip = clip;
                this.eventName = eventName;
                this.eventNearEnd = eventNearEnd;
            }
        }

        private static readonly ImpactSpec[] ImpactSpecs =
        {
            new ImpactSpec("Attack_1", SlashImpactEvent, false),
            new ImpactSpec("Attack_2", SlashImpactEvent, false),
            new ImpactSpec("Attack_3", SlashImpactEvent, false),
            new ImpactSpec("Attack_4", SlashImpactEvent, false),
            // ---- T-050 弓：放箭帧 ----
            // 实测（Unity 侧逐帧手臂位移，见 tmp/cs_t050_measure.cs 的输出）：
            //   `1H_Ranged_Shoot` 32 帧：峰值在 **f5（0.167s，抬弓段）**，
            //   最静止的一段是 **f11..f23（0.367..0.767s，举弓保持段）**，之后 f25+ 是放下段。
            //   以峰值锚定的裁剪窗口 = **f0..f18** → 裁完 0.633s。
            // 所以**不能用峰值当放箭点**（那是抬弓最快的一帧，弓还没举稳）；
            // 也不能照抄 vfx 测出的 f23 = 0.767s —— 那个秒数在**未裁剪**的剪辑上成立，
            // 裁完之后 f18 就是末帧，0.767s 已经出界。
            // 采用"末尾留出收势"（复用 ComboTrimTailMin = 0.18s）→ 事件落在裁后 0.453s，
            // 换算回原剪辑 ≈ f14，**落在举弓保持段 f11..f23 内**，弓仍举着 → 视觉说得通。
            new ImpactSpec(BowShootClip, ArrowReleaseEvent, true),
        };

        /// <summary>
        /// 抽完、存盘、刷新**之后**再回头改剪辑内容（裁帧 + 打命中事件）。
        ///
        /// 为什么必须单独一遍：`Install()` 结尾会 `AssetDatabase.Refresh()`，而 Refresh 会从磁盘
        /// 重新导入 .anim，把"已经改过但还没落盘"的内存版本冲掉 —— 实测第一次跑时裁剪明明执行了
        /// （日志里有），读回来却还是 1.000s 且没有事件。放到存盘之后再改、再存一次就稳了。
        /// </summary>
        private static void PostProcessClips()
        {
            foreach (var spec in ImpactSpecs)
            {
                var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>($"{ClipDir}/{spec.clip}.anim");
                if (clip == null)
                {
                    Debug.LogError($"[My World] 后处理找不到剪辑 {spec.clip}");
                    continue;
                }

                // 顺序不能反：事件时间是相对剪辑自身的，裁完再测峰值才对。
                // 弓用自己那组常量（Ranged*），剑用 Combo* —— 手感的耦合在源码层面就断开了。
                bool ranged = spec.clip == BowShootClip;
                var range = ranged
                    ? ComboTrimRange(clip, RangedLeadIn, RangedClipLength, RangedTrimTailMin)
                    : ComboTrimRange(clip, ComboLeadIn, ComboClipLength, ComboTrimTailMin);
                TrimClip(clip, range.from, range.to);
                AddImpactEvent(clip, spec.eventName, spec.eventNearEnd);

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
        /// 以峰值帧为锚点，取一个固定长度的窗口：事件帧落在开头 <paramref name="leadIn"/> 秒处，
        /// 总长 <paramref name="clipLength"/> 秒，命中之后至少留 <paramref name="tailMin"/> 秒收势。
        ///
        /// 越界时优先挪窗口而不是缩窗口 —— 缩了节奏就不齐了。
        /// （T-050：改为**显式传参**，让剑与弓各用自己那组常量，避免两边手感静默耦合。）
        /// </summary>
        private static (int from, int to) ComboTrimRange(
            AnimationClip clip, float leadIn, float clipLength, float tailMin)
        {
            int fps, frames;
            var motion = MotionProfile(clip, out fps, out frames);
            int peak = PeakFrame(motion, frames);

            int span = Mathf.Max(4, Mathf.RoundToInt(clipLength * fps));
            int lead = Mathf.RoundToInt(leadIn * fps);
            int tail = Mathf.RoundToInt(tailMin * fps);
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
        /// 在剪辑上打命中帧事件。
        ///
        /// **两种钉法**（T-050 拆开）：
        ///  * `nearEnd = false`（挥砍）—— 钉在**手臂链逐帧位移的峰值帧**，即挥得最快的那一帧。
        ///    裁剪之后重新测，所以时间始终是相对裁好的剪辑；四段实测都落在 0.200s。
        ///  * `nearEnd = true`（放箭）—— 钉在**末尾收势前** `clip.length - tailMin`。
        ///    **为什么放箭不能也用峰值**（实测，见 tmp/cs_t050_measure.cs）：
        ///    `1H_Ranged_Shoot` 的峰值在 f5（抬弓段），而"举弓保持段"是 f11..f23；
        ///    且峰值锚定的窗口因越界被夹到 f0 起，**峰值落在裁后 0.167s —— 仍在抬弓**。
        ///    照峰值挂事件 = 弓还没举稳箭就飞了，正是要修的那个不同步。
        ///    末尾留出收势 → 0.453s，换算回原剪辑 ≈ f14，落在保持段内。
        ///
        /// 注意峰值只是启发式：角速度峰值通常略早于真正的接触帧，最终该按手感微调。
        /// </summary>
        private static void AddImpactEvent(AnimationClip clip, string eventName, bool nearEnd)
        {
            if (clip == null) return;

            int fps, frames;
            var motion = MotionProfile(clip, out fps, out frames);

            int peak = 1;
            for (int i = 1; i < frames; i++)
                if (motion[i] > motion[peak]) peak = i;

            float t;
            if (nearEnd)
            {
                // 复用"留够收势"的同一语义，但用**远程自己的常量**，避免与剑的手感耦合（见 RangedTrimTailMin）。
                t = Mathf.Clamp(clip.length - RangedTrimTailMin, 0.05f, Mathf.Max(0.06f, clip.length - 0.02f));
            }
            else
            {
                t = peak / (float)fps;
            }

            var ev = new AnimationEvent
            {
                functionName = eventName,
                time = t,
                messageOptions = SendMessageOptions.DontRequireReceiver,
            };
            AnimationUtility.SetAnimationEvents(clip, new[] { ev });
            EditorUtility.SetDirty(clip);
            Debug.Log($"[My World] 动画事件 {eventName} @ {t:F3}s" +
                      $"（{(nearEnd ? "末尾收势前" : "角速度峰值帧")}，第 {peak} 帧 / 共 {frames} 帧，"
                      + $"剪辑长 {clip.length:F3}s）");
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

            // ---- T-050 弓：自己的 Trigger + 状态 ----
            // **为什么不复用 Slash/ComboStep**：复用会造成两个**静默** bug ——
            //   ① `PlayerMage.PlayAttack(n)` 会 SetInteger(ComboStep,n)+SetTrigger(Slash)
            //      → 射箭播的是横劈，而且**动到了剑的连招段位**；
            //   ② Trigger 若当帧没被消费会残留，之后又触发一次剑招（表现为"莫名挥了一刀"）。
            // 这里用独立的 `BowShot` Trigger，与剑的连招完全无关。
            ctrl.AddParameter(BowShotTrigger, AnimatorControllerParameterType.Trigger);

            clips.TryGetValue(BowShootClip, out var cBow);
            if (cBow == null)
            {
                Debug.LogError($"[My World] controller 里没有 {BowShootClip} 剪辑，弓的射箭状态被跳过。");
            }
            else
            {
                var bowState = AddState(sm, "BowShot", cBow);
                var bt = sm.AddAnyStateTransition(bowState);
                bt.hasExitTime = false;
                bt.duration = 0.07f;
                // 允许打断自己：连射时后一箭应该重新起手，而不是等前一箭播完
                bt.canTransitionToSelf = true;
                bt.AddCondition(AnimatorConditionMode.If, 0f, BowShotTrigger);
                bt.AddCondition(AnimatorConditionMode.IfNot, 0f, "Dead");
                // ⚠️ 必须自己接回 Idle：否则会**卡在放箭姿势里**再也不回待机（且不报错）
                BackToIdle(bowState, idle);
            }

            // ---- T-058 第一批：跳跃组 5 个状态 ----
            // 目的：**把剪辑接入控制器、可被寻址、可被播到**。
            // ⛔ **本批不做完整跳跃状态机**（滞空↔落地的衔接是**后续功能任务**，
            //    而 `loop` 一栏还只是侦察部的推断，未实测首尾闭合）—— 所以这里只建最小通路：
            //    * `Jump` 触发 → `Jump_Start`（AnyState，`Dead` 守卫）→ 于是"新剪辑真的能被播到"可被验证
            //    * 其余 4 个状态可经 `Animator.Play(name)` 直接寻址（验收抽查用）
            // ⚠️ `BackToIdle` 只给**非循环单次**剪辑（§3 R4）；`Jump_Idle` 是循环，**不给**。
            ctrl.AddParameter(JumpTrigger, AnimatorControllerParameterType.Trigger);
            // T-079 §⑥ 片 1（接法二）：滞空布尔量，由 `PlayerController8Dir` **每帧**喂
            ctrl.AddParameter(AirborneParam, AnimatorControllerParameterType.Bool);

            AnimatorState jumpStartState = null, jumpIdleState = null, jumpLandState = null;
            foreach (var js in JumpStates)
            {
                clips.TryGetValue(js.name, out var jumpClip);
                if (jumpClip == null)
                {
                    Debug.LogError($"[My World] controller 里没有 {js.name} 剪辑，该跳跃状态被跳过。");
                    continue;
                }

                var st = AddState(sm, js.name, jumpClip);
                if (!js.loop) BackToIdle(st, idle);      // 非循环才回 Idle
                if (js.name == "Jump_Start") jumpStartState = st;
                else if (js.name == "Jump_Idle") jumpIdleState = st;
                else if (js.name == "Jump_Land") jumpLandState = st;
            }

            if (jumpStartState != null)
            {
                var jt = sm.AddAnyStateTransition(jumpStartState);
                jt.hasExitTime = false;
                jt.duration = 0.08f;
                jt.canTransitionToSelf = false;   // 起跳不重复打断自己
                jt.AddCondition(AnimatorConditionMode.If, 0f, JumpTrigger);
                jt.AddCondition(AnimatorConditionMode.IfNot, 0f, "Dead");
            }

            // ================= T-079 §⑥ 片 1：**完整跳跃链（接法二）** =================
            //   Jump_Start --(Airborne==true)--> Jump_Idle --(Airborne==false)--> Jump_Land --(既有 BackToIdle)--> Idle
            //
            // ⚠️ **`Jump_Idle` 是循环态，所以给它的是"通向 `Jump_Land` 的条件转移"，不是 `BackToIdle`** ——
            //    §3 R4 禁的是"给循环态挂 `BackToIdle`"，不是禁"给它一条正经出边"。
            // ⚠️ **落地回 Idle 必须经 `Jump_Land`**：`Jump_Idle` 的**唯一**出边就是下面这条，
            //    所以"滞空结束"只能由 `Airborne` 由真变假来触发。
            // ⚠️ **已知可见行为（本批按最小改动不动，待用户拍板）**：
            //    `Slash`/`Hit`/`Attack` 的 AnyState 转移条件里**没有"是否在空中"** →
            //    **空中挥剑会打断跳跃动作**（直接切进攻击状态）。这是**玩法设计**问题，不是 bug。
            if (jumpStartState != null && jumpIdleState != null)
            {
                var tUp = jumpStartState.AddTransition(jumpIdleState);
                tUp.hasExitTime = false;      // 不等起跳动作播完：离地就走
                tUp.duration = 0.10f;
                tUp.AddCondition(AnimatorConditionMode.If, 0f, AirborneParam);
            }
            if (jumpIdleState != null && jumpLandState != null)
            {
                var tDown = jumpIdleState.AddTransition(jumpLandState);
                tDown.hasExitTime = false;
                tDown.duration = 0.10f;
                tDown.AddCondition(AnimatorConditionMode.IfNot, 0f, AirborneParam);
            }
            // `Jump_Land → Idle` 已在上面由 `BackToIdle(st, idle)` 建好（它是**非循环**态），此处**不重复建**。

            // ================= T-079 §⑦ 片 2：**格挡组** =================
            //   状态：`Block`(单次起手) / `Blocking`(循环保持) / `Block_Hit`(单次受击)
            //   参数：只有 `IsBlocking`(Bool)，由 `PlayerMage.Update` 每帧喂 `PlayerCombat.IsBlocking`
            //        （`PlayerCombat.cs:120-121` 在 `Update` 里逐帧写 `IsBlocking = shieldUp`）。
            //
            // ⚠️ **为什么入口边写成"从 Idle/Walk/Run 出发"，而不是 `AnyState` + `IsBlocking`**：
            //    `IsBlocking` 是**电平**（举着盾就一直为真），**不是边沿**。
            //    若写成 AnyState→Block（或 →Blocking），则在 `Blocking` 里**每帧条件都成立** →
            //    会被立刻拽回 `Block` → **`Block`↔`Blocking` 抖动** —— 而 **G1 明文把抖动判红**。
            //    改成"从常态出发"后：`Block`→`Blocking` 只在起手播到 exit time 时走一次，
            //    且 `Blocking` / `Block_Hit` 里**没有任何转移会把它们拽走** → 不抖动。
            //    （代价：从 `Cast`/`Hit`/`Attack*`/`BowShot`/`Jump_*` 里按举盾不会**立刻**进 Block，
            //      要等那些状态自己回 `Idle` 再进 —— 这是**刻意**的，见"表现跟随事实"那条纪律。）
            //
            // ⚠️ **`Blocking` 是循环态 → 不给 `BackToIdle`**（§3 R4：`BackToIdle` 只给非循环单次）；
            //    它的出边是**条件边**（`IsBlocking` 由真变假 → `Idle`），这条正是"收盾退出"。
            //
            // ⚠️ **`Block_Hit` 的进入边不在控制器里**，由代码 `Animator.Play("Block_Hit")`
            //    （`PlayerMage.PlayBlockHit`）直接寻址；调用点在 `PlayerHealth.TakeDamage` 的
            //    **80° 角检内部、与 `amount *= mult` 同层**（真减伤那一刻），**不是**"举着盾"那层。
            //    出边仍在控制器里（两条 exit time）→ **不会卡在 `Block_Hit` 里**。

            ctrl.AddParameter(IsBlockingParam, AnimatorControllerParameterType.Bool);

            AnimatorState blockState = null, blockingState = null, blockHitState = null;
            foreach (var bs in BlockStates)
            {
                clips.TryGetValue(bs, out var blockClip);
                if (blockClip == null)
                {
                    Debug.LogError($"[My World] controller 里没有 {bs} 剪辑，该格挡状态被跳过。");
                    continue;
                }

                var st = AddState(sm, bs, blockClip);
                if (bs == "Block") blockState = st;
                else if (bs == "Blocking") blockingState = st;
                else if (bs == "Block_Hit") blockHitState = st;
            }

            if (blockState != null && blockingState != null)
            {
                // 起手（单次）→ 保持（循环）：等起手播到 85% 再切，免得动作被截断
                var tHold = blockState.AddTransition(blockingState);
                tHold.hasExitTime = true;
                tHold.exitTime = 0.85f;
                tHold.duration = 0.10f;
                tHold.AddCondition(AnimatorConditionMode.If, 0f, IsBlockingParam);

                // 举盾途中松手 → 直接回 Idle（否则要等起手播完、再经 Blocking 绕一圈才回）
                var tAbort = blockState.AddTransition(idle);
                tAbort.hasExitTime = false;
                tAbort.duration = 0.12f;
                tAbort.AddCondition(AnimatorConditionMode.IfNot, 0f, IsBlockingParam);

                // 入口：三个常态 → Block（条件边；只在"还没举盾"的常态下成立）
                AddBlockEntrance(idle, blockState);
                AddBlockEntrance(walk, blockState);
                AddBlockEntrance(run, blockState);
            }

            if (blockingState != null)
            {
                // 收盾 → Idle：**这是离开 `Blocking` 的唯一通路**（G1 的"收盾后不得停在 Blocking"）
                var tLower = blockingState.AddTransition(idle);
                tLower.hasExitTime = false;
                tLower.duration = 0.12f;
                tLower.AddCondition(AnimatorConditionMode.IfNot, 0f, IsBlockingParam);
            }

            if (blockHitState != null)
            {
                // 两条出边**都带 exit time** → 无论此刻是否还举着盾，`Block_Hit` 播到 90% 必定离开它（不卡死）。
                // ⚠️ `Block_Hit` **刻意不接 `BackToIdle`**：举着盾挨完一下应当回**保持态**，而不是放下盾回 Idle。
                if (blockingState != null)
                {
                    var tBack = blockHitState.AddTransition(blockingState);
                    tBack.hasExitTime = true;
                    tBack.exitTime = 0.90f;
                    tBack.duration = 0.10f;
                    tBack.AddCondition(AnimatorConditionMode.If, 0f, IsBlockingParam);
                }

                var tOut = blockHitState.AddTransition(idle);
                tOut.hasExitTime = true;
                tOut.exitTime = 0.90f;
                tOut.duration = 0.12f;
                tOut.AddCondition(AnimatorConditionMode.IfNot, 0f, IsBlockingParam);
            }

            return ctrl;
        }

        /// <summary>
        /// T-079 §⑦ 片 2：格挡入口边（`Idle`/`Walk`/`Run` → `Block`）。
        /// **只有这三个常态**是入口 —— 见 `BuildAnimator` 里"为什么不用 AnyState"的那段说明。
        /// </summary>
        private static void AddBlockEntrance(AnimatorState from, AnimatorState block)
        {
            var t = from.AddTransition(block);
            t.hasExitTime = false;
            t.duration = 0.10f;
            t.AddCondition(AnimatorConditionMode.If, 0f, IsBlockingParam);
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
