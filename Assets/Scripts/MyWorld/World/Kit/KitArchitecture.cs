using System.Collections.Generic;
using UnityEngine;

namespace MyWorld
{
    // ============================================================================================
    // 建筑生成器：民居 / 城墙 / 塔楼（其余 Inn / GuildHall / CastleGate / MarketStall / Fountain /
    // Well / QuestBoard 在 KitBuildings.cs 的同一 partial 类里）。
    //
    // 全部纯 C# 运行期生成：不读 AssetDatabase / Resources，材质只走 MapMaterials，
    // 几何只用 Kit 原语 + 自建 Mesh（坡屋顶/三角山墙），因此 Play 里可以直接调。
    // 坐标语义：pos/yaw 都是**父节点局部空间**；返回的根节点已摆在 pos 上。
    // 尺度参照：角色身高 1.5m、门高 2.1m、一层高 2.8~3.0m。
    // ============================================================================================
    public static partial class KitArchitecture
    {
        // ---------------------------------------------------------------- 共用材质（懒加载缓存）
        static Material _winLit;
        static Material _winDay;
        static Material _iron;
        static Material _woodPlank;
        static Material _flowerRed;
        static Material _flowerOrange;
        static Material _flowerCream;

        static Material WinLit()
        {
            if (_winLit == null) _winLit = KitMat.Emi("kit_win_lit", new Color(1f, 0.80f, 0.46f), 1.25f);
            return _winLit;
        }

        static Material WinDay()
        {
            // 白天窗：淡蓝玻璃自发光一点点，保证俯视相机下能看清"这里有窗"
            if (_winDay == null) _winDay = KitMat.Emi("kit_win_day", new Color(0.52f, 0.70f, 0.85f), 0.32f);
            return _winDay;
        }

        static Material Iron()
        {
            if (_iron == null) _iron = MapMaterials.Get("iron");
            return _iron;
        }

        static Material DoorWood()
        {
            if (_woodPlank == null) _woodPlank = KitMat.WoodTinted("wood_plank");
            return _woodPlank;
        }

        static Material Flower(int i)
        {
            switch (i % 3)
            {
                case 0: if (_flowerRed == null) _flowerRed = KitMat.Solid("kit_flower_red", MapMaterials.ClothRed); return _flowerRed;
                case 1: if (_flowerOrange == null) _flowerOrange = KitMat.Solid("kit_flower_org", MapMaterials.ClothOrange); return _flowerOrange;
                default: if (_flowerCream == null) _flowerCream = KitMat.Solid("kit_flower_crm", MapMaterials.ClothCream); return _flowerCream;
            }
        }

        // ---------------------------------------------------------------- 共用小工具
        /// <summary>不可见的碰撞盒（每个建筑只留一个，压 GameObject/Collider 数量）。</summary>
        static GameObject Blocker(Transform parent, string name, Vector3 size, Vector3 pos)
        {
            return Kit.Blocker(parent, name, size, pos);
        }

        /// <summary>一个立面的局部坐标系：+X 沿墙、+Y 上、+Z 朝外。窗/木筋/招牌都在这个坐标系里建。</summary>
        static Transform Facade(Transform parent, string name, Vector3 pos, float yaw)
        {
            return Kit.Pivot(parent, name, pos, yaw).transform;
        }

        /// <summary>
        /// 窗：木框 + 十字窗棂 + 窗台石 + 可选百叶 + 可选窗下花箱。
        /// 本地原点 = 窗中心，+Z 朝外；pane 自带一点自发光，远看不会糊成黑块。
        /// </summary>
        static void Window(Transform face, string name, Vector3 pos, float w, float h, bool lit,
            bool shutters, bool flowerBox, Material frameMat)
        {
            var piv = Kit.Pivot(face, name, pos, 0f);
            var t = piv.transform;
            Kit.Box(t, "Pane", new Vector3(w, h, 0.05f), new Vector3(0f, 0f, 0.012f), lit ? WinLit() : WinDay(), 0f, false);
            float ft = 0.085f;
            Kit.Box(t, "FrameT", new Vector3(w + ft * 2f, ft, 0.13f), new Vector3(0f, h * 0.5f + ft * 0.5f, 0.04f), frameMat, 0f, false);
            Kit.Box(t, "FrameB", new Vector3(w + ft * 2f, ft, 0.13f), new Vector3(0f, -h * 0.5f - ft * 0.5f, 0.04f), frameMat, 0f, false);
            Kit.Box(t, "FrameL", new Vector3(ft, h, 0.13f), new Vector3(-w * 0.5f - ft * 0.5f, 0f, 0.04f), frameMat, 0f, false);
            Kit.Box(t, "FrameR", new Vector3(ft, h, 0.13f), new Vector3(w * 0.5f + ft * 0.5f, 0f, 0.04f), frameMat, 0f, false);
            Kit.Box(t, "MullionV", new Vector3(0.05f, h, 0.08f), new Vector3(0f, 0f, 0.045f), frameMat, 0f, false);
            Kit.Box(t, "MullionH", new Vector3(w, 0.05f, 0.08f), new Vector3(0f, h * 0.10f, 0.045f), frameMat, 0f, false);
            Kit.Box(t, "Sill", new Vector3(w + 0.36f, 0.09f, 0.26f), new Vector3(0f, -h * 0.5f - 0.11f, 0.10f),
                KitMat.Stone("stone_light"), 0f, false);

            if (shutters)
            {
                float sw = w * 0.46f, sh = h * 0.96f;
                float sx = w * 0.5f + ft + sw * 0.5f;
                Kit.BoxRot(t, "ShutterL", new Vector3(sw, sh, 0.05f), new Vector3(-sx, 0f, 0.075f),
                    Quaternion.Euler(0f, 20f, 0f), KitMat.Timber("timber_mid"), false);
                Kit.BoxRot(t, "ShutterR", new Vector3(sw, sh, 0.05f), new Vector3(sx, 0f, 0.075f),
                    Quaternion.Euler(0f, -20f, 0f), KitMat.Timber("timber_mid"), false);
            }

            if (flowerBox)
            {
                var boxMat = KitMat.WoodTinted("wood_dark");
                Kit.Box(t, "FlowerBox", new Vector3(w * 0.86f, 0.16f, 0.24f), new Vector3(0f, -h * 0.5f - 0.24f, 0.17f), boxMat, 0f, false);
                for (int i = 0; i < 3; i++)
                {
                    float fx = (i - 1) * w * 0.26f;
                    Kit.Sphere(t, "Flower", 0.085f, new Vector3(fx, -h * 0.5f - 0.13f, 0.2f), Flower(i), false, 8);
                }
            }
        }

