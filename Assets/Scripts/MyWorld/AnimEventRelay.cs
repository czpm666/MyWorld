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
        private bool warnedMissingCombat;

        private void Awake()
        {
            combat = GetComponentInParent<PlayerCombat>();
        }

        /// <summary>挥砍命中帧。伤害判定和斩击特效都在这里发生，不再跟着按键那一帧走。</summary>
        public void OnSlashImpact()
        {
            if (!Resolve()) return;
            combat.OnSlashImpact();
        }

        /// <summary>
        /// 弓箭离弦帧（T-050）。**箭矢在这里才生成** —— 起手只记录 `pendingShot`，
        /// 于是"动画还在抬弓、箭已经飞出去"这个不同步被结构性消除。
        /// </summary>
        public void OnArrowRelease()
        {
            if (!Resolve()) return;
            combat.OnArrowRelease();
        }

        /// <summary>
        /// 惰性补引用。**找不到时只警告一次，不再静默**（T-050 要求）：
        /// 动画事件以 `SendMessageOptions.DontRequireReceiver` 派发，**接收者不存在时 Unity 一声不吭**。
        /// 所以 relay 挂错物体、或 PlayerCombat 不在父链上，表现就是"动作播了但什么都不发生"，
        /// 排查时毫无线索。这里至少留一行。
        /// </summary>
        private bool Resolve()
        {
            if (combat == null) combat = GetComponentInParent<PlayerCombat>();
            if (combat != null) return true;

            if (!warnedMissingCombat)
            {
                warnedMissingCombat = true;
                Debug.LogWarning("[My World] AnimEventRelay 收到动画事件，却在父链上找不到 PlayerCombat —— "
                                 + "事件会被丢弃且不会有别的提示。请检查 relay 是否挂在 Animator 所在物体上、"
                                 + "以及 PlayerCombat 是否位于它的某个父级。");
            }
            return false;
        }
    }
}
