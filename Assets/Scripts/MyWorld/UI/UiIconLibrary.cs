using System.Collections.Generic;
using UnityEngine;

namespace MyWorld.UI
{
    /// <summary>
    /// 武器图标库：统一入口 <see cref="Load(WeaponKind)"/>。
    ///
    /// 取图顺序（契约 §3 要求"先读磁盘、没有就程序化画、禁止留空"）：
    ///   1. 编辑器下读 Assets/UI/Icons/&lt;Kind&gt;.png —— blender-art 后续补的 Grapple/Gauntlet 会自动生效；
    ///   2. 读 Resources/UI/Icons/&lt;Kind&gt;（Assets/Editor/UiSetup.cs 会把图标复制进来，出包也能用）；
    ///   3. 都没有 → 用 UiCanvas 程序化画一张（每个武器一套手工绘制的形状，不是占位方块）。
    ///
    /// ⚠️ 缓存是运行时对象，退出 Play 会被销毁；所以每次取都要判 null 重建。
    ///   编辑器里每次脚本重编（域重载）也会清缓存，方便 blender-art 补图后立刻看到新图。
    /// </summary>
    public static class UiIconLibrary
    {
        /// <summary>项目里的图标目录（blender-art 交付位置）。</summary>
        public const string ProjectFolder = "Assets/UI/Icons/";
        /// <summary>Resources 里的镜像目录（UiSetup 负责同步，保证打包后也能取到）。</summary>
        public const string ResourcesFolder = "UI/Icons/";

        private static readonly Dictionary<WeaponKind, Sprite> cache = new Dictionary<WeaponKind, Sprite>();

        // ---------------- 图标里用到的颜色（保持全套统一） ----------------

        private static readonly Color Outline = UiColor.Hex("#1b120c");
        private static readonly Color Steel = UiColor.Hex("#bcc6d0");
        private static readonly Color SteelDark = UiColor.Hex("#7e8994");
        private static readonly Color SteelLight = UiColor.Hex("#eef4f9");
        private static readonly Color Wood = UiColor.Hex("#7a5330");
        private static readonly Color WoodDark = UiColor.Hex("#4d321f");
        private static readonly Color WoodLight = UiColor.Hex("#ab7c4e");
        private static readonly Color Leather = UiColor.Hex("#5c3d24");
        private static readonly Color LeatherLight = UiColor.Hex("#8a6038");
        private static readonly Color GlowBlue = UiColor.Hex("#5fbfe8");
        private static readonly Color GlowCyan = UiColor.Hex("#c9f3ff");
        private static readonly Color Skin = UiColor.Hex("#e2b083");
        private static readonly Color SkinDark = UiColor.Hex("#b7825a");
        private static readonly Color SkinLight = UiColor.Hex("#f3cba0");

        /// <summary>取某武器的图标；没有美术素材时返回程序化绘制的版本（绝不返回 null）。</summary>
        public static Sprite Load(WeaponKind kind)
        {
            Sprite cached;
            if (cache.TryGetValue(kind, out cached) && cached != null) return cached;

            Sprite sprite = LoadFromProject(kind);
            if (sprite == null) sprite = LoadFromResources(kind);
            if (sprite == null) sprite = Generate(kind);

            cache[kind] = sprite;
            return sprite;
        }

        /// <summary>清缓存（美术补图后想立刻看到新图时调用）。</summary>
        public static void ClearCache()
        {
            cache.Clear();
        }

        // ---------------- 素材读取 ----------------

        private static Sprite LoadFromProject(WeaponKind kind)
        {
#if UNITY_EDITOR
            string path = ProjectFolder + kind + ".png";
            var sprite = UnityEditor.AssetDatabase.LoadAssetAtPath<Sprite>(path);
            if (sprite != null) return sprite;

            // 万一是 Default 导入类型（不是 Sprite），退一步拿贴图自己包一层 Sprite，
            // 这样 blender-art 只要把 png 丢进目录就能用，不必记得改 Import Settings。
            var tex = UnityEditor.AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            if (tex != null)
            {
                var s = Sprite.Create(tex, new Rect(0f, 0f, tex.width, tex.height), new Vector2(0.5f, 0.5f), 100f);
                s.name = kind + "_Icon";
                return s;
            }
#endif
            return null;
        }