        /// <summary>门：木门板 + 门框 + 半圆石拱 + 台阶。本地原点 = 地面门中心，+Z 朝外。</summary>
        static void Door(Transform face, Vector3 pos, bool arch)
        {
            var piv = Kit.Pivot(face, "Door", pos, 0f);
            var t = piv.transform;
            float dw = 1.16f, dh = Kit.DoorHeight;
            Kit.Box(t, "Slab", new Vector3(dw, dh, 0.12f), new Vector3(0f, dh * 0.5f, 0.06f), DoorWood(), 0f, false);
            for (int i = 0; i < 3; i++)
                Kit.Box(t, "Plank", new Vector3(dw * 1.02f, 0.055f, 0.03f),
                    new Vector3(0f, dh * (0.22f + 0.27f * i), 0.13f), KitMat.WoodTinted("wood_dark"), 0f, false);
            Kit.Box(t, "Handle", new Vector3(0.09f, 0.09f, 0.07f), new Vector3(dw * 0.33f, dh * 0.48f, 0.15f), Iron(), 0f, false);
            Kit.Box(t, "PostL", new Vector3(0.16f, dh + 0.16f, 0.2f), new Vector3(-dw * 0.5f - 0.08f, (dh + 0.16f) * 0.5f, 0.05f),
                KitMat.Timber("timber_dark"), 0f, false);
            Kit.Box(t, "PostR", new Vector3(0.16f, dh + 0.16f, 0.2f), new Vector3(dw * 0.5f + 0.08f, (dh + 0.16f) * 0.5f, 0.05f),
                KitMat.Timber("timber_dark"), 0f, false);
            Kit.Box(t, "Lintel", new Vector3(dw + 0.34f, 0.2f, 0.26f), new Vector3(0f, dh + 0.18f, 0.06f),
                KitMat.Stone("stone_light"), 0f, false);
            if (arch)
            {
                int n = 7;
                float r = dw * 0.62f;
                var stone = KitMat.Stone("stone_light");
                for (int i = 0; i < n; i++)
                {
                    float a = Mathf.PI * (i / (float)(n - 1));
                    float ax = Mathf.Cos(a) * r;
                    float ay = Mathf.Sin(a) * r;
                    Kit.BoxRot(t, "Arch", new Vector3(0.18f, 0.34f, 0.2f),
                        new Vector3(ax, dh + 0.3f + ay, 0.07f),
                        Quaternion.Euler(0f, 0f, a * Mathf.Rad2Deg), stone, false);
                }
            }
            Kit.Box(t, "Step1", new Vector3(dw + 0.7f, 0.14f, 0.62f), new Vector3(0f, 0.07f, 0.36f), KitMat.Stone("stone_light"), 0f, false);
            Kit.Box(t, "Step2", new Vector3(dw + 1.0f, 0.09f, 0.95f), new Vector3(0f, 0.045f, 0.40f), KitMat.Stone("stone_dark"), 0f, false);
        }

