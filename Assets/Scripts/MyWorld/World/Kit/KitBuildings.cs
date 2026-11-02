using System.Collections.Generic;
using UnityEngine;

namespace MyWorld
{
    // ============================================================================================
    // 建筑生成器（第二批）：酒馆 / 冒险者协会 / 城门 / 市集摊位 / 喷泉 / 水井 / 委托板。
    // 与 KitArchitecture.cs（民居/城墙/塔楼）是同一个 partial 类：共用窗/门/灯笼/木筋等私有工具。
    //
    // 坐标语义：pos/yaw 都是**父节点局部空间**；返回的根节点已摆在 pos 上，正面 = 本地 +Z。
    // 尺度：角色 1.5m、门高 2.1m、一层 2.8~3.2m；民居两层总高约 6m（见 HouseSpec 说明）。
    // ============================================================================================
    public static partial class KitArchitecture
    {
        // ---------------------------------------------------------------- 本文件共用材质/工具
        static Material StoneM(string key) { return KitMat.Stone(key); }
        static Material RoofM(string key) { return KitMat.Roof(key); }
        static Material TimberM(string key) { return KitMat.Timber(key); }
        static Material WoodM(string key) { return KitMat.WoodTinted(key); }

        static Material GoldM()
        {
            if (_gold == null) _gold = MapMaterials.Get("gold");
            return _gold;
        }
        static Material _gold;
        static Material _bronze;
        static Material BronzeM()
        {
            if (_bronze == null) _bronze = MapMaterials.Get("bronze");
            return _bronze;
        }
        static Material _darkSolid;
        static Material DarkSolid()
        {
            // 屋脊/门楣压暗的纯色（瓦片纹理放在大坡面上，脊瓦用纯色更干净）
            if (_darkSolid == null) _darkSolid = KitMat.Solid("kit_ridge_dark", KitPalette.Darken(MapMaterials.RoofTerracotta, 0.55f), 0.22f);
            return _darkSolid;
        }

        /// <summary>带纹理的任意旋转方板（遮阳棚布条、斜置展板、门扇）。</summary>
        static GameObject TexSlabRot(Transform parent, string name, Vector3 size, Vector3 pos, Quaternion rot,
            Material mat, bool collider = false)
        {
            return Kit.MeshRot(parent, name, KitGeo.BoxMesh(size, Vector2.zero), pos, rot, mat, collider);
        }

        /// <summary>沿本地 X 的屋脊压条。length 应 = 屋面宽 + 2*出檐。</summary>
        static void RidgeX(Transform parent, float length, float y, Material mat)
        {
            Kit.Box(parent, "RidgeCap", new Vector3(length, 0.2f, 0.42f), new Vector3(0f, y, 0f), mat, 0f, false);
        }

        /// <summary>沿本地 Z 的屋脊压条（屋脊朝 Z 的房子）。</summary>
        static void RidgeZ(Transform parent, float length, float y, Material mat)
        {
            Kit.Box(parent, "RidgeCap", new Vector3(0.42f, 0.2f, length), new Vector3(0f, y, 0f), mat, 0f, false);
        }

        /// <summary>沿本地 X 的城垛（merlon），用于墙顶/门楼顶。</summary>
        static void MerlonsX(Transform parent, string name, float span, float y, float depth, float mw, float mh, int count, Material mat)
        {
            for (int i = 0; i < count; i++)
            {
                float t = count == 1 ? 0.5f : i / (float)(count - 1);
                float x = -span * 0.5f + span * t;
                Kit.Box(parent, name, new Vector3(mw, mh, depth), new Vector3(x, y, 0f), mat, 0f, false);
            }
        }

        /// <summary>圆环布置的方块（水井/喷泉的池壁、塔顶垛口）。方块长边会自动沿切线方向。</summary>
        static void RingOfBoxes(Transform parent, string name, float radius, float y, int count, Vector3 size,
            Material mat, float startAng = 0f)
        {
            for (int i = 0; i < count; i++)
            {
                float ang = startAng + i * 360f / count;
                Vector3 d = KitMath.OnCircle(radius, ang);
                Kit.Box(parent, name, size, new Vector3(d.x, y, d.z), mat, ang + 90f, false);
            }
        }

