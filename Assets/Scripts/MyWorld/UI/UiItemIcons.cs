using System.Collections.Generic;
using UnityEngine;

namespace MyWorld.UI
{
    /// <summary>
    /// 消耗品 / 背包物品图标：同样"程序化画，绝不空白"。
    ///
    /// 商店/背包里的物品 id 来自 ShopCatalog（potion_small / potion_large / potion_elixir / bread / mana_ink）；
    /// 契约只要求武器图标走 UiIconLibrary，物品图标扩展在这里，互不干扰。
    /// </summary>
    public static class UiItemIcons
    {
        private static readonly Dictionary<string, Sprite> cache = new Dictionary<string, Sprite>();

        private static readonly Color Outline = UiColor.Hex("#1b120c");
        private static readonly Color Glass = UiColor.Hex("#cfe0e8");
        private static readonly Color GlassDark = UiColor.Hex("#8fa6b2");
        private static readonly Color Cork = UiColor.Hex("#a9793f");
        private static readonly Color CorkDark = UiColor.Hex("#6f4a22");
        private static readonly Color RedPotion = UiColor.Hex("#c0392b");
        private static readonly Color GoldPotion = UiColor.Hex("#e8c24a");
        private static readonly Color InkBlue = UiColor.Hex("#2c4a7a");
        private static readonly Color BreadCrust = UiColor.Hex("#a5702f");
        private static readonly Color BreadLight = UiColor.Hex("#d9a860");

        public static readonly string[] KnownIds =
        {
            "potion_small", "potion_large", "potion_elixir", "bread", "mana_ink",
        };

        /// <summary>按物品 id 取图标；未知 id 画一个皮袋（提示"这是个物品"）。</summary>
        public static Sprite Load(string itemId)
        {
            if (string.IsNullOrEmpty(itemId)) itemId = "unknown";

            Sprite cached;
            if (cache.TryGetValue(itemId, out cached) && cached != null) return cached;

            var c = new UiCanvas(128, 128, new Color(0f, 0f, 0f, 0f));
            switch (itemId)
            {
                case "potion_small": DrawFlask(c, 0.82f, RedPotion, RedPotion.Shade(0.55f)); break;
                case "potion_large": DrawFlask(c, 1f, RedPotion, RedPotion.Shade(0.55f)); break;
                case "potion_elixir": DrawFlask(c, 1f, GoldPotion, GoldPotion.Shade(0.45f), true); break;
                case "bread": DrawBread(c); break;
                case "mana_ink": DrawInkBottle(c); break;
                default: DrawPouch(c); break;
            }

            var sprite = c.BakeSprite(Vector4.zero);
            sprite.name = "UiItem_" + itemId;
            cache[itemId] = sprite;
            return sprite;
        }

        // ---- 药水瓶：玻璃瓶 + 彩色药液 + 软木塞 ----
        private static void DrawFlask(UiCanvas c, float scale, Color liquid, Color liquidDark, bool ornate = false)
        {
            float cx = 64f;
            float neckW = 20f * scale;
            float bodyW = 58f * scale;
            float bodyH = 56f * scale;
            float bodyY = 18f;
            float neckY = bodyY + bodyH - 6f * scale;
            float neckH = 20f * scale;

            // 瓶身
            c.RoundRect(cx - bodyW * 0.5f - 3f, bodyY - 3f, bodyW + 6f, bodyH + 6f, 18f * scale, Outline);
            c.RoundRect(cx - bodyW * 0.5f, bodyY, bodyW, bodyH, 16f * scale, Glass.Alpha(0.75f), GlassDark.Alpha(0.85f));

            // 药液（下半瓶）+ 液面
            c.RoundRect(cx - bodyW * 0.5f + 4f, bodyY + 3f, bodyW - 8f, bodyH * 0.55f, 13f * scale,
                liquid.Alpha(0.92f), liquidDark.Alpha(0.95f));
            c.Rect(cx - bodyW * 0.5f + 7f, bodyY + bodyH * 0.55f + 2f, bodyW - 14f, 2.2f, liquid.Shade(1.25f).Alpha(0.9f));

            // 瓶颈
            c.Rect(cx - neckW * 0.5f - 2.5f, neckY - 4f, neckW + 5f, neckH + 4f, Outline);
            c.Rect(cx - neckW * 0.5f, neckY, neckW, neckH, Glass.Alpha(0.8f));
            c.Rect(cx - neckW * 0.5f + 2f, neckY, 3f, neckH, Color.white.Alpha(0.45f));

            // 软木塞
            c.RoundRect(cx - neckW * 0.5f - 3f, neckY + neckH - 2f, neckW + 6f, 13f, 3f, Outline);
            c.RoundRect(cx - neckW * 0.5f - 1f, neckY + neckH, neckW + 2f, 9f, 2.5f, Cork, CorkDark);

            // 玻璃高光
            c.Rect(cx - bodyW * 0.5f + 6f, bodyY + bodyH * 0.5f, 3f, bodyH * 0.32f, Color.white.Alpha(0.55f));
            c.Circle(cx + bodyW * 0.22f, bodyY + bodyH * 0.62f, 3.2f, Color.white.Alpha(0.4f));

            if (ornate)
            {
                // 高等药：金色束带 + 辉光
                c.Circle(cx, bodyY + bodyH * 0.4f, 34f, liquid.Alpha(0.14f));
                c.Rect(cx - bodyW * 0.5f + 2f, bodyY + bodyH * 0.42f, bodyW - 4f, 4f, UiSkin.Gold);
                c.Rect(cx - bodyW * 0.5f + 2f, bodyY + bodyH * 0.42f, bodyW - 4f, 1.4f, UiSkin.GoldLight);
                c.Circle(cx, bodyY + bodyH * 0.5f, 4.6f, UiSkin.GoldDark);
                c.Circle(cx, bodyY + bodyH * 0.5f, 3.4f, UiSkin.Gold);
            }
        }

