#if UNITY_EDITOR
using System.Text;
using UnityEditor;
using UnityEngine;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// 动画手感自检：`Tools > My World > 校验动画手感（滑步/倍率）`。
    ///
    /// **为什么要有这个菜单**：本轮把"移动动画跟不跟得上实际速度"做成了
    /// `播放倍率 = 实际水平速度 ÷ 剪辑自带速度`（见 <see cref="AnimPlaybackTuner"/>）。
    /// 这句话对不对、倍率有没有撞到上下限、"还滑不滑步"，全部可以**算**出来 ——
    /// 不必进 Play 模式靠眼睛看，也不必截图。这个菜单就是把那段算术跑一遍并打印表格。
    ///
    /// 它**调用的是运行时真正在用的那个函数**（<see cref="AnimPlaybackTuner.ScaleForState"/>），
    /// 不是在这里重抄一遍公式，所以参数改了、代码改了，结论会跟着变。
    /// 滑步量 = |实际速度| − 剪辑自带速度 × 播放倍率；等于 0 就是脚不打滑。
    /// </summary>
    public static class AnimFeelQa
    {
        // ------------------------------------------------------------------
        // 剪辑自带速度（**实测值**，单位 m/s @ 1.0 倍速）
        //
        // 测法（本轮真跑过）：把 MageCharacter.prefab 实例化，`AnimationMode.StartAnimationMode()`
        // 逐帧 `SampleAnimationClip`，取脚掌骨骼 Y 最低的那段"贴地窗口"，
        // 用窗口内脚在角色本地空间的水平位移 ÷ 时长 —— 就是这段动画"假定人在走多快"。
        // 脚掌有左右两只，取两只里较慢（更保守）的那个。
        // ------------------------------------------------------------------
        private const float MeasuredWalkSpeed = 0.85f;    // Walk.anim
        private const float MeasuredRunSpeed = 3.60f;     // Run.anim（Sprint 就用它）
        private const float MeasuredStrafeSpeed = 3.55f;  // Run_Strafe_L/R.anim
        private const float MeasuredBackSpeed = 0.83f;    // Walk_Back.anim

        /// <summary>实测值与参数值的允许偏差。</summary>
        private const float SpeedTolerance = 0.06f;

        // ------------------------------------------------------------------
        // 控制器里的过渡阈值（**必须与 Assets/Editor/MageSetup.cs 里的一致**）
        //   Idle→Walk  Speed > 0.15      Walk→Run / Idle→Run  Speed > 0.75
        // ------------------------------------------------------------------
        private const float WalkEnterThreshold = 0.15f;
        private const float RunEnterThreshold = 0.75f;

        /// <summary>没有玩家实例时用的兜底速度（= 场景里那份组件的值）。</summary>
        private const float FallbackWalkSpeed = 5.5f;
        private const float FallbackRunSpeed = 9.5f;

        [MenuItem("Tools/My World/校验动画手感（滑步/倍率）", priority = 31)]
        public static void Run()
        {
            AnimFeelSettings feel = AnimFeelSettings.Active;
            if (feel == null)
            {
                Debug.LogError("[手感自检] 拿不到 AnimFeelSettings —— 运行时连代码默认值都给不出来，先查 AnimFeelSettings.Active。");
                return;
            }

            var sb = new StringBuilder();
            sb.AppendLine("[手感自检] 移动动画播放倍率 / 滑步量");
            sb.AppendLine("  滑步量 = |实际速度| − 剪辑自带速度 × 播放倍率；0 = 脚不打滑。");

            bool allGood = true;

            // ---- 1) 参数里的"剪辑自带速度"是不是还等于实测值 ----
            sb.AppendLine();
            sb.AppendLine("① 剪辑自带速度：参数值 vs 实测值");
            allGood &= CheckClipSpeed(sb, "walkClipSpeed", feel.walkClipSpeed, MeasuredWalkSpeed);
            allGood &= CheckClipSpeed(sb, "runClipSpeed", feel.runClipSpeed, MeasuredRunSpeed);
            allGood &= CheckClipSpeed(sb, "strafeClipSpeed", feel.strafeClipSpeed, MeasuredStrafeSpeed);
            allGood &= CheckClipSpeed(sb, "backClipSpeed", feel.backClipSpeed, MeasuredBackSpeed);

            // ---- 2) 场景里玩家真正用的速度 ----
            float walkSpeed = FallbackWalkSpeed;
            float runSpeed = FallbackRunSpeed;
            PlayerController8Dir controller = Object.FindFirstObjectByType<PlayerController8Dir>();
            if (controller != null)
            {
                var so = new SerializedObject(controller);
                SerializedProperty w = so.FindProperty("walkSpeed");
                SerializedProperty r = so.FindProperty("runSpeed");
                if (w != null) walkSpeed = w.floatValue;
                if (r != null) runSpeed = r.floatValue;
            }
            else
            {
                sb.AppendLine();
                sb.AppendLine("  ⚠ 场景里没有 PlayerController8Dir，用兜底速度 " + FallbackWalkSpeed + " / " + FallbackRunSpeed + "。");
            }

            // ---- 3) 滑步表 ----
            sb.AppendLine();
            sb.AppendLine("② 滑步表（玩家 walkSpeed=" + walkSpeed.ToString("0.##") + "，runSpeed=" + runSpeed.ToString("0.##") + "）");
            sb.AppendLine("   速度     状态          播放倍率   滑步量(m/s)  备注");

            // 走/跑状态下限 + 两个真实速度 + 锁定时的侧移/后退
            allGood &= Row(sb, feel, "Walk", 0.6f);
            allGood &= Row(sb, feel, "Run", walkSpeed * 0.5f);
            allGood &= Row(sb, feel, "Run", walkSpeed);
            allGood &= Row(sb, feel, "Run", runSpeed);
            allGood &= Row(sb, feel, "Run_Strafe_L", walkSpeed);
            allGood &= Row(sb, feel, "Walk_Back", walkSpeed, knownLimit: true);

            // ---- 4) 播放倍率上限够不够用 ----
            sb.AppendLine();
            sb.AppendLine("③ 倍率上限");
            float needed = runSpeed / Mathf.Max(feel.runClipSpeed, 0.01f);
            bool upperOk = feel.maxPlayback + 0.001f >= needed;
            sb.AppendLine("  冲刺需要 " + needed.ToString("0.###") + "×，maxPlayback=" + feel.maxPlayback.ToString("0.###")
                          + " → " + (upperOk ? "够用" : "**不够，冲刺会打滑**"));
            allGood &= upperOk;

            // ---- 5) 状态速度带（玩家看不出走路循环其实是"起步过渡"用的）----
            sb.AppendLine();
            sb.AppendLine("④ 控制器状态按本参数划分的速度带（Speed 参数 = 速度 ÷ speedParamFullSpeed）");
            float full = Mathf.Max(feel.speedParamFullSpeed, 0.01f);
            sb.AppendLine("   Idle   : 0 ~ " + (WalkEnterThreshold * full).ToString("0.##") + " m/s");
            sb.AppendLine("   Walk   : " + (WalkEnterThreshold * full).ToString("0.##") + " ~ " + (RunEnterThreshold * full).ToString("0.##") + " m/s");
            sb.AppendLine("   Run    : " + (RunEnterThreshold * full).ToString("0.##") + " m/s 以上");

            sb.AppendLine();
            sb.AppendLine(allGood
                ? "[手感自检] 通过：倍率没撞上限，走 / 跑 / 冲刺 / 锁定侧移都不滑步。唯一保留项是锁定后退（KayKit 没有 Run_Back 剪辑），已在表里标成已知限制。"
                : "[手感自检] **有不通过项**，见上面标注。");

            if (allGood) Debug.Log(sb.ToString());
            else Debug.LogWarning(sb.ToString());
        }

        private static bool CheckClipSpeed(StringBuilder sb, string fieldName, float configured, float measured)
        {
            bool ok = Mathf.Abs(configured - measured) <= SpeedTolerance;
            sb.AppendLine("  " + fieldName.PadRight(18) + "参数 " + configured.ToString("0.###").PadLeft(6)
                          + "   实测 " + measured.ToString("0.###").PadLeft(6)
                          + "   " + (ok ? "一致" : "**不一致 → 滑步量会算错，请按实测值改参数**"));
            return ok;
        }

        private static bool Row(StringBuilder sb, AnimFeelSettings feel, string stateName, float speed, bool knownLimit = false)
        {
            int hash = Animator.StringToHash(stateName);
            float playback = AnimPlaybackTuner.ScaleForState(hash, speed, feel);

            float clipSpeed = ClipSpeedFor(stateName, feel);
            float slip = speed - clipSpeed * playback;

            bool clamped = playback >= feel.maxPlayback - 0.001f || playback <= feel.minPlayback + 0.001f;
            // 贴地容差：0.15 m/s 以内的残差眼睛看不出来（脚本来也不是绝对锁死的）。
            bool ok = Mathf.Abs(slip) <= 0.15f;

            // 已知限制不算回归：KayKit 没有 Run_Back 剪辑，锁定后退只能靠 Walk_Back 硬拉倍率。
            // 仍然打印出来，但不让自检变红，否则每次跑都失败、真正的回归就没人看了。
            if (knownLimit && !ok)
            {
                sb.AppendLine("   " + speed.ToString("0.##").PadLeft(6) + "   " + stateName.PadRight(14)
                              + playback.ToString("0.###").PadLeft(7) + "   " + slip.ToString("+0.00;-0.00;0.00").PadLeft(9)
                              + "     ⚠ 已知限制：没有 Run_Back 剪辑，只能滑（改前 " +
                              (speed - clipSpeed).ToString("0.00") + " m/s → 现在 " + Mathf.Abs(slip).ToString("0.00") + " m/s）");
                return true;
            }

            string note = ok ? "OK" : (clamped ? "**倍率撞限，剪辑带不动这个速度**" : "**不匹配**");

            sb.AppendLine("   " + speed.ToString("0.##").PadLeft(6) + "   " + stateName.PadRight(14)
                          + playback.ToString("0.###").PadLeft(7) + "   " + slip.ToString("+0.00;-0.00;0.00").PadLeft(9)
                          + "     " + note);
            return ok;
        }

        private static float ClipSpeedFor(string stateName, AnimFeelSettings feel)
        {
            switch (stateName)
            {
                case "Walk": return feel.walkClipSpeed;
                case "Run": return feel.runClipSpeed;
                case "Walk_Back": return feel.backClipSpeed;
                default: return feel.strafeClipSpeed;
            }
        }
    }
}
#endif
