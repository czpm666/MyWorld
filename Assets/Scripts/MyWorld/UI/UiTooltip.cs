using UnityEngine;
using UnityEngine.InputSystem;

namespace MyWorld.UI
{
    /// <summary>
    /// 悬停说明浮层（tooltip）：悬停 <see cref="ShowDelay"/> 秒后弹出，移出立刻消失，展开期间跟随鼠标。
    ///
    /// 设计约定（都是这套 uGUI 代码里踩过的坑）：
    /// * 节点**常驻激活**，靠 CanvasGroup.alpha 显隐 —— 一旦 SetActive(false) 就收不到 Update，计时会停死；
    /// * 内容由调用方在 <see cref="Request"/> 里用 UiKit 铺，本类只管"计时 + 跟随 + 贴边翻转"；
    /// * 子图形一律 raycastTarget=false（UiKit 默认就是），鼠标不会被浮层吃掉，
    ///   卡片也就不会收到假的 OnPointerExit —— 否则浮层会自己把自己闪没；
    /// * host 约定为左上角原点、pivot (0,1)（即 UiKit.Place 的坐标系），
    ///   优先出现在光标右下方，贴到内容区边缘时自动翻到左侧 / 上方并夹回区内。
    /// </summary>
    public sealed class UiTooltip : MonoBehaviour
    {
        /// <summary>悬停多久才弹出（秒，不受 timeScale 影响）。</summary>
        public const float ShowDelay = 0.4f;

        private const float CursorOffsetX = 22f;
        private const float CursorOffsetY = 24f;
        private const float EdgePadding = 8f;

        private RectTransform host;
        private RectTransform root;
        private CanvasGroup group;
        private System.Action<RectTransform> builder;
        private float timer;
        private bool pending;
        private bool shown;

        /// <summary>在 host 里建一个空浮层节点（内容留到 Request 时再铺）。</summary>
        public static UiTooltip Create(RectTransform host, string name)
        {
            var rt = UiKit.Node(name, host);
            rt.anchorMin = new Vector2(0f, 1f);
            rt.anchorMax = new Vector2(0f, 1f);
            rt.pivot = new Vector2(0f, 1f);
            rt.sizeDelta = new Vector2(320f, 120f);

            var tip = rt.gameObject.AddComponent<UiTooltip>();
            tip.host = host;
            tip.root = rt;
            tip.group = rt.gameObject.AddComponent<CanvasGroup>();
            tip.group.alpha = 0f;
            tip.group.interactable = false;
            tip.group.blocksRaycasts = false;
            return tip;
        }

        /// <summary>请求显示（每次都重新计时）。build 里负责铺内容并设置 root 的 sizeDelta。</summary>
        public void Request(System.Action<RectTransform> build)
        {
            builder = build;
            pending = build != null;
            timer = 0f;
            if (shown) Hide();   // 换目标时先收回，重新等 0.4s
        }

        /// <summary>移出即消失。</summary>
        public void Dismiss()
        {
            builder = null;
            pending = false;
            timer = 0f;
            Hide();
        }

        private void Hide()
        {
            shown = false;
            if (group != null) group.alpha = 0f;
        }

        private void Update()
        {
            if (pending)
            {
                timer += Time.unscaledDeltaTime;
                if (timer >= ShowDelay)
                {
                    pending = false;
                    Show();
                }
            }

            if (shown) Follow();
        }

        private void Show()
        {
            if (builder == null || root == null) return;

            UiKit.ClearChildren(root);   // 上次的内容还挂在节点上（只是 alpha=0），先清掉
            builder(root);
            builder = null;

            shown = true;
            if (group != null) group.alpha = 1f;
            Follow();
        }

        private void Follow()
        {
            if (root == null || host == null) return;

            Vector2 local;
            if (!RectTransformUtility.ScreenPointToLocalPointInRectangle(host, PointerScreenPosition(), null, out local))
                return;

            Vector2 size = root.sizeDelta;
            float hostW = host.rect.width;
            float hostH = host.rect.height;

            // host 的局部坐标：原点在左上角，x 向右、y 向上（所以 y 是负的）
            float x = local.x + CursorOffsetX;
            float y = local.y - CursorOffsetY;

            if (x + size.x > hostW - EdgePadding) x = local.x - CursorOffsetX - size.x;   // 右边放不下 → 翻到左侧
            x = Mathf.Clamp(x, EdgePadding, Mathf.Max(EdgePadding, hostW - size.x - EdgePadding));

            if (y - size.y < -(hostH - EdgePadding)) y = local.y + CursorOffsetY + size.y;   // 下边放不下 → 翻到上方
            float minY = -(hostH - EdgePadding) + size.y;
            float maxY = -EdgePadding;
            y = Mathf.Clamp(y, Mathf.Min(minY, maxY), maxY);

            root.anchoredPosition = new Vector2(x, y);
        }

        /// <summary>指针屏幕坐标（新输入系统；不碰 UnityEngine.Input，避免旧输入被禁用时抛异常）。</summary>
        private static Vector2 PointerScreenPosition()
        {
            var mouse = Mouse.current;
            if (mouse != null) return mouse.position.ReadValue();

            var pointer = Pointer.current;
            if (pointer != null) return pointer.position.ReadValue();

            return Vector2.zero;
        }
    }
}
