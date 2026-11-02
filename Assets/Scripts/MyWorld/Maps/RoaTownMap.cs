using UnityEngine;

namespace MyWorld.Maps
{
    /// <summary>
    /// 罗亚市（Roa Town）——《无职转生》风格的中世纪主城。
    ///
    /// 布局（世界坐标：+X 东、+Z 北、Y 向上）：
    ///   · 南门（CastleGate, z=-46）→ 中央广场（喷泉 + 英雄雕像, z≈3..16）
    ///   · 主干道两侧是商店街（杂货 / 魔法用品 / 面包房 / 裁缝 + 旅店）
    ///   · 北端台地是冒险者协会（地标，门口有委托板与接待员）
    ///   · 东西两侧是民居街区（石板副街 + 水井小广场）
    ///   · 六座市场摊位、五道挂旗、二十盏路灯，城内有内城墙与角楼
    ///   · 两个 ScenePortal：南门外通布耶纳村，东侧魔法阵通拉诺亚魔法学院
    ///
    /// 所有视觉物件先造好，再按组调用 RoaKit.Batch 合批（合批会销毁子物体与子碰撞体），
    /// 因此招牌、点光源、碰撞体一律在合批之后追加。
    /// </summary>
    public class RoaTownMap : MapBootstrap
    {
        // ================= 布局常量 =================
        const float GateZ = -46f;      // 南门中心
        const float PlazaZ = 6f;       // 中央广场圆心
        const float PlazaR = 17.4f;    // 中央广场半径
        const float GuildZ = 34f;      // 冒险者协会中心
        const float ShopX = 16.5f;     // 商店街两侧店铺中心 X
        const float HouseX = 42f;      // 民居排中心 X
        const float LaneX = 33f;       // 南北副街中心 X
        const float WallX = 46f;       // 内城墙 X
        const float WallN = 45f;       // 内城墙北 Z

        // ================= 台词 =================
        static readonly string[] LinesGuild =
        {
            "欢迎来到罗亚市冒险者协会。",
            "门口的委托板上贴着最新的委托，先挑一件合手的吧。",
            "新人的话，从城外那几只史莱姆开始最稳妥。",
        };

        static readonly string[] LinesGeneral =
        {
            "罗亚商会，杂货齐全。",
            "药水、口粮、绳子，出门前都备一点。",
            "最近商队来得勤，价格还算公道。",
        };

        static readonly string[] LinesMagic =
        {
            "欢迎，魔法用品都在架子上。",
            "魔力墨水是学院那边送来的货。",
            "施法前记得检查法杖，别在城外炸了手。",
        };

        static readonly string[] LinesBakery =
        {
            "刚出炉的面包，还热着呢。",
            "面粉是今早从布耶纳村运来的。",
            "冒险者出门带两条，比干粮强。",
        };

        static readonly string[] LinesTailor =
        {
            "要补斗篷还是做新外套？",
            "皮料和线团都有，尺寸量一下就行。",
            "挂着的样衣可以摸，别扯坏就行。",
        };

        static readonly string[] LinesInn =
        {
            "旅店「炉火与麦酒」，一晚八枚铜币。",
            "壁炉边上的位子最抢手，早点回来。",
            "要打听消息？酒馆里总有说得比唱得好听的家伙。",
        };

        static readonly string[] LinesGuard =
        {
            "城门内外都归我们管，别惹事。",
            "出城小心魔物，最近林子那边不太平。",
            "城里可以随便逛，武器收好就行。",
        };

        static readonly string[] LinesGuardGate =
        {
            "进城登记一下……算了，看你像是正经冒险者。",
            "协会就在大道尽头，很好找。",
        };

        static readonly string[] LinesVendor =
        {
            "新鲜果子，今早刚摘的！",
            "看看这布料，从北方运来的。",
            "铜币也好，以物易物也成。",
        };

        static readonly string[] LinesVillagerA =
        {
            "广场的喷泉是罗亚市的心脏。",
            "傍晚时分，卖艺的会在喷泉边唱歌。",
        };

        static readonly string[] LinesVillagerB =
        {
            "我在这城里住了四十年。",
            "协会那栋楼以前是领主的宅子，你信不信？",
        };

        static readonly string[] LinesVillagerC =
        {
            "学园传送阵就在东边，魔法师都从那儿走。",
            "听说今年的新生里有位很了不起的姑娘。",
        };

        static readonly string[] LinesVillagerD =
        {
            "马厩在集市那头，牲口比人还金贵。",
            "别踩到地上的菜叶，摊主会瞪你的。",
        };

        static readonly string[] LinesVillagerE =
        {
            "巡逻就是绕着城墙走一圈，无聊得很。",
            "东墙的石头去年刚修过。",
        };

        static readonly string[] LinesScholar =
        {
            "我在等学园的马车。",
            "传送阵偶尔会闪，那是正常的魔力波动。",
        };

        static readonly string[] LinesKid =
        {
            "嘘——我在数石板，数到一百就回家。",
            "你见过协会门口的雕像吗？比城门还高！",
        };

        static readonly string[] LinesTrainer =
        {
            "草人不会还手，先把挥剑的姿势练顺。",
            "协会的训练场谁都能用，别把靶子劈了就行。",
            "想出城接委托？先在我这儿过三招。",
        };

        static readonly string[] LinesSpice =
        {
            "香料、干果、南边来的茶叶，都在这儿。",
            "闻闻这个，炖肉放一撮，整条街都香。",
        };

        static readonly string[] LinesCloth =
        {
            "布匹按尺卖，颜色自己挑。",
            "这批羊毛是布耶纳村送来的，结实。",
        };

        static readonly string[] LinesPotter =
        {
            "陶罐、水壶、小炉子，样样都有。",
            "轻拿轻放，摔了可要照价赔。",
        };

        // ================= 环境 =================

        protected override void BuildEnvironment(Transform world)
        {
            var ground = Node(world, "Ground");
            // 城市里铺装覆盖了中央区域，外围保留草地；地面必须保留 BoxCollider。
            Box(ground, "GroundPlate", new Vector3(0f, -0.5f, 0f), new Vector3(120f, 1f, 120f),
                MapMaterials.Get("grass"), 0f, true);
            BuildBoundary(world, 3.0f);
        }

        protected override void BuildMapContent(Transform world)
        {
            BuildPaving(world);
            BuildCityWalls(world);
            BuildLandmarks(world);
            BuildGuildPrecinct(world);
            BuildShopStreet(world);
            BuildResidential(world);
            BuildMarket(world);
            BuildGatehouse(world);
            BuildTravel(world);
            BuildStreetDetails(world);
            BuildNature(world);
            BuildNpcs(world);
            Debug.Log("[RoaTown] 罗亚市生成完成");
        }

        // ================= 铺装 =================

