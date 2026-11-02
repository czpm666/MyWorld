using UnityEngine;

namespace MyWorld
{
    // ============================================================================================
    // 街道小道具（第一批）。全部纯运行期生成、返回 GameObject 根节点，pos/yaw 是父节点局部空间。
    // 尺度参照：角色高 1.5m、木桶高约 1.1m、长凳坐高 0.45m。
    // 每个道具 3~15 个 primitive，只给"该挡人的东西"留一个碰撞体。
    // （第二批：Cart / Statue / RuneCircle / CrystalCluster / WeaponRack / CropRow 在 KitProps2.cs）
    // ============================================================================================
    public static partial class KitProps
    {
        static Material M(string key)
        {
            return MapMaterials.Get(key);
        }

        /// <summary>布类材质（带织纹），key 形如 cloth_red；空/非法就回退红布。</summary>
        static Material ClothMat(string key)
        {
            if (string.IsNullOrEmpty(key)) key = "cloth_red";
            return KitMat.Cloth(key);
        }

        /// <summary>徽记/金属小件的材质，key 走 KitPalette 的色板（gold/bronze/cloth_*）。</summary>
        static Material EmblemMat(string key)
        {
            if (string.IsNullOrEmpty(key)) key = "gold";
            return MapMaterials.Solid("kit_emblem_" + key, KitPalette.Of(key), 0.4f, 0.35f);
        }

        // ============================================================================================
        // 木桶
        // ============================================================================================
        /// <summary>三节圆柱拼出鼓腹木桶 + 两道铁箍 + 桶盖。直径约 0.86m、高 1.1m。</summary>
        public static GameObject Barrel(Transform parent, Vector3 pos, float yaw = 0f, float scale = 1f)
        {
            scale = Mathf.Max(0.2f, scale);
            var root = Kit.Pivot(parent, "Barrel", pos, yaw);
            var t = root.transform;
            var wood = KitMat.WoodTinted("wood_barrel");
            var iron = M("iron");
            Kit.Cyl(t, "Lower", 0.36f * scale, 0.28f * scale, new Vector3(0f, 0.14f * scale, 0f), wood, 12, false);
            Kit.Cyl(t, "Belly", 0.44f * scale, 0.5f * scale, new Vector3(0f, 0.53f * scale, 0f), wood, 12, true);
            Kit.Cyl(t, "Upper", 0.36f * scale, 0.28f * scale, new Vector3(0f, 0.92f * scale, 0f), wood, 12, false);
            Kit.Cyl(t, "HoopLow", 0.45f * scale, 0.07f * scale, new Vector3(0f, 0.22f * scale, 0f), iron, 12, false);
            Kit.Cyl(t, "HoopHigh", 0.45f * scale, 0.07f * scale, new Vector3(0f, 0.84f * scale, 0f), iron, 12, false);
            Kit.Cyl(t, "Lid", 0.35f * scale, 0.05f * scale, new Vector3(0f, 1.08f * scale, 0f),
                KitMat.WoodTinted("wood_dark"), 12, false);
            return root;
        }

        // ============================================================================================
        // 木箱
        // ============================================================================================
        /// <summary>木箱：箱体（米制 UV 木纹）+ 四角边条 + 正面斜撑。边长 0.72m。</summary>
        public static GameObject Crate(Transform parent, Vector3 pos, float yaw = 0f, float scale = 1f)
        {
            float s = Mathf.Max(0.2f, 0.72f * scale);
            var root = Kit.Pivot(parent, "Crate", pos, yaw);
            var t = root.transform;
            var plank = KitMat.WoodTinted("wood_plank");
            var edge = KitMat.Timber("timber_mid");
            Kit.Slab(t, "Body", new Vector3(s, s, s), new Vector3(0f, s * 0.5f, 0f), plank, 0f, true);
            for (int sx = -1; sx <= 1; sx += 2)
                for (int sz = -1; sz <= 1; sz += 2)
                    Kit.Box(t, "Edge", new Vector3(0.06f, s, 0.06f),
                        new Vector3(sx * (s * 0.5f - 0.015f), s * 0.5f, sz * (s * 0.5f - 0.015f)), edge, 0f, false);
            Kit.Box(t, "TopX1", new Vector3(s + 0.02f, 0.055f, 0.055f), new Vector3(0f, s - 0.03f, s * 0.5f), edge, 0f, false);
            Kit.Box(t, "TopX2", new Vector3(s + 0.02f, 0.055f, 0.055f), new Vector3(0f, s - 0.03f, -s * 0.5f), edge, 0f, false);
            Kit.BoxRot(t, "Brace", new Vector3(s * 0.86f, 0.05f, 0.04f), new Vector3(0f, s * 0.5f, s * 0.5f + 0.012f),
                Quaternion.Euler(0f, 0f, 40f), edge, false);
            return root;
        }

