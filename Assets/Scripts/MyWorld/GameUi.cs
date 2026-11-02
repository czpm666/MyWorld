using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.UI;
using MyWorld.UI;

namespace MyWorld
{
    /// <summary>
    /// 游戏 UI 主控（partial）。
    ///
    /// 分工：
    ///   · 本文件：实例/契约状态(IsOpen)、Canvas/HUD/菜单窗框/Toast/黑场、按键分发、武器事件监听；
    ///   · GameUiEquipment.cs：菜单里的四个页签（装备 / 背包 / 角色 / 设置）；
    ///   · GameUiPanels.cs：对话 / 商店 / 任务板 / 交互提示 / 任务追踪 / 金币 等对外契约。
    ///
    /// 视觉全部程序化生成（见 UI/UiSkin.cs、UiIconLibrary.cs），不依赖任何外部美术素材。
    /// 玩法数值只读显示，绝不改写。
    /// </summary>
    [DisallowMultipleComponent]
    public partial class GameUi : MonoBehaviour
    {
        // ---------------- 对外状态 ----------------

        /// <summary>菜单 / 对话 / 商店 / 任务板任一打开时为 true（PlayerCombat 靠它屏蔽攻击）。</summary>
        public static bool IsOpen { get; private set; }

        public static GameUi Instance { get; private set; }

        // ---------------- 场景引用（由 MyWorldBootstrap / SessionBridge 配置） ----------------

        [SerializeField] private MyWorldInput input;
        [SerializeField] private WeaponLoadout loadout;
        [SerializeField] private WeaponMount mount;
        [SerializeField] private PlayerCombat combat;
        [SerializeField] private PlayerHealth health;

        public void Configure(MyWorldInput i, WeaponLoadout l, WeaponMount m, PlayerCombat c, PlayerHealth h)
        {
            input = i;
            loadout = l;
            mount = m;
            combat = c;
            health = h;
        }

        // ---------------- 构建产物 ----------------

        private Canvas canvas;
        private RectTransform hudRoot;
        private RectTransform menuRoot;
        private RectTransform menuWindow;
        private RectTransform menuContent;
        private RectTransform overlayRoot;
        private RectTransform toastRoot;
        private Image fadeImage;

        // HUD
        private Image hpFill;
        private Text hpText;
        private Text bleedText;
        private Text hudGoldText;
        private RectTransform questPanel;
        private Text questBody;
        private RectTransform promptRoot;
        private Text promptText;
        private HudSlot slotMain;
        private HudSlot slotOff;
        private float slotMainFlash;
        private float slotOffFlash;

        // 菜单
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
        private int currentBranch;
        private int settingsBranchIndex;
        private readonly List<Image> navImages = new List<Image>();
        private readonly List<Text> navTexts = new List<Text>();
        private Text menuGoldText;
        private bool menuOpen;
        private Font font;

        // Toast
        private CanvasGroup toastGroup;
        private Text toastText;
        private float toastTimer;
        private bool toastActive;
        private const float ToastHoldSeconds = 2.5f;
        private const float ToastFadeSeconds = 0.5f;

        // 武器槽 / 拾取事件
        private WeaponDefinition lastMain;
        private WeaponDefinition lastOff;
        private int lastPickupCount = -1;
        private bool lastHadMainHand;

        // ---------------- HUD 武器槽小部件 ----------------

        private sealed class HudSlot
        {
            public RectTransform root;
            public Image frame;
            public Image icon;
            public Text key;
            public Text name;
            public Text cooldown;
            public WeaponDefinition current;
        }

        // ---------------- 生命周期 ----------------

        private void Awake()
        {
            Instance = this;
        }

