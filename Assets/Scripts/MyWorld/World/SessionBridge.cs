using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 把"场景里的玩家组件"和"跨场景的 GameSession"接起来：
    ///   · 进图时恢复血量/装备；   · 血量变化写回会话；
    ///   · 金币/任务追踪转发给 HUD；   · 黑场淡入。
    /// 训练场（烘焙场景）和新地图（运行时生成）都挂这一个组件，行为一致。
    /// </summary>
    [DisallowMultipleComponent]
    public class SessionBridge : MonoBehaviour
    {
        [SerializeField] private PlayerHealth health;
        [SerializeField] private WeaponLoadout loadout;
        [SerializeField] private GameUi ui;

        private float equipPollTimer;
        private WeaponKind lastMain, lastOff;

        public void Configure(PlayerHealth h, WeaponLoadout l, GameUi u)
        {
            health = h;
            loadout = l;
            ui = u;
        }

        private void Start()
        {
            GameSession.EnsureInitialized();

            if (health != null)
            {
                // 跨图保留血量：上一张图剩多少就带多少过来（默认 100/100）
                float cur = GameSession.Health;
                float max = GameSession.MaxHealth;
                if (cur > 0f && max > 0f) health.ImportHealth(cur, max);
                GameSession.SetHealth(health.Health, health.MaxHealth);
                health.HealthChanged += HandleHealth;
            }

            GameSession.GoldChanged += HandleGold;
            QuestSystem.Changed += HandleQuests;

            ApplySavedEquipment();
            RefreshHud();

            StartCoroutine(FadeInNextFrame());
        }

        private void OnDestroy()
        {
            if (health != null) health.HealthChanged -= HandleHealth;
            GameSession.GoldChanged -= HandleGold;
            QuestSystem.Changed -= HandleQuests;
        }

        private void Update()
        {
            // 装备可能被 UI 改动；轮询比给 WeaponLoadout 加事件侵入更小（0.4s 一次开销可忽略）
            equipPollTimer -= Time.deltaTime;
            if (equipPollTimer > 0f) return;
            equipPollTimer = 0.4f;
            PersistEquipment();
        }

        private void HandleHealth(float current, float max)
        {
            GameSession.SetHealth(current, max);
        }

        private void HandleGold(int gold)
        {
            if (GameUi.Instance != null) GameUi.Instance.SetGold(gold);
        }

        private void HandleQuests()
        {
            if (GameUi.Instance != null) GameUi.Instance.SetQuestTracker(QuestSystem.TrackerLine());
        }

        private void RefreshHud()
        {
            if (GameUi.Instance == null) return;
            GameUi.Instance.SetGold(GameSession.Gold);
            GameUi.Instance.SetQuestTracker(QuestSystem.TrackerLine());
        }

        private void ApplySavedEquipment()
        {
            if (loadout == null || !GameSession.HasEquipment) return;

            WeaponDefinition main = null;
            WeaponDefinition off = null;
            var owned = loadout.Owned;
            for (int i = 0; i < owned.Count; i++)
            {
                if (owned[i] == null) continue;
                if (owned[i].kind == GameSession.EquippedMain) main = owned[i];
                if (owned[i].kind == GameSession.EquippedOff) off = owned[i];
            }
            if (main != null) loadout.SetEquipped(main, off);
        }

        private void PersistEquipment()
        {
            if (loadout == null) return;
            var main = loadout.MainHand;
            var off = loadout.OffHand;
            if (main == null) return;
            WeaponKind m = main.kind;
            WeaponKind o = off != null ? off.kind : WeaponKind.Unarmed;
            if (m == lastMain && o == lastOff) return;
            lastMain = m;
            lastOff = o;
            GameSession.SetEquipment(m, o);
        }

        private System.Collections.IEnumerator FadeInNextFrame()
        {
            // 等一帧，让 GameUi 的 Start 把黑幕建出来
            yield return null;
            if (GameUi.Instance != null) GameUi.Instance.PlayFadeIn(0.5f);
            RefreshHud();
        }
    }
}
