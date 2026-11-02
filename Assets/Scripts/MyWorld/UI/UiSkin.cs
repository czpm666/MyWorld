using System.Collections.Generic;
using UnityEngine;

namespace MyWorld.UI
{
    /// <summary>
    /// 界面皮肤：中世纪羊皮纸 + 金边 + 墨棕 的**程序化**视觉基础。
    ///
    /// 全部 Sprite 在运行期用 <see cref="UiCanvas"/> 画出来（Texture2D → Sprite.Create + 九宫格 border），
    /// 不依赖任何外部美术素材 —— 这样风格统一、分辨率无损，且不会因为素材缺失出现空白块。
    ///
    /// 约定：
    /// * 面板类 Sprite 一律 **9-slice**（border 见各 Builder 注释），配合 Image.Type.Sliced 使用；
    /// * 生成对象随 Play 退出被销毁 → 所有缓存都走 <see cref="Lazy"/> 判空重建；
    /// * 字体优先系统微软雅黑（中文必须可读），标题优先楷体（中世纪书信感），失败回退 LegacyRuntime.ttf。
    /// </summary>
    public static class UiSkin
    {
        // ---------------- 配色（契约 §3 指定 + 派生） ----------------

        /// <summary>墨棕 —— 主要文字色 / 深底。</summary>
        public static readonly Color Ink = UiColor.Hex("#2b1d14");
        /// <summary>更深的墨（面板外圈、阴影）。</summary>
        public static readonly Color InkDeep = UiColor.Hex("#191009");
        /// <summary>偏暖的深棕（凹槽底）。</summary>
        public static readonly Color InkSoft = UiColor.Hex("#3a2a1c");
        /// <summary>羊皮纸主色。</summary>
        public static readonly Color Parchment = UiColor.Hex("#e8d5b0");
        public static readonly Color ParchmentLight = UiColor.Hex("#f3e6c8");
        public static readonly Color ParchmentDark = UiColor.Hex("#cdb489");
        /// <summary>金。</summary>
        public static readonly Color Gold = UiColor.Hex("#c9a227");
        public static readonly Color GoldLight = UiColor.Hex("#f0d060");
        public static readonly Color GoldDark = UiColor.Hex("#8a6a14");
        /// <summary>暗红（血、印章）。</summary>
        public static readonly Color Red = UiColor.Hex("#8f2b2b");
        public static readonly Color RedLight = UiColor.Hex("#c9463a");
        /// <summary>稀有蓝（契约指定）。</summary>
        public static readonly Color Blue = UiColor.Hex("#3f6fb5");
        public static readonly Color Green = UiColor.Hex("#4f8f4a");
        public static readonly Color Purple = UiColor.Hex("#7a4fa0");
        public static readonly Color Orange = UiColor.Hex("#c26a2a");

        public static readonly Color TextLight = UiColor.Hex("#f2e7cc");
        public static readonly Color TextDark = UiColor.Hex("#2b1d14");
        public static readonly Color TextMuted = UiColor.Hex("#b9a888");

        // ---------------- 字体 ----------------

        private static Font bodyFont;
        private static Font titleFont;

