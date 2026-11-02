using System.Collections.Generic;
using UnityEngine;

namespace MyWorld.Maps
{
    // ============================================================================================
    // 罗亚市组合件：在 Kit 原语 / KitProps / KitArchitecture 之上拼出广场、冒险者协会、商店街、
    // 旅店、城门、喷泉、市场摊位等。只属于罗亚市地图，不修改任何地基文件。
    //
    // 坐标约定：所有 pos/yaw 都是父节点局部空间；建筑本地 +Z = 正立面。
    // 视觉子物体先建在 root/Visual 下，然后 Kit.Optimize 合并，招牌/点光/碰撞盒在合并后再加。
    // ============================================================================================
    internal enum ShopKind
    {
        General = 0,
        Magic = 1,
        Bakery = 2,
        Tailor = 3,
    }

    internal static class RoaKit
    {
        // ================================================================================
        // 基础工具
        // ================================================================================
        static Material Mat(string key)
        {
            return MapMaterials.Get(key);
        }

        static Material WallM(string key) { return KitMat.Wall(key); }
        static Material RoofM(string key) { return KitMat.Roof(key); }
        static Material TimberM(string key) { return KitMat.Timber(key); }
        static Material StoneM(string key) { return KitMat.Stone(key); }
        static Material ClothM(string key) { return KitMat.Cloth(key); }
        static Material AwningM(string key) { return KitMat.Awning(key); }
        static Material WoodM(string key) { return KitMat.WoodTinted(key); }

        static readonly Color Ink = MapMaterials.Hex("#2B1D14");

        static Material _winLit, _winDay, _lampGlow, _fire, _runeCyan, _runeViolet;

        static Material WinLit()
        {
            if (_winLit == null) _winLit = MapMaterials.Emissive("roa_win_lit", new Color(1f, 0.80f, 0.46f), 1.25f);
            return _winLit;
        }

        static Material WinDay()
        {
            if (_winDay == null) _winDay = MapMaterials.Emissive("roa_win_day", new Color(0.52f, 0.70f, 0.85f), 0.34f);
            return _winDay;
        }

        static Material LampGlow()
        {
            if (_lampGlow == null) _lampGlow = MapMaterials.Emissive("roa_lamp_glow", MapMaterials.GlowWarm, 2.4f);
            return _lampGlow;
        }

        static Material FireGlow()
        {
            if (_fire == null) _fire = MapMaterials.Emissive("roa_fire", new Color(1f, 0.55f, 0.18f), 2.8f);
            return _fire;
        }

        static Material RuneCyan()
        {
            if (_runeCyan == null) _runeCyan = MapMaterials.Emissive("roa_rune_cyan", MapMaterials.GlowCyan, 2.1f);
            return _runeCyan;
        }

        static Material RuneViolet()
        {
            if (_runeViolet == null) _runeViolet = MapMaterials.Emissive("roa_rune_violet", MapMaterials.GlowViolet, 2.1f);
            return _runeViolet;
        }

        // 原语短别名（本文件的局部坐标）
        static GameObject B(Transform p, string n, Vector3 size, Vector3 pos, Material m, float yaw = 0f,
            bool collider = false)
        {
            return Kit.Box(p, n, size, pos, m, yaw, collider);
        }

        static GameObject BR(Transform p, string n, Vector3 size, Vector3 pos, Quaternion rot, Material m)
        {
            return Kit.BoxRot(p, n, size, pos, rot, m, false);
        }

        static GameObject SL(Transform p, string n, Vector3 size, Vector3 pos, Material m, float yaw = 0f)
        {
            return Kit.Slab(p, n, size, pos, m, yaw, false);
        }

        static GameObject CY(Transform p, string n, float radius, float height, Vector3 pos, Material m,
            int seg = 10, bool collider = false)
        {
            return Kit.Cyl(p, n, radius, height, pos, m, seg, collider);
        }

        static GameObject CYR(Transform p, string n, float radius, float height, Vector3 pos, Quaternion rot,
            Material m, int seg = 10)
        {
            return Kit.CylRot(p, n, radius, height, pos, rot, m, seg, false);
        }

        static GameObject CN(Transform p, string n, float radius, float height, Vector3 pos, Material m,
            int seg = 8)
        {
            return Kit.Cone(p, n, radius, height, pos, m, seg, false);
        }

        static GameObject CNR(Transform p, string n, float radius, float height, Vector3 pos, Quaternion rot,
            Material m, int seg = 8)
        {
            return Kit.ConeRot(p, n, radius, height, pos, rot, m, seg);
        }

        static GameObject SP(Transform p, string n, float radius, Vector3 pos, Material m, int seg = 9)
        {
            return Kit.Sphere(p, n, radius, pos, m, false, seg);
        }

        static GameObject SPE(Transform p, string n, Vector3 size, Vector3 pos, Material m, int seg = 9)
        {
            return Kit.Sphere(p, n, size, pos, m, false, seg);
        }

        static Transform Piv(Transform p, string n, Vector3 pos, float yaw = 0f)
        {
            return Kit.Pivot(p, n, pos, yaw).transform;
        }

        static Transform Piv(Transform p, string n)
        {
            return Kit.Pivot(p, n, Vector3.zero, 0f).transform;
        }

        static void Blocker(Transform p, string n, Vector3 size, Vector3 pos)
        {
            Kit.Blocker(p, n, size, pos);
        }

        internal static int Batch(GameObject root, bool collider = false)
        {
            return Kit.Optimize(root, collider);
        }

        // ================================================================================
        // 通用零件
        // ================================================================================

        /// <summary>带窗框/窗棂/窗台/百叶/花箱的窗。face 原点 = 墙面上窗的中心，+Z 朝外。</summary>
        internal static void Win(Transform face, Vector3 pos, float w, float h, bool lit, bool shutters,
            bool flowerBox, Material frame)
        {
            var t = Piv(face, "Win", pos);
            B(t, "Pane", new Vector3(w, h, 0.05f), new Vector3(0f, 0f, 0.015f), lit ? WinLit() : WinDay());
            float ft = 0.08f;
            B(t, "FrameT", new Vector3(w + ft * 2f, ft, 0.12f), new Vector3(0f, h * 0.5f + ft * 0.5f, 0.04f), frame);
            B(t, "FrameB", new Vector3(w + ft * 2f, ft, 0.12f), new Vector3(0f, -h * 0.5f - ft * 0.5f, 0.04f), frame);
            B(t, "FrameL", new Vector3(ft, h, 0.12f), new Vector3(-w * 0.5f - ft * 0.5f, 0f, 0.04f), frame);
            B(t, "FrameR", new Vector3(ft, h, 0.12f), new Vector3(w * 0.5f + ft * 0.5f, 0f, 0.04f), frame);
            B(t, "MullV", new Vector3(0.05f, h, 0.07f), new Vector3(0f, 0f, 0.045f), frame);
            B(t, "MullH", new Vector3(w, 0.05f, 0.07f), new Vector3(0f, h * 0.08f, 0.045f), frame);
            B(t, "Sill", new Vector3(w + 0.32f, 0.08f, 0.24f), new Vector3(0f, -h * 0.5f - 0.1f, 0.1f), StoneM("stone_light"));
            if (shutters)
            {
                float sw = w * 0.46f, sh = h * 0.96f;
                float sx = w * 0.5f + 0.17f + sw * 0.5f;
                BR(t, "ShutterL", new Vector3(sw, sh, 0.05f), new Vector3(-sx, 0f, 0.07f),
                    Quaternion.Euler(0f, 20f, 0f), TimberM("timber_mid"));
                BR(t, "ShutterR", new Vector3(sw, sh, 0.05f), new Vector3(sx, 0f, 0.07f),
                    Quaternion.Euler(0f, -20f, 0f), TimberM("timber_mid"));
            }
            if (flowerBox)
            {
                B(t, "FlowerBox", new Vector3(w * 0.9f, 0.17f, 0.24f), new Vector3(0f, -h * 0.5f - 0.25f, 0.16f),
                    WoodM("wood_dark"));
                for (int i = 0; i < 3; i++)
                {
                    Color fc = i == 0 ? MapMaterials.ClothRed : (i == 1 ? MapMaterials.ClothOrange : MapMaterials.ClothCream);
                    SP(t, "Flower", 0.08f, new Vector3((i - 1) * w * 0.27f, -h * 0.5f - 0.14f, 0.2f),
                        MapMaterials.Solid("roa_flower_" + ColorUtility.ToHtmlStringRGB(fc), fc, 0.25f), 8);
                }
            }
        }

        /// <summary>拱形门洞：木门框 + 石拱券 + 门套。face 原点 = 地面上门中心，+Z 朝外。</summary>
        internal static void ArchFrame(Transform face, float width, float height, Material stone, Material frame)
        {
            var t = Piv(face, "DoorFrame");
            float dw = width;
            B(t, "PostL", new Vector3(0.2f, height + 0.1f, 0.34f), new Vector3(-dw * 0.5f - 0.1f, (height + 0.1f) * 0.5f, 0.06f), frame);
            B(t, "PostR", new Vector3(0.2f, height + 0.1f, 0.34f), new Vector3(dw * 0.5f + 0.1f, (height + 0.1f) * 0.5f, 0.06f), frame);
            // 石拱券
            int n = 9;
            float r = dw * 0.5f + 0.24f;
            for (int i = 0; i < n; i++)
            {
                float a = Mathf.PI * (i / (float)(n - 1));
                BR(t, "Voussoir", new Vector3(0.26f, 0.36f, 0.36f),
                    new Vector3(Mathf.Cos(a) * r, height + 0.1f + Mathf.Sin(a) * r, 0.02f),
                    Quaternion.Euler(0f, 0f, a * Mathf.Rad2Deg), stone);
            }
            // 门槛
            SL(t, "Threshold", new Vector3(dw + 0.6f, 0.05f, 0.5f), new Vector3(0f, 0.02f, 0.15f), StoneM("stone_light"));
        }

        /// <summary>店门口的木遮阳棚（条纹布）：斜面 + 前垂边 + 两根支杆。</summary>
        internal static void Awning(Transform face, float width, float y, float depth, string clothKey)
        {
            var t = Piv(face, "Awning");
            float span = width + 1.9f;
            BR(t, "Canopy", new Vector3(span, 0.07f, depth), new Vector3(0f, y, depth * 0.5f - 0.1f),
                Quaternion.Euler(-16f, 0f, 0f), AwningM(clothKey));
            B(t, "Valance", new Vector3(span, 0.3f, 0.05f), new Vector3(0f, y - depth * 0.28f, depth - 0.12f),
                ClothM(clothKey));
            for (int s = -1; s <= 1; s += 2)
            {
                CY(t, "Pole", 0.06f, y - 0.15f, new Vector3(s * width * 0.5f, (y - 0.15f) * 0.5f, depth - 0.35f),
                    TimberM("timber_mid"), 8);
            }
        }

        /// <summary>门口摆的灯笼（铁艺 + 暖光），light=true 时建点光。</summary>
        internal static void PorchLantern(Transform face, Vector3 pos, bool light)
        {
            var t = Piv(face, "Lantern", pos);
            var iron = Mat("iron");
            B(t, "Arm", new Vector3(0.06f, 0.06f, 0.36f), new Vector3(0f, 0.2f, 0.18f), iron);
            B(t, "Top", new Vector3(0.3f, 0.06f, 0.3f), new Vector3(0f, 0.06f, 0.4f), iron);
            B(t, "Glow", new Vector3(0.22f, 0.3f, 0.22f), new Vector3(0f, -0.1f, 0.4f), LampGlow());
            B(t, "Bottom", new Vector3(0.26f, 0.05f, 0.26f), new Vector3(0f, -0.27f, 0.4f), iron);
            if (light) Kit.PointLight(t, new Vector3(0f, -0.05f, 0.4f), MapMaterials.GlowWarm, 5.5f, 1.1f);
        }

