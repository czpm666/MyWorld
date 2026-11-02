using System.Collections.Generic;

namespace MyWorld
{
    /// <summary>
    /// 给 UI 用的数据模型：对话 / 商店 / 任务板。
    /// 玩法代码只构造这些模型交给 GameUi；UI 只读模型、通过 host 接口回调。
    /// UI 实现与玩法逻辑因此可以各改各的（详见 OVERHAUL-PLAN §3）。
    /// </summary>

    // ---------------- 对话 ----------------

    public class DialogueView
    {
        public string speaker = "";
        public string[] lines = new string[0];
        /// <summary>玩家读完后关闭时回调（发任务计数、给奖励等）。</summary>
        public System.Action onComplete;

        public static DialogueView Simple(string speaker, params string[] lines)
        {
            return new DialogueView { speaker = speaker, lines = lines ?? new string[0] };
        }
    }

    // ---------------- 商店 ----------------

    public enum ShopEffect
    {
        None = 0,
        Heal = 1,           // 恢复 amount 点血
        FullHeal = 2,       // 回满（高等药水）
    }

    public class ShopItemDef
    {
        public string id;
        public string displayName;
        public string description;
        public int price;
        public ShopEffect effect = ShopEffect.None;
        public float amount;
    }

    public class ShopView
    {
        public string title;
        public string[] itemIds;

        public ShopView(string title, params string[] itemIds)
        {
            this.title = title;
            this.itemIds = itemIds ?? new string[0];
        }
    }

    /// <summary>商店宿主（MerchantShop 实现；UI 通过它买卖）。</summary>
    public interface IShopHost
    {
        ShopView View { get; }
        /// <summary>尝试扣钱并生效；成功返回 true（金币不足/已满血等返回 false，UI 自己提示）。</summary>
        bool Buy(string itemId);
    }

    /// <summary>
    /// 商品目录：目前只有消耗品（药水/面包），全部走 PlayerHealth 治疗，不引入新数值体系。
    /// 价格是**新内容的经济数值**，不改动既有战斗数值。
    /// </summary>
    public static class ShopCatalog
    {
        static readonly Dictionary<string, ShopItemDef> Items = new Dictionary<string, ShopItemDef>
        {
            { "potion_small", new ShopItemDef { id = "potion_small", displayName = "治疗药水", description = "温和的草药汤剂，回复 25 点生命。", price = 30, effect = ShopEffect.Heal, amount = 25f } },
            { "potion_large", new ShopItemDef { id = "potion_large", displayName = "治疗药水·大", description = "冒险者的常备药，回复 60 点生命。", price = 80, effect = ShopEffect.Heal, amount = 60f } },
            { "potion_elixir", new ShopItemDef { id = "potion_elixir", displayName = "高等治疗药", description = "教会秘传的配方，立刻回满生命。", price = 200, effect = ShopEffect.FullHeal } },
            { "bread", new ShopItemDef { id = "bread", displayName = "黑麦面包", description = "布耶纳村的日常口粮，回复 10 点生命。", price = 8, effect = ShopEffect.Heal, amount = 10f } },
            { "mana_ink", new ShopItemDef { id = "mana_ink", displayName = "魔法墨水", description = "拉诺亚的炼金产物，学者们抢着要。", price = 45, effect = ShopEffect.None } },
            { "herb_bundle", new ShopItemDef { id = "herb_bundle", displayName = "草药束", description = "晒干的常见药草，嚼两口就能回点血。", price = 18, effect = ShopEffect.Heal, amount = 15f } },
            { "guild_ration", new ShopItemDef { id = "guild_ration", displayName = "协会干粮", description = "协会给外勤配的行军口粮，顶饿也顶伤。", price = 45, effect = ShopEffect.Heal, amount = 35f } },
            { "crystal_dust", new ShopItemDef { id = "crystal_dust", displayName = "魔晶粉末", description = "研磨过的魔晶碎屑，学园的炼金材料。", price = 120, effect = ShopEffect.None } },
            // ---- 村与学园的生活向商品（新增内容，不改既有战斗数值）----
            { "farm_stew", new ShopItemDef { id = "farm_stew", displayName = "农家炖菜", description = "大锅炖的根菜和腌肉，一口下去从胃暖到手指。回复 30 点生命。", price = 32, effect = ShopEffect.Heal, amount = 30f } },
            { "apple_cider", new ShopItemDef { id = "apple_cider", displayName = "苹果酒", description = "村里自己酿的淡酒，酸甜，孩子也偷着喝。回复 10 点生命。", price = 12, effect = ShopEffect.Heal, amount = 10f } },
            { "honey_bread", new ShopItemDef { id = "honey_bread", displayName = "蜂蜜面包", description = "刚出炉的面包刷一层野蜂蜜，学园食堂的抢手货。回复 14 点生命。", price = 16, effect = ShopEffect.Heal, amount = 14f } },
            { "whetstone", new ShopItemDef { id = "whetstone", displayName = "磨刀石", description = "铁匠随手磨出来的一块青石，铁器见了它就得低头。", price = 60, effect = ShopEffect.None } },
            { "star_chart", new ShopItemDef { id = "star_chart", displayName = "星图抄本", description = "旧书摊淘来的手抄星图，边角还留着前任主人的批注。", price = 95, effect = ShopEffect.None } },
        };

