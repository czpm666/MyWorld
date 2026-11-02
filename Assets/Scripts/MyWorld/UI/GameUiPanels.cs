using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using MyWorld.UI;

namespace MyWorld
{
    /// <summary>
    /// GameUi 的**对外契约面板层**（对话 / 商店 / 任务板 / 交互提示 / 任务追踪 / 金币 / 黑场）。
    ///
    /// 契约（OVERHAUL-PLAN §3，签名不可改）：
    ///   Instance(在 GameUi.cs) / ShowDialogue / ShowShop / ShowQuestBoard /
    ///   SetInteractPrompt / SetQuestTracker / SetGold / PlayFadeOut / PlayFadeIn / ShowToast(在 GameUi.cs)
    ///
    /// 视觉全部复用 UI/UiSkin + UI/UiKit 的程序化皮肤；HUD 元素（金币/任务追踪/交互提示/黑场）
    /// 由 GameUi.cs 的 BuildHud/BuildFade 建好，本文件只负责**填内容**，不再另建第二层 HUD。
    ///
    /// 输入：只读 MyWorldInput 已公开的 InteractPressed / SettingsPressed（不新开 InputAction）。
    ///   E → 推进对话 / 关闭面板；Esc → 关闭面板。
    /// </summary>
    public partial class GameUi
    {
        // ---------------- 面板层状态 ----------------

        private bool overlayOpen;
        private bool dialogueOpen;
        private DialogueView dialogueView;
        private int dialogueLine;

        private IShopHost shopHost;

        private IQuestBoardHost boardHost;

        private RectTransform panelWindow;
        private Text panelTitleText;
        private Text panelGoldText;
        private RectTransform panelContent;

        private Image dimImage;
        private Text speakerText;
        private Text dialogueBody;
        private Text dialogueHint;

        private Coroutine fadeRoutine;

        private const float WindowW = 1040f;
        private const float WindowH = 660f;

        // ---------------- 面板层骨架 ----------------

        /// <summary>在菜单之上、Toast/黑场之下建对话/商店/任务板层。</summary>
        private void BuildOverlayLayer()
        {
            overlayRoot = UiKit.Stretch(canvas.transform, "Overlay");

            dimImage = overlayRoot.gameObject.AddComponent<Image>();
            dimImage.sprite = UiSkin.White;
            dimImage.color = new Color(0.02f, 0.015f, 0.01f, 0f);
            // 只在面板真的打开时才挡射线（见 GameUi.RefreshOpenState 的注释）：
            // 这里是整屏遮罩，alpha=0 时仍然会被 uGUI 射线命中，会吞掉下面菜单的所有指针事件。
            dimImage.raycastTarget = false;

            panelWindow = UiKit.Center(overlayRoot, "PanelWindow", 0f, 0f, WindowW, WindowH);
            var winBg = panelWindow.gameObject.AddComponent<Image>();
            winBg.sprite = UiSkin.Window;
            winBg.type = Image.Type.Sliced;
            winBg.raycastTarget = true;
            UiKit.Corners(panelWindow, 14f, 52f);

            panelTitleText = UiKit.Title(panelWindow, "Title", "", 34, UiSkin.GoldLight,
                30f, 10f, 660f, 50f, TextAnchor.MiddleLeft).WithShadow(0.85f);
            panelTitleText.fontStyle = FontStyle.Bold;

            panelGoldText = UiKit.Label(panelWindow, "Gold", "", 25, UiSkin.GoldLight,
                700f, 16f, 250f, 38f, TextAnchor.MiddleRight);
            panelGoldText.fontStyle = FontStyle.Bold;

            UiKit.TextButton(panelWindow, "CloseButton", "×", 966f, 14f, 46f, 46f, CloseOverlay, false, 28);
            UiKit.Divider(panelWindow, "TitleDivider", 30f, 64f, 980f);

            panelContent = UiKit.Place(panelWindow, "Content", 30f, 84f, 980f, 552f);

            UiKit.Label(panelWindow, "Hint", "E / 回车 推进　·　Esc 关闭", 17, UiSkin.TextMuted,
                34f, 624f, 640f, 26f, TextAnchor.MiddleLeft);

            panelWindow.gameObject.SetActive(false);

            BuildDialoguePanel();
        }

