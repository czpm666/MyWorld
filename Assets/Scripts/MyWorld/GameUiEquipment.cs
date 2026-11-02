using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using MyWorld.UI;

namespace MyWorld
{
    /// <summary>
    /// 菜单四个页签：装备 / 背包 / 角色 / 设置（GameUi 的 partial 部分）。
    ///
    /// 设计原则：
    ///   · 武器数值一律**只读** WeaponDefinition（伤害/冷却/特性），绝不写回；
    ///   · 装备规则完全交给 WeaponLoadout：左键 = Equip(自然槽位)，右键 = 副手槽武器快速装备；
    ///   · 所有卡片、槽位、按钮都在运行时用程序化 Sprite 搭出来，不依赖外部素材。
    /// </summary>
    public partial class GameUi
    {
        // ---------------- 装备页状态 ----------------

        private WeaponDefinition selectedWeapon;
        private readonly List<Image> cardFrames = new List<Image>();

        /// <summary>
        /// 武器卡悬停浮层。菜单每次导航都是 ClearChildren + 整页重建，
        /// 所以它只跟着当前这一页活着，不能跨页缓存复用（重建后引用会被 Unity 判成 null）。
        /// </summary>
        private UiTooltip weaponTooltip;

        // ---------------- 拖拽装备状态 ----------------
        /// <summary>拖动时跟着指针走的半透明图标；一次只可能有一个。</summary>
        private RectTransform dragGhostRoot;
        /// <summary>当前拖拽悬停的槽位（用于给槽位描边提亮）。</summary>
        private Image dragHoverSlot;

        // ---------------- 设置页状态 ----------------

        private static readonly string[] ResolutionLabels = { "1280 × 720", "1920 × 1080", "2048 × 1152", "2560 × 1440" };
        private static readonly int[] ResolutionWidths = { 1280, 1920, 2048, 2560 };
        private static readonly int[] ResolutionHeights = { 720, 1080, 1152, 1440 };
        private int settingsResolution = 1;
        private bool settingsFullscreen;
        private Text settingsStatus;

        // =================================================================
        //  装备页
        // =================================================================

        private void BuildEquipmentPage(RectTransform content)
        {
            cardFrames.Clear();
            weaponTooltip = null;   // 上一页的浮层节点已随 ClearChildren 销毁，引用作废
            if (loadout == null)
            {
                UiKit.Label(content, "NoLoadout", "（拿不到武器数据）", 22, UiSkin.TextMuted, 0f, 0f, 400f, 40f);
                return;
            }

            // 选中武器：优先玩家上次点的，其次已装备，最后第一把
            if (selectedWeapon == null || !ContainsWeapon(selectedWeapon))
                selectedWeapon = loadout.MainHand != null ? loadout.MainHand : (loadout.OffHand != null ? loadout.OffHand : FirstOwned());

            // ---------------- 左：角色 + 双手槽 ----------------
            var left = UiKit.Panel(content, "HeroPanel", UiSkin.Card, Color.white, 0f, 0f, 368f, 700f);
            UiKit.Corners(left.transform, 7f, 30f);

            var title = UiKit.Title(left.transform, "Title", "英 雄", 28, UiSkin.TextDark,
                20f, 8f, 200f, 42f, TextAnchor.MiddleLeft);
            title.fontStyle = FontStyle.Bold;
            UiKit.Divider(left.transform, "TitleDivider", 20f, 48f, 328f);

            UiKit.Icon(left.transform, "Crest", UiSkin.HeroCrest, 84f, 60f, 200f, 200f);
            var crestFrame = UiKit.Panel(left.transform, "CrestFrame", UiSkin.Frame(UiSkin.GoldDark), Color.white,
                80f, 56f, 208f, 208f);
            crestFrame.color = new Color(1f, 1f, 1f, 0.85f);

            var equippedLabel = UiKit.Label(left.transform, "EquippedLabel", "已 装 备", 18, UiSkin.Ink.Alpha(0.72f),
                20f, 266f, 200f, 26f, TextAnchor.MiddleLeft);
            equippedLabel.fontStyle = FontStyle.Bold;

            BuildEquipSlot(left.transform, 18f, 296f, 332f, 122f, "主手 · 左键", loadout.MainHand, HandSlot.MainHand);
            BuildEquipSlot(left.transform, 18f, 428f, 332f, 122f, "副手 · 右键", loadout.OffHand, HandSlot.OffHand);

            // 底部总览（只读显示，压成两行给外观切换腾位置；三项都必须完整可读）
            float cur = health != null ? health.Health : GameSession.Health;
            float max = health != null ? health.MaxHealth : GameSession.MaxHealth;
            if (max <= 0f) max = 1f;
            string overview =
                "生命　" + Mathf.CeilToInt(cur) + " / " + Mathf.CeilToInt(max) + "　·　金币　" + GameSession.Gold + "\n" +
                "已拥有武器　" + CountOwnedWeapons() + " / 6";
            UiKit.Label(left.transform, "Overview", overview, 16, UiSkin.TextDark,
                22f, 556f, 324f, 42f, TextAnchor.UpperLeft);

            // ---------------- 外观切换（法师 / 骑士 / 游侠） ----------------
            // 选中态沿用导航页签那套：ButtonGold + 深色文字 + 小火漆印。
            int look = GameSession.Appearance;
            var lookLabel = UiKit.Label(left.transform, "LookLabel", "外 观", 15, UiSkin.Ink.Alpha(0.72f),
                20f, 600f, 200f, 20f, TextAnchor.MiddleLeft);
            lookLabel.fontStyle = FontStyle.Bold;
            for (int i = 0; i < PlayerAppearance.LookNames.Length && i < 3; i++)
            {
                int index = i;
                bool selected = index == look;
                var button = UiKit.TextButton(left.transform, "Look" + i, PlayerAppearance.LookNames[i],
                    18f + i * 110f, 620f, 104f, 40f, () => SelectAppearance(index), selected, 17);
                var face = button.GetComponent<Image>();
                if (face != null) face.raycastTarget = true;   // UiKit.Panel 的 raycastTarget=false 老坑，显式兜底
                var caption = button.GetComponentInChildren<Text>();
                if (caption != null) caption.color = selected ? UiSkin.TextDark : UiSkin.TextLight;
                if (selected) BuildSeal(button.transform, "LookSeal", 78f, 16f, 20f);
            }

            // 拖拽这条信息页脚没有，留一行；左右各让 40px 避开四角装饰
            UiKit.Label(left.transform, "DragHint", "把卡片拖到槽里也能装备", 14, UiSkin.Ink.Alpha(0.55f),
                40f, 664f, 288f, 24f, TextAnchor.MiddleCenter);

            // ---------------- 右：6 张武器卡 + 详情 ----------------
            var cards = loadout.Owned;
            int visible = 0;
            for (int i = 0; i < cards.Count; i++)
            {
                var w = cards[i];
                if (w == null || w.kind == WeaponKind.Unarmed) continue;
                if (visible >= 6) break;   // 契约要求 6 张卡；多出来的不显示
                int col = visible % 2;
                int row = visible / 2;
                BuildWeaponCard(content, w, 384f + col * 446f, row * 166f);
                visible++;
            }

            // 空槽位补几张"待解锁"占位卡，保证视觉上是 2×3 的完整格子
            for (int i = visible; i < 6; i++)
            {
                int col = i % 2;
                int row = i / 2;
                BuildEmptyCard(content, 384f + col * 446f, row * 166f);
            }

            BuildWeaponDetail(content, 384f, 508f, 876f, 192f, selectedWeapon);

            // tooltip 最后建：uGUI 的绘制顺序与命中顺序就是兄弟顺序，放最后才能压在所有卡片和详情之上
            weaponTooltip = UiTooltip.Create(content, "WeaponTooltip");
        }