        /// <summary>墙挂铁艺灯笼（默认只自发光，不建点光；需要点光的地标再单独加）。</summary>
        static GameObject WallLantern(Transform face, string name, Vector3 pos, bool light = false)
        {
            var piv = Kit.Pivot(face, name, pos, 0f);
            var t = piv.transform;
            var iron = Iron();
            Kit.Box(t, "Arm", new Vector3(0.06f, 0.06f, 0.3f), new Vector3(0f, 0.22f, 0.15f), iron, 0f, false);
            Kit.Box(t, "Stem", new Vector3(0.06f, 0.22f, 0.06f), new Vector3(0f, 0.33f, 0.0f), iron, 0f, false);
            Kit.Box(t, "Chain", new Vector3(0.03f, 0.14f, 0.03f), new Vector3(0f, 0.16f, 0.3f), iron, 0f, false);
            Kit.Box(t, "Top", new Vector3(0.26f, 0.06f, 0.26f), new Vector3(0f, 0.08f, 0.3f), iron, 0f, false);
            Kit.Box(t, "Glow", new Vector3(0.2f, 0.24f, 0.2f), new Vector3(0f, -0.06f, 0.3f),
                KitMat.Emi("kit_lantern_glow", MapMaterials.GlowWarm, 2.4f), 0f, false);
            Kit.Box(t, "Bottom", new Vector3(0.24f, 0.05f, 0.24f), new Vector3(0f, -0.2f, 0.3f), iron, 0f, false);
            Kit.Box(t, "Cap", new Vector3(0.1f, 0.08f, 0.1f), new Vector3(0f, 0.14f, 0.3f), iron, 0f, false);
            if (light) Kit.PointLight(t, new Vector3(0f, -0.05f, 0.3f), MapMaterials.GlowWarm, 3.6f, 1.1f);
            return piv;
        }

        /// <summary>某一层的窗列位置（本地 X）。有门的底层让开中间，宽的立面给 3 列。</summary>
        static List<float> WindowCols(float width, bool ground, bool hasDoor)
        {
            var list = new List<float>(3);
            if (ground && hasDoor)
            {
                if (width >= 5.0f)
                {
                    list.Add(-width * 0.31f);
                    list.Add(width * 0.31f);
                }
                else if (width >= 3.5f) list.Add(width * 0.28f);
            }
            else
            {
                if (width >= 6.6f)
                {
                    list.Add(-width * 0.29f);
                    list.Add(0f);
                    list.Add(width * 0.29f);
                }
                else if (width >= 3.2f)
                {
                    list.Add(-width * 0.26f);
                    list.Add(width * 0.26f);
                }
            }
            return list;
        }

        /// <summary>在某个立面上铺窗（face 的局部坐标：x 沿墙、y 世界高度原点=地面）。</summary>
        static void WindowsOnFace(Transform face, string tag, float faceW, float y0, float perFloor, int floors,
            Material frameMat, ref KitRand rnd, bool doorFace, bool trims)
        {
            for (int f = 0; f < floors; f++)
            {
                var cols = WindowCols(faceW, f == 0, doorFace);
                float cy = y0 + f * perFloor + perFloor * 0.56f;
                for (int i = 0; i < cols.Count; i++)
                {
                    float w = f == 0 ? 0.95f : 0.86f;
                    float h = f == 0 ? 1.15f : 1.02f;
                    bool lit = rnd.Chance(0.3f);
                    bool flower = trims && f == 0 && faceW > 3.6f && rnd.Chance(0.45f);
                    Window(face, tag + "W" + f + "_" + i, new Vector3(cols[i], cy, 0.02f), w, h, lit, true, flower, frameMat);
                }
            }
        }

        /// <summary>木筋立面：层间横带 + 竖向立柱 + 底层斜撑。木梁比墙面凸出 2cm 才不会 z-fighting。</summary>
        static void FacadeTimber(Transform face, float width, float y0, float perFloor, int floors,
            Material timberMat, bool front, KitRand rnd)
        {
            int bays = Mathf.Clamp(Mathf.RoundToInt(width / 1.55f), 2, 4);
            float bw = width / bays;
            for (int f = 0; f < floors; f++)
            {
                float fy = y0 + f * perFloor;
                for (int i = 0; i <= bays; i++)
                {
                    float x = -width * 0.5f + bw * i;
                    if (front && f == 0 && Mathf.Abs(x) < 0.9f) continue; // 让开门洞
                    Kit.Box(face, "Stud", new Vector3(0.15f, perFloor - 0.12f, 0.11f),
                        new Vector3(x, fy + perFloor * 0.5f, 0.02f), timberMat, 0f, false);
                }
                if (f == 0)
                {
                    int nb = front ? 2 : 1;
                    for (int b = 0; b < nb; b++)
                    {
                        int bay = front ? (b == 0 ? 0 : bays - 1) : (b % bays);
                        float cx = -width * 0.5f + bw * (bay + 0.5f);
                        float sign = (b % 2 == 0) ? 1f : -1f;
                        float len = Mathf.Sqrt(bw * bw + perFloor * perFloor) * 0.86f;
                        Kit.BoxRot(face, "Brace", new Vector3(len, 0.12f, 0.09f),
                            new Vector3(cx, fy + perFloor * 0.5f, 0.03f),
                            Quaternion.Euler(0f, 0f, sign * Mathf.Atan2(perFloor, bw) * Mathf.Rad2Deg),
                            timberMat, false);
                    }
                }
            }
        }

