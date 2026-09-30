using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.UI;

namespace MyWorld
{
    /// <summary>
    /// 游戏界面。按 Tab 开关，**默认打开的是背包页**。
    ///
    /// 结构是"左边分支列表 + 右边内容区"，分支用数组定义 ——
    /// 以后要加角色/地图/设置页，只要往 Branches 里加一项、再补一个 Build 方法即可，
    /// 不用动布局代码。
    ///
    /// 全部用代码在运行时搭（不生成 UI 资源文件），和这个工程"烘焙场景 + 运行时补细节"的做法一致。
    /// </summary>
    [DisallowMultipleComponent]
    public class GameUi : MonoBehaviour
    {
        /// <summary>菜单是否打开。PlayerCombat 靠它屏蔽攻击输入。</summary>
        public static bool IsOpen { get; private set; }

        private struct Branch
        {
            public string name;
            public System.Action<RectTransform> build;
            public Branch(string name, System.Action<RectTransform> build)
            {
                this.name = name;
                this.build = build;
            }
        }

        private Branch[] branches;

        private Canvas canvas;
        private GameObject menuRoot;
        private RectTransform navColumn;
        private RectTransform content;
        private Text hudText;

        // ---- Toast 提示层（T-056 改动 3）----
        private RectTransform toastRoot;
        private CanvasGroup toastGroup;
        private Text toastText;
        private float toastTimer;

        /// <summary>显示时长 + 淡出时长。总可见时间 = 两者之和。</summary>
        private const float ToastHoldSeconds = 2.5f;
        private const float ToastFadeSeconds = 0.5f;

        // 边沿检测用的上一帧快照（-1 = 尚未对齐基线）
        private int lastPickupCount = -1;   // T-076：改用**拾取计数**（背包不再承载武器，数量不再变）
        private bool lastHadMainHand;

        // 这些引用必须序列化：烘焙出的组件在场景重载时要从场景文件恢复。
        // 用一个普通 class 打包它们是不行的 —— 非序列化字段重载后就是 null。
        [SerializeField] private MyWorldInput input;
        [SerializeField] private WeaponLoadout loadout;
        [SerializeField] private WeaponMount mount;
        [SerializeField] private PlayerCombat combat;
        [SerializeField] private PlayerHealth health;

        private int currentBranch = 0;
        private readonly List<GameObject> navButtons = new List<GameObject>();

        private Font font;

        public void Configure(MyWorldInput i, WeaponLoadout l, WeaponMount m, PlayerCombat c, PlayerHealth h)
        {
            input = i;
            loadout = l;
            mount = m;
            combat = c;
            health = h;
        }

        private void Start()
        {
            font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");

            branches = new[]
            {
                new Branch("背包", BuildBackpackPage),
                new Branch("武器", BuildWeaponPage),
                // 占位，用来证明这套结构是可分支的
                new Branch("角色", BuildPlaceholderPage),
                new Branch("设置", BuildSettingsPage),
            };

            LoadSavedSettings();

            // 设置页下标按**名字**推导（见 settingsBranchIndex 的注释）。
            settingsBranchIndex = -1;
            for (int i = 0; i < branches.Length; i++)
                if (branches[i].name == "设置") { settingsBranchIndex = i; break; }
            if (settingsBranchIndex < 0) settingsBranchIndex = branches.Length - 1;   // 兜底：末页

            BuildCanvas();
            BuildHud();
            BuildMenu();
            // ⚠️ 必须在 BuildMenu() **之后**：Toast 要是 canvas 的最后一个子节点，
            // 否则会被 MenuRoot 的全屏 0.6 黑遮罩压暗（见 BuildToast 的注释）。
            BuildToast();

            SetMenuOpen(false);
            ShowBranch(0);   // 默认背包页
        }

        private void Update()
        {
            if (input != null && input.MenuPressed) SetMenuOpen(!IsOpen);

            // Esc：直接跳到设置页。菜单已经开着且就在设置页时，再按一次关掉。
            if (input != null && input.SettingsPressed)
            {
                if (IsOpen && currentBranch == settingsBranchIndex) SetMenuOpen(false);
                else
                {
                    SetMenuOpen(true);
                    if (settingsBranchIndex >= 0) ShowBranch(settingsBranchIndex);
                }
            }

            UpdateToast();
            WatchWeaponEvents();
            UpdateHud();
        }

        // ---------------- 构建 ----------------

        private void BuildCanvas()
        {
            var canvasGo = new GameObject("UiCanvas");
            canvasGo.transform.SetParent(transform, false);
            canvas = canvasGo.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 100;

            var scaler = canvasGo.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;
            canvasGo.AddComponent<GraphicRaycaster>();

            // uGUI 的点击需要 EventSystem；项目用的是新输入系统，所以要挂 InputSystemUIInputModule
            if (Object.FindFirstObjectByType<EventSystem>() == null)
            {
                var es = new GameObject("EventSystem");
                es.transform.SetParent(transform, false);
                es.AddComponent<EventSystem>();
                var module = es.AddComponent<InputSystemUIInputModule>();
                module.AssignDefaultActions();
            }
        }