        private bool ContainsWeapon(WeaponDefinition weapon)
        {
            if (weapon == null || loadout == null) return false;
            var owned = loadout.Owned;
            for (int i = 0; i < owned.Count; i++) if (owned[i] == weapon) return true;
            return false;
        }

        private WeaponDefinition FirstOwned()
        {
            if (loadout == null) return null;
            var owned = loadout.Owned;
            for (int i = 0; i < owned.Count; i++)
                if (owned[i] != null && owned[i].kind != WeaponKind.Unarmed) return owned[i];
            return null;
        }

        private int CountOwnedWeapons()
        {
            if (loadout == null) return 0;
            int n = 0;
            var owned = loadout.Owned;
            for (int i = 0; i < owned.Count; i++)
                if (owned[i] != null && owned[i].kind != WeaponKind.Unarmed) n++;
            return n;
        }

        /// <summary>点外观按钮：先存档，再立刻换装（含选回法师时的原材质还原），最后重画本页刷新选中态。</summary>
        private void SelectAppearance(int index)
        {
            GameSession.SetAppearance(index);
            UiAppearanceBoot.ApplySaved();
            ShowBranch(currentBranch);
        }

        /// <summary>左侧的装备槽（深色凹槽 + 图标 + 名称 + 关键数值），同时是拖拽落点。</summary>
        private void BuildEquipSlot(Transform parent, float x, float y, float w, float h, string handLabel,
            WeaponDefinition weapon, HandSlot handSlot)
        {
            var slot = UiKit.Panel(parent, "EquipSlot_" + handLabel, UiSkin.Slot, Color.white, x, y, w, h);
            slot.raycastTarget = true;   // 默认 false，收不到 OnDrop

            // 拖拽落点：这里只负责"接住"，规则判断在 HandleWeaponDrop
            var drop = slot.gameObject.AddComponent<ClickRelay>();
            drop.onDrop = data =>
            {
                if (data == null || data.pointerDrag == null) return;
                var payload = data.pointerDrag.GetComponent<WeaponDragPayload>();
                if (payload != null) HandleWeaponDrop(handSlot, payload);
            };
            drop.onEnter = _ => { slot.color = new Color(1.06f, 1.04f, 0.92f, 1f); };
            drop.onExit = _ => { slot.color = Color.white; };

            UiKit.Icon(slot.transform, "Icon", UiIconLibrary.Load(weapon != null ? weapon.kind : WeaponKind.Unarmed),
                12f, (h - 88f) * 0.5f, 88f, 88f);

            var hand = UiKit.Label(slot.transform, "Hand", handLabel, 15, UiSkin.GoldLight,
                110f, 10f, w - 120f, 22f, TextAnchor.MiddleLeft);
            hand.WithShadow(0.85f);

            var name = UiKit.Label(slot.transform, "Name",
                weapon != null ? weapon.displayName : "空手",
                22, UiSkin.TextLight, 110f, 32f, w - 120f, 30f, TextAnchor.MiddleLeft);
            name.WithShadow(0.85f);
            name.fontStyle = FontStyle.Bold;

            string stats = weapon != null ? WeaponStatsLine(weapon) : "没有任何武器，按左键挥拳";
            var st = UiKit.Label(slot.transform, "Stats", stats, 15, UiSkin.TextMuted,
                110f, 66f, w - 120f, 46f, TextAnchor.UpperLeft);
            st.WithShadow(0.7f);
        }

        /// <summary>一张武器卡：图标 + 名称 + 关键数值 + 稀有度色边框 + 火漆"已装备"角标 + 悬停描边 + 悬停浮层。</summary>
        private void BuildWeaponCard(Transform parent, WeaponDefinition weapon, float x, float y)
        {
            bool equippedMain = loadout.MainHand == weapon;
            bool equippedOff = loadout.OffHand == weapon;
            bool equipped = equippedMain || equippedOff;
            bool selected = selectedWeapon == weapon;
            Color rarity = RarityColor(weapon.kind);

            var card = UiKit.Panel(parent, "Card_" + weapon.kind, UiSkin.Card, Color.white, x, y, 430f, 156f);
            // ⚠️ UiKit.Panel 默认 raycastTarget=false，卡片要收悬停/左右键就必须自己当射线目标，
            // 否则 HoverTint / ClickRelay / tooltip 永远不会被触发（之前的卡片就是"点不动"的）。
            card.raycastTarget = true;

            // 稀有度色边框（选中时再加一层亮金）
            var rarityFrame = UiKit.Panel(card.transform, "RarityFrame", UiSkin.Frame(rarity),
                new Color(1f, 1f, 1f, 0.9f), 0f, 0f, 430f, 156f);
            cardFrames.Add(rarityFrame);

            UiKit.Icon(card.transform, "Icon", UiIconLibrary.Load(weapon.kind), 14f, 26f, 100f, 100f);

            var name = UiKit.Label(card.transform, "Name", weapon.displayName, 26, UiSkin.TextDark,
                126f, 12f, 190f, 34f, TextAnchor.MiddleLeft);
            name.fontStyle = FontStyle.Bold;

            UiKit.Label(card.transform, "Rarity", RarityName(weapon.kind), 16, rarity,
                300f, 14f, 116f, 24f, TextAnchor.MiddleRight);

            UiKit.Label(card.transform, "SlotLabel", weapon.slot == HandSlot.MainHand ? "主手槽" : "副手槽",
                16, UiSkin.Ink.Alpha(0.62f), 126f, 48f, 150f, 22f, TextAnchor.MiddleLeft);

            // 数值列宽：已装备的卡片右上角盖着火漆印（48px 方块斜 12° 后实际左缘 ≈ 369），
            // 列必须收窄到 232 才不会让文字伸到印章底下（否则"盾击 12"会压住印章左边）。
            float statsWidth = equipped ? 232f : 286f;
            UiKit.Label(card.transform, "Stats", WeaponStatsLine(weapon), 16, UiSkin.TextDark,
                126f, 72f, statsWidth, 46f, TextAnchor.UpperLeft);

            if (equipped)
            {
                // 火漆印章角标（UiSkin.Seal 在本工程第一次被用上）：斜盖在卡片右上角。
                // 48px @ (374,66) 旋转后的 AABB ≈ 369..427 × 61..119，完全留在 430×156 的卡内。
                BuildSeal(card.transform, "EquippedSeal", 374f, 66f, 48f);
                var badge = UiKit.Label(card.transform, "EquippedBadge",
                    "已装备 · " + (equippedMain ? "主手" : "副手"),
                    16, UiSkin.Red, 246f, 130f, 176f, 22f, TextAnchor.MiddleRight);
                badge.fontStyle = FontStyle.Bold;
            }
            else
            {
                UiKit.Label(card.transform, "Hint",
                    weapon.slot == HandSlot.OffHand ? "左键 / 右键装备到副手" : "左键装备到主手",
                    14, UiSkin.Ink.Alpha(0.55f), 126f, 126f, 250f, 20f, TextAnchor.MiddleLeft);
            }

            // 悬停描边（选中卡已经有金框，就不再叠第二圈，免得两圈金边糊在一起）
            Image hoverFrame = null;
            if (!selected)
            {
                hoverFrame = UiKit.Panel(card.transform, "HoverFrame", UiSkin.Frame(UiSkin.GoldLight),
                    new Color(1f, 1f, 1f, 0f), -3f, -3f, 436f, 162f);
                hoverFrame.raycastTarget = false;
            }

            if (selected)
            {
                var sel = UiKit.Panel(card.transform, "SelectionFrame", UiSkin.Frame(UiSkin.GoldLight),
                    new Color(1f, 1f, 1f, 0.95f), -3f, -3f, 436f, 162f);
                sel.raycastTarget = false;
            }

            // 悬停提亮 + 左右键点击 + 悬停描边/浮层
            UiKit.AddHoverTint(card, Color.white, new Color(1.05f, 1.03f, 0.95f));
            var relay = card.gameObject.AddComponent<ClickRelay>();
            relay.onClick = data =>
            {
                if (data != null && data.button == PointerEventData.InputButton.Right)
                    OnWeaponCardRightClick(weapon);
                else
                    OnWeaponCardLeftClick(weapon);
            };

            var frame = hoverFrame;
            relay.onEnter = _ =>
            {
                if (frame != null) frame.color = new Color(1f, 1f, 1f, 0.95f);
                HoverTooltip(weapon);
            };
            relay.onExit = _ =>
            {
                if (frame != null) frame.color = new Color(1f, 1f, 1f, 0f);
                DismissTooltip();
            };

            // ---- 拖拽：卡片可以拖到左侧槽位 ----
            var payload = card.gameObject.AddComponent<WeaponDragPayload>();
            payload.kind = weapon.kind;
            payload.slot = weapon.slot;
            payload.displayName = weapon.displayName;

            relay.onBeginDrag = data => BeginDragWeapon(payload, card.canvas, data);
            relay.onDrag = UpdateDragWeapon;
            relay.onEndDrag = _ => EndDragWeapon();
        }

