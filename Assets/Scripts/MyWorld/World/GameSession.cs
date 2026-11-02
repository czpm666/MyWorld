using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MyWorld
{
    /// <summary>可传送的地图。枚举 int 值等于场景索引（场景文件在 BuildSettings 里按这个顺序）。</summary>
    public enum MapId
    {
        TrainingGround = 0,   // 训练场（旧世界，烘焙场景 Assets/Scenes/MyWorld.unity）
        RoaTown = 1,          // 罗亚市（主城）
        BuenaVillage = 2,     // 布耶纳村
        RanoaAcademy = 3,     // 拉诺亚魔法学园
        BlenderKitTown = 4,   // 石墙镇（Blender Kit 场景，和主城通过传送门互通）
        AsuraKingdom = 5,     // 阿斯拉王国大地图（3km×3km，几十座小镇）
        AsuraCapital = 6,     // 阿斯拉王都「阿尔斯」（大地图中央，约 5 倍直径 / 30 倍面积）
    }

    /// <summary>
    /// 跨场景的玩家状态（血量/金币/装备/背包/任务计数）。
    /// 用 static 而不是 DontDestroyOnLoad 物体：切场景不重载程序集，static 天然跨图保留，
    /// 也不用担心场景里忘了放常驻物体。退出 Play 后自动清空。
    /// </summary>
    public static class GameSession
    {
        public const int GoldStart = 120;   // 开局给点钱，够在商人那买一瓶药水试试

        static bool initialized;
        static int gold = GoldStart;
        static float health = 100f;
        static float maxHealth = 100f;
        static WeaponKind equippedMain = WeaponKind.Staff;
        static WeaponKind equippedOff = WeaponKind.Grapple;

        static readonly List<string> purchased = new List<string>();
        static readonly Dictionary<string, int> counters = new Dictionary<string, int>(32);
        static readonly HashSet<string> flags = new HashSet<string>();

        // 传送中转数据：当前场景发起，目标场景 Awake 时消费
        static MapId pendingTarget;
        static string pendingSpawn;
        static bool hasPending;

        public static bool Initialized => initialized;
        public static int Gold => gold;
        public static float Health => health;
        public static float MaxHealth => maxHealth;
        public static float HealthFraction => maxHealth > 0f ? Mathf.Clamp01(health / maxHealth) : 0f;
        public static WeaponKind EquippedMain => equippedMain;
        public static WeaponKind EquippedOff => equippedOff;
        public static bool HasEquipment { get; private set; }
        public static IReadOnlyList<string> PurchasedItemIds => purchased;
        public static IReadOnlyDictionary<string, int> Counters => counters;

        public static event System.Action<int> GoldChanged;             // HUD 金币
        public static event System.Action<float, float> HealthChanged;  // HUD 血条
        public static event System.Action<string, int> CounterChanged;  // 任务/收集计数
        public static event System.Action<string> ItemPurchased;        // 商店买了什么
        public static event System.Action<MapId> TransitionStarted;     // 传送开始（特效层订阅）

        public static void EnsureInitialized()
        {
            if (initialized) return;
            initialized = true;
        }

        // ---------------- 金币 ----------------

        public static void AddGold(int delta)
        {
            if (delta == 0) return;
            EnsureInitialized();
            gold = Mathf.Max(0, gold + delta);
            GoldChanged?.Invoke(gold);
        }

        public static bool SpendGold(int amount)
        {
            if (amount < 0) return false;
            EnsureInitialized();
            if (gold < amount) return false;
            gold -= amount;
            GoldChanged?.Invoke(gold);
            return true;
        }

        // ---------------- 血量 ----------------

        public static void SetHealth(float current, float max)
        {
            EnsureInitialized();
            if (max > 0f) maxHealth = max;
            health = Mathf.Clamp(current, 0f, maxHealth);
            HealthChanged?.Invoke(health, maxHealth);
        }

        // ---------------- 装备 ----------------

        public static void SetEquipment(WeaponKind main, WeaponKind off)
        {
            equippedMain = main;
            equippedOff = off;
            HasEquipment = true;
        }

        // ---------------- 外观（PlayerAppearance：0=法师 1=骑士 2=游侠） ----------------

        /// <summary>外观存档键。与设置页的 mw_res / mw_fullscreen 同一套 PlayerPrefs 约定。</summary>
        public const string AppearanceKey = "mw_look";

        static int appearance = -1;   // -1 = 尚未从 PlayerPrefs 读过

        /// <summary>当前外观序号（懒读存档，重开游戏仍生效）。</summary>
        public static int Appearance
        {
            get
            {
                if (appearance < 0)
                    appearance = Mathf.Clamp(PlayerPrefs.GetInt(AppearanceKey, 0), 0, 2);
                return appearance;
            }
        }

        /// <summary>外观变化（0/1/2）。</summary>
        public static event System.Action<int> AppearanceChanged;

        /// <summary>设置并落盘外观。只有数值真的变了才写盘和发事件。</summary>
        public static void SetAppearance(int index)
        {
            index = Mathf.Clamp(index, 0, 2);
            if (Appearance == index) return;
            appearance = index;
            PlayerPrefs.SetInt(AppearanceKey, index);
            PlayerPrefs.Save();
            AppearanceChanged?.Invoke(index);
        }

        // ---------------- 背包（商店买到的消耗品） ----------------

        public static void AddPurchasedItem(string itemId)
        {
            if (string.IsNullOrEmpty(itemId)) return;
            EnsureInitialized();
            purchased.Add(itemId);
            ItemPurchased?.Invoke(itemId);
        }

        public static int CountItem(string itemId)
        {
            int n = 0;
            for (int i = 0; i < purchased.Count; i++)
                if (purchased[i] == itemId) n++;
            return n;
        }

        // ---------------- 旗标（宝箱开过没、NPC 聊过没） ----------------

        public static bool GetFlag(string key)
        {
            return !string.IsNullOrEmpty(key) && flags.Contains(key);
        }

        public static void SetFlag(string key)
        {
            if (string.IsNullOrEmpty(key)) return;
            flags.Add(key);
        }

        // ---------------- 任务计数 ----------------

        public static int GetCounter(string key)
        {
            if (string.IsNullOrEmpty(key)) return 0;
            int v;
            return counters.TryGetValue(key, out v) ? v : 0;
        }

        /// <summary>增加计数并通知任务系统（任务进度就是这么推进的）。</summary>
        public static void AddCounter(string key, int delta = 1)
        {
            if (string.IsNullOrEmpty(key) || delta == 0) return;
            EnsureInitialized();
            int v = GetCounter(key) + delta;
            counters[key] = v;
            CounterChanged?.Invoke(key, v);
            QuestSystem.ReportProgress(key, delta);
        }

        // ---------------- 传送 ----------------

        public static string SceneNameOf(MapId id)
        {
            switch (id)
            {
                case MapId.RoaTown: return "RoaTown";
                case MapId.BuenaVillage: return "BuenaVillage";
                case MapId.RanoaAcademy: return "RanoaAcademy";
                case MapId.BlenderKitTown: return "BlenderKitTown";
                case MapId.AsuraKingdom: return "KingdomWorld";
                case MapId.AsuraCapital: return "AsuraCapital";
                default: return "MyWorld";
            }
        }

        public static string DisplayNameOf(MapId id)
        {
            switch (id)
            {
                case MapId.RoaTown: return "罗亚市";
                case MapId.BuenaVillage: return "布耶纳村";
                case MapId.RanoaAcademy: return "拉诺亚魔法学园";
                case MapId.BlenderKitTown: return "石墙镇";
                case MapId.AsuraKingdom: return "阿斯拉王国";
                case MapId.AsuraCapital: return "王都 阿尔斯";
                default: return "训练场";
            }
        }

        /// <summary>
        /// 发起传送：先黑场再切场景；目标场景的 MapBootstrap 会用 TryConsumeSpawn 拿到出生点名。
        /// </summary>
        public static void BeginTransition(MapId target, string spawnId = "start")
        {
            EnsureInitialized();
            pendingTarget = target;
            pendingSpawn = string.IsNullOrEmpty(spawnId) ? "start" : spawnId;
            hasPending = true;
            TransitionStarted?.Invoke(target);

            string sceneName = SceneNameOf(target);
            if (GameUi.Instance != null)
                GameUi.Instance.PlayFadeOut(0.35f, () => SceneManager.LoadScene(sceneName));
            else
                SceneManager.LoadScene(sceneName);
        }

        /// <summary>目标场景醒来时调用：有匹配的待处理传送就取走出生点名。</summary>
        public static bool TryConsumeSpawn(MapId arrived, out string spawnId)
        {
            if (hasPending && pendingTarget == arrived)
            {
                spawnId = pendingSpawn;
                hasPending = false;
                return true;
            }
            spawnId = null;
            return false;
        }
    }
}
