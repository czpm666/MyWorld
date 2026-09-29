using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 法师角色的表现层：驱动 Animator，处理左键攻击并放出法术弹。
    /// 挂在 Player 根节点上，Animator 在子物体（KayKit 角色预制体）里自动找。
    ///
    /// 法术朝哪飞**不在这里决定**，由 `PlayerCombat.CastSpell()` 按优先级取：
    /// **锁定目标 > 鼠标方向 > 角色朝向**（`PlayerCombat.cs:198-208`）；未锁定时用
    /// `PlayerAim.MouseDirection`（每帧都写，`PlayerAim.cs:22-25,63-64`），
    /// 只有连鼠标方向都拿不到才回退 `transform.forward`。
    ///
    /// ⚠️ 本类原先写"法术朝角色当前朝向飞（transform.forward），**不做鼠标瞄准**" —— 那是**旧行为**，
    /// 已订正（R-003(a)）。相机的 yaw 仍恒为 0、朝向仍吸附 8 方向，这两条没变。
    /// </summary>
    [DisallowMultipleComponent]
    public class PlayerMage : MonoBehaviour
    {
        private static readonly int SpeedHash = Animator.StringToHash("Speed");
        private static readonly int AttackHash = Animator.StringToHash("Attack");
        private static readonly int SlashHash = Animator.StringToHash("Slash");
        private static readonly int ComboHash = Animator.StringToHash("ComboStep");
        private static readonly int HitHash = Animator.StringToHash("Hit");
        private static readonly int DeadHash = Animator.StringToHash("Dead");

        /// <summary>弓的**独立**触发器（T-050）。见 PlayBowShot 的说明。</summary>
        private static readonly int BowShotHash = Animator.StringToHash("BowShot");

        /// <summary>一套连招有几段。要和 MageSetup 里 ComboClips 的长度一致。</summary>
        public const int ComboLength = 4;

        private Animator animator;
        private PlayerController8Dir move;

        private void Awake()
        {
            animator = GetComponentInChildren<Animator>();
            move = GetComponent<PlayerController8Dir>();
        }

        private void Update()
        {
            // 只负责把移动速度喂给 Animator；攻击/施法由 PlayerCombat 驱动
            if (animator != null && move != null)
                animator.SetFloat(SpeedHash, move.AnimSpeed);
        }

        /// <summary>播放施法动作。实际的伤害/弹道由 PlayerCombat 负责。</summary>
        public void PlayCast()
        {
            if (animator != null) animator.SetTrigger(AttackHash);
        }

        /// <summary>
        /// 播放挥砍动作（剑/斧这类近战主手）。
        ///
        /// 用**独立的 `Slash` 触发器**，不能复用 `Attack`：那个参数（以及
        /// MageAnimator 里的 AnyState 过渡）是给施法用的，接到 Cast 状态上。
        /// 之前 `PlayAttack()` 和 `PlayCast()` 共用一个 trigger，所以挥剑播的是
        /// 法师原地念咒的动作 —— 也就是"挥砍时什么动作都没有"的直接原因。
        /// </summary>
        public void PlayAttack()
        {
            PlayAttack(0);
        }

        /// <summary>
        /// 播放连招的第 <paramref name="comboStep"/> 段（0=横劈 1=下劈 2=斜劈 3=突刺）。
        ///
        /// `ComboStep` 是整数参数，Animator 里每段状态挂一个 "Slash + ComboStep == n" 的
        /// AnyState 过渡。用整数而不是四个独立触发器，是为了参数少、而且同时只会命中一条过渡。
        /// </summary>
        public void PlayAttack(int comboStep)
        {
            if (animator == null) return;
            animator.SetInteger(ComboHash, Mathf.Clamp(comboStep, 0, ComboLength - 1));
            animator.SetTrigger(SlashHash);
        }

        /// <summary>
        /// 播放射箭动作（T-050）。用**独立的 `BowShot` 触发器**，理由与 `PlayAttack` 用 `Slash` 完全一致：
        /// 若改用 `PlayAttack()`，它会 `SetInteger(ComboStep, 0)` + `SetTrigger(Slash)` ——
        /// 结果是 **①射箭播横劈**、**②动到剑的连招段位**、**③Trigger 若当帧没被消费会残留**，
        /// 之后莫名再挥一刀。三个都是静默的。
        ///
        /// ⚠️ 本方法**只起手**；箭矢由剪辑上的 `OnArrowRelease` 事件经 `AnimEventRelay` 回调
        /// `PlayerCombat.OnArrowRelease()` 才生成。
        /// </summary>
        public void PlayBowShot()
        {
            if (animator != null) animator.SetTrigger(BowShotHash);
        }

        /// <summary>供木桩/敌人回调，播受击动作。</summary>
        public void PlayHit()
        {
            if (animator != null) animator.SetTrigger(HitHash);
        }

        /// <summary>死亡动作（留着给后面的战斗系统用）。</summary>
        public void PlayDeath()
        {
            if (animator != null) animator.SetBool(DeadHash, true);
        }
    }
}