        /// <summary>挂在墙上的旗帜：横杆 + 布面 + 燕尾 + 金徽章。face 原点在墙面上。</summary>
        internal static void WallBanner(Transform face, Vector3 pos, string clothKey, float width, float height)
        {
            var t = Piv(face, "WallBanner", pos);
            var iron = Mat("iron");
            B(t, "Pole", new Vector3(width + 0.3f, 0.07f, 0.07f), new Vector3(0f, height * 0.5f + 0.05f, 0.12f), iron);
            B(t, "Cloth", new Vector3(width, height, 0.05f), new Vector3(0f, 0f, 0.11f), ClothM(clothKey));
            var tail = Kit.GableFace(t, "Tail", width, 0.4f, 0.05f, new Vector3(0f, -height * 0.5f - 0.2f, 0.11f),
                ClothM(clothKey), 180f);
            tail.transform.localRotation = Quaternion.Euler(0f, 0f, 180f);
            CYR(t, "Emblem", 0.24f, 0.06f, new Vector3(0f, height * 0.12f, 0.15f),
                Quaternion.Euler(90f, 0f, 0f), MapMaterials.Emissive("roa_emblem_gold", MapMaterials.GlowGold, 0.9f), 12);
        }

        /// <summary>柜台 + 台面 + 台上的货品。pos 为柜台中心地面点，+Z 朝顾客。</summary>
        internal static void Counter(Transform t, Vector3 pos, float width, float depth, Material wood, int goods)
        {
            var p = Piv(t, "Counter", pos);
            B(p, "Body", new Vector3(width, 0.92f, depth), new Vector3(0f, 0.46f, 0f), wood);
            B(p, "Top", new Vector3(width + 0.18f, 0.09f, depth + 0.18f), new Vector3(0f, 0.96f, 0f),
                WoodM("wood_plank"));
            B(p, "FrontPanel", new Vector3(width * 0.88f, 0.62f, 0.05f), new Vector3(0f, 0.44f, depth * 0.5f + 0.03f),
                TimberM("timber_dark"));
            for (int i = 0; i < goods; i++)
            {
                float x = width * (0.32f - 0.64f * (goods <= 1 ? 0.5f : i / (float)(goods - 1)));
                Color c = GoodsColor(i);
                if (i % 2 == 0)
                    B(p, "Good", new Vector3(0.22f, 0.22f, 0.22f), new Vector3(x, 1.11f, 0.05f),
                        MapMaterials.Solid("roa_goods_" + i, c, 0.3f));
                else
                    CY(p, "Potion", 0.1f, 0.3f, new Vector3(x, 1.15f, 0.02f),
                        MapMaterials.Emissive("roa_potion_" + i, c, 0.9f), 8);
            }
        }

        static Color GoodsColor(int i)
        {
            switch (i % 6)
            {
                case 0: return MapMaterials.ClothRed;
                case 1: return MapMaterials.GlowGold;
                case 2: return MapMaterials.ClothGreen;
                case 3: return MapMaterials.ClothPurple;
                case 4: return MapMaterials.ClothOrange;
                default: return MapMaterials.ClothTeal;
            }
        }

        /// <summary>货架：木框 + 3 层隔板 + 彩色货品，贴墙放。face 原点在墙面上，+Z 朝外。</summary>
        internal static void Shelf(Transform face, Vector3 pos, float width, int kinds)
        {
            var t = Piv(face, "Shelf", pos);
            float h = 2.0f;
            B(t, "Back", new Vector3(width, h, 0.06f), new Vector3(0f, h * 0.5f, 0f), TimberM("timber_dark"));
            for (int s = -1; s <= 1; s += 2)
                B(t, "Side", new Vector3(0.08f, h, 0.34f), new Vector3(s * width * 0.5f, h * 0.5f, 0.16f), TimberM("timber_mid"));
            for (int lv = 0; lv < 3; lv++)
            {
                float y = 0.45f + lv * 0.62f;
                B(t, "Board", new Vector3(width - 0.1f, 0.06f, 0.34f), new Vector3(0f, y, 0.16f), WoodM("wood_plank"));
                for (int i = 0; i < 4; i++)
                {
                    float x = -width * 0.34f + i * width * 0.22f;
                    int k = (lv * 4 + i) % kinds;
                    B(t, "Item", new Vector3(0.16f, 0.26f, 0.14f), new Vector3(x, y + 0.17f, 0.14f),
                        MapMaterials.Solid("roa_shelf_" + k + "_" + (lv * 4 + i), GoodsColor(lv + i), 0.3f));
                }
            }
        }

        /// <summary>地面圆形铺装（广场/传送门平台）。uv 用米制，配合程序化石板纹理。</summary>
        internal static GameObject FloorDisc(Transform parent, string name, float radius, Vector3 pos, Material mat,
            int segments = 40)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            var mf = go.AddComponent<MeshFilter>();
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = mat;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            var verts = new List<Vector3>(segments + 1);
            var uvs = new List<Vector2>(segments + 1);
            var tris = new List<int>(segments * 3);
            verts.Add(Vector3.zero);
            uvs.Add(Vector2.zero);
            for (int i = 0; i < segments; i++)
            {
                float a = i * Mathf.PI * 2f / segments;
                var p = new Vector3(Mathf.Cos(a) * radius, 0f, Mathf.Sin(a) * radius);
                verts.Add(p);
                uvs.Add(new Vector2(p.x, p.z));
            }
            for (int i = 0; i < segments; i++)
            {
                int a = 1 + i;
                int b = 1 + (i + 1) % segments;
                tris.Add(0);
                tris.Add(b);
                tris.Add(a);
            }
            var mesh = new Mesh { name = name };
            mesh.SetVertices(verts);
            mesh.SetUVs(0, uvs);
            mesh.SetTriangles(tris, 0);
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            mf.sharedMesh = mesh;
            return go;
        }

        /// <summary>草地上的小草簇（低成本上色点缀）。</summary>
        internal static GameObject GrassTuft(Transform parent, Vector3 pos, float scale = 1f)
        {
            var root = Kit.Pivot(parent, "Grass", pos, 0f);
            var t = root.transform;
            Material m = scale > 1.15f ? Mat("grass_dry") : Mat("foliage_dark");
            for (int i = 0; i < 3; i++)
            {
                float a = i * 120f;
                Vector3 dir = KitMath.OnCircle(0.14f * scale, a);
                CN(t, "Blade", 0.13f * scale, 0.46f * scale, new Vector3(dir.x, 0.23f * scale, dir.z), m, 5);
            }
            return root;
        }

        // ================================================================================
        // 喷泉（广场中心地标）
        // ================================================================================
        internal static GameObject Fountain(Transform parent, Vector3 pos)
        {
            var root = Kit.Pivot(parent, "Fountain", pos, 0f);
            var v = Piv(root.transform, "Visual");
            var stoneDark = StoneM("stone_dark");
            var stone = StoneM("stone_wall");
            var stoneLight = StoneM("stone_light");
            var water = Mat("water");
            var gold = Mat("gold");
            var marble = Mat("marble");

            CY(v, "Step", 3.55f, 0.16f, new Vector3(0f, 0.08f, 0f), stoneDark, 16);
            CY(v, "Step2", 3.3f, 0.1f, new Vector3(0f, 0.2f, 0f), stone, 16);
            // 八角形水池壁
            for (int i = 0; i < 8; i++)
            {
                float a = i * 45f;
                Vector3 dir = KitMath.OnCircle(2.95f, a);
                B(v, "BasinWall", new Vector3(1.0f, 0.62f, 0.42f), new Vector3(dir.x, 0.42f, dir.z),
                    i % 2 == 0 ? stone : stoneLight, -a);
                CY(v, "Bollard", 0.13f, 0.72f, new Vector3(dir.x * 1.1f, 0.46f, dir.z * 1.1f), stoneLight, 8);
            }
            CY(v, "Water", 2.78f, 0.07f, new Vector3(0f, 0.38f, 0f), water, 24);
            // 中央柱与两级水盘
            CY(v, "Pedestal", 0.62f, 1.15f, new Vector3(0f, 0.72f, 0f), stoneLight, 12);
            CY(v, "GoldBand", 0.68f, 0.1f, new Vector3(0f, 1.02f, 0f), gold, 12);
            CY(v, "MidBasin", 1.62f, 0.2f, new Vector3(0f, 1.5f, 0f), stoneLight, 16);
            CY(v, "MidWater", 1.42f, 0.06f, new Vector3(0f, 1.6f, 0f), water, 20);
            CY(v, "Shaft", 0.34f, 0.95f, new Vector3(0f, 2.0f, 0f), stone, 10);
            CY(v, "TopBasin", 0.95f, 0.16f, new Vector3(0f, 2.5f, 0f), stoneLight, 12);
            CY(v, "TopWater", 0.8f, 0.05f, new Vector3(0f, 2.58f, 0f), water, 14);
            // 顶部雕像（持瓶少女）
            CY(v, "Statue", 0.3f, 0.6f, new Vector3(0f, 2.86f, 0f), marble, 10);
            SP(v, "Head", 0.2f, new Vector3(0f, 3.3f, 0f), marble, 10);
            B(v, "ArmL", new Vector3(0.11f, 0.5f, 0.11f), new Vector3(-0.3f, 3.08f, 0.02f), marble, 0f);
            B(v, "ArmR", new Vector3(0.11f, 0.5f, 0.11f), new Vector3(0.3f, 3.08f, 0.02f), marble, 0f);
            B(v, "Jug", new Vector3(0.22f, 0.3f, 0.22f), new Vector3(0.42f, 2.92f, 0.12f), stoneLight);
            // 四道水流
            for (int i = 0; i < 4; i++)
            {
                float a = i * 90f + 45f;
                Vector3 dir = KitMath.OnCircle(1.62f, a);
                BR(v, "Jet", new Vector3(0.09f, 1.7f, 0.09f), new Vector3(dir.x * 0.85f, 1.02f, dir.z * 0.85f),
                    Quaternion.Euler(0f, -a, 26f), water);
            }
            // 四盏矮灯
            for (int i = 0; i < 4; i++)
            {
                float a = i * 90f;
                Vector3 dir = KitMath.OnCircle(4.1f, a);
                CY(v, "LampPost", 0.06f, 1.35f, new Vector3(dir.x, 0.68f, dir.z), Mat("iron"), 8);
                B(v, "LampGlow", new Vector3(0.2f, 0.26f, 0.2f), new Vector3(dir.x, 1.5f, dir.z), LampGlow());
            }
            Kit.Optimize(root, false);
            Kit.PointLight(root.transform, new Vector3(0f, 2.2f, 0f), MapMaterials.GlowWarm, 8.5f, 1.35f);
            Kit.MakeFadeable(root, 0.32f);
            return root;
        }

        // ================================================================================
        // 英雄雕像 / 水井
        // ================================================================================
        internal static GameObject Statue(Transform parent, Vector3 pos, float yaw)
        {
            var root = Kit.Pivot(parent, "Statue", pos, yaw);
            var v = Piv(root.transform, "Visual");
            var light = StoneM("stone_light");
            var dark = StoneM("stone_dark");
            var marble = Mat("marble");
            var gold = Mat("gold");
            B(v, "Base1", new Vector3(2.6f, 0.34f, 2.6f), new Vector3(0f, 0.17f, 0f), dark);
            B(v, "Base2", new Vector3(2.2f, 0.3f, 2.2f), new Vector3(0f, 0.49f, 0f), light);
            B(v, "Plinth", new Vector3(1.1f, 1.5f, 1.1f), new Vector3(0f, 1.39f, 0f), marble, 45f);
            B(v, "PlinthTop", new Vector3(1.35f, 0.16f, 1.35f), new Vector3(0f, 2.2f, 0f), light);
            // 英雄：斗篷 + 躯干 + 头 + 剑 + 盾
            B(v, "Cape", new Vector3(0.78f, 1.3f, 0.3f), new Vector3(0f, 2.85f, -0.1f), ClothM("cloth_blue"));
            B(v, "Torso", new Vector3(0.62f, 0.9f, 0.42f), new Vector3(0f, 2.95f, 0f), marble);
            B(v, "Legs", new Vector3(0.5f, 0.55f, 0.34f), new Vector3(0f, 2.42f, 0f), marble);
            SP(v, "Head", 0.2f, new Vector3(0f, 3.62f, 0f), marble, 10);
            B(v, "Helm", new Vector3(0.34f, 0.18f, 0.34f), new Vector3(0f, 3.8f, 0f), gold);
            B(v, "Sword", new Vector3(0.1f, 1.9f, 0.1f), new Vector3(-0.55f, 3.35f, 0.16f), Mat("steel"));
            B(v, "Hilt", new Vector3(0.34f, 0.09f, 0.12f), new Vector3(-0.55f, 4.28f, 0.16f), gold);
            CYR(v, "Shield", 0.42f, 0.1f, new Vector3(0.5f, 2.95f, 0.28f), Quaternion.Euler(90f, 0f, 0f), light, 12);
            CYR(v, "ShieldBoss", 0.16f, 0.14f, new Vector3(0.5f, 2.95f, 0.35f), Quaternion.Euler(90f, 0f, 0f), gold, 10);
            Kit.Optimize(root, false);
            AddRootBlocker(root, new Vector3(2.6f, 2.4f, 2.6f), new Vector3(0f, 1.2f, 0f));
            Kit.MakeFadeable(root, 0.3f);
            return root;
        }