        // =================================================================
        //  拖拽装备
        // =================================================================

        private void BeginDragWeapon(WeaponDragPayload payload, Canvas canvas, PointerEventData data)
        {
            EndDragWeapon();
            if (payload == null || canvas == null) return;
            DismissTooltip();

            var go = new GameObject("DragGhost", typeof(RectTransform), typeof(Image));
            var rt = (RectTransform)go.transform;
            rt.SetParent(canvas.transform, false);
            rt.SetAsLastSibling();
            rt.anchorMin = rt.anchorMax = new Vector2(0.5f, 0.5f);
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = new Vector2(88f, 88f);

            var img = go.GetComponent<Image>();
            img.sprite = UiIconLibrary.Load(payload.kind);
            img.raycastTarget = false;                 // 不能挡住指针，否则收不到 OnDrop
            img.color = new Color(1f, 1f, 1f, 0.82f);
            img.preserveAspect = true;

            dragGhostRoot = rt;
            UpdateDragWeapon(data);
        }

        private void UpdateDragWeapon(PointerEventData data)
        {
            if (dragGhostRoot == null || data == null) return;
            var parent = dragGhostRoot.parent as RectTransform;
            if (parent == null) return;
            Vector2 local;
            if (RectTransformUtility.ScreenPointToLocalPointInRectangle(
                    parent, data.position, data.pressEventCamera, out local))
                dragGhostRoot.anchoredPosition = local;

            // 拖到槽上时把槽提亮（槽自己的 onEnter 在拖拽期间收不到，这里补）
            var hover = data.pointerCurrentRaycast.gameObject;
            Image hit = hover != null ? hover.GetComponentInParent<Image>() : null;
            if (hit != dragHoverSlot)
            {
                if (dragHoverSlot != null) dragHoverSlot.color = Color.white;
                dragHoverSlot = (hit != null && hit.gameObject.name.StartsWith("EquipSlot_")) ? hit : null;
                if (dragHoverSlot != null) dragHoverSlot.color = new Color(1.10f, 1.06f, 0.86f, 1f);
            }
        }

        private void EndDragWeapon()
        {
            if (dragHoverSlot != null) { dragHoverSlot.color = Color.white; dragHoverSlot = null; }
            if (dragGhostRoot != null)
            {
                Destroy(dragGhostRoot.gameObject);
                dragGhostRoot = null;
            }
        }

        /// <summary>把拖到某个槽上的武器装上去。槽和武器的原生栏位不一致时拒绝并说明。</summary>
        private void HandleWeaponDrop(HandSlot hand, WeaponDragPayload payload)
        {
            if (loadout == null || payload == null) return;

            WeaponDefinition def = FindOwned(payload.kind);
            if (def == null) { ShowToast("找不到这把武器"); return; }

            if (def.slot != hand)
            {
                ShowToast("「" + def.displayName + "」是" +
                          (def.slot == HandSlot.MainHand ? "主手" : "副手") + "武器，放不进这个槽");
                return;
            }

            selectedWeapon = def;
            loadout.Equip(def);
            if (mount != null) mount.Refresh(loadout);
            RefreshWeaponSlots();
            ShowToast("已装备 " + def.displayName + " → " + (hand == HandSlot.MainHand ? "主手槽" : "副手槽"));
            ShowBranch(currentBranch);
        }

        private WeaponDefinition FindOwned(WeaponKind kind)
        {
            if (loadout == null) return null;
            var owned = loadout.Owned;
            for (int i = 0; i < owned.Count; i++)
                if (owned[i] != null && owned[i].kind == kind) return owned[i];
            return null;
        }

        /// <summary>
        /// 悬停时才开始用浮层。浮层节点是整页构建的**最后一步**才建的（要当最后一个兄弟节点才能压在卡片上），
        /// 所以卡片构建时字段还是 null —— 这里在悬停那一刻现取，不能提前抓进 lambda。
        /// </summary>
        private void HoverTooltip(WeaponDefinition weapon)
        {
            if (weaponTooltip != null)
                weaponTooltip.Request(rt => BuildWeaponTooltip(rt, weapon));
        }

        private void DismissTooltip()
        {
            if (weaponTooltip != null) weaponTooltip.Dismiss();
        }

        private void BuildEmptyCard(Transform parent, float x, float y)
        {
            var card = UiKit.Panel(parent, "EmptyCard", UiSkin.Slot, new Color(1f, 1f, 1f, 0.9f), x, y, 430f, 156f);
            var icon = UiKit.Icon(card.transform, "Icon", UiSkin.ScrollIcon, 26f, 26f, 100f, 100f);
            icon.color = new Color(1f, 1f, 1f, 0.35f);
            UiKit.Label(card.transform, "Hint", "尚未获得\n去世界各处拾取武器", 18, UiSkin.TextMuted,
                140f, 44f, 260f, 70f, TextAnchor.MiddleLeft);
        }