        private void Start()
        {
            font = UiSkin.Body;

            GameSession.EnsureInitialized();

            // 页签先定义好，菜单窗框建按钮时要用名字
            branches = new[]
            {
                new Branch("装备", BuildEquipmentPage),
                new Branch("背包", BuildBackpackPage),
                new Branch("角色", BuildCharacterPage),
                new Branch("设置", BuildSettingsPage),
            };

            // 设置页下标按**名字**推导（避免以后插页签时硬编码错位）
            settingsBranchIndex = -1;
            for (int i = 0; i < branches.Length; i++)
                if (branches[i].name == "设置") { settingsBranchIndex = i; break; }
            if (settingsBranchIndex < 0) settingsBranchIndex = branches.Length - 1;

            BuildCanvas();
            BuildHud();
            BuildMenu();
            BuildOverlayLayer();   // 对话/商店/任务板层（在菜单之上）
            BuildToast();          // Toast 在菜单/面板之上
            BuildFade();           // 黑场永远最上

            LoadSavedSettings();

            SetMenuOpen(false);
            ShowBranch(0);   // 默认装备页 —— 用户第一诉求

            // 数据联动
            if (health != null) health.HealthChanged += HandleHealthChanged;
            GameSession.GoldChanged += HandleGoldChanged;
            QuestSystem.Changed += HandleQuestChanged;

            RefreshHudAll();
            RefreshOpenState();
        }

        private void OnDestroy()
        {
            if (health != null) health.HealthChanged -= HandleHealthChanged;
            GameSession.GoldChanged -= HandleGoldChanged;
            QuestSystem.Changed -= HandleQuestChanged;
            StopFadeRoutine();

            if (Instance == this) Instance = null;
            IsOpen = false;
            menuOpen = false;
        }

        private void Update()
        {
            UpdateToast();
            WatchWeaponEvents();
            UpdateHud(Time.unscaledDeltaTime);

            if (input == null) return;

            // 对话/商店/任务板打开时：按键交给面板层处理（E/回车推进、Esc 关闭），
            // 不允许顺手再打开菜单（否则两个界面叠着抢输入）。
            if (overlayOpen)
            {
                UpdateOverlays();
                return;
            }

            if (input.MenuPressed) ToggleMenu();
            else if (input.SettingsPressed) ToggleSettingsPage();
        }

        // ---------------- Canvas ----------------

        private void BuildCanvas()
        {
            var go = new GameObject("Canvas", typeof(RectTransform));
            go.transform.SetParent(transform, false);
            canvas = go.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 100;

            var scaler = go.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.screenMatchMode = CanvasScaler.ScreenMatchMode.MatchWidthOrHeight;
            scaler.matchWidthOrHeight = 0.5f;
            go.AddComponent<GraphicRaycaster>();

            // uGUI 的点击需要 EventSystem；项目用的是新输入系统，所以挂 InputSystemUIInputModule
            if (Object.FindFirstObjectByType<EventSystem>() == null)
            {
                var es = new GameObject("EventSystem");
                es.transform.SetParent(transform, false);
                es.AddComponent<EventSystem>();
                es.AddComponent<InputSystemUIInputModule>().AssignDefaultActions();
            }
        }

        // ---------------- HUD ----------------