        private static Sprite LoadFromResources(WeaponKind kind)
        {
            var sprite = Resources.Load<Sprite>(ResourcesFolder + kind);
            if (sprite != null) return sprite;

            var tex = Resources.Load<Texture2D>(ResourcesFolder + kind);
            if (tex != null)
            {
                var s = Sprite.Create(tex, new Rect(0f, 0f, tex.width, tex.height), new Vector2(0.5f, 0.5f), 100f);
                s.name = kind + "_Icon";
                return s;
            }
            return null;
        }

#if UNITY_EDITOR
        // 域重载（脚本重编 / 美术导入新图）后清缓存：下一次 Load 会重新读磁盘。
        [UnityEditor.Callbacks.DidReloadScripts]
        private static void OnScriptsReloaded()
        {
            cache.Clear();
        }
#endif

        // ---------------- 程序化绘制 ----------------

        /// <summary>程序化生成图标（128x128，透明底）。</summary>
        public static Sprite Generate(WeaponKind kind)
        {
            var c = new UiCanvas(128, 128, new Color(0f, 0f, 0f, 0f));

            switch (kind)
            {
                case WeaponKind.Staff: DrawStaff(c); break;
                case WeaponKind.Sword: DrawSword(c); break;
                case WeaponKind.Bow: DrawBow(c); break;
                case WeaponKind.Grapple: DrawGrapple(c); break;
                case WeaponKind.Shield: DrawShield(c); break;
                case WeaponKind.Gauntlet: DrawGauntlet(c); break;
                case WeaponKind.Unarmed: DrawFist(c); break;
                default: DrawSword(c); break; // 未来新增武器类型：先给一把剑，绝不空白
            }

            var sprite = c.BakeSprite(Vector4.zero);
            sprite.name = "UiIcon_" + kind;
            return sprite;
        }

        // ---- 法杖：木杆 + 金箍 + 顶端魔法宝珠 ----
        private static void DrawStaff(UiCanvas c)
        {
            Vector2 a = new Vector2(24f, 20f);
            Vector2 b = new Vector2(94f, 98f);
            Vector2 dir = (b - a).normalized;
            Vector2 perp = new Vector2(-dir.y, dir.x);

            // 杆（带锥形：下端粗、接近宝珠处略细）
            c.Line(a, b, 11f, Outline);
            c.TaperLine(a, b, 8f, 6.5f, Wood);
            c.TaperLine(a + perp * 1.6f, b + perp * 1.2f, 2.6f, 1.8f, WoodLight.Alpha(0.85f));
            c.TaperLine(a - perp * 2.6f, b - perp * 2.2f, 1.6f, 1.2f, WoodDark.Alpha(0.75f));

            // 两道金箍
            DrawBand(c, a + dir * 30f, perp, 6.2f, 3f);
            DrawBand(c, a + dir * 66f, perp, 5.6f, 2.6f);

            // 宝珠
            Vector2 orb = new Vector2(100f, 105f);
            c.Circle(orb.x, orb.y, 18f, Outline);
            c.Circle(orb.x, orb.y, 16f, GlowCyan, UiColor.Hex("#1e4f7a"));
            c.Circle(orb.x - 3f, orb.y - 2f, 10f, GlowBlue.Alpha(0.85f), UiColor.Hex("#2a6ea8").Alpha(0.6f));
            c.Circle(orb.x - 5f, orb.y + 4f, 4f, Color.white.Alpha(0.75f));
            c.Ring(orb.x, orb.y, 16.5f, 2.2f, UiSkin.Gold);
            c.Ring(orb.x, orb.y, 19f, 1f, UiSkin.GoldDark.Alpha(0.8f));

            // 宝珠外的金焰尖刺
            for (int i = 0; i < 7; i++)
            {
                float ang = (18f + i * 36f) * Mathf.Deg2Rad;
                Vector2 d = new Vector2(Mathf.Cos(ang), Mathf.Sin(ang));
                c.TaperLine(orb + d * 19f, orb + d * 25f, 2.4f, 0.7f, UiSkin.Gold);
            }

            // 魔法星屑
            DrawSpark(c, new Vector2(72f, 116f), 5f, GlowCyan.Alpha(0.85f));
            DrawSpark(c, new Vector2(118f, 84f), 4f, GlowCyan.Alpha(0.7f));
            DrawSpark(c, new Vector2(88f, 122f), 3f, GlowCyan.Alpha(0.6f));
        }