        void BuildPaving(Transform world)
        {
            var root = Node(world, "Paving");
            var cobble = MapMaterials.Get("cobble");
            var stoneLight = MapMaterials.Get("stone_light");
            var stoneWall = MapMaterials.Get("stone_wall");
            var marble = MapMaterials.Get("marble");

            // 主干道：南门 → 协会前
            Box(root, "Avenue", new Vector3(0f, 0.02f, -9.5f), new Vector3(20f, 0.04f, 73f), cobble, 0f, false);
            // 城门前广场 + 城外驿道（避免与主干道共面 z-fighting）
            Box(root, "GateApron", new Vector3(0f, 0.03f, -45f), new Vector3(34f, 0.04f, 8f), cobble, 0f, false);
            Box(root, "ApproachRoad", new Vector3(0f, 0.03f, -55f), new Vector3(11f, 0.04f, 11f), stoneWall, 0f, false);
            // 南北副街（民居区）
            Box(root, "LaneWest", new Vector3(-LaneX, 0.02f, -8f), new Vector3(6f, 0.04f, 76f), stoneWall, 0f, false);
            Box(root, "LaneEast", new Vector3(LaneX, 0.02f, -8f), new Vector3(6f, 0.04f, 76f), stoneWall, 0f, false);
            // 东西向集市巷（略低，避免与主干道共面）+ 旅店巷（正好接上主干道）
            Box(root, "LaneMarket", new Vector3(0f, 0.015f, -28f), new Vector3(92f, 0.04f, 6f), stoneWall, 0f, false);
            Box(root, "LaneInnWest", new Vector3(-28f, 0.02f, 15f), new Vector3(36f, 0.04f, 6f), stoneWall, 0f, false);
            Box(root, "LaneInnEast", new Vector3(28f, 0.02f, 15f), new Vector3(36f, 0.04f, 6f), stoneWall, 0f, false);
            // 协会前庭（略高，压住广场石板边缘）
            Box(root, "GuildForecourt", new Vector3(0f, 0.04f, 25f), new Vector3(22f, 0.06f, 8f), stoneLight, 0f, false);
            // 学园魔法阵小径
            Box(root, "AcademyPath", new Vector3(LaneX + 4f, 0.03f, 19.5f), new Vector3(4f, 0.04f, 15f), stoneWall, 0f, false);

            // 广场铺装：外圈石板 + 内圈大理石
            RoaKit.FloorDisc(root, "PlazaFloor", PlazaR, new Vector3(0f, 0.05f, PlazaZ), stoneLight);
            RoaKit.FloorDisc(root, "PlazaInlay", 9.4f, new Vector3(0f, 0.07f, PlazaZ), marble);
            RoaKit.FloorDisc(root, "GateSquare", 9f, new Vector3(0f, 0.06f, -42f), stoneLight);
            RoaKit.FloorDisc(root, "WellSquare", 5f, new Vector3(-LaneX, 0.05f, PlazaZ), stoneLight);
            RoaKit.FloorDisc(root, "InnSquare", 5.5f, new Vector3(-24f, 0.05f, 15f), stoneLight);
            RoaKit.FloorDisc(root, "AcademyPad", 5.6f, new Vector3(LaneX + 4f, 0.06f, 27f), marble);
            RoaKit.FloorDisc(root, "VillagePad", 4.6f, new Vector3(0f, 0.07f, -53f), stoneLight);

            int batches = RoaKit.Batch(root.gameObject, false);
            Debug.Log("[RoaTown] 铺装合批 " + batches + " 组");
        }

        // ================= 内城墙与角楼 =================

        void BuildCityWalls(Transform world)
        {
            var root = Node(world, "CityWalls");
            var walls = Node(root, "Walls");
            // 南墙（城门两侧，门洞 x ±7.6）
            RoaKit.Wall(walls, new Vector3(27.8f, 0f, GateZ), 0f, 40.4f, 5.4f);
            RoaKit.Wall(walls, new Vector3(-27.8f, 0f, GateZ), 0f, 40.4f, 5.4f);
            // 北墙
            RoaKit.Wall(walls, new Vector3(23f, 0f, WallN), 0f, 46f, 5.4f);
            RoaKit.Wall(walls, new Vector3(-23f, 0f, WallN), 0f, 46f, 5.4f);
            // 东西墙（每侧三段）
            for (int i = 0; i < 3; i++)
            {
                float z = -31f + i * 31f;
                RoaKit.Wall(walls, new Vector3(WallX, 0f, z), 90f, 31f, 5.4f);
                RoaKit.Wall(walls, new Vector3(-WallX, 0f, z), 90f, 31f, 5.4f);
            }

            var towers = Node(root, "Towers");
            RoaKit.Tower(towers, new Vector3(11.2f, 0f, GateZ));
            RoaKit.Tower(towers, new Vector3(-11.2f, 0f, GateZ));
            RoaKit.Tower(towers, new Vector3(WallX, 0f, GateZ));
            RoaKit.Tower(towers, new Vector3(-WallX, 0f, GateZ));
            RoaKit.Tower(towers, new Vector3(WallX, 0f, WallN));
            RoaKit.Tower(towers, new Vector3(-WallX, 0f, WallN));
            RoaKit.Tower(towers, new Vector3(WallX, 0f, 0f));
            RoaKit.Tower(towers, new Vector3(-WallX, 0f, 0f));
        }

        // ================= 地标：协会 / 喷泉 / 雕像 / 水井 =================

        void BuildLandmarks(Transform world)
        {
            var root = Node(world, "Landmarks");
            // 冒险者协会：正面朝南（-Z），门前台阶一直伸到 z≈26.4
            RoaKit.GuildHall(root, new Vector3(0f, 0f, GuildZ), 180f);
            // 中央广场：喷泉 + 英雄雕像
            RoaKit.Fountain(root, new Vector3(0f, 0f, 3f));
            RoaKit.Statue(root, new Vector3(0f, 0f, 16f), 180f);
            // 水井小广场（西副街）
            RoaKit.Well(root, new Vector3(-LaneX, 0f, PlazaZ), 20f);

            // 广场家具与花坛
            var deck = Node(root, "PlazaDeck");
            RoaKit.Bench(deck, new Vector3(-9f, 0f, 9f), 90f, 2.2f);
            RoaKit.Bench(deck, new Vector3(9f, 0f, 11f), -90f, 2.2f);
            RoaKit.Bench(deck, new Vector3(-5.4f, 0f, -8.6f), 20f, 2.0f);
            RoaKit.Bench(deck, new Vector3(-LaneX + 2.2f, 0f, PlazaZ - 2.6f), -20f, 1.8f);
            RoaKit.Bench(deck, new Vector3(-11.6f, 0f, 18.4f), -60f, 1.8f);

            RoaKit.Flowers(deck, new Vector3(5.6f, 0f, 7.6f), new Color(0.92f, 0.35f, 0.42f));
            RoaKit.Flowers(deck, new Vector3(0f, 0f, 9.6f), new Color(0.95f, 0.82f, 0.36f));
            RoaKit.Flowers(deck, new Vector3(-5.6f, 0f, 7.6f), new Color(0.68f, 0.45f, 0.92f));
            RoaKit.Flowers(deck, new Vector3(-5.2f, 0f, -1.4f), new Color(0.95f, 0.95f, 0.92f));
            RoaKit.Flowers(deck, new Vector3(5.2f, 0f, -1.4f), new Color(0.94f, 0.55f, 0.25f));
            RoaKit.Bush(deck, new Vector3(3.2f, 0f, 14.2f), 1.1f);
            RoaKit.Bush(deck, new Vector3(-3.2f, 0f, 14.2f), 1.1f);

            // 协会门前路灯（低亮度，主要靠门廊灯笼）
            RoaKit.Lamp(deck, "LampGuildW", new Vector3(-8.2f, 0f, 23.6f), 0f, false);
            RoaKit.Lamp(deck, "LampGuildE", new Vector3(8.2f, 0f, 23.6f), 0f, false);

            // 水井旁杂物
            RoaKit.Barrel(deck, new Vector3(-30.6f, 0f, 3.4f), 15f);
            RoaKit.Pot(deck, new Vector3(-34.8f, 0f, 3.6f), true);
            RoaKit.Lamp(deck, "LampWell", new Vector3(-30.4f, 0f, 8.2f), 0f, true);
        }

        // ================= 冒险者协会前庭（地标强化） =================
        // 协会本身是 RoaKit.GuildHall（18×11，正面朝南），这里补的是"一进门就认得出"的
        // 前庭：抬高石台 + 方柱 + 横幅 + 公告墙 + 训练场 + 纪念碑 + 火光。