        private void BuildDialoguePanel()
        {
            var win = UiKit.Center(overlayRoot, "DialogueWindow", 0f, -250f, 1180f, 300f);
            var bg = win.gameObject.AddComponent<Image>();
            bg.sprite = UiSkin.Window;
            bg.type = Image.Type.Sliced;
            bg.raycastTarget = true;
            UiKit.Corners(win, 14f, 52f);

            speakerText = UiKit.Title(win, "Speaker", "", 30, UiSkin.GoldLight,
                44f, 14f, 700f, 42f, TextAnchor.MiddleLeft).WithShadow(0.85f);
            speakerText.fontStyle = FontStyle.Bold;

            dialogueBody = UiKit.Label(win, "Body", "", 27, UiSkin.TextDark,
                44f, 70f, 1092f, 150f, TextAnchor.UpperLeft);
            dialogueBody.lineSpacing = 1.15f;

            dialogueHint = UiKit.Label(win, "Next", "▼", 26, UiSkin.Gold,
                1030f, 232f, 120f, 40f, TextAnchor.MiddleRight).WithShadow(0.55f);

            win.gameObject.SetActive(false);
            dialogueWindow = win;
        }

        private RectTransform dialogueWindow;

        // ---------------- 契约：对话 ----------------

        public void ShowDialogue(DialogueView view)
        {
            if (view == null) return;
            dialogueView = view;
            dialogueLine = 0;
            dialogueOpen = true;
            overlayOpen = true;

            SetMenuOpen(false);
            if (dialogueWindow != null) dialogueWindow.gameObject.SetActive(true);
            PaintDialogueLine();
            RefreshOpenState();
        }

        private void PaintDialogueLine()
        {
            if (dialogueView == null) return;
            string text = "";
            if (dialogueView.lines != null && dialogueView.lines.Length > 0)
            {
                int i = Mathf.Clamp(dialogueLine, 0, dialogueView.lines.Length - 1);
                text = dialogueView.lines[i] ?? "";
            }
            if (speakerText != null) speakerText.text = dialogueView.speaker ?? "";
            if (dialogueBody != null) dialogueBody.text = text;
            if (dialogueHint != null)
            {
                bool last = dialogueView.lines == null || dialogueLine >= dialogueView.lines.Length - 1;
                dialogueHint.text = last ? "▼ 结束" : "▼ 继续";
            }
        }

        private void AdvanceDialogue()
        {
            if (!dialogueOpen) return;
            dialogueLine++;
            if (dialogueView != null && dialogueView.lines != null && dialogueLine < dialogueView.lines.Length)
            {
                PaintDialogueLine();
                return;
            }
            CloseDialogue();
        }

        private void CloseDialogue()
        {
            var view = dialogueView;
            dialogueOpen = false;
            dialogueView = null;
            dialogueLine = 0;
            overlayOpen = false;
            if (dialogueWindow != null) dialogueWindow.gameObject.SetActive(false);
            RefreshOpenState();

            // 读完（或 Esc 跳过）都回调一次：任务计数/奖励不能被 UI 卡住
            if (view != null) view.onComplete?.Invoke();
        }

        // ---------------- 契约：商店 ----------------

        public void ShowShop(IShopHost host)
        {
            if (host == null) return;
            shopHost = host;
            overlayOpen = true;

            SetMenuOpen(false);
            if (panelWindow != null) panelWindow.gameObject.SetActive(true);
            PaintShop();
            RefreshOpenState();
        }

        private void PaintShop()
        {
            if (panelTitleText != null) panelTitleText.text = shopHost != null ? shopHost.View.title : "商店";
            if (panelGoldText != null) panelGoldText.text = "金币  " + GameSession.Gold;
            if (panelContent == null) return;

            UiKit.ClearChildren(panelContent);

            string[] ids = shopHost != null && shopHost.View != null ? shopHost.View.itemIds : null;
            if (ids == null || ids.Length == 0)
            {
                UiKit.Label(panelContent, "Empty", "（今天没有货）", 24, UiSkin.TextMuted,
                    20f, 20f, 600f, 40f, TextAnchor.MiddleLeft);
                return;
            }

            for (int i = 0; i < ids.Length; i++)
            {
                var def = ShopCatalog.Get(ids[i]);
                if (def == null) continue;

                float y = i * 96f;
                var row = UiKit.Panel(panelContent, "Row" + i, UiSkin.Card, Color.white, 0f, y, 970f, 86f);
                UiKit.Corners(row.transform, 6f, 20f);

                UiKit.Icon(row.transform, "Coin", UiSkin.Coin, 16f, 16f, 30f, 30f);

                UiKit.Label(row.transform, "Name", def.displayName, 24, UiSkin.TextDark,
                    58f, 8f, 470f, 34f, TextAnchor.MiddleLeft).fontStyle = FontStyle.Bold;
                UiKit.Label(row.transform, "Desc", def.description, 18, UiSkin.InkSoft,
                    58f, 44f, 560f, 32f, TextAnchor.MiddleLeft);

                var price = UiKit.Label(row.transform, "Price", def.price + " 金币", 23, UiSkin.GoldDark,
                    628f, 8f, 150f, 34f, TextAnchor.MiddleRight);
                price.fontStyle = FontStyle.Bold;

                string id = def.id;
                bool affordable = GameSession.Gold >= def.price;
                var btn = UiKit.TextButton(row.transform, "Buy", affordable ? "购买" : "买不起",
                    796f, 18f, 150f, 50f, () => HandleBuy(id), true, 22);
                if (!affordable) btn.interactable = false;
            }
        }

