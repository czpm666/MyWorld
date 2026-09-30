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

        // ⚠️ 下面两个字符串**必须与 `MageSetup`（Editor 程序集）逐字一致** —— 两个程序集
        //    **不能互相引用**，只能各写一份；**名字不匹配不会报错，只会静默不动**（陷阱 20 / 21）。
        //    * 参数：`MageSetup.IsBlockingParam`（`MageSetup.cs`）
        //    * 状态：`MageSetup.Wanted[]` 的**首列**（**不是** `expectSource`！两者有 20/29 条不同名）
        /// <summary>T-079 §⑦ 片 2：格挡保持态的参数名（Bool）。</summary>
        private static readonly int IsBlockingHash = Animator.StringToHash("IsBlocking");

        /// <summary>T-079 §⑦ 片 2：格挡受击状态名（`Animator.Play` 用的是**状态名**）。</summary>
        private const string BlockHitStateName = "Block_Hit";

        /// <summary>一套连招有几段。要和 MageSetup 里 ComboClips 的长度一致。</summary>
        public const int ComboLength = 4;

        private Animator animator;
        private PlayerController8Dir move;
        private PlayerCombat combat;

        private void Awake()
        {
            animator = GetComponentInChildren<Animator>();
            move = GetComponent<PlayerController8Dir>();
            combat = GetComponent<PlayerCombat>();
        }

        private void Update()
        {
            // 只负责把移动速度喂给 Animator；攻击/施法由 PlayerCombat 驱动
            if (animator != null && move != null)
                animator.SetFloat(SpeedHash, move.AnimSpeed);

            // T-079 §⑦ 片 2：格挡保持态。**每帧喂**（与 `Speed` 同一个地方、同一种语义：
            // "此刻是不是这个状态"）。`PlayerCombat.IsBlocking` 在它自己的 `Update` 里逐帧赋值为
            // `shieldUp`（`PlayerCombat.cs:120-121`），本方法只做搬运，**不自己判定举盾**。
            if (animator != null)
            {
                // 烘焙场景里 Awake 的时序不可靠（同 PlayerHealth.Start 的兜底），拿不到就再取一次
                if (combat == null) combat = GetComponent<PlayerCombat>();
                animator.SetBool(IsBlockingHash, combat != null && combat.IsBlocking);
            }
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

        /// <summary>
        /// T-079 §⑦ 片 2：播**格挡受击**（`Block_Hit`）。
        ///
        /// **谁调、什么时候调**：`PlayerHealth.TakeDamage` 在**真正减伤那一刻**调它 ——
        /// 落点在 80° 角检**内部**、与 `amount *= mult`（`PlayerHealth.cs:144-151`）**同一层**。
        /// **不是**"举着盾"那层（`:139`，那里只问有没有举盾、不看攻击来自哪个方向），
        /// **更不是**按键那一刻。**表现跟随事实，不跟随意图。**
        /// 侧后方挨打（角度 > 80°）**不该**播它 —— 由"调用点只在角检里"这一条保证（不是靠这里判方向）。
        ///
        /// ⚠️ **为什么用 `Animator.Play(状态名, 0, 0)`，而不是新增一个 Trigger 参数**：
        /// ① 新增 Trigger = **再新增一个参数**，而本片的预期新增只有 `IsBlocking` + 三个状态；
        /// ② `PlayHit()` 与本节在同一帧、同一方法里（`TakeDamage`）都会被调用到，
        ///    两个 Trigger 同帧成立时谁赢取决于 AnyState 的判定顺序 → **不确定**；
        ///    拆成**互斥两支**（挡住 → 本方法；没挡住 → `PlayHit`）+ 直接 `Play` 才是确定的。
        /// ③ 出边仍在控制器里（`Block_Hit` 的两条 exit time 出边）→ **不会卡在 `Block_Hit` 里**。
        /// ⚠️ 用**状态名**寻址 —— 必须与 `MageSetup.Wanted[]` 的**首列**逐字一致（见上面的注释）。
        /// </summary>
        public void PlayBlockHit()
        {
            if (animator != null) animator.Play(BlockHitStateName, 0, 0f);
        }

        /// <summary>死亡动作（留着给后面的战斗系统用）。</summary>
        public void PlayDeath()
        {
            if (animator != null) animator.SetBool(DeadHash, true);
        }
    }
}