        internal static GameObject Well(Transform parent, Vector3 pos, float yaw)
        {
            var root = Kit.Pivot(parent, "Well", pos, yaw);
            var v = Piv(root.transform, "Visual");
            var stone = StoneM("stone_wall");
            var light = StoneM("stone_light");
            var dark = StoneM("stone_dark");
            var wood = WoodM("wood_dark");
            for (int i = 0; i < 8; i++)
            {
                float a = i * 45f;
                Vector3 dir = KitMath.OnCircle(1.28f, a);
                B(v, "Ring", new Vector3(0.44f, 0.72f, 0.42f), new Vector3(dir.x, 0.36f, dir.z),
                    i % 2 == 0 ? stone : light, -a);
            }
            CY(v, "Water", 1.06f, 0.05f, new Vector3(0f, 0.45f, 0f), Mat("water_deep"), 16);
            for (int s = -1; s <= 1; s += 2)
            {
                CY(v, "Post", 0.11f, 2.5f, new Vector3(s * 1.05f, 1.25f, 0f), wood, 8);
                B(v, "Brace", new Vector3(0.1f, 0.55f, 0.1f), new Vector3(s * 0.8f, 2.3f, 0f), wood, 0f);
            }
            B(v, "Axle", new Vector3(2.35f, 0.12f, 0.12f), new Vector3(0f, 2.42f, 0f), wood);
            B(v, "RoofL", new Vector3(2.9f, 0.08f, 0.9f), new Vector3(0f, 2.72f, -0.42f), RoofM("roof_terracotta"),
                0f);
            B(v, "RoofR", new Vector3(2.9f, 0.08f, 0.9f), new Vector3(0f, 2.72f, 0.42f), RoofM("roof_terracotta"), 0f);
            BR(v, "RoofA", new Vector3(2.9f, 0.07f, 1.0f), new Vector3(0f, 2.82f, -0.34f), Quaternion.Euler(34f, 0f, 0f),
                RoofM("roof_terracotta"));
            BR(v, "RoofB", new Vector3(2.9f, 0.07f, 1.0f), new Vector3(0f, 2.82f, 0.34f), Quaternion.Euler(-34f, 0f, 0f),
                RoofM("roof_terracotta"));
            CY(v, "Rope", 0.045f, 0.9f, new Vector3(0f, 1.95f, 0f), Mat("wood_light"), 6);
            CY(v, "Bucket", 0.2f, 0.28f, new Vector3(0f, 1.4f, 0f), wood, 8);
            Kit.Optimize(root, false);
            AddRootBlocker(root, new Vector3(2.6f, 1.0f, 2.6f), new Vector3(0f, 0.5f, 0f));
            Kit.MakeFadeable(root, 0.3f);
            return root;
        }

        static void AddRootBlocker(GameObject root, Vector3 size, Vector3 center)
        {
            var bc = root.GetComponent<BoxCollider>();
            if (bc == null) bc = root.AddComponent<BoxCollider>();
            bc.center = center;
            bc.size = size;
        }

        // ================================================================================
        // 市场摊位
        // ================================================================================
        internal static GameObject MarketStall(Transform parent, Vector3 pos, float yaw, string clothKey)
        {
            var root = Kit.Pivot(parent, "Stall", pos, yaw);
            var v = Piv(root.transform, "Visual");
            var wood = WoodM("wood_plank");
            var dark = TimberM("timber_dark");
            float w = 3.2f, d = 2.6f;
            for (int sx = -1; sx <= 1; sx += 2)
                for (int sz = -1; sz <= 1; sz += 2)
                    CY(v, "Post", 0.09f, 2.45f, new Vector3(sx * w * 0.46f, 1.22f, sz * d * 0.36f), dark, 8);
            B(v, "Counter", new Vector3(w, 0.9f, 0.7f), new Vector3(0f, 0.45f, d * 0.3f), wood);
            B(v, "CounterTop", new Vector3(w + 0.16f, 0.08f, 0.86f), new Vector3(0f, 0.94f, d * 0.3f), WoodM("wood_plank"));
            B(v, "BackShelf", new Vector3(w * 0.9f, 0.1f, 0.5f), new Vector3(0f, 1.5f, -d * 0.22f), wood);
            B(v, "BackPanel", new Vector3(w * 0.92f, 1.1f, 0.06f), new Vector3(0f, 0.75f, -d * 0.34f), dark);
            // 条纹遮阳棚
            BR(v, "Canopy", new Vector3(w + 0.9f, 0.07f, 3.1f), new Vector3(0f, 2.72f, 0.05f),
                Quaternion.Euler(-13f, 0f, 0f), AwningM(clothKey));
            B(v, "Valance", new Vector3(w + 0.9f, 0.34f, 0.06f), new Vector3(0f, 2.36f, 1.55f), ClothM(clothKey));
            for (int i = 0; i < 7; i++)
            {
                float x = w * (-0.42f + i * 0.14f);
                CNR(v, "Tassel", 0.09f, 0.22f, new Vector3(x, 2.28f, 1.56f), Quaternion.Euler(180f, 0f, 0f),
                    ClothM(clothKey), 6);
            }
            // 货品
            for (int i = 0; i < 6; i++)
            {
                float x = (i - 2.5f) * 0.46f;
                bool fruit = i % 2 == 0;
                if (fruit)
                {
                    Color fc = GoodsColor(i);
                    SP(v, "Fruit", 0.14f, new Vector3(x, 1.08f, d * 0.3f + 0.1f),
                        MapMaterials.Solid("roa_fruit_" + i + "_" + ColorUtility.ToHtmlStringRGB(fc), fc, 0.35f), 8);
                }
                else
                {
                    B(v, "Loaf", new Vector3(0.3f, 0.14f, 0.2f), new Vector3(x, 1.06f, d * 0.28f), WoodM("wood_light"));
                }
            }
            // 后架上的罐子
            for (int i = 0; i < 4; i++)
            {
                CY(v, "Jar", 0.1f, 0.26f, new Vector3(-1.2f + i * 0.8f, 1.7f, -d * 0.22f),
                    ClothM(i % 2 == 0 ? "cloth_teal" : "cloth_red"), 8);
            }
            B(v, "Crate", new Vector3(0.62f, 0.62f, 0.62f), new Vector3(-w * 0.32f, 0.31f, -0.9f), WoodM("wood_plank"));
            B(v, "Barrel", new Vector3(0.5f, 0.72f, 0.5f), new Vector3(w * 0.34f, 0.36f, -0.95f), WoodM("wood_barrel"));
            Kit.Optimize(root, false);
            AddRootBlocker(root, new Vector3(w, 1.0f, 1.6f), new Vector3(0f, 0.5f, 0f));
            Kit.MakeFadeable(root, 0.3f);
            return root;
        }

        // ================================================================================
        // 装饰：横幅 / 篝火 / 帐篷 / 板车 / 魔法阵
        // ================================================================================
        internal static GameObject Bunting(Transform parent, Vector3 pos, float yaw, float length)
        {
            var root = Kit.Pivot(parent, "Bunting", pos, yaw);
            var t = root.transform;
            var iron = Mat("iron");
            for (int s = -1; s <= 1; s += 2)
            {
                CY(t, "Pole", 0.07f, 4.3f, new Vector3(s * length * 0.5f, 2.15f, 0f), iron, 8, true);
                SP(t, "Cap", 0.12f, new Vector3(s * length * 0.5f, 4.36f, 0f), Mat("gold"), 8);
            }
            BR(t, "Rope", new Vector3(length, 0.035f, 0.035f), new Vector3(0f, 4.02f, 0f),
                Quaternion.Euler(0f, 0f, 0f), Mat("wood_dark"));
            int n = 9;
            for (int i = 0; i < n; i++)
            {
                float x = -length * 0.5f + length * (i + 0.5f) / n;
                float sag = Mathf.Sin((i + 0.5f) / n * Mathf.PI) * 0.42f;
                string cloth = i % 3 == 0 ? "cloth_red" : (i % 3 == 1 ? "cloth_blue" : "cloth_gold");
                var mat = i % 3 == 2
                    ? MapMaterials.Emissive("roa_bunting_gold", MapMaterials.GlowGold, 0.55f)
                    : ClothM(cloth);
                var tri = Kit.GableFace(t, "Pennant", 0.34f, 0.5f, 0.04f,
                    new Vector3(x, 3.78f - sag, 0f), mat, 180f);
                tri.transform.localRotation = Quaternion.Euler(0f, 0f, 180f);
            }
            return root;
        }

        internal static GameObject Campfire(Transform parent, Vector3 pos)
        {
            var root = Kit.Pivot(parent, "Campfire", pos, 0f);
            var v = Piv(root.transform, "Visual");
            var stone = StoneM("stone_wall");
            var stoneDark = StoneM("stone_dark");
            var wood = WoodM("wood_dark");
            for (int i = 0; i < 8; i++)
            {
                float a = i * 45f;
                Vector3 dir = KitMath.OnCircle(0.72f, a);
                SP(v, "Stone", 0.2f, new Vector3(dir.x, 0.1f, dir.z), i % 2 == 0 ? stone : stoneDark, 7);
            }
            for (int i = 0; i < 4; i++)
            {
                float a = i * 90f + 20f;
                BR(v, "Log", new Vector3(0.16f, 0.16f, 1.1f), new Vector3(0f, 0.16f, 0f),
                    Quaternion.Euler(90f, a, 0f), wood);
            }
            CN(v, "Fire", 0.4f, 0.9f, new Vector3(0f, 0.62f, 0f), FireGlow(), 8);
            CN(v, "Fire2", 0.24f, 0.6f, new Vector3(0.1f, 0.85f, -0.05f),
                MapMaterials.Emissive("roa_fire2", new Color(1f, 0.78f, 0.3f), 3.2f), 7);
            Kit.Optimize(root, false);
            Kit.PointLight(root.transform, new Vector3(0f, 1.1f, 0f), new Color(1f, 0.62f, 0.3f), 6.5f, 1.5f);
            return root;
        }

        internal static GameObject Tent(Transform parent, Vector3 pos, float yaw, string clothKey)
        {
            var root = Kit.Pivot(parent, "Tent", pos, yaw);
            var v = Piv(root.transform, "Visual");
            var cloth = ClothM(clothKey);
            var wood = WoodM("wood_dark");
            B(v, "Ground", new Vector3(2.6f, 0.03f, 3.1f), new Vector3(0f, 0.02f, 0f), ClothM("cloth_cream"));
            for (int s = -1; s <= 1; s += 2)
            {
                BR(v, "Wall", new Vector3(2.7f, 0.05f, 2.2f), new Vector3(0f, 1.02f, s * 0.52f),
                    Quaternion.Euler(s * 55f, 0f, 0f), cloth);
                CY(v, "Pole", 0.055f, 2.1f, new Vector3(s * 1.25f, 1.05f, 0f), wood, 6);
                B(v, "Pole", new Vector3(0.09f, 0.09f, 2.9f), new Vector3(s * 1.25f, 2.08f, 0f), wood);
            }
            BR(v, "Entrance", new Vector3(1.15f, 0.04f, 1.1f), new Vector3(0.28f, 0.62f, 1.12f),
                Quaternion.Euler(64f, 18f, 0f), ClothM("cloth_cream"));
            Kit.Optimize(root, false);
            var bc = root.AddComponent<BoxCollider>();
            bc.center = new Vector3(0f, 1.0f, 0f);
            bc.size = new Vector3(2.6f, 2.0f, 3.0f);
            return root;
        }

