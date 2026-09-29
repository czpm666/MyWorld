using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 动画事件转发器。
    ///
    /// **AnimationEvent 只派发到"持有 Animator 的那个 GameObject"上的组件。**
    /// 本工程的 Animator 在 `Player/Character`（预制体 `MageCharacter` 的根节点），
    /// 而 `PlayerCombat` / `PlayerMage` 挂在 `Player` 根节点上 —— 两者是父子关系。
    /// 所以动画事件里直接写 `PlayerCombat` 的方法名**永远不会被调用**，
    /// 而且不会报错（SendMessage 找不到接收者时是静默的）。
    ///
    /// 这个组件就挂在 Animator 所在的那个物体上，把事件转发给父级的 PlayerCombat。
    ///
    /// 目前转发的事件：
    ///   OnSlashImpact —— 剑的四段连招剪辑 `Attack_1..4.anim` **各在 0.200 秒**触发一次
    ///   （四段实测都是 0.200s，直接读 `.anim` 的 `m_Events` 可核）。
    ///
    ///   ⚠️ 这个时间**不是写死的**：`MageSetup.AddImpactEvent()` 在裁剪之后重新采样手臂链角速度、
    ///   取峰值帧打事件；`ComboLeadIn = 0.20f` 就是"命中帧落在裁剪后剪辑开头 0.2s 处"的成因。
    ///   改了 `ComboLeadIn` / `ComboClipLength`，这里的时间会跟着变 —— **一切以 `.anim` 里的
    ///   `m_Events` 为准，不要信注释里的数字**。
    ///
    ///   （订正：本文原先写"`Attack_Slash.anim` 第 0.433 秒（第 13 帧）"—— 那个单段资产
    ///   已被 `Attack_1..4` 取代并删除，照它去翻文件只会浪费一次排查。）
    /// </summary>
    [DisallowMultipleComponent]
    public class AnimEventRelay : MonoBehaviour
    {
        private PlayerCombat combat;

        private void Awake()
        {
            combat = GetComponentInParent<PlayerCombat>();
        }

        /// <summary>挥砍命中帧。伤害判定和斩击特效都在这里发生，不再跟着按键那一帧走。</summary>
        public void OnSlashImpact()
        {
            // 惰性补引用：这个组件可能是预制体实例上的，Awake 时机不保证
            if (combat == null) combat = GetComponentInParent<PlayerCombat>();
            if (combat != null) combat.OnSlashImpact();
        }
    }
}
