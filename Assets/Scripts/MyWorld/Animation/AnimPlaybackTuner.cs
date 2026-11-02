using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 把 <see cref="Animator.speed"/> 调到「与当前动作/实际速度匹配的播放倍率」。
    ///
    /// 🔴 **它解决什么**：原来所有状态都是 1.0 倍速播（实测控制器里每个 state 的
    /// `speed = 1`、`speedParameterActive = false`），而 Walk 剪辑自带的地面速度只有
    /// ≈0.83 m/s、Run ≈3.62 m/s，玩法速度却是 5.5 / 9.5 m/s —— 脚在地上滑 6 倍。
    /// 倍率 = 实际速度 ÷ 剪辑自带速度 之后，**脚掌落地期间不再位移**。
    ///
    /// 剪辑自带速度是拿 `AnimationMode` 逐帧采样 `toes.l/toes.r/foot.l/foot.r` 实测出来的，
    /// 数值与出处写在 <see cref="AnimFeelSettings"/> 里。
    ///
    /// 控制器侧不需要任何新参数 —— 只写 <see cref="Animator.speed"/>，
    /// 所以**不用改 `Assets/Editor/MageSetup.cs` 重新生成 Controller**。
    /// </summary>
    public static class AnimPlaybackTuner
    {
        // ---- 位移类剪辑：倍率 = 实际速度 / 剪辑自带速度 ----
        private static readonly int WalkState = Animator.StringToHash("Walk");
        private static readonly int RunState = Animator.StringToHash("Run");
        private static readonly int WalkBackState = Animator.StringToHash("Walk_Back");
        private static readonly int StrafeLeftState = Animator.StringToHash("Run_Strafe_L");
        private static readonly int StrafeRightState = Animator.StringToHash("Run_Strafe_R");

        // ---- 攻击/施法类剪辑：倍率 = 配置的固定值 ----
        private static readonly int Attack1State = Animator.StringToHash("Attack1");
        private static readonly int Attack2State = Animator.StringToHash("Attack2");
        private static readonly int Attack3State = Animator.StringToHash("Attack3");
        private static readonly int Attack4State = Animator.StringToHash("Attack4");
        private static readonly int CastState = Animator.StringToHash("Cast");
        private static readonly int BowShotState = Animator.StringToHash("BowShot");
        private static readonly int HitState = Animator.StringToHash("Hit");
        private static readonly int PunchAState = Animator.StringToHash("Punch_A");
        private static readonly int PunchBState = Animator.StringToHash("Punch_B");
        private static readonly int KickState = Animator.StringToHash("Kick");
        private static readonly int GauntletPunchAState = Animator.StringToHash("GauntletPunch_A");
        private static readonly int GauntletPunchBState = Animator.StringToHash("GauntletPunch_B");
        private static readonly int ShieldBashState = Animator.StringToHash("Shield_Bash");

        /// <summary>是不是「角色在世界里位移」的剪辑（只有这类剪辑需要按速度对拍）。</summary>
        public static bool IsLocomotion(int stateHash)
        {
            return stateHash == WalkState
                || stateHash == RunState
                || stateHash == WalkBackState
                || stateHash == StrafeLeftState
                || stateHash == StrafeRightState;
        }

        /// <summary>
        /// 当前应该用的播放倍率。
        /// </summary>
        /// <param name="anim">目标 Animator（第 0 层）。</param>
        /// <param name="planarVelocity">角色**实际**的水平速度（米/秒），不是输入意图。</param>
        /// <param name="feel">手感参数，null 时用 <see cref="AnimFeelSettings.Active"/>。</param>
        public static float DesiredScale(Animator anim, Vector3 planarVelocity, AnimFeelSettings feel)
        {
            if (anim == null) return 1f;

            // 只取水平分量：上下坡的 Y 是重力，不是迈步。
            float speed = new Vector2(planarVelocity.x, planarVelocity.z).magnitude;
            return ScaleForState(PickStateHash(anim), speed, feel);
        }

        /// <summary>
        /// **纯函数**：给定"状态 + 水平速度"算出播放倍率。
        ///
        /// 拆出来的唯一目的是**可以离线验算**：滑步量 = 实际速度 − 剪辑自带速度 × 倍率，
        /// 控制器的状态/剪辑全都实测过，于是"到底还滑不滑"能用一段算术直接证明，
        /// 不必进 Play 模式靠眼睛看（`Assets/Scripts/MyWorld/Animation/` 里没有测试框架，
        /// 验算走的是编辑器 MCP 的 `execute_code`）。
        /// </summary>
        /// <param name="stateHash">动画状态的 <see cref="Animator.StringToHash"/>（用状态名算）。</param>
        /// <param name="planarSpeed">水平速度的模长（米/秒）。</param>
        public static float ScaleForState(int stateHash, float planarSpeed, AnimFeelSettings feel)
        {
            if (feel == null) feel = AnimFeelSettings.Active;

            if (IsLocomotion(stateHash))
            {
                if (stateHash == WalkState) return feel.Clamp(planarSpeed / Mathf.Max(feel.walkClipSpeed, 0.01f));
                if (stateHash == RunState) return feel.Clamp(planarSpeed / Mathf.Max(feel.runClipSpeed, 0.01f));
                if (stateHash == WalkBackState) return feel.Clamp(planarSpeed / Mathf.Max(feel.backClipSpeed, 0.01f));
                return feel.Clamp(planarSpeed / Mathf.Max(feel.strafeClipSpeed, 0.01f));
            }

            // ---- 动作类剪辑 ----
            if (stateHash == Attack1State) return feel.Clamp(feel.ComboPlayback(0));
            if (stateHash == Attack2State) return feel.Clamp(feel.ComboPlayback(1));
            if (stateHash == Attack3State) return feel.Clamp(feel.ComboPlayback(2));
            if (stateHash == Attack4State) return feel.Clamp(feel.ComboPlayback(3));
            if (stateHash == CastState) return feel.Clamp(feel.castPlayback);
            if (stateHash == BowShotState) return feel.Clamp(feel.bowShotPlayback);
            if (stateHash == HitState) return feel.Clamp(feel.hitPlayback);

            if (stateHash == PunchAState || stateHash == PunchBState || stateHash == KickState
                || stateHash == GauntletPunchAState || stateHash == GauntletPunchBState
                || stateHash == ShieldBashState)
            {
                return feel.Clamp(feel.unarmedPlayback);
            }

            // Idle / Blocking / Jump / Death 等：1.0 倍速最自然。
            return 1f;
        }

        /// <summary>
        /// 取「这一帧最该按它算倍率」的状态。
        ///
        /// 正在过渡时（例如 Idle→Walk 那 0.12s 交叉淡入）当前状态还是**旧**的那个，
        /// 但画面上正在淡入的是**新**的位移剪辑 —— 新剪辑必须一进场就是正确节奏，
        /// 否则起步那两步仍然是滑的。所以：当前/目标里**只要有一个是位移剪辑，就用它**。
        /// 反过来 Run→Idle 刹停时，留在 Run 上继续对拍，刹车那几步也不会滑。
        /// </summary>
        private static int PickStateHash(Animator anim)
        {
            int current = anim.GetCurrentAnimatorStateInfo(0).shortNameHash;
            if (!anim.IsInTransition(0)) return current;

            int next = anim.GetNextAnimatorStateInfo(0).shortNameHash;
            if (next == 0 || next == current) return current;

            return IsLocomotion(next) ? next : current;
        }
    }
}
