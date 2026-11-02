using UnityEngine;
using UnityEngine.SceneManagement;

namespace MyWorld
{
    /// <summary>
    /// 老场景（训练场 MyWorld 是**烘焙**的，不是运行时生成的）的运行时补丁：
    /// 进 Play / 从新地图回来时，自动给玩家补上 SessionBridge（血量/金币/装备跨图）
    /// 和 PlayerInteractor（新交互系统：E 键），并在广场放一座通往罗亚市的传送门。
    ///
    /// 为什么不直接改烘焙场景：那张场景是 MyWorldBaker 生成的、几百个物件，
    /// 为加两个组件重烘焙一次会带来无谓的 diff 风险；用 RuntimeInitializeOnLoadMethod
    /// 在场景加载后补组件，零场景改动，也不影响已有的烘焙真值。
    /// ⚠️ 只在 MyWorld 场景生效；新地图由 MapBootstrap 自己接。
    /// </summary>
    public static class LegacySceneBridge
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void AfterSceneLoad()
        {
            if (SceneManager.GetActiveScene().name != "MyWorld") return;

            var health = Object.FindFirstObjectByType<PlayerHealth>();
            if (health == null) return;
            var player = health.gameObject;

            if (player.GetComponent<PlayerInteractor>() == null)
                player.AddComponent<PlayerInteractor>();

            if (player.GetComponent<SessionBridge>() == null)
            {
                var bridge = player.AddComponent<SessionBridge>();
                bridge.Configure(health,
                    player.GetComponent<WeaponLoadout>(),
                    Object.FindFirstObjectByType<GameUi>());
            }

            // 传送门：放在广场边缘、玩家出生点右前方，避开木桩和敌人。
            if (Object.FindFirstObjectByType<ScenePortal>() == null)
            {
                var world = GameObject.Find("World");
                ScenePortal.Create(world != null ? world.transform : null,
                    new Vector3(7f, 0.1f, -15f), MapId.RoaTown, "start", "罗亚市", 200f);
            }
        }
    }
}
