using UnityEngine;

namespace MyWorld.UI
{
    /// <summary>
    /// 程序化贴图绘制小库。
    ///
    /// 为什么不用素材：用户要求"中世纪羊皮纸+金边+墨棕"的 UI，但工程里没有对应素材，
    /// 也不允许导入外部图片。所以全部面板/图标都在运行期用 <see cref="Texture2D"/> 画出来，
    /// 再用 <see cref="Sprite.Create(Texture2D, Rect, Vector2, float, uint, SpriteMeshType, Vector4)"/>
    /// 变成 9-slice Sprite —— 零美术资源依赖，缩放时边角不糊。
    ///
    /// 坐标系：像素坐标 (0,0) 在**左下角**（和 Unity Texture2D 一致）。
    /// 所有形状都做了 1px 抗锯齿（用有向距离场算覆盖率），否则金线会锯齿得很明显。
    ///
    /// ⚠️ 生成的 Texture/Sprite 是运行时对象：退出 Play 后会被 Unity 销毁，
    /// 所以缓存字段一律要判 null 再重建（见 UiSkin / UiIconLibrary 的懒加载写法）。
    /// </summary>
    public sealed class UiCanvas
    {
        public readonly int Width;
        public readonly int Height;

        private readonly Color32[] pixels;

        public UiCanvas(int width, int height, Color clear)
        {
            Width = width;
            Height = height;
            pixels = new Color32[width * height];

            Color32 c = clear;
            for (int i = 0; i < pixels.Length; i++) pixels[i] = c;
        }

        // ---------------- 像素级 ----------------

        /// <summary>按"直通 alpha"做 over 混合。越界自动丢弃。</summary>
        public void Pixel(int x, int y, Color color, float alphaMul = 1f)
        {
            if (x < 0 || y < 0 || x >= Width || y >= Height) return;

            float sa = Mathf.Clamp01(color.a) * Mathf.Clamp01(alphaMul);
            if (sa <= 0.0005f) return;

            int i = y * Width + x;
            Color32 dst = pixels[i];
            float da = dst.a / 255f;
            float outA = sa + da * (1f - sa);
            if (outA <= 0.0005f)
            {
                pixels[i] = new Color32(0, 0, 0, 0);
                return;
            }

            float k = da * (1f - sa) / outA;
            float s = sa / outA;
            byte r = (byte)Mathf.Clamp(color.r * 255f * s + dst.r * k, 0f, 255f);
            byte g = (byte)Mathf.Clamp(color.g * 255f * s + dst.g * k, 0f, 255f);
            byte b = (byte)Mathf.Clamp(color.b * 255f * s + dst.b * k, 0f, 255f);
            pixels[i] = new Color32(r, g, b, (byte)Mathf.Clamp(outA * 255f, 0f, 255f));
        }

        /// <summary>直接覆盖（不混合），用于擦出透明区 / 精确边界。</summary>
        public void PixelRaw(int x, int y, Color color)
        {
            if (x < 0 || y < 0 || x >= Width || y >= Height) return;
            pixels[y * Width + x] = color;
        }

        // ---------------- 矩形 / 圆角矩形 ----------------

        public void Rect(float x, float y, float w, float h, Color color)
        {
            int x0 = Mathf.Max(0, Mathf.FloorToInt(x));
            int y0 = Mathf.Max(0, Mathf.FloorToInt(y));
            int x1 = Mathf.Min(Width - 1, Mathf.CeilToInt(x + w) - 1);
            int y1 = Mathf.Min(Height - 1, Mathf.CeilToInt(y + h) - 1);
            for (int py = y0; py <= y1; py++)
                for (int px = x0; px <= x1; px++)
                    Pixel(px, py, color);
        }

        /// <summary>圆角矩形（支持上下渐变色）。x/y = 左下角。</summary>
        public void RoundRect(float x, float y, float w, float h, float radius, Color top, Color bottom)
        {
            radius = Mathf.Min(radius, Mathf.Min(w, h) * 0.5f);
            float cx = x + w * 0.5f, cy = y + h * 0.5f;
            float hw = w * 0.5f, hh = h * 0.5f;

            int x0 = Mathf.Max(0, Mathf.FloorToInt(x - 1f));
            int y0 = Mathf.Max(0, Mathf.FloorToInt(y - 1f));
            int x1 = Mathf.Min(Width - 1, Mathf.CeilToInt(x + w + 1f));
            int y1 = Mathf.Min(Height - 1, Mathf.CeilToInt(y + h + 1f));

            for (int py = y0; py <= y1; py++)
            {
                float t = Mathf.Clamp01((py + 0.5f - y) / Mathf.Max(h, 0.001f));
                Color color = Color.LerpUnclamped(top, bottom, t);
                for (int px = x0; px <= x1; px++)
                {
                    float d = RoundRectDistance(px + 0.5f, py + 0.5f, cx, cy, hw, hh, radius);
                    float a = Mathf.Clamp01(0.5f - d);
                    if (a > 0f) Pixel(px, py, color, a);
                }
            }
        }

