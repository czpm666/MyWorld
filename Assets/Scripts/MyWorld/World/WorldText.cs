using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 世界空间文字（招牌、路牌、NPC 名字、传送门目的地）。
    /// 字体优先系统中文（雅黑/黑体），没有就回退 Unity 内置 LegacyRuntime —— 绝不留方块字。
    /// </summary>
    public static class WorldText
    {
        static Font font;

        public static Font GetFont()
        {
            if (font != null) return font;
            try
            {
                font = Font.CreateDynamicFontFromOSFont(new[] { "Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "SimSun", "Arial" }, 64);
            }
            catch (System.Exception)
            {
                font = null;
            }
            if (font == null) font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            if (font == null) font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            return font;
        }

        /// <summary>
        /// 建一段世界文字。size = 字高（米），maxWidth &gt; 0 时自动换行。
        /// 返回的 GameObject 没碰撞体，纯装饰。
        /// </summary>
        public static TextMesh Create(Transform parent, string text, Vector3 pos, float size = 0.3f,
            Color? color = null, float yaw = 0f, float maxWidth = 0f)
        {
            var go = new GameObject("Text_" + Trim(text, 12));
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localRotation = Quaternion.Euler(0f, yaw, 0f);

            var tm = go.AddComponent<TextMesh>();
            tm.font = GetFont();
            tm.fontSize = 64;
            tm.characterSize = 0.1f * size;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            tm.color = color ?? new Color(0.18f, 0.12f, 0.08f);
            tm.text = text;
            if (maxWidth > 0f)
            {
                var mr = go.GetComponent<MeshRenderer>();
                if (mr != null && tm.font != null)
                {
                    // TextMesh 自身没有自动换行宽度，靠字符数估算：中文 1 字 ≈ 1 个 size，英文 ≈ 0.55
                    int perLine = Mathf.Max(2, Mathf.FloorToInt(maxWidth / Mathf.Max(0.01f, size * 0.9f)));
                    tm.text = Wrap(text, perLine);
                }
            }
            return tm;
        }

        static string Wrap(string text, int perLine)
        {
            if (string.IsNullOrEmpty(text)) return text;
            var sb = new System.Text.StringBuilder(text.Length + text.Length / Mathf.Max(1, perLine));
            int count = 0;
            for (int i = 0; i < text.Length; i++)
            {
                char c = text[i];
                if (c == '\n') { sb.Append(c); count = 0; continue; }
                sb.Append(c);
                count++;
                if (count >= perLine && i + 1 < text.Length)
                {
                    sb.Append('\n');
                    count = 0;
                }
            }
            return sb.ToString();
        }

        static string Trim(string s, int n)
        {
            if (string.IsNullOrEmpty(s)) return "label";
            return s.Length <= n ? s : s.Substring(0, n);
        }
    }
}