        private void BuildHud()
        {
            hudRoot = UiKit.Stretch(canvas.transform, "Hud");

            // --- 左上：生命 ---
            var hpPanel = UiKit.Panel(hudRoot, "HealthPanel", UiSkin.Card, Color.white, 20f, 20f, 400f, 104f);
            hpPanel.raycastTarget = false;
            UiKit.Corners(hpPanel.transform, 6f, 26f);

            UiKit.Icon(hpPanel.transform, "Heart", UiSkin.Heart, 14f, 28f, 46f, 46f);

            var barBg = UiKit.Panel(hpPanel.transform, "BarBg", UiSkin.Slot, Color.white, 72f, 30f, 302f, 22f);
            var fillRt = UiKit.Node("Fill", barBg.transform);
            fillRt.anchorMin = new Vector2(0f, 0.5f);
            fillRt.anchorMax = new Vector2(0f, 0.5f);
            fillRt.pivot = new Vector2(0f, 0.5f);
            fillRt.sizeDelta = new Vector2(288f, 13f);
            fillRt.anchoredPosition = new Vector2(7f, 0f);
            hpFill = fillRt.gameObject.AddComponent<Image>();
            hpFill.sprite = UiSkin.BarFill;
            hpFill.type = Image.Type.Sliced;
            hpFill.color = UiSkin.RedLight;
            hpFill.raycastTarget = false;

            hpText = UiKit.Label(hpPanel.transform, "HpText", "生命 100 / 100", 19, UiSkin.TextDark,
                72f, 54f, 302f, 26f, TextAnchor.MiddleLeft);
            bleedText = UiKit.Label(hpPanel.transform, "Bleed", "流血中", 16, UiSkin.Red,
                72f, 78f, 302f, 22f, TextAnchor.MiddleLeft);
            bleedText.fontStyle = FontStyle.Bold;
            bleedText.gameObject.SetActive(false);

            // --- 右上：金币 ---
            var goldPanel = UiKit.PanelRight(hudRoot, "GoldPanel", UiSkin.Card, Color.white, -24f, 20f, 250f, 58f);
            UiKit.Corners(goldPanel.transform, 6f, 22f);
            UiKit.Icon(goldPanel.transform, "Coin", UiSkin.Coin, 12f, 12f, 34f, 34f);
            hudGoldText = UiKit.Label(goldPanel.transform, "Gold", "120", 26, UiSkin.TextDark,
                54f, 12f, 182f, 34f, TextAnchor.MiddleLeft);
            hudGoldText.fontStyle = FontStyle.Bold;

            // --- 右上：任务追踪 ---
            questPanel = UiKit.PlaceRight(hudRoot, "QuestPanel", -24f, 88f, 544f, 160f);
            var questBg = questPanel.gameObject.AddComponent<Image>();
            questBg.sprite = UiSkin.ParchmentPanel;
            questBg.type = Image.Type.Sliced;
            questBg.color = new Color(1f, 1f, 1f, 0.94f);
            questBg.raycastTarget = false;
            UiKit.Corners(questPanel, 8f, 30f);
            var questTitle = UiKit.Label(questPanel, "Title", "任务追踪", 16, UiSkin.Ink.Alpha(0.72f),
                18f, 8f, 200f, 24f, TextAnchor.MiddleLeft);
            questTitle.fontStyle = FontStyle.Bold;
            questBody = UiKit.Label(questPanel, "Body", "", 19, UiSkin.TextDark,
                18f, 34f, 508f, 118f, TextAnchor.UpperLeft);
            questPanel.gameObject.SetActive(false);

            // --- 右下：双手武器槽 ---
            var slotsRoot = UiKit.Node("WeaponSlots", hudRoot);
            slotsRoot.anchorMin = new Vector2(1f, 0f);
            slotsRoot.anchorMax = new Vector2(1f, 0f);
            slotsRoot.pivot = new Vector2(1f, 0f);
            slotsRoot.sizeDelta = new Vector2(248f, 178f);
            slotsRoot.anchoredPosition = new Vector2(-20f, 20f);

            slotMain = BuildHudSlot(slotsRoot, "MainHandSlot", 0f, "左键");
            slotOff = BuildHudSlot(slotsRoot, "OffHandSlot", 128f, "右键");

            // --- 底部中央：交互提示 ---
            promptRoot = UiKit.BottomCenter(hudRoot, "InteractPrompt", 130f, 580f, 74f);
            var promptBg = promptRoot.gameObject.AddComponent<Image>();
            promptBg.sprite = UiSkin.ParchmentPanel;
            promptBg.type = Image.Type.Sliced;
            promptBg.color = Color.white;
            promptBg.raycastTarget = false;
            UiKit.Corners(promptRoot, 8f, 30f);

            var keyBadge = UiKit.Panel(promptRoot, "KeyBadge", UiSkin.ButtonGold, Color.white, 16f, 17f, 40f, 40f);
            var keyText = UiKit.Label(keyBadge.transform, "KeyText", "E", 22, UiSkin.TextDark,
                0f, 0f, 40f, 40f, TextAnchor.MiddleCenter);
            keyText.fontStyle = FontStyle.Bold;
            promptText = UiKit.Label(promptRoot, "PromptText", "交谈", 24, UiSkin.TextDark,
                70f, 12f, 490f, 50f, TextAnchor.MiddleLeft);
            promptRoot.gameObject.SetActive(false);

            // --- 左下：按键提示 ---
            var hintRoot = UiKit.Node("Hint", hudRoot);
            hintRoot.anchorMin = new Vector2(0f, 0f);
            hintRoot.anchorMax = new Vector2(0f, 0f);
            hintRoot.pivot = new Vector2(0f, 0f);
            hintRoot.sizeDelta = new Vector2(1120f, 26f);
            hintRoot.anchoredPosition = new Vector2(24f, 18f);
            UiKit.LabelFill(hintRoot, "HintText",
                "Tab 冒险手札　·　V 切换视角　·　, . 转视角　·　Q 锁定　·　Shift 疾跑　·　空格 跳跃　·　Ctrl 翻滚　·　Esc 设置",
                16, new Color(0.94f, 0.9f, 0.8f, 0.9f), TextAnchor.MiddleLeft).WithShadow(0.8f);
        }

