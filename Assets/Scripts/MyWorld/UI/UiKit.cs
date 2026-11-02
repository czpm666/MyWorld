using UnityEngine;
using UnityEngine.UI;

namespace MyWorld.UI
{
    /// <summary>
    /// uGUI 控件小工厂：把"建节点 / 铺九宫格 / 写字 / 做按钮 / 加装饰"这些样板代码收在一处。
    ///
    /// 约定：
    /// * 坐标默认以**左上角**为原点（<see cref="Place"/>：x 向右、y 向下），符合 UI 直觉；
    /// * 所有文字默认 raycastTarget=false、支持富文本（&lt;color&gt; 标色用）；
    /// * 字体默认 <see cref="UiSkin.Body"/>（微软雅黑链），标题用 <see cref="UiSkin.Title"/>；
    /// * 面板 Sprite 一律 Sliced（九宫格），所以不同尺寸下金边粗细一致。
    /// </summary>
    public static class UiKit
    {
        // ---------------- 节点 / 布局 ----------------

        /// <summary>新建一个只有 RectTransform 的空节点。</summary>
        public static RectTransform Node(string name, Transform parent)
        {
            var go = new GameObject(name, typeof(RectTransform));
            var rt = (RectTransform)go.transform;
            rt.SetParent(parent, false);
            rt.localScale = Vector3.one;
            rt.localRotation = Quaternion.identity;
            return rt;
        }

        /// <summary>铺满父节点（可留边距）。</summary>
        public static RectTransform Stretch(Transform parent, string name, float left = 0f, float top = 0f, float right = 0f, float bottom = 0f)
        {
            var rt = Node(name, parent);
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.offsetMin = new Vector2(left, bottom);
            rt.offsetMax = new Vector2(-right, -top);
            return rt;
        }

        /// <summary>屏幕空间定位：以父节点左上角为原点，x 向右、y 向下。pivot 默认 (0,1)。</summary>
        public static RectTransform Place(Transform parent, string name, float x, float y, float w, float h)
        {
            var rt = Node(name, parent);
            rt.anchorMin = new Vector2(0f, 1f);
            rt.anchorMax = new Vector2(0f, 1f);
            rt.pivot = new Vector2(0f, 1f);
            rt.sizeDelta = new Vector2(w, h);
            rt.anchoredPosition = new Vector2(x, -y);
            return rt;
        }

        /// <summary>屏幕空间定位，但锚在父节点右上角（x 向右为负方向）。</summary>
        public static RectTransform PlaceRight(Transform parent, string name, float right, float y, float w, float h)
        {
            var rt = Node(name, parent);
            rt.anchorMin = new Vector2(1f, 1f);
            rt.anchorMax = new Vector2(1f, 1f);
            rt.pivot = new Vector2(1f, 1f);
            rt.sizeDelta = new Vector2(w, h);
            rt.anchoredPosition = new Vector2(right, -y);
            return rt;
        }

        /// <summary>以父节点中心定位（pivot 居中）。</summary>
        public static RectTransform Center(Transform parent, string name, float x, float y, float w, float h)
        {
            var rt = Node(name, parent);
            rt.anchorMin = new Vector2(0.5f, 0.5f);
            rt.anchorMax = new Vector2(0.5f, 0.5f);
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = new Vector2(w, h);
            rt.anchoredPosition = new Vector2(x, y);
            return rt;
        }

        /// <summary>底部居中定位（pivot 下中，y 向上偏移）。</summary>
        public static RectTransform BottomCenter(Transform parent, string name, float y, float w, float h)
        {
            var rt = Node(name, parent);
            rt.anchorMin = new Vector2(0.5f, 0f);
            rt.anchorMax = new Vector2(0.5f, 0f);
            rt.pivot = new Vector2(0.5f, 0f);
            rt.sizeDelta = new Vector2(w, h);
            rt.anchoredPosition = new Vector2(0f, y);
            return rt;
        }

        /// <summary>清空子节点（用于页签重建）。</summary>
        public static void ClearChildren(Transform parent)
        {
            for (int i = parent.childCount - 1; i >= 0; i--)
                Object.Destroy(parent.GetChild(i).gameObject);
        }

        // ---------------- 图片 / 面板 ----------------

        /// <summary>九宫格面板（默认羊皮纸）。</summary>
        public static Image Panel(Transform parent, string name, Sprite sprite, Color color,
            float x, float y, float w, float h)
        {
            var rt = Place(parent, name, x, y, w, h);
            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = sprite;
            img.color = color;
            img.type = Image.Type.Sliced;
            img.raycastTarget = false;
            return img;
        }

