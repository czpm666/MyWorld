using UnityEngine;
using UnityEngine.UI;

namespace MyWorld.UI
{
    /// <summary>
    /// 简单的 hover 变色反馈：鼠标移入/移出时把 Graphic 的颜色在 normal / hover 之间切换。
    ///
    /// 单独成文件是因为 Unity 对 MonoBehaviour 有"类名=文件名"的序列化约定；
    /// 虽然运行期 AddComponent 不严格要求，但独立文件更稳、也方便以后挂到预制体上。
    /// </summary>
    public sealed class HoverTint : MonoBehaviour,
        UnityEngine.EventSystems.IPointerEnterHandler,
        UnityEngine.EventSystems.IPointerExitHandler
    {
        private Graphic graphic;
        private Color normal;
        private Color hover;

        public void Init(Graphic target, Color normalColor, Color hoverColor)
        {
            graphic = target;
            normal = normalColor;
            hover = hoverColor;
            if (graphic != null) graphic.color = normal;
        }

        public void OnPointerEnter(UnityEngine.EventSystems.PointerEventData eventData)
        {
            if (graphic != null) graphic.color = hover;
        }

        public void OnPointerExit(UnityEngine.EventSystems.PointerEventData eventData)
        {
            if (graphic != null) graphic.color = normal;
        }
    }
}