        private HudSlot BuildHudSlot(Transform parent, string name, float x, string keyLabel)
        {
            var root = UiKit.Place(parent, name, x, 0f, 120f, 178f);

            var frame = UiKit.Panel(root, "Frame", UiSkin.Slot, Color.white, 0f, 0f, 120f, 120f);
            var icon = UiKit.Icon(root, "Icon", null, 13f, 13f, 94f, 94f);

            var slot = new HudSlot { root = root, frame = frame, icon = icon };
            slot.key = UiKit.Label(root, "Key", keyLabel, 15, UiSkin.GoldLight,
                0f, 0f, 120f, 22f, TextAnchor.MiddleCenter).WithShadow(0.9f);
            slot.cooldown = UiKit.Label(root, "Cd", "", 14, UiSkin.TextLight,
                0f, 96f, 108f, 22f, TextAnchor.MiddleRight).WithShadow(0.9f);
            slot.name = UiKit.Label(root, "Name", "空手", 17, UiSkin.TextLight,
                0f, 122f, 120f, 24f, TextAnchor.MiddleCenter).WithShadow(0.9f);
            return slot;
        }

        private void FillHudSlot(HudSlot slot, WeaponDefinition weapon, string handLabel)
        {
            // The HUD is rebuilt from scratch on Start, and a domain reload
            // during Play (e.g. an asset import while the game is running)
            // can hand us a refresh before the slots exist. TintSlot has the
            // same guard; without it this line threw a NullReferenceException.
            if (slot == null) return;
            slot.current = weapon;
            if (slot.icon != null)
            {
                slot.icon.sprite = UiIconLibrary.Load(weapon != null ? weapon.kind : WeaponKind.Unarmed);
                slot.icon.color = Color.white;
            }
            if (slot.name != null) slot.name.text = weapon != null ? weapon.displayName : "空手 · " + handLabel;
            if (slot.cooldown != null) slot.cooldown.text = weapon != null ? weapon.cooldown.ToString("0.##") + "s" : "";
        }

        private void RefreshHudAll()
        {
            RefreshWeaponSlots();
            UpdateHealthHud();
            SetGold(GameSession.Gold);
            SetQuestTracker(QuestSystem.TrackerLine());
            SetInteractPrompt(null);
        }