        // ---- 黑麦面包：椭圆面包 + 三道割口 ----
        private static void DrawBread(UiCanvas c)
        {
            c.Ellipse(64f, 58f, 44f, 26f, 14f, Outline);
            c.Ellipse(64f, 58f, 40f, 22f, 12f, BreadLight, BreadCrust);

            for (int i = 0; i < 3; i++)
            {
                float x = 44f + i * 20f;
                c.Line(new Vector2(x, 44f), new Vector2(x + 9f, 58f), 3.2f, BreadCrust.Shade(0.7f).Alpha(0.9f));
                c.Line(new Vector2(x, 45f), new Vector2(x + 8f, 58f), 1.4f, BreadLight.Shade(1.1f).Alpha(0.9f));
            }

            // 底部阴影 + 顶部高光
            c.Ellipse(64f, 40f, 34f, 8f, 6f, BreadCrust.Shade(0.6f).Alpha(0.45f));
            c.Ellipse(54f, 68f, 14f, 5f, 4f, Color.white.Alpha(0.25f));
        }

        // ---- 魔法墨水：墨水瓶 + 羽毛笔 ----
        private static void DrawInkBottle(UiCanvas c)
        {
            // 瓶身
            c.RoundRect(38f, 20f, 52f, 50f, 10f, Outline);
            c.RoundRect(41f, 23f, 46f, 44f, 8f, UiColor.Hex("#5f7a9a"), UiColor.Hex("#33465f"));
            // 液面
            c.Rect(44f, 50f, 40f, 3f, UiColor.Hex("#8fb4d8").Alpha(0.7f));
            // 瓶口
            c.Rect(50f, 66f, 28f, 10f, Outline);
            c.Rect(52f, 67f, 24f, 7f, UiColor.Hex("#8b6a3c"));
            // 标签
            c.Rect(48f, 32f, 32f, 14f, UiSkin.ParchmentLight);
            c.Rect(48f, 32f, 32f, 2f, UiSkin.Ink.Alpha(0.35f));
            c.Line(new Vector2(52f, 38f), new Vector2(76f, 38f), 1.4f, UiSkin.Ink.Alpha(0.6f));

            // 羽毛笔（右侧斜插）
            Vector2 tip = new Vector2(74f, 70f);
            Vector2 top = new Vector2(104f, 118f);
            c.Line(tip, top, 6.5f, Outline);
            c.Line(tip, top, 3f, UiColor.Hex("#e6ddc4"));
            c.Polygon(Outline, top, new Vector2(96f, 106f), new Vector2(112f, 104f));
            c.Polygon(UiColor.Hex("#f3ecd8"), top, new Vector2(99f, 106.5f), new Vector2(110f, 105f));
            c.Line(new Vector2(76f, 80f), new Vector2(88f, 98f), 1.4f, UiColor.Hex("#a89a78").Alpha(0.8f));

            // 高光
            c.Rect(45f, 28f, 3f, 28f, Color.white.Alpha(0.3f));
        }

        // ---- 未知物品：皮袋 ----
        private static void DrawPouch(UiCanvas c)
        {
            c.Circle(64f, 56f, 38f, Outline);
            c.Circle(64f, 56f, 34f, UiSkin.ParchmentDark, UiSkin.InkSoft);
            c.Rect(54f, 86f, 20f, 14f, Outline);
            c.Rect(56f, 87f, 16f, 11f, UiSkin.GoldDark);
            c.Line(new Vector2(56f, 88f), new Vector2(72f, 88f), 2.2f, UiSkin.Gold);
            c.Rect(46f, 52f, 3f, 22f, Color.white.Alpha(0.22f));
            c.Circle(64f, 44f, 3f, UiSkin.Gold.Alpha(0.9f));
        }
    }
}