        void BuildGuildPrecinct(Transform world)
        {
            var root = Node(world, "GuildPrecinct");
            var stone = MapMaterials.Get("stone_light");
            var stoneDark = MapMaterials.Get("stone_dark");
            var marble = MapMaterials.Get("marble");
            var timber = MapMaterials.Get("timber_dark");
            var iron = MapMaterials.Get("iron");

            // 中轴大理石引道：广场北缘 → 协会大台阶
            Box(root, "GuildPath", new Vector3(0f, 0.03f, 25.3f), new Vector3(7.6f, 0.06f, 6.2f), marble, 0f, false);
            // 两侧抬高石台，把协会"托"起来
            Box(root, "GuildPlinthW", new Vector3(-11.6f, 0.24f, 29.4f), new Vector3(5.2f, 0.48f, 6.4f), stone, 0f, true);
            Box(root, "GuildPlinthE", new Vector3(11.6f, 0.24f, 29.4f), new Vector3(5.2f, 0.48f, 6.4f), stone, 0f, true);

            // 石台上的方柱 + 柱顶火盆 + 面向广场的横幅
            for (int s = -1; s <= 1; s += 2)
            {
                var side = Node(root, s < 0 ? "PlinthW" : "PlinthE");
                for (int i = 0; i < 2; i++)
                {
                    float z = 27.2f + i * 4.4f;
                    Box(side, "Base" + i, new Vector3(s * 11.6f, 0.66f, z), new Vector3(1.9f, 0.4f, 1.9f), stoneDark, 0f, false);
                    Box(side, "Pillar" + i, new Vector3(s * 11.6f, 3.4f, z), new Vector3(1.5f, 6.8f, 1.5f), stone, 0f, true);
                    Box(side, "Cap" + i, new Vector3(s * 11.6f, 6.9f, z), new Vector3(1.9f, 0.34f, 1.9f), stoneDark, 0f, false);
                    Brazier(side, "GuildBrazier" + (s < 0 ? "W" : "E") + i, new Vector3(s * 11.6f, 7.07f, z));
                }
                Box(side, "Banner", new Vector3(s * 11.6f, 4.5f, 26.14f), new Vector3(4.2f, 3.0f, 0.12f),
                    MapMaterials.Get(s < 0 ? "cloth_red" : "cloth_blue"), 0f, false);
            }

            // 委托公告墙（门前东侧）+ 可交互委托板
            Box(root, "NoticeWall", new Vector3(9.0f, 1.5f, 25.85f), new Vector3(5.6f, 3.0f, 0.42f), stoneDark, 0f, true);
            Box(root, "NoticeLedge", new Vector3(9.0f, 3.1f, 25.85f), new Vector3(6.0f, 0.24f, 0.62f), stone, 0f, false);
            Kit.SignBoard(root, "罗亚市冒险者协会", new Vector3(9.0f, 2.62f, 25.6f), 180f, 4.4f, 0.6f);
            Kit.SignBoard(root, "委托 · 讨伐 · 采集", new Vector3(9.0f, 1.98f, 25.6f), 180f, 3.0f, 0.42f);
            QuestBoardInteractable.CreateStand(root, new Vector3(9.0f, 0f, 24.5f), "roa_guild", 180f);

            // 纪念碑：英雄之剑（西侧）
            var mon = Node(root, "Monument");
            Box(mon, "Pedestal", new Vector3(-8.6f, 0.5f, 24.4f), new Vector3(2.0f, 1.0f, 2.0f), stone, 0f, true);
            Box(mon, "PedestalCap", new Vector3(-8.6f, 1.06f, 24.4f), new Vector3(2.3f, 0.16f, 2.3f), stoneDark, 0f, false);
            Cyl(mon, "Blade", new Vector3(-8.6f, 2.1f, 24.4f), new Vector3(0.22f, 0.95f, 0.22f), MapMaterials.Get("steel"), 0f, false);
            Box(mon, "Guard", new Vector3(-8.6f, 3.05f, 24.4f), new Vector3(1.1f, 0.16f, 0.26f), MapMaterials.Get("gold"), 0f, false);
            Cyl(mon, "Grip", new Vector3(-8.6f, 3.3f, 24.4f), new Vector3(0.14f, 0.2f, 0.14f), MapMaterials.Get("gold"), 0f, false);

            // 训练场：东侧沙地 + 木栅 + 三名草人 + 武器架 + 靶子
            var yard = Node(root, "TrainingYard");
            RoaKit.FloorDisc(yard, "YardSand", 4.8f, new Vector3(18.6f, 0.05f, 30.6f), MapMaterials.Get("sand"), 30);
            for (int i = 0; i < 8; i++)
            {
                float a = i * 45f;
                Vector3 p = KitMath.OnCircle(4.6f, a) + new Vector3(18.6f, 0f, 30.6f);
                if (p.x < 14.2f) continue;      // 靠协会一侧留出入口
                Box(yard, "FencePost" + i, p + new Vector3(0f, 0.55f, 0f), new Vector3(0.16f, 1.1f, 0.16f), timber, 0f, true);
                Box(yard, "FenceRail" + i, p + new Vector3(0f, 0.85f, 0f), new Vector3(0.1f, 0.1f, 3.6f), timber, a + 90f, false);
            }
            var straw = MapMaterials.Get("roof_thatch");
            for (int i = 0; i < 3; i++)
            {
                var d = Node(yard, "Dummy" + i);
                Vector3 p = new Vector3(16.4f + i * 2.2f, 0f, 28.4f - i * 0.9f);
                Box(d, "Post", p + new Vector3(0f, 0.9f, 0f), new Vector3(0.18f, 1.8f, 0.18f), timber, 0f, true);
                Box(d, "Arm", p + new Vector3(0f, 1.52f, 0f), new Vector3(1.5f, 0.14f, 0.14f), timber, 0f, false);
                Cyl(d, "Torso", p + new Vector3(0f, 1.22f, 0f), new Vector3(0.72f, 0.48f, 0.72f), straw);
                Sphere(d, "Head", p + new Vector3(0f, 1.95f, 0f), new Vector3(0.42f, 0.42f, 0.42f), straw);
            }
            Box(yard, "RackTop", new Vector3(21.6f, 1.08f, 32.4f), new Vector3(2.6f, 0.14f, 0.5f), timber, 0f, true);
            for (int i = 0; i < 3; i++)
                Cyl(yard, "Spear" + i, new Vector3(20.6f + i * 1.0f, 1.7f, 32.4f), new Vector3(0.07f, 1.7f, 0.07f),
                    MapMaterials.Get("wood_plank"), 0f, false);
            for (int i = 0; i < 2; i++)
            {
                var tg = Node(yard, "Target" + i);
                Vector3 p = new Vector3(16.2f + i * 4.4f, 0f, 33.8f);
                Box(tg, "Post", p + new Vector3(0f, 0.8f, 0f), new Vector3(0.18f, 1.6f, 0.18f), timber, 0f, true);
                Box(tg, "Board", p + new Vector3(0f, 1.7f, 0f), new Vector3(1.15f, 1.15f, 0.16f), MapMaterials.Get("wood_plank"), 0f, true);
                Box(tg, "Bull", p + new Vector3(0f, 1.7f, -0.12f), new Vector3(0.5f, 0.5f, 0.06f), MapMaterials.Get("cloth_red"), 0f, false);
            }
            RoaKit.Haystack(yard, new Vector3(22.4f, 0f, 28.2f), 0.9f);
            RoaKit.Bench(yard, new Vector3(15.2f, 0f, 33.4f), 180f, 2.0f);

            // 前庭旗杆（红蓝交替，广场上一眼能认出）
            for (int i = 0; i < 4; i++)
            {
                float x = -13.2f + i * 8.8f;
                Cyl(root, "GuildFlagPole" + i, new Vector3(x, 3.2f, 23.9f), new Vector3(0.14f, 3.2f, 0.14f), iron, 0f, true);
                Box(root, "GuildFlag" + i, new Vector3(x + 0.95f, 5.5f, 23.9f), new Vector3(1.8f, 1.15f, 0.06f),
                    MapMaterials.Get(i % 2 == 0 ? "cloth_red" : "cloth_blue"), 0f, false);
            }
            RoaKit.Bush(root, new Vector3(-15.4f, 0f, 25.6f), 1.1f);
            RoaKit.Bush(root, new Vector3(15.4f, 0f, 25.4f), 1.0f);
        }

        /// <summary>石柱火盆：柱顶的一小簇暖光（合批之后加，光源不受 Batch 影响）。</summary>
        void Brazier(Transform parent, string name, Vector3 pos)
        {
            Cyl(parent, name + "_Bowl", pos + new Vector3(0f, 0.18f, 0f), new Vector3(0.9f, 0.18f, 0.9f),
                MapMaterials.Get("stone_dark"), 0f, false);
            Cyl(parent, name + "_Coal", pos + new Vector3(0f, 0.42f, 0f), new Vector3(0.62f, 0.08f, 0.62f),
                MapMaterials.Emissive("roa_guild_ember", new Color(1f, 0.56f, 0.2f), 2.6f), 0f, false);
            var go = new GameObject(name + "_Light");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos + new Vector3(0f, 0.55f, 0f);
            var l = go.AddComponent<Light>();
            l.type = LightType.Point;
            l.range = 9f;
            l.intensity = 1.6f;
            l.color = new Color(1f, 0.74f, 0.44f);
            l.shadows = LightShadows.None;
        }

        // ================= 商店街 =================

