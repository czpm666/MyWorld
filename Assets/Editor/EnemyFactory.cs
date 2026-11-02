using System.Collections.Generic;
using System.IO;
using MyWorld;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MyWorldEnemies.EditorTools
{
    /// <summary>
    /// 敌人生产线：从 KayKit Adventurers 的 FBX 动画库里挑片段，
    /// 生成 Idle / Walk / Attack / Hit / Death 五状态 AnimatorController，
    /// 再拼出满足 <see cref="Enemy"/> 要求的 prefab（Animator + CharacterController + Enemy）。
    ///
    /// 全部产物落在 Assets/Generated/ 下，可反复执行（幂等：先删后建）。
    /// 不改动任何既有脚本 / 第三方 prefab。
    /// </summary>
    public static class EnemyFactory
    {
        // ---------- 路径 ----------
        private const string AnimRoot = "Assets/Generated/CharacterAnimations";
        private const string ClipDir = AnimRoot + "/Clips";
        private const string CtrlDir = AnimRoot + "/Controllers";
        private const string EnemyRoot = "Assets/Generated/Enemies";
        private const string PrefabDir = EnemyRoot + "/Prefabs";
        private const string MatDir = EnemyRoot + "/Materials";
        private const string QcDir = "WorkQC";

        private const string BarbarianPrefab = "Assets/ThirdParty/KayKit_Adventurers/Enemies/EnemyBarbarian.prefab";
        private const string BarbarianFbx = "Assets/ThirdParty/KayKit_Adventurers/Enemies/Barbarian.fbx";
        private const string MagePrefab = "Assets/ThirdParty/KayKit_Adventurers/MageCharacter.prefab";
        private const string MageFbx = "Assets/ThirdParty/KayKit_Adventurers/Mage.fbx";
        private const string MageMat = "Assets/ThirdParty/KayKit_Adventurers/M_Mage.mat";

        /// <summary>一个敌人的配方。</summary>
        private sealed class EnemySpec
        {
            public string Id;              // 资源名 / prefab 名
            public string DisplayName;     // 中文名
            public string BasePrefab;      // 带正确 URP 材质的第三方 prefab（只读引用）
            public string ClipFbx;         // 动画片段来源 FBX
            public string IdleClip, WalkClip, RunClip, AttackClip, HitClip, DeathClip;
            public float Scale = 0.68f;    // 统一到和玩家同样的身高
            public float WorldHeight = 1.9f; // CharacterController 世界高度
            public float Hp = 70f, WalkSpeed = 3f, RunSpeed = 5f, Damage = 10f, Range = 2.4f;
            public bool Tint;
            public Color TintColor = Color.white;
            public string TintSourceMat;
            public string TintMatPrefix;
        }

        private static EnemySpec[] GetSpecs()
        {
            return new[]
            {
                new EnemySpec
                {
                    Id = "E_Barbarian",
                    DisplayName = "蛮兵（近战）",
                    BasePrefab = BarbarianPrefab,
                    ClipFbx = BarbarianFbx,
                    IdleClip = "Idle",
                    WalkClip = "Walking_A",
                    RunClip = "Running_A",
                    AttackClip = "1H_Melee_Attack_Chop",
                    HitClip = "Hit_A",
                    DeathClip = "Death_A",
                    Scale = 0.68f,
                    Hp = 90f,
                    WalkSpeed = 2.7f,
                    RunSpeed = 4.6f,
                    Damage = 9f,
                    Range = 2.4f,
                },
                new EnemySpec
                {
                    Id = "E_FallenMage",
                    DisplayName = "堕落法师（远程外形）",
                    BasePrefab = MagePrefab,
                    ClipFbx = MageFbx,
                    IdleClip = "Idle",
                    WalkClip = "Walking_A",
                    RunClip = "Running_A",
                    AttackClip = "Spellcast_Raise",
                    HitClip = "Hit_A",
                    DeathClip = "Death_A",
                    Scale = 0.68f,
                    Hp = 55f,
                    WalkSpeed = 2.3f,
                    RunSpeed = 3.8f,
                    Damage = 7f,
                    Range = 2.6f,
                    Tint = true,
                    TintColor = new Color(0.46f, 0.34f, 0.66f, 1f),
                    TintSourceMat = MageMat,
                    TintMatPrefix = "M_Mage",
                },
            };
        }

        // =====================================================================
        //  菜单 ① 重建
        // =====================================================================

        [MenuItem("Tools/My World/敌人/① 重建动画控制器与敌人 Prefab", false, 1)]
        public static void RebuildAll()
        {
            EnsureFolders();

            var report = new System.Text.StringBuilder();
            report.AppendLine("[EnemyFactory] 开始重建");
            var done = new List<string>();

            foreach (var spec in GetSpecs())
            {
                var clips = BuildClips(spec, report);
                var ctrl = BuildController(spec, clips, report);
                var prefabPath = BuildPrefab(spec, ctrl, report);
                done.Add(spec.Id + " -> " + prefabPath);
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            report.AppendLine("完成：");
            foreach (var d in done) report.AppendLine("  " + d);
            Debug.Log(report.ToString());
        }

        // =====================================================================
        //  菜单 ② 导出数据（骨骼 / 动画 / 状态机）
        // =====================================================================

        [MenuItem("Tools/My World/敌人/② 导出敌人数据到 WorkQC", false, 2)]
        public static void ExportData()
        {
            var sb = new System.Text.StringBuilder();
            sb.AppendLine("# 敌人数据（由 EnemyFactory 自动导出）");
            sb.AppendLine();
            sb.AppendLine("## 骨骼对照（第三人称 KayKit Adventurers 骨架）");
            sb.AppendLine();
            sb.AppendLine("| 来源 | Transform 数量 | 关键骨骼 |");
            sb.AppendLine("|---|---|---|");
            foreach (var fbx in new[] { BarbarianFbx, MageFbx })
            {
                var go = AssetDatabase.LoadAssetAtPath<GameObject>(fbx);
                if (go == null) { sb.AppendLine("| " + fbx + " | MISSING | |"); continue; }
                var names = new List<string>();
                foreach (var t in go.GetComponentsInChildren<Transform>(true)) names.Add(t.name);
                bool ok = names.Contains("Rig") && names.Contains("hips") && names.Contains("chest")
                          && names.Contains("upperarm.l") && names.Contains("hand.r");
                sb.AppendLine("| " + Path.GetFileName(fbx) + " | " + names.Count + " | "
                    + (ok ? "Rig/root/hips/spine/chest/upperarm.l... 齐全" : "缺失！") + " |");
            }
            sb.AppendLine();

            // 新动画包（不同骨架）作为反面对照记一笔
            sb.AppendLine("### 对照：kaykit-character-animations v1.2 的骨架（**不同**，不可重定向）");
            sb.AppendLine();
            sb.AppendLine("```");
            sb.AppendLine("KayKit Animated Character");
            sb.AppendLine("  Body");
            sb.AppendLine("    armLeft / handSlotLeft");
            sb.AppendLine("    armRight / handSlotRight");
            sb.AppendLine("    Head");
            sb.AppendLine("```");
            sb.AppendLine();

            sb.AppendLine("## 每个敌人的动画片段");
            sb.AppendLine();
            sb.AppendLine("| 敌人 | 状态 | 源 Clip | 时长(s) | 帧数 | 循环 | 曲线数 |");
            sb.AppendLine("|---|---|---|---|---|---|---|");
            foreach (var spec in GetSpecs())
            {
                var map = new[]
                {
                    new KeyValuePair<string, string>("Idle", spec.IdleClip),
                    new KeyValuePair<string, string>("Walk", spec.WalkClip),
                    new KeyValuePair<string, string>("Attack", spec.AttackClip),
                    new KeyValuePair<string, string>("Hit", spec.HitClip),
                    new KeyValuePair<string, string>("Death", spec.DeathClip),
                };
                foreach (var kv in map)
                {
                    var clip = FindClip(spec.ClipFbx, kv.Value);
                    if (clip == null) { sb.AppendLine("| " + spec.Id + " | " + kv.Key + " | 缺失 " + kv.Value + " | | | | |"); continue; }
                    int frames = Mathf.RoundToInt(clip.length * clip.frameRate);
                    int curves = AnimationUtility.GetCurveBindings(clip).Length;
                    sb.AppendLine("| " + spec.Id + " | " + kv.Key + " | " + clip.name + " | "
                        + clip.length.ToString("F3") + " | " + frames + " | "
                        + (kv.Key == "Idle" || kv.Key == "Walk" ? "是" : "否") + " | " + curves + " |");
                }
            }
            sb.AppendLine();

            sb.AppendLine("## AnimatorController");
            sb.AppendLine();
            foreach (var spec in GetSpecs())
            {
                var ctrlPath = CtrlDir + "/AC_" + spec.Id + ".controller";
                var ctrl = AssetDatabase.LoadAssetAtPath<AnimatorController>(ctrlPath);
                if (ctrl == null) { sb.AppendLine("- " + ctrlPath + " : 尚未生成"); continue; }
                sb.AppendLine("### " + spec.DisplayName + "（" + spec.Id + "）");
                sb.AppendLine();
                sb.AppendLine("- 参数：" + DescribeParams(ctrl));
                foreach (var layer in ctrl.layers)
                {
                    var sm = layer.stateMachine;
                    sb.AppendLine("- 关卡 " + layer.name + "，默认状态：" + (sm.defaultState == null ? "?" : sm.defaultState.name));
                    foreach (var st in sm.states)
                    {
                        var clip = st.state.motion as AnimationClip;
                        sb.AppendLine("  - 状态 " + st.state.name + "  clip=" + (clip == null ? "(无)" : clip.name)
                            + "  时长=" + (clip == null ? "?" : clip.length.ToString("F3")));
                        foreach (var tr in st.state.transitions)
                            sb.AppendLine("    → " + (tr.destinationState == null ? "?" : tr.destinationState.name) + "  " + DescribeTransition(tr));
                    }
                    foreach (var any in sm.anyStateTransitions)
                        sb.AppendLine("  - AnyState → " + (any.destinationState == null ? "?" : any.destinationState.name) + "  " + DescribeTransition(any));
                }
                sb.AppendLine();
            }

            Directory.CreateDirectory(Path.Combine(Directory.GetCurrentDirectory(), QcDir));
            var path = Path.Combine(QcDir, "enemy_data.md");
            File.WriteAllText(path, sb.ToString());
            Debug.Log("[EnemyFactory] 数据已导出到 " + Path.GetFullPath(path));
        }

        private static string DescribeParams(AnimatorController ctrl)
        {
            var parts = new List<string>();
            foreach (var p in ctrl.parameters)
                parts.Add(p.name + "(" + p.type + ")");
            return string.Join("，", parts);
        }

        private static string DescribeTransition(AnimatorStateTransition tr)
        {
            var conds = new List<string>();
            foreach (var c in tr.conditions)
                conds.Add(c.parameter + " " + c.mode + " " + c.threshold.ToString("F2"));
            return (tr.hasExitTime ? "exitTime=" + tr.exitTime.ToString("F2") + " " : "")
                 + "duration=" + tr.duration.ToString("F2")
                 + (conds.Count > 0 ? " [" + string.Join(" && ", conds) + "]" : "");
        }

        // =====================================================================
        //  Clip
        // =====================================================================

        private static Dictionary<string, AnimationClip> BuildClips(EnemySpec spec, System.Text.StringBuilder report)
        {
            var result = new Dictionary<string, AnimationClip>();
            var defs = new[]
            {
                new KeyValuePair<string, string>("Idle", spec.IdleClip),
                new KeyValuePair<string, string>("Walk", spec.WalkClip),
                new KeyValuePair<string, string>("Run", spec.RunClip),
                new KeyValuePair<string, string>("Attack", spec.AttackClip),
                new KeyValuePair<string, string>("Hit", spec.HitClip),
                new KeyValuePair<string, string>("Death", spec.DeathClip),
            };

            foreach (var kv in defs)
            {
                var state = kv.Key;
                var srcName = kv.Value;
                var src = FindClip(spec.ClipFbx, srcName);
                if (src == null)
                {
                    report.AppendLine("  ! " + spec.Id + " 找不到 clip " + srcName + " @ " + spec.ClipFbx);
                    continue;
                }

                var path = ClipDir + "/CL_" + spec.Id + "_" + state + ".anim";
                AssetDatabase.DeleteAsset(path);

                var clone = Object.Instantiate(src);
                clone.name = "CL_" + spec.Id + "_" + state;
                bool loop = state == "Idle" || state == "Walk" || state == "Run";
                clone.wrapMode = loop ? WrapMode.Loop : WrapMode.ClampForever;
                var settings = AnimationUtility.GetAnimationClipSettings(clone);
                settings.loopTime = loop;
                settings.loopBlend = loop;
                AnimationUtility.SetAnimationClipSettings(clone, settings);

                AssetDatabase.CreateAsset(clone, path);
                result[state] = AssetDatabase.LoadAssetAtPath<AnimationClip>(path);

                report.AppendLine("  clip " + spec.Id + "/" + state + " <- " + srcName
                    + " len=" + src.length.ToString("F3") + " frames=" + Mathf.RoundToInt(src.length * src.frameRate)
                    + " loop=" + loop);
            }

            return result;
        }

        private static AnimationClip FindClip(string fbxPath, string clipName)
        {
            var objects = AssetDatabase.LoadAllAssetsAtPath(fbxPath);
            foreach (var o in objects)
            {
                var c = o as AnimationClip;
                if (c == null) continue;
                if (c.name.StartsWith("__preview__")) continue;
                if (c.name == clipName) return c;
            }
            return null;
        }

        // =====================================================================
        //  AnimatorController
        // =====================================================================

        private static AnimatorController BuildController(
            EnemySpec spec, Dictionary<string, AnimationClip> clips, System.Text.StringBuilder report)
        {
            var path = CtrlDir + "/AC_" + spec.Id + ".controller";
            AssetDatabase.DeleteAsset(path);

            var ctrl = AnimatorController.CreateAnimatorControllerAtPath(path);
            ctrl.AddParameter("Speed", AnimatorControllerParameterType.Float);
            ctrl.AddParameter("Attack", AnimatorControllerParameterType.Trigger);
            ctrl.AddParameter("Hit", AnimatorControllerParameterType.Trigger);
            ctrl.AddParameter("Dead", AnimatorControllerParameterType.Bool);

            var sm = ctrl.layers[0].stateMachine;

            var idle = AddState(sm, "Idle", Clip(clips, "Idle"));
            var walk = AddState(sm, "Walk", Clip(clips, "Walk"));
            var runClip = Clip(clips, "Run");
            var run = AddState(sm, "Run", runClip != null ? runClip : Clip(clips, "Walk"));
            var attack = AddState(sm, "Attack", Clip(clips, "Attack"));
            var hit = AddState(sm, "Hit", Clip(clips, "Hit"));
            var death = AddState(sm, "Death", Clip(clips, "Death"));

            sm.defaultState = idle;

            // Idle <-> Walk <-> Run（阈值和 Enemy.SetAnimSpeed 的 0 / 0.5 / 1 对应）
            AddSpeedTransition(idle, walk, 0.15f, AnimatorConditionMode.Greater, 0.12f);
            AddSpeedTransition(walk, idle, 0.15f, AnimatorConditionMode.Less, 0.12f);
            AddSpeedTransition(walk, run, 0.75f, AnimatorConditionMode.Greater, 0.12f);
            AddSpeedTransition(run, walk, 0.75f, AnimatorConditionMode.Less, 0.12f);

            // 回到 Idle（播完再回）
            AddReturnToIdle(attack, idle);
            AddReturnToIdle(hit, idle);
            // Attack / Hit 播到一半时如果玩家还活着仍在移动，Walk 会在下一条 Idle→Walk 的判定里接上

            // AnyState -> Attack / Hit / Death
            var anyAttack = sm.AddAnyStateTransition(attack);
            anyAttack.hasExitTime = false;
            anyAttack.duration = 0.08f;
            anyAttack.canTransitionToSelf = false;
            anyAttack.AddCondition(AnimatorConditionMode.If, 0f, "Attack");
            anyAttack.AddCondition(AnimatorConditionMode.IfNot, 0f, "Dead");

            var anyHit = sm.AddAnyStateTransition(hit);
            anyHit.hasExitTime = false;
            anyHit.duration = 0.06f;
            anyHit.canTransitionToSelf = false;
            anyHit.AddCondition(AnimatorConditionMode.If, 0f, "Hit");
            anyHit.AddCondition(AnimatorConditionMode.IfNot, 0f, "Dead");

            var anyDeath = sm.AddAnyStateTransition(death);
            anyDeath.hasExitTime = false;
            anyDeath.duration = 0.1f;
            anyDeath.canTransitionToSelf = false;
            anyDeath.AddCondition(AnimatorConditionMode.If, 0f, "Dead");

            report.AppendLine("  controller " + path + " states=6 params=Speed/Attack/Hit/Dead");

            EditorUtility.SetDirty(ctrl);
            AssetDatabase.SaveAssets();
            return AssetDatabase.LoadAssetAtPath<AnimatorController>(path);
        }

        private static AnimationClip Clip(Dictionary<string, AnimationClip> clips, string key)
        {
            AnimationClip c;
            return clips.TryGetValue(key, out c) ? c : null;
        }

        private static AnimatorState AddState(AnimatorStateMachine sm, string name, AnimationClip clip)
        {
            var st = sm.AddState(name);
            st.motion = clip;
            st.writeDefaultValues = true;
            st.speed = 1f;
            return st;
        }

        private static void AddReturnToIdle(AnimatorState from, AnimatorState idle)
        {
            var tr = from.AddTransition(idle);
            tr.hasExitTime = true;
            tr.exitTime = 0.9f;
            tr.duration = 0.1f;
        }

        private static void AddSpeedTransition(AnimatorState from, AnimatorState to, float threshold,
            AnimatorConditionMode mode, float duration)
        {
            var tr = from.AddTransition(to);
            tr.hasExitTime = false;
            tr.duration = duration;
            tr.AddCondition(mode, threshold, "Speed");
        }

        // =====================================================================
        //  Prefab
        // =====================================================================

        private static string BuildPrefab(EnemySpec spec, RuntimeAnimatorController ctrl, System.Text.StringBuilder report)
        {
            var basePrefab = AssetDatabase.LoadAssetAtPath<GameObject>(spec.BasePrefab);
            if (basePrefab == null)
            {
                report.AppendLine("  ! 缺少 base prefab " + spec.BasePrefab);
                return "(失败)";
            }

            // 用一个临时空场景承载实例，避免弄脏用户当前打开的场景
            var tempScene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
            GameObject root = null;
            try
            {
                root = Object.Instantiate(basePrefab);
                SceneManager.MoveGameObjectToScene(root, tempScene);
                root.name = spec.Id;
                root.transform.position = Vector3.zero;
                root.transform.rotation = Quaternion.identity;
                root.transform.localScale = Vector3.one * spec.Scale;

                // --- 材质（可选染色） ---
                if (spec.Tint)
                {
                    var tintMat = BuildTintMaterial(spec);
                    foreach (var smr in root.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                    {
                        var mats = smr.sharedMaterials;
                        bool changed = false;
                        for (int i = 0; i < mats.Length; i++)
                        {
                            if (mats[i] != null && mats[i].name.StartsWith(spec.TintMatPrefix))
                            {
                                mats[i] = tintMat;
                                changed = true;
                            }
                        }
                        if (changed) smr.sharedMaterials = mats;
                    }
                }

                // --- Animator ---
                var animator = root.GetComponent<Animator>();
                if (animator == null) animator = root.AddComponent<Animator>();
                animator.runtimeAnimatorController = ctrl;
                animator.applyRootMotion = false;
                animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
                animator.updateMode = AnimatorUpdateMode.Normal;

                // --- CharacterController ---
                var cc = root.GetComponent<CharacterController>();
                if (cc == null) cc = root.AddComponent<CharacterController>();
                float s = Mathf.Max(0.01f, root.transform.lossyScale.y);
                cc.height = spec.WorldHeight / s;
                cc.radius = 0.45f / s;
                cc.center = new Vector3(0f, spec.WorldHeight * 0.5f / s, 0f);
                cc.slopeLimit = 50f;
                cc.stepOffset = 0.4f / s;
                cc.skinWidth = 0.03f / s;
                cc.minMoveDistance = 0f;
                cc.enableOverlapRecovery = true;

                // --- 刚体（运动学）：满足“敌人要有刚体”的约定，同时不跟 CharacterController 抢位移 ---
                var rb = root.GetComponent<Rigidbody>();
                if (rb == null) rb = root.AddComponent<Rigidbody>();
                rb.isKinematic = true;
                rb.useGravity = false;
                rb.constraints = RigidbodyConstraints.FreezeRotation;
                rb.interpolation = RigidbodyInterpolation.None;
                rb.collisionDetectionMode = CollisionDetectionMode.Discrete;

                // --- 血条：结构和 HealthBar.Attach() 一致，Awake 里会按名字找回 Bar/Fill ---
                BuildHealthBar(root, report);

                // --- Enemy ---
                var enemy = root.GetComponent<Enemy>();
                if (enemy == null) enemy = root.AddComponent<Enemy>();
                var so = new SerializedObject(enemy);
                SetFloat(so, "maxHealth", spec.Hp);
                SetFloat(so, "walkSpeed", spec.WalkSpeed);
                SetFloat(so, "runSpeed", spec.RunSpeed);
                SetFloat(so, "attackDamage", spec.Damage);
                SetFloat(so, "attackRange", spec.Range);
                so.ApplyModifiedPropertiesWithoutUndo();

                var path = PrefabDir + "/" + spec.Id + ".prefab";
                AssetDatabase.DeleteAsset(path);
                PrefabUtility.SaveAsPrefabAsset(root, path, out bool ok);
                report.AppendLine("  prefab " + path + " ok=" + ok + " hp=" + spec.Hp + " scale=" + spec.Scale);
                return path;
            }
            finally
            {
                if (root != null) Object.DestroyImmediate(root);
                EditorSceneManager.CloseScene(tempScene, true);
            }
        }

        private static void BuildHealthBar(GameObject root, System.Text.StringBuilder report)
        {
            var old = root.transform.Find("HealthBar");
            if (old != null) Object.DestroyImmediate(old.gameObject);

            var barGo = new GameObject("HealthBar");
            barGo.transform.SetParent(root.transform, false);
            barGo.transform.localPosition = new Vector3(0f, 2.6f, 0f); // 和 MyWorldBootstrap 里 HealthBar.Attach(t, 2.6f) 一致
            barGo.AddComponent<HealthBar>();

            var barRoot = new GameObject("Bar");
            barRoot.transform.SetParent(barGo.transform, false);
            barRoot.transform.localPosition = new Vector3(0f, 0.3f, 0f);

            var bgMat = MakeBarMaterial("M_E_HealthBarBG", new Color(0.10f, 0.10f, 0.12f));
            var fillMat = MakeBarMaterial("M_E_HealthBarFill", new Color(0.90f, 0.30f, 0.28f));
            MakeBarPiece(barRoot.transform, root.scene, "BG", new Vector3(1.3f, 0.16f, 0.02f), Vector3.zero, bgMat);
            MakeBarPiece(barRoot.transform, root.scene, "Fill", new Vector3(1.248f, 0.0992f, 0.03f),
                new Vector3(0f, 0f, -0.02f), fillMat);

            report.AppendLine("  healthbar 已加入 prefab（Bar/BG/Fill）");
        }

        private static Material MakeBarMaterial(string name, Color color)
        {
            var path = MatDir + "/" + name + ".mat";
            AssetDatabase.DeleteAsset(path);
            var mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
            mat.name = name;
            mat.SetColor("_BaseColor", color);
            AssetDatabase.CreateAsset(mat, path);
            return AssetDatabase.LoadAssetAtPath<Material>(path);
        }

        private static void MakeBarPiece(Transform parent, Scene scene, string name, Vector3 scale,
            Vector3 localPos, Material mat)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            SceneManager.MoveGameObjectToScene(go, scene);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localScale = scale;
            var col = go.GetComponent<Collider>();
            if (col != null) Object.DestroyImmediate(col);
            var r = go.GetComponent<MeshRenderer>();
            r.sharedMaterial = mat;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
        }

        private static void SetFloat(SerializedObject so, string field, float value)        {
            var p = so.FindProperty(field);
            if (p != null) p.floatValue = value;
            else Debug.LogWarning("[EnemyFactory] Enemy 字段不存在: " + field);
        }

        private static Material BuildTintMaterial(EnemySpec spec)
        {
            var src = AssetDatabase.LoadAssetAtPath<Material>(spec.TintSourceMat);
            var mat = new Material(src);
            mat.name = "M_" + spec.Id;
            if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", spec.TintColor);
            var path = MatDir + "/M_" + spec.Id + ".mat";
            AssetDatabase.DeleteAsset(path);
            AssetDatabase.CreateAsset(mat, path);
            return AssetDatabase.LoadAssetAtPath<Material>(path);
        }

        // =====================================================================
        //  菜单 ③ 接进当前场景（只写 enemyPrefab 槽位，不保存场景）
        // =====================================================================

        [MenuItem("Tools/My World/敌人/③ 把蛮兵接进当前地图的 enemyPrefab 槽位", false, 3)]
        public static void WireIntoCurrentScene()
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabDir + "/E_Barbarian.prefab");
            if (prefab == null)
            {
                Debug.LogError("[EnemyFactory] 还没有 E_Barbarian.prefab，先执行菜单 ①。");
                return;
            }

            var all = Object.FindObjectsByType<MonoBehaviour>(FindObjectsSortMode.None);
            int wired = 0;
            foreach (var mb in all)
            {
                // MapBootstrap（BuenaVillage / RoaTown / RanoaAcademy）和 MyWorldBootstrap 都有一个叫 enemyPrefab 的私有序列化字段
                bool isMap = mb is MapBootstrap;
                bool isWorld = mb is MyWorldBootstrap;
                if (!isMap && !isWorld) continue;

                var so = new SerializedObject(mb);
                var p = so.FindProperty("enemyPrefab");
                if (p == null) continue;
                p.objectReferenceValue = prefab;
                so.ApplyModifiedPropertiesWithoutUndo();
                EditorUtility.SetDirty(mb);
                wired++;
                Debug.Log("[EnemyFactory] 已把 " + prefab.name + " 接到 " + mb.GetType().Name + " (" + mb.gameObject.name + ")");
            }

            if (wired == 0)
                Debug.LogWarning("[EnemyFactory] 当前场景里没有 MapBootstrap / MyWorldBootstrap（先打开 BuenaVillage / RoaTown / RanoaAcademy / MyWorld 场景）。");
            else
            {
                EditorSceneManager.MarkSceneDirty(SceneManager.GetActiveScene());
                Debug.Log("[EnemyFactory] 接线完成，共 " + wired + " 处。按 Ctrl+S 保存场景后进 Play 才生效。");
            }
        }

        // =====================================================================
        //  工具
        // =====================================================================

        private static void EnsureFolders()
        {
            EnsureFolder("Assets/Generated");
            EnsureFolder(AnimRoot);
            EnsureFolder(ClipDir);
            EnsureFolder(CtrlDir);
            EnsureFolder(EnemyRoot);
            EnsureFolder(PrefabDir);
            EnsureFolder(MatDir);
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            var parent = Path.GetDirectoryName(path).Replace('\\', '/');
            var leaf = Path.GetFileName(path);
            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, leaf);
        }
    }
}
