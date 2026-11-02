using UnityEngine;

namespace MyWorld.Maps
{
    /// <summary>
    /// 把 BlenderKitSceneBuilder 烘焙好的静态城镇（Assets/Scenes/BlenderKitTown.unity）变成可玩地图。
    ///
    /// 场景里的装饰件 / 房子 / 铺装 / 城墙 / 太阳都已经是**真实对象**，所以这里不重复生成环境，
    /// 只覆写 <see cref="MapBootstrap.BuildMapContent"/> 放敌人和 NPC；玩家、俯视相机、HUD
    /// 全部复用 <see cref="MapBootstrap.BuildAll"/> 的运行时搭建逻辑（和罗亚市同一套）。
    ///
    /// 注意：<see cref="MapBootstrap"/> 的 Awake 只在 buildOnPlay 且非 bakedIntoScene 时调 BuildAll。
    /// 本组件由 BlenderKitSceneBuilder 在编辑期挂在场景根上，并显式写入 buildOnPlay = true，
    /// 所以进 Play 会自动搭出 Player / Main Camera / UI。
    /// </summary>
    public class BlenderKitTownMap : MapBootstrap
    {
        // 出生点在广场南缘（井在原点、四个摊位在 ±6.4），这里留出空地给玩家和镜头。
        static readonly Vector3 PlayerSpawn = new Vector3(0f, 0.2f, -11f);

        static readonly string[] LinesVillager =
        {
            "欢迎来到这座小城。",
            "广场中央那口井，据说是建城时挖的第一口井。",
            "小心，最近有几只蛮兵在附近游荡。",
        };

        static readonly string[] LinesGuard =
        {
            "城墙以内归我们管，别惹事。",
            "东边的市集今天开得早。",
            "看见蛮兵就喊一声，别硬拼。",
        };

        static readonly string[] LinesMerchant =
        {
            "要买点什么？今天刚到的货。",
            "面包、绳子、药水，出门前都备一点。",
        };

        static readonly string[] LinesShopkeeper =
        {
            "随便看，货架上的都能买。",
            "从王都拉来的干货，比外头便宜两成。",
            "要出城的话，药水多备两瓶。",
        };

        static readonly string[] LinesInnkeeper =
        {
            "住店还是吃饭？炉火一直烧着。",
            "楼上还有空房，一晚三十铜板。",
            "南来北往的客人，我都记得住。",
        };

        /// <summary>场景里已有 Ground / Paving / Walls / Sun，不再生成环境。</summary>
        protected override void BuildEnvironment(Transform world)
        {
        }

        /// <summary>敌人 + NPC。位置都选在中央广场的空地上，避开井和摊位。</summary>
        protected override void BuildMapContent(Transform world)
        {
            // 三个蛮兵守在广场北 / 东 / 西缘，离出生点都在 10m 仇恨圈外。
            // 开局先让玩家看清城镇，往广场里走几步再触发战斗；否则一出生就被盾击
            // 连推到南墙外，看起来像场景坏了。
            SpawnEnemyAt(world, "Enemy_PlazaN", new Vector3(0f, 0.2f, 9.5f), 180f);
            SpawnEnemyAt(world, "Enemy_PlazaE", new Vector3(9.5f, 0.2f, 0f), 200f);
            SpawnEnemyAt(world, "Enemy_PlazaW", new Vector3(-9.5f, 0.2f, 0f), 160f);

            // NPC：两个村民 + 一个卫兵，站在广场边缘，靠近可按 E 对话。
            SpawnNpc(NpcRole.Villager, "艾拉", new Vector3(-9f, 0f, 8f), 160f, LinesVillager);
            SpawnNpc(NpcRole.Villager, "米娅", new Vector3(9f, 0f, 8f), 200f, LinesMerchant);
            SpawnNpc(NpcRole.Guard, "卫兵 汉斯", new Vector3(0f, 0f, 13f), 180f, LinesGuard);

            // 商铺 / 旅店：直接找场景里已烙好的 EnterableHouse，在室内局部坐标放 NPC。
            // 这样以后调整房子在 A 环的角度，NPC 会跟着房子走，不用两边各改一次坐标。
            SpawnInteriorNpcs();

            Debug.Log("[BlenderKitTown] 运行时内容：玩家出生点 " + PlayerSpawn +
                      "，敌人 3，广场 NPC 3，室内 NPC 2（玩家/相机/HUD 由 MapBootstrap 生成）");
        }