        private void HandleBuy(string itemId)
        {
            if (shopHost == null) return;
            shopHost.Buy(itemId);   // 成败都由 host 自己 Toast
            PaintShop();            // 金币/可买状态即时刷新
        }

        // ---------------- 契约：任务板 ----------------

        public void ShowQuestBoard(IQuestBoardHost host)
        {
            if (host == null) return;
            boardHost = host;
            overlayOpen = true;

            SetMenuOpen(false);
            if (panelWindow != null) panelWindow.gameObject.SetActive(true);
            PaintBoard();
            RefreshOpenState();
        }

        private void PaintBoard()
        {
            var view = boardHost != null ? boardHost.View : null;
            if (panelTitleText != null) panelTitleText.text = view != null ? view.title : "委托板";
            if (panelGoldText != null) panelGoldText.text = "金币  " + GameSession.Gold;
            if (panelContent == null) return;

            UiKit.ClearChildren(panelContent);

            if (view == null || view.cards == null || view.cards.Count == 0)
            {
                UiKit.Label(panelContent, "Empty", "（暂时没有可接的委托）", 24, UiSkin.TextMuted,
                    20f, 20f, 600f, 40f, TextAnchor.MiddleLeft);
                return;
            }

            for (int i = 0; i < view.cards.Count; i++)
            {
                var card = view.cards[i];
                int col = i % 2;
                int row = i / 2;
                float x = col * 496f;
                float y = row * 214f;

                var panel = UiKit.Panel(panelContent, "Card" + i, UiSkin.Card, Color.white, x, y, 474f, 198f);
                UiKit.Corners(panel.transform, 6f, 20f);

                UiKit.Label(panel.transform, "Title", string.IsNullOrEmpty(card.title) ? card.id : card.title,
                    23, UiSkin.TextDark, 18f, 8f, 320f, 32f, TextAnchor.MiddleLeft).fontStyle = FontStyle.Bold;

                var stateText = UiKit.Label(panel.transform, "State", StateLabel(card.state), 17,
                    StateColor(card.state), 348f, 10f, 108f, 28f, TextAnchor.MiddleRight);
                stateText.fontStyle = FontStyle.Bold;

                UiKit.Label(panel.transform, "Summary", card.summary ?? "", 17, UiSkin.InkSoft,
                    18f, 42f, 438f, 48f, TextAnchor.UpperLeft);

                UiKit.Label(panel.transform, "Objective", JoinObjectives(card.objectiveLines), 16, UiSkin.Ink.Alpha(0.85f),
                    18f, 96f, 438f, 56f, TextAnchor.UpperLeft);

                UiKit.Label(panel.transform, "Reward", "报酬  " + card.rewardGold + " 金币", 18, UiSkin.GoldDark,
                    18f, 160f, 220f, 28f, TextAnchor.MiddleLeft).fontStyle = FontStyle.Bold;

                string id = card.id;
                if (card.canAccept)
                {
                    UiKit.TextButton(panel.transform, "Accept", "接受", 324f, 152f, 132f, 38f, () => HandleAccept(id), true, 20);
                }
                else if (card.canClaim)
                {
                    UiKit.TextButton(panel.transform, "Claim", "交任务", 324f, 152f, 132f, 38f, () => HandleClaim(id), true, 20);
                }
            }
        }