        // ============================================================================================
        // 麻袋
        // ============================================================================================
        /// <summary>鼓鼓的麻袋：扁椭球袋身 + 束口 + 袋口翻边。</summary>
        public static GameObject Sack(Transform parent, Vector3 pos, float yaw = 0f, float scale = 1f, bool standing = true)
        {
            scale = Mathf.Max(0.2f, scale);
            var root = Kit.Pivot(parent, "Sack", pos, yaw);
            var t = root.transform;
            var cloth = KitMat.Cloth("cloth_cream");
            float h = standing ? 0.95f : 0.55f;
            Kit.Sphere(t, "Body", new Vector3(0.86f, h, 0.66f) * scale, new Vector3(0f, h * 0.5f * scale, 0f), cloth, true, 9);
            Kit.Cyl(t, "Neck", 0.17f * scale, 0.14f * scale, new Vector3(0f, h * 0.94f * scale, 0f),
                KitMat.Cloth("cloth_cream"), 8, false);
            Kit.Sphere(t, "Top", new Vector3(0.3f, 0.16f, 0.24f) * scale, new Vector3(0.03f, h * 1.02f * scale, 0f),
                KitMat.Cloth("cloth_cream"), false, 8);
            return root;
        }

        // ============================================================================================
        // 陶罐
        // ============================================================================================
        /// <summary>赤陶罐：鼓腹 + 收口 + 罐沿，可插一小束草。</summary>
        public static GameObject Pot(Transform parent, Vector3 pos, float yaw = 0f, float scale = 1f, bool withPlant = false)
        {
            scale = Mathf.Max(0.2f, scale);
            var root = Kit.Pivot(parent, "Pot", pos, yaw);
            var t = root.transform;
            var clay = MapMaterials.Solid("kit_clay", MapMaterials.RoofTerracotta * 0.92f, 0.25f);
            Kit.Cyl(t, "Belly", 0.28f * scale, 0.42f * scale, new Vector3(0f, 0.24f * scale, 0f), clay, 12, false);
            Kit.Cyl(t, "Neck", 0.19f * scale, 0.16f * scale, new Vector3(0f, 0.52f * scale, 0f), clay, 12, false);
            Kit.Cyl(t, "Lip", 0.24f * scale, 0.07f * scale, new Vector3(0f, 0.6f * scale, 0f),
                MapMaterials.Solid("kit_clay_dark", MapMaterials.RoofTerracotta * 0.72f, 0.25f), 12, false);
            Kit.Sphere(t, "Base", new Vector3(0.5f, 0.1f, 0.5f) * scale, new Vector3(0f, 0.02f * scale, 0f),
                MapMaterials.Solid("kit_clay_dark", MapMaterials.RoofTerracotta * 0.72f, 0.25f), false, 10);
            if (withPlant)
            {
                for (int i = 0; i < 3; i++)
                {
                    float ang = i * 120f;
                    Vector3 d = KitMath.OnCircle(0.1f * scale, ang);
                    Kit.BoxRot(t, "Sprig", new Vector3(0.05f, 0.4f, 0.05f),
                        new Vector3(d.x, 0.82f * scale, d.z), Quaternion.Euler(0f, ang, 14f),
                        M("foliage_dark"), false);
                }
            }
            return root;
        }