        private void RefreshWeaponSlots()
        {
            if (loadout == null) return;
            if (slotMain == null && slotOff == null) return;   // HUD 还没建好
            lastMain = loadout.MainHand;
            lastOff = loadout.OffHand;
            FillHudSlot(slotMain, lastMain, "主手");
            FillHudSlot(slotOff, lastOff, "副手");
        }

        private void UpdateHud(float dt)
        {
            UpdateHealthHud();

            // 攻击按键 → 武器槽闪一下（PlayerCombat 没有公开冷却读数，只能做"触发反馈"）
            if (input != null)
            {
                if (input.AttackPressed) slotMainFlash = 0.16f;
                if (input.OffHandPressed) slotOffFlash = 0.16f;
            }
            slotMainFlash = Mathf.Max(0f, slotMainFlash - dt);
            slotOffFlash = Mathf.Max(0f, slotOffFlash - dt);
            TintSlot(slotMain, slotMainFlash);
            TintSlot(slotOff, slotOffFlash);
        }

        private void TintSlot(HudSlot slot, float flash)
        {
            if (slot == null || slot.frame == null) return;
            slot.frame.color = Color.Lerp(Color.white, UiSkin.GoldLight, Mathf.Clamp01(flash / 0.16f) * 0.9f);
        }

        private void UpdateHealthHud()
        {
            float cur;
            float max;
            bool bleeding = false;
            if (health != null)
            {
                cur = health.Health;
                max = health.MaxHealth;
                bleeding = health.IsBleeding;
            }
            else
            {
                cur = GameSession.Health;
                max = GameSession.MaxHealth;
            }
            if (max <= 0f) max = 1f;
            float frac = Mathf.Clamp01(cur / max);

            if (hpFill != null)
            {
                var rt = hpFill.rectTransform;
                rt.sizeDelta = new Vector2(288f * frac, rt.sizeDelta.y);
                hpFill.color = Color.Lerp(UiSkin.Red, UiSkin.RedLight, frac);
            }
            if (hpText != null) hpText.text = "生命 " + Mathf.CeilToInt(cur) + " / " + Mathf.CeilToInt(max);
            if (bleedText != null)
            {
                if (bleedText.gameObject.activeSelf != bleeding) bleedText.gameObject.SetActive(bleeding);
                if (bleeding)
                {
                    float a = 0.55f + 0.45f * Mathf.Abs(Mathf.Sin(Time.unscaledTime * 3.2f));
                    bleedText.color = new Color(UiSkin.Red.r, UiSkin.Red.g, UiSkin.Red.b, a);
                }
            }
        }

        // ---------------- 菜单窗框 ----------------