        private void OnWeaponCardLeftClick(WeaponDefinition weapon)
        {
            if (weapon == null || loadout == null) return;

            selectedWeapon = weapon;
            loadout.Equip(weapon);
            if (mount != null) mount.Refresh(loadout);
            RefreshWeaponSlots();

            bool toMain = loadout.MainHand == weapon;
            ShowToast("已装备 " + weapon.displayName + " → " + (toMain ? "主手槽" : "副手槽"));
            ShowBranch(currentBranch);
        }

        private void OnWeaponCardRightClick(WeaponDefinition weapon)
        {
            if (weapon == null || loadout == null) return;

            // 右键只对副手武器生效：主手武器硬塞进副手槽会绕过 WeaponLoadout 的兼容规则
            if (weapon.slot != HandSlot.OffHand)
            {
                ShowToast("「" + weapon.displayName + "」是主手武器，请用左键装备");
                return;
            }

            selectedWeapon = weapon;
            loadout.Equip(weapon);
            if (mount != null) mount.Refresh(loadout);
            RefreshWeaponSlots();
            ShowToast("已装备 " + weapon.displayName + " → 副手槽");
            ShowBranch(currentBranch);
        }

        /// <summary>底部详情：名称 / 稀有度 / 属性条（并与已装备武器逐条对比）/ 特性 / 装备按钮。</summary>
        private void BuildWeaponDetail(Transform parent, float x, float y, float w, float h, WeaponDefinition weapon)
        {
            var panel = UiKit.Panel(parent, "Detail", UiSkin.Card, Color.white, x, y, w, h);
            UiKit.Corners(panel.transform, 6f, 24f);

            if (weapon == null)
            {
                UiKit.Label(panel.transform, "Empty", "还没有选中武器 —— 点上面的卡片看看详情", 20, UiSkin.TextMuted,
                    24f, 20f, w - 48f, 40f, TextAnchor.MiddleLeft);
                return;
            }

            bool equipped = loadout.MainHand == weapon || loadout.OffHand == weapon;

            var title = UiKit.Title(panel.transform, "Name", weapon.displayName, 28, UiSkin.TextDark,
                20f, 4f, 300f, 40f, TextAnchor.MiddleLeft);
            title.fontStyle = FontStyle.Bold;

            if (equipped) BuildSeal(panel.transform, "EquippedSeal", 396f, 0f, 38f);

            UiKit.Label(panel.transform, "Rarity",
                RarityName(weapon.kind) + "　·　" + (weapon.slot == HandSlot.MainHand ? "主手武器" : "副手武器"),
                16, RarityColor(weapon.kind), 20f, 44f, 420f, 24f, TextAnchor.MiddleLeft);

            UiKit.Divider(panel.transform, "Divider", 20f, 70f, 436f);

            // 属性对比：基准 = 同槽位已装备的那把；同槽空着 / 就是自己 → 退到另一只手
            string caption;
            var baseline = ComparisonBaseline(weapon, out caption);
            var baselineMap = baseline != null ? MetricMap(baseline) : null;
            UiKit.Label(panel.transform, "Compare",
                baseline != null ? caption + "　·　绿=更强 红=更弱" : caption + "　·　没有对比基准",
                15, UiSkin.Ink.Alpha(0.6f), 20f, 86f, 436f, 18f, TextAnchor.MiddleLeft);

            var metrics = WeaponMetrics(weapon);
            for (int i = 0; i < metrics.Count && i < 3; i++)
                BuildMetricRow(panel.transform, "Metric" + i, 20f, 104f + i * 26f, 436f, metrics[i], baselineMap);

            // 右列：竖分隔线 + 特性文案 + 装备按钮
            var rule = UiKit.Panel(panel.transform, "ColumnRule", UiSkin.White, UiSkin.Gold.Alpha(0.3f),
                462f, 12f, 1.5f, h - 24f);
            rule.raycastTarget = false;

            UiKit.Label(panel.transform, "Trait", WeaponTraitLine(weapon), 16, UiSkin.Ink.Alpha(0.82f),
                480f, 8f, 376f, 124f, TextAnchor.UpperLeft);

            var button = UiKit.TextButton(panel.transform, "EquipButton", equipped ? "已装备" : "装备", 690f, 140f, 166f, 44f,
                () => OnWeaponCardLeftClick(weapon), !equipped, 22);
            button.interactable = !equipped;
        }

        // ---------------- 数值文案（只读） ----------------

        private static string RarityColorHex(WeaponKind kind)
        {
            return "#" + ColorUtility.ToHtmlStringRGB(RarityColor(kind));
        }

        private static Color RarityColor(WeaponKind kind)
        {
            switch (kind)
            {
                case WeaponKind.Staff: return UiSkin.Blue;
                case WeaponKind.Gauntlet: return UiSkin.Purple;
                case WeaponKind.Bow:
                case WeaponKind.Shield: return UiSkin.Green;
                case WeaponKind.Grapple: return UiSkin.Orange;
                default: return UiSkin.Gold;
            }
        }

        private static string RarityName(WeaponKind kind)
        {
            switch (kind)
            {
                case WeaponKind.Staff: return "稀有 · 奥术";
                case WeaponKind.Gauntlet: return "史诗 · 奥术";
                case WeaponKind.Bow: return "精良 · 远程";
                case WeaponKind.Shield: return "精良 · 防御";
                case WeaponKind.Grapple: return "精良 · 工具";
                default: return "普通";
            }
        }

        /// <summary>关键数值一行（伤害 / 冷却等，全部来自 WeaponDefinition 只读字段）。</summary>
        private static string WeaponStatsLine(WeaponDefinition w)
        {
            if (w == null) return "";

            // 与 tooltip / 详情里的属性条共用同一份只读数值，免得两处文案对不上
            var metrics = WeaponMetrics(w);
            var parts = new List<string>(metrics.Count + 1);
            for (int i = 0; i < metrics.Count; i++)
                parts.Add(metrics[i].label + " " + metrics[i].display);
            if (w.kind == WeaponKind.Grapple) parts.Add("位移工具");
            return string.Join(" · ", parts);
        }

        /// <summary>特性说明（同样是只读字段拼出来，不写任何玩法逻辑）。</summary>
        private static string WeaponTraitLine(WeaponDefinition w)
        {
            if (w == null) return "";
            switch (w.kind)
            {
                case WeaponKind.Staff:
                    return "远程奥术法杖：消耗魔力发射法术弹。「施法速度 ×" + w.castSpeedMultiplier.ToString("0.##") + "」影响出手接续节奏。";
                case WeaponKind.Sword:
                    return "近战挥砍：范围 " + w.meleeRange.ToString("0.##") + "m / 半角 " + w.meleeHalfAngle.ToString("0") + "°，命中击退 " + w.stabKnockbackGrids.ToString("0.#") + " 格。";
                case WeaponKind.Bow:
                    return "远程弓：箭矢速度 " + w.arrowSpeed.ToString("0.#") + "，飞行 " + w.arrowLifeTime.ToString("0.##") + "s；可蓄力瞄准。";
                case WeaponKind.Shield:
                    return "副手盾：按住可格挡（减伤 " + Mathf.RoundToInt((1f - w.blockDamageMultiplier) * 100f) + "%），右键盾击造成 " + w.shieldBashDamage.ToString("0.#") + " 伤害并击退 " + w.shieldBashKnockbackGrids.ToString("0.#") + " 格。";
                case WeaponKind.Gauntlet:
                    return "副手魔法护手：强化法术——施法速度 ×" + w.castSpeedMultiplier.ToString("0.##") + "，法术伤害 ×" + w.castDamageMultiplier.ToString("0.##") + "。";
                case WeaponKind.Grapple:
                    return "副手抓钩：勾住地形拉近 / 位移，是探索地图的关键工具。";
                default:
                    return "";
            }
        }