        private static void DrawBand(UiCanvas c, Vector2 center, Vector2 perp, float halfLen, float thick)
        {
            c.Line(center - perp * (halfLen + 1.4f), center + perp * (halfLen + 1.4f), thick + 2.4f, Outline);
            c.Line(center - perp * halfLen, center + perp * halfLen, thick, UiSkin.Gold);
            c.Line(center - perp * (halfLen * 0.5f) + new Vector2(0.6f, 0.6f),
                   center + perp * (halfLen * 0.5f), thick * 0.35f, UiSkin.GoldLight.Alpha(0.9f));
        }

        // ---- 剑：剑身 + 护手 + 皮柄 + 圆头 ----
        private static void DrawSword(UiCanvas c)
        {
            // 剑身（外轮廓用多边形叠出来，保证有墨线包边）
            c.Polygon(Outline, new Vector2(64f, 120f), new Vector2(53f, 97f), new Vector2(53f, 52f),
                new Vector2(75f, 52f), new Vector2(75f, 97f));
            c.Polygon(SteelDark, new Vector2(64f, 114f), new Vector2(56f, 95f), new Vector2(56f, 54f),
                new Vector2(72f, 54f), new Vector2(72f, 95f));
            c.Polygon(Steel, new Vector2(64f, 113f), new Vector2(57.5f, 95f), new Vector2(57.5f, 54f),
                new Vector2(64f, 54f), new Vector2(64f, 95f));
            // 中脊高光 + 侧锋压暗
            c.Polygon(SteelLight, new Vector2(64f, 110f), new Vector2(59.5f, 95f), new Vector2(59.5f, 55f),
                new Vector2(62f, 55f), new Vector2(62f, 95f));
            c.Polygon(SteelDark.Alpha(0.55f), new Vector2(64f, 112f), new Vector2(70.5f, 95f),
                new Vector2(70.5f, 55f), new Vector2(67f, 55f), new Vector2(67f, 95f));

            // 护手
            c.RoundRect(35f, 42f, 58f, 12f, 4f, Outline);
            c.RoundRect(37f, 44f, 54f, 8f, 3.5f, UiSkin.GoldLight, UiSkin.GoldDark);
            c.Rect(39f, 47f, 50f, 1.6f, UiSkin.GoldLight.Alpha(0.75f));
            c.Circle(39f, 48f, 4.6f, Outline);
            c.Circle(39f, 48f, 3.6f, UiSkin.Gold);
            c.Circle(89f, 48f, 4.6f, Outline);
            c.Circle(89f, 48f, 3.6f, UiSkin.Gold);

            // 皮柄
            c.RoundRect(55.5f, 15f, 17f, 29f, 5f, Outline);
            c.RoundRect(57f, 16.5f, 14f, 26f, 4.5f, LeatherLight, Leather);
            for (int i = 0; i < 4; i++)
            {
                float y = 20f + i * 6.2f;
                c.Line(new Vector2(58f, y), new Vector2(70f, y + 3.2f), 1.4f, WoodDark.Alpha(0.6f));
            }

            // 圆头
            c.Circle(64f, 13f, 7.4f, Outline);
            c.Circle(64f, 13f, 6.2f, UiSkin.GoldLight, UiSkin.GoldDark);
            c.Circle(62.5f, 14.5f, 2f, Color.white.Alpha(0.6f));

            // 剑身反光
            c.Line(new Vector2(60.5f, 57f), new Vector2(60.5f, 100f), 1.2f, Color.white.Alpha(0.5f));
        }