        // ============================================================================================
        // 酒馆 / 旅店
        // ============================================================================================
        /// <summary>
        /// 两层酒馆（地标级）：石砌一层 + 灰泥木筋二层 + 大坡屋顶 + 天窗 + 阳台 +
        /// 主招牌/悬挂招牌 + 壁灯 + 门口木桶长凳。约 260~300 个 primitive。
        /// </summary>
        public static GameObject Inn(Transform parent, Vector3 pos, float yaw = 0f)
        {
            var root = Kit.Pivot(parent, "Inn", pos, yaw);
            var t = root.transform;
            var rnd = new KitRand(KitRand.SeedFrom(pos, 6101));

            const float W = 9f, D = 7f;
            const float baseH = 0.35f, gH = 2.9f, uH = 2.5f;
            float gTop = baseH + gH;              // 3.25
            float eave = gTop + uH;               // 5.75
            const float ov = 0.6f, roofH = 2.7f;
            float ridgeY = eave + roofH;          // 8.45

            var stoneW = StoneM("stone_wall");
            var stoneD = StoneM("stone_dark");
            var stoneL = StoneM("stone_light");
            var plaster = KitMat.Wall("plaster_warm");
            var timber = TimberM("timber_dark");
            var roofMat = RoofM("roof_terracotta");
            var wood = WoodM("wood_plank");
            var woodDark = WoodM("wood_dark");

            // ---- 基座 / 一层 / 二层 ----
            Kit.Slab(t, "Plinth", new Vector3(W + 0.5f, baseH, D + 0.5f), new Vector3(0f, baseH * 0.5f, 0f), stoneD);
            Kit.Slab(t, "Ground", new Vector3(W, gH, D), new Vector3(0f, baseH + gH * 0.5f, 0f), stoneW);
            Kit.Slab(t, "Upper", new Vector3(W + 0.3f, uH, D + 0.3f), new Vector3(0f, gTop + uH * 0.5f, 0f), plaster);
            Kit.Box(t, "BeltBand", new Vector3(W + 0.55f, 0.16f, D + 0.55f), new Vector3(0f, gTop, 0f), timber, 0f, false);
            Kit.Box(t, "EaveBand", new Vector3(W + 0.6f, 0.14f, D + 0.6f), new Vector3(0f, eave - 0.1f, 0f), timber, 0f, false);

            // 一层四角石柱 + 正面两块角石（错缝）
            for (int sx = -1; sx <= 1; sx += 2)
                for (int sz = -1; sz <= 1; sz += 2)
                    Kit.Box(t, "QuoinPillar", new Vector3(0.68f, gH, 0.68f),
                        new Vector3(sx * (W * 0.5f - 0.1f), baseH + gH * 0.5f, sz * (D * 0.5f - 0.1f)), stoneL, 0f, false);
            for (int c = -1; c <= 1; c += 2)
                for (int i = 0; i < 5; i++)
                {
                    bool wide = (i % 2 == 0);
                    Kit.Box(t, "Quoin", new Vector3(wide ? 0.62f : 0.4f, 0.28f, wide ? 0.4f : 0.62f),
                        new Vector3(c * (W * 0.5f + 0.01f), baseH + 0.24f + i * 0.55f, D * 0.5f - 0.28f), stoneL, 0f, false);
                }

            // ---- 立面 ----
            var front = Facade(t, "Front", new Vector3(0f, 0f, D * 0.5f), 0f);
            var back = Facade(t, "Back", new Vector3(0f, 0f, -D * 0.5f), 180f);
            var right = Facade(t, "RightFace", new Vector3(W * 0.5f, 0f, 0f), 90f);
            var left = Facade(t, "LeftFace", new Vector3(-W * 0.5f, 0f, 0f), 270f);

            // 一层窗（石框 + 百叶 + 花箱）
            Window(front, "GW1", new Vector3(-3.0f, 1.95f, 0.02f), 1.3f, 1.5f, rnd.Chance(0.5f), true, true, stoneL);
            Window(front, "GW2", new Vector3(3.0f, 1.95f, 0.02f), 1.3f, 1.5f, rnd.Chance(0.5f), true, true, stoneL);
            Window(left, "GW3", new Vector3(0.6f, 1.95f, 0.02f), 1.15f, 1.4f, rnd.Chance(0.4f), false, false, stoneL);
            Window(right, "GW4", new Vector3(-0.4f, 1.95f, 0.02f), 1.15f, 1.4f, rnd.Chance(0.4f), false, false, stoneL);
            Window(back, "GW5", new Vector3(2.4f, 1.95f, 0.02f), 1.15f, 1.4f, false, false, false, stoneL);

            // 二层木筋 + 窗
            FacadeTimber(front, W, gTop, uH, 1, timber, false, rnd);
            FacadeTimber(back, W, gTop, uH, 1, timber, false, rnd);
            FacadeTimber(right, D, gTop, uH, 1, timber, false, rnd);
            FacadeTimber(left, D, gTop, uH, 1, timber, false, rnd);
            Window(front, "UW1", new Vector3(-2.9f, gTop + uH * 0.56f, 0.02f), 0.9f, 1.05f, rnd.Chance(0.55f), true, false, timber);
            Window(front, "UW2", new Vector3(0f, gTop + uH * 0.56f, 0.02f), 0.9f, 1.05f, rnd.Chance(0.55f), true, false, timber);
            Window(front, "UW3", new Vector3(2.9f, gTop + uH * 0.56f, 0.02f), 0.9f, 1.05f, rnd.Chance(0.55f), true, false, timber);
            Window(right, "UW4", new Vector3(-1.5f, gTop + uH * 0.56f, 0.02f), 0.85f, 1.0f, rnd.Chance(0.4f), false, false, timber);
            Window(right, "UW5", new Vector3(1.6f, gTop + uH * 0.56f, 0.02f), 0.85f, 1.0f, rnd.Chance(0.4f), false, false, timber);
            Window(left, "UW6", new Vector3(0.4f, gTop + uH * 0.56f, 0.02f), 0.85f, 1.0f, rnd.Chance(0.4f), false, false, timber);
            Window(back, "UW7", new Vector3(-1.8f, gTop + uH * 0.56f, 0.02f), 0.85f, 1.0f, false, false, false, timber);
            Window(back, "UW8", new Vector3(1.8f, gTop + uH * 0.56f, 0.02f), 0.85f, 1.0f, false, false, false, timber);

            // 门（拱门）
            Door(front, new Vector3(0f, 0f, 0.02f), true);

            // ---- 阳台 ----
            float balY = gTop + 0.07f;
            Kit.Box(t, "BalconyFloor", new Vector3(5.6f, 0.14f, 1.0f), new Vector3(0f, balY, D * 0.5f + 0.52f), wood, 0f, false);
            for (int i = 0; i < 7; i++)
            {
                float bx = -2.6f + i * (5.2f / 6f);
                Kit.Box(t, "BalPost", new Vector3(0.07f, 0.64f, 0.07f), new Vector3(bx, balY + 0.39f, D * 0.5f + 1.0f), timber, 0f, false);
            }
            Kit.Box(t, "BalRail", new Vector3(5.6f, 0.08f, 0.08f), new Vector3(0f, balY + 0.75f, D * 0.5f + 1.0f), timber, 0f, false);
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Box(t, "BalSideRail", new Vector3(0.08f, 0.08f, 0.96f), new Vector3(s * 2.78f, balY + 0.75f, D * 0.5f + 0.52f), timber, 0f, false);
                Kit.Box(t, "BalBracket", new Vector3(0.12f, 0.12f, 1.15f), new Vector3(s * 2.4f, balY - 0.35f, D * 0.5f + 0.42f), timber, 0f, false);
            }

            // ---- 屋顶 + 山墙 + 天窗 + 烟囱 ----
            Kit.Mesh(t, "Roof", Kit.GableRoofMesh(W + 0.9f, D + 0.9f, roofH, ov, 0.18f), new Vector3(0f, eave, 0f), roofMat, false);
            RidgeX(t, W + 0.9f + ov * 2f, ridgeY + 0.08f, DarkSolid());
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.GableFace(t, "Gable", D, roofH, 0.28f,
                    new Vector3(s * (W * 0.5f + 0.14f), eave, 0f), plaster, s * 90f);
                GableTimber(t, "GableTimber", new Vector3(s * (W * 0.5f + 0.15f), eave, 0f), s * 90f, D, roofH, timber);
                GableWindow(Facade(t, "GableFace", new Vector3(s * (W * 0.5f + 0.16f), eave, 0f), s * 90f),
                    "GableWindow", new Vector3(0f, roofH * 0.4f, 0.12f), 0.52f);
            }

            // 天窗（正面坡上）
            float dz = 2.45f;
            float dormerY = ridgeY - Mathf.Abs(dz) * (roofH / (D * 0.5f + ov)) - 0.35f;
            Kit.Box(t, "DormerBody", new Vector3(1.35f, 1.05f, 0.95f), new Vector3(1.55f, dormerY, dz), plaster, 0f, false);
            Kit.Box(t, "DormerGlass", new Vector3(0.95f, 0.68f, 0.06f), new Vector3(1.55f, dormerY + 0.04f, dz + 0.49f), WinDay(), 0f, false);
            Kit.Box(t, "DormerFrameL", new Vector3(0.08f, 0.78f, 0.08f), new Vector3(1.55f - 0.52f, dormerY + 0.04f, dz + 0.5f), timber, 0f, false);
            Kit.Box(t, "DormerFrameR", new Vector3(0.08f, 0.78f, 0.08f), new Vector3(1.55f + 0.52f, dormerY + 0.04f, dz + 0.5f), timber, 0f, false);
            Kit.Mesh(t, "DormerRoof", Kit.PyramidRoofMesh(1.7f, 1.3f, 0.62f), new Vector3(1.55f, dormerY + 0.55f, dz), roofMat, false);

            // 烟囱 + 烟
            Kit.Box(t, "Chimney", new Vector3(0.9f, 2.6f, 0.9f), new Vector3(-2.4f, 7.95f, 0.7f), stoneW, 0f, false);
            Kit.Box(t, "ChimneyCap", new Vector3(1.16f, 0.18f, 1.16f), new Vector3(-2.4f, 9.3f, 0.7f), stoneL, 0f, false);
            Kit.Box(t, "ChimneyBand", new Vector3(1.0f, 0.14f, 1.0f), new Vector3(-2.4f, 8.7f, 0.7f), stoneL, 0f, false);
            Kit.Smoke(t, new Vector3(-2.4f, 9.45f, 0.7f), new Color(0.86f, 0.86f, 0.9f), 4, 0.3f);

            // ---- 招牌 / 壁灯 / 门口道具 ----
            Kit.SignBoard(t, "金鹿酒馆", new Vector3(0f, 4.62f, D * 0.5f + 0.2f), 0f, 2.9f, 0.6f,
                MapMaterials.ClothCream, KitPalette.Ink);
            // 悬挂招牌（垂直墙面，铁支架）
            Kit.Box(t, "SignBracketH", new Vector3(0.08f, 0.08f, 1.05f), new Vector3(2.5f, 4.15f, D * 0.5f + 0.42f), Iron(), 0f, false);
            Kit.Box(t, "SignBracketV", new Vector3(0.08f, 0.5f, 0.08f), new Vector3(2.5f, 3.95f, D * 0.5f + 0.92f), Iron(), 0f, false);
            Kit.Box(t, "SignChain1", new Vector3(0.03f, 0.35f, 0.03f), new Vector3(2.35f, 3.6f, D * 0.5f + 0.9f), Iron(), 0f, false);
            Kit.Box(t, "SignChain2", new Vector3(0.03f, 0.35f, 0.03f), new Vector3(2.65f, 3.6f, D * 0.5f + 0.9f), Iron(), 0f, false);
            var hang = Kit.SignBoard(t, "酒", new Vector3(2.5f, 3.18f, D * 0.5f + 0.9f), 90f, 0.95f, 0.72f,
                MapMaterials.ClothRed, MapMaterials.ClothCream);
            hang.name = "HangingSign";