        // =================================================================
        //  属性指标（卡片文案 / 属性条 / tooltip / 对比 共用同一份只读数据）
        // =================================================================

        // 条形长度用的参考值（满条 ≈ 什么水平）。只影响视觉长度，不改任何玩法数值。
        private const float DamageFull = 40f;
        private const float CastSpeedFull = 2f;
        private const float ArrowSpeedFull = 60f;
        private const float MeleeRangeFull = 5f;
        private const float BashDamageFull = 20f;
        private const float CooldownBest = 0.3f;    // 冷却 0.3s 记满条
        private const float CooldownWorst = 2f;     // 冷却 2.0s 记空条

        /// <summary>一条可展示 / 可比对的武器属性。数值全部直接来自 WeaponDefinition 的只读字段。</summary>
        private struct WeaponMetric
        {
            public string label;        // 伤害 / 冷却 / 施法速度 …
            public float value;         // 原始数值（算差值用）
            public string display;      // "24" / "0.5s" / "×1.5" / "75%"
            public float quality;       // 0..1，条形长度（已折算成"越大越好"）
            public Color barColor;
            public bool higherBetter;   // 跟基准比时，数值更大算更好吗
            public string unit;         // 差值后缀："" / "s" / "%" / "×"
        }

        private static WeaponMetric MakeMetric(string label, float value, string display, float quality,
            Color color, bool higherBetter, string unit)
        {
            return new WeaponMetric
            {
                label = label,
                value = value,
                display = display,
                quality = Mathf.Clamp01(quality),
                barColor = color,
                higherBetter = higherBetter,
                unit = unit,
            };
        }

        /// <summary>把一把武器的只读数值整理成指标列表（每种武器 1~3 条，正好在详情栏里一行一条）。</summary>
        private static List<WeaponMetric> WeaponMetrics(WeaponDefinition w)
        {
            var list = new List<WeaponMetric>(3);
            if (w == null) return list;

            switch (w.kind)
            {
                case WeaponKind.Staff:
                    AddDamageMetric(list, w);
                    AddCooldownMetric(list, w);
                    AddCastSpeedMetric(list, w);
                    break;

                case WeaponKind.Bow:
                    AddDamageMetric(list, w);
                    AddCooldownMetric(list, w);
                    list.Add(MakeMetric("箭速", w.arrowSpeed, w.arrowSpeed.ToString("0.#"),
                        w.arrowSpeed / ArrowSpeedFull, UiSkin.Gold, true, ""));
                    break;

                case WeaponKind.Sword:
                    AddDamageMetric(list, w);
                    AddCooldownMetric(list, w);
                    list.Add(MakeMetric("范围", w.meleeRange, w.meleeRange.ToString("0.##") + "m",
                        w.meleeRange / MeleeRangeFull, UiSkin.Green, true, "m"));
                    break;

                case WeaponKind.Shield:
                    float block = Mathf.Clamp01(1f - w.blockDamageMultiplier);
                    list.Add(MakeMetric("格挡减伤", block, Mathf.RoundToInt(block * 100f) + "%",
                        block, UiSkin.Blue, true, "%"));
                    AddCooldownMetric(list, w);
                    list.Add(MakeMetric("盾击", w.shieldBashDamage, w.shieldBashDamage.ToString("0.#"),
                        w.shieldBashDamage / BashDamageFull, UiSkin.RedLight, true, ""));
                    break;

                case WeaponKind.Gauntlet:
                    AddDamageMetric(list, w);
                    AddCooldownMetric(list, w);
                    AddCastSpeedMetric(list, w);
                    break;

                case WeaponKind.Grapple:
                    AddCooldownMetric(list, w);   // 工具类没有伤害
                    break;

                default:
                    AddDamageMetric(list, w);
                    AddCooldownMetric(list, w);
                    break;
            }
            return list;
        }

        private static void AddDamageMetric(List<WeaponMetric> list, WeaponDefinition w)
        {
            list.Add(MakeMetric("伤害", w.damage, w.damage.ToString("0.#"),
                w.damage / DamageFull, UiSkin.RedLight, true, ""));
        }

        private static void AddCooldownMetric(List<WeaponMetric> list, WeaponDefinition w)
        {
            // 冷却越短越好 → 条形长度反向折算（0.3s 满条，2.0s 空条）
            float quality = Mathf.InverseLerp(CooldownWorst, CooldownBest, w.cooldown);
            list.Add(MakeMetric("冷却", w.cooldown, w.cooldown.ToString("0.##") + "s",
                quality, UiSkin.Gold, false, "s"));
        }

        private static void AddCastSpeedMetric(List<WeaponMetric> list, WeaponDefinition w)
        {
            list.Add(MakeMetric("施法速度", w.castSpeedMultiplier, "×" + w.castSpeedMultiplier.ToString("0.##"),
                w.castSpeedMultiplier / CastSpeedFull, UiSkin.Blue, true, "×"));
        }

        private static Dictionary<string, WeaponMetric> MetricMap(WeaponDefinition weapon)
        {
            var map = new Dictionary<string, WeaponMetric>();
            var metrics = WeaponMetrics(weapon);
            for (int i = 0; i < metrics.Count; i++) map[metrics[i].label] = metrics[i];
            return map;
        }

        /// <summary>
        /// 属性对比的基准武器：优先"这把武器天然对应的槽位"（新法杖 vs 已装备法杖），
        /// 同槽空着 / 就是它自己时退到另一只手（新法杖 vs 已装备副手）；都没有就返回 null。
        /// </summary>
        private WeaponDefinition ComparisonBaseline(WeaponDefinition weapon, out string caption)
        {
            caption = "";
            if (loadout == null || weapon == null) return null;

            bool mainSlot = weapon.slot == HandSlot.MainHand;
            var same = mainSlot ? loadout.MainHand : loadout.OffHand;
            var other = mainSlot ? loadout.OffHand : loadout.MainHand;
            string sameLabel = mainSlot ? "主手" : "副手";
            string otherLabel = mainSlot ? "副手" : "主手";

            if (same != null && same != weapon)
            {
                caption = "对比" + sameLabel + "「" + same.displayName + "」";
                return same;
            }

            if (other != null && other != weapon)
            {
                caption = (same == weapon ? "已装备在" + sameLabel + " · " : sameLabel + "槽空着 · ")
                    + "对比" + otherLabel + "「" + other.displayName + "」";
                return other;
            }

            caption = same == weapon ? "已装备在" + sameLabel + "槽" : sameLabel + "槽空着";
            return null;
        }