        // ============================================================================================
        // 长凳
        // ============================================================================================
        /// <summary>木长凳：坐面 + 四条腿 + 靠背 + 扶手柱。坐高 0.45m。</summary>
        public static GameObject Bench(Transform parent, Vector3 pos, float yaw = 0f, float length = 1.5f)
        {
            length = Mathf.Max(0.6f, length);
            var root = Kit.Pivot(parent, "Bench", pos, yaw);
            var t = root.transform;
            var wood = KitMat.WoodTinted("wood_plank");
            var leg = KitMat.WoodTinted("wood_dark");
            const float seatH = 0.45f;
            Kit.Box(t, "Seat", new Vector3(length, 0.09f, 0.44f), new Vector3(0f, seatH, 0f), wood, 0f, true);
            for (int sx = -1; sx <= 1; sx += 2)
            {
                Kit.Box(t, "LegF", new Vector3(0.09f, seatH, 0.09f), new Vector3(sx * length * 0.42f, seatH * 0.5f, 0.15f), leg, 0f, false);
                Kit.Box(t, "LegB", new Vector3(0.09f, seatH, 0.09f), new Vector3(sx * length * 0.42f, seatH * 0.5f, -0.15f), leg, 0f, false);
                Kit.Box(t, "BackPost", new Vector3(0.08f, 0.72f, 0.08f), new Vector3(sx * length * 0.42f, seatH + 0.3f, -0.2f), leg, 0f, false);
            }
            Kit.Box(t, "Back", new Vector3(length, 0.42f, 0.07f), new Vector3(0f, seatH + 0.32f, -0.2f), wood, 0f, false);
            Kit.Box(t, "BackRail", new Vector3(length + 0.05f, 0.08f, 0.11f), new Vector3(0f, seatH + 0.55f, -0.2f), leg, 0f, false);
            return root;
        }

        // ============================================================================================
        // 路灯 / 庭院灯
        // ============================================================================================
        /// <summary>
        /// 铁艺路灯：石基座 + 铁杆 + 灯笼头。默认只自发光（不给点光，每图点光 ≤8 由地图控制）；
        /// light:true 才建一个真实点光源。
        /// </summary>
        public static GameObject Lamp(Transform parent, Vector3 pos, float yaw = 0f, bool light = false, float height = 2.9f)
        {
            height = Mathf.Max(1.6f, height);
            var root = Kit.Pivot(parent, "Lamp", pos, yaw);
            var t = root.transform;
            var iron = M("iron");
            Kit.Cyl(t, "Base", 0.26f, 0.2f, new Vector3(0f, 0.1f, 0f), KitMat.Stone("stone_dark"), 10, false);
            Kit.Cyl(t, "Post", 0.075f, height - 0.45f, new Vector3(0f, 0.2f + (height - 0.45f) * 0.5f, 0f), iron, 8, true);
            Kit.Cyl(t, "Collar", 0.12f, 0.09f, new Vector3(0f, 0.46f, 0f), iron, 8, false);
            float topY = height - 0.2f;
            Kit.Box(t, "LampBase", new Vector3(0.34f, 0.06f, 0.34f), new Vector3(0f, topY, 0f), iron, 0f, false);
            Kit.Box(t, "Glow", new Vector3(0.26f, 0.42f, 0.26f), new Vector3(0f, topY + 0.24f, 0f),
                KitMat.Emi("kit_lamp_glow", MapMaterials.GlowWarm, 2.6f), 0f, false);
            for (int sx = -1; sx <= 1; sx += 2)
                for (int sz = -1; sz <= 1; sz += 2)
                    Kit.Box(t, "Bar", new Vector3(0.045f, 0.46f, 0.045f),
                        new Vector3(sx * 0.145f, topY + 0.24f, sz * 0.145f), iron, 0f, false);
            Kit.Box(t, "LampTop", new Vector3(0.44f, 0.07f, 0.44f), new Vector3(0f, topY + 0.5f, 0f), iron, 0f, false);
            Kit.Cone(t, "LampRoof", 0.32f, 0.24f, new Vector3(0f, topY + 0.53f, 0f), iron, 8, false);
            Kit.Sphere(t, "Finial", 0.07f, new Vector3(0f, topY + 0.8f, 0f), M("gold"), false, 8);
            if (light) Kit.PointLight(t, new Vector3(0f, topY + 0.2f, 0f), MapMaterials.GlowWarm, 4.6f, 1.15f);
            return root;
        }