        void BuildShopStreet(Transform world)
        {
            var root = Node(world, "ShopStreet");
            var inn = Node(root, "Inn");

            // 西侧西向街面（正面朝东 = +X）
            PlaceShop(root, "General", "罗亚商会 · 杂货", ShopKind.General, -ShopX, -38f, 90f,
                8f, 6.5f, "plaster_cream", "plaster_warm", "roof_terracotta", "cloth_blue", true);
            PlaceShop(root, "Magic", "米莉的魔法用品", ShopKind.Magic, -ShopX, -18f, 90f,
                7.6f, 6.4f, "plaster_grey", "plaster_ochre", "roof_teal", "cloth_purple", false);
            // 东侧街面（正面朝西 = -X）
            PlaceShop(root, "Bakery", "甜麦面包房", ShopKind.Bakery, ShopX, -38f, -90f,
                8f, 6.4f, "plaster_white", "plaster_cream", "roof_thatch", "cloth_orange", true);
            PlaceShop(root, "Tailor", "线团与扣子", ShopKind.Tailor, ShopX, -18f, -90f,
                7.6f, 6.4f, "plaster_salmon", "plaster_warm", "roof_burgundy", "cloth_green", true);

            // 旅店：西侧，正面朝东
            RoaKit.Inn(inn, new Vector3(-20f, 0f, 14f), 90f);
            RoaKit.Barrel(inn, new Vector3(-13.4f, 0f, 8.2f), 10f);
            RoaKit.Sack(inn, new Vector3(-13.9f, 0f, 9.0f), -20f);
            RoaKit.Pot(inn, new Vector3(-14.2f, 0f, 17.6f), true);
            RoaKit.Bench(inn, new Vector3(-13.4f, 0f, 16.8f), -90f, 1.8f);
            RoaKit.Lamp(inn, "LampInnN", new Vector3(-13.6f, 0f, 19.8f), 0f, true);
            RoaKit.Lamp(inn, "LampInnS", new Vector3(-13.6f, 0f, 8.4f), 0f, false);

            // 商店街与广场之间补几栋沿街民居，制造连续的街墙
            var row = Node(root, "StreetHouses");
            PlaceHouse(row, Spec("plaster_ochre", "roof_slate", "timber_dark", 2, true, 6.4f, 5.4f),
                "HouseStreetW1", -17.5f, -8f, 90f);
            PlaceHouse(row, Spec("plaster_warm", "roof_terracotta", "timber_mid", 2, true, 6.4f, 5.4f),
                "HouseStreetE1", 17.5f, 2f, -90f);
            PlaceHouse(row, Spec("plaster_cream", "roof_thatch", "timber_light", 1, false, 5.6f, 4.6f),
                "HouseStreetE2", 17.5f, 12f, -90f);
            PlaceHouse(row, Spec("plaster_grey", "roof_blue", "timber_dark", 2, true, 6.4f, 5.4f),
                "HouseStreetE3", 17.5f, 22f, -90f);
            PlaceHouse(row, Spec("plaster_salmon", "roof_terracotta", "timber_mid", 1, false, 5.8f, 4.8f),
                "HouseStreetW2", -17.5f, 24f, 90f);

            // 店门口的箱子、木桶与堆货（商业密度）
            var props = Node(root, "ShopProps");
            // 杂货店（西，z=-38）
            RoaKit.Barrel(props, new Vector3(-12.4f, 0f, -41.6f), 12f);
            RoaKit.Barrel(props, new Vector3(-13.2f, 0f, -40.7f), -30f);
            RoaKit.Crate(props, new Vector3(-13.4f, 0f, -41.8f), 16f);
            RoaKit.Crate(props, new Vector3(-13.3f, 0.62f, -41.7f), 28f);
            RoaKit.Sack(props, new Vector3(-12.2f, 0f, -40.0f), 8f);
            RoaKit.Crate(props, new Vector3(-13.2f, 0f, -33.4f), 8f);
            RoaKit.Barrel(props, new Vector3(-12.4f, 0f, -32.6f), -12f);
            // 魔法用品店（西，z=-18）
            RoaKit.Crate(props, new Vector3(-13.5f, 0f, -21.4f), 14f);
            RoaKit.Crate(props, new Vector3(-13.4f, 0.62f, -21.3f), -22f);
            RoaKit.Pot(props, new Vector3(-12.4f, 0f, -20.5f), true);
            RoaKit.Pot(props, new Vector3(-12.6f, 0f, -21.4f), false);
            RoaKit.Sack(props, new Vector3(-12.6f, 0f, -13.6f), 18f);
            RoaKit.Barrel(props, new Vector3(-13.3f, 0f, -12.8f), 6f);
            // 面包房（东，z=-38）
            RoaKit.Barrel(props, new Vector3(12.4f, 0f, -41.4f), -14f);
            RoaKit.Sack(props, new Vector3(13.2f, 0f, -40.6f), 12f);
            RoaKit.Sack(props, new Vector3(12.6f, 0f, -39.8f), -25f);
            RoaKit.Crate(props, new Vector3(13.4f, 0f, -41.6f), -10f);
            RoaKit.Crate(props, new Vector3(13.3f, 0.62f, -41.5f), 20f);
            RoaKit.Barrel(props, new Vector3(13.3f, 0f, -32.6f), 20f);
            // 裁缝店（东，z=-18）
            RoaKit.Crate(props, new Vector3(13.4f, 0f, -21.2f), 10f);
            RoaKit.Crate(props, new Vector3(13.3f, 0.62f, -21.1f), -18f);
            RoaKit.Pot(props, new Vector3(12.5f, 0f, -20.4f), true);
            RoaKit.Sack(props, new Vector3(12.6f, 0f, -13.4f), -8f);
            RoaKit.Barrel(props, new Vector3(13.3f, 0f, -12.6f), 24f);

            // 店铺立面上的挑旗（沿街一眼能看出是商铺）
            var banners = Node(root, "ShopBanners");
            ShopBanner(banners, "BannerGeneral", -13.6f, -34.6f, MapMaterials.Get("cloth_blue"));
            ShopBanner(banners, "BannerMagic", -13.6f, -14.6f, MapMaterials.Get("cloth_purple"));
            ShopBanner(banners, "BannerBakery", 13.6f, -34.6f, MapMaterials.Get("cloth_orange"));
            ShopBanner(banners, "BannerTailor", 13.6f, -14.6f, MapMaterials.Get("cloth_green"));
        }

        /// <summary>店门口的挑旗：一根木杆 + 一面竖旗（旗面朝南北，沿街可见）。</summary>
        void ShopBanner(Transform parent, string name, float x, float z, Material cloth)
        {
            var pole = MapMaterials.Get("wood_dark");
            Cyl(parent, name + "Pole", new Vector3(x, 2.9f, z), new Vector3(0.11f, 2.9f, 0.11f), pole, 0f, false);
            var flagX = x + (x < 0f ? 0.62f : -0.62f);
            Box(parent, name + "Flag", new Vector3(flagX, 4.35f, z), new Vector3(1.05f, 1.5f, 0.07f), cloth, 0f, false);
            Box(parent, name + "Bar", new Vector3(x + (x < 0f ? 0.3f : -0.3f), 5.12f, z), new Vector3(0.75f, 0.08f, 0.08f), pole, 0f, false);
        }

        // ================= 民居街区 =================