        /// <summary>一行属性：名称 + 属性条（UiSkin.BarFill）+ 数值 + 与基准的差值。</summary>
        private static void BuildMetricRow(Transform parent, string id, float x, float y, float w,
            WeaponMetric metric, Dictionary<string, WeaponMetric> baseline)
        {
            // 名称列必须宽于 4 个汉字：「格挡减伤」「施法速度」= 4×16 = 64px，
            // 正好给 64px 会踩在换行边界上（Text 是 Wrap + Overflow），一旦折行第二行就会压进下一行属性里。
            const float nameW = 78f;
            const float barW = 172f;
            const float valueW = 88f;
            const float gap = 6f;

            UiKit.Label(parent, id + "Name", metric.label, 16, UiSkin.Ink.Alpha(0.78f),
                x, y, nameW, 26f, TextAnchor.MiddleLeft);

            float barX = x + nameW;
            var track = UiKit.Panel(parent, id + "Bar", UiSkin.BarFill, UiSkin.Ink.Alpha(0.40f),
                barX, y + 7f, barW, 13f);
            track.raycastTarget = false;

            // 空条也留一小截，否则 0 值看起来像"根本没画"
            float fill = Mathf.Clamp(metric.quality, 0.06f, 1f) * (barW - 4f);
            var bar = UiKit.Panel(track.transform, "Fill", UiSkin.BarFill, metric.barColor, 2f, 2f, fill, 9f);
            bar.raycastTarget = false;

            float valueX = barX + barW + gap;
            var value = UiKit.Label(parent, id + "Value", metric.display, 17, UiSkin.TextDark,
                valueX, y, valueW, 26f, TextAnchor.MiddleRight);
            value.fontStyle = FontStyle.Bold;

            // 差值列吃掉"传进来的行宽"剩下的部分：详情栏和 tooltip 的内宽不同（436 / 442），
            // 用 w 推右边界，两边都不会漫出去（而不是写死一个数）。
            float deltaX = valueX + valueW + gap;
            float deltaW = Mathf.Max(60f, x + w - deltaX);
            var delta = UiKit.Label(parent, id + "Delta", "", 16, UiSkin.TextMuted,
                deltaX, y, deltaW, 26f, TextAnchor.MiddleRight);
            delta.fontStyle = FontStyle.Bold;

            WeaponMetric baseMetric;
            if (baseline != null && baseline.TryGetValue(metric.label, out baseMetric))
            {
                Color deltaColor;
                delta.text = DeltaText(metric, baseMetric.value, out deltaColor);
                delta.color = deltaColor;
            }
        }

        /// <summary>
        /// 差值文案与颜色。颜色看**好坏**而不是正负：绿 = 比基准更强（伤害更高 / 冷却更短），红 = 更弱；
        /// 所以"冷却 +0.3s"是红的、"冷却 -0.3s"是绿的（这点在文案里标了"绿=更强 红=更弱"）。
        /// </summary>
        private static string DeltaText(WeaponMetric metric, float baseValue, out Color color)
        {
            float diff = metric.value - baseValue;
            if (Mathf.Abs(diff) < 0.005f)
            {
                color = UiSkin.TextMuted;
                return "±0";
            }

            bool better = metric.higherBetter ? diff > 0f : diff < 0f;
            color = better ? UiSkin.Green : UiSkin.RedLight;
            return (diff > 0f ? "+" : "-") + Mathf.Abs(diff).ToString("0.##") + metric.unit;
        }

        /// <summary>火漆印章（UiSkin.Seal）角标：略微倾斜 + 投影，像刚盖上去的。</summary>
        private static Image BuildSeal(Transform parent, string name, float x, float y, float size)
        {
            var seal = UiKit.Icon(parent, name, UiSkin.Seal, x, y, size, size);
            seal.rectTransform.localEulerAngles = new Vector3(0f, 0f, -12f);
            var shadow = seal.gameObject.AddComponent<Shadow>();
            shadow.effectColor = new Color(0f, 0f, 0f, 0.35f);
            shadow.effectDistance = new Vector2(2f, -2f);
            shadow.useGraphicAlpha = true;
            return seal;
        }

        // =================================================================
        //  悬停浮层内容（计时 / 跟随由 UiTooltip 负责，这里只铺内容）
        // =================================================================

        /// <summary>武器卡悬停后的说明浮层：名称 / 稀有度 / 全部属性（带对比）/ 特性 / 是否已装备。</summary>
        private void BuildWeaponTooltip(RectTransform panel, WeaponDefinition weapon)
        {
            const float w = 470f;
            const float pad = 14f;
            float inner = w - pad * 2f;

            var bg = UiKit.PanelFill(panel, "Bg", UiSkin.ParchmentPanel, new Color(1f, 1f, 1f, 0.99f));
            var shadow = bg.gameObject.AddComponent<Shadow>();
            shadow.effectColor = new Color(0f, 0f, 0f, 0.45f);
            shadow.effectDistance = new Vector2(4f, -4f);
            shadow.useGraphicAlpha = true;

            var frame = UiKit.PanelFill(panel, "Frame", UiSkin.Frame(RarityColor(weapon.kind)),
                new Color(1f, 1f, 1f, 0.9f));
            frame.raycastTarget = false;
            UiKit.Corners(panel, 10f, 34f);

            float y = 10f;

            var title = UiKit.Title(panel, "Name", weapon.displayName, 24, UiSkin.TextDark,
                pad, y, inner, 32f, TextAnchor.MiddleLeft);
            title.fontStyle = FontStyle.Bold;
            y += 34f;

            UiKit.Label(panel, "Rarity",
                RarityName(weapon.kind) + "　·　" + (weapon.slot == HandSlot.MainHand ? "主手武器" : "副手武器"),
                16, RarityColor(weapon.kind), pad, y, inner, 22f, TextAnchor.MiddleLeft);
            y += 26f;

            UiKit.Divider(panel, "DividerTop", pad, y, inner);
            y += 22f;

            string caption;
            var baseline = ComparisonBaseline(weapon, out caption);
            var baselineMap = baseline != null ? MetricMap(baseline) : null;

            var metrics = WeaponMetrics(weapon);
            for (int i = 0; i < metrics.Count; i++)
            {
                BuildMetricRow(panel, "Metric" + i, pad, y, inner, metrics[i], baselineMap);
                y += 26f;
            }

            UiKit.Label(panel, "Compare", baseline != null ? caption + "　·　绿=更强 红=更弱" : caption,
                15, UiSkin.Ink.Alpha(0.6f), pad, y, inner, 18f, TextAnchor.MiddleLeft);
            y += 22f;

            UiKit.Divider(panel, "DividerBottom", pad, y, inner);
            y += 22f;

            var trait = UiKit.Label(panel, "Trait", WeaponTraitLine(weapon), 16, UiSkin.Ink.Alpha(0.85f),
                pad, y, inner, 22f, TextAnchor.UpperLeft);
            // 按实际宽度换行后的真实高度（Text.preferredHeight），浮层高度跟着内容走，不写死
            float traitHeight = trait.preferredHeight;
            if (float.IsNaN(traitHeight) || traitHeight < 22f) traitHeight = 22f;
            y += traitHeight + 6f;

            bool equippedMain = loadout.MainHand == weapon;
            bool equippedOff = loadout.OffHand == weapon;
            if (equippedMain || equippedOff)
            {
                BuildSeal(panel, "Seal", pad, y - 1f, 30f);
                var line = UiKit.Label(panel, "EquippedLine", "已装备 · " + (equippedMain ? "主手槽" : "副手槽"),
                    16, UiSkin.Red, pad + 38f, y, inner - 38f, 28f, TextAnchor.MiddleLeft);
                line.fontStyle = FontStyle.Bold;
            }
            else
            {
                UiKit.Label(panel, "ActionLine",
                    weapon.slot == HandSlot.MainHand ? "左键：装备到主手槽" : "左键 / 右键：装备到副手槽",
                    16, UiSkin.Ink.Alpha(0.7f), pad, y, inner, 28f, TextAnchor.MiddleLeft);
            }
            y += 32f;

            panel.sizeDelta = new Vector2(w, y + 6f);
        }