        // ============================================================================================
        // 路牌
        // ============================================================================================
        /// <summary>
        /// 木路牌：主柱 + 两块指向不同的箭头板（text 用 "|" 分两块，例如 "罗亚市|布耶纳村"）。
        /// 箭头板文字走 SignText（自动缩放到牌面内）。
        /// </summary>
        public static GameObject Signpost(Transform parent, Vector3 pos, float yaw = 0f, string text = "", float boardYaw = 0f)
        {
            var root = Kit.Pivot(parent, "Signpost", pos, yaw);
            var t = root.transform;
            var wood = KitMat.WoodTinted("wood_dark");
            Kit.Cyl(t, "Post", 0.1f, 2.6f, new Vector3(0f, 1.3f, 0f), wood, 8, true);
            Kit.Sphere(t, "Finial", 0.14f, new Vector3(0f, 2.66f, 0f), KitMat.WoodTinted("wood_plank"), false, 8);
            string[] labels = string.IsNullOrEmpty(text) ? new[] { "", "" } : text.Split('|');
            for (int i = 0; i < labels.Length && i < 2; i++)
            {
                float by = 2.2f - i * 0.62f;
                var piv = Kit.Pivot(t, "Arrow" + i, new Vector3(0f, by, 0f), boardYaw + (i == 0 ? 0f : 148f));
                var pt = piv.transform;
                Kit.Box(pt, "Board", new Vector3(0.95f, 0.28f, 0.07f), new Vector3(0.48f, 0f, 0f), KitMat.WoodTinted("wood_plank"), 0f, false);
                // 箭头尖（三角柱，绕 Z 转 -90 让尖朝 +X）
                var tipMesh = KitGeo.GablePrismMesh(0.4f, 0.28f, 0.07f);
                Kit.MeshRot(pt, "Tip", tipMesh, new Vector3(0.95f, 0f, 0f), Quaternion.Euler(0f, 0f, -90f),
                    KitMat.WoodTinted("wood_plank"), false);
                if (!string.IsNullOrEmpty(labels[i]))
                    Kit.SignText(pt, labels[i], new Vector3(0.45f, 0f, 0.045f), 0f, KitPalette.Ink, 0.78f, 0.16f);
            }
            return root;
        }

        // ============================================================================================
        // 旗帜
        // ============================================================================================
        /// <summary>立旗：铁旗杆 + 金顶 + 横杆 + 布面（带织纹）+ 燕尾 + 徽记圆章。cloth/emblemColor 都走 MapMaterials 色板 key。</summary>
        public static GameObject Banner(Transform parent, Vector3 pos, float yaw, string cloth, string emblemColor)
        {
            var root = Kit.Pivot(parent, "Banner", pos, yaw);
            var t = root.transform;
            var iron = M("iron");
            Kit.Cyl(t, "Pole", 0.065f, 4.4f, new Vector3(0f, 2.2f, 0f), iron, 8, true);
            Kit.Sphere(t, "Finial", 0.13f, new Vector3(0f, 4.46f, 0f), M("gold"), false, 10);
            Kit.Box(t, "Arm", new Vector3(1.35f, 0.07f, 0.07f), new Vector3(0.62f, 4.1f, 0f), iron, 0f, false);
            var cm = ClothMat(cloth);
            float clothW = 1.1f, clothH = 1.9f;
            Kit.Box(t, "Cloth", new Vector3(clothW, clothH, 0.05f), new Vector3(0.62f, 4.1f - 0.04f - clothH * 0.5f, 0.005f), cm, 0f, false);
            // 燕尾（倒三角）
            var tail = KitGeo.GablePrismMesh(clothW, 0.42f, 0.05f);
            Kit.MeshRot(t, "Tail", tail, new Vector3(0.62f, 4.1f - 0.04f - clothH - 0.2f, 0.005f),
                Quaternion.Euler(0f, 0f, 180f), cm, false);
            // 徽记
            var em = EmblemMat(emblemColor);
            Kit.CylRot(t, "Emblem", 0.26f, 0.05f, new Vector3(0.62f, 4.1f - 0.04f - clothH * 0.45f, 0.045f),
                Quaternion.Euler(90f, 0f, 0f), em, 12, false);
            Kit.Box(t, "EmblemBar", new Vector3(0.3f, 0.06f, 0.03f), new Vector3(0.62f, 4.1f - 0.04f - clothH * 0.45f, 0.05f), em, 0f, false);
            return root;
        }