        // ---- 弓：木弓 + 弓弦 + 搭在弦上的箭 ----
        private static void DrawBow(UiCanvas c)
        {
            // 弓臂
            c.Arc(76f, 64f, 43f, 118f, 242f, 10f, Outline);
            c.Arc(76f, 64f, 42.5f, 120f, 240f, 7f, Wood);
            c.Arc(76f, 64f, 41f, 128f, 232f, 1.6f, WoodLight.Alpha(0.9f));
            c.Arc(76f, 64f, 38f, 132f, 228f, 1.6f, WoodDark.Alpha(0.7f));

            // 握把
            c.RoundRect(32f, 50f, 17f, 28f, 6f, Outline);
            c.RoundRect(33.5f, 51.5f, 14f, 25f, 5f, LeatherLight, Leather);
            for (int i = 0; i < 3; i++)
                c.Line(new Vector2(34f, 55f + i * 6.5f), new Vector2(47f, 57f + i * 6.5f), 1.2f, WoodDark.Alpha(0.55f));

            // 弓梢金饰
            Vector2 tipTop = new Vector2(55f, 101f);
            Vector2 tipBottom = new Vector2(55f, 27f);
            c.Circle(tipTop.x, tipTop.y, 5f, Outline);
            c.Circle(tipTop.x, tipTop.y, 3.8f, UiSkin.Gold);
            c.Circle(tipBottom.x, tipBottom.y, 5f, Outline);
            c.Circle(tipBottom.x, tipBottom.y, 3.8f, UiSkin.Gold);

            // 弓弦
            c.Line(tipTop, tipBottom, 2.6f, Outline);
            c.Line(tipTop, tipBottom, 1.2f, UiColor.Hex("#efe6c8").Alpha(0.95f));

            // 箭（横穿，朝右）
            c.Line(new Vector2(28f, 64f), new Vector2(98f, 64f), 4.6f, Outline);
            c.Line(new Vector2(29f, 64f), new Vector2(97f, 64f), 2.6f, WoodLight);
            c.Line(new Vector2(29f, 65.2f), new Vector2(96f, 65.2f), 1f, UiColor.Hex("#d9b98c").Alpha(0.9f));
            // 箭头
            c.Polygon(Outline, new Vector2(108f, 64f), new Vector2(94f, 71.5f), new Vector2(94f, 56.5f));
            c.Polygon(Steel, new Vector2(104f, 64f), new Vector2(95.5f, 69.5f), new Vector2(95.5f, 58.5f));
            c.Polygon(SteelLight, new Vector2(103f, 64.6f), new Vector2(96.5f, 68f), new Vector2(96.5f, 64.6f));
            // 尾羽
            c.Polygon(Outline, new Vector2(30f, 64f), new Vector2(18f, 57f), new Vector2(24f, 64f), new Vector2(18f, 71f));
            c.Polygon(UiColor.Hex("#a83434"), new Vector2(30f, 64f), new Vector2(21f, 59f), new Vector2(26f, 64f), new Vector2(21f, 69f));
            // 搭弦处的箭尾卡口
            c.Circle(55f, 64f, 2.4f, Outline);
        }