        // =================================================================
        //  背包页（物品来自 GameSession.PurchasedItemIds）
        // =================================================================

        private void BuildBackpackPage(RectTransform content)
        {
            var title = UiKit.Title(content, "Title", "背 包", 34, UiSkin.GoldLight,
                0f, 0f, 320f, 44f, TextAnchor.MiddleLeft);
            title.fontStyle = FontStyle.Bold;
            UiKit.Divider(content, "TitleDivider", 0f, 48f, 1260f);

            List<string> ids = new List<string>();
            var purchased = GameSession.PurchasedItemIds;
            if (purchased != null)
            {
                for (int i = 0; i < purchased.Count; i++)
                {
                    string id = purchased[i];
                    if (!string.IsNullOrEmpty(id) && !ids.Contains(id)) ids.Add(id);
                }
            }

            if (ids.Count == 0)
            {
                var empty = UiKit.Panel(content, "EmptyPanel", UiSkin.Card, Color.white, 330f, 160f, 600f, 330f);
                UiKit.Corners(empty.transform, 10f, 34f);
                var icon = UiKit.Icon(empty.transform, "BagIcon", UiSkin.BagIcon, 250f, 40f, 100f, 100f);
                icon.color = new Color(1f, 1f, 1f, 0.8f);
                UiKit.Label(empty.transform, "EmptyText", "背包空空如也\n去商店买点药水和面包吧", 24, UiSkin.TextDark,
                    40f, 160f, 520f, 110f, TextAnchor.MiddleCenter);
                UiKit.Label(content, "WeaponHint", "武器不占背包格子 —— 到「装备」页管理", 18, UiSkin.TextMuted,
                    0f, 560f, 1260f, 28f, TextAnchor.MiddleLeft);
                return;
            }

            for (int i = 0; i < ids.Count && i < 6; i++)
            {
                string id = ids[i];
                int count = GameSession.CountItem(id);
                int col = i % 2;
                int row = i / 2;
                BuildItemCard(content, id, Mathf.Max(1, count), col * 620f, 56f + row * 214f);
            }

            int total = 0;
            for (int i = 0; i < ids.Count; i++) total += Mathf.Max(1, GameSession.CountItem(ids[i]));
            UiKit.Label(content, "Footer", "共 " + total + " 件物品　·　武器不占背包格子 —— 到「装备」页管理", 18,
                UiSkin.TextMuted, 0f, 656f, 1260f, 28f, TextAnchor.MiddleLeft);
        }

        private void BuildItemCard(Transform parent, string itemId, int count, float x, float y)
        {
            var def = ShopCatalog.Get(itemId);
            string displayName = def != null ? def.displayName : itemId;
            string description = def != null ? def.description : "（未登记的物品）";
            int price = def != null ? def.price : 0;

            var card = UiKit.Panel(parent, "Item_" + itemId, UiSkin.Card, Color.white, x, y, 604f, 200f);
            UiKit.Corners(card.transform, 6f, 24f);
            UiKit.Icon(card.transform, "Icon", UiItemIcons.Load(itemId), 18f, 40f, 120f, 120f);

            var name = UiKit.Label(card.transform, "Name", displayName, 26, UiSkin.TextDark,
                158f, 20f, 360f, 34f, TextAnchor.MiddleLeft);
            name.fontStyle = FontStyle.Bold;

            UiKit.Label(card.transform, "Desc", description, 18, UiSkin.Ink.Alpha(0.8f),
                158f, 62f, 420f, 82f, TextAnchor.UpperLeft);

            var badge = UiKit.Panel(card.transform, "Count", UiSkin.ButtonGold, Color.white, 502f, 16f, 86f, 34f);
            var badgeText = UiKit.Label(badge.transform, "Text", "×" + count, 20, UiSkin.TextDark,
                0f, 0f, 86f, 34f, TextAnchor.MiddleCenter);
            badgeText.fontStyle = FontStyle.Bold;

            UiKit.Label(card.transform, "Category", price > 0 ? "消耗品 · 商店价 " + price + " 金币" : "消耗品",
                16, UiSkin.Ink.Alpha(0.55f), 158f, 154f, 420f, 26f, TextAnchor.MiddleLeft);

            var relay = card.gameObject.AddComponent<ClickRelay>();
            relay.onClick = data => ShowToast(displayName + "：" + (description.Length > 30 ? description.Substring(0, 30) + "…" : description));
            UiKit.AddHoverTint(card, Color.white, new Color(1.04f, 1.02f, 0.95f));
        }

        // =================================================================
        //  角色页（属性 + 已装备）
        // =================================================================

