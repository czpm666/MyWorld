using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MyWorld
{
    /// <summary>
    /// **事件接线员**：把"游戏里发生了什么"转给 VfxCombat / SfxLibrary / VfxAmbient。
    ///
    /// 订阅的都是**静态事件**（Lead 已在 Enemy/GameSession/PlayerHealth 里提供），不修改这些文件：
    ///   * Enemy.AnyDamaged / Enemy.AnyDefeated  → 敌人受击 / 死亡特效
    ///   * PlayerHealth.HealthChanged           → 玩家受击 / 治疗特效（含复活时的治疗）
    ///   * GameSession.GoldChanged              → 金币拾取特效 + 金币音
    ///   * GameSession.CounterChanged           → 采集类任务计数 → 拾取特效
    ///   * GameSession.ItemPurchased            → 拾取/购买音
    ///   * GameSession.TransitionStarted        → 传送门特效
    ///   * SceneManager.sceneLoaded             → 重新扫描环境粒子 / 玩家
    ///
    /// 另外做两件"没有人做"的小事：脚步音（按位移速度节流）、给抓钩挂可视化装饰（VfxGrappleDecorator）。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class VfxDirector : MonoBehaviour
    {
        sealed class PlayerWatch
        {
            public PlayerHealth Health;
            public System.Action<float, float> Handler;
            public float LastHealth;
        }

        readonly List<PlayerWatch> players = new List<PlayerWatch>(2);

        float playerScanTimer;
        int lastGold;
        bool bound;

        // 脚步
        Transform footPlayer;
        CharacterController footCc;
        Vector3 lastFootPos;
        float footTimer;
        int footFlip;

        void OnEnable()
        {
            Bind();
        }

        void OnDisable()
        {
            Unbind();
        }

        void OnDestroy()
        {
            // static 事件必须显式退订，避免域重载/场景卸载后留下悬空委托
            Unbind();
        }

        void Start()
        {
            SfxLibrary.Warmup();
            lastGold = GameSession.Gold;
            FindPlayers();
            VfxAmbient.ScanScene();
            StartCoroutine(RescanRoutine());
        }

        IEnumerator RescanRoutine()
        {
            yield return new WaitForSecondsRealtime(0.5f);
            FindPlayers();
            VfxAmbient.ScanScene();
            yield return new WaitForSecondsRealtime(1.5f);
            FindPlayers();
            VfxAmbient.ScanScene();
        }

        // ---------------- 事件绑定 ----------------

        void Bind()
        {
            if (bound) return;
            bound = true;

            Enemy.AnyDamaged += OnEnemyDamaged;
            Enemy.AnyDefeated += OnEnemyDefeated;
            GameSession.GoldChanged += OnGoldChanged;
            GameSession.CounterChanged += OnCounterChanged;
            GameSession.ItemPurchased += OnItemPurchased;
            GameSession.TransitionStarted += OnTransitionStarted;
            SceneManager.sceneLoaded += OnSceneLoaded;
        }

        void Unbind()
        {
            if (!bound) return;
            bound = false;

            Enemy.AnyDamaged -= OnEnemyDamaged;
            Enemy.AnyDefeated -= OnEnemyDefeated;
            GameSession.GoldChanged -= OnGoldChanged;
            GameSession.CounterChanged -= OnCounterChanged;
            GameSession.ItemPurchased -= OnItemPurchased;
            GameSession.TransitionStarted -= OnTransitionStarted;
            SceneManager.sceneLoaded -= OnSceneLoaded;

            ClearPlayers();
        }

        // ---------------- 敌人 ----------------

        void OnEnemyDamaged(Enemy enemy, Vector3 point, Vector3 normal)
        {
            if (enemy == null) return;
            // 档位从敌人身上读：`AnyDamaged` 的签名里没有伤害值，而扩签名会波及每一个订阅方。
            // `Enemy.LastHitGrade` 是这次掉血时算好的同一档（同一帧同一伤害只掷一次骰子），
            // 所以血花的大小和闪色/僵直/命中音**一定是同一级**，不会出现"闪红却小声"。
            //
            // 法线修正：近战调用方历史上传的是 `Vector3.up`（那是"受击方向"的老约定，
            // 不是真实表面法线）。血花沿 up 喷就是"从头顶冒血"，很假。这里改成
            // **从伤口朝外辐射**（敌人中心 → 命中点的水平方向），正面砍/背砍的血花方向
            // 自然相反。`point` 本身仍然是真实碰撞点，没有动。
            Vector3 spray = normal;
            Vector3 radial = point - enemy.transform.position;
            radial.y = 0f;
            if (radial.sqrMagnitude > 1e-4f) spray = radial.normalized;
            VfxCombat.EnemyHit(point, spray, enemy.LastHitGrade);
        }

        void OnEnemyDefeated(Enemy enemy)
        {
            if (enemy == null) return;
            VfxCombat.EnemyDeath(enemy.transform.position);
        }

        // ---------------- 金币 / 拾取 ----------------

        void OnGoldChanged(int gold)
        {
            bool gained = gold > lastGold;
            lastGold = gold;
            if (!gained) return;

            Transform p = SfxLibrary.LocalPlayer();
            if (p != null) VfxCombat.PickupGold(p.position);
            else SfxLibrary.Play2D("coin", 0.4f);
        }

        void OnCounterChanged(string key, int value)
        {
            if (string.IsNullOrEmpty(key)) return;
            bool collect = key.StartsWith("collect", System.StringComparison.OrdinalIgnoreCase)
                || key.StartsWith("gather", System.StringComparison.OrdinalIgnoreCase)
                || key.StartsWith("pickup", System.StringComparison.OrdinalIgnoreCase)
                || key.StartsWith("harvest", System.StringComparison.OrdinalIgnoreCase);
            if (!collect) return;

            Transform p = SfxLibrary.LocalPlayer();
            if (p != null) VfxCombat.PickupItem(p.position);
        }

        void OnItemPurchased(string itemId)
        {
            SfxLibrary.Play2D("ui_confirm", 0.4f);
        }

        void OnTransitionStarted(MapId target)
        {
            Transform p = SfxLibrary.LocalPlayer();
            if (p != null) VfxCombat.PortalAt(p.position);
            else VfxCombat.PortalAt(Vector3.zero);
        }

        // ---------------- 玩家 ----------------

        void ClearPlayers()
        {
            for (int i = 0; i < players.Count; i++)
            {
                PlayerWatch w = players[i];
                if (w == null || w.Health == null) continue;
                if (w.Handler != null) w.Health.HealthChanged -= w.Handler;
            }
            players.Clear();
        }

        void FindPlayers()
        {
            PlayerHealth[] found = Object.FindObjectsByType<PlayerHealth>(FindObjectsSortMode.None);

            // 清掉已经失效的
            for (int i = players.Count - 1; i >= 0; i--)
            {
                PlayerWatch w = players[i];
                if (w != null && w.Health != null) continue;
                if (w != null && w.Handler != null) { /* 目标已销毁，事件自然失效 */ }
                players.RemoveAt(i);
            }

            if (found == null) return;
            for (int i = 0; i < found.Length; i++)
            {
                PlayerHealth ph = found[i];
                if (ph == null) continue;
                bool exists = false;
                for (int j = 0; j < players.Count; j++)
                {
                    if (players[j] != null && players[j].Health == ph) { exists = true; break; }
                }
                if (exists) continue;

                var watch = new PlayerWatch { Health = ph, LastHealth = ph.Health };
                watch.Handler = (cur, max) => OnPlayerHealthChanged(watch, cur, max);
                ph.HealthChanged += watch.Handler;
                players.Add(watch);
            }

            // 抓钩装饰（新地图/新玩家身上的抓钩）
            GrappleWeapon[] grapples = Object.FindObjectsByType<GrappleWeapon>(FindObjectsSortMode.None);
            if (grapples != null)
            {
                for (int i = 0; i < grapples.Length; i++)
                {
                    if (grapples[i] != null) VfxCombat.DecorateGrapple(grapples[i].gameObject);
                }
            }
        }

        void OnPlayerHealthChanged(PlayerWatch watch, float current, float max)
        {
            if (watch == null || watch.Health == null) return;

            float delta = current - watch.LastHealth;
            watch.LastHealth = current;
            if (Mathf.Abs(delta) < 0.01f) return;

            Vector3 position = watch.Health.transform.position;
            // 扣血的**数值**就是这一跳的伤害（`delta` 是负的）→ 直接拿去分级，
            // 于是"玩家挨了一记重击"也会有顿帧 + 震屏 + 红色伤害数字，
            // 而"流血的每 0.5 秒一跳"（2 点）会被判成轻击、不顿帧（见 VfxCombat.PlayerHurt）。
            if (delta < 0f) VfxCombat.PlayerHurt(position, -delta);
            else VfxCombat.PlayerHeal(position, delta);
        }

        // ---------------- 每帧小逻辑 ----------------

        void Update()
        {
            playerScanTimer -= Time.unscaledDeltaTime;
            if (playerScanTimer <= 0f)
            {
                playerScanTimer = 2f;
                if (players.Count == 0) FindPlayers();
            }

            UpdateFootsteps();
        }

        void UpdateFootsteps()
        {
            Transform player = SfxLibrary.LocalPlayer();
            if (player == null)
            {
                footPlayer = null;
                return;
            }

            if (footPlayer != player)
            {
                footPlayer = player;
                // 用 GetComponentInParent：LocalPlayer() 有可能返回挂视觉的**子节点**，
                // 而 CharacterController 和逻辑都在根节点上（见 MapBootstrap 的玩家搭建）。
                // 在子节点上 GetComponent 会拿到 null → 空中判断静默失效，等于没修。
                footCc = player.GetComponentInParent<CharacterController>();
                lastFootPos = player.position;
                footTimer = 0f;
                return;
            }

            // ⚠️ 空中不踩脚步声。
            // 旧逻辑只看**水平**速度（下面 `delta.y = 0f`），只要空中有水平位移，
            // 脚步计时器就会继续走 → 跳跃/坠落时在半空里"踩"出声。
            // 用户报的"起跳响"就是这个：按空格那一下通常伴随一次水平位移，
            // 计时器恰好在同一帧到期，听起来像起跳自带音效（其实工程里根本没有跳跃音）。
            if (footCc != null && !footCc.isGrounded)
            {
                lastFootPos = player.position;   // 记住落点，落地那一帧不要按空中位移补一脚
                return;
            }

            Vector3 delta = player.position - lastFootPos;
            lastFootPos = player.position;
            delta.y = 0f;

            float dt = Mathf.Max(0.0001f, Time.unscaledDeltaTime);
            float speed = delta.magnitude / dt;

            footTimer -= dt;
            if (speed < 1.3f || footTimer > 0f) return;

            bool running = speed > 4.5f;
            footTimer = running ? 0.28f : 0.40f;
            footFlip++;

            string clip = IsGrassScene() ? "footstep_grass" : "footstep_stone";
            float volume = running ? 0.32f : 0.22f;
            SfxLibrary.PlayOnPlayer(clip, volume, Random.Range(0.92f, 1.06f));

            // 跑步时脚下小尘
            if (running && VfxHub.Instance != null)
            {
                VfxHub hub = VfxHub.Instance;
                hub.Burst(hub.Dust, player.position + Vector3.up * 0.06f, Vector3.up, 2,
                    0.3f, 1.0f, 70f, new Color(0.8f, 0.75f, 0.65f, 0.35f),
                    0.08f, 0.16f, 0.20f, 0.35f, 0.2f);
            }
        }

        static bool IsGrassScene()
        {
            string sceneName = SceneManager.GetActiveScene().name;
            if (string.IsNullOrEmpty(sceneName)) return true;
            if (sceneName == "MyWorld") return true;             // 训练场（旧世界）
            if (sceneName.IndexOf("Village", System.StringComparison.OrdinalIgnoreCase) >= 0) return true;
            if (sceneName.IndexOf("Town", System.StringComparison.OrdinalIgnoreCase) >= 0) return false;
            return false; // 城堡/学园默认石地
        }

        // ---------------- 场景切换 ----------------

        void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            ClearPlayers();
            playerScanTimer = 0f;
            StartCoroutine(RescanAfterScene());
        }

        IEnumerator RescanAfterScene()
        {
            yield return null;
            FindPlayers();
            VfxAmbient.ScanScene();
            yield return new WaitForSecondsRealtime(0.6f);
            FindPlayers();
            VfxAmbient.ScanScene();
        }
    }
}