        /// <summary>常驻 HUD：血量 + 当前双手武器 + 操作提示。</summary>
        private void BuildHud()
        {
            var panel = MakePanel(canvas.transform, "Hud",
                new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(0f, 1f),
                new Vector2(20f, -20f), new Vector2(480f, 150f),
                new Color(0.05f, 0.06f, 0.08f, 0.55f));

            hudText = MakeText(panel, "", 22, TextAnchor.UpperLeft, new Color(0.95f, 0.96f, 0.98f));
            Stretch(hudText.rectTransform, 12f);
        }

        // ---------------- Toast 提示层 ----------------

        /// <summary>
        /// 顶部提示条。**必须是 canvas 的最后一个子节点**（兄弟序号大于 `MenuRoot`）：
        /// `MenuRoot` 上挂着一张全屏 `alpha=0.6` 的黑遮罩，Toast 若建在它之前，
        /// 玩家**开着菜单看背包时**（恰恰是最需要看到拾取提示的时刻）提示会被压暗看不见。
        /// 所以本方法只在 `BuildMenu()` 之后调用一次。
        /// </summary>
        private void BuildToast()
        {
            toastRoot = MakePanel(canvas.transform, "Toast",
                new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), new Vector2(0.5f, 1f),
                new Vector2(0f, -28f), new Vector2(560f, 52f),
                new Color(0.10f, 0.11f, 0.14f, 0.92f));

            // 不吞点击：提示正下方可能压着菜单按钮，默认 raycastTarget=true 会把它吃掉。
            var bg = toastRoot.GetComponent<Image>();
            if (bg != null) bg.raycastTarget = false;

            toastGroup = toastRoot.gameObject.AddComponent<CanvasGroup>();
            toastGroup.alpha = 0f;
            toastGroup.interactable = false;
            toastGroup.blocksRaycasts = false;

            toastText = MakeText(toastRoot, "", 22, TextAnchor.MiddleCenter, new Color(1f, 0.88f, 0.55f));
            toastText.raycastTarget = false;   // 文字也要关，否则同样吞点击
            Stretch(toastText.rectTransform, 6f);

            toastRoot.gameObject.SetActive(false);
        }

        /// <summary>
        /// 弹一条提示。**计时未结束时来新事件 → 替换文案并重置计时**：
        /// 否则"主手被打掉"紧接着"走过去捡起"会把第二条吃掉。
        /// </summary>
        private void ShowToast(string message)
        {
            if (toastText == null || toastRoot == null) return;

            toastText.text = message;
            toastTimer = ToastHoldSeconds + ToastFadeSeconds;
            toastRoot.gameObject.SetActive(true);
            toastGroup.alpha = 1f;
        }

        /// <summary>推进消散。用计时器而**不引协程** —— 与本文件现有风格一致（文件内 0 个协程）。</summary>
        private void UpdateToast()
        {
            if (toastRoot == null || toastGroup == null) return;
            if (!toastRoot.gameObject.activeSelf) return;

            toastTimer -= Time.deltaTime;
            if (toastTimer <= 0f)
            {
                toastGroup.alpha = 0f;
                toastRoot.gameObject.SetActive(false);
                return;
            }
            // 前 2.5s 恒为 1，最后 0.5s 线性淡出
            toastGroup.alpha = Mathf.Clamp01(toastTimer / ToastFadeSeconds);
        }

        /// <summary>
        /// 两个**无声发生**的武器事件 → 提示。都是**边沿检测**（对比上一帧），不是状态检测。
        ///
        /// A 拾取：🔴 **T-076（分支 B）换了触发源** —— 武器**不再进背包**，
        ///   所以原先"`Backpack.Count` 变多"的边沿检测**永远不会触发** → **拾取会无声发生**
        ///   （玩家不知道捡到了什么）。改成 `WeaponLoadout.PickupCount`（拾取处显式 +1）。
        /// B 主手被打掉：`MainHand` 变 null 的**唯一**路径是 `DropMainHand()`，
        ///   其唯一调用者是 `PlayerCombat.KnockOffMainHand()`（由敌人盾击触发）→ 无假阳性。
        /// </summary>
        private void WatchWeaponEvents()
        {
            if (loadout == null) return;

            int picks = loadout.PickupCount;
            if (lastPickupCount < 0)
                lastPickupCount = picks;                 // 首帧只对齐基线，不弹提示
            else if (picks > lastPickupCount)
            {
                // T-076 §4.3#1：武器**不再进背包** → Toast 必须改指**武器页**，
                // 并说明它在那里以"未装备"出现（否则玩家会去背包页找一件不在那儿的武器）。
                var picked = loadout.LastPickedUp;
                ShowToast($"已拾取 {(picked != null ? picked.displayName : "武器")} → 在左侧「武器」页（未装备，点一下装备）");
            }
            lastPickupCount = picks;

            bool hasMain = loadout.MainHand != null;
            if (!hasMain && lastHadMainHand)
                ShowToast("主手武器被打掉了！走过去就能捡回来");
            lastHadMainHand = hasMain;
        }

        private void BuildMenu()
        {
            menuRoot = new GameObject("MenuRoot");
            var mr = menuRoot.AddComponent<RectTransform>();
            mr.SetParent(canvas.transform, false);
            Stretch(mr, 0f);

            // 半透明遮罩
            var dim = menuRoot.AddComponent<Image>();
            dim.color = new Color(0f, 0f, 0f, 0.6f);

            // 窗口
            var window = MakePanel(menuRoot.transform, "Window",
                new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f),
                Vector2.zero, new Vector2(1180f, 680f),
                new Color(0.10f, 0.11f, 0.14f, 0.98f));