        /// <summary>山墙面的木筋（中柱 + 横梁 + 两条斜撑）。face 原点 = 山墙底边中心，+Z 朝外。</summary>
        static void GableTimber(Transform parent, string name, Vector3 pos, float yaw, float span, float roofH, Material timberMat)
        {
            if (timberMat == null) return;
            var face = Facade(parent, name, pos, yaw);
            float half = span * 0.5f;
            // 中柱 + 横梁
            Kit.Box(face, "KingPost", new Vector3(0.13f, roofH * 0.8f, 0.11f), new Vector3(0f, roofH * 0.4f, 0.15f), timberMat, 0f, false);
            Kit.Box(face, "TieBeam", new Vector3(span * 0.9f, 0.14f, 0.12f), new Vector3(0f, roofH * 0.42f, 0.15f), timberMat, 0f, false);
            // 两条斜撑（贴瓦坡下缘）
            for (int s = 0; s < 2; s++)
            {
                float sign = s == 0 ? 1f : -1f;
                float len = Mathf.Sqrt(half * half + roofH * roofH) * 0.82f;
                float ang = Mathf.Atan2(roofH, half) * Mathf.Rad2Deg * sign;
                Kit.BoxRot(face, "Rafter", new Vector3(len, 0.12f, 0.1f),
                    new Vector3(sign * half * 0.45f, roofH * 0.46f, 0.15f),
                    Quaternion.Euler(0f, 0f, ang), timberMat, false);
            }
        }

        /// <summary>山墙上的圆窗（木圈 + 淡蓝玻璃）。face 原点 = 山墙底边中心，+Z 朝外。</summary>
        static void GableWindow(Transform face, string name, Vector3 pos, float radius)
        {
            var piv = Kit.Pivot(face, name, pos, 0f);
            var t = piv.transform;
            Kit.CylRot(t, "Ring", radius, 0.08f, Vector3.zero, Quaternion.Euler(90f, 0f, 0f),
                KitMat.Timber("timber_mid"), 12, false);
            Kit.CylRot(t, "Glass", radius * 0.76f, 0.05f, new Vector3(0f, 0f, 0.03f), Quaternion.Euler(90f, 0f, 0f),
                WinDay(), 12, false);
        }