        public void RoundRect(float x, float y, float w, float h, float radius, Color color)
        {
            RoundRect(x, y, w, h, radius, color, color);
        }

        /// <summary>圆角矩形描边（粗细 thickness，居中对齐到边界）。</summary>
        public void RoundRectRing(float x, float y, float w, float h, float radius, float thickness, Color color)
        {
            float cx = x + w * 0.5f, cy = y + h * 0.5f;
            float hw = w * 0.5f, hh = h * 0.5f;
            float half = Mathf.Max(thickness, 0.1f) * 0.5f;

            int x0 = Mathf.Max(0, Mathf.FloorToInt(x - thickness - 1f));
            int y0 = Mathf.Max(0, Mathf.FloorToInt(y - thickness - 1f));
            int x1 = Mathf.Min(Width - 1, Mathf.CeilToInt(x + w + thickness + 1f));
            int y1 = Mathf.Min(Height - 1, Mathf.CeilToInt(y + h + thickness + 1f));

            for (int py = y0; py <= y1; py++)
            {
                for (int px = x0; px <= x1; px++)
                {
                    float d = RoundRectDistance(px + 0.5f, py + 0.5f, cx, cy, hw, hh, radius);
                    float a = Mathf.Clamp01(0.5f - (Mathf.Abs(d) - half));
                    if (a > 0f) Pixel(px, py, color, a);
                }
            }
        }

        // ---------------- 圆 / 环 / 弧 ----------------

        public void Circle(float cx, float cy, float radius, Color color)
        {
            Circle(cx, cy, radius, color, color);
        }

        /// <summary>圆（上下渐变）。</summary>
        public void Circle(float cx, float cy, float radius, Color top, Color bottom)
        {
            if (radius <= 0f) return;
            int x0 = Mathf.Max(0, Mathf.FloorToInt(cx - radius - 1f));
            int y0 = Mathf.Max(0, Mathf.FloorToInt(cy - radius - 1f));
            int x1 = Mathf.Min(Width - 1, Mathf.CeilToInt(cx + radius + 1f));
            int y1 = Mathf.Min(Height - 1, Mathf.CeilToInt(cy + radius + 1f));

            for (int py = y0; py <= y1; py++)
            {
                float t = Mathf.Clamp01((py + 0.5f - (cy - radius)) / (radius * 2f));
                Color color = Color.LerpUnclamped(top, bottom, t);
                for (int px = x0; px <= x1; px++)
                {
                    float dx = px + 0.5f - cx, dy = py + 0.5f - cy;
                    float d = Mathf.Sqrt(dx * dx + dy * dy) - radius;
                    float a = Mathf.Clamp01(0.5f - d);
                    if (a > 0f) Pixel(px, py, color, a);
                }
            }
        }

        public void Ellipse(float cx, float cy, float rx, float ry, Color color)
        {
            Ellipse(cx, cy, rx, ry, 0f, color, color);
        }

        /// <summary>椭圆（上下渐变）。feather = 边缘柔化像素：0 = 1px 抗锯齿硬边，&gt;0 = 向外柔和过渡（画阴影用）。</summary>
        public void Ellipse(float cx, float cy, float rx, float ry, float feather, Color color)
        {
            Ellipse(cx, cy, rx, ry, feather, color, color);
        }

        /// <summary>椭圆（上下渐变 + 柔边）。x/y 中心，rx/ry 半径。</summary>
        public void Ellipse(float cx, float cy, float rx, float ry, float feather, Color top, Color bottom)
        {
            if (rx <= 0.001f || ry <= 0.001f) return;
            feather = Mathf.Max(0f, feather);
            float pad = feather + 2f;
            int x0 = Mathf.Max(0, Mathf.FloorToInt(cx - rx - pad));
            int y0 = Mathf.Max(0, Mathf.FloorToInt(cy - ry - pad));
            int x1 = Mathf.Min(Width - 1, Mathf.CeilToInt(cx + rx + pad));
            int y1 = Mathf.Min(Height - 1, Mathf.CeilToInt(cy + ry + pad));
            float invRx = 1f / rx, invRy = 1f / ry;
            float minR = Mathf.Min(rx, ry);

            for (int py = y0; py <= y1; py++)
            {
                float t = Mathf.Clamp01((py + 0.5f - (cy - ry)) / (ry * 2f));
                Color color = Color.LerpUnclamped(top, bottom, t);
                for (int px = x0; px <= x1; px++)
                {
                    float dx = (px + 0.5f - cx) * invRx;
                    float dy = (py + 0.5f - cy) * invRy;
                    float d = Mathf.Sqrt(dx * dx + dy * dy);
                    // 归一化距离 → 近似像素距离，再做 1px 硬边 / feather 宽容的柔边
                    float sdf = (d - 1f) * minR;
                    float a = feather > 0.0001f
                        ? Mathf.Clamp01(1f - sdf / feather)
                        : Mathf.Clamp01(0.5f - sdf);
                    if (a > 0f) Pixel(px, py, color, a);
                }
            }
        }