        // ============================================================================================
        // 栅栏
        // ============================================================================================
        /// <summary>木栅栏（沿本地 X 方向）：立柱 + 两道横杆，整段只有 1 个碰撞盒。</summary>
        public static GameObject Fence(Transform parent, Vector3 pos, float yaw = 0f, float length = 4f)
        {
            length = Mathf.Max(1f, length);
            var root = Kit.Pivot(parent, "Fence", pos, yaw);
            var t = root.transform;
            var wood = KitMat.Timber("timber_mid");
            var dark = KitMat.WoodTinted("wood_dark");
            int posts = Mathf.Max(2, Mathf.RoundToInt(length / 1.4f) + 1);
            float step = length / (posts - 1);
            for (int i = 0; i < posts; i++)
            {
                float x = -length * 0.5f + step * i;
                Kit.Box(t, "Post", new Vector3(0.12f, 1.1f, 0.12f), new Vector3(x, 0.55f, 0f), wood, 0f, false);
                Kit.Box(t, "PostCap", new Vector3(0.17f, 0.06f, 0.17f), new Vector3(x, 1.12f, 0f), dark, 0f, false);
            }
            for (int r = 0; r < 2; r++)
                Kit.Box(t, "Rail", new Vector3(length, 0.1f, 0.07f), new Vector3(0f, 0.42f + r * 0.44f, 0.02f), wood, 0f, false);
            Kit.Blocker(t, "Collider", new Vector3(length, 1.1f, 0.24f), new Vector3(0f, 0.55f, 0f));
            return root;
        }

        // ============================================================================================
        // 树 / 松树 / 灌木 / 石头 / 花丛 / 草垛
        // ============================================================================================
        /// <summary>阔叶树：树干 + 3~4 团低多边形树冠（两种绿色叠出体积感）。autumn 换秋色。</summary>
        public static GameObject Tree(Transform parent, Vector3 pos, float scale = 1f, bool autumn = false)
        {
            scale = Mathf.Max(0.25f, scale);
            var root = Kit.Pivot(parent, autumn ? "TreeAutumn" : "Tree", pos, 0f);
            var t = root.transform;
            var bark = KitMat.WoodTinted("wood_dark");
            Kit.Cyl(t, "Trunk", 0.17f * scale, 1.6f * scale, new Vector3(0f, 0.8f * scale, 0f), bark, 8, true);
            Kit.Cyl(t, "TrunkUpper", 0.1f * scale, 0.8f * scale, new Vector3(0f, 1.85f * scale, 0f), bark, 8, false);
            var f1 = M(autumn ? "foliage_autumn" : "foliage");
            var f2 = M(autumn ? "grass_dry" : "foliage_dark");
            Kit.Sphere(t, "Canopy1", 0.98f * scale, new Vector3(0f, 2.55f * scale, 0f), f1, false, 9);
            Kit.Sphere(t, "Canopy2", 0.72f * scale, new Vector3(0.58f * scale, 2.15f * scale, 0.28f * scale), f2, false, 8);
            Kit.Sphere(t, "Canopy3", 0.64f * scale, new Vector3(-0.54f * scale, 2.32f * scale, -0.22f * scale), f1, false, 8);
            Kit.Sphere(t, "Canopy4", 0.52f * scale, new Vector3(0.06f * scale, 3.14f * scale, 0.04f * scale), f2, false, 8);
            return root;
        }

        /// <summary>松树：树干 + 三层锥形树冠（越往上越小）。</summary>
        public static GameObject Pine(Transform parent, Vector3 pos, float scale = 1f)
        {
            scale = Mathf.Max(0.25f, scale);
            var root = Kit.Pivot(parent, "Pine", pos, 0f);
            var t = root.transform;
            var bark = KitMat.WoodTinted("wood_dark");
            var needle = M("foliage_dark");
            var needle2 = M("foliage");
            Kit.Cyl(t, "Trunk", 0.13f * scale, 1.1f * scale, new Vector3(0f, 0.55f * scale, 0f), bark, 8, true);
            Kit.Cone(t, "Cone1", 0.92f * scale, 1.5f * scale, new Vector3(0f, 0.7f * scale, 0f), needle2, 9, false);
            Kit.Cone(t, "Cone2", 0.72f * scale, 1.35f * scale, new Vector3(0f, 1.65f * scale, 0f), needle, 9, false);
            Kit.Cone(t, "Cone3", 0.5f * scale, 1.15f * scale, new Vector3(0f, 2.55f * scale, 0f), needle2, 9, false);
            return root;
        }

        /// <summary>灌木：三团叶子挤在一起，中间塞一点深色增加层次。</summary>
        public static GameObject Bush(Transform parent, Vector3 pos, float scale = 1f)
        {
            scale = Mathf.Max(0.2f, scale);
            var root = Kit.Pivot(parent, "Bush", pos, 0f);
            var t = root.transform;
            var g1 = M("foliage");
            var g2 = M("foliage_dark");
            Kit.Sphere(t, "B1", new Vector3(1.1f, 0.8f, 0.95f) * scale, new Vector3(-0.16f, 0.4f, 0f) * scale, g1, false, 8);
            Kit.Sphere(t, "B2", new Vector3(0.9f, 0.68f, 0.85f) * scale, new Vector3(0.36f, 0.34f, 0.14f) * scale, g2, false, 8);
            Kit.Sphere(t, "B3", new Vector3(0.75f, 0.58f, 0.72f) * scale, new Vector3(0.02f, 0.3f, 0.34f) * scale, g1, false, 8);
            return root;
        }