        private static string JoinObjectives(string[] lines)
        {
            if (lines == null || lines.Length == 0) return "";
            var sb = new System.Text.StringBuilder();
            for (int i = 0; i < lines.Length; i++)
            {
                if (i > 0) sb.Append('\n');
                sb.Append("· ").Append(lines[i]);
            }
            return sb.ToString();
        }

        private static string StateLabel(string state)
        {
            switch (state)
            {
                case "Available": return "可接取";
                case "Active": return "进行中";
                case "Ready": return "可交付";
                case "Done": return "已完成";
                default: return string.IsNullOrEmpty(state) ? "" : state;
            }
        }

        private static Color StateColor(string state)
        {
            switch (state)
            {
                case "Ready": return UiSkin.GoldDark;
                case "Active": return UiSkin.Ink.Alpha(0.75f);
                case "Done": return UiSkin.Green;
                default: return UiSkin.Ink.Alpha(0.65f);
            }
        }

        private void HandleAccept(string questId)
        {
            if (boardHost == null) return;
            boardHost.Accept(questId);   // 成败由 host Toast
            PaintBoard();
        }

        private void HandleClaim(string questId)
        {
            if (boardHost == null) return;
            boardHost.Claim(questId);
            PaintBoard();
        }

        // ---------------- 面板输入 / 关闭 ----------------

        /// <summary>任一覆盖层打开时由 GameUi.Update 调用。</summary>
        private void UpdateOverlays()
        {
            if (input == null) return;

            bool confirm = input.InteractPressed;
            bool cancel = input.SettingsPressed;

            if (dialogueOpen)
            {
                if (confirm || cancel) AdvanceDialogue();
                return;
            }
            if (confirm || cancel) CloseOverlay();
        }

        private void CloseOverlay()
        {
            if (dialogueOpen)
            {
                CloseDialogue();
                return;
            }

            shopHost = null;
            boardHost = null;
            overlayOpen = false;

            if (panelWindow != null) panelWindow.gameObject.SetActive(false);
            if (panelContent != null) UiKit.ClearChildren(panelContent);
            RefreshOpenState();
        }

        // ---------------- 契约：HUD 单向写入 ----------------

        public void SetInteractPrompt(string text)
        {
            if (promptRoot == null) return;
            bool show = !string.IsNullOrEmpty(text);
            if (promptRoot.gameObject.activeSelf != show) promptRoot.gameObject.SetActive(show);
            if (show && promptText != null) promptText.text = text;
        }

        public void SetQuestTracker(string line)
        {
            if (questPanel == null) return;
            bool show = !string.IsNullOrEmpty(line);
            if (questPanel.gameObject.activeSelf != show) questPanel.gameObject.SetActive(show);
            if (questBody != null && show) questBody.text = line;
        }

        public void SetGold(int gold)
        {
            if (hudGoldText != null) hudGoldText.text = gold.ToString();
            if (menuGoldText != null) menuGoldText.text = gold.ToString();
            if (panelGoldText != null && panelWindow != null && panelWindow.gameObject.activeSelf)
                panelGoldText.text = "金币  " + gold;
        }

        // ---------------- 契约：黑场 ----------------

        public void PlayFadeOut(float seconds, System.Action onBlack)
        {
            StopFadeRoutine();
            fadeRoutine = StartCoroutine(FadeRoutine(1f, seconds, onBlack));
        }

        public void PlayFadeIn(float seconds)
        {
            StopFadeRoutine();
            fadeRoutine = StartCoroutine(FadeRoutine(0f, seconds, null));
        }

        private void StopFadeRoutine()
        {
            if (fadeRoutine != null)
            {
                StopCoroutine(fadeRoutine);
                fadeRoutine = null;
            }
        }

        /// <summary>0→1 变黑（或 1→0 变亮），到点后回调。</summary>
        private IEnumerator FadeRoutine(float target, float seconds, System.Action done)
        {
            if (seconds < 0.01f) seconds = 0.01f;
            float from = fadeImage != null ? fadeImage.color.a : 0f;
            float t = 0f;
            while (t < seconds)
            {
                t += Time.unscaledDeltaTime;
                float a = Mathf.Lerp(from, target, Mathf.Clamp01(t / seconds));
                if (fadeImage != null) fadeImage.color = new Color(0f, 0f, 0f, a);
                yield return null;
            }
            if (fadeImage != null) fadeImage.color = new Color(0f, 0f, 0f, target);
            fadeRoutine = null;
            done?.Invoke();
        }
    }
}