        // ---- 抓钩：三爪钩 + 铁杆 + 锁链 ----
        private static void DrawGrapple(UiCanvas c)
        {
            // 铁杆
            c.Line(new Vector2(64f, 20f), new Vector2(64f, 88f), 9f, Outline);
            c.Line(new Vector2(64f, 21f), new Vector2(64f, 87f), 5.5f, Steel);
            c.Line(new Vector2(62f, 22f), new Vector2(62f, 86f), 1.4f, SteelLight.Alpha(0.9f));
            c.Line(new Vector2(66.2f, 22f), new Vector2(66.2f, 86f), 1.2f, SteelDark.Alpha(0.8f));

            // 中爪
            DrawBone(c, new Vector2(64f, 86f), new Vector2(64f, 118f), 5.2f);
            c.Polygon(Outline, new Vector2(64f, 124f), new Vector2(59f, 114f), new Vector2(69f, 114f));
            c.Polygon(SteelLight, new Vector2(64f, 121f), new Vector2(60.5f, 114.5f), new Vector2(67.5f, 114.5f));

            // 左爪：先向外再向下弯
            DrawBone(c, new Vector2(62f, 90f), new Vector2(45f, 103f), 5.2f);
            DrawBone(c, new Vector2(45f, 103f), new Vector2(34f, 100f), 4.6f);
            DrawBone(c, new Vector2(34f, 100f), new Vector2(31f, 91f), 3.6f);
            c.Circle(31f, 90f, 2.6f, Steel);
            c.Circle(31f, 90f, 1.4f, SteelLight);

            // 右爪（镜像）
            DrawBone(c, new Vector2(66f, 90f), new Vector2(83f, 103f), 5.2f);
            DrawBone(c, new Vector2(83f, 103f), new Vector2(94f, 100f), 4.6f);
            DrawBone(c, new Vector2(94f, 100f), new Vector2(97f, 91f), 3.6f);
            c.Circle(97f, 90f, 2.6f, Steel);
            c.Circle(97f, 90f, 1.4f, SteelLight);

            // 三爪交汇处的金箍
            c.RoundRect(54f, 78f, 20f, 11f, 4f, Outline);
            c.RoundRect(55.5f, 79.5f, 17f, 8f, 3f, UiSkin.Gold, UiSkin.GoldDark);
            c.Rect(57f, 84f, 14f, 1.2f, UiSkin.GoldLight.Alpha(0.85f));

            // 锁链（三个环，交替方向）
            DrawChainRing(c, 64f, 22f, 6.5f);
            DrawChainRing(c, 64f, 12f, 6f);
            DrawChainRing(c, 64f, 4f, 4.6f);
        }

        /// <summary>画一段带墨线包边的金属"骨头"（抓钩爪的一条边）。</summary>
        private static void DrawBone(UiCanvas c, Vector2 a, Vector2 b, float thick)
        {
            c.Line(a, b, thick + 4.6f, Outline);
            c.Line(a, b, thick, Steel);
            c.Line(a + new Vector2(-0.8f, 1f), b + new Vector2(-0.8f, 1f), thick * 0.3f, SteelLight.Alpha(0.85f));
        }

        /// <summary>画一个链环。</summary>
        private static void DrawChainRing(UiCanvas c, float x, float y, float r)
        {
            c.Ring(x, y, r, 3.4f, Outline);
            c.Ring(x, y, r, 1.9f, Steel);
            c.Ring(x - 0.6f, y + 0.6f, r, 0.7f, SteelLight.Alpha(0.8f));
        }

        // ---- 盾：鸢形盾 + 金边 + 十字纹 ----
        private static void DrawShield(UiCanvas c)
        {
            Vector2[] outline = { new Vector2(30f, 112f), new Vector2(98f, 112f), new Vector2(94f, 66f), new Vector2(64f, 14f), new Vector2(34f, 66f) };
            Vector2[] gold = { new Vector2(35f, 107f), new Vector2(93f, 107f), new Vector2(89f, 64f), new Vector2(64f, 22f), new Vector2(39f, 64f) };
            Vector2[] field = { new Vector2(40f, 102f), new Vector2(88f, 102f), new Vector2(85f, 64f), new Vector2(64f, 31f), new Vector2(43f, 64f) };

            c.Polygon(outline, Outline);
            c.Polygon(gold, UiSkin.Gold);
            c.Polygon(field, UiColor.Hex("#2c4b73"));
            // 盾面上半部提亮
            c.Polygon(UiColor.Hex("#3d6291").Alpha(0.85f), new Vector2(42f, 100f), new Vector2(86f, 100f),
                new Vector2(78f, 78f), new Vector2(64f, 68f), new Vector2(50f, 78f));

            // 顶边金条
            c.RoundRect(34f, 99f, 60f, 9f, 3f, Outline);
            c.RoundRect(36f, 100.5f, 56f, 6f, 2.5f, UiSkin.GoldLight, UiSkin.GoldDark);

            // 十字纹（竖 + 横）
            c.Rect(59.5f, 38f, 9f, 56f, Outline);
            c.Rect(61f, 39.5f, 6f, 53f, UiSkin.Gold);
            c.Rect(61f, 39.5f, 1.8f, 53f, UiSkin.GoldLight.Alpha(0.8f));
            c.Rect(45f, 70f, 38f, 9f, Outline);
            c.Rect(46.5f, 71.5f, 35f, 6f, UiSkin.Gold);
            c.Rect(46.5f, 76f, 35f, 1.4f, UiSkin.GoldLight.Alpha(0.8f));

            // 中央盾钉
            c.Circle(64f, 76f, 8.4f, Outline);
            c.Circle(64f, 76f, 7f, UiSkin.GoldLight, UiSkin.GoldDark);
            c.Circle(64f, 76f, 2.6f, Color.white.Alpha(0.55f));

            // 四角铆钉
            c.Circle(41f, 101f, 2.4f, Outline);
            c.Circle(41f, 101f, 1.5f, UiSkin.GoldLight);
            c.Circle(87f, 101f, 2.4f, Outline);
            c.Circle(87f, 101f, 1.5f, UiSkin.GoldLight);
            c.Circle(46f, 65f, 2.2f, Outline);
            c.Circle(46f, 65f, 1.4f, UiSkin.GoldLight);
            c.Circle(82f, 65f, 2.2f, Outline);
            c.Circle(82f, 65f, 1.4f, UiSkin.GoldLight);

            // 左缘高光
            c.Line(new Vector2(39f, 100f), new Vector2(51f, 40f), 1.6f, Color.white.Alpha(0.22f));
        }

