using UnityEngine;

namespace MyWorld
{
    public enum NpcRole
    {
        Merchant = 0,     // 商人：按 E 打开商店
        GuildStaff = 1,   // 冒险者协会职员：按 E 打开委托板
        Villager = 2,     // 村民：闲谈
        Student = 3,      // 学园学生
        Guard = 4,        // 卫兵
        Innkeeper = 5,    // 旅店老板
    }

    /// <summary>
    /// NPC：站着/看着玩家，靠近按 E 对话；商人和协会职员直接用同一个组件带出商店/委托板。
    /// 动画驱动参数（anim-dev 的 NPC 控制器约定）：`Speed` (float)、`Talk` (trigger，可选)。
    /// 控制器没有这些参数时 SetFloat/SetTrigger 也不会报错，所以这里不强制要求。
    /// </summary>
    [DisallowMultipleComponent]
    public class NpcActor : InteractableBase
    {
        public NpcRole role = NpcRole.Villager;
        public string displayName = "村民";
        public string[] lines = new string[0];
        public string shopId;
        public string boardId;
        public string talkCounter;

        private Animator animator;
        private Transform visual;
        private float lookTimer;
        private MerchantShop shop;
        private QuestBoardInteractable board;
        private bool hasTalkParam;

        public void Configure(NpcRole r, string name, string[] dialogue, string shop, string questBoard, string counter)
        {
            role = r;
            displayName = name;
            lines = dialogue ?? new string[0];
            shopId = shop;
            boardId = questBoard;
            talkCounter = counter;
            prompt = RolePrompt();
        }

        private void Awake()
        {
            animator = GetComponentInChildren<Animator>();
            visual = transform.childCount > 0 ? transform.GetChild(0) : null;
            shop = GetComponent<MerchantShop>();
            board = GetComponent<QuestBoardInteractable>();
            hasTalkParam = HasParameter("Talk");
        }

        private bool HasParameter(string paramName)
        {
            if (animator == null || animator.runtimeAnimatorController == null) return false;
            var ps = animator.parameters;
            for (int i = 0; i < ps.Length; i++) if (ps[i].name == paramName) return true;
            return false;
        }

        private void Update()
        {
            // 玩家靠近时缓缓转向玩家（不追逐，站着卖东西的 NPC 这样最自然）
            lookTimer -= Time.deltaTime;
            if (lookTimer > 0f) return;
            lookTimer = 0.15f;

            var player = FindPlayer();
            if (player == null) return;
            Vector3 d = player.transform.position - transform.position;
            d.y = 0f;
            if (d.sqrMagnitude > 1e-4f && d.sqrMagnitude < 25f)
            {
                Quaternion want = Quaternion.LookRotation(d.normalized, Vector3.up);
                transform.rotation = Quaternion.Slerp(transform.rotation, want, 6f * 0.15f);
            }
        }

        private Transform FindPlayer()
        {
            var health = Object.FindFirstObjectByType<PlayerHealth>();
            return health != null ? health.transform : null;
        }

        public override void Interact(GameObject interactor)
        {
            if (animator != null && hasTalkParam) animator.SetTrigger("Talk");
            if (!string.IsNullOrEmpty(talkCounter) && !string.IsNullOrEmpty(flagKeyOfTalk))
            {
                if (!GameSession.GetFlag(flagKeyOfTalk))
                {
                    GameSession.SetFlag(flagKeyOfTalk);
                    GameSession.AddCounter(talkCounter);
                }
            }

            if (role == NpcRole.Merchant && shop != null)
            {
                GameUi.Instance?.ShowShop(shop);
                return;
            }
            if (role == NpcRole.GuildStaff && board != null)
            {
                GameUi.Instance?.ShowQuestBoard(board);
                return;
            }

            var view = DialogueView.Simple(displayName, lines.Length > 0 ? lines : new[] { "……" });
            view.onComplete = () => GameSession.AddCounter("talk_npc");
            GameUi.Instance?.ShowDialogue(view);
        }