        void BuildResidential(Transform world)
        {
            var root = Node(world, "Residential");
            var west = Node(root, "WestBlock");
            // 西侧民居排：正面朝东（+X），面向南北副街
            PlaceHouse(west, Spec("plaster_cream", "roof_thatch", "timber_light", 1, false, 5.4f, 4.4f),
                "HouseW1", -HouseX, -38f, 90f);
            PlaceHouse(west, Spec("plaster_warm", "roof_terracotta", "timber_dark", 2, true, 6.2f, 5.2f, "草药"),
                "HouseW2", -HouseX, -20f, 90f, 1f);
            PlaceHouse(west, Spec("plaster_white", "roof_burgundy", "timber_mid", 2, true, 8.5f, 6.5f),
                "HouseW3", -HouseX, -6f, 90f);
            PlaceHouse(west, Spec("plaster_ochre", "roof_thatch", "timber_light", 1, false, 5.6f, 4.6f),
                "HouseW4", -HouseX, 6f, 90f);
            PlaceHouse(west, Spec("plaster_grey", "roof_slate", "timber_dark", 2, true, 6.2f, 5.2f),
                "HouseW5", -HouseX, 20f, 90f);
            PlaceHouse(west, Spec("plaster_white", "roof_blue", "timber_mid", 2, true, 8.5f, 6.5f),
                "HouseW6", -HouseX, 32f, 90f);

            var east = Node(root, "EastBlock");
            // 东侧民居排：正面朝西（-X）
            PlaceHouse(east, Spec("plaster_cream", "roof_thatch", "timber_light", 1, false, 5.4f, 4.4f),
                "HouseE1", HouseX, -38f, -90f);
            PlaceHouse(east, Spec("plaster_warm", "roof_terracotta", "timber_dark", 2, true, 6.2f, 5.2f),
                "HouseE2", HouseX, -20f, -90f);
            PlaceHouse(east, Spec("plaster_white", "roof_burgundy", "timber_mid", 2, true, 8.5f, 6.5f, null, true),
                "HouseE3", HouseX, -6f, -90f);
            PlaceHouse(east, Spec("plaster_salmon", "roof_thatch", "timber_light", 1, false, 5.6f, 4.6f),
                "HouseE4", HouseX, 6f, -90f);
            PlaceHouse(east, Spec("plaster_grey", "roof_slate", "timber_dark", 2, true, 6.2f, 5.2f),
                "HouseE5", HouseX, 18f, -90f);

            var north = Node(root, "NorthBlock");
            // 协会两侧的北排民居：正面朝南（-Z）
            PlaceHouse(north, Spec("plaster_ochre", "roof_terracotta", "timber_mid", 1, false, 6.0f, 4.6f),
                "HouseN1", -30f, 38f, 180f);
            PlaceHouse(north, Spec("plaster_cream", "roof_thatch", "timber_light", 1, false, 6.0f, 4.6f),
                "HouseN2", 30f, 38f, 180f);
            PlaceHouse(north, Spec("plaster_warm", "roof_slate", "timber_dark", 2, true, 6.6f, 5.4f),
                "HouseN3", 40f, 34f, 90f);

            // 民居前的小院杂物与花坛
            var yards = Node(root, "Yards");
            RoaKit.Crate(yards, new Vector3(-38.8f, 0f, -34.6f), -18f);
            RoaKit.Barrel(yards, new Vector3(-38.6f, 0f, -33.8f), 12f);
            RoaKit.Pot(yards, new Vector3(-38.9f, 0f, -2.6f), true);
            RoaKit.Pot(yards, new Vector3(-38.9f, 0f, -1.8f), false);
            RoaKit.Sack(yards, new Vector3(38.8f, 0f, -34.4f), 24f);
            RoaKit.Crate(yards, new Vector3(38.6f, 0f, -35.2f), -8f);
            RoaKit.Barrel(yards, new Vector3(38.7f, 0f, -2.4f), 30f);
            RoaKit.Pot(yards, new Vector3(38.9f, 0f, 8.6f), true);
            RoaKit.Pot(yards, new Vector3(-38.8f, 0f, 23.4f), true);
            RoaKit.Flowers(yards, new Vector3(-38.6f, 0f, -20f), new Color(0.92f, 0.4f, 0.5f));
            RoaKit.Flowers(yards, new Vector3(38.6f, 0f, -20f), new Color(0.95f, 0.8f, 0.35f));
            RoaKit.Flowers(yards, new Vector3(-38.6f, 0f, 6f), new Color(0.65f, 0.5f, 0.95f));
            RoaKit.Flowers(yards, new Vector3(38.6f, 0f, 6f), new Color(0.95f, 0.95f, 0.9f));
            RoaKit.Flowers(yards, new Vector3(-30f, 0f, 35.2f), new Color(0.9f, 0.45f, 0.35f));
            RoaKit.Flowers(yards, new Vector3(30f, 0f, 35.2f), new Color(0.5f, 0.75f, 0.95f));
        }

        // ================= 集市 =================

        void BuildMarket(Transform world)
        {
            var root = Node(world, "Market");
            var stalls = Node(root, "Stalls");
            // 广场四角：摊位正面朝向广场中心 (0, PlazaZ)
            RoaKit.MarketStall(stalls, new Vector3(8.5f, 0f, 14.5f), 225f, "cloth_orange");
            RoaKit.MarketStall(stalls, new Vector3(-8.5f, 0f, 14.5f), 135f, "cloth_red");
            RoaKit.MarketStall(stalls, new Vector3(-8.5f, 0f, -2.5f), 45f, "cloth_blue");
            RoaKit.MarketStall(stalls, new Vector3(8.5f, 0f, -2.5f), 315f, "cloth_teal");
            // 集市巷两侧各一座
            RoaKit.MarketStall(stalls, new Vector3(-8f, 0f, -24.6f), 180f, "cloth_green");
            RoaKit.MarketStall(stalls, new Vector3(8f, 0f, -30.2f), 0f, "cloth_cream");

            // 喷泉市集环：四座摊位放在 45° 对角线上（正面朝喷泉），把中轴留给喷泉/雕像视线
            RoaKit.MarketStall(stalls, new Vector3(6.1f, 0f, 9.1f), 225f, "cloth_purple");
            RoaKit.MarketStall(stalls, new Vector3(-6.1f, 0f, 9.1f), 135f, "cloth_teal");
            RoaKit.MarketStall(stalls, new Vector3(6.1f, 0f, -3.1f), 315f, "cloth_orange");
            RoaKit.MarketStall(stalls, new Vector3(-6.1f, 0f, -3.1f), 45f, "cloth_red");

            // 主街摊车：沿街摆开，把 20m 宽的大道变成"露天市集"
            var streetStalls = Node(root, "StreetStalls");
            RoaKit.MarketStall(streetStalls, new Vector3(-11.8f, 0f, -44f), 90f, "cloth_blue");
            RoaKit.MarketStall(streetStalls, new Vector3(11.8f, 0f, -42f), 270f, "cloth_orange");
            RoaKit.MarketStall(streetStalls, new Vector3(-11.8f, 0f, -30f), 90f, "cloth_green");
            RoaKit.MarketStall(streetStalls, new Vector3(11.8f, 0f, -28f), 270f, "cloth_red");
            RoaKit.MarketStall(streetStalls, new Vector3(-11.8f, 0f, -8f), 90f, "cloth_cream");
            RoaKit.MarketStall(streetStalls, new Vector3(11.8f, 0f, -10f), 270f, "cloth_purple");

            // 广场北口的市集牌坊（挂旗 + 匾额）：放在广场北缘，正对从城门进来的玩家，
            // 但不能挡在出生点正前方（否则初始镜头只看得到牌坊，看不到城市本体）。
            var arch = Node(root, "MarketArch");
            var archTimber = MapMaterials.Get("timber_dark");
            Box(arch, "ArchPostW", new Vector3(-8.6f, 2.25f, 21.5f), new Vector3(0.55f, 4.5f, 0.55f), archTimber, 0f, true);
            Box(arch, "ArchPostE", new Vector3(8.6f, 2.25f, 21.5f), new Vector3(0.55f, 4.5f, 0.55f), archTimber, 0f, true);
            Box(arch, "ArchBeam", new Vector3(0f, 4.72f, 21.5f), new Vector3(18.4f, 0.45f, 0.6f), archTimber, 0f, false);
            Box(arch, "ArchFootW", new Vector3(-8.6f, 0.2f, 21.5f), new Vector3(1.1f, 0.4f, 1.1f), MapMaterials.Get("stone_dark"), 0f, false);
            Box(arch, "ArchFootE", new Vector3(8.6f, 0.2f, 21.5f), new Vector3(1.1f, 0.4f, 1.1f), MapMaterials.Get("stone_dark"), 0f, false);
            Kit.SignBoard(arch, "中央市集 · Central Market", new Vector3(0f, 4.12f, 21.15f), 0f, 6.2f, 0.85f);
            RoaKit.Bunting(arch, new Vector3(0f, 0f, 19.9f), 0f, 16f);

            // 挂旗（跨街彩旗）
            var buntings = Node(root, "Buntings");
            RoaKit.Bunting(buntings, new Vector3(0f, 0f, -41f), 0f, 18f);
            RoaKit.Bunting(buntings, new Vector3(0f, 0f, -36f), 0f, 20f);
            RoaKit.Bunting(buntings, new Vector3(0f, 0f, -20f), 0f, 20f);
            RoaKit.Bunting(buntings, new Vector3(-LaneX, 0f, 8f), 0f, 7f);
            RoaKit.Bunting(buntings, new Vector3(LaneX, 0f, 8f), 0f, 7f);

            // 摊位周围的货物（每摊背后都堆一点，撑起"市集"密度）
            var goods = Node(root, "Goods");
            RoaKit.Crate(goods, new Vector3(4.0f, 0f, -4.6f), 12f);
            RoaKit.Crate(goods, new Vector3(4.7f, 0f, -4.0f), -22f);
            RoaKit.Sack(goods, new Vector3(5.2f, 0f, -5.2f), 15f);
            RoaKit.Crate(goods, new Vector3(-4.2f, 0f, 13.4f), 20f);
            RoaKit.Crate(goods, new Vector3(-5.0f, 0f, 14.2f), -16f);
            RoaKit.Sack(goods, new Vector3(-4.6f, 0f, 12.4f), -20f);
            RoaKit.Crate(goods, new Vector3(11.6f, 0f, -27.4f), 8f);
            RoaKit.Crate(goods, new Vector3(12.3f, 0f, -28.1f), -12f);
            RoaKit.Barrel(goods, new Vector3(-11.4f, 0f, -26.8f), 18f);
            RoaKit.Sack(goods, new Vector3(-11.8f, 0f, -27.6f), 6f);

            // 喷泉市集环：四摊背后各一堆
            RoaKit.Crate(goods, new Vector3(-2.4f, 0f, 12.7f), 16f);
            RoaKit.Sack(goods, new Vector3(2.5f, 0f, 12.5f), -12f);
            RoaKit.Crate(goods, new Vector3(9.8f, 0f, 4.4f), 22f);
            RoaKit.Barrel(goods, new Vector3(9.7f, 0f, 1.6f), -8f);
            RoaKit.Sack(goods, new Vector3(-9.8f, 0f, 4.4f), 14f);
            RoaKit.Crate(goods, new Vector3(-9.7f, 0f, 1.6f), -20f);
            RoaKit.Barrel(goods, new Vector3(-2.3f, 0f, -6.7f), 10f);
            RoaKit.Crate(goods, new Vector3(2.4f, 0f, -6.6f), 26f);

            // 主街摊车：车侧堆货 + 一只叠箱
            RoaKit.Crate(goods, new Vector3(-13.0f, 0f, -44.8f), 12f);
            RoaKit.Barrel(goods, new Vector3(-12.9f, 0f, -43.2f), -14f);
            RoaKit.Sack(goods, new Vector3(12.9f, 0f, -42.8f), 18f);
            RoaKit.Crate(goods, new Vector3(13.0f, 0f, -41.2f), -6f);
            RoaKit.Crate(goods, new Vector3(12.9f, 0.62f, -41.1f), 24f);
            RoaKit.Barrel(goods, new Vector3(-12.9f, 0f, -30.8f), 16f);
            RoaKit.Sack(goods, new Vector3(-13.0f, 0f, -29.2f), -22f);
            RoaKit.Crate(goods, new Vector3(13.0f, 0f, -28.8f), 8f);
            RoaKit.Pot(goods, new Vector3(12.9f, 0f, -27.2f), true);
            RoaKit.Crate(goods, new Vector3(-13.0f, 0f, -8.8f), -18f);
            RoaKit.Sack(goods, new Vector3(-12.9f, 0f, -7.2f), 12f);
            RoaKit.Crate(goods, new Vector3(13.0f, 0f, -10.8f), 20f);
            RoaKit.Barrel(goods, new Vector3(12.9f, 0f, -9.2f), -10f);

            // 集市巷口的价格牌
            var wood = MapMaterials.Get("wood_dark");
            Cyl(goods, "PricePostA", new Vector3(-11.2f, 0.95f, -24.4f), new Vector3(0.12f, 0.95f, 0.12f), wood, 0f, false);
            Cyl(goods, "PricePostB", new Vector3(-11.2f, 0.95f, -26.2f), new Vector3(0.12f, 0.95f, 0.12f), wood, 0f, false);
            Kit.SignBoard(goods, "今日市价 · 卯时开市", new Vector3(-11.15f, 2.2f, -25.3f), 90f, 2.8f, 0.72f);
        }