        // ============================================================================================
        // 民居
        // ============================================================================================
        /// <summary>
        /// 一间中世纪民居。结构：石基座 + 墙体 + 木筋 + 窗 + 门 + 人字坡屋顶（自建 Mesh，带出檐）+
        /// 山墙三角 + 圆窗 + 烟囱冒烟 + 可选阳台/招牌/挂灯。整栋只留 1 个碰撞盒。
        /// 约 120~220 个 primitive（两层带阳台的版本接近上限）。
        /// </summary>
        public static GameObject House(Transform parent, HouseSpec spec, Vector3 pos, float yaw = 0f)
        {
            if (spec == null) spec = new HouseSpec();
            float finalYaw = yaw + spec.Yaw;
            int seed = spec.Seed != 0
                ? spec.Seed
                : KitRand.SeedFrom(pos, Mathf.RoundToInt(spec.Width * 13f + spec.Depth * 7f + spec.Floors * 31f + finalYaw));
            var rnd = new KitRand(seed);

            var root = Kit.Pivot(parent, "House", pos, finalYaw);
            var t = root.transform;

            float W = Mathf.Max(2.4f, spec.Width);
            float D = Mathf.Max(2.4f, spec.Depth);
            int floors = Mathf.Clamp(spec.Floors, 1, 3);
            float perFloor = Mathf.Max(2.5f, spec.WallHeight);
            float bodyH = perFloor * floors;
            const float y0 = 0.4f;                       // 石基座高度
            float wallTop = y0 + bodyH;
            float overhang = Mathf.Max(0f, spec.Overhang);
            bool ridgeX = spec.RidgeAlongWidth;

            var wallMat = KitMat.Wall(spec.Wall);
            var roofMat = KitMat.Roof(spec.Roof);
            var timberMat = string.IsNullOrEmpty(spec.Timber) ? null : KitMat.Timber(spec.Timber);
            var frameMat = timberMat != null ? timberMat : KitMat.Timber("timber_mid");

            // ---- 石基座 / 墙体 / 单一碰撞盒 ----
            Kit.Box(t, "Foundation", new Vector3(W + 0.18f, y0, D + 0.18f), new Vector3(0f, y0 * 0.5f, 0f),
                KitMat.Stone("stone_dark"), 0f, false);
            Kit.Box(t, "Body", new Vector3(W, bodyH, D), new Vector3(0f, y0 + bodyH * 0.5f, 0f), wallMat, 0f, false);
            if (spec.Collider) Blocker(t, "Collider", new Vector3(W, y0 + bodyH, D), new Vector3(0f, (y0 + bodyH) * 0.5f, 0f));

            // ---- 四个立面：窗 / 木筋 / 门 / 招牌 / 灯 ----
            var front = Facade(t, "FaceFront", new Vector3(0f, 0f, D * 0.5f), 0f);
            var back = Facade(t, "FaceBack", new Vector3(0f, 0f, -D * 0.5f), 180f);
            var right = Facade(t, "FaceRight", new Vector3(W * 0.5f, 0f, 0f), 90f);
            var left = Facade(t, "FaceLeft", new Vector3(-W * 0.5f, 0f, 0f), -90f);

            bool doorFront = spec.DoorOnFront;
            WindowsOnFace(front, "F", W, y0, perFloor, floors, frameMat, ref rnd, doorFront, spec.Trim);
            WindowsOnFace(back, "B", W, y0, perFloor, floors, frameMat, ref rnd, false, false);
            WindowsOnFace(right, "R", D, y0, perFloor, floors, frameMat, ref rnd, false, false);
            WindowsOnFace(left, "L", D, y0, perFloor, floors, frameMat, ref rnd, false, false);

            if (timberMat != null)
            {
                FacadeTimber(front, W, y0, perFloor, floors, timberMat, true, rnd);
                FacadeTimber(back, W, y0, perFloor, floors, timberMat, false, rnd);
                FacadeTimber(right, D, y0, perFloor, floors, timberMat, false, rnd);
                FacadeTimber(left, D, y0, perFloor, floors, timberMat, false, rnd);
                // 层间横带（围一圈，凸出墙面 8cm）
                for (int lv = 0; lv <= floors; lv++)
                {
                    float by = y0 + lv * perFloor;
                    Kit.Box(t, "BeltF", new Vector3(W + 0.16f, 0.18f, 0.16f), new Vector3(0f, by, D * 0.5f), timberMat, 0f, false);
                    Kit.Box(t, "BeltB", new Vector3(W + 0.16f, 0.18f, 0.16f), new Vector3(0f, by, -D * 0.5f), timberMat, 0f, false);
                    Kit.Box(t, "BeltR", new Vector3(0.16f, 0.18f, D + 0.16f), new Vector3(W * 0.5f, by, 0f), timberMat, 0f, false);
                    Kit.Box(t, "BeltL", new Vector3(0.16f, 0.18f, D + 0.16f), new Vector3(-W * 0.5f, by, 0f), timberMat, 0f, false);
                }
                // 四角立柱（比墙面凸 10cm）
                for (int sx = -1; sx <= 1; sx += 2)
                    for (int sz = -1; sz <= 1; sz += 2)
                        Kit.Box(t, "CornerPost", new Vector3(0.26f, bodyH, 0.26f),
                            new Vector3(sx * (W * 0.5f - 0.02f), y0 + bodyH * 0.5f, sz * (D * 0.5f - 0.02f)),
                            timberMat, 0f, false);
            }

            if (doorFront) Door(front, new Vector3(0f, 0f, 0f), true);

            // ---- 屋檐/屋顶 ----
            float roofH = Mathf.Max(0.9f, spec.RoofHeight);
            float spanW = ridgeX ? W : D;      // 沿屋脊方向跨度
            float slopeD = ridgeX ? D : W;     // 坡面跨度
            var roofMesh = Kit.GableRoofMesh(spanW, slopeD, roofH, overhang, 0.16f);
            var roof = Kit.Mesh(t, "Roof", roofMesh, new Vector3(0f, wallTop, 0f), roofMat, spec.Collider);
            if (!ridgeX) roof.transform.localRotation = Quaternion.Euler(0f, 90f, 0f);
            float tan = roofH / (slopeD * 0.5f);
            float eaveDrop = overhang * tan;

            // 脊瓦
            Kit.BoxRot(t, "RidgeCap", new Vector3(spanW + overhang * 2f + 0.2f, 0.16f, 0.24f),
                new Vector3(0f, wallTop + roofH + 0.05f, 0f),
                Quaternion.Euler(0f, ridgeX ? 0f : 90f, 0f), KitMat.Roof(spec.Roof), false);
            // 檐口封板（两侧长檐）
            var fasciaMat = KitMat.Timber("timber_dark");
            for (int s = -1; s <= 1; s += 2)
            {
                Vector3 fpos = ridgeX
                    ? new Vector3(0f, wallTop - eaveDrop - 0.04f, s * (slopeD * 0.5f + overhang))
                    : new Vector3(s * (slopeD * 0.5f + overhang), wallTop - eaveDrop - 0.04f, 0f);
                Kit.BoxRot(t, "Fascia", new Vector3(spanW + overhang * 2f, 0.15f, 0.1f), fpos,
                    Quaternion.Euler(0f, ridgeX ? 0f : 90f, 0f), fasciaMat, false);
            }

            // ---- 山墙三角 + 木筋 + 圆窗 ----
            if (ridgeX)
            {
                for (int s = -1; s <= 1; s += 2)
                {
                    Kit.GableFace(t, "Gable", D, roofH, 0.24f,
                        new Vector3(s * W * 0.5f, wallTop, 0f), wallMat, s * 90f);
                    GableTimber(t, "GableTimber", new Vector3(s * W * 0.5f, wallTop, 0f), s * 90f, D, roofH, timberMat);
                    GableWindow(Facade(t, "GableFace", new Vector3(s * W * 0.5f, wallTop, 0f), s * 90f),
                        "GableWindow", new Vector3(0f, roofH * 0.36f, 0.14f), 0.3f);
                }
            }
            else
            {
                for (int s = -1; s <= 1; s += 2)
                {
                    Kit.GableFace(t, "Gable", W, roofH, 0.24f,
                        new Vector3(0f, wallTop, s * D * 0.5f), wallMat, s > 0 ? 0f : 180f);
                    GableTimber(t, "GableTimber", new Vector3(0f, wallTop, s * D * 0.5f), s > 0 ? 0f : 180f, W, roofH, timberMat);
                    GableWindow(Facade(t, "GableFace", new Vector3(0f, wallTop, s * D * 0.5f), s > 0 ? 0f : 180f),
                        "GableWindow", new Vector3(0f, roofH * 0.36f, 0.14f), 0.3f);
                }
            }

            // ---- 烟囱 + 烟 ----
            if (spec.Chimney)
            {
                float cx = (rnd.Chance(0.5f) ? 1f : -1f) * W * 0.27f;
                float cz = (rnd.Chance(0.5f) ? 1f : -1f) * D * 0.14f;
                float chBot = wallTop + roofH * 0.32f;
                float chH = roofH * 0.72f + 0.8f;
                Kit.Box(t, "Chimney", new Vector3(0.52f, chH, 0.52f), new Vector3(cx, chBot + chH * 0.5f, cz),
                    KitMat.Stone("stone_dark"), 0f, false);
                Kit.Box(t, "ChimneyCap", new Vector3(0.72f, 0.12f, 0.72f), new Vector3(cx, chBot + chH + 0.06f, cz),
                    KitMat.Stone("stone_light"), 0f, false);
                Kit.Smoke(t, new Vector3(cx, chBot + chH + 0.2f, cz), new Color(0.94f, 0.93f, 0.91f), 4, 0.2f);
            }

            // ---- 阳台 ----
            if (spec.Balcony && floors >= 2)
            {
                float by = y0 + perFloor;
                var bal = Facade(front, "Balcony", new Vector3(0f, by, 0f), 0f);
                float bw = Mathf.Min(W * 0.56f, 3.2f);
                float bd = 0.95f;
                Kit.Box(bal, "Platform", new Vector3(bw, 0.16f, bd), new Vector3(0f, 0.08f, bd * 0.5f), KitMat.Timber("timber_dark"), 0f, false);
                for (int s = -1; s <= 1; s += 2)
                {
                    Kit.Box(bal, "Support", new Vector3(0.12f, 0.12f, bd * 0.9f),
                        new Vector3(s * bw * 0.42f, -0.26f, bd * 0.45f), KitMat.Timber("timber_mid"), 0f, false);
                    Kit.BoxRot(bal, "Bracket", new Vector3(0.1f, 0.1f, 0.85f),
                        new Vector3(s * bw * 0.42f, -0.3f, bd * 0.38f), Quaternion.Euler(38f, 0f, 0f),
                        KitMat.Timber("timber_mid"), false);
                    Kit.Box(bal, "Post", new Vector3(0.11f, 0.95f, 0.11f), new Vector3(s * bw * 0.5f, 0.55f, bd - 0.05f),
                        KitMat.Timber("timber_mid"), 0f, false);
                    Kit.Box(bal, "SideRail", new Vector3(0.09f, 0.09f, bd), new Vector3(s * bw * 0.5f, 0.98f, bd * 0.5f),
                        KitMat.Timber("timber_mid"), 0f, false);
                }
                Kit.Box(bal, "TopRail", new Vector3(bw, 0.09f, 0.09f), new Vector3(0f, 0.98f, bd - 0.05f),
                    KitMat.Timber("timber_mid"), 0f, false);
                for (int i = 0; i < 6; i++)
                {
                    float bx = (i - 2.5f) * (bw / 6f);
                    Kit.Box(bal, "Baluster", new Vector3(0.06f, 0.82f, 0.06f), new Vector3(bx, 0.55f, bd - 0.05f),
                        KitMat.Timber("timber_mid"), 0f, false);
                }
            }

            // ---- 招牌 / 挂灯 ----
            float signY = floors > 1
                ? y0 + perFloor + 0.62f
                : Mathf.Min(y0 + perFloor - 0.5f, y0 + Kit.DoorHeight + 0.6f);
            if (spec.Sign && !string.IsNullOrEmpty(spec.SignText))
            {
                Kit.SignBoard(front, spec.SignText, new Vector3(0f, signY, 0.12f), 0f,
                    Mathf.Min(W * 0.44f, 1.9f), 0.46f);
            }
            if (spec.HangingSign && !string.IsNullOrEmpty(spec.SignText))
            {
                var hp = Kit.Pivot(front, "HangingSign", new Vector3(W * 0.32f, signY + 0.25f, 0f), 0f);
                var hpt = hp.transform;
                Kit.Box(hpt, "BracketH", new Vector3(0.07f, 0.07f, 0.66f), new Vector3(0f, 0.36f, 0.33f), Iron(), 0f, false);
                Kit.Box(hpt, "BracketV", new Vector3(0.07f, 0.4f, 0.07f), new Vector3(0f, 0.2f, 0.02f), Iron(), 0f, false);
                Kit.Box(hpt, "ChainL", new Vector3(0.03f, 0.2f, 0.03f), new Vector3(-0.3f, 0.24f, 0.62f), Iron(), 0f, false);
                Kit.Box(hpt, "ChainR", new Vector3(0.03f, 0.2f, 0.03f), new Vector3(0.3f, 0.24f, 0.62f), Iron(), 0f, false);
                Kit.SignBoard(hpt, spec.SignText, new Vector3(0f, -0.14f, 0.62f), 90f, 1.05f, 0.62f);
            }
            if (spec.Trim)
            {
                WallLantern(front, "Lantern", new Vector3(-W * 0.22f, y0 + 2.4f, 0.02f));
                // 门两侧的小木桶/花盆留给 KitProps，这里不堆道具，保持建筑本身干净
            }

            if (spec.Fadeable) Kit.MakeFadeable(root, 0.22f);
            return root;
        }