        /// <summary>石头：2~3 块压扁的低多边形岩石 + 一块深色底座。位置决定形状（确定性随机）。</summary>
        public static GameObject Rock(Transform parent, Vector3 pos, float scale = 1f)
        {
            scale = Mathf.Max(0.2f, scale);
            var root = Kit.Pivot(parent, "Rock", pos, 0f);
            var t = root.transform;
            var rnd = new KitRand(KitRand.SeedFrom(pos, 771));
            var light = KitMat.Stone("stone_light");
            var mid = KitMat.Stone("stone_wall");
            var dark = KitMat.Stone("stone_dark");
            Kit.Sphere(t, "R1", new Vector3(1.0f, 0.66f, 0.9f) * scale, new Vector3(0f, 0.3f, 0f) * scale,
                mid, true, 8);
            Kit.Sphere(t, "R2", new Vector3(0.62f, 0.5f, 0.58f) * scale,
                new Vector3(rnd.Range(0.3f, 0.6f), 0.2f, rnd.Range(-0.2f, 0.2f)) * scale, light, false, 7);
            Kit.Sphere(t, "R3", new Vector3(0.5f, 0.32f, 0.46f) * scale,
                new Vector3(rnd.Range(-0.6f, -0.3f), 0.14f, rnd.Range(0.2f, 0.4f)) * scale, dark, false, 7);
            return root;
        }

        /// <summary>花丛：绿色垫底 + 一圈彩色小花球。pos 是地面点。</summary>
        public static GameObject Flowers(Transform parent, Vector3 pos, Color c)
        {
            var root = Kit.Pivot(parent, "Flowers", pos, 0f);
            var t = root.transform;
            var green = M("foliage_dark");
            var flowerMat = MapMaterials.Solid("kit_prop_flower_" + ColorUtility.ToHtmlStringRGB(c), c, 0.25f);
            Kit.Cyl(t, "Patch", 0.52f, 0.12f, new Vector3(0f, 0.06f, 0f), green, 10, false);
            var rnd = new KitRand(KitRand.SeedFrom(pos, 913));
            for (int i = 0; i < 6; i++)
            {
                float ang = i * 60f + rnd.Range(-12f, 12f);
                Vector3 p = KitMath.OnCircle(rnd.Range(0.12f, 0.42f), ang);
                Kit.Sphere(t, "Bloom", 0.085f, new Vector3(p.x, 0.18f + rnd.Range(0f, 0.1f), p.z), flowerMat, false, 7);
            }
            return root;
        }

        /// <summary>草垛：压扁的圆形草堆 + 顶部小尖 + 捆绳。路上拉货的村子场景很好用。</summary>
        public static GameObject Haystack(Transform parent, Vector3 pos, float scale = 1f)
        {
            scale = Mathf.Max(0.2f, scale);
            var root = Kit.Pivot(parent, "Haystack", pos, 0f);
            var t = root.transform;
            var hay = M("grass_dry");
            var hayDark = M("dirt");
            Kit.Cyl(t, "Base", 0.9f * scale, 0.3f * scale, new Vector3(0f, 0.15f * scale, 0f), hayDark, 12, false);
            Kit.Sphere(t, "Dome", new Vector3(1.75f, 1.15f, 1.75f) * scale, new Vector3(0f, 0.62f * scale, 0f), hay, true, 9);
            Kit.Cone(t, "Peak", 0.42f * scale, 0.55f * scale, new Vector3(0f, 1.12f * scale, 0f), hay, 8, false);
            Kit.Cyl(t, "Rope", 0.88f * scale, 0.05f * scale, new Vector3(0f, 0.55f * scale, 0f),
                MapMaterials.Get("wood_dark"), 12, false);
            Kit.Cyl(t, "Pole", 0.05f * scale, 1.5f * scale, new Vector3(0f, 1.2f * scale, 0f),
                MapMaterials.Get("wood_dark"), 6, false);
            return root;
        }
    }
}