        /// <summary>正文字体：微软雅黑优先（中文完整），失败回退内置 LegacyRuntime。</summary>
        public static Font Body
        {
            get
            {
                if (bodyFont == null)
                    bodyFont = CreateFont(new[] { "Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "SimSun" }, 32);
                return bodyFont;
            }
        }

        /// <summary>标题字体：楷体优先（书信/古籍手写感），失败退回正文字体。</summary>
        public static Font Title
        {
            get
            {
                if (titleFont == null)
                {
                    titleFont = CreateFont(new[] { "STKaiti", "KaiTi", "楷体", "Microsoft YaHei UI", "Microsoft YaHei" }, 40);
                    if (titleFont == null) titleFont = Body;
                }
                return titleFont;
            }
        }

        private static Font CreateFont(string[] osNames, int size)
        {
            try
            {
                var f = Font.CreateDynamicFontFromOSFont(osNames, size);
                if (f != null) return f;
            }
            catch { /* 某些平台没有 OS 字体 API，走下面的内置回退 */ }
            try { return Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); }
            catch { return null; }
        }

        // ---------------- 懒加载缓存 ----------------
        // ⚠️ 这些是运行时对象：退出 Play 后 Unity 会销毁它们，所以每次访问都要判空重建，
        //    不能只在第一次赋值（否则第二次进 Play 会拿到已销毁的 Sprite，Image 显示空白）。

        private static Sprite white;
        private static Sprite window;
        private static Sprite parchment;
        private static Sprite card;
        private static Sprite slot;
        private static Sprite button;
        private static Sprite buttonGold;
        private static Sprite divider;
        private static Sprite diamond;
        private static Sprite ornament;
        private static Sprite heart;
        private static Sprite coin;
        private static Sprite scrollIcon;
        private static Sprite bagIcon;
        private static Sprite seal;
        private static Sprite barFill;
        private static Sprite heroCrest;

        private static readonly Dictionary<int, Sprite> frames = new Dictionary<int, Sprite>();

        /// <summary>1x1 纯白（做纯色块/遮罩用；9-slice 不适用）。</summary>
        public static Sprite White => Lazy(ref white, () =>
        {
            var c = new UiCanvas(4, 4, Color.white);
            return c.BakeSprite(Vector4.zero);
        });

        /// <summary>主窗口底：深墨木纹 + 双金边 + 四角卷草纹。9-slice border = 36。</summary>
        public static Sprite Window => Lazy(ref window, BuildWindow);

        /// <summary>羊皮纸内容板：墨线 + 金线 + 纸面。9-slice border = 28。</summary>
        public static Sprite ParchmentPanel => Lazy(ref parchment, BuildParchment);

        /// <summary>武器卡底：比内容板薄一圈的羊皮纸。9-slice border = 20。</summary>
        public static Sprite Card => Lazy(ref card, BuildCard);

        /// <summary>深色凹槽（装备槽 / 图标底板 / 血条槽 / HUD 面板）。9-slice border = 18。</summary>
        public static Sprite Slot => Lazy(ref slot, BuildSlot);

        /// <summary>普通按钮底（羊皮纸+金边，文字用墨色）。9-slice border = 18。</summary>
        public static Sprite Button => Lazy(ref button, BuildButton);

        /// <summary>当前页签/主行动按钮（金底，文字用墨色）。9-slice border = 18。</summary>
        public static Sprite ButtonGold => Lazy(ref buttonGold, BuildButtonGold);

        /// <summary>分隔线（横向拉伸，两端有小菱形）。9-slice border = (16,6,16,6)。</summary>
        public static Sprite Divider => Lazy(ref divider, BuildDivider);

        /// <summary>小菱形装饰（24x24）。</summary>
        public static Sprite Diamond => Lazy(ref diamond, BuildDiamond);

        /// <summary>角饰卷草纹（64x64，可旋转 4 个角）。</summary>
        public static Sprite Ornament => Lazy(ref ornament, BuildOrnament);

        /// <summary>心形（血量图标，64x64）。</summary>
        public static Sprite Heart => Lazy(ref heart, BuildHeart);

        /// <summary>金币图标（64x64）。</summary>
        public static Sprite Coin => Lazy(ref coin, BuildCoin);

        /// <summary>任务卷轴图标（64x64）。</summary>
        public static Sprite ScrollIcon => Lazy(ref scrollIcon, BuildScroll);

        /// <summary>背包图标（64x64）。</summary>
        public static Sprite BagIcon => Lazy(ref bagIcon, BuildBag);

        /// <summary>火漆印章（"已装备"角标，64x64）。</summary>
        public static Sprite Seal => Lazy(ref seal, BuildSeal);

        /// <summary>条状填充（白渐变，用 Image.color 染色；9-slice border = 12）。</summary>
        public static Sprite BarFill => Lazy(ref barFill, BuildBarFill);

        /// <summary>冒险者纹章圆牌（角色页头像，128x128）。</summary>
        public static Sprite HeroCrest => Lazy(ref heroCrest, BuildHeroCrest);

        /// <summary>
        /// 彩色描边框（稀有度/状态色），叠在卡片或槽位上用。9-slice border = 16。
        /// 只缓存少量颜色，字典很小。
        /// </summary>
        public static Sprite Frame(Color edge)
        {
            Color32 c32 = edge;
            int key = (c32.r << 24) | (c32.g << 16) | (c32.b << 8) | c32.a;
            Sprite s;
            if (frames.TryGetValue(key, out s) && s != null) return s;
            s = BuildFrame(edge);
            frames[key] = s;
            return s;
        }

        private static Sprite Lazy(ref Sprite cache, System.Func<Sprite> build)
        {
            if (cache != null) return cache;
            cache = build();
            return cache;
        }

        // ============================================================
        // 面板类
        // ============================================================

        /// <summary>128x128，border 36。</summary>
        private static Sprite BuildWindow()
        {
            var c = new UiCanvas(128, 128, new Color(0f, 0f, 0f, 0f));

            // 1) 外轮廓 + 金边三线（暗金 / 亮金 / 墨），模仿木框包金
            c.RoundRect(0.5f, 0.5f, 127f, 127f, 17f, InkDeep);
            c.RoundRect(2.5f, 2.5f, 123f, 123f, 15f, GoldDark, GoldDark.Shade(0.85f));
            c.RoundRectRing(5.5f, 5.5f, 117f, 117f, 13f, 2f, Gold);
            c.RoundRect(8.5f, 8.5f, 111f, 111f, 12f, Ink);

            // 2) 深色木底（中心只放极弱竖向渐变 —— 9-slice 拉伸中心时必须"平"，否则花纹会被拉成条纹）
            c.RoundRect(11f, 11f, 106f, 106f, 11f, UiColor.Hex("#2f2115"), UiColor.Hex("#1b120c"));

            // 3) 木纹只画在 border 区（36px 内），九宫格会原样保留；中心保持干净
            var rng = new System.Random(90210);
            Color grain = Ink.Alpha(0.22f);
            for (int i = 0; i < 26; i++)
            {
                // 上/下边带：横向短木纹
                float x = 14f + (float)rng.NextDouble() * 100f;
                float len = 4f + (float)rng.NextDouble() * 16f;
                c.Line(new Vector2(x, 14f + (float)rng.NextDouble() * 6f),
                       new Vector2(x + len, 14f + (float)rng.NextDouble() * 6f), 1f, grain);
                c.Line(new Vector2(x, 108f + (float)rng.NextDouble() * 5f),
                       new Vector2(x + len, 108f + (float)rng.NextDouble() * 5f), 1f, grain);
            }
            for (int i = 0; i < 18; i++)
            {
                // 左/右边带：竖向短木纹
                float y = 20f + (float)rng.NextDouble() * 88f;
                float len = 4f + (float)rng.NextDouble() * 14f;
                c.Line(new Vector2(14f + (float)rng.NextDouble() * 4f, y),
                       new Vector2(14f + (float)rng.NextDouble() * 4f, y + len), 1f, grain);
                c.Line(new Vector2(110f + (float)rng.NextDouble() * 4f, y),
                       new Vector2(110f + (float)rng.NextDouble() * 4f, y + len), 1f, grain);
            }

            // 4) 内圈金发丝线（把内容区和边框分开）
            c.RoundRectRing(13f, 13f, 102f, 102f, 9f, 1f, Gold.Alpha(0.35f));

            // 5) 四角卷草纹（在 border 36 内，缩放不丢）
            DrawCornerFlourish(c, 12f, 12f, 1f, 1f, 1f, Gold.Alpha(0.95f));
            DrawCornerFlourish(c, 115f, 12f, -1f, 1f, 1f, Gold.Alpha(0.95f));
            DrawCornerFlourish(c, 12f, 115f, 1f, -1f, 1f, Gold.Alpha(0.95f));
            DrawCornerFlourish(c, 115f, 115f, -1f, -1f, 1f, Gold.Alpha(0.95f));

            // 6) 顶部/底部极弱高光，增加"金属包边"的立体感
            c.Rect(16f, 124f, 96f, 1f, GoldLight.Alpha(0.20f));
            c.Rect(16f, 3f, 96f, 1f, Ink.Alpha(0.55f));

            return c.BakeSprite(new Vector4(36f, 36f, 36f, 36f));
        }

        /// <summary>96x96，border 28。</summary>
        private static Sprite BuildParchment()
        {
            var c = new UiCanvas(96, 96, new Color(0f, 0f, 0f, 0f));

            c.RoundRect(0.5f, 0.5f, 95f, 95f, 11f, Ink);
            c.RoundRect(2f, 2f, 92f, 92f, 9.5f, GoldDark, Gold.Shade(0.92f));
            c.RoundRectRing(4.5f, 4.5f, 87f, 87f, 8f, 1.5f, Gold);
            c.RoundRect(6.5f, 6.5f, 83f, 83f, 7f, Ink);
            // 纸面：中心接近纯色（九宫格拉伸安全），仅 3% 的竖向渐变
            c.RoundRect(8.5f, 8.5f, 79f, 79f, 6f, ParchmentLight, ParchmentDark);

            // 纸边做旧：只在 28px 边框带里撒短纤维，避免中心被拉伸成条纹
            var rng = new System.Random(4711);
            Color fiber = UiColor.Hex("#a98f63").Alpha(0.16f);
            c.Speckles(60, fiber, 11f, 11f, 85f, 25f, rng, 4f);
            c.Speckles(60, fiber, 11f, 71f, 85f, 85f, rng, 4f);
            c.Speckles(30, fiber, 11f, 25f, 25f, 71f, rng, 4f);
            c.Speckles(30, fiber, 71f, 25f, 85f, 71f, rng, 4f);

            // 内侧阴影 + 一条细墨线，让"纸"有厚度
            c.RoundRectRing(9.5f, 9.5f, 77f, 77f, 5.5f, 3f, Ink.Alpha(0.13f));
            c.RoundRectRing(11f, 11f, 74f, 74f, 5f, 1f, Ink.Alpha(0.50f));

            // 四角小卷叶
            DrawCornerFlourish(c, 13f, 13f, 1f, 1f, 0.62f, Ink.Alpha(0.55f));
            DrawCornerFlourish(c, 83f, 13f, -1f, 1f, 0.62f, Ink.Alpha(0.55f));
            DrawCornerFlourish(c, 13f, 83f, 1f, -1f, 0.62f, Ink.Alpha(0.55f));
            DrawCornerFlourish(c, 83f, 83f, -1f, -1f, 0.62f, Ink.Alpha(0.55f));

            return c.BakeSprite(new Vector4(28f, 28f, 28f, 28f));
        }

        /// <summary>96x96，border 20（卡片更小，边框要薄）。</summary>
        private static Sprite BuildCard()
        {
            var c = new UiCanvas(96, 96, new Color(0f, 0f, 0f, 0f));

            c.RoundRect(0.5f, 0.5f, 95f, 95f, 9f, Ink.Alpha(0.9f));
            c.RoundRect(2f, 2f, 92f, 92f, 8f, Parchment.Alpha(0.95f));
            c.RoundRect(4f, 4f, 88f, 88f, 7f, ParchmentLight, ParchmentDark);
            c.RoundRectRing(5.5f, 5.5f, 85f, 85f, 6f, 1.2f, Ink.Alpha(0.55f));
            // 顶部一条弱金线，卡面不至于太素
            c.Rect(16f, 90f, 64f, 1f, Gold.Alpha(0.55f));
            c.Rect(16f, 5f, 64f, 1f, Ink.Alpha(0.35f));

            return c.BakeSprite(new Vector4(20f, 20f, 20f, 20f));
        }

        /// <summary>64x64，border 18。</summary>
        private static Sprite BuildSlot()
        {
            var c = new UiCanvas(64, 64, new Color(0f, 0f, 0f, 0f));

            c.RoundRect(0.5f, 0.5f, 63f, 63f, 9f, Ink);
            c.RoundRect(2f, 2f, 60f, 60f, 8f, GoldDark, GoldDark.Shade(0.8f));
            c.RoundRectRing(5f, 5f, 54f, 54f, 7f, 1.2f, Gold.Alpha(0.85f));
            c.RoundRect(7f, 7f, 50f, 50f, 6f, UiColor.Hex("#231810"), UiColor.Hex("#150e09"));

            // 凹槽：上暗下亮（假内阴影）
            c.Rect(9f, 53f, 46f, 2f, Ink.Alpha(0.55f));
            c.Rect(9f, 8f, 46f, 1f, GoldLight.Alpha(0.10f));
            c.RoundRectRing(8.5f, 8.5f, 47f, 47f, 5.5f, 2f, Ink.Alpha(0.35f));

            return c.BakeSprite(new Vector4(18f, 18f, 18f, 18f));
        }

        /// <summary>64x64，border 18。</summary>
        private static Sprite BuildButton()
        {
            var c = new UiCanvas(64, 64, new Color(0f, 0f, 0f, 0f));

            c.RoundRect(0.5f, 0.5f, 63f, 63f, 10f, Ink);
            c.RoundRect(2f, 2f, 60f, 60f, 9f, GoldDark, GoldDark.Shade(0.8f));
            c.RoundRect(4f, 4f, 56f, 56f, 8f, ParchmentLight, Parchment);
            c.RoundRectRing(5.5f, 5.5f, 53f, 53f, 7f, 1.2f, Gold.Alpha(0.75f));

            // 顶部高光 / 底部压暗 → 有一点"压花"感
            c.Rect(8f, 56f, 48f, 2f, Color.white.Alpha(0.35f));
            c.Rect(8f, 6f, 48f, 2f, Ink.Alpha(0.15f));

            return c.BakeSprite(new Vector4(18f, 18f, 18f, 18f));
        }

        /// <summary>64x64，border 18。金色主行动按钮。</summary>
        private static Sprite BuildButtonGold()
        {
            var c = new UiCanvas(64, 64, new Color(0f, 0f, 0f, 0f));

            c.RoundRect(0.5f, 0.5f, 63f, 63f, 10f, Ink);
            c.RoundRect(2f, 2f, 60f, 60f, 9f, GoldDark);
            c.RoundRect(4f, 4f, 56f, 56f, 8f, GoldLight, Gold);
            c.RoundRectRing(5.5f, 5.5f, 53f, 53f, 7f, 1.2f, Ink.Alpha(0.55f));
            c.Rect(8f, 56f, 48f, 2f, Color.white.Alpha(0.45f));
            c.Rect(8f, 6f, 48f, 2f, Ink.Alpha(0.25f));

            return c.BakeSprite(new Vector4(18f, 18f, 18f, 18f));
        }

        /// <summary>64x16，border (16,6,16,6)。中间只有线，横向拉伸不糊。</summary>
        private static Sprite BuildDivider()
        {
            var c = new UiCanvas(64, 16, new Color(0f, 0f, 0f, 0f));

            c.Rect(16f, 7.4f, 32f, 1.2f, Gold.Alpha(0.85f));
            c.Rect(16f, 8.8f, 32f, 0.8f, Ink.Alpha(0.25f));
            // 两端小菱形钉
            c.Polygon(Gold, new Vector2(9f, 8f), new Vector2(14f, 11.5f), new Vector2(9f, 15f), new Vector2(4f, 11.5f));
            c.Polygon(GoldDark.Alpha(0.9f), new Vector2(55f, 8f), new Vector2(60f, 11.5f), new Vector2(55f, 15f), new Vector2(50f, 11.5f));

            return c.BakeSprite(new Vector4(16f, 6f, 16f, 6f));
        }

        /// <summary>24x24。</summary>
        private static Sprite BuildDiamond()
        {
            var c = new UiCanvas(24, 24, new Color(0f, 0f, 0f, 0f));
            c.Polygon(Ink, new Vector2(12f, 1f), new Vector2(23f, 12f), new Vector2(12f, 23f), new Vector2(1f, 12f));
            c.Polygon(Gold, new Vector2(12f, 4f), new Vector2(20f, 12f), new Vector2(12f, 20f), new Vector2(4f, 12f));
            c.Polygon(GoldLight.Alpha(0.8f), new Vector2(12f, 7f), new Vector2(16f, 12f), new Vector2(12f, 15f), new Vector2(8f, 12f));
            return c.BakeSprite(Vector4.zero);
        }

        /// <summary>64x64，透明底的金色角饰（左下方向，旋转即得四角）。</summary>
        private static Sprite BuildOrnament()
        {
            var c = new UiCanvas(64, 64, new Color(0f, 0f, 0f, 0f));

            c.Arc(18f, 18f, 20f, 0f, 90f, 2.6f, Gold);
            c.Arc(18f, 18f, 27f, 12f, 78f, 1.2f, Gold.Alpha(0.65f));
            c.Arc(26f, 26f, 10f, 200f, 340f, 1.6f, Gold.Alpha(0.75f));
            c.Circle(38f, 18f, 2.6f, Gold);
            c.Circle(18f, 38f, 2.6f, Gold);
            c.Polygon(Gold, new Vector2(6f, 6f), new Vector2(11f, 6f), new Vector2(6f, 11f));
            c.Ring(18f, 18f, 20f, 0.8f, Ink.Alpha(0.4f));

            return c.BakeSprite(Vector4.zero);
        }

        /// <summary>48x48，border 16：只画边框，中间透明。</summary>
        private static Sprite BuildFrame(Color edge)
        {
            var c = new UiCanvas(48, 48, new Color(0f, 0f, 0f, 0f));

            c.RoundRectRing(1.5f, 1.5f, 45f, 45f, 8f, 2.2f, Ink.Alpha(0.9f));
            c.RoundRectRing(3.6f, 3.6f, 40.8f, 40.8f, 6.8f, 2.4f, edge);
            c.RoundRectRing(6.8f, 6.8f, 34.4f, 34.4f, 5f, 1f, edge.Shade(0.55f).Alpha(0.85f));

            // 四角小方钉，强化"牌框"
            c.Circle(7f, 7f, 1.7f, Gold);
            c.Circle(41f, 7f, 1.7f, Gold);
            c.Circle(7f, 41f, 1.7f, Gold);
            c.Circle(41f, 41f, 1.7f, Gold);

            return c.BakeSprite(new Vector4(16f, 16f, 16f, 16f));
        }

        /// <summary>32x32，border 12：白色圆角渐变条，用 Image.color 染色。</summary>
        private static Sprite BuildBarFill()
        {
            var c = new UiCanvas(32, 32, new Color(0f, 0f, 0f, 0f));
            c.RoundRect(0.5f, 0.5f, 31f, 31f, 10f, Color.white, new Color(0.72f, 0.72f, 0.72f, 1f));
            c.Rect(5f, 26f, 22f, 2f, Color.white.Alpha(0.55f));
            return c.BakeSprite(new Vector4(12f, 12f, 12f, 12f));
        }

        // ============================================================
        // 图标类
        // ============================================================

        private static Sprite BuildHeart()
        {
            var c = new UiCanvas(64, 64, new Color(0f, 0f, 0f, 0f));
            DrawHeart(c, 32f, 30f, 22f, Ink);
            DrawHeart(c, 32f, 31f, 20f, RedLight);
            DrawHeart(c, 30f, 33f, 16f, Red);
            // 左上高光
            c.Circle(24f, 40f, 5f, Color.white.Alpha(0.28f));
            c.Circle(22f, 42f, 2.2f, Color.white.Alpha(0.35f));
            return c.BakeSprite(Vector4.zero);
        }

        private static void DrawHeart(UiCanvas c, float cx, float cy, float r, Color color)
        {
            c.Circle(cx - r * 0.5f, cy + r * 0.32f, r * 0.56f, color);
            c.Circle(cx + r * 0.5f, cy + r * 0.32f, r * 0.56f, color);
            c.Polygon(color,
                new Vector2(cx - r * 1.02f, cy + r * 0.42f),
                new Vector2(cx + r * 1.02f, cy + r * 0.42f),
                new Vector2(cx, cy - r * 0.95f));
        }

        private static Sprite BuildCoin()
        {
            var c = new UiCanvas(64, 64, new Color(0f, 0f, 0f, 0f));
            c.Circle(32f, 32f, 27f, Ink);
            c.Circle(32f, 32f, 25f, GoldLight, Gold.Shade(0.8f));
            c.Ring(32f, 32f, 20f, 1.6f, GoldDark.Alpha(0.9f));
            c.Ring(32f, 32f, 25f, 1f, GoldDark.Alpha(0.55f));
            // 中心的菱形徽记
            c.Polygon(Ink.Alpha(0.8f), new Vector2(32f, 16f), new Vector2(44f, 32f), new Vector2(32f, 48f), new Vector2(20f, 32f));
            c.Polygon(GoldLight, new Vector2(32f, 19.5f), new Vector2(40.5f, 32f), new Vector2(32f, 44.5f), new Vector2(23.5f, 32f));
            // 高光弧
            c.Arc(32f, 32f, 21f, 95f, 160f, 2.4f, Color.white.Alpha(0.5f));
            return c.BakeSprite(Vector4.zero);
        }

        private static Sprite BuildScroll()
        {
            var c = new UiCanvas(64, 64, new Color(0f, 0f, 0f, 0f));
            // 纸卷主体
            c.RoundRect(19f, 12f, 26f, 40f, 2f, Ink.Alpha(0.9f));
            c.RoundRect(20.5f, 13.5f, 23f, 37f, 2f, ParchmentLight, ParchmentDark);
            // 上下卷轴
            c.RoundRect(13f, 4f, 38f, 10f, 5f, Ink);
            c.RoundRect(14.5f, 5.5f, 35f, 7f, 3.5f, Parchment, ParchmentDark);
            c.RoundRect(13f, 54f, 38f, 10f, 5f, Ink);
            c.RoundRect(14.5f, 55.5f, 35f, 7f, 3.5f, Parchment, ParchmentDark);
            // 字迹（三行）
            Color ink = Ink.Alpha(0.55f);
            c.Rect(24f, 40f, 16f, 1.6f, ink);
            c.Rect(24f, 34f, 12f, 1.6f, ink);
            c.Rect(24f, 28f, 15f, 1.6f, ink);
            // 金色绶带
            c.Rect(26f, 21f, 12f, 3f, Gold);
            c.Polygon(Gold, new Vector2(26f, 21f), new Vector2(22f, 17f), new Vector2(26f, 17f));
            c.Polygon(Gold, new Vector2(38f, 21f), new Vector2(42f, 17f), new Vector2(38f, 17f));
            return c.BakeSprite(Vector4.zero);
        }

        private static Sprite BuildBag()
        {
            var c = new UiCanvas(64, 64, new Color(0f, 0f, 0f, 0f));
            // 袋身
            c.Circle(32f, 26f, 20f, Ink);
            c.Circle(32f, 27f, 18f, ParchmentDark);
            // 袋口与束带
            c.Rect(22f, 40f, 20f, 9f, Ink);
            c.Rect(23.5f, 41f, 17f, 7f, Parchment);
            c.Rect(20f, 44f, 24f, 4f, Gold);
            c.Rect(20f, 44f, 24f, 1.2f, GoldLight);
            // 扣子
            c.Rect(30f, 38f, 4f, 8f, GoldDark);
            c.Circle(32f, 36f, 2.6f, Gold);
            // 缝线
            Color stitch = Ink.Alpha(0.35f);
            c.Line(new Vector2(16f, 20f), new Vector2(48f, 20f), 1f, stitch);
            return c.BakeSprite(Vector4.zero);
        }

        private static Sprite BuildSeal()
        {
            var c = new UiCanvas(64, 64, new Color(0f, 0f, 0f, 0f));
            Color dark = UiColor.Hex("#5e1717");
            // 不规则火漆边
            c.Circle(32f, 32f, 23f, dark);
            var rng = new System.Random(1234);
            for (int i = 0; i < 14; i++)
            {
                float ang = i / 14f * Mathf.PI * 2f;
                float r = 22f + (float)rng.NextDouble() * 2.5f;
                c.Circle(32f + Mathf.Cos(ang) * r, 32f + Mathf.Sin(ang) * r, 3.2f, dark);
            }
            c.Circle(31f, 33f, 21f, Red.Shade(0.9f), dark);
            c.Ring(32f, 32f, 18f, 1.8f, Gold.Alpha(0.9f));
            // 中间的"剑"徽记
            c.Polygon(GoldLight, new Vector2(32f, 44f), new Vector2(36f, 32f), new Vector2(32f, 20f), new Vector2(28f, 32f));
            c.Line(new Vector2(23f, 26f), new Vector2(41f, 26f), 2f, Gold);
            c.Line(new Vector2(32f, 20f), new Vector2(32f, 15f), 3f, Gold);
            c.Arc(32f, 32f, 15f, 100f, 150f, 1.4f, Color.white.Alpha(0.22f));
            return c.BakeSprite(Vector4.zero);
        }

        /// <summary>128x128 的冒险者纹章（角色页头像）：暗红盾面 + 交叉法杖/剑 + 金环。</summary>
        private static Sprite BuildHeroCrest()
        {
            var c = new UiCanvas(128, 128, new Color(0f, 0f, 0f, 0f));

            // 金环外圈
            c.Circle(64f, 64f, 61f, Ink);
            c.Circle(64f, 64f, 58f, Gold, GoldDark);
            c.Circle(64f, 64f, 53f, InkDeep);
            // 盾面
            c.Polygon(Ink, new Vector2(64f, 112f), new Vector2(104f, 92f), new Vector2(97f, 46f),
                new Vector2(64f, 16f), new Vector2(31f, 46f), new Vector2(24f, 92f));
            c.Polygon(Red.Shade(0.9f), new Vector2(64f, 106f), new Vector2(98f, 88f), new Vector2(92f, 48f),
                new Vector2(64f, 23f), new Vector2(36f, 48f), new Vector2(30f, 88f));
            // 交叉的法杖（左下→右上）与剑（右下→左上）
            c.Line(new Vector2(38f, 34f), new Vector2(90f, 96f), 4f, UiColor.Hex("#6b4a2a"));
            c.Line(new Vector2(38f, 34f), new Vector2(90f, 96f), 1.6f, UiColor.Hex("#9a7246"));
            c.Circle(92f, 99f, 7f, Blue, UiColor.Hex("#26527d"));
            c.Circle(92f, 99f, 4f, UiColor.Hex("#7fd0e8"));
            c.Line(new Vector2(88f, 34f), new Vector2(40f, 96f), 4.6f, Ink);
            c.Line(new Vector2(88f, 34f), new Vector2(40f, 96f), 2.6f, UiColor.Hex("#c8d0d8"));
            c.Line(new Vector2(36f, 88f), new Vector2(52f, 96f), 3f, Gold);
            c.Line(new Vector2(83f, 38f), new Vector2(93f, 30f), 3.6f, Gold);
            // 纹章下的绶带
            c.Rect(38f, 8f, 52f, 10f, Ink);
            c.Rect(40f, 9.5f, 48f, 7f, Gold);
            c.RoundRect(40f, 9.5f, 48f, 7f, 2.5f, Gold, GoldDark);
            c.Polygon(Ink, new Vector2(38f, 8f), new Vector2(30f, 3f), new Vector2(38f, 3f));
            c.Polygon(Ink, new Vector2(90f, 8f), new Vector2(98f, 3f), new Vector2(90f, 3f));

            return c.BakeSprite(Vector4.zero);
        }

        // ============================================================
        // 公共绘制辅助
        // ============================================================

        /// <summary>
        /// 四角卷草纹：在 (x,y) 这个角上、朝 (dirX,dirY) 方向画一小段双弧 + 圆钉 + 角楔。
        /// 所有笔画都压在 sprite 的 border 区内，九宫格拉伸时不会被拉变形。
        /// </summary>
        private static void DrawCornerFlourish(UiCanvas c, float x, float y, float dirX, float dirY, float s, Color color)
        {
            float baseAng = Mathf.Atan2(dirY, dirX) * Mathf.Rad2Deg + 180f;

            Vector2 c1 = new Vector2(x + dirX * 10f * s, y + dirY * 10f * s);
            c.Arc(c1.x, c1.y, 9f * s, baseAng - 52f, baseAng + 52f, 1.5f * s, color);

            Vector2 c2 = new Vector2(x + dirX * 13f * s, y + dirY * 13f * s);
            c.Arc(c2.x, c2.y, 9f * s, baseAng - 34f, baseAng + 34f, 0.8f * s, color.Alpha(color.a * 0.55f));

            c.Circle(x + dirX * 20f * s, y + dirY * 9f * s, 1.8f * s, color);
            c.Circle(x + dirX * 9f * s, y + dirY * 20f * s, 1.8f * s, color);
            c.Polygon(color, new Vector2(x, y), new Vector2(x + dirX * 7f * s, y), new Vector2(x, y + dirY * 7f * s));
        }
    }
}