        /// <summary>圆环（粗细 thickness）。</summary>
        public void Ring(float cx, float cy, float radius, float thickness, Color color)
        {
            float half = Mathf.Max(thickness, 0.1f) * 0.5f;
            float outer = radius + half + 1f;
            int x0 = Mathf.Max(0, Mathf.FloorToInt(cx - outer));
            int y0 = Mathf.Max(0, Mathf.FloorToInt(cy - outer));
            int x1 = Mathf.Min(Width - 1, Mathf.CeilToInt(cx + outer));
            int y1 = Mathf.Min(Height - 1, Mathf.CeilToInt(cy + outer));

            for (int py = y0; py <= y1; py++)
                for (int px = x0; px <= x1; px++)
                {
                    float dx = px + 0.5f - cx, dy = py + 0.5f - cy;
                    float d = Mathf.Abs(Mathf.Sqrt(dx * dx + dy * dy) - radius) - half;
                    float a = Mathf.Clamp01(0.5f - d);
                    if (a > 0f) Pixel(px, py, color, a);
                }
        }

        /// <summary>圆弧（角度制，0°=右，逆时针；用于角饰卷草纹）。</summary>
        public void Arc(float cx, float cy, float radius, float fromDeg, float toDeg, float thickness, Color color)
        {
            float half = Mathf.Max(thickness, 0.1f) * 0.5f;
            float outer = radius + half + 1f;
            int x0 = Mathf.Max(0, Mathf.FloorToInt(cx - outer));
            int y0 = Mathf.Max(0, Mathf.FloorToInt(cy - outer));
            int x1 = Mathf.Min(Width - 1, Mathf.CeilToInt(cx + outer));
            int y1 = Mathf.Min(Height - 1, Mathf.CeilToInt(cy + outer));

            float a0 = Mathf.Min(fromDeg, toDeg);
            float a1 = Mathf.Max(fromDeg, toDeg);

            for (int py = y0; py <= y1; py++)
                for (int px = x0; px <= x1; px++)
                {
                    float dx = px + 0.5f - cx, dy = py + 0.5f - cy;
                    float dist = Mathf.Sqrt(dx * dx + dy * dy);
                    if (dist < radius - half - 1f || dist > radius + half + 1f) continue;

                    float ang = Mathf.Atan2(dy, dx) * Mathf.Rad2Deg;
                    while (ang < 0f) ang += 360f;
                    bool inside = false;
                    if (a1 - a0 >= 359f) inside = true;
                    else
                    {
                        for (int k = -1; k <= 1 && !inside; k++)
                        {
                            float a = ang + k * 360f;
                            if (a >= a0 && a <= a1) inside = true;
                        }
                    }
                    if (!inside) continue;

                    float d = Mathf.Abs(dist - radius) - half;
                    float alpha = Mathf.Clamp01(0.5f - d);
                    if (alpha > 0f) Pixel(px, py, color, alpha);
                }
        }

        // ---------------- 线 / 多边形 ----------------

        /// <summary>两点之间的胶囊线（带 1px 抗锯齿）。</summary>
        public void Line(Vector2 a, Vector2 b, float thickness, Color color)
        {
            float half = Mathf.Max(thickness, 0.5f) * 0.5f;
            int x0 = Mathf.Max(0, Mathf.FloorToInt(Mathf.Min(a.x, b.x) - half - 2f));
            int y0 = Mathf.Max(0, Mathf.FloorToInt(Mathf.Min(a.y, b.y) - half - 2f));
            int x1 = Mathf.Min(Width - 1, Mathf.CeilToInt(Mathf.Max(a.x, b.x) + half + 2f));
            int y1 = Mathf.Min(Height - 1, Mathf.CeilToInt(Mathf.Max(a.y, b.y) + half + 2f));

            for (int py = y0; py <= y1; py++)
                for (int px = x0; px <= x1; px++)
                {
                    float d = DistanceToSegment(new Vector2(px + 0.5f, py + 0.5f), a, b) - half;
                    float alpha = Mathf.Clamp01(0.5f - d);
                    if (alpha > 0f) Pixel(px, py, color, alpha);
                }
        }