        // ================= 城门与城外营地 =================

        void BuildGatehouse(Transform world)
        {
            var root = Node(world, "Gatehouse");
            RoaKit.CastleGate(root, new Vector3(0f, 0f, GateZ), 0f);

            // 城门灯
            RoaKit.Lamp(root, "LampGateE", new Vector3(5.6f, 0f, -42.6f), 0f, true);
            RoaKit.Lamp(root, "LampGateW", new Vector3(-5.6f, 0f, -42.6f), 0f, false);

            // 城外木牌：罗亚市
            var sign = Node(root, "TownSign");
            Box(sign, "SignPostL", new Vector3(-1.8f, 1.05f, -49.8f), new Vector3(0.18f, 2.1f, 0.18f),
                MapMaterials.Get("wood_dark"), 0f, true);
            Box(sign, "SignPostR", new Vector3(1.8f, 1.05f, -49.8f), new Vector3(0.18f, 2.1f, 0.18f),
                MapMaterials.Get("wood_dark"), 0f, true);
            Kit.SignBoard(sign, "罗亚市 · Roa Town", new Vector3(0f, 2.55f, -49.8f), 180f, 4.2f, 0.72f);

            // 广场入口的小指示牌
            var plazaSign = Node(root, "PlazaSign");
            Box(plazaSign, "SignPost", new Vector3(7.4f, 0.95f, -8.4f), new Vector3(0.16f, 1.9f, 0.16f),
                MapMaterials.Get("wood_dark"), 0f, true);
            Kit.SignBoard(plazaSign, "中央广场", new Vector3(7.4f, 2.25f, -8.4f), 190f, 2.2f, 0.5f);

            // 城外商队营地
            var camp = Node(root, "Camp");
            RoaKit.Tent(camp, new Vector3(-14f, 0f, -52f), 30f, "cloth_red");
            RoaKit.Tent(camp, new Vector3(14f, 0f, -53f), -35f, "cloth_blue");
            RoaKit.Campfire(camp, new Vector3(-17.4f, 0f, -50.4f));
            RoaKit.Haystack(camp, new Vector3(10.5f, 0f, -51.4f), 1f);
            RoaKit.Haystack(camp, new Vector3(-10.6f, 0f, -51.0f), 0.9f);
            RoaKit.Crate(camp, new Vector3(8.4f, 0f, -44.6f), 14f);
            RoaKit.Crate(camp, new Vector3(-8.6f, 0f, -45.2f), -10f);
            RoaKit.Barrel(camp, new Vector3(16.6f, 0f, -50.2f), 18f);
            RoaKit.Lamp(camp, "LampVillageE", new Vector3(3.4f, 0f, -50.6f), 0f, false);
            RoaKit.Lamp(camp, "LampVillageW", new Vector3(-3.4f, 0f, -50.6f), 0f, true);
        }

        // ================= 传送门与出生点 =================

        void BuildTravel(Transform world)
        {
            var root = Node(world, "Travel");
            // 南门外 → 布耶纳村
            ScenePortal.Create(root, new Vector3(0f, 0f, -53f), MapId.BuenaVillage, "start", "布耶纳村", 0f);
            // 东侧魔法阵 → 拉诺亚魔法学院
            RoaKit.RuneCircle(root, new Vector3(LaneX + 4f, 0.09f, 27f), true);
            ScenePortal.Create(root, new Vector3(LaneX + 4f, 0f, 27f), MapId.RanoaAcademy, "start", "拉诺亚魔法学园", -90f);
            RoaKit.Lamp(root, "LampAcademy1", new Vector3(LaneX + 0.6f, 0f, 24.2f), 0f, true);
            RoaKit.Lamp(root, "LampAcademy2", new Vector3(LaneX + 7.4f, 0f, 29.8f), 0f, false);
            RoaKit.Bush(root, new Vector3(LaneX + 0.8f, 0f, 30.6f), 1.1f);
            RoaKit.Bush(root, new Vector3(LaneX + 7.2f, 0f, 23.4f), 1.0f);
            RoaKit.Pot(root, new Vector3(LaneX + 1.2f, 0f, 23.2f), true);

            // 出生点：start 为默认；其余供其它地图传送过来使用
            // 主线开场：出生在主街中段，一睁眼就是广场 + 喷泉 + 协会，相机不会卡在城门/城墙外
            PlaceSpawn("start", new Vector3(0f, 0.2f, -8f), 0f);
            PlaceSpawn("gate", new Vector3(0f, 0.2f, -43.5f), 0f);
            PlaceSpawn("village", new Vector3(0f, 0.2f, -51f), 180f);
            PlaceSpawn("plaza", new Vector3(0f, 0.2f, -1.5f), 0f);
            PlaceSpawn("market", new Vector3(0f, 0.2f, -28f), 0f);
            PlaceSpawn("guild", new Vector3(0f, 0.2f, 23f), 0f);
            PlaceSpawn("inn", new Vector3(-13f, 0.2f, 14f), 90f);
            PlaceSpawn("academy", new Vector3(LaneX + 1f, 0.2f, 27f), 90f);
        }