        private string flagKeyOfTalk
        {
            get { return "talked_" + displayName; }
        }

        private string RolePrompt()
        {
            switch (role)
            {
                case NpcRole.Merchant: return "与 " + displayName + " 交易";
                case NpcRole.GuildStaff: return "查看冒险者协会委托";
                case NpcRole.Innkeeper: return "与 " + displayName + " 交谈";
                default: return "与 " + displayName + " 交谈";
            }
        }
    }

    /// <summary>NPC 工厂：用角色预制体实例化，套色区分，挂名字牌。</summary>
    public static class NpcFactory
    {
        /// <summary>
        /// 在 parent 下生成一个 NPC。
        /// prefab 用 KayKit 角色预制体（MageCharacter 或 anim-dev 产出的 NPC 预制体）。
        /// tint 为空时按角色自动取色。
        /// </summary>
        public static NpcActor Create(Transform parent, GameObject prefab, NpcRole role, string name,
            Vector3 pos, float yaw = 0f, string[] lines = null, string shopId = null, string boardId = null,
            string talkCounter = null, Color? tint = null, float scale = 0.68f)
        {
            var root = new GameObject("NPC_" + name);
            root.transform.SetParent(parent, false);
            root.transform.position = pos;
            root.transform.rotation = Quaternion.Euler(0f, yaw, 0f);

            // 碰撞体：让玩家撞得到（不挡视线）
            var cap = root.AddComponent<CapsuleCollider>();
            cap.height = 1.55f;
            cap.radius = 0.3f;
            cap.center = new Vector3(0f, 0.78f, 0f);

            if (prefab != null)
            {
                var visual = Object.Instantiate(prefab, root.transform);
                visual.name = "Visual";
                visual.transform.localPosition = Vector3.zero;
                visual.transform.localRotation = Quaternion.identity;
                visual.transform.localScale = Vector3.one * scale;
                Tint(visual, tint ?? RoleColor(role));
            }

            var actor = root.AddComponent<NpcActor>();
            actor.Configure(role, name, lines, shopId, boardId, talkCounter);

            if (!string.IsNullOrEmpty(shopId))
            {
                var shop = root.AddComponent<MerchantShop>();
                shop.Configure(shopId, name);
            }
            if (!string.IsNullOrEmpty(boardId))
            {
                QuestBoardInteractable.CreateBoardComponent(root, boardId);
            }

            // 名字牌
            WorldText.Create(root.transform, name, new Vector3(0f, 2.05f, 0f), 0.16f,
                new Color(1f, 0.96f, 0.85f), 0f, 0f);

            return actor;
        }

        static Color RoleColor(NpcRole role)
        {
            switch (role)
            {
                case NpcRole.Merchant: return new Color(0.85f, 0.55f, 0.25f);
                case NpcRole.GuildStaff: return new Color(0.35f, 0.45f, 0.75f);
                case NpcRole.Guard: return new Color(0.45f, 0.5f, 0.55f);
                case NpcRole.Innkeeper: return new Color(0.7f, 0.4f, 0.4f);
                case NpcRole.Student: return new Color(0.45f, 0.65f, 0.7f);
                default: return new Color(0.75f, 0.7f, 0.6f);
            }
        }

        /// <summary>把角色身上所有材质克隆后染色（不会污染别的 NPC）。</summary>
        static void Tint(GameObject visual, Color color)
        {
            var renderers = visual.GetComponentsInChildren<Renderer>(true);
            for (int i = 0; i < renderers.Length; i++)
            {
                var mats = renderers[i].materials;
                for (int m = 0; m < mats.Length; m++)
                {
                    if (mats[m] == null) continue;
                    Color c = Color.Lerp(mats[m].color, color, 0.55f);
                    if (mats[m].HasProperty("_BaseColor")) mats[m].SetColor("_BaseColor", c);
                    mats[m].color = c;
                }
            }
        }
    }
}