        // ---- 魔法护手：铁手套 + 掌心魔法辉光 + 金色符文 ----
        private static void DrawGauntlet(UiCanvas c)
        {
            // 掌心魔法辉光（垫在手套后面）
            c.Circle(64f, 62f, 33f, GlowBlue.Alpha(0.16f));
            c.Circle(64f, 62f, 23f, GlowBlue.Alpha(0.24f));

            // 护腕
            c.Polygon(Outline, new Vector2(44f, 8f), new Vector2(84f, 8f), new Vector2(92f, 42f), new Vector2(36f, 42f));
            c.Polygon(UiColor.Hex("#9aa5b4"), new Vector2(46f, 10f), new Vector2(82f, 10f), new Vector2(88f, 40f), new Vector2(40f, 40f));
            c.Polygon(UiColor.Hex("#c7d0dc"), new Vector2(48f, 10.5f), new Vector2(80f, 10.5f), new Vector2(62f, 40f), new Vector2(42f, 40f));
            c.Rect(37f, 37f, 54f, 5.5f, Outline);
            c.Rect(38.5f, 38.2f, 51f, 3.4f, UiSkin.Gold);

            // 掌部
            c.RoundRect(38f, 36f, 52f, 44f, 12f, Outline);
            c.RoundRect(40f, 38f, 48f, 40f, 10f, UiColor.Hex("#c3ccd8"), UiColor.Hex("#8792a2"));
            // 掌面弱化（让魔法符文显眼）
            c.RoundRect(47f, 45f, 34f, 27f, 8f, UiColor.Hex("#6e7a8c").Alpha(0.55f));

            // 四指（每节带墨线）
            for (int i = 0; i < 4; i++)
            {
                float x = 41f + i * 12.4f;
                c.RoundRect(x, 74f, 10.4f, 26f, 4.6f, Outline);
                c.RoundRect(x + 1.4f, 75.4f, 7.6f, 23f, 3.6f, UiColor.Hex("#d2dae5"), UiColor.Hex("#93a0b0"));
                c.Rect(x + 2.4f, 86f, 5.6f, 1.6f, Outline.Alpha(0.5f));
                c.Rect(x + 2.4f, 96f, 5.6f, 1.2f, Color.white.Alpha(0.35f));
            }

            // 拇指（左下方）
            c.RoundRect(24f, 46f, 17f, 27f, 8f, Outline);
            c.RoundRect(25.5f, 47.5f, 14f, 24f, 7f, UiColor.Hex("#d2dae5"), UiColor.Hex("#93a0b0"));
            c.Rect(27f, 57f, 11f, 1.4f, Outline.Alpha(0.45f));

            // 掌心金色符文（菱形 + 两段弧）
            c.Polygon(Outline, new Vector2(64f, 47f), new Vector2(75f, 58f), new Vector2(64f, 69f), new Vector2(53f, 58f));
            c.Polygon(UiSkin.Gold, new Vector2(64f, 49.5f), new Vector2(72.5f, 58f), new Vector2(64f, 66.5f), new Vector2(55.5f, 58f));
            c.Arc(64f, 58f, 12.5f, 30f, 150f, 1.6f, UiSkin.GoldLight.Alpha(0.9f));
            c.Arc(64f, 58f, 15.5f, 200f, 340f, 1.6f, UiSkin.GoldLight.Alpha(0.9f));

            // 术法碎光
            DrawSpark(c, new Vector2(92f, 96f), 5.5f, GlowCyan.Alpha(0.9f));
            DrawSpark(c, new Vector2(30f, 88f), 4.5f, GlowCyan.Alpha(0.8f));
            DrawSpark(c, new Vector2(98f, 44f), 3.5f, GlowCyan.Alpha(0.7f));
        }