        private void BuildMenu()
        {
            menuRoot = UiKit.Stretch(canvas.transform, "Menu");

            // 全屏压暗层：同时负责挡住世界点击
            var dim = menuRoot.gameObject.AddComponent<Image>();
            dim.color = new Color(0.02f, 0.015f, 0.01f, 0.78f);
            dim.raycastTarget = true;

            menuWindow = UiKit.Center(menuRoot, "Window", 0f, 0f, 1560f, 860f);
            var winBg = menuWindow.gameObject.AddComponent<Image>();
            winBg.sprite = UiSkin.Window;
            winBg.type = Image.Type.Sliced;
            winBg.raycastTarget = true;
            UiKit.Corners(menuWindow, 14f, 52f);

            // 标题
            var title = UiKit.Title(menuWindow, "Title", "冒险手札", 40, UiSkin.GoldLight,
                34f, 12f, 480f, 54f, TextAnchor.MiddleLeft).WithShadow(0.85f);
            title.fontStyle = FontStyle.Bold;

            UiKit.Divider(menuWindow, "TitleDivider", 34f, 68f, 1492f);

            // 菜单内金币
            var goldPanel = UiKit.Panel(menuWindow, "GoldPanel", UiSkin.Slot, Color.white, 1186f, 16f, 250f, 52f);
            goldPanel.raycastTarget = false;
            UiKit.Icon(goldPanel.transform, "Coin", UiSkin.Coin, 10f, 10f, 32f, 32f);
            menuGoldText = UiKit.Label(goldPanel.transform, "Gold", "120", 25, UiSkin.GoldLight,
                50f, 9f, 186f, 34f, TextAnchor.MiddleLeft);
            menuGoldText.fontStyle = FontStyle.Bold;

            // 关闭按钮
            UiKit.TextButton(menuWindow, "CloseButton", "×", 1474f, 16f, 46f, 46f,
                () => SetMenuOpen(false), false, 28);

            // 左侧页签
            for (int i = 0; i < branches.Length; i++)
            {
                int index = i;
                var btn = UiKit.TextButton(menuWindow, "Nav" + i, branches[i].name, 24f, 96f + i * 72f, 224f, 62f,
                    () => ShowBranch(index), false, 24);
                var img = (Image)btn.targetGraphic;
                var text = btn.GetComponentInChildren<Text>();
                navImages.Add(img);
                navTexts.Add(text);
            }

            // 右侧内容区
            menuContent = UiKit.Place(menuWindow, "Content", 272f, 96f, 1260f, 700f);

            UiKit.Label(menuWindow, "Hint",
                "Tab 关闭　·　Esc 设置　·　左键点击卡片装备　·　右键装备到副手槽",
                18, UiSkin.TextMuted, 276f, 808f, 1200f, 30f, TextAnchor.MiddleLeft);
        }

        private void ShowBranch(int index)
        {
            if (branches == null || index < 0 || index >= branches.Length) return;
            currentBranch = index;

            if (menuContent == null) return;
            UiKit.ClearChildren(menuContent);
            branches[index].build(menuContent);

            // 页签高亮：当前页金底
            for (int i = 0; i < navImages.Count; i++)
            {
                if (navImages[i] == null) continue;
                navImages[i].sprite = i == currentBranch ? UiSkin.ButtonGold : UiSkin.Button;
                if (i < navTexts.Count && navTexts[i] != null)
                    navTexts[i].color = UiSkin.TextDark;
            }
        }

        private void SetMenuOpen(bool open)
        {
            if (open && overlayOpen) return;

            menuOpen = open;
            if (menuRoot != null) menuRoot.gameObject.SetActive(open);
            if (open) ShowBranch(currentBranch);
            RefreshOpenState();
        }

        private void ToggleMenu()
        {
            SetMenuOpen(!menuOpen);
        }

        private void ToggleSettingsPage()
        {
            // 与旧行为一致：已在设置页 → 关菜单；否则打开菜单并跳到设置页
            if (menuOpen && currentBranch == settingsBranchIndex)
            {
                SetMenuOpen(false);
                return;
            }
            SetMenuOpen(true);
            if (settingsBranchIndex >= 0) ShowBranch(settingsBranchIndex);
        }

        private void RefreshOpenState()
        {
            IsOpen = menuOpen || overlayOpen;
            if (combat != null) combat.enabled = !IsOpen;

            // ⚠️ 关键修复：对话/商店/任务板那层是「整屏 Stretch + Image」，它盖在菜单之上、
            // 只在打开时才有 alpha。但 uGUI 的射线检测**不看 alpha**，只要 raycastTarget=true
            // 就吃掉指针 —— 所以之前装备卡片的悬停/点击/拖拽全部被这层隐形遮罩吞掉，
            // 表现就是"鼠标点了完全没反应"。这里让它只在面板真的打开时挡射线。
            if (dimImage != null) dimImage.raycastTarget = overlayOpen;
        }

        // ---------------- Toast ----------------