        /// <summary>九宫格面板，锚在父节点右上角（right 为右边缘距离，通常传负数）。</summary>
        public static Image PanelRight(Transform parent, string name, Sprite sprite, Color color,
            float right, float y, float w, float h)
        {
            var rt = PlaceRight(parent, name, right, y, w, h);
            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = sprite;
            img.color = color;
            img.type = Image.Type.Sliced;
            img.raycastTarget = false;
            return img;
        }

        /// <summary>铺满父节点的九宫格面板（可留边距）。</summary>
        public static Image PanelFill(Transform parent, string name, Sprite sprite, Color color,
            float left = 0f, float top = 0f, float right = 0f, float bottom = 0f)
        {
            var rt = Stretch(parent, name, left, top, right, bottom);
            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = sprite;
            img.color = color;
            img.type = Image.Type.Sliced;
            img.raycastTarget = false;
            return img;
        }

        /// <summary>普通图片（不切片）。</summary>
        public static Image Icon(Transform parent, string name, Sprite sprite, float x, float y, float w, float h)
        {
            var rt = Place(parent, name, x, y, w, h);
            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = sprite;
            img.type = Image.Type.Simple;
            img.preserveAspect = true;
            img.raycastTarget = false;
            return img;
        }

        /// <summary>铺满父节点的普通图片。</summary>
        public static Image IconFill(Transform parent, string name, Sprite sprite)
        {
            var rt = Stretch(parent, name);
            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = sprite;
            img.type = Image.Type.Simple;
            img.preserveAspect = true;
            img.raycastTarget = false;
            return img;
        }

        // ---------------- 文字 ----------------

        /// <summary>正文文字（微软雅黑），默认左对齐、不拦截点击。</summary>
        public static Text Label(Transform parent, string name, string content, int size, Color color,
            float x, float y, float w, float h, TextAnchor anchor = TextAnchor.MiddleLeft)
        {
            var rt = Place(parent, name, x, y, w, h);
            return FillText(rt, content, size, color, anchor, UiSkin.Body, false);
        }

        /// <summary>铺满父节点的正文文字。</summary>
        public static Text LabelFill(Transform parent, string name, string content, int size, Color color,
            TextAnchor anchor = TextAnchor.MiddleLeft)
        {
            var rt = Stretch(parent, name);
            return FillText(rt, content, size, color, anchor, UiSkin.Body, false);
        }

        /// <summary>标题文字（楷体，失败回退正文字体）。</summary>
        public static Text Title(Transform parent, string name, string content, int size, Color color,
            float x, float y, float w, float h, TextAnchor anchor = TextAnchor.MiddleCenter)
        {
            var rt = Place(parent, name, x, y, w, h);
            return FillText(rt, content, size, color, anchor, UiSkin.Title, true);
        }

        /// <summary>给已有 RectTransform 填一个 Text（不额外挪位置）。</summary>
        public static Text FillText(RectTransform rt, string content, int size, Color color,
            TextAnchor anchor, Font font, bool bold = false)
        {
            var text = rt.gameObject.AddComponent<Text>();
            text.text = content;
            text.font = font != null ? font : UiSkin.Body;
            text.fontSize = size;
            text.color = color;
            text.alignment = anchor;
            text.supportRichText = true;
            text.raycastTarget = false;
            text.horizontalOverflow = HorizontalWrapMode.Wrap;
            text.verticalOverflow = VerticalWrapMode.Overflow;
            if (bold) text.fontStyle = FontStyle.Bold;
            return text;
        }

        /// <summary>加一层 1px 阴影，让浅色字压在花纹底上也能看清。</summary>
        public static Text WithShadow(this Text text, float alpha = 0.65f)
        {
            if (text == null) return text;
            var shadow = text.gameObject.AddComponent<Shadow>();
            shadow.effectColor = new Color(0f, 0f, 0f, alpha);
            shadow.effectDistance = new Vector2(1.2f, -1.2f);
            shadow.useGraphicAlpha = true;
            return text;
        }

        // ---------------- 按钮 ----------------