        /// <summary>向量的线（带锥形——用于剑刃/法杖杆的粗细变化）。</summary>
        public void TaperLine(Vector2 a, Vector2 b, float thickA, float thickB, Color color)
        {
            float maxHalf = Mathf.Max(thickA, thickB) * 0.5f;
            int x0 = Mathf.Max(0, Mathf.FloorToInt(Mathf.Min(a.x, b.x) - maxHalf - 2f));
            int y0 = Mathf.Max(0, Mathf.FloorToInt(Mathf.Min(a.y, b.y) - maxHalf - 2f));
            int x1 = Mathf.Min(Width - 1, Mathf.CeilToInt(Mathf.Max(a.x, b.x) + maxHalf + 2f));
            int y1 = Mathf.Min(Height - 1, Mathf.CeilToInt(Mathf.Max(a.y, b.y) + maxHalf + 2f));

            Vector2 ab = b - a;
            float len2 = Mathf.Max(ab.sqrMagnitude, 0.0001f);

            for (int py = y0; py <= y1; py++)
                for (int px = x0; px <= x1; px++)
                {
                    Vector2 p = new Vector2(px + 0.5f, py + 0.5f);
                    float t = Mathf.Clamp01(Vector2.Dot(p - a, ab) / len2);
                    float half = Mathf.Lerp(thickA, thickB, t) * 0.5f;
                    float d = Vector2.Distance(p, a + ab * t) - half;
                    float alpha = Mathf.Clamp01(0.5f - d);
                    if (alpha > 0f) Pixel(px, py, color, alpha);
                }
        }

        /// <summary>任意简单多边形填充（2x2 超采样抗锯齿；点按顺序给，凹凸均可）。</summary>
        public void Polygon(Vector2[] pts, Color color)
        {
            if (pts == null || pts.Length < 3) return;

            float minX = pts[0].x, maxX = pts[0].x, minY = pts[0].y, maxY = pts[0].y;
            for (int i = 1; i < pts.Length; i++)
            {
                minX = Mathf.Min(minX, pts[i].x); maxX = Mathf.Max(maxX, pts[i].x);
                minY = Mathf.Min(minY, pts[i].y); maxY = Mathf.Max(maxY, pts[i].y);
            }

            int x0 = Mathf.Max(0, Mathf.FloorToInt(minX - 1f));
            int y0 = Mathf.Max(0, Mathf.FloorToInt(minY - 1f));
            int x1 = Mathf.Min(Width - 1, Mathf.CeilToInt(maxX + 1f));
            int y1 = Mathf.Min(Height - 1, Mathf.CeilToInt(maxY + 1f));

            for (int py = y0; py <= y1; py++)
                for (int px = x0; px <= x1; px++)
                {
                    int hit = 0;
                    for (int sy = 0; sy < 2; sy++)
                        for (int sx = 0; sx < 2; sx++)
                        {
                            float x = px + 0.25f + sx * 0.5f;
                            float y = py + 0.25f + sy * 0.5f;
                            if (PointInPolygon(pts, x, y)) hit++;
                        }
                    if (hit > 0) Pixel(px, py, color, hit / 4f);
                }
        }

        public void Polygon(Color color, params Vector2[] pts)
        {
            Polygon(pts, color);
        }

        // ---------------- 杂项 ----------------

        /// <summary>细金属高光：一条 1px 半透明线，让金边看起来有厚度。</summary>
        public void Glow(float x, float y, float length, Color color, bool horizontal = true, float thickness = 1f)
        {
            if (horizontal) Rect(x, y, length, thickness, color);
            else Rect(x, y, thickness, length, color);
        }

        /// <summary>随机纤维/麻点（羊皮纸的脏旧感）。rng 必须由调用方给固定种子，保证每次生成一样。</summary>
        public void Speckles(int count, Color color, float minX, float minY, float maxX, float maxY, System.Random rng, float maxLen = 6f)
        {
            if (rng == null) rng = new System.Random(12345);
            for (int i = 0; i < count; i++)
            {
                float x = Mathf.Lerp(minX, maxX, (float)rng.NextDouble());
                float y = Mathf.Lerp(minY, maxY, (float)rng.NextDouble());
                float len = 1f + (float)rng.NextDouble() * maxLen;
                float ang = (float)rng.NextDouble() * Mathf.PI;
                Vector2 d = new Vector2(Mathf.Cos(ang), Mathf.Sin(ang)) * len;
                Line(new Vector2(x, y), new Vector2(x + d.x, y + d.y), 0.8f, color);
            }
        }

