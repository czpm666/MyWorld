using UnityEngine;

namespace MyWorld
{
    // ============================================================================================
    // 街道/场景小道具（第二批）：板车 / 雕像 / 魔法阵 / 水晶簇 / 武器架 / 庄稼地。
    // 与 KitProps.cs 是同一个 partial 类，共用 M/ClothMat/EmblemMat 辅助。
    // ============================================================================================
    public static partial class KitProps
    {
        // ============================================================================================
        // 板车
        // ============================================================================================
        /// <summary>两轮木板车：车厢板 + 侧板 + 辐条车轮 + 车辕 + 干草/麻袋货。车头朝本地 +Z。</summary>
        public static GameObject Cart(Transform parent, Vector3 pos, float yaw = 0f, float scale = 1f)
        {
            scale = Mathf.Max(0.3f, scale);
            var root = Kit.Pivot(parent, "Cart", pos, yaw);
            var t = root.transform;
            var plank = KitMat.WoodTinted("wood_plank");
            var dark = KitMat.WoodTinted("wood_dark");
            var iron = M("iron");

            // 车轮（轴沿 X，轮面在 YZ 平面）
            for (int s = -1; s <= 1; s += 2)
            {
                float wx = s * 0.68f * scale;
                Kit.CylRot(t, "Wheel", 0.42f * scale, 0.12f * scale, new Vector3(wx, 0.45f * scale, 0f),
                    Quaternion.Euler(0f, 0f, 90f), plank, 14);
                Kit.CylRot(t, "WheelHub", 0.13f * scale, 0.17f * scale, new Vector3(wx, 0.45f * scale, 0f),
                    Quaternion.Euler(0f, 0f, 90f), iron, 8);
                for (int i = 0; i < 6; i++)
                    Kit.BoxRot(t, "Spoke", new Vector3(0.06f * scale, 0.78f * scale, 0.05f * scale),
                        new Vector3(wx, 0.45f * scale, 0f),
                        Quaternion.Euler(i * 30f, 0f, 90f), dark, false);
            }
            // 车轴
            Kit.CylRot(t, "Axle", 0.07f * scale, 1.5f * scale, new Vector3(0f, 0.45f * scale, 0f),
                Quaternion.Euler(0f, 0f, 90f), dark, 8);
            // 车厢板 + 侧板 + 前后挡板
            Kit.Slab(t, "Bed", new Vector3(1.3f * scale, 0.12f * scale, 2.2f * scale),
                new Vector3(0f, 0.75f * scale, 0f), plank);
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Box(t, "SideRail", new Vector3(0.08f * scale, 0.32f * scale, 2.2f * scale),
                    new Vector3(s * 0.66f * scale, 0.95f * scale, 0f), dark, 0f, false);
                for (int i = 0; i < 4; i++)
                    Kit.Box(t, "Stake", new Vector3(0.09f * scale, 0.42f * scale, 0.09f * scale),
                        new Vector3(s * 0.66f * scale, 1.0f * scale, -0.9f * scale + i * 0.6f * scale), dark, 0f, false);
            }
            Kit.Box(t, "FrontBoard", new Vector3(1.3f * scale, 0.4f * scale, 0.08f * scale),
                new Vector3(0f, 0.98f * scale, 1.1f * scale), dark, 0f, false);
            Kit.Box(t, "BackBoard", new Vector3(1.3f * scale, 0.4f * scale, 0.08f * scale),
                new Vector3(0f, 0.98f * scale, -1.1f * scale), dark, 0f, false);
            // 车辕
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Box(t, "Shaft", new Vector3(0.09f * scale, 0.09f * scale, 1.7f * scale),
                    new Vector3(s * 0.36f * scale, 0.62f * scale, 1.85f * scale), dark, 0f, false);
                Kit.Box(t, "ShaftTip", new Vector3(0.12f * scale, 0.14f * scale, 0.12f * scale),
                    new Vector3(s * 0.36f * scale, 0.62f * scale, 2.7f * scale), iron, 0f, false);
            }
            // 货
            Kit.Sphere(t, "HayLoad", new Vector3(1.15f, 0.7f, 1.9f) * scale, new Vector3(0f, 1.05f * scale, 0f),
                M("grass_dry"), false, 9);
            KitProps.Sack(t, new Vector3(-0.32f * scale, 0.82f * scale, 0.55f * scale), 22f, 0.6f, false);
            KitProps.Sack(t, new Vector3(0.34f * scale, 0.82f * scale, -0.35f * scale), -35f, 0.55f, false);
            Kit.Blocker(t, "Blocker", new Vector3(1.5f * scale, 1.4f * scale, 2.6f * scale), new Vector3(0f, 0.7f * scale, 0f));
            return root;
        }

        // ============================================================================================
        // 雕像
        // ============================================================================================
        /// <summary>
        /// 广场雕像：双层石基座 + 抽象骑士（腿/甲裙/胸甲/披风/头盔/盾/剑）。bronze=true 用青铜；
        /// false 用石材（配合 stone 参数选择石材 key）。
        /// </summary>
        public static GameObject Statue(Transform parent, Vector3 pos, float yaw = 0f, bool bronze = true, string stone = "stone_light")
        {
            var root = Kit.Pivot(parent, "Statue", pos, yaw);
            var t = root.transform;
            var stoneD = KitMat.Stone("stone_dark");
            var stoneL = KitMat.Stone(stone);
            var mat = bronze ? M("bronze") : stoneL;
            var matDark = bronze ? M("copper") : stoneD;
            var gold = M("gold");

            // 基座
            Kit.Box(t, "Base1", new Vector3(2.0f, 0.3f, 2.0f), new Vector3(0f, 0.15f, 0f), stoneD, 0f, false);
            Kit.Box(t, "Base2", new Vector3(1.6f, 0.5f, 1.6f), new Vector3(0f, 0.55f, 0f), stoneL, 0f, false);
            Kit.Box(t, "Plinth", new Vector3(1.25f, 0.35f, 1.25f), new Vector3(0f, 0.97f, 0f), stoneD, 0f, false);
            Kit.Box(t, "PlinthCap", new Vector3(1.45f, 0.12f, 1.45f), new Vector3(0f, 1.2f, 0f), stoneL, 0f, false);
            // 铭牌
            Kit.Box(t, "Plaque", new Vector3(0.72f, 0.28f, 0.06f), new Vector3(0f, 0.62f, 0.81f), gold, 0f, false);

            float y0 = 1.26f;
            // 腿 / 甲裙 / 胸甲 / 肩甲
            for (int s = -1; s <= 1; s += 2)
                Kit.Box(t, "Leg", new Vector3(0.2f, 0.62f, 0.24f), new Vector3(s * 0.17f, y0 + 0.31f, 0f), matDark, 0f, false);
            Kit.Box(t, "Skirt", new Vector3(0.62f, 0.4f, 0.46f), new Vector3(0f, y0 + 0.68f, 0f), mat, 0f, false);
            Kit.Box(t, "Chest", new Vector3(0.66f, 0.5f, 0.42f), new Vector3(0f, y0 + 1.1f, 0f), mat, 0f, false);
            Kit.Box(t, "ChestTrim", new Vector3(0.7f, 0.08f, 0.46f), new Vector3(0f, y0 + 1.3f, 0f), gold, 0f, false);
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Sphere(t, "Pauldron", new Vector3(0.3f, 0.26f, 0.32f), new Vector3(s * 0.4f, y0 + 1.32f, 0f), mat, false, 8);
                // 手臂：一只举剑，一只持盾
                if (s > 0)
                {
                    Kit.BoxRot(t, "ArmSword", new Vector3(0.16f, 0.5f, 0.18f), new Vector3(0.46f, y0 + 1.05f, 0f),
                        Quaternion.Euler(0f, 0f, -18f), matDark, false);
                    Kit.BoxRot(t, "SwordBlade", new Vector3(0.09f, 1.25f, 0.05f), new Vector3(0.62f, y0 + 1.75f, 0f),
                        Quaternion.Euler(0f, 0f, -18f), M("steel"), false);
                    Kit.BoxRot(t, "SwordGuard", new Vector3(0.44f, 0.09f, 0.12f), new Vector3(0.52f, y0 + 1.18f, 0f),
                        Quaternion.Euler(0f, 0f, -18f), gold, false);
                    Kit.Sphere(t, "SwordPommel", 0.075f, new Vector3(0.4f, y0 + 1.0f, 0f), gold, false, 8);
                }
                else
                {
                    Kit.BoxRot(t, "ArmShield", new Vector3(0.16f, 0.5f, 0.18f), new Vector3(-0.46f, y0 + 1.05f, 0.02f),
                        Quaternion.Euler(0f, 0f, 18f), matDark, false);
                    Kit.CylRot(t, "Shield", 0.42f, 0.1f, new Vector3(-0.66f, y0 + 1.02f, 0.3f),
                        Quaternion.Euler(90f, 0f, 12f), mat, 12);
                    Kit.CylRot(t, "ShieldBoss", 0.17f, 0.06f, new Vector3(-0.66f, y0 + 1.02f, 0.37f),
                        Quaternion.Euler(90f, 0f, 12f), gold, 10);
                }
            }
            // 披风
            Kit.BoxRot(t, "Cape", new Vector3(0.82f, 1.3f, 0.1f), new Vector3(0f, y0 + 0.95f, -0.26f),
                Quaternion.Euler(8f, 0f, 0f), matDark, false);
            // 头 + 头盔 + 羽饰
            Kit.Sphere(t, "Head", 0.21f, new Vector3(0f, y0 + 1.5f, 0f), matDark, false, 9);
            Kit.Cyl(t, "Helmet", 0.24f, 0.26f, new Vector3(0f, y0 + 1.6f, 0f), mat, 10, false);
            Kit.Cone(t, "HelmetTop", 0.16f, 0.22f, new Vector3(0f, y0 + 1.8f, 0f), mat, 8, false);
            Kit.BoxRot(t, "Plume", new Vector3(0.12f, 0.55f, 0.1f), new Vector3(0f, y0 + 1.98f, -0.06f),
                Quaternion.Euler(18f, 0f, 0f), M("cloth_red"), false);

            Kit.Blocker(t, "Blocker", new Vector3(1.9f, 2.2f, 1.9f), new Vector3(0f, 1.1f, 0f));
            return root;
        }

        // ============================================================================================
        // 魔法阵
        // ============================================================================================
        /// <summary>
        /// 地面魔法阵：石盘 + 双层发光圆环 + 五芒星 + 12 枚符文 + 四座小晶柱。直径 ≈ 2*radius。
        /// light:true 时加一盏紫色点光（注意每图 ≤8 点光）。
        /// </summary>
        public static GameObject RuneCircle(Transform parent, Vector3 pos, float radius = 3f, bool light = false)
        {
            radius = Mathf.Max(0.8f, radius);
            var root = Kit.Pivot(parent, "RuneCircle", pos, 0f);
            var t = root.transform;
            var stone = KitMat.Stone("stone_dark");
            var glow = KitMat.Emi("kit_rune_glow", MapMaterials.GlowViolet, 2.2f);
            var glowCyan = KitMat.Emi("kit_rune_cyan", MapMaterials.GlowCyan, 1.8f);

            Kit.Cyl(t, "Disk", radius, 0.1f, new Vector3(0f, 0.05f, 0f), stone, 24, false);
            Kit.Cyl(t, "RingOuter", radius * 0.94f, 0.03f, new Vector3(0f, 0.11f, 0f), glow, 32, false);
            Kit.Cyl(t, "RingInner", radius * 0.6f, 0.03f, new Vector3(0f, 0.115f, 0f), glow, 24, false);
            Kit.Cyl(t, "RingCore", radius * 0.3f, 0.03f, new Vector3(0f, 0.12f, 0f), glowCyan, 16, false);

            // 五芒星（连接五边形隔点）
            int pts = 5;
            for (int i = 0; i < pts; i++)
            {
                float a0 = (i * 360f / pts) * Mathf.Deg2Rad;
                float a1 = ((i + 2) * 360f / pts) * Mathf.Deg2Rad;
                float r = radius * 0.6f;
                Vector3 p0 = new Vector3(Mathf.Cos(a0) * r, 0.13f, Mathf.Sin(a0) * r);
                Vector3 p1 = new Vector3(Mathf.Cos(a1) * r, 0.13f, Mathf.Sin(a1) * r);
                Vector3 mid = (p0 + p1) * 0.5f;
                float len = Vector3.Distance(p0, p1);
                float ang = Mathf.Atan2(p1.z - p0.z, p1.x - p0.x) * Mathf.Rad2Deg;
                Kit.BoxRot(t, "StarLine", new Vector3(len, 0.03f, 0.07f), mid, Quaternion.Euler(0f, -ang, 0f), glow, false);
            }

            // 符文（12 枚围绕外环的短线段，交替紫/青）
            for (int i = 0; i < 12; i++)
            {
                float ang = i * 30f;
                Vector3 d = KitMath.OnCircle(radius * 0.78f, ang);
                bool cyan = (i % 2) == 0;
                Kit.BoxRot(t, "Rune", new Vector3(0.06f, 0.035f, 0.3f), new Vector3(d.x, 0.14f, d.z),
                    Quaternion.Euler(0f, -ang, 0f), cyan ? glowCyan : glow, false);
            }

            // 四座小晶柱
            for (int i = 0; i < 4; i++)
            {
                Vector3 d = KitMath.OnCircle(radius * 0.86f, i * 90f + 45f);
                Kit.Cyl(t, "Pylon", 0.13f, 0.6f, new Vector3(d.x, 0.35f, d.z), KitMat.Stone("stone_light"), 8, false);
                Kit.ConeRot(t, "PylonCrystal", 0.11f, 0.3f, new Vector3(d.x, 0.82f, d.z), Quaternion.identity, glowCyan, 6);
            }

            if (light) Kit.PointLight(t, new Vector3(0f, 0.5f, 0f), MapMaterials.GlowViolet, radius * 2.2f, 1.4f);
            return root;
        }

        // ============================================================================================
        // 水晶簇
        // ============================================================================================
        /// <summary>魔法水晶簇：碎石堆 + 5~7 根双色发光晶柱（主晶最高，其余倾斜）。</summary>
        public static GameObject CrystalCluster(Transform parent, Vector3 pos, float scale = 1f, bool glow = true)
        {
            scale = Mathf.Max(0.2f, scale);
            var root = Kit.Pivot(parent, "CrystalCluster", pos, 0f);
            var t = root.transform;
            var rnd = new KitRand(KitRand.SeedFrom(pos, 505));
            var stone = KitMat.Stone("stone_dark");
            var violet = glow ? KitMat.Emi("kit_crystal_violet", MapMaterials.GlowViolet, 2.0f)
                              : KitMat.Solid("kit_crystal_violet_dark", MapMaterials.GlowViolet * 0.7f);
            var cyan = glow ? KitMat.Emi("kit_crystal_cyan", MapMaterials.GlowCyan, 1.7f)
                            : KitMat.Solid("kit_crystal_cyan_dark", MapMaterials.GlowCyan * 0.7f);

            for (int i = 0; i < 3; i++)
            {
                Vector3 d = KitMath.OnCircle(0.45f * scale, i * 120f + 30f);
                Kit.Sphere(t, "Rock", new Vector3(1.1f, 0.55f, 1.0f) * scale, new Vector3(d.x, 0.2f * scale, d.z),
                    stone, false, 7);
            }
            // 主晶
            Kit.CylRot(t, "MainCrystal", 0.2f * scale, 1.5f * scale, new Vector3(0f, 0.95f * scale, 0f),
                Quaternion.Euler(0f, 0f, 4f), violet, 6);
            Kit.ConeRot(t, "MainTip", 0.2f * scale, 0.55f * scale, new Vector3(-0.05f * scale, 1.95f * scale, 0f),
                Quaternion.Euler(0f, 0f, 4f), violet, 6);
            // 侧晶
            for (int i = 0; i < 5; i++)
            {
                float ang = i * 72f + rnd.Range(-14f, 14f);
                Vector3 d = KitMath.OnCircle(rnd.Range(0.24f, 0.46f) * scale, ang);
                float tilt = rnd.Range(12f, 34f);
                float h = rnd.Range(0.55f, 1.0f) * scale;
                var m = (i % 2 == 0) ? cyan : violet;
                Vector3 dir = new Vector3(-Mathf.Cos(ang * Mathf.Deg2Rad) * tilt, 0f, -Mathf.Sin(ang * Mathf.Deg2Rad) * tilt);
                Kit.CylRot(t, "SideCrystal", 0.12f * scale, h, new Vector3(d.x, 0.15f * scale + h * 0.5f, d.z),
                    Quaternion.Euler(dir.x, ang, dir.z), m, 6);
                Kit.ConeRot(t, "SideTip", 0.12f * scale, 0.3f * scale,
                    new Vector3(d.x, 0.15f * scale + h + 0.12f * scale, d.z),
                    Quaternion.Euler(dir.x, ang, dir.z), m, 6);
            }
            // 地面微光
            Kit.Cyl(t, "GlowPad", 0.85f * scale, 0.03f, new Vector3(0f, 0.15f * scale, 0f), cyan, 16, false);
            return root;
        }

        // ============================================================================================
        // 武器架
        // ============================================================================================
        /// <summary>铁匠铺/兵营的武器架：A 字木架 + 横杆，斜靠 3 把剑 + 2 支长矛 + 2 面盾。</summary>
        public static GameObject WeaponRack(Transform parent, Vector3 pos, float yaw = 0f)
        {
            var root = Kit.Pivot(parent, "WeaponRack", pos, yaw);
            var t = root.transform;
            var wood = KitMat.WoodTinted("wood_dark");
            var plank = KitMat.WoodTinted("wood_plank");
            var iron = M("iron");
            var steel = M("steel");

            // A 字架
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.BoxRot(t, "LegF", new Vector3(0.12f, 1.7f, 0.12f), new Vector3(s * 1.0f, 0.82f, 0.16f),
                    Quaternion.Euler(-12f, 0f, 0f), wood, false);
                Kit.BoxRot(t, "LegB", new Vector3(0.12f, 1.7f, 0.12f), new Vector3(s * 1.0f, 0.82f, -0.16f),
                    Quaternion.Euler(12f, 0f, 0f), wood, false);
            }
            for (int i = 0; i < 2; i++)
                Kit.Box(t, "Rail", new Vector3(2.4f, 0.12f, 0.2f), new Vector3(0f, 1.35f - i * 0.75f, 0f), plank, 0f, false);

            // 剑 ×3（斜靠）
            for (int i = 0; i < 3; i++)
            {
                float sx = -0.55f + i * 0.55f;
                Kit.BoxRot(t, "Blade", new Vector3(0.1f, 1.15f, 0.035f), new Vector3(sx, 0.55f, 0.12f),
                    Quaternion.Euler(0f, 0f, -8f), steel, false);
                Kit.BoxRot(t, "Guard", new Vector3(0.34f, 0.07f, 0.1f), new Vector3(sx + 0.08f, 0.02f, 0.12f),
                    Quaternion.Euler(0f, 0f, -8f), iron, false);
                Kit.CylRot(t, "Grip", 0.045f, 0.3f, new Vector3(sx + 0.11f, -0.16f, 0.12f),
                    Quaternion.Euler(0f, 0f, -8f), wood, 6);
            }
            // 长矛 ×2（架在横杆上）
            for (int i = 0; i < 2; i++)
            {
                float sx = -1.2f + i * 2.4f;
                Kit.CylRot(t, "SpearShaft", 0.035f, 2.4f, new Vector3(sx, 1.3f, -0.1f), Quaternion.Euler(0f, 0f, 90f), wood, 6);
                Kit.ConeRot(t, "SpearTip", 0.09f, 0.34f, new Vector3(sx + (i == 0 ? -1.2f : 1.2f), 1.3f, -0.1f),
                    Quaternion.Euler(0f, 0f, i == 0 ? 90f : -90f), steel, 6);
            }
            // 盾 ×2
            for (int i = 0; i < 2; i++)
            {
                float sx = -0.95f + i * 1.9f;
                Kit.CylRot(t, "Shield", 0.4f, 0.1f, new Vector3(sx, 1.85f, -0.18f), Quaternion.Euler(90f, 0f, 0f), plank, 12);
                Kit.CylRot(t, "ShieldBoss", 0.15f, 0.06f, new Vector3(sx, 1.85f, -0.25f), Quaternion.Euler(90f, 0f, 0f), iron, 10);
            }
            Kit.Blocker(t, "Blocker", new Vector3(2.6f, 2.2f, 0.8f), new Vector3(0f, 1.1f, 0f));
            return root;
        }

        // ============================================================================================
        // 庄稼地
        // ============================================================================================
        /// <summary>
        /// 一垄庄稼：土垄 + 两侧田埂 + 沿垄的作物（wheat=麦子，cabbage=卷心菜，pumpkin=南瓜）。
        /// 默认长 5m、正面朝 +Z。可并排多垄拼成农田。
        /// </summary>
        public static GameObject CropRow(Transform parent, Vector3 pos, float yaw = 0f, float length = 5f, string crop = "wheat")
        {
            length = Mathf.Max(1f, length);
            var root = Kit.Pivot(parent, "CropRow", pos, yaw);
            var t = root.transform;
            var dirt = M("dirt");
            var dirtDark = M("dirt_dark");

            Kit.Slab(t, "Soil", new Vector3(1.1f, 0.16f, length), new Vector3(0f, 0.08f, 0f), dirt);
            for (int s = -1; s <= 1; s += 2)
                Kit.Slab(t, "Furrow", new Vector3(0.16f, 0.22f, length), new Vector3(s * 0.6f, 0.11f, 0f), dirtDark);

            int count = Mathf.Max(2, Mathf.FloorToInt(length / 0.62f));
            var rnd = new KitRand(KitRand.SeedFrom(pos, 3311));
            for (int i = 0; i < count; i++)
            {
                float z = -length * 0.5f + (i + 0.5f) * (length / count);
                float x = rnd.Range(-0.16f, 0.16f);
                if (crop == "cabbage")
                {
                    Kit.Sphere(t, "Cabbage", new Vector3(0.42f, 0.32f, 0.42f), new Vector3(x, 0.24f, z),
                        M("foliage"), false, 8);
                    Kit.Sphere(t, "Leaf", new Vector3(0.5f, 0.14f, 0.5f), new Vector3(x, 0.15f, z),
                        M("foliage_dark"), false, 7);
                }
                else if (crop == "pumpkin")
                {
                    Kit.Sphere(t, "Pumpkin", new Vector3(0.48f, 0.36f, 0.48f), new Vector3(x, 0.2f, z),
                        M("cloth_orange"), false, 9);
                    Kit.Box(t, "PumpkinStem", new Vector3(0.07f, 0.12f, 0.07f), new Vector3(x, 0.42f, z),
                        M("foliage_dark"), 0f, false);
                }
                else
                {
                    for (int b = 0; b < 3; b++)
                    {
                        float a = b * 120f + i * 37f;
                        Vector3 d = KitMath.OnCircle(0.09f, a);
                        Kit.BoxRot(t, "WheatBlade", new Vector3(0.045f, 0.62f, 0.045f),
                            new Vector3(x + d.x, 0.48f, z + d.z),
                            Quaternion.Euler(0f, a, rnd.Range(-9f, 9f)),
                            b == 0 ? M("grass_dry") : M("grass_dry"), false);
                    }
                }
            }
            return root;
        }
    }
}
