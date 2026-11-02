using UnityEngine;

namespace MyWorld
{
    // ⚠️ 这个文件只放**接口、抽象基类和枚举**。
    //
    // 为什么把 4 个 MonoBehaviour 拆出去了（SpawnMarker / ScenePortal /
    // PickupInteractable / PlayerInteractor 各自一个同名文件）：
    // Unity 的 MonoScript 只能对应「文件名 == 类名」的那一个类型。一个 .cs 里挤多个
    // MonoBehaviour 时，除同名那一个以外都拿不到自己的 MonoScript，场景只能写
    // hash 式 `m_Script: {fileID: <哈希>}` 引用；hash 跨会话不稳定，重新加载后组件
    // 就变成 missing script。
    // 这不是理论：烘焙后的 `RoaTown.unity` 实际丢了 17 个组件 ——
    // 8 SpawnMarker 剩 3、6 PickupInteractable 剩 3、2 ScenePortal 剩 0、
    // 1 PlayerInteractor 剩 0（传送门不可用、按 E 无反应），
    // 而同场景 171 个 guid 式引用的组件（NpcActor / MerchantShop 等）全部正常绑定。
    // 别再往这个文件里加 MonoBehaviour。

    /// <summary>可交互对象：玩家靠近时显示提示，按 E 触发。</summary>
    public interface IInteractable
    {
        string InteractionPrompt { get; }
        bool CanInteract { get; }
        void Interact(GameObject interactor);
    }

    public abstract class InteractableBase : MonoBehaviour, IInteractable
    {
        [SerializeField] protected string prompt = "交互";

        public virtual string InteractionPrompt => prompt;
        public virtual bool CanInteract => isActiveAndEnabled;

        public abstract void Interact(GameObject interactor);
    }

    public enum PickupKind
    {
        Herb = 0,
        Coin = 1,
        Crystal = 2,
    }
}