        private void BuildToast()
        {
            toastRoot = UiKit.Node("Toast", canvas.transform);
            toastRoot.anchorMin = new Vector2(0.5f, 1f);
            toastRoot.anchorMax = new Vector2(0.5f, 1f);
            toastRoot.pivot = new Vector2(0.5f, 1f);
            toastRoot.sizeDelta = new Vector2(820f, 72f);
            toastRoot.anchoredPosition = new Vector2(0f, -28f);

            var bg = toastRoot.gameObject.AddComponent<Image>();
            bg.sprite = UiSkin.Card;
            bg.type = Image.Type.Sliced;
            bg.raycastTarget = false;
            UiKit.Corners(toastRoot, 6f, 26f);

            UiKit.Icon(toastRoot, "DiamondL", UiSkin.Diamond, 10f, 24f, 22f, 22f);
            UiKit.Icon(toastRoot, "DiamondR", UiSkin.Diamond, 788f, 24f, 22f, 22f);
            toastText = UiKit.Label(toastRoot, "Text", "", 22, UiSkin.TextDark,
                44f, 10f, 732f, 52f, TextAnchor.MiddleCenter);

            toastGroup = toastRoot.gameObject.AddComponent<CanvasGroup>();
            toastGroup.alpha = 0f;
            toastGroup.blocksRaycasts = false;
            toastGroup.interactable = false;
            toastRoot.gameObject.SetActive(false);
        }

        public void ShowToast(string message)
        {
            if (string.IsNullOrEmpty(message)) return;
            if (toastText == null) return;

            toastText.text = message;
            toastTimer = 0f;
            toastActive = true;
            if (!toastRoot.gameObject.activeSelf) toastRoot.gameObject.SetActive(true);
            toastGroup.alpha = 1f;
        }

        private void UpdateToast()
        {
            if (!toastActive || toastGroup == null) return;

            toastTimer += Time.unscaledDeltaTime;
            if (toastTimer < ToastHoldSeconds)
            {
                toastGroup.alpha = 1f;
                return;
            }
            float t = (toastTimer - ToastHoldSeconds) / ToastFadeSeconds;
            if (t >= 1f)
            {
                toastActive = false;
                toastGroup.alpha = 0f;
                toastRoot.gameObject.SetActive(false);
                return;
            }
            toastGroup.alpha = 1f - t;
        }

        // ---------------- 黑场 ----------------

        private void BuildFade()
        {
            var rt = UiKit.Stretch(canvas.transform, "Fade");
            fadeImage = rt.gameObject.AddComponent<Image>();
            fadeImage.color = new Color(0f, 0f, 0f, 0f);
            fadeImage.raycastTarget = false;
        }

        // ---------------- 武器事件（拾取 / 被打掉） ----------------

        private void WatchWeaponEvents()
        {
            if (loadout == null) return;

            if (lastPickupCount < 0)
            {
                lastPickupCount = loadout.PickupCount;
                lastHadMainHand = loadout.MainHand != null;
            }

            if (loadout.PickupCount > lastPickupCount)
            {
                lastPickupCount = loadout.PickupCount;
                var w = loadout.LastPickedUp;
                ShowToast(w != null
                    ? "拾取了 " + w.displayName + " —— 按 Tab 在「装备」页装备"
                    : "拾取到新武器 —— 按 Tab 打开装备页");
                RefreshWeaponSlots();
            }

            bool hasMain = loadout.MainHand != null;
            if (lastHadMainHand && !hasMain)
            {
                ShowToast("主手武器被打掉了！走过去就能捡回来");
                RefreshWeaponSlots();
            }
            lastHadMainHand = hasMain;

            if (!ReferenceEquals(loadout.MainHand, lastMain) || !ReferenceEquals(loadout.OffHand, lastOff))
                RefreshWeaponSlots();
        }

        // ---------------- 数据联动 ----------------

        private void HandleHealthChanged(float current, float max)
        {
            UpdateHealthHud();
        }

        private void HandleGoldChanged(int gold)
        {
            SetGold(gold);
        }

        private void HandleQuestChanged()
        {
            SetQuestTracker(QuestSystem.TrackerLine());
        }
    }
}