        /// <summary>文字按钮。gold=true 用金底（当前页签 / 主行动）。</summary>
        public static Button TextButton(Transform parent, string name, string label, float x, float y, float w, float h,
            System.Action onClick, bool gold = false, int fontSize = 22)
        {
            var rt = Place(parent, name, x, y, w, h);
            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = gold ? UiSkin.ButtonGold : UiSkin.Button;
            img.type = Image.Type.Sliced;
            img.raycastTarget = true;

            var btn = rt.gameObject.AddComponent<Button>();
            btn.targetGraphic = img;
            btn.transition = Selectable.Transition.ColorTint;
            var colors = btn.colors;
            colors.normalColor = Color.white;
            colors.highlightedColor = new Color(1.06f, 1.06f, 1.06f, 1f);
            colors.pressedColor = new Color(0.82f, 0.82f, 0.82f, 1f);
            colors.selectedColor = Color.white;
            colors.disabledColor = new Color(0.55f, 0.55f, 0.55f, 0.7f);
            colors.fadeDuration = 0.08f;
            btn.colors = colors;
            if (onClick != null) btn.onClick.AddListener(() => onClick());

            var textRt = Stretch(rt, "Label", 8f, 2f, 8f, 2f);
            var text = FillText(textRt, label, fontSize, gold ? UiSkin.TextDark : UiSkin.TextDark,
                TextAnchor.MiddleCenter, UiSkin.Body, true);
            text.horizontalOverflow = HorizontalWrapMode.Wrap;
            return btn;
        }

        /// <summary>把任意面板变成可点击按钮（用面板自己的图形做 target，不加文字）。</summary>
        public static Button Clickable(Component target, System.Action onClick, bool tint = true)
        {
            var graphic = target.GetComponent<Graphic>();
            var btn = target.gameObject.AddComponent<Button>();
            btn.targetGraphic = graphic;
            if (tint)
            {
                btn.transition = Selectable.Transition.ColorTint;
                var colors = btn.colors;
                colors.normalColor = Color.white;
                colors.highlightedColor = new Color(1.08f, 1.06f, 0.98f, 1f);
                colors.pressedColor = new Color(0.86f, 0.86f, 0.86f, 1f);
                colors.fadeDuration = 0.08f;
                btn.colors = colors;
            }
            else
            {
                btn.transition = Selectable.Transition.None;
            }
            if (onClick != null) btn.onClick.AddListener(() => onClick());
            return btn;
        }

        // ---------------- 装饰 ----------------

        /// <summary>金色分隔线（宽度自适应，两端带小菱形）。</summary>
        public static Image Divider(Transform parent, string name, float x, float y, float w)
        {
            var rt = Place(parent, name, x, y, w, 14f);
            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = UiSkin.Divider;
            img.type = Image.Type.Sliced;
            img.raycastTarget = false;
            return img;
        }

        /// <summary>在面板四角加卷草纹（旋转复用同一张 Sprite）。</summary>
        public static void Corners(Transform parent, float inset = 10f, float size = 44f)
        {
            AddCorner(parent, "CornerBL", 0f, 0f, 0f, inset, size);
            AddCorner(parent, "CornerBR", 1f, 0f, 90f, inset, size);
            AddCorner(parent, "CornerTR", 1f, 1f, 180f, inset, size);
            AddCorner(parent, "CornerTL", 0f, 1f, 270f, inset, size);
        }

        /// <summary>角饰 Sprite 是"左下方向展开"画的，所以按角落给旋转角。</summary>
        private static void AddCorner(Transform parent, string name, float anchorX, float anchorY, float rot, float inset, float size)
        {
            var rt = Node(name, parent);
            rt.anchorMin = new Vector2(anchorX, anchorY);
            rt.anchorMax = new Vector2(anchorX, anchorY);
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = new Vector2(size, size);
            float signX = anchorX > 0.5f ? -1f : 1f;
            float signY = anchorY > 0.5f ? -1f : 1f;
            rt.anchoredPosition = new Vector2(signX * (inset + size * 0.5f), signY * (inset + size * 0.5f));

            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = UiSkin.Ornament;
            img.type = Image.Type.Simple;
            img.preserveAspect = true;
            img.raycastTarget = false;
            img.color = new Color(1f, 1f, 1f, 0.95f);
            rt.localEulerAngles = new Vector3(0f, 0f, rot);
        }

        /// <summary>给窗口类面板加"羊皮纸底 + 四角金饰"。</summary>
        public static Image WindowPanel(Transform parent, string name, float x, float y, float w, float h)
        {
            var img = Panel(parent, name, UiSkin.Window, Color.white, x, y, w, h);
            Corners(img.transform, 14f, 52f);
            return img;
        }

        // ---------------- 交互反馈 ----------------

        /// <summary>鼠标悬停时轻微提亮（给卡片用；Button 组件已自带 tint，这个用于非按钮元素的手动效果）。</summary>
        public static void AddHoverTint(Graphic graphic, Color normal, Color hover)
        {
            var relay = graphic.gameObject.AddComponent<HoverTint>();
            relay.Init(graphic, normal, hover);
        }
    }
}