        internal static GameObject Cart(Transform parent, Vector3 pos, float yaw)
        {
            var root = Kit.Pivot(parent, "Cart", pos, yaw);
            var v = Piv(root.transform, "Visual");
            var wood = WoodM("wood_plank");
            var dark = TimberM("timber_dark");
            B(v, "Bed", new Vector3(1.5f, 0.14f, 2.7f), new Vector3(0f, 0.82f, 0f), wood);
            for (int s = -1; s <= 1; s += 2)
            {
                B(v, "Side", new Vector3(0.09f, 0.42f, 2.7f), new Vector3(s * 0.72f, 1.05f, 0f), dark);
                CYR(v, "Wheel", 0.55f, 0.14f, new Vector3(s * 0.86f, 0.56f, -0.6f),
                    Quaternion.Euler(90f, 0f, 0f), dark, 12);
                CYR(v, "Wheel", 0.55f, 0.14f, new Vector3(s * 0.86f, 0.56f, 0.6f),
                    Quaternion.Euler(90f, 0f, 0f), dark, 12);
                BR(v, "Shaft", new Vector3(0.1f, 0.1f, 1.7f), new Vector3(s * 0.6f, 0.9f, 1.9f),
                    Quaternion.Euler(12f, 0f, 0f), dark);
            }
            B(v, "Load1", new Vector3(0.9f, 0.5f, 0.8f), new Vector3(-0.1f, 1.15f, -0.4f), wood);
            B(v, "Load2", new Vector3(0.7f, 0.42f, 0.7f), new Vector3(0.18f, 1.1f, 0.55f), WoodM("wood_barrel"));
            Kit.Optimize(root, false);
            AddRootBlocker(root, new Vector3(1.8f, 1.3f, 2.9f), new Vector3(0f, 0.65f, 0f));
            return root;
        }

        internal static GameObject RuneCircle(Transform parent, Vector3 pos, bool violet)
        {
            var root = Kit.Pivot(parent, "RuneCircle", pos, 0f);
            var t = root.transform;
            var ring = Piv(t, "Ring");
            for (int i = 0; i < 16; i++)
            {
                float a = i * 22.5f;
                Vector3 dir = KitMath.OnCircle(2.5f, a);
                B(ring, "Rune", new Vector3(0.22f, 0.05f, 0.6f), new Vector3(dir.x, 0.04f, dir.z),
                    violet ? RuneViolet() : RuneCyan(), -a);
            }
            CY(t, "Core", 1.7f, 0.03f, new Vector3(0f, 0.03f, 0f),
                MapMaterials.Transparent("roa_rune_glow", violet ? MapMaterials.GlowViolet : MapMaterials.GlowCyan, 0.35f), 20);
            for (int i = 0; i < 4; i++)
            {
                float a = i * 90f + 45f;
                Vector3 dir = KitMath.OnCircle(3.05f, a);
                CY(t, "Pillar", 0.18f, 1.5f, new Vector3(dir.x, 0.75f, dir.z), StoneM("stone_light"), 8);
                SP(t, "RuneStone", 0.16f, new Vector3(dir.x, 1.62f, dir.z),
                    MapMaterials.Emissive("roa_runestone_" + i, violet ? MapMaterials.GlowViolet : MapMaterials.GlowCyan, 1.6f), 8);
            }
            Kit.Optimize(root, false);
            return root;
        }

        // ================================================================================
        // 商店（杂货铺 / 魔法商店 / 面包房 / 裁缝铺）
        // ================================================================================
        internal static GameObject Shop(Transform parent, string name, Vector3 pos, float yaw,
            float w, float d, ShopKind kind, string label, string wallKey, string upperKey, string roofKey,
            string awningCloth, bool chimney)
        {
            var root = Kit.Pivot(parent, name, pos, yaw);
            var t = root.transform;
            var v = Piv(t, "Visual");
            var wall = WallM(wallKey);
            var upper = WallM(upperKey);
            var timber = TimberM("timber_dark");
            var lightStone = StoneM("stone_light");
            var darkStone = StoneM("stone_dark");
            var roof = RoofM(roofKey);

            float hw = w * 0.5f, hd = d * 0.5f;
            float wt = 0.34f;
            float plinth = 0.12f;
            float h1 = 2.95f;
            float h2 = 2.35f;
            float roofH = 2.3f;
            float wallTop = plinth + h1 + h2;
            float openW = 2.8f;
            float openH = 2.5f;

            B(v, "Foundation", new Vector3(w + 0.3f, plinth, d + 0.3f), new Vector3(0f, plinth * 0.5f, 0f), darkStone);
            SL(v, "Floor", new Vector3(w - 0.08f, 0.03f, d - 0.08f), new Vector3(0f, 0.045f, 0f), WoodM("wood_plank"));

            // 一层墙体（正面留店门洞）
            float segW = hw - openW * 0.5f - 0.02f;
            B(v, "FrontL", new Vector3(segW, h1, wt), new Vector3(-(hw - segW * 0.5f), plinth + h1 * 0.5f, hd - wt * 0.5f), wall);
            B(v, "FrontR", new Vector3(segW, h1, wt), new Vector3(hw - segW * 0.5f, plinth + h1 * 0.5f, hd - wt * 0.5f), wall);
            B(v, "FrontTop", new Vector3(openW + 0.1f, h1 - openH, wt),
                new Vector3(0f, plinth + openH + (h1 - openH) * 0.5f, hd - wt * 0.5f), wall);
            B(v, "SideL", new Vector3(wt, h1, d), new Vector3(-hw + wt * 0.5f, plinth + h1 * 0.5f, 0f), wall);
            B(v, "SideR", new Vector3(wt, h1, d), new Vector3(hw - wt * 0.5f, plinth + h1 * 0.5f, 0f), wall);
            B(v, "Back", new Vector3(w, h1, wt), new Vector3(0f, plinth + h1 * 0.5f, -hd + wt * 0.5f), wall);
            // 一层石墙裙
            B(v, "SkirtL", new Vector3(segW + 0.02f, 0.62f, wt + 0.06f), new Vector3(-(hw - segW * 0.5f), 0.31f, hd - wt * 0.5f), darkStone);
            B(v, "SkirtR", new Vector3(segW + 0.02f, 0.62f, wt + 0.06f), new Vector3(hw - segW * 0.5f, 0.31f, hd - wt * 0.5f), darkStone);
            // 门框
            ArchFrame(Piv(v, "DoorFace", new Vector3(0f, 0f, hd - wt * 0.5f)), openW, openH, lightStone, timber);

            // 二层木筋墙
            B(v, "Upper", new Vector3(w + 0.24f, h2, d + 0.24f),
                new Vector3(0f, plinth + h1 + h2 * 0.5f, 0f), upper);
            for (int s = -1; s <= 1; s += 2)
            {
                B(v, "BeltF", new Vector3(w + 0.4f, 0.2f, 0.16f),
                    new Vector3(0f, plinth + h1, hd + 0.05f), timber);
                B(v, "BeltB", new Vector3(w + 0.4f, 0.2f, 0.16f),
                    new Vector3(0f, plinth + h1, -hd - 0.05f), timber);
                B(v, "CornerPost", new Vector3(0.24f, h2, 0.24f),
                    new Vector3(s * (hw + 0.05f), plinth + h1 + h2 * 0.5f, hd + 0.05f), timber);
                B(v, "CornerPost", new Vector3(0.24f, h2, 0.24f),
                    new Vector3(s * (hw + 0.05f), plinth + h1 + h2 * 0.5f, -hd - 0.05f), timber);
            }
            for (int i = 0; i < 4; i++)
            {
                B(v, "Stud", new Vector3(0.12f, h2 - 0.2f, 0.1f),
                    new Vector3(-hw * 0.66f + i * hw * 0.44f, plinth + h1 + h2 * 0.5f, hd + 0.09f), timber);
            }
            // 一层正面斜撑
            for (int s = -1; s <= 1; s += 2)
            {
                BR(v, "Brace", new Vector3(0.11f, 1.5f, 0.08f),
                    new Vector3(s * (hw - segW * 0.5f), plinth + h1 * 0.62f, hd + 0.04f),
                    Quaternion.Euler(0f, 0f, s * 34f), timber);
            }
            // 窗
            var faceFront = Piv(v, "FaceFront", new Vector3(0f, 0f, hd + 0.12f));
            Win(faceFront, new Vector3(-hw * 0.3f, plinth + h1 + h2 * 0.56f, 0f), 0.86f, 1.0f, kind == ShopKind.Bakery, true, false, timber);
            Win(faceFront, new Vector3(0f, plinth + h1 + h2 * 0.56f, 0f), 0.86f, 1.0f, true, true, false, timber);
            Win(faceFront, new Vector3(hw * 0.3f, plinth + h1 + h2 * 0.56f, 0f), 0.86f, 1.0f, kind == ShopKind.Magic, true, false, timber);
            var faceSideR = Piv(v, "FaceSideR", new Vector3(hw + 0.12f, 0f, 0f), 90f);
            Win(faceSideR, new Vector3(0.6f, plinth + h1 * 0.6f, 0f), 0.8f, 1.0f, false, false, false, timber);
            Win(faceSideR, new Vector3(-1.2f, plinth + h1 * 0.6f, 0f), 0.8f, 1.0f, false, false, true, timber);
            var faceSideL = Piv(v, "FaceSideL", new Vector3(-hw - 0.12f, 0f, 0f), -90f);
            Win(faceSideL, new Vector3(0.4f, plinth + h1 * 0.6f, 0f), 0.8f, 1.0f, true, false, false, timber);
            var faceBack = Piv(v, "FaceBack", new Vector3(0f, 0f, -hd - 0.12f), 180f);
            Win(faceBack, new Vector3(-hw * 0.28f, plinth + h1 + h2 * 0.56f, 0f), 0.8f, 0.95f, false, true, false, timber);
            Win(faceBack, new Vector3(hw * 0.28f, plinth + h1 + h2 * 0.56f, 0f), 0.8f, 0.95f, false, true, false, timber);

            // 屋顶 + 山墙
            Kit.Mesh(v, "Roof", Kit.GableRoofMesh(w + 0.24f, d + 0.24f, roofH, 0.55f, 0.16f),
                new Vector3(0f, wallTop, 0f), roof, false);
            B(v, "RidgeCap", new Vector3(w + 0.24f + 1.2f, 0.17f, 0.28f), new Vector3(0f, wallTop + roofH + 0.04f, 0f), roof);
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.GableFace(v, "Gable", d + 0.24f, roofH, 0.26f, new Vector3(s * (w * 0.5f + 0.12f), wallTop, 0f),
                    upper, s * 90f);
                CYR(v, "GableWin", 0.3f, 0.08f, new Vector3(s * (w * 0.5f + 0.27f), wallTop + roofH * 0.34f, 0f),
                    Quaternion.Euler(0f, 0f, 90f), WinDay(), 12);
                B(v, "Eave", new Vector3(0.14f, 0.16f, d + 2.0f), new Vector3(s * (w * 0.5f + 0.55f), wallTop - 0.14f, 0f),
                    timber);
            }
            if (chimney)
            {
                B(v, "Chimney", new Vector3(0.55f, 1.7f, 0.55f),
                    new Vector3(-hw * 0.46f, wallTop + roofH * 0.56f, 0f), darkStone);
                B(v, "ChimneyCap", new Vector3(0.75f, 0.12f, 0.75f),
                    new Vector3(-hw * 0.46f, wallTop + roofH * 0.56f + 0.9f, 0f), lightStone);
                if (kind != ShopKind.Magic)
                    Kit.Smoke(v, new Vector3(-hw * 0.46f, wallTop + roofH * 0.56f + 1.0f, 0f),
                        new Color(0.94f, 0.93f, 0.91f), 3, 0.2f);
            }

            // 遮阳棚 + 招牌
            Awning(Piv(v, "AwningFace", new Vector3(0f, 0f, hd - wt * 0.5f)), openW + 1.0f, plinth + h1 - 0.32f, 2.1f, awningCloth);
            float signY = plinth + h1 + 0.42f;
            Quaternion signRot = Quaternion.identity;