        /// <summary>
        /// 商铺里放商人（带 kittown_general 商店），旅店里放 Innkeeper。
        /// 位置是房子本地坐标：门在 +Z，所以 NPC 放在 z 负半轴、面朝 +Z 门口。
        /// </summary>
        private void SpawnInteriorNpcs()
        {
            EnterableHouse shop = null;
            EnterableHouse inn = null;
            var houses = Object.FindObjectsByType<EnterableHouse>(FindObjectsSortMode.None);
            foreach (var h in houses)
            {
                if (h == null) continue;
                if (h.name.StartsWith("InteriorShop_A")) shop = h;
                else if (h.name.StartsWith("InteriorInn_A")) inn = h;
            }

            if (shop != null)
                SpawnNpcInHouse(shop, NpcRole.Merchant, "杂货商人 格伦",
                    new Vector3(0.1f, 0f, -1.55f), LinesShopkeeper, "kittown_general");
            else
                Debug.LogWarning("[BlenderKitTown] 场景里没找到 InteriorShop_A，商人没生成。");

            if (inn != null)
                SpawnNpcInHouse(inn, NpcRole.Innkeeper, "旅店老板 罗莎",
                    new Vector3(-1.35f, 0f, -1.45f), LinesInnkeeper, null);
            else
                Debug.LogWarning("[BlenderKitTown] 场景里没找到 InteriorInn_A，Innkeeper 没生成。");
        }

        private void SpawnNpcInHouse(EnterableHouse house, NpcRole role, string name,
            Vector3 localPos, string[] lines, string shopId)
        {
            Vector3 pos = house.transform.TransformPoint(localPos);
            float yaw = house.transform.eulerAngles.y;
            SpawnNpc(role, name, pos, yaw, lines, shopId);
        }

        /// <summary>实例化敌人后挂到 World 下，重复 BuildAll 时能跟着 World 一起清掉。</summary>
        private void SpawnEnemyAt(Transform world, string name, Vector3 pos, float yaw)
        {
            var enemy = SpawnEnemy(pos, yaw);
            if (enemy == null) return;
            enemy.name = name;
            enemy.transform.SetParent(world, true);

            // KayKit 的 EnemyBarbarian.prefab 只有模型 + Animator，没有逻辑组件。
            // 训练场是在烘焙时补 Enemy + CharacterController + 血条（MyWorldBootstrap.BuildEnemies），
            // 这里同样补上，否则敌人只是一动不动的模型展件。
            var brain = enemy.GetComponent<Enemy>();
            if (brain == null) brain = enemy.AddComponent<Enemy>();

            // RequireComponent 会自动补 CharacterController；尺寸要按根节点缩放折算，
            // 否则 0.68 的模型会配出一个大一圈的胶囊，抓钩/攻击判定都会偏。
            var cc = enemy.GetComponent<CharacterController>();
            if (cc == null) cc = enemy.AddComponent<CharacterController>();
            float s = Mathf.Max(0.01f, enemy.transform.lossyScale.y);
            cc.height = 1.9f / s;
            cc.radius = 0.45f / s;
            cc.center = new Vector3(0f, 0.95f / s, 0f);
            cc.slopeLimit = 50f;
            cc.stepOffset = 0.4f / s;
            cc.skinWidth = 0.03f / s;

            var bar = HealthBar.Attach(enemy.transform, 2.6f, new Color(0.9f, 0.3f, 0.28f));
            brain.AttachHealthBar(bar);
        }

        /// <summary>兜底：没配 SpawnMarker 时用广场南缘。</summary>
        protected override Vector3 ResolveSpawn(string spawnId)
        {
            return PlayerSpawn;
        }
    }
}
