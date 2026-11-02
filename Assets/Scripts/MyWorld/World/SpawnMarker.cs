using UnityEngine;

namespace MyWorld
{
    /// <summary>出生点标记。传送时按 id 选落点。</summary>
    /// <remarks>
    /// ⚠️ 这个类**必须独占一个同名文件**（SpawnMarker.cs）。
    /// Unity 的 MonoScript 只能对应「文件名 == 类名」的那一个类型；当一个 .cs 里挤了多个
    /// MonoBehaviour 时，除同名那一个之外的类型都拿不到自己的 MonoScript，场景里只能写成
    /// hash 式的 `m_Script: {fileID: &lt;哈希&gt;}` 引用 —— 而 hash 跨会话不稳定，重新加载后
    /// 组件就变成 missing script。
    /// 这不是理论：烘焙后的 `RoaTown.unity` 实际丢过 17 个组件（8 SpawnMarker 剩 3、
    /// 6 PickupInteractable 剩 3、2 ScenePortal 剩 0、1 PlayerInteractor 剩 0），
    /// 而同一个场景里 171 个 guid 式引用的组件（NpcActor / MerchantShop 等）全部正常。
    /// </remarks>
    public class SpawnMarker : MonoBehaviour
    {
        public string id = "start";
        public float yaw;

        public static SpawnMarker Create(Transform parent, string id, Vector3 pos, float yaw = 0f)
        {
            var go = new GameObject("Spawn_" + id);
            go.transform.SetParent(parent, false);
            go.transform.position = pos;
            go.transform.rotation = Quaternion.Euler(0f, yaw, 0f);
            var m = go.AddComponent<SpawnMarker>();
            m.id = id;
            m.yaw = yaw;
            return m;
        }
    }
}