            // 店内
            float innerZ = hd - wt - 1.2f;
            Counter(v, new Vector3(0f, 0f, -hd + wt + 1.0f), Mathf.Min(w - 1.6f, 4.2f), 0.75f, WoodM("wood_plank"), 5);
            var shelfFace = Piv(v, "ShelfFace", new Vector3(hw - wt - 0.06f, 0f, 0f), -90f);
            Shelf(shelfFace, new Vector3(-0.9f, 0f, 0f), 2.4f, 4);
            if (kind == ShopKind.Magic)
            {
                // 魔法商店：水晶货架 + 发光法阵
                for (int i = 0; i < 5; i++)
                {
                    CNR(v, "Crystal", 0.15f, 0.52f, new Vector3(-1.4f + i * 0.7f, 0.42f, innerZ - 0.2f),
                        Quaternion.Euler(180f, i * 60f, 0f), RuneViolet(), 6);
                }
                CY(v, "MagicCircle", 0.9f, 0.03f, new Vector3(0.9f, 0.03f, -hd + wt + 0.9f),
                    MapMaterials.Transparent("roa_shop_rune", MapMaterials.GlowCyan, 0.4f), 18);
            }
            else if (kind == ShopKind.Bakery)
            {
                for (int i = 0; i < 4; i++)
                    B(v, "Bread", new Vector3(0.44f, 0.16f, 0.3f), new Vector3(-1.2f + i * 0.8f, 0.44f, innerZ + 0.3f),
                        WoodM("wood_light"));
            }
            else if (kind == ShopKind.Tailor)
            {
                for (int i = 0; i < 3; i++)
                    B(v, "ClothRoll", new Vector3(0.34f, 0.34f, 0.8f), new Vector3(-1.0f + i * 0.7f, 0.4f, innerZ),
                        ClothM(i == 0 ? "cloth_red" : (i == 1 ? "cloth_blue" : "cloth_cream")));
            }
            else
            {
                for (int i = 0; i < 4; i++)
                    B(v, "Crate", new Vector3(0.5f, 0.5f, 0.5f), new Vector3(-1.1f + i * 0.72f, 0.25f, innerZ + 0.4f),
                        WoodM("wood_plank"));
            }
            // 店内吊灯
            B(v, "LampChain", new Vector3(0.04f, 0.7f, 0.04f), new Vector3(0f, plinth + h1 - 0.6f, 0f), Mat("iron"));
            B(v, "LampGlow", new Vector3(0.26f, 0.2f, 0.26f), new Vector3(0f, plinth + h1 - 1.0f, 0f), LampGlow());
            B(v, "Rug", new Vector3(1.4f, 0.03f, 2.2f), new Vector3(0f, 0.06f, 0.4f), ClothM("cloth_red"));

            Kit.Optimize(root, false);

