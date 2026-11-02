using UnityEngine;
using UnityEngine.EventSystems;

namespace MyWorld.UI
{
    /// <summary>
    /// 点击 / 悬停 / 拖拽 回调转发器。
    ///
    /// 为什么不用 Button：装备卡片需要区分**左键（装备）/ 右键（副手快速装备）**，
    /// 而 uGUI 的 Button 只给 onClick、拿不到鼠标键；这里直接实现 IPointerClickHandler，
    /// 从 PointerEventData.button 判断左右键。
    ///
    /// 拖拽（T-1xx）：卡片当拖出方（IBeginDragHandler/IDragHandler/IEndDragHandler），
    /// 装备槽当落点（IDropHandler）。uGUI 会在松手时把 OnDrop 派发给指针下面的对象，
    /// 所以槽位只要实现 IDropHandler 就能收到；拖出方也可以完全不用管落点是谁。
    /// </summary>
    public sealed class ClickRelay : MonoBehaviour,
        IPointerClickHandler, IPointerEnterHandler, IPointerExitHandler,
        IPointerDownHandler, IPointerUpHandler,
        IBeginDragHandler, IDragHandler, IEndDragHandler, IDropHandler
    {
        /// <summary>排查用开关：打开后每次指针事件都会往 Console 打一行。交付前保持 false。</summary>
        public static bool DebugLog = false;

        public System.Action<PointerEventData> onClick;
        public System.Action<PointerEventData> onEnter;
        public System.Action<PointerEventData> onExit;
        public System.Action<PointerEventData> onPointerDown;
        public System.Action<PointerEventData> onPointerUp;

        // ---- 拖拽 ----
        public System.Action<PointerEventData> onBeginDrag;
        public System.Action<PointerEventData> onDrag;
        public System.Action<PointerEventData> onEndDrag;
        public System.Action<PointerEventData> onDrop;

        private static void Log(string what, GameObject go, PointerEventData e)
        {
            if (!DebugLog) return;
            Debug.Log("[ClickRelay] " + what + " " + (go != null ? go.name : "?") +
                      " btn=" + (e != null ? e.button.ToString() : "-") +
                      " pos=" + (e != null ? e.position.ToString("F0") : "-") +
                      " drag=" + (e != null && e.pointerDrag != null ? e.pointerDrag.name : "-"));
        }

        public void OnPointerDown(PointerEventData eventData)
        {
            Log("down", gameObject, eventData);
            if (onPointerDown != null) onPointerDown(eventData);
        }

        public void OnPointerUp(PointerEventData eventData)
        {
            Log("up", gameObject, eventData);
            if (onPointerUp != null) onPointerUp(eventData);
        }

        public void OnPointerClick(PointerEventData eventData)
        {
            Log("click", gameObject, eventData);
            if (onClick != null) onClick(eventData);
        }

        public void OnPointerEnter(PointerEventData eventData)
        {
            if (onEnter != null) onEnter(eventData);
        }

        public void OnPointerExit(PointerEventData eventData)
        {
            if (onExit != null) onExit(eventData);
        }

        public void OnBeginDrag(PointerEventData eventData)
        {
            Log("beginDrag", gameObject, eventData);
            if (onBeginDrag != null) onBeginDrag(eventData);
        }

        public void OnDrag(PointerEventData eventData)
        {
            if (onDrag != null) onDrag(eventData);
        }

        public void OnEndDrag(PointerEventData eventData)
        {
            if (onEndDrag != null) onEndDrag(eventData);
        }

        public void OnDrop(PointerEventData eventData)
        {
            Log("drop", gameObject, eventData);
            if (onDrop != null) onDrop(eventData);
        }
    }

    /// <summary>
    /// 挂在"可拖拽的武器卡"上，让落点能在 OnDrop 里问出"拖的是哪把武器"。
    /// 用 `eventData.pointerDrag.GetComponent&lt;WeaponDragPayload&gt;()` 取，
    /// 比依赖静态字段可靠（uGUI 松手时 endDrag / drop 的派发顺序随版本而变）。
    /// </summary>
    public sealed class WeaponDragPayload : MonoBehaviour
    {
        public WeaponKind kind;
        public HandSlot slot;
        public string displayName;
    }
}