        // ================= 街道细节：路灯 / 手推车 / 采集物 =================

        void BuildStreetDetails(Transform world)
        {
            var root = Node(world, "Details");
            var lamps = Node(root, "Lamps");

            // 主干道
            RoaKit.Lamp(lamps, "LampAve1", new Vector3(-9.6f, 0f, -38.5f), 0f, false);
            RoaKit.Lamp(lamps, "LampAve2", new Vector3(9.6f, 0f, -38.5f), 0f, true);
            RoaKit.Lamp(lamps, "LampAve3", new Vector3(-9.6f, 0f, -23f), 0f, true);
            RoaKit.Lamp(lamps, "LampAve4", new Vector3(9.6f, 0f, -23f), 0f, false);
            // 广场外圈
            RoaKit.Lamp(lamps, "LampPlazaN", new Vector3(0f, 0f, 22.6f), 0f, false);
            RoaKit.Lamp(lamps, "LampPlazaE", new Vector3(16.4f, 0f, PlazaZ), 0f, false);
            RoaKit.Lamp(lamps, "LampPlazaW", new Vector3(-16.4f, 0f, PlazaZ), 0f, false);
            RoaKit.Lamp(lamps, "LampPlazaNE", new Vector3(11.7f, 0f, 17.7f), 0f, false);
            RoaKit.Lamp(lamps, "LampPlazaNW", new Vector3(-11.7f, 0f, 17.7f), 0f, true);
            RoaKit.Lamp(lamps, "LampPlazaSW", new Vector3(-11.7f, 0f, -5.7f), 0f, false);
            RoaKit.Lamp(lamps, "LampPlazaSE", new Vector3(11.7f, 0f, -5.7f), 0f, true);
            // 集市巷
            RoaKit.Lamp(lamps, "LampMarketW", new Vector3(-10.6f, 0f, -23.8f), 0f, false);
            RoaKit.Lamp(lamps, "LampMarketE", new Vector3(10.6f, 0f, -32.2f), 0f, true);
            // 民居副街
            RoaKit.Lamp(lamps, "LampWest1", new Vector3(-36.6f, 0f, -14f), 0f, false);
            RoaKit.Lamp(lamps, "LampWest2", new Vector3(-36.6f, 0f, 10f), 0f, false);
            RoaKit.Lamp(lamps, "LampEast1", new Vector3(36.6f, 0f, -14f), 0f, false);
            RoaKit.Lamp(lamps, "LampEast2", new Vector3(36.6f, 0f, 10f), 0f, false);

            // 手推车
            var carts = Node(root, "Carts");
            RoaKit.Cart(carts, new Vector3(-7.4f, 0f, -41.0f), 15f);
            RoaKit.Cart(carts, new Vector3(7.0f, 0f, -31.8f), -80f);
            RoaKit.Cart(carts, new Vector3(13.0f, 0f, -24.6f), 88f);

            // 散落的木桶 / 木箱 / 麻袋
            var junk = Node(root, "Junk");
            RoaKit.Barrel(junk, new Vector3(-12.4f, 0f, -45.6f), 20f);
            RoaKit.Crate(junk, new Vector3(12.6f, 0f, -45.4f), -14f);
            RoaKit.Barrel(junk, new Vector3(-12.8f, 0f, 21.6f), 8f);
            RoaKit.Sack(junk, new Vector3(12.4f, 0f, 21.2f), -18f);
            RoaKit.Pot(junk, new Vector3(-30.2f, 0f, 6.8f), true);
            RoaKit.Crate(junk, new Vector3(-31.2f, 0f, -2.4f), 26f);
            RoaKit.Sack(junk, new Vector3(30.6f, 0f, -3.2f), 12f);
            RoaKit.Barrel(junk, new Vector3(30.8f, 0f, 8.4f), -22f);

            // 采集物：草药 / 金币 / 魔力结晶
            var pickups = Node(root, "Pickups");
            PickupInteractable.Create(pickups, new Vector3(-37.6f, 0.25f, -24.6f), PickupKind.Herb);
            PickupInteractable.Create(pickups, new Vector3(37.6f, 0.25f, -24.6f), PickupKind.Herb);
            PickupInteractable.Create(pickups, new Vector3(-36.2f, 0.25f, 13.6f), PickupKind.Herb);
            PickupInteractable.Create(pickups, new Vector3(14.6f, 0.25f, 28.4f), PickupKind.Herb);
            PickupInteractable.Create(pickups, new Vector3(3.6f, 0.25f, -3.2f), PickupKind.Coin, 15);
            PickupInteractable.Create(pickups, new Vector3(LaneX - 1.6f, 0.25f, 29.6f), PickupKind.Crystal, 0, "mana_crystal");
        }

        // ================= 草木 =================

        void BuildNature(Transform world)
        {
            var root = Node(world, "Nature");
            var trees = Node(root, "Trees");
            // 副街行道树
            RoaKit.Tree(trees, new Vector3(-36.8f, 0f, -38f), 1f, false);
            RoaKit.Tree(trees, new Vector3(-36.8f, 0f, -12f), 0.9f, true);
            RoaKit.Tree(trees, new Vector3(-36.8f, 0f, 4f), 1.05f, false);
            RoaKit.Tree(trees, new Vector3(-36.8f, 0f, 20f), 0.95f, false);
            RoaKit.Tree(trees, new Vector3(-36.8f, 0f, 32f), 1f, true);
            RoaKit.Tree(trees, new Vector3(36.8f, 0f, -38f), 1f, false);
            RoaKit.Tree(trees, new Vector3(36.8f, 0f, -12f), 0.9f, false);
            RoaKit.Tree(trees, new Vector3(36.8f, 0f, 4f), 1.05f, true);
            RoaKit.Tree(trees, new Vector3(36.8f, 0f, 40f), 0.95f, false);
            // 城外树林与城门景观树
            RoaKit.Pine(trees, new Vector3(-52f, 0f, -30f), 1.2f);
            RoaKit.Pine(trees, new Vector3(-52f, 0f, 0f), 1.0f);
            RoaKit.Pine(trees, new Vector3(-52f, 0f, 30f), 1.15f);
            RoaKit.Pine(trees, new Vector3(52f, 0f, -30f), 1.1f);
            RoaKit.Pine(trees, new Vector3(52f, 0f, 0f), 1.25f);
            RoaKit.Pine(trees, new Vector3(52f, 0f, 30f), 1.0f);
            RoaKit.Pine(trees, new Vector3(-40f, 0f, -54f), 1.1f);
            RoaKit.Pine(trees, new Vector3(40f, 0f, -54f), 1.05f);
            RoaKit.Tree(trees, new Vector3(-20f, 0f, -55f), 1.3f, true);
            RoaKit.Tree(trees, new Vector3(20f, 0f, -55f), 1.2f, true);
            RoaKit.Tree(trees, new Vector3(-52f, 0f, 46f), 1.1f, false);
            RoaKit.Tree(trees, new Vector3(52f, 0f, 46f), 1.1f, true);

            var shrubs = Node(root, "Shrubs");
            RoaKit.Bush(shrubs, new Vector3(-19.6f, 0f, 2.4f), 1.2f);
            RoaKit.Bush(shrubs, new Vector3(19.6f, 0f, 2.4f), 1.1f);
            RoaKit.Bush(shrubs, new Vector3(-19.4f, 0f, 12.6f), 1.0f);
            RoaKit.Bush(shrubs, new Vector3(19.4f, 0f, 8.6f), 1.2f);
            RoaKit.Bush(shrubs, new Vector3(-39.4f, 0f, -30.4f), 1.0f);
            RoaKit.Bush(shrubs, new Vector3(39.4f, 0f, -30.4f), 1.1f);
            RoaKit.Bush(shrubs, new Vector3(-39.4f, 0f, 0.6f), 1.0f);
            RoaKit.Bush(shrubs, new Vector3(39.4f, 0f, 0.6f), 1.0f);
            RoaKit.Bush(shrubs, new Vector3(-39.2f, 0f, 26.4f), 1.15f);
            RoaKit.Bush(shrubs, new Vector3(39.2f, 0f, 26.4f), 1.05f);
            RoaKit.Bush(shrubs, new Vector3(-16.8f, 0f, -49.6f), 1.1f);
            RoaKit.Bush(shrubs, new Vector3(16.8f, 0f, -49.6f), 1.0f);
            RoaKit.Bush(shrubs, new Vector3(-6.4f, 0f, 26.4f), 0.9f);
            RoaKit.Bush(shrubs, new Vector3(6.4f, 0f, 26.4f), 0.9f);
            RoaKit.Rock(shrubs, new Vector3(-46.4f, 0f, -50.6f), 1.1f);
            RoaKit.Rock(shrubs, new Vector3(46.4f, 0f, -50.6f), 0.95f);
            RoaKit.Rock(shrubs, new Vector3(-46.6f, 0f, 49.4f), 1.05f);
            RoaKit.Rock(shrubs, new Vector3(46.6f, 0f, 49.4f), 1.2f);

            // 路边草簇
            var tufts = Node(root, "Tufts");
            var tuftPos = new[]
            {
                new Vector3(-11.2f, 0f, -44f), new Vector3(11.2f, 0f, -44f),
                new Vector3(-11.4f, 0f, -30f), new Vector3(11.4f, 0f, -30f),
                new Vector3(-11.2f, 0f, -14f), new Vector3(11.2f, 0f, -14f),
                new Vector3(-11.6f, 0f, -2f), new Vector3(11.6f, 0f, -2f),
                new Vector3(-19.2f, 0f, 22.6f), new Vector3(19.2f, 0f, 22.6f),
                new Vector3(-37.4f, 0f, -32f), new Vector3(37.4f, 0f, -32f),
                new Vector3(-37.4f, 0f, -6f), new Vector3(37.4f, 0f, -6f),
                new Vector3(-37.4f, 0f, 16f), new Vector3(37.4f, 0f, 16f),
                new Vector3(-27.6f, 0f, 33.6f), new Vector3(27.6f, 0f, 33.6f),
                new Vector3(-7.6f, 0f, -49.4f), new Vector3(7.6f, 0f, -49.4f),
                new Vector3(-48.4f, 0f, -20f), new Vector3(48.4f, 0f, -20f),
                new Vector3(-48.4f, 0f, 12f), new Vector3(48.4f, 0f, 12f),
            };
            for (int i = 0; i < tuftPos.Length; i++)
                RoaKit.GrassTuft(tufts, tuftPos[i], 0.9f + (i % 3) * 0.12f);
        }

