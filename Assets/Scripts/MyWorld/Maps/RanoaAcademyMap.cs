using System.Collections.Generic;
using UnityEngine;

namespace MyWorld.Maps
{
    /// <summary>
    /// 拉诺亚魔法学园（Ranoa Magic Academy）——拉诺亚王国的魔法学校，主角青年期就读。
    ///
    /// 构图意图与布耶纳村刻意相反：村子是土。茅草/木头/歪斜；学园是**对称的石造校。*。
    ///   南侧门楼（双。+ 拱门 + 匾额）→ 石板大道（中央大理石条）两侧柱廊拱门
    ///   。中庭：喷泉、雕像、紫罗兰魔法阵与悬浮水晶、修剪花。
    ///   。北端石造学院主楼（两层 + 门廊列柱 + 山墙 + 屋顶水晶。
    ///   主楼两翼各一。wizard 魔法塔（符文 + 悬浮水晶 + 紫光）、西侧图书馆（穹顶）。
    ///   东侧宿舍排屋（六门通廊 + 二层柱廊）、东边门通往布耶纳村。
    /// 所有几何都是原。primitive 拼装，没有复用村子的任何布局。
    /// 约定：建筑先。root/Visual 下建视觉 。Kit.Optimize(visual,false) 。再加招牌 / 。/ 本地空间 Blocker。
    /// （用本地 Blocker 而不。Optimize(root,true)：后者写进本。size 的是世界 AABB，一转角度就横竖颠倒。）
    /// </summary>
    public class RanoaAcademyMap : MapBootstrap
    {
        // ==================== 布局常量（地。120×120，内容压。±53 内）====================
        const float GateZ = -44f;        // 南门。
        const float AvenueZ = -10f;      // 大道中心
        const float HallZ = 24f;         // 主楼
        const float TowerZ = 26f;        // 魔法。
        const float LibraryX = -30f;     // 图书。
        const float DormX = 30f;         // 宿舍排屋
        const float EastGateX = 45f;     // 东边门（去布耶纳村）

        Transform _w;
        readonly Dictionary<string, Material> _mats = new Dictionary<string, Material>();
        System.Random _rng = new System.Random(20261019);

        Material M(string key)
        {
            Material m;
            if (!_mats.TryGetValue(key, out m)) { m = MapMaterials.Get(key); _mats[key] = m; }
            return m;
        }

        float R(float a, float b) { return a + (float)_rng.NextDouble() * (b - a); }
        // Kit.SignBoard        泯     -Z    ͼʵ    ֤        ͳһ +180 㣬
        //          泯   ÷      +Z     ɶ         Ҵ    濴     Ǿ    ֣   
        static void Sign(Transform parent, string text, Vector3 pos, float yaw, float width = 1.2f,
            float height = 0.5f, Color? bg = null, Color? fg = null)
        {
            Kit.SignBoard(parent, text, pos, yaw + 180f, width, height, bg, fg);
        }

        // ====================================================================================
        // 环境：修剪草。+ 石板铺装 + 学园院墙 + 院内树列
        // ====================================================================================
        protected override void BuildEnvironment(Transform world)
        {
            _w = world;

            var ground = new GameObject("Ground").transform;
            ground.SetParent(world, false);
            Kit.Box(ground, "Lawn", new Vector3(GroundSize, 1f, GroundSize), new Vector3(0f, -0.5f, 0f), M("grass"), 0f, true);

            var pave = new GameObject("Paving").transform;
            pave.SetParent(world, false);
            Pave(pave, "GatePlaza", new Vector3(0f, 0f, -38f), 42f, 15f, "cobble");
            Pave(pave, "Avenue", new Vector3(0f, 0f, AvenueZ), 13f, 54f, "cobble");
            Pave(pave, "HallForecourt", new Vector3(0f, 0f, 8f), 46f, 18f, "cobble");
            Pave(pave, "WestCourt", new Vector3(-16f, 0f, -18f), 14f, 26f, "cobble");
            Pave(pave, "DormWalk", new Vector3(19f, 0f, -18f), 10f, 40f, "cobble");
            Pave(pave, "EastPath", new Vector3(31f, 0f, -6f), 26f, 7f, "cobble");
            // 大道镶边 + 中央大理石条（学园的中轴。
            Kit.Slab(pave, "AvenueMarble", new Vector3(3.6f, 0.1f, 54f), new Vector3(0f, 0.075f, AvenueZ), M("marble"));
            Kit.Slab(pave, "AvenueEdgeW", new Vector3(0.7f, 0.1f, 54f), new Vector3(-6.3f, 0.07f, AvenueZ), M("marble"));
            Kit.Slab(pave, "AvenueEdgeE", new Vector3(0.7f, 0.1f, 54f), new Vector3(6.3f, 0.07f, AvenueZ), M("marble"));
            Kit.Slab(pave, "PlazaMarble", new Vector3(42f, 0.1f, 1.1f), new Vector3(0f, 0.075f, -31.4f), M("marble"));

            // 院墙（比村子的高。 内侧扶壁
            BuildBoundary(world, 5.0f);
            var wall = new GameObject("WallButtress").transform;
            wall.SetParent(world, false);
            for (int i = -4; i <= 4; i++)
            {
                float x = i * 12f;
                if (Mathf.Abs(x) < 13f) continue;            // 给南门楼留口
                Kit.Box(wall, "ButtressS", new Vector3(1.7f, 6.2f, 1.7f), new Vector3(x, 3.1f, -58.4f), M("stone_wall"), 0f, false);
                Kit.Box(wall, "CapS", new Vector3(2.1f, 0.5f, 2.1f), new Vector3(x, 6.4f, -58.4f), M("stone_dark"), 0f, false);
            }
            for (int i = -4; i <= 4; i++)
            {
                float z = i * 12f;
                if (Mathf.Abs(z + 6f) < 9f) continue;        // 给东边门留口
                Kit.Box(wall, "ButtressE", new Vector3(1.7f, 6.2f, 1.7f), new Vector3(58.4f, 3.1f, z), M("stone_wall"), 0f, false);
                Kit.Box(wall, "CapE", new Vector3(2.1f, 0.5f, 2.1f), new Vector3(58.4f, 6.4f, z), M("stone_dark"), 0f, false);
            }

            // 院内树列（修剪过的行道树，区别于村外的野林）
            var trees = new GameObject("Trees").transform;
            trees.SetParent(world, false);
            for (int i = 0; i < 44; i++)
            {
                float a = i * (360f / 44f) + 4f;
                float rr = R(47f, 53f);
                var p = new Vector3(Mathf.Sin(a * Mathf.Deg2Rad) * rr, 0f, Mathf.Cos(a * Mathf.Deg2Rad) * rr);
                if (Mathf.Abs(p.x) < 14f && p.z < -36f) continue;              // 南门
                if (p.x > 38f && Mathf.Abs(p.z + 6f) < 8f) continue;           // 东边。
                if (i % 3 == 0) RoaKit.Pine(trees, p, R(1.0f, 1.35f));
                else RoaKit.Tree(trees, p, R(0.95f, 1.3f), i % 7 == 0);
            }
            // 门楼两侧的柏。
            for (int s = -1; s <= 1; s += 2)
                for (int i = 0; i < 3; i++)
                    RoaKit.Pine(trees, new Vector3(s * (14f + i * 4.5f), 0f, -40f), 1.10f + i * 0.06f);
        }

        void Pave(Transform parent, string name, Vector3 c, float w, float d, string mat)
        {
            Kit.Slab(parent, name, new Vector3(w, 0.09f, d), new Vector3(c.x, 0.05f, c.z), M(mat));
        }

        // ====================================================================================
        // 地图内容
        // ====================================================================================
        protected override void BuildMapContent(Transform world)
        {
            _w = world;

            BuildGatehouse(world);
            BuildColonnades(world);
            BuildCourtyard(world);
            BuildMainHall(world);
            BuildWizardTowers(world);
            BuildLibrary(world);
            BuildDormitory(world);
            BuildMagicShop(world);
            BuildTrainingYard(world);
            BuildEastGate(world);
            BuildObservatory(world);     // 第二地标：观星塔
            BuildCanteen(world);         // 学生食堂（可购买。
            BuildGreenhouse(world);      // 温室药圃
            BuildGuestHouse(world);      // 访客驿站 / 据点（可购买。
            BuildStudentMarket(world);   // 旧书。+ 炼金。+ 告示。
            BuildCampusLife(world);      // 路灯 / 挂旗 / 晾衣。/ 货堆
            BuildInteractables(world);
            BuildPeople(world);
            BuildSpawns();
        }

        // ------------------------------------------------------------------ 通用石构。
        /// <summary>一根石柱：柱础 + 柱身 + 柱头。/summary>
        void Column(Transform parent, Vector3 pos, float h, float r, Material stone, Material trim)
        {
            Kit.Box(parent, "Base", new Vector3(r * 2.7f, 0.34f, r * 2.7f), pos + new Vector3(0f, 0.17f, 0f), trim, 0f, false);
            Kit.Cyl(parent, "Shaft", r, h - 0.7f, pos + new Vector3(0f, 0.34f + (h - 0.7f) * 0.5f, 0f), stone, 12, false);
            Kit.Box(parent, "Cap", new Vector3(r * 2.9f, 0.36f, r * 2.9f), pos + new Vector3(0f, h - 0.18f, 0f), trim, 0f, false);
        }

        /// <summary>一个柱廊开间：两柱 + 半圆拱（7 块楔石）+ 檐口。width 沿本。X，正面朝本地 +Z。/summary>
        void ArchBay(Transform parent, Vector3 pos, float yaw, float width, float height, Material stone, Material trim)
        {
            var root = new GameObject("ArchBay").transform;
            root.SetParent(parent, false);
            root.localPosition = pos;
            root.localRotation = Quaternion.Euler(0f, yaw, 0f);

            float hw = width * 0.5f;
            Column(root, new Vector3(-hw, 0f, 0f), height, 0.42f, stone, trim);
            Column(root, new Vector3(hw, 0f, 0f), height, 0.42f, stone, trim);

            int n = 7;
            float chord = Mathf.PI * hw / n;
            for (int i = 0; i < n; i++)
            {
                float a = Mathf.Lerp(7f, 173f, (i + 0.5f) / n);
                float rad = a * Mathf.Deg2Rad;
                var p = new Vector3(-Mathf.Cos(rad) * hw, height + Mathf.Sin(rad) * hw, 0f);
                Kit.BoxRot(root, "Voussoir" + i, new Vector3(0.62f, chord * 1.35f, 0.92f), p,
                    Quaternion.Euler(0f, 0f, 180f - a), stone, false);
            }
            // 拱肩填角 + 檐口
            Kit.Box(root, "SpandrelL", new Vector3(hw * 0.42f, 0.5f, 0.9f), new Vector3(-hw * 0.84f, height + 0.16f, 0f), stone, 0f, false);
            Kit.Box(root, "SpandrelR", new Vector3(hw * 0.42f, 0.5f, 0.9f), new Vector3(hw * 0.84f, height + 0.16f, 0f), stone, 0f, false);
            Kit.Box(root, "ArchCornice", new Vector3(width + 1.5f, 0.36f, 1.15f), new Vector3(0f, height + hw + 0.34f, 0f), trim, 0f, false);
        }