            // 左侧分支列。注意：**不要在这里再调 Stretch()** ——
            // 那会把已经定好的 240 宽覆盖成撑满整个窗口，分支按钮就会跑到中间去。
            navColumn = MakePanel(window, "Nav",
                new Vector2(0f, 0f), new Vector2(0f, 1f), new Vector2(0f, 0.5f),
                new Vector2(0f, 0f), new Vector2(240f, 0f),
                new Color(0.13f, 0.14f, 0.18f, 1f));

            var title = MakeText(navColumn, "菜单", 30, TextAnchor.UpperLeft, new Color(1f, 0.85f, 0.4f));
            title.rectTransform.anchorMin = new Vector2(0f, 1f);
            title.rectTransform.anchorMax = new Vector2(1f, 1f);
            title.rectTransform.pivot = new Vector2(0f, 1f);
            title.rectTransform.anchoredPosition = new Vector2(20f, -22f);
            title.rectTransform.sizeDelta = new Vector2(-40f, 40f);

            for (int i = 0; i < branches.Length; i++)
            {
                int index = i;
                var b = MakeButton(navColumn, branches[i].name,
                    new Vector2(0f, 1f), new Vector2(1f, 1f),
                    new Vector2(0f, -80f - i * 62f), new Vector2(-30f, 52f),
                    delegate { ShowBranch(index); });
                navButtons.Add(b.gameObject);
            }

            // 右侧内容区
            content = MakePanel(window, "Content",
                new Vector2(0f, 0f), new Vector2(1f, 1f), new Vector2(0.5f, 0.5f),
                Vector2.zero, Vector2.zero,
                new Color(0f, 0f, 0f, 0f));
            content.offsetMin = new Vector2(250f, 20f);
            content.offsetMax = new Vector2(-20f, -20f);