        // ============================================================================================
        // 城墙段
        // ============================================================================================
        /// <summary>城墙：石墙身 + 收分基座 + 走道 + 城垛（外侧）+ 扶壁。默认沿本地 X 方向延伸。</summary>
        public static GameObject WallSegment(Transform parent, Vector3 pos, float yaw = 0f, float length = 6f, float height = 3.5f)
        {
            length = Mathf.Max(1.5f, length);
            height = Mathf.Max(1.4f, height);
            var root = Kit.Pivot(parent, "WallSegment", pos, yaw);
            var t = root.transform;
            var stoneMat = KitMat.Stone("stone_wall");
            var darkMat = KitMat.Stone("stone_dark");
            var lightMat = KitMat.Stone("stone_light");
            const float thick = 1.1f;

            Kit.Box(t, "Body", new Vector3(length, height, thick), new Vector3(0f, height * 0.5f, 0f), stoneMat, 0f, true);
            Kit.Box(t, "Base", new Vector3(length + 0.1f, 0.42f, thick + 0.34f), new Vector3(0f, 0.21f, 0f), darkMat, 0f, false);
            Kit.Box(t, "Walk", new Vector3(length, 0.16f, thick + 0.2f), new Vector3(0f, height + 0.08f, 0f), lightMat, 0f, false);

            // 外侧城垛（+Z）
            int merlons = Mathf.Max(2, Mathf.RoundToInt(length / 1.1f));
            float step = length / merlons;
            for (int i = 0; i < merlons; i++)
            {
                if (i % 2 == 1) continue;
                float x = -length * 0.5f + step * (i + 0.5f);
                Kit.Box(t, "Merlon", new Vector3(step * 0.74f, 0.74f, 0.44f),
                    new Vector3(x, height + 0.16f + 0.37f, thick * 0.5f - 0.24f), stoneMat, 0f, false);
                Kit.Box(t, "MerlonCap", new Vector3(step * 0.8f, 0.09f, 0.5f),
                    new Vector3(x, height + 0.16f + 0.78f, thick * 0.5f - 0.24f), lightMat, 0f, false);
            }
            // 内侧矮墙
            Kit.Box(t, "InnerParapet", new Vector3(length, 0.55f, 0.26f), new Vector3(0f, height + 0.43f, -thick * 0.5f + 0.15f), stoneMat, 0f, false);
            // 扶壁
            int butt = Mathf.Max(1, Mathf.RoundToInt(length / 2.8f));
            float bstep = length / butt;
            for (int i = 0; i < butt; i++)
            {
                float x = -length * 0.5f + bstep * (i + 0.5f);
                Kit.Box(t, "Buttress", new Vector3(0.52f, height * 0.78f, 0.5f),
                    new Vector3(x, height * 0.39f, thick * 0.5f + 0.16f), darkMat, 0f, false);
            }
            return root;
        }