        /// <summary>拱窗：窗。+ 玻璃 + 边框 + 顶部楔石。+ 中挺。pos 是墙面上窗中心的本地坐标，正面朝本地 +Z。/summary>
        void ArchedWindow(Transform parent, Vector3 pos, float yaw, float w, float h, Material frame, Material pane)
        {
            var root = new GameObject("Window").transform;
            root.SetParent(parent, false);
            root.localPosition = pos;
            root.localRotation = Quaternion.Euler(0f, yaw, 0f);

            float hw = w * 0.5f;
            float straight = h - hw;
            Kit.Box(root, "Pane", new Vector3(w, h * 0.95f, 0.1f), new Vector3(0f, -0.15f, 0.05f), pane, 0f, false);
            Kit.Box(root, "Sill", new Vector3(w + 0.7f, 0.24f, 0.45f), new Vector3(0f, -h * 0.5f - 0.1f, 0.12f), frame, 0f, false);
            Kit.Box(root, "JambL", new Vector3(0.24f, straight + 0.3f, 0.34f), new Vector3(-hw - 0.12f, -h * 0.15f, 0.09f), frame, 0f, false);
            Kit.Box(root, "JambR", new Vector3(0.24f, straight + 0.3f, 0.34f), new Vector3(hw + 0.12f, -h * 0.15f, 0.09f), frame, 0f, false);
            int n = 5;
            for (int i = 0; i < n; i++)
            {
                float a = Mathf.Lerp(10f, 170f, (i + 0.5f) / n);
                float rad = a * Mathf.Deg2Rad;
                var p = new Vector3(-Mathf.Cos(rad) * hw, straight * 0.5f + Mathf.Sin(rad) * hw, 0f);
                Kit.BoxRot(root, "Arch" + i, new Vector3(0.34f, Mathf.PI * hw / n * 1.4f, 0.36f), p,
                    Quaternion.Euler(0f, 0f, 180f - a), frame, false);
            }
            Kit.Box(root, "Mullion", new Vector3(0.13f, h * 0.9f, 0.18f), new Vector3(0f, -0.25f, 0.11f), frame, 0f, false);
            Kit.Box(root, "Transom", new Vector3(w, 0.13f, 0.18f), new Vector3(0f, h * 0.06f, 0.11f), frame, 0f, false);
        }

        /// <summary>三级石阶。pos 是最下面一级前缘中心的本地坐标，向本地 -Z 收。/summary>
        void StairFlight(Transform parent, Vector3 pos, float width, Material mat)
        {
            for (int i = 0; i < 3; i++)
            {
                float h = 0.5f - i * 0.16f;
                Kit.Box(parent, "Step" + i, new Vector3(width - i * 1.2f, h, 0.95f),
                    pos + new Vector3(0f, h * 0.5f, i * 0.95f), mat, 0f, false);
            }
        }

        // ------------------------------------------------------------------ 南门。
        void BuildGatehouse(Transform world)
        {
            var root = new GameObject("Gatehouse").transform;
            root.SetParent(world, false);
            root.localPosition = new Vector3(0f, 0f, GateZ);
            var v = new GameObject("Visual").transform;
            v.SetParent(root, false);

            // 两根门柱（中。9m 净宽可以走人）
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Box(v, "Pier", new Vector3(3.4f, 8.4f, 3.4f), new Vector3(s * 6f, 4.2f, 0f), M("stone_light"), 0f, false);
                Kit.Box(v, "PierBase", new Vector3(4.0f, 0.7f, 4.0f), new Vector3(s * 6f, 0.35f, 0f), M("stone_dark"), 0f, false);
                Kit.Box(v, "PierCap", new Vector3(4.2f, 0.6f, 4.2f), new Vector3(s * 6f, 8.6f, 0f), M("stone_dark"), 0f, false);
                // 侧面壁龛里的。
                Kit.Box(v, "Niche", new Vector3(0.5f, 2.0f, 1.2f), new Vector3(s * 4.2f, 4.6f, 0f), M("stone_dark"), 0f, false);
            }
            // 门楣 + 山墙屋顶
            Kit.Box(v, "Lintel", new Vector3(15.6f, 1.6f, 3.2f), new Vector3(0f, 9.7f, 0f), M("stone_wall"), 0f, false);
            Kit.MeshRot(v, "GateRoof", Kit.GableRoofMesh(15.8f, 4.4f, 2.3f, 0.45f, 0.3f), new Vector3(0f, 10.5f, 0f),
                Quaternion.Euler(0f, 90f, 0f), M("roof_slate"), false);
            // 拱腹（门洞上方的弧形装饰。
            for (int i = 0; i < 7; i++)
            {
                float a = Mathf.Lerp(12f, 168f, (i + 0.5f) / 7f);
                float rad = a * Mathf.Deg2Rad;
                var p = new Vector3(-Mathf.Cos(rad) * 4.6f, 7.2f + Mathf.Sin(rad) * 0.9f, 1.62f);
                Kit.BoxRot(v, "GateArch" + i, new Vector3(0.4f, 1.25f, 0.4f), p, Quaternion.Euler(0f, 0f, 180f - a), M("stone_dark"), false);
            }
            // 铁栅栏（半开。
            for (int i = 0; i < 5; i++)
                Kit.Cyl(v, "Bar", 0.09f, 6.4f, new Vector3(-3.2f + i * 1.6f, 3.2f, -0.9f), M("iron"), 6, false);
            Kit.Box(v, "BarRail", new Vector3(8.0f, 0.22f, 0.26f), new Vector3(0f, 5.4f, -0.9f), M("iron"), 0f, false);

            // 双塔
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Cyl(v, "TowerShaft", 2.7f, 11.4f, new Vector3(s * 9.6f, 5.7f, 1.2f), M("stone_wall"), 14, false);
                Kit.Cyl(v, "TowerBand", 2.95f, 0.6f, new Vector3(s * 9.6f, 9.2f, 1.2f), M("stone_dark"), 14, false);
                Kit.Cyl(v, "TowerTop", 3.15f, 0.7f, new Vector3(s * 9.6f, 11.6f, 1.2f), M("stone_dark"), 14, false);
                Kit.Cone(v, "TowerRoof", 3.5f, 3.8f, new Vector3(s * 9.6f, 13.85f, 1.2f), M("roof_teal"), 14, false);
                Kit.Cyl(v, "Finial", 0.22f, 0.9f, new Vector3(s * 9.6f, 16.1f, 1.2f), M("gold"), 8, false);
                // 塔身箭窗
                for (int k = 0; k < 2; k++)
                    ArchedWindow(v, new Vector3(s * 9.6f, 5.4f + k * 3.2f, 3.85f), 0f, 0.9f, 1.7f, M("stone_dark"), M("glow_amber"));
            }
            Kit.Optimize(v.gameObject, false);

            // 匾额（合并之后再加）
            Sign(root, "拉诺亚魔法学园", new Vector3(0f, 9.6f, 1.75f), 0f, 8.2f, 1.15f);
            Sign(root, "王立 · 魔导学部", new Vector3(0f, 7.9f, 1.7f), 0f, 4.6f, 0.55f, M("stone_dark").color, M("marble").color);

