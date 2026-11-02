using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 传送门：走近按 E 切换地图。外观是石拱门 + 发光魔法幕。
    /// </summary>
    /// <remarks>
    /// ⚠️ 必须独占同名文件（ScenePortal.cs）—— 理由见 <see cref="SpawnMarker"/> 的注释：
    /// 挤在 Interactables.cs 里会让场景只能存 hash 式 m_Script 引用，
    /// 重新加载后组件变 missing script（烘焙场景实际丢过 0/2 个传送门）。
    /// </remarks>
    public class ScenePortal : InteractableBase
    {
        [SerializeField] private MapId target = MapId.RoaTown;
        [SerializeField] private string arrivalSpawn = "start";
        [SerializeField] private string targetLabel = "";

        public static ScenePortal Create(Transform parent, Vector3 pos, MapId target, string arrivalSpawn, string label, float yaw = 0f)
        {
            var root = new GameObject("Portal_" + target);
            root.transform.SetParent(parent, false);
            root.transform.position = pos;
            root.transform.rotation = Quaternion.Euler(0f, yaw, 0f);

            var stone = MapMaterials.Get("stone_light");
            var stoneDark = MapMaterials.Get("stone_dark");
            var glow = MapMaterials.Emissive("portal_glow", new Color(0.55f, 0.9f, 1f), 2.2f);
            _ = glow;

            // 两根石柱 + 顶部横梁
            PlaceholderArt.Primitive(PrimitiveType.Cube, root.transform, "PillarL", new Vector3(-1.15f, 1.15f, 0f), new Vector3(0.42f, 2.3f, 0.42f), stone);
            PlaceholderArt.Primitive(PrimitiveType.Cube, root.transform, "PillarR", new Vector3(1.15f, 1.15f, 0f), new Vector3(0.42f, 2.3f, 0.42f), stone);
            PlaceholderArt.Primitive(PrimitiveType.Cube, root.transform, "Lintel", new Vector3(0f, 2.42f, 0f), new Vector3(2.9f, 0.4f, 0.5f), stoneDark);
            PlaceholderArt.Primitive(PrimitiveType.Cube, root.transform, "Step", new Vector3(0f, 0.1f, 0f), new Vector3(2.6f, 0.2f, 1.0f), stoneDark);
            // 门后的发光魔法幕（半透明，作为视觉焦点）
            var veil = PlaceholderArt.Primitive(PrimitiveType.Quad, root.transform, "Veil", new Vector3(0f, 1.15f, 0.05f), new Vector3(1.9f, 2.1f, 1f), MapMaterials.Transparent("portal_veil", new Color(0.5f, 0.85f, 1f), 0.35f));
            veil.transform.localRotation = Quaternion.Euler(0f, 180f, 0f);
            PlaceholderArt.StripCollider(veil);

            var portal = root.AddComponent<ScenePortal>();
            portal.target = target;
            portal.arrivalSpawn = string.IsNullOrEmpty(arrivalSpawn) ? "start" : arrivalSpawn;
            portal.targetLabel = string.IsNullOrEmpty(label) ? GameSession.DisplayNameOf(target) : label;
            portal.prompt = "前往 " + portal.targetLabel;

            WorldText.Create(root.transform, portal.targetLabel, new Vector3(0f, 2.9f, 0f), 0.28f, new Color(1f, 0.95f, 0.8f), 0f, 0.6f);
            return portal;
        }

        public override void Interact(GameObject interactor)
        {
            GameSession.BeginTransition(target, arrivalSpawn);
        }

        // 运行时/编辑器查用：烘焙后校验场景里还剩几个传送门、连的是哪张图
        public MapId Target => target;
        public string ArrivalSpawn => arrivalSpawn;
        public string TargetLabel => targetLabel;
    }
}