            // 招牌（合并后再加，避免被当网格合并掉文字）
            Kit.SignBoard(t, label, new Vector3(0f, signY, hd + 0.16f), 0f,
                Mathf.Min(w * 0.52f, 3.2f), 0.62f, MapMaterials.ClothCream, Ink);
            // 墙面碰撞（合并后加，店门保持可走进去）
            Blocker(t, "BlockFrontL", new Vector3(segW, h1, 0.5f), new Vector3(-(hw - segW * 0.5f), plinth + h1 * 0.5f, hd - wt * 0.5f));
            Blocker(t, "BlockFrontR", new Vector3(segW, h1, 0.5f), new Vector3(hw - segW * 0.5f, plinth + h1 * 0.5f, hd - wt * 0.5f));
            Blocker(t, "BlockSideL", new Vector3(0.5f, h1, d), new Vector3(-hw + 0.1f, plinth + h1 * 0.5f, 0f));
            Blocker(t, "BlockSideR", new Vector3(0.5f, h1, d), new Vector3(hw - 0.1f, plinth + h1 * 0.5f, 0f));
            Blocker(t, "BlockBack", new Vector3(w, h1, 0.5f), new Vector3(0f, plinth + h1 * 0.5f, -hd + 0.1f));
            Kit.MakeFadeable(root, 0.3f);
            return root;
        }

        // ================================================================================
        // 旅店
        // ================================================================================
        internal static GameObject Inn(Transform parent, Vector3 pos, float yaw)
        {
            var root = Kit.Pivot(parent, "Inn", pos, yaw);
            var t = root.transform;
            var v = Piv(t, "Visual");
            float w = 11.5f, dir = 8.5f;
            float hw = w * 0.5f, hd = dir * 0.5f;
            float wt = 0.36f, plinth = 0.14f;
            float h1 = 3.15f, h2 = 2.85f, roofH = 2.7f;
            float wallTop = plinth + h1 + h2;
            float openW = 2.2f, openH = 2.55f;
            var wall = WallM("plaster_warm");
            var upper = WallM("plaster_cream");
            var timber = TimberM("timber_dark");
            var timberMid = TimberM("timber_mid");
            var darkStone = StoneM("stone_dark");
            var lightStone = StoneM("stone_light");
            var roof = RoofM("roof_burgundy");

            B(v, "Foundation", new Vector3(w + 0.3f, plinth, dir + 0.3f), new Vector3(0f, plinth * 0.5f, 0f), darkStone);
            SL(v, "Floor", new Vector3(w - 0.1f, 0.03f, dir - 0.1f), new Vector3(0f, 0.05f, 0f), WoodM("wood_plank"));
            B(v, "FrontL", new Vector3(hw - openW * 0.5f - 0.02f, h1, wt),
                new Vector3(-(openW * 0.5f + (hw - openW * 0.5f) * 0.5f), plinth + h1 * 0.5f, hd - wt * 0.5f), wall);
            B(v, "FrontR", new Vector3(hw - openW * 0.5f - 0.02f, h1, wt),
                new Vector3(openW * 0.5f + (hw - openW * 0.5f) * 0.5f, plinth + h1 * 0.5f, hd - wt * 0.5f), wall);
            B(v, "FrontTop", new Vector3(openW + 0.1f, h1 - openH, wt),
                new Vector3(0f, plinth + openH + (h1 - openH) * 0.5f, hd - wt * 0.5f), wall);
            B(v, "SideL", new Vector3(wt, h1, dir), new Vector3(-hw + wt * 0.5f, plinth + h1 * 0.5f, 0f), wall);
            B(v, "SideR", new Vector3(wt, h1, dir), new Vector3(hw - wt * 0.5f, plinth + h1 * 0.5f, 0f), wall);
            B(v, "Back", new Vector3(w, h1, wt), new Vector3(0f, plinth + h1 * 0.5f, -hd + wt * 0.5f), wall);
            ArchFrame(Piv(v, "DoorFace", new Vector3(0f, 0f, hd - wt * 0.5f)), openW, openH, lightStone, timber);
            // 半开的双开门
            BR(v, "DoorLeafL", new Vector3(openW * 0.48f, openH * 0.96f, 0.1f),
                new Vector3(-openW * 0.46f, plinth + openH * 0.48f, hd - wt * 0.2f), Quaternion.Euler(0f, -52f, 0f),
                WoodM("wood_dark"));
            BR(v, "DoorLeafR", new Vector3(openW * 0.48f, openH * 0.96f, 0.1f),
                new Vector3(openW * 0.46f, plinth + openH * 0.48f, hd - wt * 0.2f), Quaternion.Euler(0f, 52f, 0f),
                WoodM("wood_dark"));

            B(v, "Upper", new Vector3(w + 0.3f, h2, dir + 0.3f), new Vector3(0f, plinth + h1 + h2 * 0.5f, 0f), upper);
            B(v, "BeltF", new Vector3(w + 0.5f, 0.22f, 0.18f), new Vector3(0f, plinth + h1, hd + 0.07f), timber);
            B(v, "BeltB", new Vector3(w + 0.5f, 0.22f, 0.18f), new Vector3(0f, plinth + h1, -hd - 0.07f), timber);
            for (int s = -1; s <= 1; s += 2)
            {
                B(v, "BeltS", new Vector3(0.18f, 0.22f, dir + 0.5f), new Vector3(s * (hw + 0.07f), plinth + h1, 0f), timber);
                B(v, "CornerPost", new Vector3(0.26f, h2, 0.26f), new Vector3(s * (hw + 0.06f), plinth + h1 + h2 * 0.5f, hd + 0.06f), timber);
                B(v, "CornerPostB", new Vector3(0.26f, h2, 0.26f), new Vector3(s * (hw + 0.06f), plinth + h1 + h2 * 0.5f, -hd - 0.06f), timber);
                BR(v, "BraceG", new Vector3(0.1f, 1.7f, 0.08f),
                    new Vector3(s * (hw - 1.3f), plinth + 1.35f, hd + 0.03f),
                    Quaternion.Euler(0f, 0f, s * 30f), timber);
            }
            // 一层窗
            var faceFront = Piv(v, "FaceFront", new Vector3(0f, 0f, hd + 0.12f));
            Win(faceFront, new Vector3(-3.4f, plinth + 1.75f, 0f), 0.95f, 1.2f, true, true, true, timber);
            Win(faceFront, new Vector3(3.4f, plinth + 1.75f, 0f), 0.95f, 1.2f, true, true, true, timber);
            Win(faceFront, new Vector3(-1.6f, plinth + h1 + h2 * 0.56f, 0f), 0.84f, 1.0f, true, true, false, timber);
            Win(faceFront, new Vector3(1.6f, plinth + h1 + h2 * 0.56f, 0f), 0.84f, 1.0f, true, true, false, timber);
            Win(faceFront, new Vector3(0f, plinth + h1 + h2 * 0.56f, 0f), 0.84f, 1.0f, false, true, false, timber);
            var faceSideR = Piv(v, "FaceSideR", new Vector3(hw + 0.14f, 0f, 0f), 90f);
            Win(faceSideR, new Vector3(-1.6f, plinth + h1 * 0.6f, 0f), 0.9f, 1.15f, false, false, true, timber);
            Win(faceSideR, new Vector3(1.4f, plinth + h1 * 0.6f, 0f), 0.9f, 1.15f, true, false, false, timber);
            Win(faceSideR, new Vector3(0f, plinth + h1 + h2 * 0.56f, 0f), 0.84f, 1.0f, true, true, false, timber);
            var faceSideL = Piv(v, "FaceSideL", new Vector3(-hw - 0.14f, 0f, 0f), -90f);
            Win(faceSideL, new Vector3(-1.4f, plinth + h1 * 0.6f, 0f), 0.9f, 1.15f, false, false, false, timber);
            Win(faceSideL, new Vector3(1.6f, plinth + h1 * 0.6f, 0f), 0.9f, 1.15f, false, false, true, timber);
            Win(faceSideL, new Vector3(0f, plinth + h1 + h2 * 0.56f, 0f), 0.84f, 1.0f, false, true, false, timber);
            var faceBack = Piv(v, "FaceBack", new Vector3(0f, 0f, -hd - 0.14f), 180f);
            Win(faceBack, new Vector3(-2.4f, plinth + h1 + h2 * 0.56f, 0f), 0.84f, 1.0f, false, true, false, timber);
            Win(faceBack, new Vector3(2.4f, plinth + h1 + h2 * 0.56f, 0f), 0.84f, 1.0f, false, true, false, timber);

            // 屋顶 + 山墙 + 烟囱
            Kit.Mesh(v, "Roof", Kit.GableRoofMesh(w + 0.3f, dir + 0.3f, roofH, 0.6f, 0.17f),
                new Vector3(0f, wallTop, 0f), roof, false);
            B(v, "RidgeCap", new Vector3(w + 0.3f + 1.3f, 0.18f, 0.3f), new Vector3(0f, wallTop + roofH + 0.04f, 0f), roof);
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.GableFace(v, "Gable", dir + 0.3f, roofH, 0.28f, new Vector3(s * (hw + 0.15f), wallTop, 0f), upper, s * 90f);
                CYR(v, "GableWin", 0.34f, 0.08f, new Vector3(s * (hw + 0.31f), wallTop + roofH * 0.34f, 0f),
                    Quaternion.Euler(0f, 0f, 90f), WinLit(), 12);
                B(v, "Eave", new Vector3(0.15f, 0.18f, dir + 2.2f), new Vector3(s * (hw + 0.6f), wallTop - 0.15f, 0f), timber);
            }
            B(v, "Chimney", new Vector3(0.62f, 2.0f, 0.62f), new Vector3(-hw * 0.52f, wallTop + roofH * 0.58f, -0.6f), darkStone);
            B(v, "ChimneyCap", new Vector3(0.82f, 0.14f, 0.82f), new Vector3(-hw * 0.52f, wallTop + roofH * 0.58f + 1.06f, -0.6f), lightStone);
            Kit.Smoke(v, new Vector3(-hw * 0.52f, wallTop + roofH * 0.58f + 1.16f, -0.6f), new Color(0.94f, 0.93f, 0.92f), 4, 0.22f);

            // 门上的木阳台
            float balY = plinth + h1;
            B(v, "Balcony", new Vector3(4.6f, 0.16f, 1.5f), new Vector3(0f, balY, hd + 0.75f), timberMid);
            for (int s = -1; s <= 1; s += 2)
            {
                B(v, "BalPost", new Vector3(0.13f, 1.05f, 0.13f), new Vector3(s * 2.15f, balY + 0.6f, hd + 1.4f), timberMid);
                BR(v, "BalBracket", new Vector3(0.12f, 0.12f, 1.2f), new Vector3(s * 1.9f, balY - 0.5f, hd + 0.5f),
                    Quaternion.Euler(42f, 0f, 0f), timberMid);
            }
            B(v, "BalRail", new Vector3(4.6f, 0.09f, 0.09f), new Vector3(0f, balY + 1.06f, hd + 1.4f), timberMid);
            for (int i = 0; i < 7; i++)
                B(v, "Baluster", new Vector3(0.06f, 0.9f, 0.06f), new Vector3(-2.1f + i * 0.7f, balY + 0.55f, hd + 1.4f), timberMid);

            // 店内：壁炉 / 桌子 / 吧台 / 地毯
            B(v, "Fireplace", new Vector3(2.6f, 3.0f, 0.6f), new Vector3(-hw + 1.9f, 1.5f, -hd + 0.5f), lightStone);
            B(v, "FireHole", new Vector3(1.5f, 1.1f, 0.4f), new Vector3(-hw + 1.9f, 0.62f, -hd + 0.82f), darkStone);
            B(v, "Fire", new Vector3(1.1f, 0.55f, 0.3f), new Vector3(-hw + 1.9f, 0.35f, -hd + 0.9f), FireGlow());
            B(v, "Mantel", new Vector3(3.0f, 0.18f, 0.8f), new Vector3(-hw + 1.9f, 1.95f, -hd + 0.7f), timberMid);
            for (int i = 0; i < 2; i++)
            {
                var tp = Piv(v, "Table", new Vector3(-1.0f + i * 3.4f, 0f, 0.6f));
                B(tp, "Top", new Vector3(1.5f, 0.1f, 1.5f), new Vector3(0f, 0.78f, 0f), WoodM("wood_plank"));
                for (int sx = -1; sx <= 1; sx += 2)
                    for (int sz = -1; sz <= 1; sz += 2)
                        B(tp, "Leg", new Vector3(0.1f, 0.78f, 0.1f), new Vector3(sx * 0.62f, 0.39f, sz * 0.62f), WoodM("wood_dark"));
                B(tp, "Mug", new Vector3(0.16f, 0.2f, 0.16f), new Vector3(0.25f, 0.92f, 0.2f), Mat("steel"));
            }
            var benchPiv = Piv(v, "BenchSeat", new Vector3(-1.0f, 0f, 2.35f));
            Kit.Box(benchPiv, "Seat", new Vector3(2.6f, 0.1f, 0.44f), new Vector3(0f, 0.46f, 0f), WoodM("wood_plank"), 0f, false);
            B(v, "BarCounter", new Vector3(4.4f, 1.0f, 0.8f), new Vector3(hw - 2.9f, 0.5f, -hd + 1.6f), WoodM("wood_dark"));
            B(v, "BarTop", new Vector3(4.7f, 0.1f, 1.0f), new Vector3(hw - 2.9f, 1.02f, -hd + 1.6f), WoodM("wood_plank"));
            for (int i = 0; i < 4; i++)
                CY(v, "Bottle", 0.08f, 0.3f, new Vector3(hw - 4.3f + i * 0.9f, 1.2f, -hd + 1.6f),
                    ClothM(i % 2 == 0 ? "cloth_green" : "cloth_orange"), 7);
            B(v, "Rug", new Vector3(2.0f, 0.03f, 3.4f), new Vector3(0f, 0.07f, 0.4f), ClothM("cloth_red"));
            B(v, "Chandelier", new Vector3(1.0f, 0.08f, 1.0f), new Vector3(0f, plinth + h1 - 0.5f, 0f), Mat("iron"));
            for (int i = 0; i < 4; i++)
            {
                Vector3 candleDir = KitMath.OnCircle(0.5f, i * 90f);
                B(v, "Candle", new Vector3(0.1f, 0.26f, 0.1f), new Vector3(candleDir.x, plinth + h1 - 0.32f, candleDir.z), LampGlow());
            }

            Kit.Optimize(root, false);
            // 吊挂招牌（垂直于墙面，沿街可见）
            var signArm = Piv(t, "HangingSign", new Vector3(hw + 0.1f, plinth + h1 + 0.9f, hd - 0.3f));
            B(signArm, "Arm", new Vector3(0.08f, 0.08f, 1.3f), new Vector3(0.65f, 0.35f, 0f), Mat("iron"));
            B(signArm, "ChainL", new Vector3(0.03f, 0.3f, 0.03f), new Vector3(0.25f, 0.12f, 0f), Mat("iron"));
            B(signArm, "ChainR", new Vector3(0.03f, 0.3f, 0.03f), new Vector3(1.05f, 0.12f, 0f), Mat("iron"));
            Kit.SignBoard(signArm, "旅店", new Vector3(0.65f, -0.3f, 0f), 90f, 1.25f, 0.72f,
                MapMaterials.ClothCream, Ink);
            // 门口招牌 + 灯笼
            Kit.SignBoard(t, "旅店 · 炉火与麦酒", new Vector3(0f, plinth + h1 + 0.48f, hd + 0.2f), 0f, 3.6f, 0.55f,
                MapMaterials.ClothCream, Ink);
            PorchLantern(Piv(t, "PorchFace", new Vector3(0f, 0f, hd - wt * 0.5f)), new Vector3(-1.75f, 2.4f, 0f), false);
            PorchLantern(Piv(t, "PorchFace2", new Vector3(0f, 0f, hd - wt * 0.5f)), new Vector3(1.75f, 2.4f, 0f), false);
            Blocker(t, "BlockFrontL", new Vector3(hw - openW * 0.5f, h1, 0.5f),
                new Vector3(-(openW * 0.5f + (hw - openW * 0.5f) * 0.5f), plinth + h1 * 0.5f, hd - wt * 0.5f));
            Blocker(t, "BlockFrontR", new Vector3(hw - openW * 0.5f, h1, 0.5f),
                new Vector3(openW * 0.5f + (hw - openW * 0.5f) * 0.5f, plinth + h1 * 0.5f, hd - wt * 0.5f));
            Blocker(t, "BlockSideL", new Vector3(0.5f, h1, dir), new Vector3(-hw + 0.1f, plinth + h1 * 0.5f, 0f));
            Blocker(t, "BlockSideR", new Vector3(0.5f, h1, dir), new Vector3(hw - 0.1f, plinth + h1 * 0.5f, 0f));
            Blocker(t, "BlockBack", new Vector3(w, h1, 0.5f), new Vector3(0f, plinth + h1 * 0.5f, -hd + 0.1f));
            Kit.MakeFadeable(root, 0.3f);
            return root;
        }

        // ================================================================================
        // 冒险者协会大厅（正立面山墙 + 大拱门 + 石砌一层）
        // ================================================================================
        internal static GameObject GuildHall(Transform parent, Vector3 pos, float yaw)
        {
            var root = Kit.Pivot(parent, "GuildHall", pos, yaw);
            var t = root.transform;
            var v = Piv(t, "Visual");
            float w = 18f, dir = 11f;
            float hw = w * 0.5f, hd = dir * 0.5f;
            float wt = 0.44f, plinth = 0.16f;
            float h1 = 3.9f, h2 = 3.1f, roofH = 3.5f;
            float wallTop = plinth + h1 + h2;
            float openW = 3.8f, openH = 3.05f;
            var stone = StoneM("stone_wall");
            var stoneLight = StoneM("stone_light");
            var stoneDark = StoneM("stone_dark");
            var plaster = WallM("plaster_cream");
            var timber = TimberM("timber_dark");
            var roof = RoofM("roof_slate");

            B(v, "Foundation", new Vector3(w + 0.5f, plinth, dir + 0.5f), new Vector3(0f, plinth * 0.5f, 0f), stoneDark);
            SL(v, "Floor", new Vector3(w - 0.1f, 0.04f, dir - 0.1f), new Vector3(0f, 0.06f, 0f), StoneM("stone_light"));
            // 一层石墙（正面留大拱门）
            float segW = hw - openW * 0.5f - 0.02f;
            B(v, "FrontL", new Vector3(segW, h1, wt), new Vector3(-(hw - segW * 0.5f), plinth + h1 * 0.5f, hd - wt * 0.5f), stone);
            B(v, "FrontR", new Vector3(segW, h1, wt), new Vector3(hw - segW * 0.5f, plinth + h1 * 0.5f, hd - wt * 0.5f), stone);
            B(v, "FrontTop", new Vector3(openW + 0.2f, h1 - openH, wt),
                new Vector3(0f, plinth + openH + (h1 - openH) * 0.5f, hd - wt * 0.5f), stone);
            B(v, "SideL", new Vector3(wt, h1, dir), new Vector3(-hw + wt * 0.5f, plinth + h1 * 0.5f, 0f), stone);
            B(v, "SideR", new Vector3(wt, h1, dir), new Vector3(hw - wt * 0.5f, plinth + h1 * 0.5f, 0f), stone);
            B(v, "Back", new Vector3(w, h1, wt), new Vector3(0f, plinth + h1 * 0.5f, -hd + wt * 0.5f), stone);
            // 一层横向石带 + 转角石
            B(v, "BandL", new Vector3(w + 0.2f, 0.24f, 0.2f), new Vector3(0f, plinth + 1.3f, hd + 0.02f), stoneLight);
            B(v, "BandR", new Vector3(w + 0.2f, 0.24f, 0.2f), new Vector3(0f, plinth + 2.6f, hd + 0.02f), stoneLight);
            for (int s = -1; s <= 1; s += 2)
                for (int lv = 0; lv < 4; lv++)
                    B(v, "Quoin", new Vector3(0.5f, 0.5f, 0.5f),
                        new Vector3(s * (hw - 0.18f), plinth + 0.3f + lv * 0.9f, hd - 0.1f), stoneLight);
            // 大拱门
            ArchFrame(Piv(v, "DoorFace", new Vector3(0f, 0f, hd - wt * 0.5f)), openW, openH, stoneLight, timber);
            // 双开木门（向内敞开）
            BR(v, "DoorLeafL", new Vector3(openW * 0.48f, openH * 0.94f, 0.12f),
                new Vector3(-openW * 0.44f, plinth + openH * 0.47f, hd - wt * 0.5f),
                Quaternion.Euler(0f, -68f, 0f), WoodM("wood_dark"));
            BR(v, "DoorLeafR", new Vector3(openW * 0.48f, openH * 0.94f, 0.12f),
                new Vector3(openW * 0.44f, plinth + openH * 0.47f, hd - wt * 0.5f),
                Quaternion.Euler(0f, 68f, 0f), WoodM("wood_dark"));
            // 两侧假拱窗
            for (int s = -1; s <= 1; s += 2)
            {
                var af = Piv(v, "ArchWin", new Vector3(s * 5.7f, 0f, hd + 0.02f));
                B(af, "Pane", new Vector3(1.5f, 2.0f, 0.08f), new Vector3(0f, plinth + 1.9f, 0f), WinLit());
                B(af, "FrameL", new Vector3(0.16f, 2.1f, 0.16f), new Vector3(-0.85f, plinth + 1.9f, 0.04f), timber);
                B(af, "FrameR", new Vector3(0.16f, 2.1f, 0.16f), new Vector3(0.85f, plinth + 1.9f, 0.04f), timber);
                BR(af, "ArchTop", new Vector3(1.9f, 0.18f, 0.16f), new Vector3(0f, plinth + 2.98f, 0.04f),
                    Quaternion.Euler(0f, 0f, 0f), stoneLight);
                B(af, "Sill", new Vector3(1.9f, 0.16f, 0.3f), new Vector3(0f, plinth + 0.82f, 0.08f), stoneLight);
            }
            // 二层木筋墙 + 阳台
            B(v, "Upper", new Vector3(w + 0.3f, h2, dir + 0.3f), new Vector3(0f, plinth + h1 + h2 * 0.5f, 0f), plaster);
            B(v, "BeltF", new Vector3(w + 0.7f, 0.26f, 0.2f), new Vector3(0f, plinth + h1, hd + 0.1f), timber);
            B(v, "BeltB", new Vector3(w + 0.7f, 0.26f, 0.2f), new Vector3(0f, plinth + h1, -hd - 0.1f), timber);
            for (int s = -1; s <= 1; s += 2)
            {
                B(v, "BeltS", new Vector3(0.2f, 0.26f, dir + 0.7f), new Vector3(s * (hw + 0.1f), plinth + h1, 0f), timber);
                B(v, "CornerPost", new Vector3(0.3f, h2, 0.3f), new Vector3(s * (hw + 0.1f), plinth + h1 + h2 * 0.5f, hd + 0.1f), timber);
                B(v, "CornerPostB", new Vector3(0.3f, h2, 0.3f), new Vector3(s * (hw + 0.1f), plinth + h1 + h2 * 0.5f, -hd - 0.1f), timber);
            }
            for (int i = 0; i < 6; i++)
                B(v, "Stud", new Vector3(0.14f, h2 - 0.2f, 0.12f),
                    new Vector3(-hw * 0.8f + i * hw * 0.32f, plinth + h1 + h2 * 0.5f, hd + 0.14f), timber);
            for (int s = -1; s <= 1; s += 2)
                for (int i = 0; i < 2; i++)
                    BR(v, "Brace", new Vector3(0.12f, 1.5f, 0.09f),
                        new Vector3(s * (hw * 0.55f + i * 2.4f), plinth + h1 + h2 * 0.5f, hd + 0.13f),
                        Quaternion.Euler(0f, 0f, s * (i == 0 ? 22f : -22f)), timber);
            // 二层窗（大拱窗 + 小窗）
            var faceFront = Piv(v, "FaceFront", new Vector3(0f, 0f, hd + 0.16f));
            for (int i = 0; i < 5; i++)
            {
                float x = -hw * 0.62f + i * hw * 0.31f;
                if (i == 2) continue;
                Win(faceFront, new Vector3(x, plinth + h1 + h2 * 0.54f, 0f), 1.0f, 1.35f, i % 2 == 0, true, false, timber);
            }
            // 中央阳台
            B(v, "Balcony", new Vector3(5.2f, 0.2f, 1.7f), new Vector3(0f, plinth + h1 + 0.1f, hd + 0.9f), stoneLight);
            for (int s = -1; s <= 1; s += 2)
            {
                B(v, "BalPost", new Vector3(0.16f, 1.1f, 0.16f), new Vector3(s * 2.4f, plinth + h1 + 0.65f, hd + 1.6f), timber);
                BR(v, "BalBracket", new Vector3(0.14f, 0.14f, 1.5f), new Vector3(s * 2.1f, plinth + h1 - 0.55f, hd + 0.5f),
                    Quaternion.Euler(44f, 0f, 0f), timber);
            }
            B(v, "BalRail", new Vector3(5.2f, 0.1f, 0.1f), new Vector3(0f, plinth + h1 + 1.18f, hd + 1.6f), timber);
            for (int i = 0; i < 8; i++)
                B(v, "Baluster", new Vector3(0.07f, 1.0f, 0.07f), new Vector3(-2.35f + i * 0.67f, plinth + h1 + 0.62f, hd + 1.6f), timber);
            // 阳台上的双旗与徽记
            WallBanner(Piv(v, "BannerL", new Vector3(-1.6f, 0f, hd + 1.62f)), new Vector3(0f, plinth + h1 + 1.55f, 0f), "cloth_red", 1.1f, 1.9f);
            WallBanner(Piv(v, "BannerR", new Vector3(1.6f, 0f, hd + 1.62f)), new Vector3(0f, plinth + h1 + 1.55f, 0f), "cloth_blue", 1.1f, 1.9f);
            // 正立面山墙屋顶（屋脊沿 Z，正面看到大三角）
            Kit.Mesh(v, "Roof", Kit.GableRoofMesh(dir + 0.3f, w + 0.3f, roofH, 0.7f, 0.2f),
                new Vector3(0f, wallTop, 0f), roof, false);
            var roofGo = v.Find("Roof");
            if (roofGo != null) roofGo.localRotation = Quaternion.Euler(0f, 90f, 0f);
            B(v, "RidgeCap", new Vector3(0.32f, 0.2f, dir + 0.3f + 1.6f), new Vector3(0f, wallTop + roofH + 0.04f, 0f), roof);
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.GableFace(v, "Gable", w + 0.3f, roofH, 0.32f, new Vector3(0f, wallTop, s * (hd + 0.15f)), plaster, s > 0 ? 0f : 180f);
                B(v, "Eave", new Vector3(w + 2.4f, 0.2f, 0.16f), new Vector3(0f, wallTop - 0.16f, s * (hd + 0.7f)), timber);
            }
            // 正山墙的圆窗 + 旗帜
            var gableFront = Piv(v, "GableFront", new Vector3(0f, wallTop, hd + 0.32f));
            CYR(gableFront, "GableWin", 0.62f, 0.1f, new Vector3(0f, roofH * 0.4f, 0f), Quaternion.Euler(90f, 0f, 0f), timber, 14);
            CYR(gableFront, "GableGlass", 0.48f, 0.07f, new Vector3(0f, roofH * 0.4f, 0.03f), Quaternion.Euler(90f, 0f, 0f), WinDay(), 14);
            B(gableFront, "KingPost", new Vector3(0.16f, roofH * 0.86f, 0.14f), new Vector3(0f, roofH * 0.43f, 0.05f), timber);
            // 屋顶小旗
            CY(v, "FlagPole", 0.05f, 1.4f, new Vector3(0f, wallTop + roofH + 0.7f, 0f), Mat("iron"), 6);
            B(v, "Flag", new Vector3(1.0f, 0.5f, 0.04f), new Vector3(0.55f, wallTop + roofH + 1.1f, 0f), ClothM("cloth_red"));
            B(v, "Chimney", new Vector3(0.7f, 2.2f, 0.7f), new Vector3(hw * 0.62f, wallTop + roofH * 0.5f, -hd * 0.4f), stoneDark);
            Kit.Smoke(v, new Vector3(hw * 0.62f, wallTop + roofH * 0.5f + 1.3f, -hd * 0.4f), new Color(0.94f, 0.93f, 0.92f), 4, 0.24f);

            // ---------- 大厅内部 ----------
            // 后墙大旗 + 交叉剑 + 盾
            B(v, "BackBanner", new Vector3(4.6f, 3.0f, 0.06f), new Vector3(0f, plinth + 2.2f, -hd + wt + 0.06f), ClothM("cloth_red"));
            B(v, "BackBannerTrim", new Vector3(4.8f, 0.18f, 0.1f), new Vector3(0f, plinth + 3.75f, -hd + wt + 0.1f), Mat("gold"));
            CYR(v, "BackEmblem", 0.7f, 0.08f, new Vector3(0f, plinth + 2.4f, -hd + wt + 0.16f), Quaternion.Euler(90f, 0f, 0f),
                MapMaterials.Emissive("roa_emblem_gold2", MapMaterials.GlowGold, 0.9f), 16);
            B(v, "Sword1", new Vector3(0.12f, 2.1f, 0.08f), new Vector3(0f, plinth + 2.3f, -hd + wt + 0.22f),
                Mat("steel"), 0f);
            B(v, "Sword2", new Vector3(2.1f, 0.12f, 0.08f), new Vector3(0f, plinth + 2.3f, -hd + wt + 0.22f),
                Mat("steel"), 0f);
            // 接待台
            B(v, "Counter", new Vector3(6.0f, 0.95f, 0.9f), new Vector3(0f, 0.48f, -hd + 2.2f), WoodM("wood_dark"));
            B(v, "CounterTop", new Vector3(6.3f, 0.1f, 1.15f), new Vector3(0f, 1.0f, -hd + 2.2f), WoodM("wood_plank"));
            for (int i = 0; i < 3; i++)
                B(v, "Paper", new Vector3(0.6f, 0.03f, 0.45f), new Vector3(-1.8f + i * 1.4f, 1.06f, -hd + 2.0f),
                    ClothM("cloth_cream"));
            // 两侧长桌与陈列
            var tableL = Piv(v, "TableL", new Vector3(-hw + 3.0f, 0f, 1.6f));
            B(tableL, "Top", new Vector3(2.4f, 0.1f, 1.3f), new Vector3(0f, 0.82f, 0f), WoodM("wood_plank"));
            for (int sx = -1; sx <= 1; sx += 2)
                for (int sz = -1; sz <= 1; sz += 2)
                    B(tableL, "Leg", new Vector3(0.12f, 0.82f, 0.12f), new Vector3(sx * 1.0f, 0.41f, sz * 0.5f), WoodM("wood_dark"));
            B(tableL, "Map", new Vector3(0.9f, 0.02f, 0.65f), new Vector3(0f, 0.88f, 0f), ClothM("cloth_cream"));
            // 地毯 + 吊灯
            B(v, "Carpet", new Vector3(3.4f, 0.03f, 8.5f), new Vector3(0f, 0.08f, 1.2f), ClothM("cloth_red"));
            CYR(v, "ChandelierRing", 0.9f, 0.1f, new Vector3(0f, plinth + h1 - 0.55f, 1.2f), Quaternion.Euler(90f, 0f, 0f),
                Mat("iron"), 12);
            for (int i = 0; i < 6; i++)
            {
                Vector3 candleDir = KitMath.OnCircle(0.8f, i * 60f);
                B(v, "Candle", new Vector3(0.09f, 0.28f, 0.09f), new Vector3(candleDir.x, plinth + h1 - 0.3f, 1.2f + candleDir.z), LampGlow());
            }
            B(v, "Chain", new Vector3(0.06f, 1.0f, 0.06f), new Vector3(0f, plinth + h1 - 0.2f, 1.2f), Mat("iron"));
            // 武器架 + 2 条长凳（用 KitProps.Bench，合并时一起批处理）
            KitProps.Bench(v, new Vector3(-hw + 2.6f, 0f, 3.6f), 90f, 2.0f);
            KitProps.Bench(v, new Vector3(hw - 2.6f, 0f, 3.6f), -90f, 2.0f);
            B(v, "WeaponRack", new Vector3(1.6f, 1.5f, 0.4f), new Vector3(hw - wt - 0.5f, 0.75f, 1.2f), TimberM("timber_mid"), 90f);
            for (int i = 0; i < 3; i++)
                B(v, "Spear", new Vector3(0.06f, 1.9f, 0.06f), new Vector3(hw - wt - 0.6f, 1.6f, 0.7f + i * 0.5f),
                    Mat("wood_light"), 0f);
            Kit.Optimize(root, false);
            // 后墙牌匾 + 正门招牌
            Kit.SignBoard(t, "冒险者协会", new Vector3(0f, plinth + h1 + 0.62f, hd + 0.24f), 0f, 4.6f, 0.8f,
                MapMaterials.ClothCream, Ink);
            Kit.SignBoard(t, "委托 · 情报 · 补给", new Vector3(0f, plinth + 2.95f, hd + 0.18f), 0f, 2.2f, 0.42f,
                MapMaterials.ClothCream, Ink);
            PorchLantern(Piv(t, "PorchFace", new Vector3(0f, 0f, hd - wt * 0.5f)), new Vector3(-2.6f, 2.75f, 0f), true);
            PorchLantern(Piv(t, "PorchFace2", new Vector3(0f, 0f, hd - wt * 0.5f)), new Vector3(2.6f, 2.75f, 0f), false);
            // 台阶
            B(t, "Step1", new Vector3(9.0f, 0.12f, 1.3f), new Vector3(0f, 0.06f, hd + 0.85f), stoneLight);
            B(t, "Step2", new Vector3(10.4f, 0.12f, 0.9f), new Vector3(0f, 0.0f, hd + 1.5f), stoneDark);
            B(t, "Step3", new Vector3(11.6f, 0.1f, 0.7f), new Vector3(0f, -0.05f, hd + 2.05f), stoneLight);
            Blocker(t, "BlockFrontL", new Vector3(segW, h1, 0.7f), new Vector3(-(hw - segW * 0.5f), plinth + h1 * 0.5f, hd - wt * 0.5f));
            Blocker(t, "BlockFrontR", new Vector3(segW, h1, 0.7f), new Vector3(hw - segW * 0.5f, plinth + h1 * 0.5f, hd - wt * 0.5f));
            Blocker(t, "BlockSideL", new Vector3(0.7f, h1, dir), new Vector3(-hw + 0.1f, plinth + h1 * 0.5f, 0f));
            Blocker(t, "BlockSideR", new Vector3(0.7f, h1, dir), new Vector3(hw - 0.1f, plinth + h1 * 0.5f, 0f));
            Blocker(t, "BlockBack", new Vector3(w, h1, 0.7f), new Vector3(0f, plinth + h1 * 0.5f, -hd + 0.1f));
            Blocker(t, "BlockCounter", new Vector3(6.0f, 1.1f, 1.0f), new Vector3(0f, 0.55f, -hd + 2.2f));
            Kit.MakeFadeable(root, 0.3f);
            return root;
        }

        // ================================================================================
        // 城门（城墙正中，带塔楼的两个垛口门楼）
        // ================================================================================
        internal static GameObject CastleGate(Transform parent, Vector3 pos, float yaw)
        {
            var root = Kit.Pivot(parent, "CastleGate", pos, yaw);
            var t = root.transform;
            var v = Piv(t, "Visual");
            float openW = 7.0f;
            float depth = 4.2f;
            float pierW = 1.9f;
            float bodyH = 7.6f;
            var stone = StoneM("stone_wall");
            var stoneDark = StoneM("stone_dark");
            var stoneLight = StoneM("stone_light");
            var roof = RoofM("roof_slate");
            // 两侧门墩
            for (int s = -1; s <= 1; s += 2)
            {
                float x = s * (openW * 0.5f + pierW * 0.5f);
                B(v, "Pier", new Vector3(pierW, bodyH, depth + 0.5f), new Vector3(x, bodyH * 0.5f, 0f), stone);
                B(v, "PierBase", new Vector3(pierW + 0.4f, 0.6f, depth + 0.9f), new Vector3(x, 0.3f, 0f), stoneDark);
                B(v, "PierCap", new Vector3(pierW + 0.5f, 0.22f, depth + 0.8f), new Vector3(x, bodyH - 0.2f, 0f), stoneLight);
                // 墩上的垛口
                for (int i = 0; i < 2; i++)
                    B(v, "Merlon", new Vector3(pierW * 0.7f, 0.9f, depth + 0.3f),
                        new Vector3(x + (i - 0.5f) * pierW * 0.5f, bodyH + 0.45f, depth * 0.5f - 0.2f), stone);
                // 火把
                B(v, "Torch", new Vector3(0.2f, 0.5f, 0.2f), new Vector3(x - s * (pierW * 0.5f + 0.12f), 3.4f, depth * 0.5f + 0.2f),
                    FireGlow());
                B(v, "TorchBracket", new Vector3(0.1f, 0.1f, 0.5f), new Vector3(x - s * (pierW * 0.5f + 0.1f), 3.1f, depth * 0.5f + 0.1f), Mat("iron"));
                // 挂旗
                WallBanner(Piv(v, "GateBanner", new Vector3(x, 0f, depth * 0.5f + 0.3f)), new Vector3(0f, 5.0f, 0f),
                    s < 0 ? "cloth_red" : "cloth_blue", 1.3f, 2.6f);
            }
            // 拱券 + 门楣墙
            int n = 11;
            float r = openW * 0.5f + 0.2f;
            for (int i = 0; i < n; i++)
            {
                float a = Mathf.PI * (i / (float)(n - 1));
                BR(v, "Voussoir", new Vector3(0.34f, 0.5f, depth + 0.9f),
                    new Vector3(Mathf.Cos(a) * r, 5.5f + Mathf.Sin(a) * r, 0f),
                    Quaternion.Euler(0f, 0f, a * Mathf.Rad2Deg), stoneLight);
            }
            B(v, "Lintel", new Vector3(openW + 2.0f, 0.5f, depth + 0.9f), new Vector3(0f, 6.3f, 0f), stoneLight);
            B(v, "UpperWall", new Vector3(openW + 2.0f, 2.1f, depth + 0.5f), new Vector3(0f, 7.55f, 0f), stone);
            B(v, "Walk", new Vector3(openW + 2.2f, 0.28f, depth + 0.8f), new Vector3(0f, 8.74f, 0f), stoneLight);
            // 走道北侧垛口
            for (int i = 0; i < 5; i++)
            {
                float x = -openW * 0.5f + 0.5f + i * (openW - 1.0f) / 4f;
                B(v, "WalkMerlon", new Vector3(0.8f, 0.85f, 0.5f), new Vector3(x, 9.3f, depth * 0.5f + 0.1f), stone);
            }
            // 升起一半的铁闸门（在世界里存在感强）
            for (int i = 0; i < 6; i++)
                B(v, "GateBar", new Vector3(0.13f, 2.6f, 0.13f),
                    new Vector3(-openW * 0.5f + 0.6f + i * (openW - 1.2f) / 5f, 5.9f, 0f), Mat("iron"));
            B(v, "GateBarH", new Vector3(openW - 0.4f, 0.14f, 0.14f), new Vector3(0f, 6.6f, 0f), Mat("iron"));
            B(v, "GateBarH2", new Vector3(openW - 0.4f, 0.14f, 0.14f), new Vector3(0f, 5.2f, 0f), Mat("iron"));
            // 门洞内的石板地
            SL(v, "Passage", new Vector3(openW + 0.4f, 0.06f, depth + 1.2f), new Vector3(0f, 0.03f, 0f), StoneM("cobble"));
            // 门楼两侧的城墙帽（把门楼与城墙段接起来）
            for (int s = -1; s <= 1; s += 2)
            {
                B(v, "Wing", new Vector3(2.4f, 5.4f, 1.4f), new Vector3(s * (openW * 0.5f + pierW + 1.0f), 2.7f, 0f), stone);
                B(v, "WingCap", new Vector3(2.6f, 0.2f, 1.6f), new Vector3(s * (openW * 0.5f + pierW + 1.0f), 5.35f, 0f), stoneLight);
            }
            // 城楼屋顶（两个小坡顶在塔楼位置）
            for (int s = -1; s <= 1; s += 2)
            {
                float x = s * (openW * 0.5f + pierW * 0.5f);
                var rg = Kit.Mesh(v, "TorchRoof", Kit.GableRoofMesh(depth + 1.2f, pierW + 1.0f, 1.4f, 0.3f, 0.14f),
                    new Vector3(x, bodyH + 0.8f, 0f), roof, false);
                if (rg != null) rg.transform.localRotation = Quaternion.Euler(0f, 90f, 0f);
            }
            Kit.Optimize(root, false);
            Kit.SignBoard(t, "罗亚市 · Roa Town", new Vector3(0f, 8.0f, depth * 0.5f + 0.35f), 0f, 4.8f, 0.75f,
                MapMaterials.ClothCream, Ink);
            Kit.PointLight(t, new Vector3(0f, 5.2f, depth * 0.5f + 0.6f), new Color(1f, 0.7f, 0.38f), 9f, 1.3f);
            Blocker(t, "BlockPierL", new Vector3(pierW + 0.4f, bodyH, depth + 0.7f),
                new Vector3(-(openW * 0.5f + pierW * 0.5f), bodyH * 0.5f, 0f));
            Blocker(t, "BlockPierR", new Vector3(pierW + 0.4f, bodyH, depth + 0.7f),
                new Vector3(openW * 0.5f + pierW * 0.5f, bodyH * 0.5f, 0f));
            Blocker(t, "BlockWingL", new Vector3(2.4f, 5.4f, 1.4f),
                new Vector3(-(openW * 0.5f + pierW + 1.0f), 2.7f, 0f));
            Blocker(t, "BlockWingR", new Vector3(2.4f, 5.4f, 1.4f),
                new Vector3(openW * 0.5f + pierW + 1.0f, 2.7f, 0f));
            Kit.MakeFadeable(root, 0.24f);
            return root;
        }

        // ================================================================================
        // KitProps 快捷包装（返回已合并道具，压 GameObject 数）
        // ================================================================================
        internal static GameObject Lamp(Transform parent, string name, Vector3 pos, float yaw, bool light)
        {
            var go = KitProps.Lamp(parent, pos, yaw, light);
            go.name = name;
            Kit.Optimize(go, false);
            return go;
        }

        internal static GameObject Barrel(Transform parent, Vector3 pos, float yaw = 0f, float scale = 1f)
        {
            var go = KitProps.Barrel(parent, pos, yaw, scale);
            Kit.Optimize(go, false);
            return go;
        }

        internal static GameObject Crate(Transform parent, Vector3 pos, float yaw = 0f, float scale = 1f)
        {
            var go = KitProps.Crate(parent, pos, yaw, scale);
            Kit.Optimize(go, false);
            return go;
        }

        internal static GameObject Pot(Transform parent, Vector3 pos, bool plant = false)
        {
            var go = KitProps.Pot(parent, pos, 0f, 1f, plant);
            Kit.Optimize(go, false);
            return go;
        }

        internal static GameObject Sack(Transform parent, Vector3 pos, float yaw = 0f)
        {
            var go = KitProps.Sack(parent, pos, yaw, 1f, true);
            Kit.Optimize(go, false);
            return go;
        }

        internal static GameObject Bench(Transform parent, Vector3 pos, float yaw = 0f, float length = 1.6f)
        {
            var go = KitProps.Bench(parent, pos, yaw, length);
            Kit.Optimize(go, false);
            return go;
        }

        internal static GameObject Tree(Transform parent, Vector3 pos, float scale = 1f, bool autumn = false)
        {
            var go = KitProps.Tree(parent, pos, scale, autumn);
            Kit.Optimize(go, true);
            return go;
        }

        internal static GameObject Pine(Transform parent, Vector3 pos, float scale = 1f)
        {
            var go = KitProps.Pine(parent, pos, scale);
            Kit.Optimize(go, true);
            return go;
        }

        internal static GameObject Bush(Transform parent, Vector3 pos, float scale = 1f)
        {
            var go = KitProps.Bush(parent, pos, scale);
            Kit.Optimize(go, false);
            return go;
        }

        internal static GameObject Rock(Transform parent, Vector3 pos, float scale = 1f)
        {
            var go = KitProps.Rock(parent, pos, scale);
            Kit.Optimize(go, false);
            return go;
        }

        internal static GameObject Flowers(Transform parent, Vector3 pos, Color c)
        {
            var go = KitProps.Flowers(parent, pos, c);
            Kit.Optimize(go, false);
            return go;
        }

        internal static GameObject Haystack(Transform parent, Vector3 pos, float scale = 1f)
        {
            var go = KitProps.Haystack(parent, pos, scale);
            Kit.Optimize(go, false);
            return go;
        }

        // ================================================================================
        // KitArchitecture 包装：民居 / 城墙段 / 塔楼（生成后合并，压 GameObject 数）
        // ================================================================================
        internal static GameObject House(Transform parent, HouseSpec spec, Vector3 pos, float yaw)
        {
            var root = KitArchitecture.House(parent, spec, pos, yaw);
            Kit.Optimize(root, true);
            return root;
        }

        internal static GameObject Tower(Transform parent, Vector3 pos, float yaw = 0f, bool wizard = false)
        {
            var root = KitArchitecture.Tower(parent, pos, yaw, wizard);
            Kit.Optimize(root, true);
            return root;
        }

        internal static GameObject Wall(Transform parent, Vector3 pos, float yaw, float length, float height)
        {
            var root = KitArchitecture.WallSegment(parent, pos, yaw, length, height);
            Kit.Optimize(root, false);
            var bc = root.GetComponent<BoxCollider>();
            if (bc == null) bc = root.AddComponent<BoxCollider>();
            // 合并后的包围盒是按世界轴取的，转了 90° 的墙段会横竖颠倒，这里用已知尺寸重设。
            bc.center = new Vector3(0f, (height + 1.25f) * 0.5f, 0f);
            bc.size = new Vector3(length, height + 1.25f, 1.95f);
            return root;
        }
    }
}