        // ============================================================================================
        // 塔楼
        // ============================================================================================
        /// <summary>
        /// 圆塔：基座 + 塔身 + 箭窗 + 顶部挑檐 + 城垛（或法师塔的锥顶 + 悬浮水晶 + 发光符文环）。
        /// wizard=true 时用浅色石、青色锥顶、紫/青发光，挂在塔根上的 FadeableObject 让相机穿过时不挡视野。
        /// </summary>
        public static GameObject Tower(Transform parent, Vector3 pos, float yaw = 0f, bool wizard = false)
        {
            var root = Kit.Pivot(parent, wizard ? "WizardTower" : "Tower", pos, yaw);
            var t = root.transform;
            var stoneMat = KitMat.Stone(wizard ? "stone_light" : "stone_wall");
            var darkMat = KitMat.Stone("stone_dark");
            float radius = 2.1f;
            float bodyH = wizard ? 11f : 9f;
            float baseH = 0.9f;

            Kit.Cyl(t, "Base", radius + 0.5f, baseH, new Vector3(0f, baseH * 0.5f, 0f), darkMat, 12, true);
            Kit.Cyl(t, "Body", radius, bodyH, new Vector3(0f, baseH + bodyH * 0.5f, 0f), stoneMat, 12, true);

            // 箭窗（三层，两个方向一组）
            for (int lv = 0; lv < 3; lv++)
            {
                float ly = baseH + bodyH * (0.22f + lv * 0.26f);
                for (int k = 0; k < 2; k++)
                {
                    float ang = (lv * 73f + k * 180f) % 360f;
                    Vector3 p = KitMath.OnCircle(radius - 0.02f, ang);
                    Kit.Box(t, "Slit", new Vector3(0.2f, 0.86f, 0.18f), new Vector3(p.x, ly, p.z), Iron(), ang, false);
                }
            }

            // 顶部挑檐
            float topY = baseH + bodyH;
            Kit.Cyl(t, "Corbel", radius + 0.32f, 0.55f, new Vector3(0f, topY + 0.275f, 0f), darkMat, 12, false);
            Kit.Cyl(t, "Rim", radius + 0.42f, 0.18f, new Vector3(0f, topY + 0.64f, 0f), KitMat.Stone("stone_light"), 12, false);

            // 门（正面 +Z）+ 台阶 + 挂灯
            var doorFace = Facade(t, "TowerDoor", new Vector3(0f, 0f, radius - 0.02f), 0f);
            Door(doorFace, Vector3.zero, true);
            WallLantern(doorFace, "Torch", new Vector3(0.9f, 2.35f, 0.02f));

            if (wizard)
            {
                // 锥顶
                Kit.Cone(t, "Roof", radius + 0.55f, 3.6f, new Vector3(0f, topY + 0.72f, 0f), KitMat.Roof("roof_teal"), 12, false);
                Kit.Sphere(t, "Finial", 0.28f, new Vector3(0f, topY + 4.35f, 0f), MapMaterials.Get("gold"), false, 10);
                // 发光符文环（绕塔身一圈）
                var ring = Kit.Pivot(t, "RuneRing", new Vector3(0f, baseH + bodyH * 0.72f, 0f), 0f);
                for (int i = 0; i < 12; i++)
                {
                    float ang = i * 30f;
                    Vector3 p = KitMath.OnCircle(radius + 0.06f, ang);
                    Kit.Box(ring.transform, "Rune", new Vector3(0.16f, 0.42f, 0.1f), new Vector3(p.x, 0f, p.z),
                        KitMat.Emi("kit_rune_cyan", MapMaterials.GlowCyan, 2.2f), ang, false);
                }
                // 悬浮水晶（旋转）
                var crystals = Kit.Pivot(t, "Crystals", new Vector3(0f, topY + 4.9f, 0f), 0f);
                for (int i = 0; i < 5; i++)
                {
                    Vector3 p = KitMath.OnCircle(0.62f, i * 72f);
                    Kit.ConeRot(crystals.transform, "Crystal", 0.17f, 0.62f,
                        new Vector3(p.x, Mathf.Sin(i * 1.7f) * 0.12f, p.z),
                        Quaternion.Euler(180f, i * 72f, 0f),
                        KitMat.Emi("kit_crystal", new Color(0.62f, 0.55f, 1f), 2.0f), 5);
                }
                crystals.AddComponent<KitSpin>().DegreesPerSecond = 18f;
                Kit.PointLight(t, new Vector3(0f, topY + 1.4f, 0f), new Color(0.7f, 0.62f, 1f), 8f, 1.6f);
            }
            else
            {
                // 城垛
                int merlons = 10;
                for (int i = 0; i < merlons; i++)
                {
                    float ang = i * 360f / merlons;
                    Vector3 p = KitMath.OnCircle(radius + 0.18f, ang);
                    Kit.Box(t, "Merlon", new Vector3(0.74f, 0.8f, 0.36f), new Vector3(p.x, topY + 1.12f, p.z),
                        stoneMat, ang, false);
                }
                // 悬挂旗帜
                var ban = Kit.Pivot(t, "TowerBanner", new Vector3(radius * 0.72f, topY - 0.1f, radius * 0.72f), 45f);
                Kit.Box(ban.transform, "Pole", new Vector3(0.07f, 2.6f, 0.07f), new Vector3(0f, -1.3f, 0f), Iron(), 0f, false);
                Kit.Box(ban.transform, "Cloth", new Vector3(1.05f, 2.0f, 0.06f), new Vector3(0.56f, -0.9f, 0f),
                    KitMat.Cloth("cloth_red"), 0f, false);
                Kit.Sphere(ban.transform, "Emblem", 0.24f, new Vector3(0.56f, -0.6f, 0.07f),
                    KitMat.Emi("kit_emblem_gold", MapMaterials.GlowGold, 0.9f), false, 10);
            }

            Kit.MakeFadeable(root, 0.2f);
            return root;
        }
    }
}