        /// <summary>把画布烤成可被 Sprite 引用的贴图。</summary>
        public Texture2D Bake()
        {
            var tex = new Texture2D(Width, Height, TextureFormat.RGBA32, false)
            {
                hideFlags = HideFlags.DontSave,
                filterMode = FilterMode.Bilinear,
                wrapMode = TextureWrapMode.Clamp,
                name = "UiGenerated",
            };
            tex.SetPixels32(pixels);
            tex.Apply(false, false);
            return tex;
        }

        /// <summary>烤成 Sprite。border = (left, bottom, right, top)，单位像素；全 0 = 不九宫格。</summary>
        public Sprite BakeSprite(Vector4 border)
        {
            var tex = Bake();
            var sprite = Sprite.Create(tex, new Rect(0f, 0f, Width, Height), new Vector2(0.5f, 0.5f),
                100f, 0, SpriteMeshType.FullRect, border);
            sprite.hideFlags = HideFlags.DontSave;
            sprite.name = tex.name;
            return sprite;
        }

        // ---------------- 几何辅助 ----------------

        private static float RoundRectDistance(float px, float py, float cx, float cy, float halfW, float halfH, float radius)
        {
            float qx = Mathf.Abs(px - cx) - (halfW - radius);
            float qy = Mathf.Abs(py - cy) - (halfH - radius);
            float ax = Mathf.Max(qx, 0f), ay = Mathf.Max(qy, 0f);
            return Mathf.Sqrt(ax * ax + ay * ay) + Mathf.Min(Mathf.Max(qx, qy), 0f) - radius;
        }

        private static float DistanceToSegment(Vector2 p, Vector2 a, Vector2 b)
        {
            Vector2 ab = b - a;
            float len2 = ab.sqrMagnitude;
            if (len2 <= 0.000001f) return Vector2.Distance(p, a);
            float t = Mathf.Clamp01(Vector2.Dot(p - a, ab) / len2);
            return Vector2.Distance(p, a + ab * t);
        }

        private static bool PointInPolygon(Vector2[] pts, float x, float y)
        {
            bool inside = false;
            int n = pts.Length;
            for (int i = 0, j = n - 1; i < n; j = i++)
            {
                Vector2 pi = pts[i], pj = pts[j];
                if (((pi.y > y) != (pj.y > y)) &&
                    (x < (pj.x - pi.x) * (y - pi.y) / (pj.y - pi.y + 0.0000001f) + pi.x))
                    inside = !inside;
            }
            return inside;
        }
    }

    /// <summary>颜色/贴图相关的静态小工具。</summary>
    public static class UiColor
    {
        /// <summary>"#RRGGBB" 或 "#RRGGBBAA" → Color。解析失败返回洋红（好定位错字）。</summary>
        public static Color Hex(string hex)
        {
            if (string.IsNullOrEmpty(hex)) return Color.magenta;
            if (hex[0] == '#') hex = hex.Substring(1);
            if (hex.Length != 6 && hex.Length != 8) return Color.magenta;

            int r = ParseByte(hex, 0);
            int g = ParseByte(hex, 2);
            int b = ParseByte(hex, 4);
            int a = hex.Length == 8 ? ParseByte(hex, 6) : 255;
            return new Color(r / 255f, g / 255f, b / 255f, a / 255f);
        }

        /// <summary>同色加透明度。</summary>
        public static Color Alpha(this Color c, float a)
        {
            c.a = a;
            return c;
        }

        /// <summary>按比例调亮/调暗（0.8=暗一点，1.2=亮一点）。</summary>
        public static Color Shade(this Color c, float mul)
        {
            return new Color(Mathf.Clamp01(c.r * mul), Mathf.Clamp01(c.g * mul), Mathf.Clamp01(c.b * mul), c.a);
        }

        private static int ParseByte(string hex, int start)
        {
            int hi = HexDigit(hex[start]);
            int lo = HexDigit(hex[start + 1]);
            if (hi < 0 || lo < 0) return 255;
            return hi * 16 + lo;
        }

        private static int HexDigit(char c)
        {
            if (c >= '0' && c <= '9') return c - '0';
            if (c >= 'a' && c <= 'f') return c - 'a' + 10;
            if (c >= 'A' && c <= 'F') return c - 'A' + 10;
            return -1;
        }
    }
}