            var hint = MakeText(menuRoot.transform, "Tab 关闭", 20, TextAnchor.LowerRight, new Color(0.75f, 0.78f, 0.82f));
            hint.rectTransform.anchorMin = new Vector2(1f, 0f);
            hint.rectTransform.anchorMax = new Vector2(1f, 0f);
            hint.rectTransform.pivot = new Vector2(1f, 0f);
            hint.rectTransform.anchoredPosition = new Vector2(-30f, 24f);
            hint.rectTransform.sizeDelta = new Vector2(200f, 30f);
        }

        // ---------------- 页面 ----------------

        private void ShowBranch(int index)
        {
            if (branches == null || index < 0 || index >= branches.Length) return;
            currentBranch = index;

            for (int i = 0; i < content.childCount; i++)
                Destroy(content.GetChild(i).gameObject);

            branches[index].build(content);

            // 高亮当前分支
            for (int i = 0; i < navButtons.Count; i++)
            {
                var img = navButtons[i].GetComponent<Image>();
                if (img != null)
                    img.color = i == index
                        ? new Color(0.24f, 0.34f, 0.52f, 1f)
                        : new Color(0.17f, 0.18f, 0.22f, 1f);
            }
        }

        private void BuildPlaceholderPage(RectTransform parent)
        {
            var t = MakeText(parent, "这个页面还没做", 26, TextAnchor.MiddleCenter, new Color(0.6f, 0.63f, 0.68f));
            Stretch(t.rectTransform, 0f);
        }

        /// <summary>
        /// 武器页：列出**已拥有**的武器，按主手/副手分开，点一下装备到对应槽位。
        /// 这是"在哪换武器"的答案 —— 之前只有背包页，而背包一开始是空的，所以看不到任何武器。
        /// </summary>
        private void BuildWeaponPage(RectTransform parent)
        {
            if (loadout == null)
            {
                var t = MakeText(parent, "找不到 WeaponLoadout", 24, TextAnchor.MiddleCenter, Color.red);
                Stretch(t.rectTransform, 0f);
                return;
            }

            var head = MakeText(parent, "武器（点一下装备到对应手；副手一律用右键）",
                24, TextAnchor.UpperLeft, new Color(0.9f, 0.92f, 0.95f));
            head.rectTransform.anchorMin = new Vector2(0f, 1f);
            head.rectTransform.anchorMax = new Vector2(1f, 1f);
            head.rectTransform.pivot = new Vector2(0f, 1f);
            head.rectTransform.anchoredPosition = Vector2.zero;
            head.rectTransform.sizeDelta = new Vector2(0f, 40f);

            var equipped = MakeText(parent,
                "当前  主手：" + (loadout.MainHand != null ? loadout.MainHand.displayName : "空")
                + "      副手：" + (loadout.OffHand != null ? loadout.OffHand.displayName : "空"),
                22, TextAnchor.UpperLeft, new Color(0.75f, 0.85f, 0.75f));
            equipped.rectTransform.anchorMin = new Vector2(0f, 1f);
            equipped.rectTransform.anchorMax = new Vector2(1f, 1f);
            equipped.rectTransform.pivot = new Vector2(0f, 1f);
            equipped.rectTransform.anchoredPosition = new Vector2(0f, -42f);
            equipped.rectTransform.sizeDelta = new Vector2(0f, 34f);

            // T-076（分支 B）：本页现在必须**自己说清"这里放什么"**，并承接**两处从背包页搬来的既有修复**：
            //   ① T-023 的"武器在哪"指引行 —— 它原来长在背包页空状态里，而背包页已不放武器，
            //      总控裁定"**改指向正确的事、不要删**" → 落到这一页（本页就是武器所在）。
            //   ② T-056 / R-001 的"为什么会掉武器"解释 —— 被缴械的武器 T-076 之后出现在**这一页**，
            //      解释必须跟着走，否则会丢掉一个已经修好的可发现性问题（玩家不知道为什么武器没了）。
            //   依据 R-001：`WeaponPickup.Spawn` 全工程唯一调用点是 `KnockOffMainHand()`，
            //   其唯一调用者是**敌人的盾击** → "打掉敌人会掉武器"这条机制**结构上不存在**。
            string ownExplain = loadout.Owned.Count > 0
                ? "这一页是你已拥有的武器；● 表示正装在手上，没有 ● 的是未装备。"
                  + "\n只有敌人的盾击会打掉你的主手武器，掉在地上走过去就能捡 —— 捡回后它仍只在这一页，以「未装备」出现。"
                : "（没有任何武器）本局还没有得到过武器。这一页会列出你已拥有的武器；● 表示正装在手上。";
            var own = MakeText(parent, ownExplain, 19, TextAnchor.UpperLeft, new Color(0.72f, 0.78f, 0.72f));
            own.rectTransform.anchorMin = new Vector2(0f, 1f);
            own.rectTransform.anchorMax = new Vector2(1f, 1f);
            own.rectTransform.pivot = new Vector2(0f, 1f);
            own.rectTransform.anchoredPosition = new Vector2(0f, -80f);
            own.rectTransform.sizeDelta = new Vector2(0f, 44f);

            // 位置：页头 0..-40、当前装备 -42..-76、上面的说明 -80..-124 → 槽位自 -130 起（间隔 6px 不重叠）
            float y = -130f;
            y = BuildWeaponSlot(parent, "主手", HandSlot.MainHand, y);
            y = BuildWeaponSlot(parent, "副手", HandSlot.OffHand, y - 12f);

            var tip = MakeText(parent,
                "规则：主手和副手各只能装一件；弓要腾出一只手拉弓，所以用弓时副手不能装盾。\n"
                + "副手武器（抓钩 / 盾 / 魔法护手）都用右键使用；盾是长按举盾，举着时按左键放盾击。",
                19, TextAnchor.UpperLeft, new Color(0.62f, 0.66f, 0.72f));
            tip.rectTransform.anchorMin = new Vector2(0f, 1f);
            tip.rectTransform.anchorMax = new Vector2(1f, 1f);
            tip.rectTransform.pivot = new Vector2(0f, 1f);
            tip.rectTransform.anchoredPosition = new Vector2(0f, y - 8f);
            tip.rectTransform.sizeDelta = new Vector2(0f, 90f);
        }

        /// <summary>画一个槽位分区，返回下一段该从哪个 y 开始。</summary>
        private float BuildWeaponSlot(RectTransform parent, string title, HandSlot slot, float y)
        {
            var label = MakeText(parent, title, 22, TextAnchor.UpperLeft, new Color(1f, 0.85f, 0.4f));
            label.rectTransform.anchorMin = new Vector2(0f, 1f);
            label.rectTransform.anchorMax = new Vector2(1f, 1f);
            label.rectTransform.pivot = new Vector2(0f, 1f);
            label.rectTransform.anchoredPosition = new Vector2(0f, y);
            label.rectTransform.sizeDelta = new Vector2(0f, 30f);

            // ---- T-083 卡片几何（界面部指定的值；**这是本规格唯一动到既有几何的地方**）----
            // 卡片 168×52 → **232×64**；水平步进 180 → **244**（= 232 + 间距 12）；
            // 每行 3 张（3×232 + 2×12 = 720 ≤ 内容区 910 ✓）；超出换行。
            const float CardW = 232f, CardH = 64f, CardGapX = 12f, CardGapY = 8f;
            const float IconBox = 48f, IconPad = 8f;
            const float TextLeft = 64f;                        // 8 内边距 + 48 图标 + 8 间距
            const float TextRight = 12f;
            const int PerRow = 3;

            int col = 0;
            for (int i = 0; i < loadout.Owned.Count; i++)
            {
                var w = loadout.Owned[i];
                if (w == null || w.slot != slot) continue;

                int index = i;
                bool isEquipped = (slot == HandSlot.MainHand && loadout.MainHand == w)
                                  || (slot == HandSlot.OffHand && loadout.OffHand == w);

                int r = col / PerRow, c = col % PerRow;
                var cardPos = new Vector2(c * (CardW + CardGapX), y - 36f - r * (CardH + CardGapY));

                // 卡片本体 = 可点面板（**不用 MakeButton**：它的文字是"居中且被 Stretch"的，
                // 而 T-083 §2.2 要求**图标在左、文字左对齐** → 结构必须自己搭）
                var rt = MakePanel(parent, "WeaponCard_" + w.displayName,
                    new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(0f, 1f),
                    cardPos, new Vector2(CardW, CardH),
                    isEquipped ? new Color(0.24f, 0.42f, 0.30f, 1f) : new Color(0.17f, 0.18f, 0.22f, 1f));

                var btn = rt.gameObject.AddComponent<Button>();
                btn.targetGraphic = rt.GetComponent<Image>();
                btn.onClick.AddListener(delegate
                    {
                        loadout.Equip(loadout.Owned[index]);
                        if (mount != null) mount.Refresh(loadout);
                        ShowBranch(1);   // 刷新武器页
                        Debug.Log("[My World] 装备 " + loadout.Owned[index].displayName);
                    });

                // ---- 图标底板（48×48，左侧、垂直居中；**底板归 UI 不归 PNG** —— T-083 §4.1）----
                var plate = MakePanel(rt, "IconPlate",
                    new Vector2(0f, 0.5f), new Vector2(0f, 0.5f), new Vector2(0f, 0.5f),
                    new Vector2(IconPad, 0f), new Vector2(IconBox, IconBox),
                    new Color(0.10f, 0.11f, 0.14f, 1f));
                var plateImg = plate.GetComponent<Image>();
                if (plateImg != null) plateImg.raycastTarget = false;   // 别挡住卡片本体的点击

                if (w.icon != null)
                {
                    // 有图标：铺满底板，**preserveAspect** 防拉伸（F8）
                    var iconGo = new GameObject("Icon");
                    var irt = iconGo.AddComponent<RectTransform>();
                    irt.SetParent(plate, false);
                    irt.anchorMin = Vector2.zero; irt.anchorMax = Vector2.one;
                    irt.offsetMin = new Vector2(2f, 2f); irt.offsetMax = new Vector2(-2f, -2f);
                    var ii = iconGo.AddComponent<Image>();
                    ii.sprite = w.icon;
                    ii.preserveAspect = true;      // F8：不被拉伸
                    ii.raycastTarget = false;
                }
                else
                {
                    // 🔴 **回退：武器名首字**（法/剑/弓/抓/盾/魔，互不相同）。
                    // 六件里 Gauntlet/Grapple 目前没有图标 → 这条路径**默认就会被执行**（F5 因此天然被覆盖）。
                    // ⚠️ **不许留空白块**（会被读成"图标加载失败"），也不许因此改卡片尺寸 → 与有图者同框同尺寸。
                    string first = string.IsNullOrEmpty(w.displayName) ? "?" : w.displayName.Substring(0, 1);
                    var fb = MakeText(plate, first, 24, TextAnchor.MiddleCenter, new Color(0.80f, 0.84f, 0.90f));
                    Stretch(fb.rectTransform, 0f);
                    fb.raycastTarget = false;
                }

                // ---- 文字：**左对齐、单行**（T-083 §2.2 / §2.3）----
                var t = MakeText(rt, w.displayName + (isEquipped ? "  ●" : ""), 22,
                    TextAnchor.MiddleLeft, new Color(0.92f, 0.94f, 0.97f));
                t.rectTransform.anchorMin = new Vector2(0f, 0.5f);
                t.rectTransform.anchorMax = new Vector2(0f, 0.5f);
                t.rectTransform.pivot = new Vector2(0f, 0.5f);
                t.rectTransform.anchoredPosition = new Vector2(TextLeft, 0f);
                t.rectTransform.sizeDelta = new Vector2(CardW - TextLeft - TextRight, 40f);
                t.raycastTarget = false;
                FitSingleLine(t, CardW - TextLeft - TextRight);

                col++;
            }

            if (col == 0)
            {
                var none = MakeText(parent, "（没有可用的" + title + "武器）", 20,
                    TextAnchor.UpperLeft, new Color(0.6f, 0.63f, 0.68f));
                none.rectTransform.anchorMin = new Vector2(0f, 1f);
                none.rectTransform.anchorMax = new Vector2(1f, 1f);
                none.rectTransform.pivot = new Vector2(0f, 1f);
                none.rectTransform.anchoredPosition = new Vector2(0f, y - 36f);
                none.rectTransform.sizeDelta = new Vector2(0f, 30f);
            }

            // 槽位段落步进：y − 88（= y−36−52）→ **y − 100（= y−36−64）**
            // —— 卡片高度 52→64 的连带结果，界面部给定；**其余各量不动**。
            return y - 36f - CardH;
        }

        // ---------------- 设置页 ----------------

        /// <summary>
        /// 可选分辨率。标签只是习惯叫法，右边一律标出真实像素数，避免"2K 到底是多少"的争论。
        /// </summary>
        private static readonly string[] ResolutionLabels = { "720P", "1080P", "2K", "2.5K" };
        private static readonly int[] ResolutionWidth = { 1280, 1920, 2048, 2560 };
        private static readonly int[] ResolutionHeight = { 720, 1080, 1152, 1440 };

        /// <summary>
        /// 设置页在 branches 数组里的下标。**不再写死**（T-056 改动 5）：
        /// 原先 `private const int SettingsBranchIndex = 3;` —— 加"武器"页时忘了把 2 改成 3，
        /// `Esc` 就跳错页（charter-ui 坑 3）。改成在 `Start()` 里**按分支名"设置"查找**后，
        /// 以后在任何位置插页都不会再跳错：这类坑被**结构性消除**，而不是靠人记得改常量。
        /// </summary>
        private int settingsBranchIndex = -1;

        private int resolutionIndex;
        private bool fullscreen;
        private Text settingsStatus;

        private void LoadSavedSettings()
        {
            resolutionIndex = Mathf.Clamp(PlayerPrefs.GetInt("mw_res", 1), 0, ResolutionLabels.Length - 1);
            fullscreen = PlayerPrefs.GetInt("mw_fullscreen", 1) == 1;
        }

        private void ApplyResolution(int index)
        {
            resolutionIndex = Mathf.Clamp(index, 0, ResolutionLabels.Length - 1);
            Screen.SetResolution(ResolutionWidth[resolutionIndex], ResolutionHeight[resolutionIndex], fullscreen);
            PlayerPrefs.SetInt("mw_res", resolutionIndex);
            PlayerPrefs.Save();
            RefreshSettingsStatus();
        }

        private void ApplyFullscreen(bool value)
        {
            fullscreen = value;
            Screen.SetResolution(ResolutionWidth[resolutionIndex], ResolutionHeight[resolutionIndex], fullscreen);
            PlayerPrefs.SetInt("mw_fullscreen", fullscreen ? 1 : 0);
            PlayerPrefs.Save();
            RefreshSettingsStatus();
        }

        private void RefreshSettingsStatus()
        {
            if (settingsStatus == null) return;
            settingsStatus.text = "当前：" + ResolutionLabels[resolutionIndex]
                + "（" + ResolutionWidth[resolutionIndex] + " × " + ResolutionHeight[resolutionIndex] + "）"
                + "    窗口模式：" + (fullscreen ? "全屏" : "窗口");
        }

        private void BuildSettingsPage(RectTransform parent)
        {
            var head = MakeText(parent, "设置", 26, TextAnchor.UpperLeft, new Color(0.9f, 0.92f, 0.95f));
            head.rectTransform.anchorMin = new Vector2(0f, 1f);
            head.rectTransform.anchorMax = new Vector2(1f, 1f);
            head.rectTransform.pivot = new Vector2(0f, 1f);
            head.rectTransform.anchoredPosition = Vector2.zero;
            head.rectTransform.sizeDelta = new Vector2(0f, 40f);

            settingsStatus = MakeText(parent, "", 21, TextAnchor.UpperLeft, new Color(0.72f, 0.86f, 0.75f));
            settingsStatus.rectTransform.anchorMin = new Vector2(0f, 1f);
            settingsStatus.rectTransform.anchorMax = new Vector2(1f, 1f);
            settingsStatus.rectTransform.pivot = new Vector2(0f, 1f);
            settingsStatus.rectTransform.anchoredPosition = new Vector2(0f, -44f);
            settingsStatus.rectTransform.sizeDelta = new Vector2(0f, 32f);

            var resLabel = MakeText(parent, "分辨率", 22, TextAnchor.UpperLeft, new Color(0.85f, 0.87f, 0.9f));
            resLabel.rectTransform.anchorMin = new Vector2(0f, 1f);
            resLabel.rectTransform.anchorMax = new Vector2(1f, 1f);
            resLabel.rectTransform.pivot = new Vector2(0f, 1f);
            resLabel.rectTransform.anchoredPosition = new Vector2(0f, -88f);
            resLabel.rectTransform.sizeDelta = new Vector2(0f, 30f);

            // 四个分辨率按钮，横向排开
            for (int i = 0; i < ResolutionLabels.Length; i++)
            {
                int index = i;
                string label = ResolutionLabels[i] + "\n" + ResolutionWidth[i] + "×" + ResolutionHeight[i];

                var b = MakeButton(parent, label,
                    new Vector2(0f, 1f), new Vector2(0f, 1f),
                    new Vector2(i * 190f, -128f), new Vector2(176f, 76f),
                    delegate { ApplyResolution(index); });
                b.GetComponentInChildren<Text>().fontSize = 22;
            }

            var fsLabel = MakeText(parent, "窗口模式", 22, TextAnchor.UpperLeft, new Color(0.85f, 0.87f, 0.9f));
            fsLabel.rectTransform.anchorMin = new Vector2(0f, 1f);
            fsLabel.rectTransform.anchorMax = new Vector2(1f, 1f);
            fsLabel.rectTransform.pivot = new Vector2(0f, 1f);
            fsLabel.rectTransform.anchoredPosition = new Vector2(0f, -224f);
            fsLabel.rectTransform.sizeDelta = new Vector2(0f, 30f);

            MakeButton(parent, "全屏", new Vector2(0f, 1f), new Vector2(0f, 1f),
                new Vector2(0f, -262f), new Vector2(176f, 52f),
                delegate { ApplyFullscreen(true); });

            MakeButton(parent, "窗口", new Vector2(0f, 1f), new Vector2(0f, 1f),
                new Vector2(190f, -262f), new Vector2(176f, 52f),
                delegate { ApplyFullscreen(false); });

            var tip = MakeText(parent,
                "提示：画面发虚多半是分辨率或抗锯齿的问题。\n"
                + "工程里 URP 的抗锯齿(MSAA)已经开到 4x；渲染倍率(Render Scale)保持 1。\n"
                + "在编辑器里，Game 视图的尺寸会覆盖这里的设置。",
                19, TextAnchor.UpperLeft, new Color(0.62f, 0.66f, 0.72f));
            tip.rectTransform.anchorMin = new Vector2(0f, 1f);
            tip.rectTransform.anchorMax = new Vector2(1f, 1f);
            tip.rectTransform.pivot = new Vector2(0f, 1f);
            tip.rectTransform.anchoredPosition = new Vector2(0f, -332f);
            tip.rectTransform.sizeDelta = new Vector2(0f, 100f);

            RefreshSettingsStatus();
        }

        /// <summary>
        /// 背包页：列出捡到的武器，点一下装备到对应槽位。
        /// 装备后手部模型会同步刷新（WeaponMount.Refresh）。
        /// </summary>
        private void BuildBackpackPage(RectTransform parent)
        {
            
            if (loadout == null)
            {
                var t = MakeText(parent, "找不到 WeaponLoadout", 24, TextAnchor.MiddleCenter, Color.red);
                Stretch(t.rectTransform, 0f);
                return;
            }

            var head = MakeText(parent, "背包（这里放武器以外的物品）",
                24, TextAnchor.UpperLeft, new Color(0.9f, 0.92f, 0.95f));
            head.rectTransform.anchorMin = new Vector2(0f, 1f);
            head.rectTransform.anchorMax = new Vector2(1f, 1f);
            head.rectTransform.pivot = new Vector2(0f, 1f);
            head.rectTransform.anchoredPosition = Vector2.zero;
            head.rectTransform.sizeDelta = new Vector2(0f, 40f);

            // 🔴 T-076 严格读法下的修正：**本页不再显示"主手/副手"状态行**。
            // 原因（是判据逼出来的，不是审美）：F1 的原文是"同一件武器在任何时刻**只在一个分类页上出现一次**"。
            //   T-076 前这里有一行 `主手：剑  副手：抓钩` —— 就算武器**不再进背包**，
            //   这行也会让**武器名出现在背包页**上 → 严格读法下 F1 仍然不通过。
            //   而分支 B 下本页的定位是"**武器以外的物品**"，武器状态行属于武器页的事
            //   （武器页已有同一行 `当前 主手/副手`，信息不丢）。
            // ⚠️ 这是我用探针查出来的：第一版留着这行时，F8 报"背包页仍出现该武器"。

            if (loadout.Backpack.Count == 0)
            {
                // T-076（分支 B）：这一页改成"武器以外的物品"，而**当前结构上必然为空**
                // （全工程只有 WeaponDefinition 一种可持有物）→ 必须**诚实说明"还没有这类物品"**，
                // 否则就是"玩家面对空列表不知道怎么回事"的老问题重演。
                //
                // ⚠️ 两处**已完成的修复曾被长在这一页上，T-076 把它们搬去了武器页**（不是删掉）：
                //   * T-023 的"武器在哪"指引行（原在下方，已被本页移除）→ 搬到武器页
                //   * T-056 / R-001 的"为什么武器会掉"解释（原在下面这句里）→ 搬到武器页
                //     依据：R-001 裁定"敌人没有武器槽，打不掉敌人的武器"，而被缴械的武器
                //     T-076 之后出现在**武器页**，所以那句解释必须跟着走，否则玩家不知道为什么武器没了。
                var empty = MakeText(parent,
                    "（空的）这里放武器以外的物品（材料、道具等）。目前游戏里还没有这类物品。",
                    22, TextAnchor.UpperLeft, new Color(0.6f, 0.63f, 0.68f));
                empty.rectTransform.anchorMin = new Vector2(0f, 1f);
                empty.rectTransform.anchorMax = new Vector2(1f, 1f);
                empty.rectTransform.pivot = new Vector2(0f, 1f);
                empty.rectTransform.anchoredPosition = new Vector2(0f, -52f);
                empty.rectTransform.sizeDelta = new Vector2(0f, 34f);
                return;
            }

            // ⚠️ T-076：下面这段是**兼容路径**（背包里若真有东西）。
            // 武器正常不再进背包，而"其他物品"目前还没有类型 —— 所以这段在正常游玩里走不到，
            // 但**保留**它，好让 F8 的"过渡态"（背包里存在武器）仍可被验证不复制、不丢失。
            for (int i = 0; i < loadout.Backpack.Count; i++)
            {
                int index = i;
                var w = loadout.Backpack[i];
                // 槽位不同，装备到不同的手
                string slot = w.slot == HandSlot.MainHand ? "主手" : "副手";

                var b = MakeButton(parent, $"{w.displayName}   [{slot}]   点击装备",
                    new Vector2(0f, 1f), new Vector2(1f, 1f),
                    new Vector2(0f, -52f - i * 58f), new Vector2(0f, 48f),
                    delegate
                    {
                        loadout.EquipFromBackpack(index);
                        if (mount != null) mount.Refresh(loadout);
                        ShowBranch(currentBranch);   // 刷新页面
                        Debug.Log($"[My World] 已装备 {w.displayName} 到{slot}");
                    });
                b.GetComponentInChildren<Text>().alignment = TextAnchor.MiddleLeft;
            }
        }

        // ---------------- 开关 ----------------

        private void SetMenuOpen(bool open)
        {
            IsOpen = open;
            if (menuRoot != null) menuRoot.SetActive(open);

            // 打开菜单时不希望角色还在打，也不希望鼠标攻击穿透到游戏里
            if (combat != null) combat.enabled = !open;
        }

        private void OnDisable()
        {
            IsOpen = false;
        }

        private void UpdateHud()
        {
            if (hudText == null) return;

            float hp = health != null ? health.Health : 0f;
            float max = health != null ? health.MaxHealth : 0f;
            string main = loadout != null && loadout.MainHand != null ? loadout.MainHand.displayName : "空";
            string off = loadout != null && loadout.OffHand != null ? loadout.OffHand.displayName : "空";

            // ⚠️ 行数**恒定 4 行**。流血是第 1 行**同行追加**，绝不新增行 ——
            // 否则面板高度会随状态跳变，HUD 一抖玩家就以为出了别的事。
            //
            // 为什么流血必须写出来：PlayerHealth 的机制是"流血期间移速 ×0.85、**疾跑时伤害翻倍**"
            // （PlayerHealth.cs:27-31,113），玩家不知道的话会把"变慢 + 跑起来掉血更快"
            // 直接当成掉血 bug —— 这条提示解释的正是"人为什么变慢"。
            string bleed = health != null && health.IsBleeding ? "    ⚠ 流血中（疾跑伤害加倍）" : "";

            hudText.text = $"血量 {hp:F0}/{max:F0}{bleed}\n主手 {main}   副手 {off}\n"
                + "左键 主手攻击    右键 副手武器\n"
                + "Tab 菜单    Esc 设置    Q 锁定    Shift 疾跑    空格 跳";
        }

        // ---------------- uGUI 小工具 ----------------

        private RectTransform MakePanel(Transform parent, string name,
            Vector2 anchorMin, Vector2 anchorMax, Vector2 pivot,
            Vector2 anchoredPos, Vector2 size, Color color)
        {
            var go = new GameObject(name);
            var rt = go.AddComponent<RectTransform>();
            rt.SetParent(parent, false);
            rt.anchorMin = anchorMin;
            rt.anchorMax = anchorMax;
            rt.pivot = pivot;
            rt.anchoredPosition = anchoredPos;
            rt.sizeDelta = size;

            var img = go.AddComponent<Image>();
            img.color = color;
            return rt;
        }

        private Text MakeText(Transform parent, string value, int size, TextAnchor anchor, Color color)
        {
            var go = new GameObject("Text");
            var rt = go.AddComponent<RectTransform>();
            rt.SetParent(parent, false);

            var t = go.AddComponent<Text>();
            t.font = font;
            t.text = value;
            t.fontSize = size;
            t.alignment = anchor;
            t.color = color;
            t.horizontalOverflow = HorizontalWrapMode.Wrap;
            t.verticalOverflow = VerticalWrapMode.Overflow;
            return t;
        }

        private Button MakeButton(Transform parent, string label,
            Vector2 anchorMin, Vector2 anchorMax, Vector2 anchoredPos, Vector2 size,
            UnityEngine.Events.UnityAction onClick)
        {
            var rt = MakePanel(parent, "Button_" + label,
                anchorMin, anchorMax, new Vector2(0f, 1f), anchoredPos, size,
                new Color(0.17f, 0.18f, 0.22f, 1f));

            var btn = rt.gameObject.AddComponent<Button>();
            btn.targetGraphic = rt.GetComponent<Image>();
            btn.onClick.AddListener(onClick);

            var text = MakeText(rt, label, 22, TextAnchor.MiddleCenter, new Color(0.92f, 0.94f, 0.97f));
            Stretch(text.rectTransform, 8f);
            return btn;
        }

        /// <summary>
        /// T-083 §2.3 的文字规则：① **不换行** → ② **降字号 22 → 20 → 18（下限 18）** →
        /// ③ 仍超出则**尾部截断加 `…`**。必须始终满足：单行、不进图标区（左边界 = 调用方给的 64）、不超卡片右边。
        ///
        /// 实现说明：用 `Text.preferredWidth`（Unity 按当前字号算出的**单行**理想宽度）判断，
        /// **不需要字体度量 API**，也不需要 `resizeTextForBestFit`（那样反而不好控下限）。
        /// </summary>
        private static void FitSingleLine(Text t, float maxWidth)
        {
            if (t == null) return;

            t.horizontalOverflow = HorizontalWrapMode.Overflow;   // ① 不换行
            t.verticalOverflow = VerticalWrapMode.Truncate;

            int[] sizes = { 22, 20, 18 };
            for (int i = 0; i < sizes.Length; i++)
            {
                t.fontSize = sizes[i];
                if (t.preferredWidth <= maxWidth) return;         // ② 降字号够用
            }

            string s = t.text;                                    // ③ 截断
            while (s.Length > 1)
            {
                s = s.Substring(0, s.Length - 1);
                t.text = s + "…";
                if (t.preferredWidth <= maxWidth) return;
            }
            t.text = "…";
        }

        private static void Stretch(RectTransform rt, float padding)
        {
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.offsetMin = new Vector2(padding, padding);
            rt.offsetMax = new Vector2(-padding, -padding);
        }
    }
}