            WallLantern(front, "LanternL", new Vector3(-1.55f, 2.95f, 0.02f));
            WallLantern(front, "LanternR", new Vector3(1.55f, 2.95f, 0.02f));

            // 门口木桶/长凳/麻袋
            KitProps.Barrel(t, new Vector3(3.7f, 0f, 3.95f), 18f, 0.95f);
            KitProps.Barrel(t, new Vector3(4.25f, 0f, 3.35f), -24f, 0.82f);
            KitProps.Bench(t, new Vector3(-3.1f, 0f, 3.95f), 0f, 1.6f);
            KitProps.Crate(t, new Vector3(-4.15f, 0f, 3.65f), 12f, 0.85f);
            KitProps.Sack(t, new Vector3(4.3f, 0f, 2.75f), 40f, 0.9f);

            Kit.Blocker(t, "Blocker", new Vector3(W + 0.4f, eave, D + 0.4f), new Vector3(0f, eave * 0.5f, 0f));
            Kit.MakeFadeable(root, 0.22f);
            return root;
        }

        // ============================================================================================
        // 冒险者协会（公会堂）
        // ============================================================================================
        /// <summary>
        /// 冒险者协会：两层石造公堂，屋脊朝前（正面是三角山墙）+ 大拱门/石柱/台阶 +
        /// 双旗 + 壁灯 + 圆形山墙窗。
        /// <b>正面左侧下方预留了一块空白石墙</b>给委托板：挂点空物体名 `QuestBoardAnchor`，
        /// 位于墙面外 0.16m，朝向 +Z，尺寸约 3.0m 宽 × 1.7m 高（y 1.05~2.75）。
        /// </summary>
        public const string QuestBoardAnchorName = "QuestBoardAnchor";

        public static GameObject GuildHall(Transform parent, Vector3 pos, float yaw = 0f)
        {
            var root = Kit.Pivot(parent, "GuildHall", pos, yaw);
            var t = root.transform;

            const float W = 11f, D = 8f;
            const float baseH = 0.45f, gH = 3.3f, uH = 3.0f;
            float gTop = baseH + gH;             // 3.75
            float eave = gTop + uH;              // 6.75
            const float roofH = 3.2f, ov = 0.7f;
            float ridgeY = eave + roofH;         // 9.95

            var stoneW = StoneM("stone_wall");
            var stoneD = StoneM("stone_dark");
            var stoneL = StoneM("stone_light");
            var timber = TimberM("timber_dark");
            var roofMat = RoofM("roof_slate");
            var wood = WoodM("wood_plank");
            var woodDark = WoodM("wood_dark");

            // ---- 体块 ----
            Kit.Slab(t, "Plinth", new Vector3(W + 0.8f, baseH, D + 0.8f), new Vector3(0f, baseH * 0.5f, 0f), stoneD);
            Kit.Slab(t, "Ground", new Vector3(W, gH, D), new Vector3(0f, baseH + gH * 0.5f, 0f), stoneW);
            Kit.Slab(t, "Upper", new Vector3(W, uH, D), new Vector3(0f, gTop + uH * 0.5f, 0f), stoneW);
            Kit.Box(t, "Band1", new Vector3(W + 0.24f, 0.22f, D + 0.24f), new Vector3(0f, gTop, 0f), stoneL, 0f, false);
            Kit.Box(t, "Band2", new Vector3(W + 0.3f, 0.2f, D + 0.3f), new Vector3(0f, eave - 0.12f, 0f), stoneL, 0f, false);
            // 角柱 + 正面扶壁
            for (int sx = -1; sx <= 1; sx += 2)
                for (int sz = -1; sz <= 1; sz += 2)
                    Kit.Box(t, "CornerPilaster", new Vector3(0.8f, eave, 0.8f),
                        new Vector3(sx * (W * 0.5f - 0.12f), baseH + (eave - baseH) * 0.5f, sz * (D * 0.5f - 0.12f)), stoneL, 0f, false);
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Box(t, "Buttress", new Vector3(0.55f, gH, 1.0f),
                    new Vector3(s * 4.7f, baseH + gH * 0.5f, D * 0.5f + 0.4f), stoneL, 0f, false);
                Kit.Box(t, "ButtressCap", new Vector3(0.7f, 0.18f, 1.15f),
                    new Vector3(s * 4.7f, gTop + 0.1f, D * 0.5f + 0.4f), stoneL, 0f, false);
            }

            // ---- 立面 ----
            var front = Facade(t, "Front", new Vector3(0f, 0f, D * 0.5f), 0f);
            var back = Facade(t, "Back", new Vector3(0f, 0f, -D * 0.5f), 180f);
            var right = Facade(t, "RightFace", new Vector3(W * 0.5f, 0f, 0f), 90f);
            var left = Facade(t, "LeftFace", new Vector3(-W * 0.5f, 0f, 0f), 270f);

            // 正面一层：右侧两扇高窗；左侧下方留白（委托板预留区，见上方注释）
            Window(front, "GW1", new Vector3(3.1f, 2.1f, 0.02f), 1.15f, 1.7f, false, false, false, stoneL);
            Window(front, "GW2", new Vector3(4.6f, 2.1f, 0.02f), 1.15f, 1.7f, false, false, false, stoneL);
            // 正面二层四扇
            for (int i = 0; i < 4; i++)
            {
                float wx = -3.6f + i * 2.4f;
                Window(front, "UW" + i, new Vector3(wx, gTop + uH * 0.54f, 0.02f), 0.95f, 1.25f,
                    i == 1, true, false, stoneL);
            }
            // 侧面/背面
            for (int s = -1; s <= 1; s += 2)
            {
                Window(right, "SW" + (s + 1), new Vector3(s * 2.2f, 2.1f, 0.02f), 1.05f, 1.55f, false, false, false, stoneL);
                Window(left, "SW" + (s + 1), new Vector3(s * 2.2f, 2.1f, 0.02f), 1.05f, 1.55f, false, false, false, stoneL);
                Window(right, "SU" + (s + 1), new Vector3(s * 2.2f, gTop + uH * 0.54f, 0.02f), 0.9f, 1.15f, false, true, false, stoneL);
                Window(left, "SU" + (s + 1), new Vector3(s * 2.2f, gTop + uH * 0.54f, 0.02f), 0.9f, 1.15f, false, true, false, stoneL);
            }
            Window(back, "BW1", new Vector3(-2.5f, 2.1f, 0.02f), 1.05f, 1.55f, false, false, false, stoneL);
            Window(back, "BW2", new Vector3(2.5f, 2.1f, 0.02f), 1.05f, 1.55f, false, false, false, stoneL);
            Window(back, "BW3", new Vector3(0f, gTop + uH * 0.54f, 0.02f), 1.1f, 1.3f, true, false, false, stoneL);

            // ---- 大门（双扇 + 拱石 + 石柱 + 三级台阶）----
            float dh = 3.0f, dw = 2.3f;
            Kit.Box(t, "DoorRecess", new Vector3(dw, dh, 0.16f), new Vector3(0f, dh * 0.5f + 0.05f, D * 0.5f + 0.03f),
                KitMat.Solid("kit_door_dark", KitPalette.Darken(MapMaterials.TimberDark, 0.35f)), 0f, false);
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Box(t, "DoorLeaf", new Vector3(dw * 0.49f, dh - 0.1f, 0.14f),
                    new Vector3(s * dw * 0.247f, (dh - 0.1f) * 0.5f + 0.05f, D * 0.5f + 0.12f), woodDark, 0f, false);
                for (int b = 0; b < 3; b++)
                    Kit.Box(t, "DoorBand", new Vector3(dw * 0.5f, 0.09f, 0.05f),
                        new Vector3(s * dw * 0.247f, 0.55f + b * 0.85f, D * 0.5f + 0.2f), Iron(), 0f, false);
                Kit.Sphere(t, "DoorHandle", 0.07f, new Vector3(s * 0.16f, 1.35f, D * 0.5f + 0.22f), GoldM(), false, 8);
                // 石柱
                Kit.Cyl(t, "Column", 0.26f, dh + 0.55f, new Vector3(s * (dw * 0.5f + 0.42f), (dh + 0.55f) * 0.5f + 0.05f, D * 0.5f + 0.2f),
                    stoneL, 12, false);
                Kit.Box(t, "ColumnBase", new Vector3(0.72f, 0.22f, 0.72f), new Vector3(s * (dw * 0.5f + 0.42f), 0.16f, D * 0.5f + 0.2f), stoneL, 0f, false);
                Kit.Box(t, "ColumnCap", new Vector3(0.78f, 0.24f, 0.78f), new Vector3(s * (dw * 0.5f + 0.42f), dh + 0.72f, D * 0.5f + 0.2f), stoneL, 0f, false);
            }
            // 拱石
            int an = 9;
            for (int i = 0; i < an; i++)
            {
                float a = Mathf.PI * (i / (float)(an - 1));
                float ax = Mathf.Cos(a) * (dw * 0.5f + 0.2f);
                float ay = Mathf.Sin(a) * (dw * 0.5f + 0.2f);
                Kit.BoxRot(t, "ArchStone", new Vector3(0.32f, 0.46f, 0.26f),
                    new Vector3(ax, dh + 0.15f + ay, D * 0.5f + 0.2f), Quaternion.Euler(0f, 0f, a * Mathf.Rad2Deg), stoneL, false);
            }
            // 台阶
            for (int i = 0; i < 3; i++)
                Kit.Box(t, "Step" + i, new Vector3(dw + 1.5f - i * 0.3f, 0.15f, 0.55f),
                    new Vector3(0f, 0.075f + i * 0.15f, D * 0.5f + 0.62f + i * 0.28f), i == 2 ? stoneL : stoneD, 0f, false);

            // ---- 屋顶（脊沿 Z，正面山墙）+ 山墙装饰 ----
            Kit.MeshRot(t, "Roof", Kit.GableRoofMesh(D, W, roofH, ov, 0.2f), new Vector3(0f, eave, 0f),
                Quaternion.Euler(0f, 90f, 0f), roofMat, false);
            RidgeZ(t, D + ov * 2f, ridgeY + 0.08f, KitMat.Solid("kit_ridge_slate", KitPalette.Darken(MapMaterials.RoofSlate, 0.45f), 0.2f));
            var gableFront = Facade(t, "GableFront", new Vector3(0f, eave, D * 0.5f), 0f);
            Kit.GableFace(t, "GableF", W, roofH, 0.3f, new Vector3(0f, eave, D * 0.5f), stoneW, 0f);
            Kit.GableFace(t, "GableB", W, roofH, 0.3f, new Vector3(0f, eave, -D * 0.5f), stoneW, 180f);
            GableTimber(t, "GableTimberF", new Vector3(0f, eave, D * 0.5f + 0.02f), 0f, W, roofH, timber);
            GableWindow(gableFront, "RoseWindow", new Vector3(0f, roofH * 0.42f, 0.18f), 0.82f);
            // 山墙封檐板（沿两条坡边）
            for (int s = -1; s <= 1; s += 2)
            {
                float half = W * 0.5f;
                float len = Mathf.Sqrt(half * half + roofH * roofH);
                float ang = Mathf.Atan2(roofH, half) * Mathf.Rad2Deg;
                Kit.BoxRot(t, "BargeBoard", new Vector3(len, 0.18f, 0.14f),
                    new Vector3(s * half * 0.5f, eave + roofH * 0.5f + 0.08f, D * 0.5f + 0.12f),
                    Quaternion.Euler(0f, 0f, s > 0 ? ang : 180f - ang), timber, false);
            }
            // 山墙徽章（盾牌 + 金环）
            Kit.Box(t, "Crest", new Vector3(0.95f, 1.15f, 0.12f), new Vector3(0f, eave + 0.75f, D * 0.5f + 0.22f), stoneD, 0f, false);
            Kit.CylRot(t, "CrestRing", 0.34f, 0.08f, new Vector3(0f, eave + 0.95f, D * 0.5f + 0.3f),
                Quaternion.Euler(90f, 0f, 0f), GoldM(), 12, false);
            Kit.Box(t, "CrestBar", new Vector3(0.42f, 0.1f, 0.06f), new Vector3(0f, eave + 0.95f, D * 0.5f + 0.32f), GoldM(), 0f, false);

            // ---- 招牌 / 旗帜 / 壁灯 / 烟囱 ----
            Kit.SignBoard(t, "冒险者协会", new Vector3(0f, 4.35f, D * 0.5f + 0.24f), 0f, 3.6f, 0.58f,
                MapMaterials.ClothCream, KitPalette.Ink);
            KitProps.Banner(t, new Vector3(-2.35f, 0f, D * 0.5f + 0.62f), 0f, "cloth_blue", "gold");
            KitProps.Banner(t, new Vector3(2.35f, 0f, D * 0.5f + 0.62f), 0f, "cloth_blue", "gold");
            WallLantern(front, "LanternL", new Vector3(-1.85f, 2.95f, 0.02f));
            WallLantern(front, "LanternR", new Vector3(1.85f, 2.95f, 0.02f));
            Kit.Box(t, "Chimney1", new Vector3(0.85f, 2.4f, 0.85f), new Vector3(-3.2f, 8.6f, -1.6f), stoneW, 0f, false);
            Kit.Box(t, "ChimneyCap1", new Vector3(1.05f, 0.16f, 1.05f), new Vector3(-3.2f, 9.85f, -1.6f), stoneL, 0f, false);
            Kit.Smoke(t, new Vector3(-3.2f, 9.98f, -1.6f), new Color(0.84f, 0.84f, 0.88f), 4, 0.3f);
            Kit.Box(t, "Chimney2", new Vector3(0.8f, 2.2f, 0.8f), new Vector3(3.4f, 8.2f, -1.4f), stoneW, 0f, false);
            Kit.Box(t, "ChimneyCap2", new Vector3(1.0f, 0.16f, 1.0f), new Vector3(3.4f, 9.35f, -1.4f), stoneL, 0f, false);

            // ---- 委托板挂点（空白墙预留区，lead 把 QuestBoardInteractable 挂到这个空物体下）----
            var anchor = Kit.Pivot(t, QuestBoardAnchorName, new Vector3(-3.6f, 1.9f, D * 0.5f + 0.16f), 0f);

            Kit.Blocker(t, "Blocker", new Vector3(W + 0.5f, eave, D + 0.5f), new Vector3(0f, eave * 0.5f, 0f));
            Kit.MakeFadeable(root, 0.2f);
            return root;
        }

        // ============================================================================================
        // 城门
        // ============================================================================================
        /// <summary>
        /// 城门：两座圆塔 + 中间门楼（拱形门洞 + 吊闸 + 敞开的木门）+ 城垛 + 两侧接墙 + 旗帜。
        /// 门洞沿本地 Z 方向通行（正面 +Z）。约 250~300 个 primitive。
        /// </summary>
        public static GameObject CastleGate(Transform parent, Vector3 pos, float yaw = 0f)
        {
            var root = Kit.Pivot(parent, "CastleGate", pos, yaw);
            var t = root.transform;
            var stoneW = StoneM("stone_wall");
            var stoneD = StoneM("stone_dark");
            var stoneL = StoneM("stone_light");
            var timber = TimberM("timber_dark");
            var woodDark = WoodM("wood_dark");
            var roofMat = RoofM("roof_slate");

            const float gateW = 5.2f, gateD = 2.4f, gateH = 6.6f;
            const float openW = 2.4f, openH = 4.3f;

            // ---- 门楼：两侧门柱 + 拱上墙 ----
            float pierW = (gateW - openW) * 0.5f;
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Slab(t, "Pier", new Vector3(pierW, gateH, gateD),
                    new Vector3(s * (openW * 0.5f + pierW * 0.5f), gateH * 0.5f, 0f), stoneW);
                Kit.Slab(t, "PierBase", new Vector3(pierW + 0.3f, 0.7f, gateD + 0.3f),
                    new Vector3(s * (openW * 0.5f + pierW * 0.5f), 0.35f, 0f), stoneD);
                // 正面角石
                for (int i = 0; i < 5; i++)
                    Kit.Box(t, "PierQuoin", new Vector3(0.4f, 0.4f, 0.34f),
                        new Vector3(s * (openW * 0.5f + 0.06f), 1.1f + i * 1.05f, gateD * 0.5f + 0.05f), stoneL, 0f, false);
            }
            Kit.Slab(t, "Lintel", new Vector3(gateW, gateH - openH, gateD),
                new Vector3(0f, (openH + gateH) * 0.5f, 0f), stoneW);

            // 门洞拱石（前后两面）
            int an = 9;
            for (int face = -1; face <= 1; face += 2)
                for (int i = 0; i < an; i++)
                {
                    float a = Mathf.PI * (i / (float)(an - 1));
                    float ax = Mathf.Cos(a) * (openW * 0.5f + 0.05f);
                    float ay = Mathf.Sin(a) * (openW * 0.5f + 0.05f);
                    Kit.BoxRot(t, "ArchStone", new Vector3(0.34f, 0.5f, 0.26f),
                        new Vector3(ax, openH + 0.12f + ay, face * (gateD * 0.5f + 0.06f)),
                        Quaternion.Euler(0f, 0f, a * Mathf.Rad2Deg), stoneL, false);
                }

            // 门洞内壁 + 地面 + 顶部压暗（假进深）
            Kit.Slab(t, "PassageFloor", new Vector3(openW, 0.14f, gateD + 0.9f), new Vector3(0f, 0.07f, 0f), StoneM("cobble"));
            Kit.Slab(t, "PassageCeil", new Vector3(openW, 0.2f, gateD), new Vector3(0f, openH - 0.12f, 0f), stoneD);
            for (int s = -1; s <= 1; s += 2)
                Kit.Slab(t, "PassageWall", new Vector3(0.18f, openH, gateD),
                    new Vector3(s * (openW * 0.5f + 0.09f), openH * 0.5f, 0f), stoneD);

            // 吊闸（半升起）：铁栅 + 尖刺
            for (int i = 0; i < 5; i++)
            {
                float bx = -0.9f + i * 0.45f;
                Kit.Box(t, "PortBar", new Vector3(0.07f, 2.5f, 0.07f), new Vector3(bx, openH - 1.25f, gateD * 0.5f + 0.08f), Iron(), 0f, false);
                Kit.ConeRot(t, "PortSpike", 0.09f, 0.28f, new Vector3(bx, openH - 2.62f, gateD * 0.5f + 0.08f),
                    Quaternion.Euler(180f, 0f, 0f), Iron(), 6);
            }
            for (int j = 0; j < 3; j++)
                Kit.Box(t, "PortRail", new Vector3(openW, 0.08f, 0.08f),
                    new Vector3(0f, openH - 0.35f - j * 0.85f, gateD * 0.5f + 0.08f), Iron(), 0f, false);

            // 敞开的木门（往内开）
            for (int s = -1; s <= 1; s += 2)
            {
                var doorPiv = Kit.Pivot(t, "GateDoor", new Vector3(s * openW * 0.5f, 0f, gateD * 0.5f), s * 62f);
                var dt = doorPiv.transform;
                Kit.Box(dt, "Leaf", new Vector3(openW * 0.5f, openH - 0.3f, 0.14f),
                    new Vector3(-s * openW * 0.25f, (openH - 0.3f) * 0.5f + 0.1f, 0f), woodDark, 0f, false);
                for (int b = 0; b < 4; b++)
                    Kit.Box(dt, "Band", new Vector3(openW * 0.5f, 0.1f, 0.05f),
                        new Vector3(-s * openW * 0.25f, 0.5f + b * 1.0f, 0.1f), Iron(), 0f, false);
            }

            // 门楼顶：走道 + 城垛
            Kit.Slab(t, "TopFloor", new Vector3(gateW + 0.2f, 0.3f, gateD + 0.2f), new Vector3(0f, gateH + 0.15f, 0f), stoneD);
            MerlonsX(t, "MerlonF", gateW - 0.4f, gateH + 0.75f, 0.42f, 0.6f, 1.0f, 5, stoneW);
            for (int i = 0; i < 5; i++)
            {
                float mx = -((gateW - 0.4f) * 0.5f) + i * ((gateW - 0.4f) / 4f);
                Kit.Box(t, "MerlonB", new Vector3(0.6f, 1.0f, 0.42f), new Vector3(mx, gateH + 0.75f, -gateD * 0.5f + 0.21f), stoneW, 0f, false);
            }
            // 门楼上的小窗/箭孔
            for (int i = 0; i < 3; i++)
                Kit.Box(t, "Slit", new Vector3(0.13f, 0.8f, 0.1f),
                    new Vector3(-1.5f + i * 1.5f, openH + 0.9f, gateD * 0.5f + 0.08f),
                    KitMat.Solid("kit_slit", KitPalette.Darken(MapMaterials.StoneDark, 0.5f)), 0f, false);

            // ---- 两侧圆塔 ----
            for (int s = -1; s <= 1; s += 2)
            {
                float tx = s * (gateW * 0.5f + 2.3f);
                float r = 2.3f;
                Kit.Cyl(t, "TowerBase", r + 0.28f, 1.5f, new Vector3(tx, 0.75f, 0f), stoneD, 12, false);
                Kit.Cyl(t, "TowerBody", r, 6.1f, new Vector3(tx, 1.5f + 3.05f, 0f), stoneW, 12, false);
                Kit.Cyl(t, "TowerBand1", r + 0.1f, 0.24f, new Vector3(tx, 4.2f, 0f), stoneL, 12, false);
                Kit.Cyl(t, "TowerBand2", r + 0.1f, 0.24f, new Vector3(tx, 7.0f, 0f), stoneL, 12, false);
                Kit.Cyl(t, "TowerCorbel", r + 0.3f, 0.34f, new Vector3(tx, 7.72f, 0f), stoneL, 12, false);
                Kit.Cyl(t, "TowerTop", r + 0.05f, 0.5f, new Vector3(tx, 8.1f, 0f), stoneW, 12, false);
                // 塔顶垛口
                for (int i = 0; i < 10; i++)
                {
                    float ang = i * 36f;
                    Vector3 d = KitMath.OnCircle(r + 0.05f, ang);
                    Kit.Box(t, "TowerMerlon", new Vector3(0.55f, 0.72f, 0.36f),
                        new Vector3(tx + d.x, 8.72f, d.z), stoneW, ang + 90f, false);
                }
                // 箭孔（朝外三个角度）
                for (int i = 0; i < 3; i++)
                {
                    float ang = (s > 0 ? 0f : 180f) + (i - 1) * 55f;
                    Vector3 d = KitMath.OnCircle(r + 0.02f, ang);
                    Kit.Box(t, "ArrowSlit", new Vector3(0.1f, 0.75f, 0.16f),
                        new Vector3(tx + d.x, 5.2f, d.z), KitMat.Solid("kit_slit", KitPalette.Darken(MapMaterials.StoneDark, 0.5f)), ang, false);
                }
                // 塔门（朝街道内侧）
                var tface = Facade(t, "TowerDoorFace", new Vector3(tx - s * (r + 0.02f), 0f, 0f), s > 0 ? 270f : 90f);
                Kit.Box(tface, "TowerDoor", new Vector3(0.95f, 1.95f, 0.14f), new Vector3(0f, 0.98f, 0.05f), woodDark, 0f, false);
                Kit.Box(tface, "TowerDoorLintel", new Vector3(1.25f, 0.2f, 0.24f), new Vector3(0f, 2.05f, 0.08f), stoneL, 0f, false);
                Kit.Box(tface, "TowerDoorStep", new Vector3(1.4f, 0.14f, 0.5f), new Vector3(0f, 0.07f, 0.3f), stoneD, 0f, false);
                // 塔顶旗帜
                KitProps.Banner(t, new Vector3(tx, 8.95f, 0f), s > 0 ? 12f : -12f, "cloth_blue", "gold");
                Kit.Blocker(t, "TowerBlocker", new Vector3(r * 2f, 8.3f, r * 2f), new Vector3(tx, 4.15f, 0f));
            }

            // ---- 门楼前的石阶/铺地 ----
            Kit.Slab(t, "Apron", new Vector3(gateW + 4.6f, 0.12f, 3.0f), new Vector3(0f, 0.06f, gateD * 0.5f + 1.5f), StoneM("cobble"));

            // ---- 两侧接墙 ----
            WallSegment(t, new Vector3(-(gateW * 0.5f + 2.3f + 2.3f + 1.9f), 0f, 0f), 0f, 3.8f, 5.2f);
            WallSegment(t, new Vector3(gateW * 0.5f + 2.3f + 2.3f + 1.9f, 0f, 0f), 0f, 3.8f, 5.2f);

            Kit.MakeFadeable(root, 0.2f);
            return root;
        }

        // ============================================================================================
        // 市集摊位
        // ============================================================================================
        /// <summary>
        /// 市集摊位：木柜台 + 四柱 + 两色交替布条遮阳棚（正反两面都出效果）+ 货品（果蔬/布卷/木箱）+
        /// 招牌 + 吊灯。awning 是主色 key（cloth_red/blue/green/...），另一色自动配米白。
        /// </summary>
        public static GameObject MarketStall(Transform parent, Vector3 pos, float yaw = 0f, string awning = "cloth_red")
        {
            var root = Kit.Pivot(parent, "MarketStall", pos, yaw);
            var t = root.transform;
            if (string.IsNullOrEmpty(awning)) awning = "cloth_red";
            string alt = awning == "cloth_cream" ? "cloth_red" : "cloth_cream";
            var clothA = KitMat.Cloth(awning);
            var clothB = KitMat.Cloth(alt);
            var wood = WoodM("wood_plank");
            var woodDark = WoodM("wood_dark");
            var timber = TimberM("timber_mid");

            const float W = 3.2f, D = 1.9f, postH = 2.35f;
            // 四柱
            for (int sx = -1; sx <= 1; sx += 2)
                for (int sz = -1; sz <= 1; sz += 2)
                {
                    Kit.Box(t, "Post", new Vector3(0.12f, postH, 0.12f),
                        new Vector3(sx * (W * 0.5f - 0.08f), postH * 0.5f, sz * (D * 0.5f - 0.08f)), timber, 0f, false);
                    Kit.Sphere(t, "PostFinial", 0.1f, new Vector3(sx * (W * 0.5f - 0.08f), postH + 0.06f, sz * (D * 0.5f - 0.08f)),
                        woodDark, false, 8);
                }
            // 布条遮阳棚：前后各铺一圈，中间高两边低（8° 斜角）
            const int strips = 6;
            float stripW = (W + 0.35f) / strips;
            float awnY = postH + 0.02f;
            for (int i = 0; i < strips; i++)
            {
                float sx = -(W + 0.35f) * 0.5f + stripW * (i + 0.5f);
                var m = (i % 2 == 0) ? clothA : clothB;
                TexSlabRot(t, "AwningStrip", new Vector3(stripW - 0.015f, 0.05f, D + 0.45f),
                    new Vector3(sx, awnY, 0.06f), Quaternion.Euler(8f, 0f, 0f), m);
                // 前沿垂布（两色交替，带一点锯齿感）
                TexSlabRot(t, "Valance", new Vector3(stripW - 0.02f, 0.3f, 0.035f),
                    new Vector3(sx, awnY - 0.17f, D * 0.5f + 0.5f), Quaternion.identity, m);
                TexSlabRot(t, "ValanceBack", new Vector3(stripW - 0.02f, 0.24f, 0.035f),
                    new Vector3(sx, awnY - 0.14f, -(D * 0.5f + 0.5f)), Quaternion.identity, m);
            }
            // 棚顶横梁
            for (int sz = -1; sz <= 1; sz += 2)
                Kit.Box(t, "Beam", new Vector3(W + 0.2f, 0.09f, 0.09f), new Vector3(0f, awnY, sz * (D * 0.5f - 0.05f)), timber, 0f, false);
            Kit.Box(t, "BeamCenter", new Vector3(0.09f, 0.09f, D + 0.2f), new Vector3(0f, awnY + 0.02f, 0f), timber, 0f, false);

            // 柜台
            Kit.Slab(t, "CounterTop", new Vector3(W - 0.35f, 0.12f, 0.8f), new Vector3(0f, 1.02f, 0.28f), wood);
            Kit.Box(t, "CounterFront", new Vector3(W - 0.35f, 0.9f, 0.1f), new Vector3(0f, 0.55f, 0.64f), woodDark, 0f, false);
            for (int i = 0; i < 5; i++)
                Kit.Box(t, "CounterRib", new Vector3(0.06f, 0.62f, 0.04f),
                    new Vector3(-(W - 0.5f) * 0.5f + i * ((W - 0.5f) / 4f), 0.55f, 0.7f), wood, 0f, false);
            // 斜置展板 + 后货架
            TexSlabRot(t, "Display", new Vector3(W - 0.5f, 0.06f, 0.55f), new Vector3(0f, 1.22f, 0.34f),
                Quaternion.Euler(-18f, 0f, 0f), wood);
            Kit.Box(t, "ShelfBack", new Vector3(W - 0.3f, 0.1f, 0.5f), new Vector3(0f, 1.55f, -0.5f), wood, 0f, false);
            for (int sx = -1; sx <= 1; sx += 2)
                Kit.Box(t, "ShelfLeg", new Vector3(0.08f, 0.55f, 0.08f), new Vector3(sx * (W * 0.5f - 0.25f), 1.3f, -0.5f), woodDark, 0f, false);

            // 货品：果蔬篮 ×2、木箱、布卷 ×3、面包
            for (int b = 0; b < 2; b++)
            {
                float bx = b == 0 ? -0.85f : 1.0f;
                float bz = 0.3f - b * 0.12f;
                Kit.Cyl(t, "Basket", 0.28f, 0.18f, new Vector3(bx, 1.15f, bz), woodDark, 12, false);
                var fruitMats = new[] {
                    KitMat.Solid("kit_fruit_red", MapMaterials.ClothRed * 0.9f),
                    KitMat.Solid("kit_fruit_org", MapMaterials.ClothOrange),
                    KitMat.Solid("kit_fruit_grn", MapMaterials.ClothGreen) };
                for (int f = 0; f < 6; f++)
                {
                    Vector3 d = KitMath.OnCircle(0.15f, f * 60f + b * 25f);
                    Kit.Sphere(t, "Fruit", 0.085f, new Vector3(bx + d.x, 1.25f + (f % 2) * 0.06f, bz + d.z),
                        fruitMats[(f + b) % 3], false, 7);
                }
            }
            KitProps.Crate(t, new Vector3(W * 0.5f - 0.45f, 1.08f, -0.15f), 8f, 0.42f);
            for (int i = 0; i < 3; i++)
            {
                var cm = KitMat.Cloth(i == 0 ? "cloth_purple" : (i == 1 ? "cloth_teal" : "cloth_orange"));
                Kit.CylRot(t, "ClothBolt", 0.1f, 0.5f, new Vector3(-W * 0.5f + 0.55f + i * 0.24f, 1.2f, -0.62f),
                    Quaternion.Euler(0f, 0f, 90f), cm, 10);
            }
            var breadMat = KitMat.Solid("kit_bread", MapMaterials.ClothOrange * 0.85f);
            for (int i = 0; i < 3; i++)
                Kit.Sphere(t, "Bread", new Vector3(0.34f, 0.2f, 0.22f), new Vector3(0.15f + i * 0.35f, 1.14f, 0.5f),
                    breadMat, false, 8);
            // 招牌 + 吊灯
            Kit.SignBoard(t, "市集", new Vector3(0f, 2.62f, D * 0.5f + 0.12f), 0f, 1.5f, 0.4f,
                MapMaterials.ClothCream, KitPalette.Ink);
            Kit.Box(t, "LampArm", new Vector3(0.05f, 0.05f, 0.42f), new Vector3(-W * 0.5f + 0.1f, postH - 0.12f, D * 0.5f - 0.1f), Iron(), 0f, false);
            Kit.Box(t, "LampGlow", new Vector3(0.16f, 0.2f, 0.16f), new Vector3(-W * 0.5f + 0.1f, postH - 0.3f, D * 0.5f + 0.3f),
                KitMat.Emi("kit_lamp_glow", MapMaterials.GlowWarm, 2.4f), 0f, false);

            Kit.Blocker(t, "Blocker", new Vector3(W + 0.2f, 2.4f, D + 0.2f), new Vector3(0f, 1.2f, 0f));
            return root;
        }

        // ============================================================================================
        // 喷泉
        // ============================================================================================
        /// <summary>广场喷泉：两级石盆 + 中心柱 + 上层水盘 + 青铜顶饰 + 水柱/水弧 + 睡莲。直径约 6m。</summary>
        public static GameObject Fountain(Transform parent, Vector3 pos)
        {
            var root = Kit.Pivot(parent, "Fountain", pos, 0f);
            var t = root.transform;
            var stoneW = StoneM("stone_wall");
            var stoneD = StoneM("stone_dark");
            var stoneL = StoneM("stone_light");
            var waterMat = MapMaterials.Get("water");
            var jetMat = KitMat.Transparent("kit_water_jet", MapMaterials.Water, 0.42f);

            // 台阶 + 池底
            Kit.Cyl(t, "Step1", 3.0f, 0.16f, new Vector3(0f, 0.08f, 0f), stoneL, 16, false);
            Kit.Cyl(t, "Step2", 2.75f, 0.14f, new Vector3(0f, 0.2f, 0f), stoneD, 16, false);
            Kit.Cyl(t, "BasinFloor", 2.55f, 0.12f, new Vector3(0f, 0.3f, 0f), stoneD, 16, false);
            // 池壁（外圈方块 + 压顶）
            RingOfBoxes(t, "BasinWall", 2.45f, 0.62f, 16, new Vector3(1.05f, 0.52f, 0.36f), stoneW);
            RingOfBoxes(t, "BasinRim", 2.45f, 0.9f, 16, new Vector3(1.12f, 0.14f, 0.5f), stoneL);
            // 水面
            Kit.Cyl(t, "Water", 2.3f, 0.12f, new Vector3(0f, 0.62f, 0f), waterMat, 24, false);

            // 中心柱 + 两层水盘
            Kit.Cyl(t, "Pedestal", 0.52f, 1.3f, new Vector3(0f, 1.28f, 0f), stoneL, 12, false);
            Kit.Cyl(t, "PedestalBase", 0.72f, 0.24f, new Vector3(0f, 0.72f, 0f), stoneD, 12, false);
            Kit.Cyl(t, "BowlBottom", 1.2f, 0.2f, new Vector3(0f, 1.98f, 0f), stoneL, 16, false);
            Kit.Cyl(t, "BowlWater", 1.05f, 0.08f, new Vector3(0f, 2.1f, 0f), waterMat, 16, false);
            Kit.Cyl(t, "Stem", 0.22f, 1.0f, new Vector3(0f, 2.6f, 0f), stoneL, 10, false);
            Kit.Cyl(t, "TopBowl", 0.62f, 0.18f, new Vector3(0f, 3.15f, 0f), stoneL, 12, false);
            Kit.Cyl(t, "TopWater", 0.5f, 0.07f, new Vector3(0f, 3.26f, 0f), waterMat, 12, false);
            Kit.Cyl(t, "Spout", 0.1f, 0.5f, new Vector3(0f, 3.5f, 0f), BronzeM(), 8, false);
            Kit.Sphere(t, "Finial", 0.22f, new Vector3(0f, 3.82f, 0f), BronzeM(), false, 10);
            Kit.ConeRot(t, "FinialSpike", 0.12f, 0.4f, new Vector3(0f, 4.12f, 0f), Quaternion.identity, BronzeM(), 6);

            // 水柱：上层水盘往下洒水弧 + 中心直喷
            for (int a = 0; a < 8; a++)
            {
                float ang = a * 45f;
                Vector3 d = KitMath.OnCircle(1.0f, ang);
                for (int k = 0; k < 4; k++)
                {
                    float u = k / 3f;
                    float rad = Mathf.Lerp(0.9f, 2.05f, u);
                    float y = Mathf.Lerp(2.05f, 0.7f, u * u);
                    Vector3 p = KitMath.OnCircle(rad, ang);
                    Kit.Sphere(t, "WaterArc", 0.1f, new Vector3(p.x, y, p.z), jetMat, false, 7);
                }
                Kit.Sphere(t, "WaterDrop", 0.07f, new Vector3(d.x * 2.2f, 0.73f, d.z * 2.2f), jetMat, false, 6);
            }
            for (int i = 0; i < 3; i++)
            {
                Vector3 d = KitMath.OnCircle(0.22f, i * 120f);
                Kit.Cyl(t, "Jet", 0.045f, 0.55f, new Vector3(d.x, 3.72f, d.z), jetMat, 6, false);
            }

            // 睡莲 + 岸边花
            var pad = MapMaterials.Get("foliage_dark");
            for (int i = 0; i < 5; i++)
            {
                Vector3 d = KitMath.OnCircle(1.35f + (i % 3) * 0.3f, i * 73f);
                Kit.Cyl(t, "LilyPad", 0.19f, 0.03f, new Vector3(d.x, 0.69f, d.z), pad, 9, false);
            }
            var flower = KitMat.Solid("kit_fountain_flower", new Color(0.94f, 0.68f, 0.78f), 0.3f);
            for (int i = 0; i < 3; i++)
            {
                Vector3 d = KitMath.OnCircle(1.6f, i * 120f + 20f);
                Kit.Sphere(t, "Bloom", 0.08f, new Vector3(d.x, 0.8f, d.z), flower, false, 7);
            }

            Kit.Blocker(t, "Blocker", new Vector3(5.0f, 1.0f, 5.0f), new Vector3(0f, 0.5f, 0f));
            return root;
        }

        // ============================================================================================
        // 水井
        // ============================================================================================
        /// <summary>石砌水井 + 木架小坡屋顶 + 绞盘/绳/木桶 + 周围小花。约 40 个 primitive。</summary>
        public static GameObject Well(Transform parent, Vector3 pos)
        {
            var root = Kit.Pivot(parent, "Well", pos, 0f);
            var t = root.transform;
            var stoneW = StoneM("stone_wall");
            var stoneD = StoneM("stone_dark");
            var stoneL = StoneM("stone_light");
            var wood = WoodM("wood_dark");
            var roofMat = RoofM("roof_thatch");

            Kit.Cyl(t, "Base", 1.15f, 0.16f, new Vector3(0f, 0.08f, 0f), stoneD, 12, false);
            RingOfBoxes(t, "WellWall", 0.9f, 0.5f, 10, new Vector3(0.62f, 0.72f, 0.3f), stoneW);
            RingOfBoxes(t, "WellRim", 0.9f, 0.9f, 10, new Vector3(0.7f, 0.14f, 0.42f), stoneL);
            Kit.Cyl(t, "WellWater", 0.72f, 0.08f, new Vector3(0f, 0.4f, 0f), MapMaterials.Get("water_deep"), 14, false);

            // 木架 + 屋顶
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Box(t, "Post", new Vector3(0.14f, 2.0f, 0.14f), new Vector3(s * 0.92f, 1.0f, 0f), wood, 0f, false);
                Kit.Box(t, "PostBrace", new Vector3(0.1f, 0.1f, 0.72f), new Vector3(s * 0.92f, 1.9f, 0f), wood, 0f, false);
            }
            Kit.Mesh(t, "WellRoof", Kit.GableRoofMesh(2.35f, 1.35f, 0.55f, 0.16f), new Vector3(0f, 2.02f, 0f), roofMat, false);
            Kit.Box(t, "WellRidge", new Vector3(2.5f, 0.1f, 0.16f), new Vector3(0f, 2.56f, 0f),
                KitMat.Solid("kit_ridge_thatch", KitPalette.Darken(MapMaterials.RoofThatch, 0.4f), 0.3f), 0f, false);
            // 绞盘 + 绳 + 桶
            Kit.CylRot(t, "Axle", 0.07f, 1.7f, new Vector3(0f, 1.75f, 0f), Quaternion.Euler(0f, 0f, 90f), wood, 8);
            Kit.Box(t, "Crank", new Vector3(0.06f, 0.46f, 0.06f), new Vector3(0.98f, 1.56f, 0f), Iron(), 0f, false);
            Kit.Sphere(t, "CrankKnob", 0.07f, new Vector3(0.98f, 1.34f, 0f), wood, false, 8);
            Kit.Cyl(t, "Rope", 0.022f, 0.72f, new Vector3(0.12f, 1.2f, 0f), KitMat.Solid("kit_rope", KitPalette.Darken(MapMaterials.ClothCream, 0.45f), 0.4f), 6, false);
            Kit.Cyl(t, "Bucket", 0.17f, 0.26f, new Vector3(0.12f, 0.68f, 0f), wood, 10, false);
            Kit.Cyl(t, "BucketHoop", 0.18f, 0.04f, new Vector3(0.12f, 0.72f, 0f), Iron(), 10, false);

            // 井边小石与花
            Kit.Sphere(t, "Stone1", new Vector3(0.42f, 0.18f, 0.3f), new Vector3(0.55f, 0.1f, 0.9f), stoneL, false, 7);
            KitProps.Flowers(t, new Vector3(-0.45f, 0f, 0.85f), MapMaterials.ClothOrange);
            Kit.Blocker(t, "Blocker", new Vector3(2.2f, 1.2f, 2.2f), new Vector3(0f, 0.6f, 0f));
            return root;
        }

        // ============================================================================================
        // 冒险者协会委托板
        // ============================================================================================
        /// <summary>委托板：双柱 + 木板面 + 小坡顶 + 钉着的委托纸 + 顶部招牌。正面 = 本地 +Z。</summary>
        public static GameObject QuestBoard(Transform parent, Vector3 pos, float yaw = 0f)
        {
            var root = Kit.Pivot(parent, "QuestBoard", pos, yaw);
            var t = root.transform;
            var wood = WoodM("wood_plank");
            var woodDark = WoodM("wood_dark");
            var timber = TimberM("timber_dark");
            var roofMat = RoofM("roof_terracotta");

            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Box(t, "Post", new Vector3(0.16f, 2.7f, 0.16f), new Vector3(s * 1.05f, 1.35f, 0f), woodDark, 0f, false);
                Kit.Box(t, "PostCap", new Vector3(0.24f, 0.1f, 0.24f), new Vector3(s * 1.05f, 2.72f, 0f), wood, 0f, false);
            }
            Kit.Slab(t, "Board", new Vector3(2.4f, 1.4f, 0.1f), new Vector3(0f, 1.75f, 0.06f), wood);
            Kit.Box(t, "FrameT", new Vector3(2.7f, 0.14f, 0.12f), new Vector3(0f, 2.5f, 0.07f), timber, 0f, false);
            Kit.Box(t, "FrameB", new Vector3(2.7f, 0.14f, 0.12f), new Vector3(0f, 1.0f, 0.07f), timber, 0f, false);
            for (int s = -1; s <= 1; s += 2)
                Kit.Box(t, "FrameSide", new Vector3(0.14f, 1.6f, 0.12f), new Vector3(s * 1.28f, 1.75f, 0.07f), timber, 0f, false);

            // 小坡屋顶
            Kit.Mesh(t, "BoardRoof", Kit.GableRoofMesh(2.9f, 1.0f, 0.5f, 0.22f), new Vector3(0f, 2.62f, 0f), roofMat, false);
            Kit.Box(t, "BoardRidge", new Vector3(3.0f, 0.1f, 0.14f), new Vector3(0f, 3.15f, 0f),
                KitMat.Solid("kit_ridge_dark", KitPalette.Darken(MapMaterials.RoofTerracotta, 0.55f), 0.22f), 0f, false);

            // 钉着的委托纸（米白 + 红漆封印）
            var rnd = new KitRand(KitRand.SeedFrom(pos, 4242));
            var paper = KitMat.Solid("kit_paper", MapMaterials.ClothCream, 0.3f);
            var seal = KitMat.Solid("kit_seal_wax", MapMaterials.ClothRed, 0.35f);
            for (int i = 0; i < 6; i++)
            {
                float px = -0.9f + (i % 3) * 0.9f;
                float py = 2.18f - (i / 3) * 0.78f;
                float rot = rnd.Range(-7f, 7f);
                Kit.BoxRot(t, "Paper", new Vector3(0.42f, 0.52f, 0.02f), new Vector3(px, py, 0.14f),
                    Quaternion.Euler(0f, 0f, rot), paper, false);
                Kit.Sphere(t, "WaxSeal", 0.055f, new Vector3(px + 0.1f, py - 0.12f, 0.16f), seal, false, 7);
            }
            Kit.SignText(t, "委托", new Vector3(0f, 2.3f, 0.2f), 0f, KitPalette.Ink, 1.4f, 0.3f);

            // 顶部招牌 + 吊灯
            Kit.SignBoard(t, "冒险者委托", new Vector3(0f, 3.05f, 0.1f), 0f, 1.9f, 0.38f,
                MapMaterials.ClothCream, KitPalette.Ink);
            Kit.Box(t, "LampArm", new Vector3(0.05f, 0.05f, 0.34f), new Vector3(1.2f, 2.4f, 0.12f), Iron(), 0f, false);
            Kit.Box(t, "LampGlow", new Vector3(0.18f, 0.22f, 0.18f), new Vector3(1.2f, 2.16f, 0.42f),
                KitMat.Emi("kit_lamp_glow", MapMaterials.GlowWarm, 2.4f), 0f, false);
            Kit.Box(t, "LampTop", new Vector3(0.24f, 0.05f, 0.24f), new Vector3(1.2f, 2.3f, 0.42f), Iron(), 0f, false);

            Kit.Blocker(t, "Blocker", new Vector3(2.8f, 2.7f, 0.6f), new Vector3(0f, 1.4f, 0f));
            return root;
        }
    }
}