        private void BuildCharacterPage(RectTransform content)
        {
            float cur = health != null ? health.Health : GameSession.Health;
            float max = health != null ? health.MaxHealth : GameSession.MaxHealth;
            if (max <= 0f) max = 1f;
            int owned = CountOwnedWeapons();
            int bagCount = 0;
            var purchased = GameSession.PurchasedItemIds;
            if (purchased != null)
                for (int i = 0; i < purchased.Count; i++) bagCount += Mathf.Max(1, GameSession.CountItem(purchased[i]));

            var left = UiKit.Panel(content, "StatsPanel", UiSkin.Card, Color.white, 0f, 0f, 620f, 700f);
            UiKit.Corners(left.transform, 7f, 30f);
            var lt = UiKit.Title(left.transform, "Title", "属 性", 30, UiSkin.TextDark,
                22f, 10f, 300f, 42f, TextAnchor.MiddleLeft);
            lt.fontStyle = FontStyle.Bold;
            UiKit.Divider(left.transform, "TitleDivider", 22f, 52f, 576f);

            var main = loadout != null ? loadout.MainHand : null;
            var off = loadout != null ? loadout.OffHand : null;
            string[][] rows =
            {
                new[] { "生命上限", Mathf.CeilToInt(max).ToString() },
                new[] { "当前生命", Mathf.CeilToInt(cur) + " / " + Mathf.CeilToInt(max) },
                new[] { "金币", GameSession.Gold.ToString() },
                new[] { "主手武器", main != null ? main.displayName : "空手" },
                new[] { "副手武器", off != null ? off.displayName : "空手" },
                new[] { "主手伤害", main != null ? main.damage.ToString("0.#") : "—" },
                new[] { "副手伤害", off != null ? off.damage.ToString("0.#") : "—" },
                new[] { "主手冷却", main != null ? main.cooldown.ToString("0.##") + "s" : "—" },
                new[] { "副手冷却", off != null ? off.cooldown.ToString("0.##") + "s" : "—" },
                new[] { "已拥有武器", owned + " / 6" },
                new[] { "背包物品", bagCount + " 件" },
            };

            float y = 72f;
            for (int i = 0; i < rows.Length; i++)
            {
                if (i % 2 == 0)
                {
                    var stripe = UiKit.Panel(left.transform, "Stripe" + i, UiSkin.White, new Color(0f, 0f, 0f, 0.045f),
                        22f, y - 2f, 576f, 44f);
                    stripe.raycastTarget = false;
                }
                UiKit.Label(left.transform, "Key" + i, rows[i][0], 20, UiSkin.Ink.Alpha(0.65f),
                    36f, y, 240f, 40f, TextAnchor.MiddleLeft);
                var val = UiKit.Label(left.transform, "Val" + i, rows[i][1], 20, UiSkin.TextDark,
                    300f, y, 280f, 40f, TextAnchor.MiddleRight);
                val.fontStyle = FontStyle.Bold;
                y += 52f;
            }

            var right = UiKit.Panel(content, "EquipPanel", UiSkin.Card, Color.white, 640f, 0f, 620f, 700f);
            UiKit.Corners(right.transform, 7f, 30f);
            var rt = UiKit.Title(right.transform, "Title", "装 备", 30, UiSkin.TextDark,
                22f, 10f, 300f, 42f, TextAnchor.MiddleLeft);
            rt.fontStyle = FontStyle.Bold;
            UiKit.Divider(right.transform, "TitleDivider", 22f, 52f, 576f);

            BuildEquipSlot(right.transform, 22f, 76f, 576f, 132f, "主手 · 左键", main, HandSlot.MainHand);
            BuildEquipSlot(right.transform, 22f, 224f, 576f, 132f, "副手 · 右键", off, HandSlot.OffHand);

            UiKit.Label(right.transform, "Trait",
                "已装备武器的特性：\n" + (main != null ? "· 主手：" + WeaponTraitLine(main) : "· 主手：空手攻击") + "\n" +
                (off != null ? "· 副手：" + WeaponTraitLine(off) : "· 副手：无副手装备"),
                17, UiSkin.Ink.Alpha(0.82f), 22f, 386f, 576f, 180f, TextAnchor.UpperLeft);

            UiKit.Label(right.transform, "Hint", "想换装就按 Tab →「装备」页点卡片", 17, UiSkin.Ink.Alpha(0.55f),
                22f, 600f, 576f, 28f, TextAnchor.MiddleLeft);
        }

        // =================================================================
        //  设置页（沿用旧版 PlayerPrefs 键：mw_res / mw_fullscreen）
        // =================================================================

        private void LoadSavedSettings()
        {
            settingsResolution = Mathf.Clamp(PlayerPrefs.GetInt("mw_res", 1), 0, ResolutionLabels.Length - 1);
            settingsFullscreen = PlayerPrefs.GetInt("mw_fullscreen", Screen.fullScreen ? 1 : 0) == 1;
        }

        private void BuildSettingsPage(RectTransform content)
        {
            var panel = UiKit.Panel(content, "SettingsPanel", UiSkin.Card, Color.white, 200f, 18f, 860f, 664f);
            UiKit.Corners(panel.transform, 9f, 32f);

            var title = UiKit.Title(panel.transform, "Title", "设 置", 30, UiSkin.TextDark,
                26f, 12f, 300f, 44f, TextAnchor.MiddleLeft);
            title.fontStyle = FontStyle.Bold;
            UiKit.Divider(panel.transform, "TitleDivider", 26f, 56f, 808f);

            UiKit.Label(panel.transform, "ResLabel", "分辨率", 20, UiSkin.Ink.Alpha(0.72f),
                26f, 78f, 200f, 28f, TextAnchor.MiddleLeft);
            for (int i = 0; i < ResolutionLabels.Length; i++)
            {
                int index = i;
                UiKit.TextButton(panel.transform, "Res" + i, ResolutionLabels[i], 26f + i * 194f, 112f, 180f, 56f,
                    () => ApplyResolution(index), index == settingsResolution, 20);
            }

            UiKit.Label(panel.transform, "FsLabel", "显示模式", 20, UiSkin.Ink.Alpha(0.72f),
                26f, 190f, 200f, 28f, TextAnchor.MiddleLeft);
            UiKit.TextButton(panel.transform, "Windowed", "窗口", 26f, 224f, 180f, 56f,
                () => ApplyFullscreen(false), !settingsFullscreen, 20);
            UiKit.TextButton(panel.transform, "Fullscreen", "全屏", 220f, 224f, 180f, 56f,
                () => ApplyFullscreen(true), settingsFullscreen, 20);

            UiKit.Divider(panel.transform, "NoteDivider", 26f, 304f, 808f);

            UiKit.Label(panel.transform, "Note",
                "画质提示：本工程使用 URP，抗锯齿由 URP Asset / Volume 控制，界面不提供；\n" +
                "窗口失焦时游戏逻辑不推进 —— 这是编辑器行为，不是卡死。\n" +
                "数值展示全部只读：这里只会改分辨率与窗口模式，不会改任何玩法数值。",
                18, UiSkin.Ink.Alpha(0.82f), 26f, 324f, 808f, 120f, TextAnchor.UpperLeft);

            settingsStatus = UiKit.Label(panel.transform, "Status", BuildSettingsStatusText(), 19, UiSkin.TextDark,
                26f, 470f, 808f, 30f, TextAnchor.MiddleLeft);
            settingsStatus.fontStyle = FontStyle.Bold;

            UiKit.Label(panel.transform, "Hint", "Esc 关闭菜单　·　Tab 返回游戏", 18, UiSkin.Ink.Alpha(0.6f),
                26f, 592f, 808f, 28f, TextAnchor.MiddleLeft);
        }

        private string BuildSettingsStatusText()
        {
            return "当前：" + ResolutionLabels[settingsResolution] + "　·　" + (settingsFullscreen ? "全屏" : "窗口");
        }

        private void RefreshSettingsStatus()
        {
            if (settingsStatus != null) settingsStatus.text = BuildSettingsStatusText();
        }

        private void ApplyResolution(int index)
        {
            settingsResolution = Mathf.Clamp(index, 0, ResolutionLabels.Length - 1);
            int w = ResolutionWidths[settingsResolution];
            int h = ResolutionHeights[settingsResolution];
            PlayerPrefs.SetInt("mw_res", settingsResolution);
            PlayerPrefs.SetInt("mw_fullscreen", settingsFullscreen ? 1 : 0);
            PlayerPrefs.Save();
            Screen.SetResolution(w, h, settingsFullscreen);
            RefreshSettingsStatus();
            ShowBranch(settingsBranchIndex);
        }

        private void ApplyFullscreen(bool fullscreen)
        {
            settingsFullscreen = fullscreen;
            PlayerPrefs.SetInt("mw_fullscreen", fullscreen ? 1 : 0);
            PlayerPrefs.SetInt("mw_res", settingsResolution);
            PlayerPrefs.Save();
            Screen.fullScreen = fullscreen;
            Screen.SetResolution(ResolutionWidths[settingsResolution], ResolutionHeights[settingsResolution], fullscreen);
            RefreshSettingsStatus();
            ShowBranch(settingsBranchIndex);
        }
    }
}