        // ================= NPC =================

        void BuildNpcs(Transform world)
        {
            var root = Node(world, "NpcAnchors");
            // 冒险者协会：接待员（可交互委托板已移到协会门前公告墙下）
            SpawnNpc(NpcRole.GuildStaff, "莉赛特", new Vector3(-3.9f, 0f, 25.1f), 185f,
                LinesGuild, null, "roa_guild");

            // 商店街：四家店各一名商人
            SpawnNpc(NpcRole.Merchant, "巴尔", new Vector3(-12.3f, 0f, -35.3f), 90f,
                LinesGeneral, "roa_general");
            SpawnNpc(NpcRole.Merchant, "米莉", new Vector3(-12.3f, 0f, -15.3f), 90f,
                LinesMagic, "roa_magic");
            SpawnNpc(NpcRole.Merchant, "萝赛", new Vector3(12.3f, 0f, -35.3f), -90f,
                LinesBakery, "roa_general");
            SpawnNpc(NpcRole.Merchant, "妮娜", new Vector3(12.3f, 0f, -15.3f), -90f,
                LinesTailor, "roa_general");

            // 旅店老板
            SpawnNpc(NpcRole.Innkeeper, "加斯顿", new Vector3(-13.9f, 0f, 10.9f), 95f, LinesInn);

            // 卫兵：城门两名 + 广场一名
            SpawnNpc(NpcRole.Guard, "汉克", new Vector3(-4.8f, 0f, -43.2f), 180f, LinesGuardGate);
            SpawnNpc(NpcRole.Guard, "奥托", new Vector3(4.8f, 0f, -43.2f), 175f, LinesGuard);
            SpawnNpc(NpcRole.Guard, "罗兰", new Vector3(4.9f, 0f, 11.2f), 205f, LinesGuard);

            // 集市摊主
            SpawnNpc(NpcRole.Merchant, "玛莎", new Vector3(-5.4f, 0f, -24.6f), 265f,
                LinesVendor, "roa_general");
            SpawnNpc(NpcRole.Merchant, "图克", new Vector3(5.4f, 0f, -30.2f), 95f,
                LinesVendor, "roa_general");

            // 喷泉市集环 + 街角摊车：每摊一名商人（站在摊位柜台后面）
            SpawnNpc(NpcRole.Merchant, "萨拉", new Vector3(9.6f, 0f, 15.6f), 225f, LinesSpice, "roa_general");
            SpawnNpc(NpcRole.Merchant, "米尔", new Vector3(7.6f, 0f, 10.6f), 225f, LinesVendor, "roa_general");
            SpawnNpc(NpcRole.Merchant, "卡恩", new Vector3(-7.6f, 0f, 10.6f), 135f, LinesVendor, "roa_general");
            SpawnNpc(NpcRole.Merchant, "蒂亚", new Vector3(7.2f, 0f, -4.2f), 315f, LinesVendor, "roa_magic");
            SpawnNpc(NpcRole.Merchant, "佩里", new Vector3(-13.3f, 0f, -28.5f), 120f, LinesCloth, "roa_general");
            SpawnNpc(NpcRole.Merchant, "古斯", new Vector3(13.3f, 0f, -26.6f), 240f, LinesPotter, "roa_general");

            // 训练场教官（协会编制）
            SpawnNpc(NpcRole.GuildStaff, "格里", new Vector3(15f, 0f, 31.4f), 175f, LinesTrainer);

            // 市民
            SpawnNpc(NpcRole.Villager, "芙洛拉", new Vector3(4.6f, 0f, 8.9f), 170f, LinesVillagerA);
            SpawnNpc(NpcRole.Villager, "汉斯", new Vector3(-6.9f, 0f, -3.4f), 35f, LinesVillagerB);
            SpawnNpc(NpcRole.Villager, "米娅", new Vector3(13.4f, 0f, 20.0f), 210f, LinesVillagerC);
            SpawnNpc(NpcRole.Villager, "图恩", new Vector3(6.6f, 0f, -23.4f), 130f, LinesVillagerD);
            SpawnNpc(NpcRole.Villager, "吉尔", new Vector3(-28.2f, 0f, 2.2f), 90f, LinesVillagerE);
            SpawnNpc(NpcRole.Villager, "阿尔文", new Vector3(36.2f, 0f, -6.2f), 80f, LinesScholar);
            SpawnNpc(NpcRole.Villager, "波波", new Vector3(-30.4f, 0f, -9.6f), 50f, LinesKid);
        }

        // ================= 小工具 =================

        static Transform Node(Transform parent, string name)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            return go.transform;
        }

        static HouseSpec Spec(string wall, string roof, string timber, int floors, bool balcony,
            float w, float d, string sign = null, bool hanging = false)
        {
            return new HouseSpec
            {
                Width = w,
                Depth = d,
                Floors = floors,
                Balcony = balcony,
                Wall = wall,
                Roof = roof,
                Timber = timber,
                Sign = !string.IsNullOrEmpty(sign),
                SignText = sign ?? "",
                HangingSign = hanging,
            };
        }

        static void PlaceHouse(Transform parent, HouseSpec spec, string name, float x, float z, float yaw,
            float scale = 1f)
        {
            var go = RoaKit.House(parent, spec, new Vector3(x, 0f, z), yaw);
            go.name = name;
            if (!Mathf.Approximately(scale, 1f))
                go.transform.localScale = new Vector3(scale, scale, scale);
        }

        static void PlaceShop(Transform parent, string id, string label, ShopKind kind, float x, float z,
            float yaw, float w, float d, string wall, string upper, string roof, string awning, bool chimney)
        {
            RoaKit.Shop(parent, "Shop_" + id, new Vector3(x, 0f, z), yaw, w, d, kind, label,
                wall, upper, roof, awning, chimney);
        }
    }
}