            // 门两侧的紫旗 + 。
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Slab(root, "BannerRod", new Vector3(0.12f, 0.12f, 2.6f), new Vector3(s * 5.9f, 8.4f, 1.5f), M("iron"));
                Kit.Slab(root, "Banner", new Vector3(2.1f, 4.0f, 0.1f), new Vector3(s * 5.9f, 6.3f, 1.6f), M("cloth_purple"));
                Kit.PointLight(root, new Vector3(s * 4.2f, 4.8f, 1.9f), new Color(0.72f, 0.66f, 1f), 11f, 1.35f);
            }
            Kit.PointLight(root, new Vector3(0f, 7.4f, 2.2f), new Color(0.85f, 0.78f, 1f), 14f, 1.1f);

            // 碰撞：门柱、塔、门楣（本地空间 。任意角度都对。
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Blocker(root, "PierBlocker", new Vector3(3.6f, 9.0f, 3.6f), new Vector3(s * 6f, 4.5f, 0f));
                Kit.Blocker(root, "TowerBlocker", new Vector3(6.0f, 11.6f, 6.0f), new Vector3(s * 9.6f, 5.8f, 1.2f));
            }
            Kit.MakeFadeable(root.gameObject, 0.3f);
        }

        // ------------------------------------------------------------------ 大道柱廊
        void BuildColonnades(Transform world)
        {
            Colonnade(world, -8.6f, false);
            Colonnade(world, 8.6f, true);
        }

        void Colonnade(Transform world, float x, bool east)
        {
            var root = new GameObject(east ? "ColonnadeEast" : "ColonnadeWest").transform;
            root.SetParent(world, false);
            root.localPosition = new Vector3(x, 0f, -34f);

            const int Bays = 7;
            const float BayW = 5.2f;
            const float ColH = 4.8f;
            float len = BayW * Bays;
            float hw = BayW * 0.5f;

            for (int i = 0; i < Bays; i++)
                ArchBay(root, new Vector3(0f, 0f, BayW * (i + 0.5f)), 90f, BayW, ColH, M("stone_light"), M("marble"));

            Kit.Box(root, "Entablature", new Vector3(1.5f, 0.75f, len + 0.6f),
                new Vector3(0f, ColH + hw + 0.9f, len * 0.5f), M("stone_dark"), 0f, false);
            Kit.Slab(root, "ColonnadeRoof", new Vector3(2.7f, 0.36f, len + 1.4f),
                new Vector3(0f, ColH + hw + 1.45f, len * 0.5f), M("roof_slate"));
            Kit.Optimize(root.gameObject, false);

            for (int i = 0; i < Bays; i++)
            {
                float z = BayW * (i + 0.5f);
                Kit.Blocker(root, "ColBlockerL", new Vector3(0.95f, ColH, 0.95f), new Vector3(-hw, ColH * 0.5f, z));
                Kit.Blocker(root, "ColBlockerR", new Vector3(0.95f, ColH, 0.95f), new Vector3(hw, ColH * 0.5f, z));
            }
            Kit.MakeFadeable(root.gameObject, 0.34f);
        }

        // ------------------------------------------------------------------ 中庭
        void BuildCourtyard(Transform world)
        {
            var court = new GameObject("Courtyard").transform;
            court.SetParent(world, false);

            // 魔法阵（紫罗兰）：中庭正中的圆形石台
            RoaKit.RuneCircle(court, new Vector3(0f, 0f, -12f), true);
            Kit.Blocker(court, "RuneCurb", new Vector3(8.4f, 0.3f, 8.4f), new Vector3(0f, 0.15f, -12f));

            // 喷泉 + 雕像
            RoaKit.Fountain(court, new Vector3(0f, 0f, -26f));
            RoaKit.Statue(court, new Vector3(0f, 0f, 5f), 180f);

            // 西侧两片修剪花园
            Parterre(court, new Vector3(-16f, 0f, -26f), 11f, 8f);
            Parterre(court, new Vector3(-16f, 0f, -10f), 11f, 8f);

            // 绿篱（大道两侧，规整排列。
            for (int s = -1; s <= 1; s += 2)
                for (int i = 0; i < 6; i++)
                    RoaKit.Bush(court, new Vector3(s * 10.7f, 0f, -33f + i * 6f), 1.25f);

            // 魔法水晶灯（柱子 + 悬浮水晶 + 紫光。
            CrystalLamp(court, new Vector3(-5.4f, 0f, -16.5f));
            CrystalLamp(court, new Vector3(5.4f, 0f, -16.5f));
            CrystalLamp(court, new Vector3(-5.4f, 0f, -7.5f));
            CrystalLamp(court, new Vector3(5.4f, 0f, -7.5f));
            CrystalLamp(court, new Vector3(-6.4f, 0f, -30f));
            CrystalLamp(court, new Vector3(6.4f, 0f, -30f));

            // 主楼台阶两侧的柏。
            for (int s = -1; s <= 1; s += 2)
            {
                RoaKit.Pine(court, new Vector3(s * 10f, 0f, 8f), 1.25f);
                RoaKit.Pine(court, new Vector3(s * 13f, 0f, 10.5f), 1.1f);
            }

            // 中庭长凳 + 花坛
            RoaKit.Bench(court, new Vector3(-4.6f, 0f, -32f), 0f, 2.2f);
            RoaKit.Bench(court, new Vector3(4.6f, 0f, -32f), 0f, 2.2f);
            RoaKit.Bench(court, new Vector3(-9.5f, 0f, -12f), 90f, 1.8f);
            RoaKit.Bench(court, new Vector3(9.5f, 0f, -12f), -90f, 1.8f);
            Color[] cols = { MapMaterials.ClothPurple, MapMaterials.PlasterWhite, MapMaterials.ClothTeal };
            for (int i = 0; i < 18; i++)
            {
                var p = new Vector3(R(-20f, 20f), 0f, R(-33f, 4f));
                if (Mathf.Abs(p.x) < 7.5f) continue;
                RoaKit.Flowers(court, p, cols[i % cols.Length]);
            }
        }

        void CrystalLamp(Transform parent, Vector3 pos)
        {
            var root = new GameObject("CrystalLamp").transform;
            root.SetParent(parent, false);
            root.localPosition = pos;
            Kit.Cyl(root, "Post", 0.22f, 3.3f, new Vector3(0f, 1.65f, 0f), M("stone_light"), 10, false);
            Kit.Box(root, "Base", new Vector3(0.9f, 0.36f, 0.9f), new Vector3(0f, 0.18f, 0f), M("stone_dark"), 0f, false);
            Kit.Box(root, "Head", new Vector3(1.0f, 0.3f, 1.0f), new Vector3(0f, 3.4f, 0f), M("stone_dark"), 0f, false);
            var crystal = Kit.BoxRot(root, "Crystal", new Vector3(0.5f, 0.9f, 0.5f), new Vector3(0f, 4.0f, 0f),
                Quaternion.Euler(45f, 45f, 0f), M("glow_cyan"), false);
            crystal.AddComponent<KitSpin>().DegreesPerSecond = 26f;
            var bob = crystal.AddComponent<KitBob>();
            bob.Amplitude = 0.07f;
            bob.Speed = 1.1f;
            Kit.PointLight(root, new Vector3(0f, 4.0f, 0f), new Color(0.62f, 0.86f, 1f), 9f, 1.25f);
            // 不能在这。Optimize：合并会销毁带 MeshRenderer 的物体，悬浮水晶（挂着 KitSpin/KitBob）也会一起没
            Kit.Blocker(root, "PostBlocker", new Vector3(0.6f, 3.4f, 0.6f), new Vector3(0f, 1.7f, 0f));
        }

        void Parterre(Transform parent, Vector3 c, float w, float d)
        {
            var root = new GameObject("Parterre").transform;
            root.SetParent(parent, false);
            root.localPosition = c;

            Kit.Slab(root, "Lawn", new Vector3(w, 0.16f, d), new Vector3(0f, 0.09f, 0f), M("grass_dark"));
            Kit.Slab(root, "CurbN", new Vector3(w + 0.7f, 0.34f, 0.55f), new Vector3(0f, 0.17f, d * 0.5f + 0.2f), M("marble"));
            Kit.Slab(root, "CurbS", new Vector3(w + 0.7f, 0.34f, 0.55f), new Vector3(0f, 0.17f, -d * 0.5f - 0.2f), M("marble"));
            Kit.Slab(root, "CurbW", new Vector3(0.55f, 0.34f, d + 0.7f), new Vector3(-w * 0.5f - 0.2f, 0.17f, 0f), M("marble"));
            Kit.Slab(root, "CurbE", new Vector3(0.55f, 0.34f, d + 0.7f), new Vector3(w * 0.5f + 0.2f, 0.17f, 0f), M("marble"));

            for (int i = 0; i < 4; i++)
            {
                float sx = (i % 2 == 0) ? -1f : 1f;
                float sz = (i < 2) ? -1f : 1f;
                RoaKit.Bush(root, new Vector3(sx * (w * 0.5f - 1.6f), 0f, sz * (d * 0.5f - 1.4f)), 1.15f);
            }
            for (int i = 0; i < 8; i++)
            {
                Color col = (i % 2 == 0) ? MapMaterials.ClothPurple : MapMaterials.PlasterWhite;
                RoaKit.Flowers(root, new Vector3(R(-w * 0.4f, w * 0.4f), 0f, R(-d * 0.4f, d * 0.4f)), col);
            }
            Kit.Cyl(root, "Sundial", 0.28f, 1.2f, new Vector3(0f, 0.6f, 0f), M("marble"), 10, false);
        }

        // ------------------------------------------------------------------ 学院主楼
        void BuildMainHall(Transform world)
        {
            var root = new GameObject("MainHall").transform;
            root.SetParent(world, false);
            root.localPosition = new Vector3(0f, 0f, HallZ);
            root.localRotation = Quaternion.Euler(0f, 180f, 0f);   // 正立面朝 -Z（对着中庭与大门）
            var v = new GameObject("Visual").transform;
            v.SetParent(root, false);

            const float W = 36f, D = 18f, FL = 5.4f, BODY = FL * 2f, PL = 0.8f;
            const float HW = W * 0.5f, HD = D * 0.5f;

            Kit.Box(v, "Plinth", new Vector3(W + 1.8f, PL, D + 1.8f), new Vector3(0f, PL * 0.5f, 0f), M("stone_dark"), 0f, false);
            // 正立面：两侧壁柱夹一。7m 宽。.8m 高的门洞，上面是过梁
            float pier = (W - 7f) * 0.5f;
            Kit.Box(v, "PierW", new Vector3(pier, BODY, D), new Vector3(-(3.5f + pier * 0.5f), PL + BODY * 0.5f, 0f), M("stone_light"), 0f, false);
            Kit.Box(v, "PierE", new Vector3(pier, BODY, D), new Vector3(3.5f + pier * 0.5f, PL + BODY * 0.5f, 0f), M("stone_light"), 0f, false);
            float lintelH = BODY - 6.8f;
            Kit.Box(v, "Lintel", new Vector3(7f, lintelH, D), new Vector3(0f, PL + 6.8f + lintelH * 0.5f, 0f), M("stone_light"), 0f, false);
            // 门洞（真洞，。18m，尽头一堵深色墙。
            Kit.Box(v, "BackWall", new Vector3(7f, 6.8f, 0.5f), new Vector3(0f, PL + 3.4f, -HD + 0.4f), M("stone_dark"), 0f, false);
            Kit.Box(v, "DoorSill", new Vector3(7.4f, 0.3f, 1.0f), new Vector3(0f, PL + 0.15f, HD + 0.2f), M("stone_dark"), 0f, false);
            // 两扇半开的木。
            Kit.BoxRot(v, "DoorW", new Vector3(3.3f, 6.4f, 0.18f), new Vector3(-3.4f, PL + 3.2f, HD - 0.3f),
                Quaternion.Euler(0f, 26f, 0f), M("wood_dark"), false);
            Kit.BoxRot(v, "DoorE", new Vector3(3.3f, 6.4f, 0.18f), new Vector3(3.4f, PL + 3.2f, HD - 0.3f),
                Quaternion.Euler(0f, -26f, 0f), M("wood_dark"), false);

            // 腰线 / 檐口
            Kit.Box(v, "Belt", new Vector3(W + 0.6f, 0.42f, D + 0.6f), new Vector3(0f, PL + FL, 0f), M("stone_dark"), 0f, false);
            Kit.Box(v, "Cornice", new Vector3(W + 1.3f, 0.55f, D + 1.3f), new Vector3(0f, PL + BODY, 0f), M("stone_dark"), 0f, false);
            // 主屋顶（脊沿 X。 脊瓦
            Kit.Mesh(v, "Roof", Kit.GableRoofMesh(W + 1.6f, D + 1.6f, 4.6f, 0.7f, 0.34f),
                new Vector3(0f, PL + BODY + 0.2f, 0f), M("roof_slate"), false);
            Kit.Box(v, "Ridge", new Vector3(W + 2.0f, 0.4f, 0.7f), new Vector3(0f, PL + BODY + 4.9f, 0f), M("roof_slate"), 0f, false);

            // 正面窗（两层各三段，避开中间门洞。
            float[] wx = { -16.2f, -11.4f, -6.6f, 6.6f, 11.4f, 16.2f };
            for (int i = 0; i < wx.Length; i++)
            {
                ArchedWindow(v, new Vector3(wx[i], PL + 3.5f, HD + 0.07f), 0f, 2.4f, 3.7f, M("stone_dark"),
                    i % 3 == 0 ? M("glow_amber") : M("glass"));
                ArchedWindow(v, new Vector3(wx[i], PL + FL + 3.4f, HD + 0.07f), 0f, 2.4f, 3.7f, M("stone_dark"), M("glass"));
            }
            // 侧面。
            for (int s = -1; s <= 1; s += 2)
                for (int i = 0; i < 4; i++)
                {
                    float z = -6.2f + i * 4.2f;
                    ArchedWindow(v, new Vector3(s * (HW + 0.07f), PL + 3.5f, z), s * 90f, 2.1f, 3.4f, M("stone_dark"), M("glass"));
                    ArchedWindow(v, new Vector3(s * (HW + 0.07f), PL + FL + 3.4f, z), s * 90f, 2.1f, 3.4f, M("stone_dark"), M("glass"));
                }

            // 门廊：柱墩台 + 6 根列。+ 。+ 小山。
            Kit.Box(v, "PorticoPodium", new Vector3(17.6f, 0.6f, 4.8f), new Vector3(0f, 0.3f, HD + 3.0f), M("stone_light"), 0f, false);
            for (int i = 0; i < 6; i++)
                Column(v, new Vector3(-7.5f + i * 3.0f, 0.6f, HD + 3.2f), 6.6f, 0.5f, M("marble"), M("stone_dark"));
            Kit.Box(v, "PorticoArch", new Vector3(17.6f, 0.8f, 3.6f), new Vector3(0f, 7.6f, HD + 3.2f), M("stone_dark"), 0f, false);
            Kit.Mesh(v, "PorticoRoof", Kit.GableRoofMesh(18.4f, 4.6f, 2.1f, 0.35f, 0.26f),
                new Vector3(0f, 8.0f, HD + 3.2f), M("roof_slate"), false);
            // 门廊下的台阶
            StairFlight(v, new Vector3(0f, 0f, HD + 5.4f), 15.6f, M("stone_light"));

            // 紫旗（正立面窗间。
            for (int s = -1; s <= 1; s += 2)
                for (int i = 0; i < 2; i++)
                {
                    float x = s * (9.0f + i * 5.1f);
                    Kit.CylRot(v, "Rod", 0.07f, 2.8f, new Vector3(x, PL + BODY - 0.6f, HD + 0.35f),
                        Quaternion.Euler(90f, 0f, 0f), M("iron"), 6, false);
                    Kit.Slab(v, "Banner", new Vector3(2.3f, 3.9f, 0.1f), new Vector3(x, PL + BODY - 2.9f, HD + 0.4f), M("cloth_purple"));
                }

            Kit.Optimize(v.gameObject, false);

            // 招牌（必须合并之后加。
            Sign(root, "拉诺亚魔法学园 · 主楼", new Vector3(0f, PL + BODY + 0.9f, HD + 0.75f), 0f, 7.6f, 1.0f);
            // 屋脊水晶 + 。
            var crystal = Kit.BoxRot(root, "RidgeCrystal", new Vector3(1.1f, 2.0f, 1.1f), new Vector3(0f, PL + BODY + 5.6f, 0f),
                Quaternion.Euler(45f, 45f, 0f), M("glow_cyan"), false);
            crystal.AddComponent<KitSpin>().DegreesPerSecond = 14f;
            var bob = crystal.AddComponent<KitBob>();
            bob.Amplitude = 0.12f;
            bob.Speed = 0.8f;
            Kit.PointLight(root, new Vector3(0f, PL + BODY + 5.6f, 0f), new Color(0.66f, 0.82f, 1f), 16f, 1.5f);
            // 门廊。
            for (int s = -1; s <= 1; s += 2)
                Kit.PointLight(root, new Vector3(s * 7.5f, 5.4f, HD + 3.2f), new Color(0.85f, 0.75f, 1f), 10f, 1.2f);

            Kit.Blocker(root, "HallBlocker", new Vector3(W + 2.0f, 13.4f, D + 2.0f), new Vector3(0f, 6.7f, 0f));
            Kit.MakeFadeable(root.gameObject, 0.3f);
        }

        // ------------------------------------------------------------------ 两座魔法。
        void BuildWizardTowers(Transform world)
        {
            var root = new GameObject("WizardTowers").transform;
            root.SetParent(world, false);
            RoaKit.Tower(root, new Vector3(-22f, 0f, TowerZ), 180f, true);
            RoaKit.Tower(root, new Vector3(22f, 0f, TowerZ), 180f, true);
            // 塔基的水晶簇 + 底光
            for (int s = -1; s <= 1; s += 2)
            {
                KitProps.CrystalCluster(root, new Vector3(s * 22f + 4.2f, 0f, TowerZ - 3.0f), 1.2f, true);
                KitProps.CrystalCluster(root, new Vector3(s * 22f - 3.4f, 0f, TowerZ - 3.4f), 0.9f, true);
                Kit.PointLight(root, new Vector3(s * 22f, 0.6f, TowerZ - 3.6f), new Color(0.62f, 0.7f, 1f), 8f, 1.1f);
            }
        }

        // ------------------------------------------------------------------ 图书。
        void BuildLibrary(Transform world)
        {
            var root = new GameObject("Library").transform;
            root.SetParent(world, false);
            root.localPosition = new Vector3(LibraryX, 0f, -18f);
            root.localRotation = Quaternion.Euler(0f, 90f, 0f);   // 正立面朝 +X（中庭）
            var v = new GameObject("Visual").transform;
            v.SetParent(root, false);

            const float W = 20f, D = 14f, FL = 4.8f, BODY = FL * 2f, PL = 0.7f;
            const float HW = W * 0.5f, HD = D * 0.5f;

            Kit.Box(v, "Plinth", new Vector3(W + 1.6f, PL, D + 1.6f), new Vector3(0f, PL * 0.5f, 0f), M("stone_dark"), 0f, false);
            Kit.Box(v, "Body", new Vector3(W, BODY, D), new Vector3(0f, PL + BODY * 0.5f, 0f), M("stone_wall"), 0f, false);
            Kit.Box(v, "Belt", new Vector3(W + 0.6f, 0.4f, D + 0.6f), new Vector3(0f, PL + FL, 0f), M("stone_dark"), 0f, false);
            Kit.Box(v, "Cornice", new Vector3(W + 1.2f, 0.5f, D + 1.2f), new Vector3(0f, PL + BODY, 0f), M("stone_dark"), 0f, false);
            Kit.Mesh(v, "Roof", Kit.GableRoofMesh(W + 1.4f, D + 1.4f, 3.7f, 0.6f, 0.3f),
                new Vector3(0f, PL + BODY + 0.16f, 0f), M("roof_teal"), false);

            // 中央塔楼 + 穹顶（图书馆的标志）
            Kit.Cyl(v, "Drum", 3.5f, 2.6f, new Vector3(0f, PL + BODY + 3.0f, 0f), M("stone_light"), 12, false);
            Kit.Cyl(v, "DrumBand", 3.9f, 0.4f, new Vector3(0f, PL + BODY + 4.3f, 0f), M("stone_dark"), 12, false);
            Kit.Cone(v, "Dome", 4.1f, 4.0f, new Vector3(0f, PL + BODY + 6.5f, 0f), M("roof_teal"), 12, false);
            Kit.Cyl(v, "DomeFinial", 0.2f, 1.1f, new Vector3(0f, PL + BODY + 9.0f, 0f), M("gold"), 8, false);
            // 穹顶一圈发光符文窗
            for (int i = 0; i < 6; i++)
            {
                float a = i * 60f;
                var p = new Vector3(Mathf.Sin(a * Mathf.Deg2Rad) * 3.58f, PL + BODY + 3.9f, Mathf.Cos(a * Mathf.Deg2Rad) * 3.58f);
                Kit.BoxRot(v, "DrumLamp" + i, new Vector3(0.9f, 1.3f, 0.2f), p, Quaternion.Euler(0f, a, 0f), M("glow_cyan"), false);
            }

            // 正立面：中央门洞（凹门）+ 两侧拱窗
            Kit.Box(v, "DoorRecess", new Vector3(4.2f, 4.6f, 0.6f), new Vector3(0f, PL + 2.3f, HD - 0.2f), M("stone_dark"), 0f, false);
            Kit.Box(v, "DoorL", new Vector3(1.9f, 4.2f, 0.2f), new Vector3(-1.0f, PL + 2.1f, HD + 0.08f), M("wood_dark"), 0f, false);
            Kit.Box(v, "DoorR", new Vector3(1.9f, 4.2f, 0.2f), new Vector3(1.0f, PL + 2.1f, HD + 0.08f), M("wood_dark"), 0f, false);
            for (int s = -1; s <= 1; s += 2)
            {
                ArchedWindow(v, new Vector3(s * 7.2f, PL + 3.2f, HD + 0.07f), 0f, 2.6f, 3.9f, M("stone_dark"), M("glow_amber"));
                ArchedWindow(v, new Vector3(s * 7.2f, PL + FL + 3.1f, HD + 0.07f), 0f, 2.6f, 3.6f, M("stone_dark"), M("glass"));
                ArchedWindow(v, new Vector3(s * (HW + 0.07f), PL + 3.2f, -2.6f), s * 90f, 2.2f, 3.5f, M("stone_dark"), M("glass"));
                ArchedWindow(v, new Vector3(s * (HW + 0.07f), PL + 3.2f, 2.6f), s * 90f, 2.2f, 3.5f, M("stone_dark"), M("glass"));
            }
            // 门廊 4 。
            for (int i = 0; i < 4; i++)
                Column(v, new Vector3(-5.4f + i * 3.6f, 0f, HD + 2.6f), 5.2f, 0.42f, M("marble"), M("stone_dark"));
            Kit.Box(v, "PorchArch", new Vector3(14.4f, 0.66f, 3.0f), new Vector3(0f, 5.6f, HD + 2.6f), M("stone_dark"), 0f, false);
            Kit.Mesh(v, "PorchRoof", Kit.GableRoofMesh(15.0f, 3.8f, 1.7f, 0.3f, 0.22f), new Vector3(0f, 5.95f, HD + 2.6f), M("roof_teal"), false);
            StairFlight(v, new Vector3(0f, 0f, HD + 4.6f), 13.0f, M("stone_light"));

            Kit.Optimize(v.gameObject, false);

            Sign(root, "图书馆", new Vector3(0f, PL + BODY + 1.0f, HD + 0.7f), 0f, 4.2f, 0.85f);
            Sign(root, "西翼 · 魔导书库", new Vector3(0f, PL + BODY - 0.9f, HD + 0.7f), 0f, 3.4f, 0.42f,
                M("stone_dark").color, M("marble").color);
            Kit.PointLight(root, new Vector3(0f, PL + BODY + 6.0f, 0f), new Color(0.66f, 0.9f, 1f), 12f, 1.2f);
            Kit.PointLight(root, new Vector3(0f, 4.6f, HD + 2.6f), new Color(0.9f, 0.82f, 1f), 9f, 1.1f);
            Kit.Blocker(root, "LibraryBlocker", new Vector3(W + 1.8f, 11.6f, D + 1.8f), new Vector3(0f, 5.8f, 0f));
            Kit.MakeFadeable(root.gameObject, 0.3f);
        }

        // ------------------------------------------------------------------ 宿舍排屋
        void BuildDormitory(Transform world)
        {
            var root = new GameObject("Dormitory").transform;
            root.SetParent(world, false);
            root.localPosition = new Vector3(DormX, 0f, -18f);
            root.localRotation = Quaternion.Euler(0f, -90f, 0f);   // 正立面朝 -X（中庭）
            var v = new GameObject("Visual").transform;
            v.SetParent(root, false);

            const float W = 36f, D = 12f, FL = 4.2f, BODY = FL * 2f, PL = 0.6f;
            const float HW = W * 0.5f, HD = D * 0.5f;

            Kit.Box(v, "Plinth", new Vector3(W + 1.4f, PL, D + 1.4f), new Vector3(0f, PL * 0.5f, 0f), M("stone_dark"), 0f, false);
            Kit.Box(v, "Body", new Vector3(W, BODY, D), new Vector3(0f, PL + BODY * 0.5f, 0f), M("brick"), 0f, false);
            Kit.Box(v, "Belt", new Vector3(W + 0.5f, 0.38f, D + 0.5f), new Vector3(0f, PL + FL, 0f), M("stone_light"), 0f, false);
            Kit.Box(v, "Cornice", new Vector3(W + 1.1f, 0.46f, D + 1.1f), new Vector3(0f, PL + BODY, 0f), M("stone_dark"), 0f, false);
            Kit.Mesh(v, "Roof", Kit.GableRoofMesh(W + 1.3f, D + 1.3f, 3.4f, 0.6f, 0.3f),
                new Vector3(0f, PL + BODY + 0.16f, 0f), M("roof_burgundy"), false);
            // 三个烟囱（学生宿舍的壁炉。
            for (int i = 0; i < 3; i++)
            {
                float x = -12f + i * 12f;
                Kit.Box(v, "Chimney", new Vector3(1.4f, 3.4f, 1.4f), new Vector3(x, PL + BODY + 2.6f, 1.6f), M("brick"), 0f, false);
                Kit.Box(v, "ChimneyCap", new Vector3(1.8f, 0.3f, 1.8f), new Vector3(x, PL + BODY + 4.4f, 1.6f), M("stone_dark"), 0f, false);
            }

            // 六个门洞：凹进去的门。+ 木门 + 石拱 + 台阶
            float[] dx = { -15f, -9f, -3f, 3f, 9f, 15f };
            for (int i = 0; i < dx.Length; i++)
            {
                Kit.Box(v, "DoorRecess", new Vector3(2.6f, 3.3f, 0.5f), new Vector3(dx[i], PL + 1.65f, HD - 0.2f), M("stone_dark"), 0f, false);
                Kit.Box(v, "Door", new Vector3(2.2f, 3.1f, 0.18f), new Vector3(dx[i], PL + 1.55f, HD + 0.06f), M("wood_dark"), 0f, false);
                Kit.Box(v, "DoorJambL", new Vector3(0.26f, 3.4f, 0.34f), new Vector3(dx[i] - 1.3f, PL + 1.7f, HD + 0.05f), M("stone_light"), 0f, false);
                Kit.Box(v, "DoorJambR", new Vector3(0.26f, 3.4f, 0.34f), new Vector3(dx[i] + 1.3f, PL + 1.7f, HD + 0.05f), M("stone_light"), 0f, false);
                Kit.BoxRot(v, "DoorArch", new Vector3(0.32f, 1.2f, 0.4f), new Vector3(dx[i], PL + 3.5f, HD + 0.05f),
                    Quaternion.Euler(0f, 0f, 90f), M("stone_light"), false);
                Kit.Box(v, "DoorStep", new Vector3(3.2f, 0.24f, 1.0f), new Vector3(dx[i], 0.12f, HD + 0.5f), M("stone_light"), 0f, false);
                // 二层。
                ArchedWindow(v, new Vector3(dx[i], PL + FL + 2.2f, HD + 0.07f), 0f, 2.0f, 3.0f, M("stone_dark"), M("glass"));
                Kit.PointLight(v, new Vector3(dx[i], PL + 3.9f, HD + 0.6f), new Color(1f, 0.85f, 0.6f), 7f, 0.9f);
            }
            // 二层外廊（石栏板 + 望柱。
            Kit.Slab(v, "Gallery", new Vector3(W, 0.24f, 1.3f), new Vector3(0f, PL + FL - 0.5f, HD + 0.65f), M("stone_light"));
            Kit.Slab(v, "GalleryRail", new Vector3(W, 0.18f, 0.26f), new Vector3(0f, PL + FL + 0.35f, HD + 1.2f), M("marble"));
            for (int i = 0; i < 25; i++)
                Kit.Cyl(v, "Baluster", 0.09f, 0.75f, new Vector3(-HW + 0.9f + i * 1.45f, PL + FL - 0.05f, HD + 1.2f), M("marble"), 6, false);
            // 山墙端头的排屋标。
            for (int s = -1; s <= 1; s += 2)
                ArchedWindow(v, new Vector3(s * (HW + 0.07f), PL + 2.6f, -1.6f), s * 90f, 2.0f, 3.2f, M("stone_dark"), M("glass"));

            Kit.Optimize(v.gameObject, false);

            Sign(root, "学生宿舍 · 东舍", new Vector3(0f, PL + BODY + 1.0f, HD + 0.8f), 0f, 6.0f, 0.85f);
            Sign(root, "男生禁入 · 女生禁入 · 教师随意", new Vector3(0f, PL + 3.9f, HD + 0.7f), 0f, 7.4f, 0.4f,
                M("cloth_cream").color, null);
            for (int i = 0; i < 3; i++)
            {
                Kit.Slab(root, "BannerRod", new Vector3(2.4f, 0.1f, 0.1f), new Vector3(-6f + i * 6f, PL + BODY - 0.5f, HD + 0.5f), M("iron"));
                Kit.Slab(root, "Banner", new Vector3(2.0f, 3.0f, 0.1f), new Vector3(-6f + i * 6f, PL + BODY - 2.2f, HD + 0.55f), M("cloth_purple"));
            }
            Kit.Blocker(root, "DormBlocker", new Vector3(W + 1.6f, 10.2f, D + 1.6f), new Vector3(0f, 5.1f, 0f));
            Kit.MakeFadeable(root.gameObject, 0.3f);
        }

        // ------------------------------------------------------------------ 学园魔法商店
        void BuildMagicShop(Transform world)
        {
            var shop = RoaKit.Shop(world, "MagicShop", new Vector3(14f, 0f, -33f), 0f, 8.5f, 7f,
                ShopKind.Magic, "魔法商店", "stone_wall", "plaster_white", "roof_slate", "cloth_purple", true);
            shop.name = "MagicShop";
            // 招牌交给 RoaKit 原样：RoaKit.Shop 在 RoaKit.cs:848 把牌挂在 +hd（本地 +Z 正面），
            // 实测（隔离测试 sg_plusZ.png）yaw 0 的牌正是从 +Z 侧可读 —— 也就是说店招本来就是朝街的，
            // 之前"店招镜像"的判断已被推翻，这里不做任何翻转。
        }

        // ------------------------------------------------------------------ 魔法训练。
        void BuildTrainingYard(Transform world)
        {
            var root = new GameObject("TrainingYard").transform;
            root.SetParent(world, false);
            root.localPosition = new Vector3(36f, 0f, 12f);
            var v = new GameObject("Visual").transform;
            v.SetParent(root, false);

            Kit.Slab(v, "Sand", new Vector3(16f, 0.12f, 14f), new Vector3(0f, 0.06f, 0f), M("sand"));
            Kit.Slab(v, "Trench", new Vector3(10f, 0.14f, 0.5f), new Vector3(0f, 0.07f, -3.4f), M("dirt_dark"));
            Kit.Box(v, "LowWall", new Vector3(16f, 1.0f, 0.6f), new Vector3(0f, 0.5f, 6.8f), M("stone_dark"), 0f, false);
            Kit.Box(v, "LowWallCap", new Vector3(16.4f, 0.2f, 0.8f), new Vector3(0f, 1.1f, 6.8f), M("marble"), 0f, false);
            Kit.Optimize(v.gameObject, false);   // 先合并场地，再摆稻草人（否则稻草人和它们的碰撞盒会被一起销毁）
            for (int i = 0; i < 3; i++) Dummy(v, new Vector3(-4.6f + i * 4.6f, 0f, 1.2f), 15f - i * 12f);
            Kit.Blocker(root, "YardWall", new Vector3(16.4f, 1.2f, 0.9f), new Vector3(0f, 0.6f, 6.8f));
        }

        void Dummy(Transform parent, Vector3 pos, float yaw)
        {
            var root = new GameObject("TrainingDummy").transform;
            root.SetParent(parent, false);
            root.localPosition = pos;
            root.localRotation = Quaternion.Euler(0f, yaw, 0f);
            Kit.Cyl(root, "Post", 0.14f, 1.9f, new Vector3(0f, 0.95f, 0f), M("wood_dark"), 8, false);
            Kit.Box(root, "Torso", new Vector3(0.8f, 1.0f, 0.55f), new Vector3(0f, 1.45f, 0f), M("sand"), 0f, false);
            Kit.Box(root, "Rope1", new Vector3(0.86f, 0.12f, 0.6f), new Vector3(0f, 1.2f, 0f), M("roof_thatch"), 0f, false);
            Kit.Box(root, "Rope2", new Vector3(0.86f, 0.12f, 0.6f), new Vector3(0f, 1.7f, 0f), M("roof_thatch"), 0f, false);
            Kit.Box(root, "Head", new Vector3(0.36f, 0.36f, 0.36f), new Vector3(0f, 2.14f, 0f), M("sand"), 0f, false);
            Kit.CylRot(root, "Arms", 0.1f, 2.1f, new Vector3(0f, 1.66f, 0f), Quaternion.Euler(0f, 0f, 90f), M("wood_dark"), 6, false);
            Kit.Box(root, "Target", new Vector3(0.56f, 0.56f, 0.06f), new Vector3(0f, 1.5f, 0.3f), M("cloth_red"), 0f, false);
            Kit.Blocker(root, "DummyBlocker", new Vector3(0.9f, 2.1f, 0.9f), new Vector3(0f, 1.05f, 0f));
        }

        // ------------------------------------------------------------------ 东边门（去布耶纳村）
        void BuildEastGate(Transform world)
        {
            var root = new GameObject("EastGate").transform;
            root.SetParent(world, false);
            root.localPosition = new Vector3(EastGateX, 0f, -6f);
            var v = new GameObject("Visual").transform;
            v.SetParent(root, false);

            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Cyl(v, "Pillar", 0.9f, 6.6f, new Vector3(0f, 3.3f, s * 3.7f), M("stone_light"), 12, false);
                Kit.Box(v, "PillarBase", new Vector3(2.4f, 0.6f, 2.4f), new Vector3(0f, 0.3f, s * 3.7f), M("stone_dark"), 0f, false);
                Kit.Box(v, "PillarCap", new Vector3(2.2f, 0.5f, 2.2f), new Vector3(0f, 6.7f, s * 3.7f), M("stone_dark"), 0f, false);
            }
            Kit.Box(v, "Lintel", new Vector3(1.7f, 0.9f, 9.0f), new Vector3(0f, 7.4f, 0f), M("stone_wall"), 0f, false);
            Kit.MeshRot(v, "Cap", Kit.GableRoofMesh(9.6f, 2.8f, 1.6f, 0.35f, 0.24f), new Vector3(0f, 7.85f, 0f),
                Quaternion.Euler(0f, 90f, 0f), M("roof_slate"), false);
            // 铁栅门（开着的两扇）
            Kit.BoxRot(v, "GateW", new Vector3(3.0f, 4.2f, 0.14f), new Vector3(0f, 2.1f, -3.3f),
                Quaternion.Euler(0f, 58f, 0f), M("iron"), false);
            Kit.BoxRot(v, "GateE", new Vector3(3.0f, 4.2f, 0.14f), new Vector3(0f, 2.1f, 3.3f),
                Quaternion.Euler(0f, -58f, 0f), M("iron"), false);
            Kit.Optimize(v.gameObject, false);

            Sign(root, "前往 布耶纳村 →", new Vector3(-0.95f, 6.2f, 0f), -90f, 4.0f, 0.8f);
            for (int s = -1; s <= 1; s += 2)
                Kit.PointLight(root, new Vector3(-0.8f, 5.6f, s * 3.7f), new Color(0.85f, 0.8f, 1f), 8f, 1.0f);
            for (int s = -1; s <= 1; s += 2)
                Kit.Blocker(root, "PillarBlocker", new Vector3(2.2f, 6.6f, 2.2f), new Vector3(0f, 3.3f, s * 3.7f));
            Kit.MakeFadeable(root.gameObject, 0.34f);
        }

        // ------------------------------------------------------------------ 可交互物
        void BuildInteractables(Transform world)
        {
            // 传送门：南门去罗亚市，东边门去布耶纳。
            ScenePortal.Create(world, new Vector3(0f, 0f, GateZ - 3.2f), MapId.RoaTown, "start", "前往 罗亚市", 180f);
            ScenePortal.Create(world, new Vector3(EastGateX - 2.2f, 0f, -6f), MapId.BuenaVillage, "village_gate", "前往 布耶纳村", -90f);

            // 学园委托板（拉诺亚学。· 委托板）
            QuestBoardInteractable.CreateStand(world, new Vector3(-20f, 0f, -30f), "ranoa_guild", 90f);

            // 魔晶（塔基与魔法阵旁。 药草（花园）+ 金币
            PickupInteractable.Create(world, new Vector3(19.4f, 0f, 22.2f), PickupKind.Crystal, 0, null, "academy_crystal_1");
            PickupInteractable.Create(world, new Vector3(-19.4f, 0f, 22.2f), PickupKind.Crystal, 0, null, "academy_crystal_2");
            PickupInteractable.Create(world, new Vector3(5.6f, 0f, -15.2f), PickupKind.Crystal, 0, null, "academy_crystal_3");
            PickupInteractable.Create(world, new Vector3(-16f, 0f, -26f), PickupKind.Herb, 0, null, null);
            PickupInteractable.Create(world, new Vector3(-16f, 0f, -10f), PickupKind.Herb, 0, null, null);
            PickupInteractable.Create(world, new Vector3(-3.2f, 0f, -25.6f), PickupKind.Coin, 15, null, "academy_coin_1");
            PickupInteractable.Create(world, new Vector3(19f, 0f, -24f), PickupKind.Coin, 10, null, "academy_coin_2");
        }

        // ------------------------------------------------------------------ NPC
        void BuildPeople(Transform world)
        {
            // 门卫
            SpawnNpc(NpcRole.Guard, "门卫 · 甲", new Vector3(-4.6f, 0f, GateZ + 2.6f), 200f, new[]
            {
                "访客请在大道尽头登记。",
                "学园内禁止施放火系魔法，请配合。",
            });
            SpawnNpc(NpcRole.Guard, "门卫 · 乙", new Vector3(4.6f, 0f, GateZ + 2.6f), 160f, new[]
            {
                "往布耶纳村走东边门，出城顺着土路。",
                "最近学生夜里溜出去，被训导长抓了三个。",
            });

            // 六名学生
            SpawnNpc(NpcRole.Student, "学生 · 见习魔法师", new Vector3(0.6f, 0f, -20f), 20f, new[]
            {
                "中庭那个魔法阵是实技课用的，别乱踩。",
                "图书馆二层的魔导书要教师签字才能借。",
            });
            SpawnNpc(NpcRole.Student, "学生 · 贵族子弟", new Vector3(-2.6f, 0f, -7f), 200f, new[]
            {
                "这种基础咒式，我家里请的导师早教过了。",
                "……其实我水系魔法总也凝不出形。",
            });
            SpawnNpc(NpcRole.Student, "学生 · 兽族少女", new Vector3(3.4f, 0f, -30f), 180f, new[]
            {
                "喷泉的水能照出魔力流动，我天天来看。",
                "风系魔法最难的地方是别把自己吹跑。",
            });
            SpawnNpc(NpcRole.Student, "学生 · 图书委员", new Vector3(-11f, 0f, -19f), 90f, new[]
            {
                "我在整理禁书目录，别碰第三排。",
                "图书馆的穹顶会把月光引进书库。",
            });
            SpawnNpc(NpcRole.Student, "学生 · 剑术", new Vector3(-4f, 0f, 3f), 10f, new[]
            {
                "魔法我不会几个，剑术课我可没输过。",
                "主楼后面有训练场，稻草人随便打。",
            });
            SpawnNpc(NpcRole.Student, "学生 · 新生", new Vector3(20.5f, 0f, -6f), -90f, new[]
            {
                "宿舍六人一间，晚上查寝很严。",
                "我还没找到教室……主楼太大了。",
            });

            // 委托板管理员 + 老图书管理员
            SpawnNpc(NpcRole.GuildStaff, "委托板管理员", new Vector3(-21f, 0f, -31.6f), 60f, new[]
            {
                "委托都贴在板上，接了就按时完成。",
                "魔晶采集是学园的老委托了。",
            }, null, "ranoa_guild");
            SpawnNpc(NpcRole.Villager, "老图书管理员", new Vector3(-21.6f, 0f, -22f), 90f, new[]
            {
                "书比剑安静，也更长久。",
                "学生总把书翻到卷角，唉。",
            });

            // 魔法商店店主
            SpawnNpc(NpcRole.Merchant, "魔法商店 · 店主", new Vector3(14f, 0f, -27.6f), 180f, new[]
            {
                "魔力药水、魔导墨水，学生价。",
                "赊账的话，拿委托完成证明来抵。",
            }, "ranoa_shop");

            // ---- 新增：教师编制（学园不能只有学生。---
            SpawnNpc(NpcRole.GuildStaff, "教师 · 元素理论", new Vector3(-3.2f, 0f, 13.2f), 200f, new[]
            {
                "元素不是被召唤来的，是被请来的。",
                "楼梯口的告示看过了吗？这周的实技课改在中庭。",
            });
            SpawnNpc(NpcRole.GuildStaff, "剑术教官 · 塞拉", new Vector3(40f, 0f, 4.6f), 200f, new[]
            {
                "拿不稳剑的人，也握不稳法杖。",
                "训练场的草人打坏了不用赔，但得自己扎。",
            });
            SpawnNpc(NpcRole.GuildStaff, "观星学者 · 奥兰", new Vector3(-32f, 0f, -5.4f), 0f, new[]
            {
                "塔顶的镜筒能看见明年才该出现的星。",
                "别在塔里点明火，穹顶的玻璃会裂。",
            });

            // ---- 新增：食。/ 旧书。/ 炼金。/ 驿站 / 温室 ----
            SpawnNpc(NpcRole.Merchant, "食堂大娘 · 玛琪", new Vector3(23.6f, 0f, 5.4f), 15f, new[]
            {
                "炖菜管饱，汤底从早上熬到现在。",
                "蜂蜜面包是学生抢的，来晚就没。",
            }, "ranoa_canteen");
            SpawnNpc(NpcRole.Merchant, "旧书摊主 · 柯林", new Vector3(-13.9f, 0f, -18f), 90f, new[]
            {
                "星图抄本、旧课本、缺页的咒式集，都收。",
                "这本书的批注是位老学生写的，值钱着呢。",
            }, "ranoa_books");
            SpawnNpc(NpcRole.Merchant, "炼金摊主 · 图娜", new Vector3(-18.9f, 0f, -18f), 90f, new[]
            {
                "魔晶粉末按克卖，学生价。",
                "炼金失败是常态，别炸了摊子就行。",
            }, "ranoa_shop");
            SpawnNpc(NpcRole.Innkeeper, "驿站门房 · 老塞", new Vector3(-25.4f, 0f, -33.6f), 0f, new[]
            {
                "访客登记一下，留宿要赶在宵禁前。",
                "热汤和床位，价钱写在门上那块牌子。",
            }, "ranoa_guest", null, "ranoa_guest_keeper");
            SpawnNpc(NpcRole.Villager, "园丁 · 苔丝", new Vector3(-34f, 0f, 11.2f), 0f, new[]
            {
                "温室的药草比野地里的娇气，得哄着养。",
                "别碰最里面那排，那是毒草。",
            });

            // ---- 新增：学生与杂役 ----
            SpawnNpc(NpcRole.Student, "学生 · 食堂常客", new Vector3(18.6f, 0f, 8.4f), 340f, new[]
            {
                "食堂的炖菜比宿舍的面包强一百倍。",
                "我早上已经在这儿吃了两碗了。",
            });
            SpawnNpc(NpcRole.Student, "学生 · 观星会", new Vector3(-26.8f, 0f, 0.6f), 120f, new[]
            {
                "观星会今晚在塔顶集合，你来吗。",
                "值班的学者凶，但讲得很好。",
            });
            SpawnNpc(NpcRole.Student, "学生 · 买书的人", new Vector3(-11.6f, 0f, -16.4f), 250f, new[]
            {
                "旧书摊这本《元素谱系》比图书馆那本还全。",
                "省钱买书，这个月只能吃面包了。",
            });
            SpawnNpc(NpcRole.Villager, "杂役 · 扫地人", new Vector3(6.4f, 0f, -34.6f), 200f, new[]
            {
                "一天扫三遍，叶子还是掉。",
                "魔法阵那边别踩，扫起来费劲。",
            });
            SpawnNpc(NpcRole.Guard, "东门卫兵", new Vector3(41.6f, 0f, -9.4f), 0f, new[]
            {
                "东边门出去就是布耶纳村的土路。",
                "夜里的林子不安全，走大路。",
            });
        }

        // ------------------------------------------------------------------ 出生。
        void BuildSpawns()
        {
            // 起点放在门楼以北 20m：俯视机位在角色正后。13.5m（camDistance 22 × cos52°），
            // 若贴着门楼出生，相机与角色之间会卡着门楼+匾额，开局长什么样取决于那块匾。
            PlaceSpawn("start", new Vector3(0f, 0.2f, GateZ + 20f), 0f);
            PlaceSpawn("gate", new Vector3(0f, 0.2f, GateZ + 2f), 0f);
            PlaceSpawn("court", new Vector3(0f, 0.2f, -12f), 0f);
            PlaceSpawn("hall", new Vector3(0f, 0.2f, 4f), 0f);
            PlaceSpawn("library", new Vector3(-19f, 0.2f, -18f), 90f);
            PlaceSpawn("dorm", new Vector3(21f, 0.2f, -18f), -90f);
            PlaceSpawn("east_gate", new Vector3(EastGateX - 4f, 0.2f, -6f), -90f);
            PlaceSpawn("training", new Vector3(36f, 0.2f, 6f), 0f);
            // 新增区域（布耶纳村传过来用的。"court"，这。id 供内部传。调试用）
            PlaceSpawn("observatory", new Vector3(-32f, 0.2f, -6.2f), 0f);
            PlaceSpawn("canteen", new Vector3(21.5f, 0.2f, 4.4f), 0f);
            PlaceSpawn("greenhouse", new Vector3(-34f, 0.2f, 9.6f), 0f);
            PlaceSpawn("guest", new Vector3(-28f, 0.2f, -32.6f), 180f);
            PlaceSpawn("bookstall", new Vector3(-12.5f, 0.2f, -15.6f), 0f);
        }

        // ================= 地标 ②：观星。=================
        void BuildObservatory(Transform world)
        {
            var root = new GameObject("Observatory").transform;
            root.SetParent(world, false);
            root.localPosition = new Vector3(-32f, 0f, 2f);
            root.localRotation = Quaternion.Euler(0f, 180f, 0f);   // 门朝大道

            var v = new GameObject("Visual").transform;
            v.SetParent(root, false);
            var stone = M("stone_light");
            var trim = M("marble");
            var wood = M("timber_dark");

            Kit.Cyl(v, "Plinth", 5.1f, 0.55f, new Vector3(0f, 0.27f, 0f), M("stone_dark"), 16, false);
            Kit.Cyl(v, "PlinthTop", 4.9f, 0.18f, new Vector3(0f, 0.6f, 0f), trim, 16, false);
            Kit.Cyl(v, "Base", 4.35f, 3.4f, new Vector3(0f, 2.3f, 0f), stone, 16, false);
            Kit.Cyl(v, "BaseBand", 4.55f, 0.34f, new Vector3(0f, 4.02f, 0f), M("stone_dark"), 16, false);
            Kit.Cyl(v, "Tower", 3.55f, 7.0f, new Vector3(0f, 7.6f, 0f), M("plaster_white"), 16, false);
            for (int i = 0; i < 3; i++)
                Kit.Cyl(v, "TowerBand" + i, 3.72f, 0.22f, new Vector3(0f, 5.4f + i * 2.1f, 0f), stone, 16, false);

            // 阳台
            Kit.Cyl(v, "Balcony", 4.55f, 0.3f, new Vector3(0f, 11.25f, 0f), trim, 18, false);
            for (int i = 0; i < 16; i++)
            {
                float a = i * 22.5f;
                Kit.Box(v, "BalR", new Vector3(0.12f, 0.8f, 0.12f),
                    new Vector3(Mathf.Sin(a * Mathf.Deg2Rad) * 4.35f, 11.65f, Mathf.Cos(a * Mathf.Deg2Rad) * 4.35f),
                    wood, 0f, false);
            }
            Kit.Cyl(v, "BalRail", 4.45f, 0.1f, new Vector3(0f, 12.05f, 0f), wood, 18, false);

            // 穹顶（压扁的球）+ 观测。
            Kit.Sphere(v, "Dome", new Vector3(8.6f, 4.6f, 8.6f), new Vector3(0f, 12.9f, 0f), M("roof_blue"), false, 14);
            Kit.Cyl(v, "DomeRing", 4.5f, 0.24f, new Vector3(0f, 12.1f, 0f), trim, 18, false);
            Kit.Box(v, "Slit", new Vector3(0.9f, 3.4f, 0.5f), new Vector3(0f, 13.4f, 3.9f), M("stone_dark"), 0f, false);
            Kit.Box(v, "SlitGlow", new Vector3(0.6f, 3.0f, 0.16f), new Vector3(0f, 13.4f, 4.16f), M("glow_cyan"), 0f, false);

            // 。/ 台阶 / 。
            Kit.Box(v, "Door", new Vector3(1.7f, 2.9f, 0.24f), new Vector3(0f, 1.75f, 4.4f), wood, 0f, false);
            Kit.Box(v, "DoorArch", new Vector3(2.2f, 0.36f, 0.34f), new Vector3(0f, 3.3f, 4.4f), trim, 0f, false);
            Kit.Box(v, "Step1", new Vector3(3.0f, 0.28f, 1.0f), new Vector3(0f, 0.14f, 5.0f), stone, 0f, false);
            Kit.Box(v, "Step2", new Vector3(2.4f, 0.26f, 0.9f), new Vector3(0f, 0.4f, 5.5f), stone, 0f, false);
            for (int i = 0; i < 3; i++)
            {
                float a = (40f + i * 100f) * Mathf.Deg2Rad;
                Kit.Box(v, "Win" + i, new Vector3(0.62f, 1.15f, 0.16f),
                    new Vector3(Mathf.Sin(a) * 3.4f, 6.6f, Mathf.Cos(a) * 3.4f), M("glow_amber"), -a * Mathf.Rad2Deg, false);
            }
            Kit.Optimize(v.gameObject, false);

            // 镜筒：斜指天空（合并之后再建，免得被合掉。
            var rot = Quaternion.Euler(-34f, 26f, 0f);
            var dir = rot * Vector3.up;
            var tubePos = new Vector3(0.2f, 14.2f, 0.8f);
            Kit.CylRot(root, "Telescope", 0.34f, 4.2f, tubePos, rot, M("bronze"), 10, false);
            Kit.CylRot(root, "TelescopeRing", 0.46f, 0.3f, tubePos + dir * 1.4f, rot, M("gold"), 10, false);
            Kit.Sphere(root, "Lens", new Vector3(0.62f, 0.62f, 0.62f), tubePos + dir * 2.2f, M("glow_cyan"), false, 10);

            // 南北两面各挂一块：Kit.SignBoard 只有单面可读，只挂一面时从背面看会成为镜像字。
            Sign(root, "观星台", new Vector3(0f, 3.72f, 4.62f), 0f, 2.0f, 0.5f);
            Sign(root, "观星台", new Vector3(0f, 3.72f, -4.62f), 180f, 2.0f, 0.5f);
            Sign(root, "闲人免进 · 塔内禁火", new Vector3(0f, 3.1f, 4.62f), 0f, 2.2f, 0.36f, M("cloth_cream").color, null);
            Sign(root, "闲人免进 · 塔内禁火", new Vector3(0f, 3.1f, -4.62f), 180f, 2.2f, 0.36f, M("cloth_cream").color, null);
            Kit.PointLight(root, new Vector3(0f, 3.6f, 5.6f), new Color(0.72f, 0.78f, 1f), 9f, 1.1f);
            Kit.Blocker(root, "TowerBlocker", new Vector3(8.4f, 16f, 8.4f), new Vector3(0f, 8f, 0f));

            // 塔前的小魔法。+ 水晶灯两。
            RoaKit.FloorDisc(root, "StarFloor", 3.4f, new Vector3(0f, 0.07f, 7.6f), M("marble"), 20);
            RoaKit.RuneCircle(root, new Vector3(0f, 0.1f, 7.6f), true);
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Cyl(root, "LampPost", 0.2f, 3.2f, new Vector3(s * 3.4f, 1.6f, 7.8f), M("stone_light"), 10, false);
                var cr = Kit.BoxRot(root, "LampCrystal", new Vector3(0.44f, 0.8f, 0.44f),
                    new Vector3(s * 3.4f, 3.6f, 7.8f), Quaternion.Euler(45f, 45f, 0f), M("glow_violet"), false);
                cr.AddComponent<KitSpin>().DegreesPerSecond = -22f;
            }
            Kit.MakeFadeable(root.gameObject, 0.32f);
        }

        // ================= 学生食堂（据。+ 商店。=================
        void BuildCanteen(Transform world)
        {
            var root = new GameObject("Canteen").transform;
            root.SetParent(world, false);
            root.localPosition = new Vector3(21.5f, 0f, 10.5f);
            root.localRotation = Quaternion.Euler(0f, 180f, 0f);   // 开敞的一侧朝中庭

            var v = new GameObject("Visual").transform;
            v.SetParent(root, false);
            var stone = M("stone_light");
            var wood = M("timber_dark");

            Kit.Slab(v, "Floor", new Vector3(11.8f, 0.16f, 9.4f), new Vector3(0f, 0.08f, 0f), M("cobble"));
            // 后墙与两侧矮。
            Kit.Box(v, "BackWall", new Vector3(11.4f, 1.6f, 0.5f), new Vector3(0f, 0.8f, -4.3f), stone, 0f, false);
            for (int s = -1; s <= 1; s += 2)
                Kit.Box(v, "SideWall", new Vector3(0.5f, 1.6f, 8.8f), new Vector3(s * 5.5f, 0.8f, 0f), stone, 0f, false);
            // 前檐六根柱子
            for (int i = 0; i < 4; i++)
                Kit.Cyl(v, "Pier" + i, 0.24f, 3.3f, new Vector3(-5f + i * 3.34f, 1.65f, 4.2f), stone, 8, false);
            // 屋顶
            Kit.Mesh(v, "Roof", Kit.GableRoofMesh(12.6f, 10.4f, 2.5f, 0.7f, 0.3f), new Vector3(0f, 3.42f, 0f), M("roof_slate"), false);
            Kit.Box(v, "Beam", new Vector3(11.6f, 0.26f, 0.3f), new Vector3(0f, 3.3f, 4.15f), wood, 0f, false);
            // 前檐布棚
            Kit.Slab(v, "Awning", new Vector3(11.2f, 0.1f, 2.4f), new Vector3(0f, 3.05f, 5.3f), M("cloth_purple"));
            for (int s = -1; s <= 1; s += 2)
                Kit.Cyl(v, "AwnPole", 0.1f, 3.0f, new Vector3(s * 5.4f, 1.5f, 6.4f), wood, 6, false);
            // 烟囱（灶台的排烟。
            Kit.Box(v, "Chimney", new Vector3(1.0f, 3.6f, 1.0f), new Vector3(-4.2f, 4.4f, -3.4f), M("stone_dark"), 0f, false);
            Kit.Optimize(v.gameObject, false);
            Kit.MakeFadeable(v.gameObject, 0.34f);

            // 灶台 / 大锅 / 蒸汽
            var fire = new GameObject("Kitchen").transform;
            fire.SetParent(root, false);
            Kit.Box(fire, "Hearth", new Vector3(3.0f, 1.0f, 2.2f), new Vector3(-4.0f, 0.5f, -3.2f), M("stone_wall"), 0f, true);
            Kit.Cyl(fire, "Cauldron", 0.8f, 0.85f, new Vector3(-4.0f, 1.42f, -3.2f), M("iron"), 14, false);
            Kit.Cyl(fire, "Stew", 0.66f, 0.06f, new Vector3(-4.0f, 1.86f, -3.2f), M("sand"), 14, false);
            Kit.Box(fire, "EmberGlow", new Vector3(1.5f, 0.22f, 0.7f), new Vector3(-4.0f, 0.34f, -2.1f), M("glow_warm"), 0f, false);
            Kit.PointLight(fire, new Vector3(-4.0f, 1.5f, -2.6f), new Color(1f, 0.66f, 0.34f), 7f, 1.3f);
            Kit.Smoke(fire, new Vector3(-4.0f, 2.0f, -3.2f), new Color(0.82f, 0.8f, 0.78f), 3, 0.3f);

            // 长桌 + 长凳
            for (int i = 0; i < 2; i++)
            {
                float z = 1.6f - i * 3.0f;
                Kit.Box(root, "Table" + i, new Vector3(6.4f, 0.16f, 1.0f), new Vector3(0.6f, 0.82f, z), M("wood_plank"), 0f, true);
                for (int sx = -1; sx <= 1; sx += 2)
                {
                    Kit.Cyl(root, "Trestle", 0.09f, 0.8f, new Vector3(0.6f + sx * 2.8f, 0.4f, z), wood, 6, false);
                    Kit.Box(root, "Bench" + i, new Vector3(6.0f, 0.14f, 0.42f), new Vector3(0.6f, 0.46f, z + 0.85f), M("wood_plank"), 0f, false);
                }
                for (int k = 0; k < 4; k++)
                {
                    Kit.Box(root, "Bowl" + i + "_" + k, new Vector3(0.34f, 0.1f, 0.34f), new Vector3(-1.6f + k * 1.5f, 0.95f, z), M("white"), 0f, false);
                    Kit.Box(root, "Loaf" + i + "_" + k, new Vector3(0.3f, 0.12f, 0.2f), new Vector3(-1.6f + k * 1.5f, 0.95f, z + 0.32f), M("sand"), 0f, false);
                }
            }

            // 前台的柜台：面包 / 陶罐 / 钱匣
            Kit.Box(root, "Counter", new Vector3(3.4f, 1.0f, 0.8f), new Vector3(3.2f, 0.5f, 4.0f), M("wood_dark"), 0f, true);
            Kit.Box(root, "CounterTop", new Vector3(3.6f, 0.12f, 0.95f), new Vector3(3.2f, 1.06f, 4.0f), M("wood_plank"), 0f, false);
            Kit.Box(root, "BreadBasket", new Vector3(0.7f, 0.22f, 0.5f), new Vector3(2.4f, 1.2f, 4.0f), M("wood_barrel"), 0f, false);
            Kit.Box(root, "Bread", new Vector3(0.55f, 0.18f, 0.32f), new Vector3(2.4f, 1.36f, 4.0f), M("sand"), 0f, false);
            RoaKit.Pot(root, new Vector3(4.2f, 0f, 3.4f), false);
            RoaKit.Barrel(root, new Vector3(-6.2f, 0f, 4.6f), 20f, 0.9f);
            RoaKit.Crate(root, new Vector3(6.2f, 0f, 5.0f), -12f, 0.9f);
            RoaKit.Sack(root, new Vector3(-6.4f, 0f, -1.6f), 20f);

            Sign(root, "学生食堂", new Vector3(0f, 3.95f, 5.9f), 0f, 3.2f, 0.66f);
            Sign(root, "炖菜 8 · 面包 4 · 蜂蜜面包 16", new Vector3(0f, 3.35f, 5.9f), 0f, 4.6f, 0.34f, M("cloth_cream").color, null);
            Kit.PointLight(root, new Vector3(0f, 2.9f, 5.4f), new Color(1f, 0.84f, 0.58f), 8f, 1.0f);
            for (int s = -1; s <= 1; s += 2)
                Kit.Blocker(root, "WallBlocker", new Vector3(11.4f, 1.7f, 0.6f), new Vector3(0f, 0.85f, s * 4.3f));
            for (int s = -1; s <= 1; s += 2)
                Kit.Blocker(root, "SideBlocker", new Vector3(0.6f, 1.7f, 8.8f), new Vector3(s * 5.5f, 0.85f, 0f));
            Kit.Blocker(root, "HearthBlocker", new Vector3(3.2f, 1.2f, 2.4f), new Vector3(-4.0f, 0.6f, -3.2f));
        }

        // ================= 温室药圃 =================
        void BuildGreenhouse(Transform world)
        {
            var root = new GameObject("Greenhouse").transform;
            root.SetParent(world, false);
            root.localPosition = new Vector3(-34f, 0f, 16f);   // 西侧草坪：远离魔法塔基座（原 -27,26 与塔穿模。
            root.localRotation = Quaternion.Euler(0f, 180f, 0f);

            var v = new GameObject("Visual").transform;
            v.SetParent(root, false);
            var wood = M("timber_dark");
            var stone = M("stone_dark");

            Kit.Slab(v, "Plinth", new Vector3(10.2f, 0.24f, 7.4f), new Vector3(0f, 0.12f, 0f), M("cobble"));
            // 石基。+ 玻璃。
            Kit.Box(v, "BaseBack", new Vector3(10f, 0.9f, 0.4f), new Vector3(0f, 0.45f, -3.5f), stone, 0f, false);
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Box(v, "BaseSide", new Vector3(0.4f, 0.9f, 7.0f), new Vector3(s * 4.8f, 0.45f, 0f), stone, 0f, false);
                Kit.Box(v, "GlassSide", new Vector3(0.1f, 2.6f, 7.0f), new Vector3(s * 4.8f, 2.2f, 0f), M("glass"), 0f, false);
            }
            Kit.Box(v, "GlassBack", new Vector3(10f, 2.6f, 0.1f), new Vector3(0f, 2.2f, -3.5f), M("glass"), 0f, false);
            // 玻璃屋顶（人字）
            Kit.Mesh(v, "GlassRoof", Kit.GableRoofMesh(10.4f, 7.6f, 1.9f, 0.4f, 0.1f), new Vector3(0f, 3.5f, 0f), M("glass"), false);
            // 木框：立。+ 檐梁 + 屋脊
            for (int sx = -1; sx <= 1; sx += 2)
                for (int sz = -1; sz <= 1; sz += 2)
                    Kit.Box(v, "Post", new Vector3(0.2f, 3.6f, 0.2f), new Vector3(sx * 4.9f, 1.8f, sz * 3.5f), wood, 0f, false);
            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Box(v, "EaveSide", new Vector3(0.2f, 0.24f, 7.2f), new Vector3(s * 4.9f, 3.6f, 0f), wood, 0f, false);
                Kit.Box(v, "EaveFront", new Vector3(10.2f, 0.24f, 0.2f), new Vector3(0f, 3.6f, s * 3.5f), wood, 0f, false);
            }
            Kit.Box(v, "Ridge", new Vector3(10.4f, 0.22f, 0.24f), new Vector3(0f, 4.5f, 0f), wood, 0f, false);
            // 门（前脸左半边，右半边是玻璃。
            Kit.Box(v, "Door", new Vector3(1.4f, 2.6f, 0.16f), new Vector3(-3.2f, 1.7f, 3.55f), wood, 0f, false);
            Kit.Box(v, "GlassFront", new Vector3(7.6f, 2.6f, 0.1f), new Vector3(1.2f, 2.2f, 3.55f), M("glass"), 0f, false);
            Kit.Optimize(v.gameObject, false);
            Kit.MakeFadeable(v.gameObject, 0.42f);

            // 育苗。
            for (int i = 0; i < 3; i++)
            {
                float z = -2.2f + i * 2.0f;
                Kit.Box(root, "Bed" + i, new Vector3(8.2f, 0.55f, 1.1f), new Vector3(0f, 0.4f, z), M("wood_barrel"), 0f, true);
                Kit.Slab(root, "Soil" + i, new Vector3(8.0f, 0.06f, 0.95f), new Vector3(0f, 0.69f, z), M("dirt_dark"));
                for (int k = 0; k < 7; k++)
                    RoaKit.Flowers(root, new Vector3(-3.4f + k * 1.15f, 0.72f, z), i == 2 ? MapMaterials.ClothTeal : MapMaterials.ClothPurple);
            }
            RoaKit.Barrel(root, new Vector3(4.1f, 0f, 2.5f), 0f, 0.9f);
            Kit.Slab(root, "Water", new Vector3(0.8f, 0.05f, 0.8f), new Vector3(4.1f, 0.83f, 2.5f), M("water"));
            Kit.Cyl(root, "WateringCan", 0.22f, 0.34f, new Vector3(2.9f, 0.17f, 3.0f), M("iron"), 10, true);
            RoaKit.Pot(root, new Vector3(-4.2f, 0f, 3.0f), true);
            RoaKit.Pot(root, new Vector3(-4.6f, 0f, 2.2f), true);
            RoaKit.Sack(root, new Vector3(-4.3f, 0f, -2.6f), 30f);
            Kit.Box(root, "Table", new Vector3(2.0f, 0.12f, 1.0f), new Vector3(3.0f, 0.8f, -2.6f), M("wood_plank"), 0f, true);
            for (int s = -1; s <= 1; s += 2)
                Kit.Cyl(root, "TableLeg", 0.08f, 0.76f, new Vector3(3.0f + s * 0.8f, 0.38f, -2.6f), wood, 6, false);

            Sign(root, "温室 · 药草", new Vector3(0f, 3.95f, 3.66f), 0f, 2.6f, 0.5f);
            Sign(root, "温室 · 药草", new Vector3(0f, 3.95f, -3.66f), 180f, 2.6f, 0.5f);
            Kit.PointLight(root, new Vector3(0f, 2.6f, 0f), new Color(0.86f, 0.96f, 0.8f), 9f, 1.1f);
            for (int s = -1; s <= 1; s += 2)
                Kit.Blocker(root, "SideBlocker", new Vector3(0.5f, 3.4f, 7.2f), new Vector3(s * 4.8f, 1.7f, 0f));
            Kit.Blocker(root, "BackBlocker", new Vector3(10f, 3.4f, 0.5f), new Vector3(0f, 1.7f, -3.5f));
            Kit.Blocker(root, "BedBlocker", new Vector3(8.2f, 0.8f, 4.4f), new Vector3(0f, 0.4f, -0.2f));
        }

        // ================= 访客驿站（据。+ 商店。=================
        void BuildGuestHouse(Transform world)
        {
            var root = new GameObject("GuestHouse").transform;
            root.SetParent(world, false);

            var spec = HouseSpec.Townhouse();
            spec.Width = 9.4f;
            spec.Depth = 7.2f;
            spec.Floors = 2;
            spec.Balcony = true;
            spec.WallHeight = 3.0f;
            spec.RoofHeight = 2.2f;
            spec.Wall = "plaster_white";
            spec.Roof = "roof_blue";
            spec.Timber = "timber_dark";
            spec.Chimney = true;
            spec.Overhang = 0.55f;
            spec.Seed = 77;
            spec.Fadeable = false;
            spec.Sign = true;
            spec.SignText = "访客驿站";
            var house = RoaKit.House(root, spec, new Vector3(-28f, 0f, -38f), 0f);
            house.name = "GuestHouseBody";
            Kit.MakeFadeable(house, 0.3f);

            var yard = new GameObject("GuestYard").transform;
            yard.SetParent(root, false);
            Kit.Slab(yard, "Apron", new Vector3(11.5f, 0.07f, 3.4f), new Vector3(-28f, 0.035f, -33.2f), M("dirt"));
            RoaKit.Bench(yard, new Vector3(-32.4f, 0f, -33.0f), 180f, 1.7f);
            RoaKit.Bench(yard, new Vector3(-23.6f, 0f, -33.0f), 180f, 1.7f);
            RoaKit.Barrel(yard, new Vector3(-32.8f, 0f, -34.4f), 12f, 0.95f);
            RoaKit.Crate(yard, new Vector3(-23.2f, 0f, -34.6f), 18f, 0.9f);
            RoaKit.Sack(yard, new Vector3(-23.6f, 0f, -35.4f), 25f);
            Kit.Cyl(yard, "LanternPost", 0.1f, 2.6f, new Vector3(-22.6f, 1.3f, -33.0f), M("wood_dark"), 8, false);
            Kit.Box(yard, "Lantern", new Vector3(0.34f, 0.5f, 0.34f), new Vector3(-22.6f, 2.55f, -33.0f), M("glow_amber"), 0f, false);
            Kit.PointLight(yard, new Vector3(-22.6f, 2.6f, -32.6f), new Color(1f, 0.82f, 0.55f), 7f, 1.0f);

            Sign(yard, "访客登记 · 热汤与床位", new Vector3(-28f, 2.85f, -32.4f), 0f, 4.2f, 0.42f, M("cloth_cream").color, null);
            KitProps.Signpost(yard, new Vector3(-21.6f, 0f, -35.6f), 20f, "访客驿站 ↗", 0f);
        }

        // ================= 学生集市：旧书摊 / 炼金。/ 告示。=================
        void BuildStudentMarket(Transform world)
        {
            var market = new GameObject("StudentMarket").transform;
            market.SetParent(world, false);

            RoaKit.MarketStall(market, new Vector3(-12.5f, 0f, -18f), 90f, "cloth_purple");
            RoaKit.MarketStall(market, new Vector3(-17.5f, 0f, -18f), 90f, "cloth_teal");
            Sign(market, "旧书 · 星图", new Vector3(-12.5f, 2.62f, -16.4f), 90f, 2.2f, 0.42f);
            Sign(market, "炼金材料", new Vector3(-17.5f, 2.62f, -16.4f), 90f, 2.1f, 0.42f);

            // 书摊边的书堆 / 书车
            Kit.Box(market, "BookStackA", new Vector3(0.5f, 0.16f, 0.34f), new Vector3(-14.6f, 0.08f, -19.6f), M("cloth_red"), 12f, false);
            Kit.Box(market, "BookStackB", new Vector3(0.46f, 0.13f, 0.3f), new Vector3(-14.6f, 0.23f, -19.6f), M("cloth_blue"), -8f, false);
            Kit.Box(market, "BookStackC", new Vector3(0.42f, 0.12f, 0.28f), new Vector3(-14.55f, 0.36f, -19.6f), M("cloth_cream"), 20f, false);
            Kit.Box(market, "CrateBooks", new Vector3(0.9f, 0.8f, 0.7f), new Vector3(-14.4f, 0.4f, -21.0f), M("wood_dark"), 0f, true);
            RoaKit.Barrel(market, new Vector3(-19.4f, 0f, -20.2f), 0f, 0.85f);
            RoaKit.Sack(market, new Vector3(-10.6f, 0f, -20.6f), 30f);
            RoaKit.Crate(market, new Vector3(-10.8f, 0f, -16.2f), -10f, 0.85f);

            // 摊位两端的水晶灯
            RoaKit.Lamp(market, "MarketLampN", new Vector3(-9.2f, 0f, -20.4f), 0f, true);
            RoaKit.Lamp(market, "MarketLampS", new Vector3(-20.8f, 0f, -20.4f), 0f, false);

            NoticeBoard(market, new Vector3(-15.2f, 0f, -13.6f), 0f, "学园通告");
        }

        // ================= 校园生活细节 =================
        void BuildCampusLife(Transform world)
        {
            var life = new GameObject("CampusLife").transform;
            life.SetParent(world, false);

            // 跨大道的挂旗（立柱落在大道两侧）
            RoaKit.Bunting(life, new Vector3(0f, 0f, -22f), 0f, 14f);
            RoaKit.Bunting(life, new Vector3(0f, 0f, -4f), 0f, 14f);
            RoaKit.Bunting(life, new Vector3(0f, 0f, 6f), 0f, 14f);

            // 路灯：沿大道两侧（柱脚在大道外，|x| > 6.5。
            float[] lz = { -20f, -13f, 2f, 9f };
            for (int i = 0; i < lz.Length; i++)
            {
                bool east = i % 2 == 0;
                RoaKit.Lamp(life, "Lamp" + i, new Vector3(east ? 7.4f : -7.4f, 0f, lz[i]), 0f, i % 2 == 0);
            }

            // 宿舍外的晾衣绳（挂在宿舍与步道之间）
            LaundryLine(life, new Vector3(22.4f, 0f, -34f), 90f, 5.0f);
            LaundryLine(life, new Vector3(22.4f, 0f, -10f), 90f, 5.0f);

            // 食堂/温室/驿站门口的货。
            RoaKit.Crate(life, new Vector3(27.2f, 0f, 5.6f), 12f, 0.9f);
            RoaKit.Barrel(life, new Vector3(27.8f, 0f, 6.6f), 0f, 0.9f);
            RoaKit.Sack(life, new Vector3(-35.6f, 0f, 11.4f), 20f);
            RoaKit.Crate(life, new Vector3(-32.6f, 0f, 11.2f), -14f, 0.85f);
            RoaKit.Haystack(life, new Vector3(-37.4f, 0f, 11.0f), 0.9f);
            RoaKit.Barrel(life, new Vector3(24.6f, 0f, -30.6f), 10f, 0.85f);

            // 主楼台阶两侧的盆。
            for (int s = -1; s <= 1; s += 2)
            {
                RoaKit.Pot(life, new Vector3(s * 3.2f, 0f, 13.4f), true);
                RoaKit.Pot(life, new Vector3(s * 4.4f, 0f, 13.0f), true);
            }

            // 大道上的水洼（纯视觉。
            Kit.Slab(life, "Puddle1", new Vector3(1.7f, 0.02f, 0.9f), new Vector3(2.4f, 0.035f, -26.4f), M("water"));
            Kit.Slab(life, "Puddle2", new Vector3(1.3f, 0.02f, 1.0f), new Vector3(-2.8f, 0.035f, -8.2f), M("water"));

            // 指路。
            KitProps.Signpost(life, new Vector3(6.9f, 0f, -30.6f), -20f, "食堂 →   观星台 ↗", 0f);
            KitProps.Signpost(life, new Vector3(-7.2f, 0f, 4.6f), 160f, "图书馆 ↓   宿舍 →", 0f);

            // 额外的魔。/ 草药 / 金币（给新区域一点奖励）
            PickupInteractable.Create(world, new Vector3(-30.2f, 0f, -7.6f), PickupKind.Crystal, 0, null, "academy_crystal_4");
            PickupInteractable.Create(world, new Vector3(-36.6f, 0f, 10.4f), PickupKind.Herb, 0, null, null);
            PickupInteractable.Create(world, new Vector3(24.4f, 0f, 12.6f), PickupKind.Coin, 12, null, "academy_coin_3");
        }

        /// <summary>一根晾衣绳：两根木。+ 绳子 + 几块布，整根合并成一个渲染。/summary>
        void LaundryLine(Transform parent, Vector3 center, float yaw, float length)
        {
            var root = new GameObject("LaundryLine").transform;
            root.SetParent(parent, false);
            root.localPosition = center;
            root.localRotation = Quaternion.Euler(0f, yaw, 0f);
            float half = length * 0.5f;

            for (int s = -1; s <= 1; s += 2)
            {
                Kit.Cyl(root, "Pole", 0.08f, 2.7f, new Vector3(s * half, 1.35f, 0f), M("wood_dark"), 6, false);
                Kit.Box(root, "PoleCap", new Vector3(0.24f, 0.14f, 0.24f), new Vector3(s * half, 2.72f, 0f), M("wood_dark"), 0f, false);
            }
            Kit.Slab(root, "Rope", new Vector3(length, 0.035f, 0.035f), new Vector3(0f, 2.5f, 0f), M("timber_mid"));

            string[] cloths = { "cloth_cream", "cloth_purple", "cloth_blue", "cloth_teal" };
            int n = Mathf.Max(2, Mathf.RoundToInt(length / 1.5f));
            for (int i = 0; i < n; i++)
            {
                float x = -half + (i + 0.5f) * (length / n);
                Kit.Slab(root, "Cloth" + i, new Vector3(0.9f, 1.0f, 0.045f),
                    new Vector3(x, 1.94f, 0.02f), M(cloths[i % cloths.Length]));
            }
            Kit.Optimize(root.gameObject, false);
        }

        /// <summary>学园告示板：石柱 + 板面 + 檐口 + 贴纸。/summary>
        void NoticeBoard(Transform parent, Vector3 pos, float yaw, string text)
        {
            var root = new GameObject("NoticeBoard").transform;
            root.SetParent(parent, false);
            root.localPosition = pos;
            root.localRotation = Quaternion.Euler(0f, yaw, 0f);

            for (int s = -1; s <= 1; s += 2)
                Kit.Cyl(root, "Post", 0.11f, 2.3f, new Vector3(s * 0.9f, 1.15f, 0f), M("stone_dark"), 8, true);
            Kit.Box(root, "BoardBack", new Vector3(2.2f, 1.4f, 0.1f), new Vector3(0f, 1.75f, 0f), M("timber_dark"), 0f, true);
            Kit.Box(root, "BoardFace", new Vector3(2.04f, 1.26f, 0.04f), new Vector3(0f, 1.75f, 0.07f), M("sand"), 0f, false);
            Kit.Box(root, "Eave", new Vector3(2.5f, 0.12f, 0.55f), new Vector3(0f, 2.5f, 0.1f), M("roof_slate"), 0f, false);
            for (int i = 0; i < 4; i++)
                Kit.Box(root, "Paper" + i, new Vector3(0.24f, 0.3f, 0.012f),
                    new Vector3(-0.6f + (i % 2) * 1.1f, 1.92f - (i / 2) * 0.42f, 0.1f), M("cloth_cream"), 0f, false);
            Sign(root, text, new Vector3(0f, 2.76f, 0.04f), 0f, 2.0f, 0.36f);
            Kit.Optimize(root.gameObject, false);
            Kit.Blocker(root, "BoardBlocker", new Vector3(2.2f, 1.4f, 0.3f), new Vector3(0f, 1.75f, 0f));
        }
    }
}