        // ---- 空手：握拳 + 皮护腕 ----
        private static void DrawFist(UiCanvas c)
        {
            // 护腕
            c.RoundRect(44f, 10f, 40f, 30f, 6f, Outline);
            c.RoundRect(45.5f, 11.5f, 37f, 27f, 5f, LeatherLight, Leather);
            c.Rect(44f, 32f, 40f, 5f, Outline);
            c.Rect(45.5f, 33.2f, 37f, 3.2f, UiSkin.Gold);
            c.Rect(45.5f, 15f, 37f, 3f, WoodDark.Alpha(0.6f));

            // 手背主体
            c.RoundRect(35f, 38f, 58f, 54f, 17f, Outline);
            c.RoundRect(37f, 40f, 54f, 50f, 15f, SkinLight, SkinDark);

            // 四个指关节
            for (int i = 0; i < 4; i++)
            {
                float x = 42f + i * 13f;
                c.Circle(x + 5.5f, 90f, 8.6f, Outline);
                c.Circle(x + 5.5f, 91f, 7.2f, SkinLight, Skin);
                c.Circle(x + 4f, 93.5f, 2.6f, Color.white.Alpha(0.35f));
            }

            // 指缝
            for (int i = 0; i < 3; i++)
            {
                float x = 55f + i * 13f;
                c.Line(new Vector2(x, 82f), new Vector2(x - 1.5f, 66f), 1.8f, SkinDark.Alpha(0.75f));
            }

            // 拇指（横在掌下）
            c.RoundRect(26f, 46f, 30f, 18f, 9f, Outline);
            c.RoundRect(27.5f, 47.5f, 27f, 15f, 8f, SkinLight, Skin);
            c.Line(new Vector2(30f, 52f), new Vector2(50f, 52f), 1.2f, SkinDark.Alpha(0.5f));

            // 手背高光 + 护腕上的金线
            c.Rect(44f, 78f, 24f, 2f, Color.white.Alpha(0.18f));
            c.Rect(48f, 34.5f, 30f, 1.2f, UiSkin.GoldLight.Alpha(0.75f));
        }

        // ---- 通用小装饰 ----

        /// <summary>四角星形闪光。</summary>
        private static void DrawSpark(UiCanvas c, Vector2 p, float r, Color color)
        {
            c.TaperLine(new Vector2(p.x - r, p.y), new Vector2(p.x + r, p.y), 1.6f, 1.6f, color);
            c.TaperLine(new Vector2(p.x, p.y - r), new Vector2(p.x, p.y + r), 1.6f, 1.6f, color);
            c.TaperLine(new Vector2(p.x - r * 0.55f, p.y - r * 0.55f), new Vector2(p.x + r * 0.55f, p.y + r * 0.55f), 1f, 1f, color);
            c.TaperLine(new Vector2(p.x - r * 0.55f, p.y + r * 0.55f), new Vector2(p.x + r * 0.55f, p.y - r * 0.55f), 1f, 1f, color);
            c.Circle(p.x, p.y, r * 0.28f, Color.white.Alpha(0.9f));
        }
    }
}