        static readonly Dictionary<string, ShopView> Shops = new Dictionary<string, ShopView>
        {
            { "roa_general", new ShopView("罗亚市集 · 杂货摊", "potion_small", "potion_large", "bread") },
            { "roa_magic", new ShopView("罗亚市集 · 魔法用品", "potion_elixir", "mana_ink", "potion_large") },
            { "buena_peddler", new ShopView("布耶纳村 · 行商", "potion_small", "bread") },
            { "ranoa_shop", new ShopView("拉诺亚学园 · 魔法商店", "potion_elixir", "mana_ink", "potion_large") },
            { "kittown_general", new ShopView("石墙镇 · 杂货摊", "herb_bundle", "potion_small", "bread", "guild_ration") },
            { "kittown_arcane", new ShopView("石墙镇 · 魔法用品", "potion_elixir", "mana_ink", "crystal_dust") },
            // ---- 布耶纳村：村子也有活路（旅店 / 铁匠 / 草药 / 集市）----
            { "buena_inn", new ShopView("布耶纳村 · 麦穗旅店", "farm_stew", "apple_cider", "bread") },
            { "buena_smith", new ShopView("布耶纳村 · 铁匠铺", "whetstone", "potion_large") },
            { "buena_herbal", new ShopView("布耶纳村 · 草药摊", "herb_bundle", "potion_small", "honey_bread") },
            { "buena_market", new ShopView("布耶纳村 · 集市摊", "honey_bread", "apple_cider", "herb_bundle") },
            // ---- 拉诺亚学园：食堂 / 旧书摊 ----
            { "ranoa_canteen", new ShopView("拉诺亚学园 · 学生食堂", "farm_stew", "honey_bread", "apple_cider") },
            { "ranoa_books", new ShopView("拉诺亚学园 · 旧书摊", "mana_ink", "star_chart", "crystal_dust") },
            { "ranoa_guest", new ShopView("拉诺亚学园 · 访客驿站", "farm_stew", "honey_bread", "bread", "apple_cider") },
        };

        public static ShopItemDef Get(string id)
        {
            ShopItemDef def;
            return (id != null && Items.TryGetValue(id, out def)) ? def : null;
        }

        public static ShopView GetShop(string shopId)
        {
            ShopView v;
            if (shopId != null && Shops.TryGetValue(shopId, out v)) return v;
            return Shops["roa_general"];
        }

        public static IEnumerable<ShopItemDef> All => Items.Values;
    }

    // ---------------- 任务板 ----------------

    public class QuestCard
    {
        public string id;
        public string title;
        public string summary;
        public string[] objectiveLines;
        public int rewardGold;
        /// <summary>Available / Active / Ready / Done</summary>
        public string state;
        public bool canAccept;
        public bool canClaim;
    }

    public class QuestBoardView
    {
        public string title;
        public List<QuestCard> cards = new List<QuestCard>();
    }

    /// <summary>任务板宿主（QuestBoardInteractable 实现；UI 通过它接受/领取）。</summary>
    public interface IQuestBoardHost
    {
        QuestBoardView View { get; }
        bool Accept(string questId);
        bool Claim(string questId);
    }
}
