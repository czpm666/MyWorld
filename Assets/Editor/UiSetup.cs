using System.IO;
using UnityEditor;
using UnityEngine;
using MyWorld.UI;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// UI 资产生成/同步工具（编辑器菜单：My World/UI/…）。
    ///
    /// 三件事：
    /// 1. <b>同步武器图标</b>：把 blender-art 交付的 Assets/UI/Icons/*.png 复制到 Assets/Resources/UI/Icons/，
    ///    并强制 Sprite 导入设置 —— 这样出包后 Resources.Load&lt;Sprite&gt; 也能取到，不依赖编辑器 API。
    /// 2. <b>皮肤预览图</b>：不启动 Play，直接把 UiSkin 的程序化面板（真实九宫格拉伸后）、图标、装饰画进一张 PNG。
    ///    用来快速检查羊皮纸/金边/角饰的观感，改 UiSkin 后重跑一次就能看图复查（这是我自己迭代视觉的主要手段）。
    /// 3. <b>图标来源检查</b>：打印每个武器图标当前来自 磁盘素材 / Resources / 程序化，方便确认 blender-art 的交付有没有生效。
    ///
    /// 所有输出都在 ui-dev 的文件归属内（Assets/Resources/UI/* 与 Assets/Screenshots/*）。
    /// </summary>
    public static class UiSetup
    {
        private const string IconSourceFolder = "Assets/UI/Icons";
        private const string IconResourceFolder = "Assets/Resources/UI/Icons";
        private const string PreviewFolder = "Assets/Screenshots";

        // ============================================================
        // 1) 图标同步
        // ============================================================

        [MenuItem("My World/UI/同步武器图标到 Resources", false, 10)]
        public static void SyncWeaponIcons()
        {
            EnsureFolder("Assets/Resources");
            EnsureFolder("Assets/Resources/UI");
            EnsureFolder(IconResourceFolder);

            if (!AssetDatabase.IsValidFolder(IconSourceFolder))
            {
                Debug.LogWarning("[UiSetup] 没有 " + IconSourceFolder + " 目录，跳过图标同步。");
                return;
            }

            string[] files = Directory.GetFiles(IconSourceFolder, "*.png", SearchOption.TopDirectoryOnly);
            int copied = 0;
            foreach (string file in files)
            {
                string name = Path.GetFileName(file);
                string src = IconSourceFolder + "/" + name;
                string dst = IconResourceFolder + "/" + name;

                if (AssetDatabase.LoadAssetAtPath<Texture2D>(src) == null)
                {
                    Debug.LogWarning("[UiSetup] 跳过（不是 Unity 认识的贴图）：" + src);
                    continue;
                }

                AssetDatabase.DeleteAsset(dst);
                if (!AssetDatabase.CopyAsset(src, dst))
                {
                    Debug.LogWarning("[UiSetup] 复制失败：" + src + " → " + dst);
                    continue;
                }

                var importer = AssetImporter.GetAtPath(dst) as TextureImporter;
                if (importer != null)
                {
                    importer.textureType = TextureImporterType.Sprite;
                    importer.spriteImportMode = SpriteImportMode.Single;
                    importer.spritePixelsPerUnit = 100f;
                    importer.mipmapEnabled = false;
                    importer.alphaIsTransparency = true;
                    importer.filterMode = FilterMode.Bilinear;
                    importer.wrapMode = TextureWrapMode.Clamp;
                    importer.maxTextureSize = 256;
                    importer.SaveAndReimport();
                }
                copied++;
            }

            AssetDatabase.Refresh();
            Debug.Log("[UiSetup] 已同步 " + copied + " 张武器图标到 " + IconResourceFolder + "。");
        }

        // ============================================================
        // 2) 皮肤预览图
        // ============================================================

        [MenuItem("My World/UI/生成皮肤预览图", false, 20)]
        public static void BakeSkinPreview()
        {
            // 画布坐标从下往上（和 Texture2D 一致），布局都按左下角算
            const int sheetW = 1500;
            const int sheetH = 1180;
            var sheet = NewSheet(sheetW, sheetH, new Color32(24, 26, 30, 255));

            int margin = 24;

            // ---- 大面板：真实的九宫格拉伸效果 ----
            DrawSlicedSprite(sheet, sheetW, UiSkin.Window, margin, sheetH - 24 - 300, 640, 300, 0.55f, Color.white);
            DrawSlicedSprite(sheet, sheetW, UiSkin.ParchmentPanel, margin, sheetH - 24 - 300 - 24 - 260, 640, 260, 0.55f, Color.white);

            int rightX = margin + 640 + 28;

            // ---- 卡片 / 槽位 / 按钮 ----
            DrawSlicedSprite(sheet, sheetW, UiSkin.Card, rightX, sheetH - 24 - 200, 300, 200, 0.5f, Color.white);
            DrawSlicedSprite(sheet, sheetW, UiSkin.Slot, rightX + 316, sheetH - 24 - 200, 128, 128, 0.5f, Color.white);
            DrawSlicedSprite(sheet, sheetW, UiSkin.Slot, rightX + 316, sheetH - 24 - 200 - 12 - 64, 64, 64, 0.5f, Color.white);
            DrawSlicedSprite(sheet, sheetW, UiSkin.Slot, rightX + 316 + 80, sheetH - 24 - 200 - 12 - 64, 64, 64, 0.5f, Color.white);
            DrawSlicedSprite(sheet, sheetW, UiSkin.Button, rightX, sheetH - 24 - 200 - 24 - 56, 220, 56, 0.5f, Color.white);
            DrawSlicedSprite(sheet, sheetW, UiSkin.ButtonGold, rightX + 236, sheetH - 24 - 200 - 24 - 56, 220, 56, 0.5f, Color.white);
            DrawSlicedSprite(sheet, sheetW, UiSkin.Frame(UiSkin.Blue), rightX + 316 + 160, sheetH - 24 - 200, 128, 128, 0.5f, Color.white);
            DrawSlicedSprite(sheet, sheetW, UiSkin.Frame(UiSkin.Red), rightX + 316 + 160, sheetH - 24 - 200 - 12 - 128, 128, 128, 0.5f, Color.white);

            // ---- 分隔线 / 菱形 / 装饰文字条 ----
            DrawSlicedSprite(sheet, sheetW, UiSkin.Divider, margin, 160, 900, 16, 0.5f, Color.white);
            DrawIcon(sheet, sheetW, UiSkin.Diamond, 24, 110, 32, 32);
            DrawIcon(sheet, sheetW, UiSkin.Ornament, 70, 96, 64, 64);
            DrawIcon(sheet, sheetW, UiSkin.Heart, 150, 96, 64, 64);
            DrawIcon(sheet, sheetW, UiSkin.Coin, 226, 96, 64, 64);
            DrawIcon(sheet, sheetW, UiSkin.ScrollIcon, 302, 96, 64, 64);
            DrawIcon(sheet, sheetW, UiSkin.BagIcon, 378, 96, 64, 64);
            DrawIcon(sheet, sheetW, UiSkin.Seal, 454, 96, 64, 64);
            DrawIcon(sheet, sheetW, UiSkin.HeroCrest, 530, 88, 72, 72);
            DrawIcon(sheet, sheetW, UiSkin.BarFill, 620, 96, 160, 32);
            DrawIcon(sheet, sheetW, UiSkin.Diamond, 620, 150, 24, 24);

            // ---- 程序化武器图标（128 → 缩放 1.0）----
            var kinds = new[]
            {
                WeaponKind.Staff, WeaponKind.Sword, WeaponKind.Bow, WeaponKind.Grapple,
                WeaponKind.Shield, WeaponKind.Gauntlet, WeaponKind.Unarmed,
            };
            int iy = sheetH - 24 - 300 - 24 - 260 - 24 - 148;
            for (int i = 0; i < kinds.Length; i++)
            {
                var sprite = UiIconLibrary.Generate(kinds[i]);
                DrawIcon(sheet, sheetW, sprite, margin + i * 148, iy, 128, 128);
            }

            // 第二行：运行时实际会用的图标（可能来自磁盘素材）
            iy -= 148;
            for (int i = 0; i < kinds.Length; i++)
            {
                var sprite = UiIconLibrary.Load(kinds[i]);
                DrawIcon(sheet, sheetW, sprite, margin + i * 148, iy, 128, 128);
                Debug.Log("[UiSetup] 图标 " + kinds[i] + " 实际来源 → " + DescribeIconSource(kinds[i]));
            }

            // ---- 角饰放大图（检查卷草纹细节）----
            DrawIcon(sheet, sheetW, UiSkin.Ornament, 1180, sheetH - 24 - 128, 128, 128);

            string path = PreviewFolder + "/ui_skin_preview.png";
            EnsureFolder(PreviewFolder);
            string abs = Path.Combine(Directory.GetParent(Application.dataPath).FullName, path.Replace('/', Path.DirectorySeparatorChar));
            File.WriteAllBytes(abs, sheet.EncodeToPNG());
            Object.DestroyImmediate(sheet);
            AssetDatabase.Refresh();

            Debug.Log("[UiSetup] 皮肤预览图已生成：" + abs);
        }

        // ============================================================
        // 3) 图标来源检查
        // ============================================================

        [MenuItem("My World/UI/检查图标来源", false, 30)]
        public static void CheckIconSources()
        {
            var kinds = (WeaponKind[])System.Enum.GetValues(typeof(WeaponKind));
            foreach (var kind in kinds)
            {
                Debug.Log("[UiSetup] " + kind + " → " + DescribeIconSource(kind));
            }
        }

        private static string DescribeIconSource(WeaponKind kind)
        {
            var projectSprite = AssetDatabase.LoadAssetAtPath<Sprite>(UiIconLibrary.ProjectFolder + kind + ".png");
            if (projectSprite != null) return "磁盘素材 " + UiIconLibrary.ProjectFolder + kind + ".png";
            var projectTex = AssetDatabase.LoadAssetAtPath<Texture2D>(UiIconLibrary.ProjectFolder + kind + ".png");
            if (projectTex != null) return "磁盘素材（Default 导入，代码包 Sprite）" + UiIconLibrary.ProjectFolder + kind + ".png";
            var resource = Resources.Load<Sprite>(UiIconLibrary.ResourcesFolder + kind);
            if (resource != null) return "Resources 镜像 " + UiIconLibrary.ResourcesFolder + kind;
            return "程序化绘制（磁盘与 Resources 都没有素材）";
        }

        // ============================================================
        // 图像工具（预览图专用）
        // ============================================================

        private static Texture2D NewSheet(int w, int h, Color32 clear)
        {
            var tex = new Texture2D(w, h, TextureFormat.RGBA32, false);
            var pixels = new Color32[w * h];
            for (int i = 0; i < pixels.Length; i++) pixels[i] = clear;
            tex.SetPixels32(pixels);
            tex.Apply(false, false);
            return tex;
        }

        /// <summary>把 Sprite 按九宫格真实拉伸画进预览图（border 从 Sprite 里取，拿不到就当普通缩放）。</summary>
        private static void DrawSlicedSprite(Texture2D sheet, int sheetW, Sprite sprite,
            int x, int y, int w, int h, float alpha, Color tint)
        {
            if (sprite == null || sprite.texture == null) return;

            Texture2D src;
            try
            {
                src = sprite.texture;
                src.GetPixels32();
            }
            catch
            {
                Debug.LogWarning("[UiSetup] 贴图不可读，跳过预览绘制：" + sprite.name);
                return;
            }

            Vector4 border = sprite.border;
            int bLeft = Mathf.RoundToInt(border.x);
            int bBottom = Mathf.RoundToInt(border.y);
            int bRight = Mathf.RoundToInt(border.z);
            int bTop = Mathf.RoundToInt(border.w);

            Color32[] dst = sheet.GetPixels32();
            Color32[] srcPix = src.GetPixels32();
            int sw = src.width, sh = src.height;

            for (int dy = 0; dy < h; dy++)
            {
                int sy = SliceCoordinate(dy, h, sh, bBottom, bTop);
                for (int dx = 0; dx < w; dx++)
                {
                    int sx = SliceCoordinate(dx, w, sw, bLeft, bRight);
                    Color32 sc = srcPix[sy * sw + sx];
                    Color c = (Color)sc;
                    c.a *= alpha;
                    c.r *= tint.r; c.g *= tint.g; c.b *= tint.b;
                    BlendPixel(dst, sheetW, sheet.height, x + dx, y + dy, c);
                }
            }
            sheet.SetPixels32(dst);
            sheet.Apply(false, false);
        }

        /// <summary>九宫格坐标映射：两端 border 区原样采样、中间区按比例缩放。</summary>
        private static int SliceCoordinate(int d, int destSize, int srcSize, int borderLow, int borderHigh)
        {
            if (d < borderLow) return Mathf.Clamp(d, 0, srcSize - 1);
            if (d >= destSize - borderHigh) return Mathf.Clamp(srcSize - (destSize - d), 0, srcSize - 1);

            int destMid = Mathf.Max(1, destSize - borderLow - borderHigh);
            int srcMid = Mathf.Max(1, srcSize - borderLow - borderHigh);
            float f = (d - borderLow + 0.5f) / destMid;
            return Mathf.Clamp(borderLow + Mathf.FloorToInt(f * srcMid), 0, srcSize - 1);
        }

        /// <summary>把 Sprite 画进预览图（简单最近邻缩放，看构图/配色够用）。</summary>
        private static void DrawIcon(Texture2D sheet, int sheetW, Sprite sprite, int x, int y, int w, int h)
        {
            if (sprite == null || sprite.texture == null) return;

            Texture2D src;
            Color32[] srcPix;
            try
            {
                src = sprite.texture;
                srcPix = src.GetPixels32();
            }
            catch
            {
                Debug.LogWarning("[UiSetup] 贴图不可读，跳过预览绘制：" + sprite.name);
                return;
            }

            Color32[] dst = sheet.GetPixels32();
            int sw = src.width, sh = src.height;
            for (int dy = 0; dy < h; dy++)
            {
                int sy = Mathf.Clamp(dy * sh / Mathf.Max(1, h), 0, sh - 1);
                for (int dx = 0; dx < w; dx++)
                {
                    int sx = Mathf.Clamp(dx * sw / Mathf.Max(1, w), 0, sw - 1);
                    BlendPixel(dst, sheetW, sheet.height, x + dx, y + dy, (Color)srcPix[sy * sw + sx]);
                }
            }
            sheet.SetPixels32(dst);
            sheet.Apply(false, false);
        }

        private static void BlendPixel(Color32[] dst, int dstW, int dstH, int x, int y, Color c)
        {
            if (x < 0 || y < 0 || x >= dstW || y >= dstH) return;
            if (c.a <= 0.001f) return;
            int i = y * dstW + x;
            Color32 d = dst[i];
            float da = d.a / 255f;
            float sa = c.a;
            float outA = sa + da * (1f - sa);
            if (outA <= 0.001f) return;
            float k = da * (1f - sa) / outA;
            float s = sa / outA;
            dst[i] = new Color32(
                (byte)Mathf.Clamp((c.r * s + d.r / 255f * k) * 255f, 0f, 255f),
                (byte)Mathf.Clamp((c.g * s + d.g / 255f * k) * 255f, 0f, 255f),
                (byte)Mathf.Clamp((c.b * s + d.b / 255f * k) * 255f, 0f, 255f),
                (byte)Mathf.Clamp(outA * 255f, 0f, 255f));
        }

        // ============================================================
        // 目录
        // ============================================================

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;

            string[] parts = path.Split('/');
            string current = parts[0];
            for (int i = 1; i < parts.Length; i++)
            {
                string next = current + "/" + parts[i];
                if (!AssetDatabase.IsValidFolder(next)) AssetDatabase.CreateFolder(current, parts[i]);
                current = next;
            }
        }
    }
}
