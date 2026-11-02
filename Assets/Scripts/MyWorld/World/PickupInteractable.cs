using UnityEngine;

namespace MyWorld
{
    /// <summary>地上可拾取物：药草/金币袋/魔晶。捡起后计数 +（可选）加钱/加物品。</summary>
    /// <remarks>
    /// ⚠️ 必须独占同名文件（PickupInteractable.cs）—— 理由见 <see cref="SpawnMarker"/>：
    /// 挤在 Interactables.cs 里会让烘焙场景丢组件（实测 6 个只剩 3 个）。
    /// </remarks>
    public class PickupInteractable : InteractableBase
    {
        [SerializeField] private string counterKey = "collect_herb";
        [SerializeField] private int gold;
        [SerializeField] private string itemId;
        [SerializeField] private string flagKey;

        public static PickupInteractable Create(Transform parent, Vector3 pos, PickupKind kind, int gold = 0, string itemId = null, string flagKey = null)
        {
            var root = new GameObject("Pickup_" + kind);
            root.transform.SetParent(parent, false);
            root.transform.position = pos;

            Material mat;
            Vector3 scale;
            switch (kind)
            {
                case PickupKind.Coin:
                    mat = MapMaterials.Get("glow_gold"); scale = new Vector3(0.34f, 0.12f, 0.34f); break;
                case PickupKind.Crystal:
                    mat = MapMaterials.Emissive("crystal_glow", new Color(0.75f, 0.55f, 1f), 1.8f); scale = new Vector3(0.3f, 0.5f, 0.3f); break;
                default:
                    mat = MapMaterials.Get("foliage"); scale = new Vector3(0.26f, 0.36f, 0.26f); break;
            }
            var body = PlaceholderArt.Primitive(PrimitiveType.Cube, root.transform, "Body", new Vector3(0f, 0.22f, 0f), scale, mat);
            body.transform.localRotation = Quaternion.Euler(0f, 45f, 0f);
            PlaceholderArt.StripCollider(body);
            if (kind == PickupKind.Herb)
            {
                // 几片叶子，让"药草"一眼能认出来
                for (int i = 0; i < 3; i++)
                {
                    float a = i * 120f;
                    var leaf = PlaceholderArt.Primitive(PrimitiveType.Cube, root.transform, "Leaf" + i,
                        new Vector3(Mathf.Sin(a * Mathf.Deg2Rad) * 0.18f, 0.14f + i * 0.05f, Mathf.Cos(a * Mathf.Deg2Rad) * 0.18f),
                        new Vector3(0.3f, 0.03f, 0.12f), MapMaterials.Get("grass"));
                    leaf.transform.localRotation = Quaternion.Euler(0f, a, 20f);
                    PlaceholderArt.StripCollider(leaf);
                }
            }

            var p = root.AddComponent<PickupInteractable>();
            p.counterKey = KindToCounter(kind);
            p.gold = gold;
            p.itemId = itemId;
            p.flagKey = flagKey;
            p.prompt = KindToPrompt(kind);
            return p;
        }

        static string KindToCounter(PickupKind kind)
        {
            switch (kind)
            {
                case PickupKind.Coin: return "collect_coin";
                case PickupKind.Crystal: return "collect_crystal";
                default: return "collect_herb";
            }
        }

        static string KindToPrompt(PickupKind kind)
        {
            switch (kind)
            {
                case PickupKind.Coin: return "拾取金币袋";
                case PickupKind.Crystal: return "采集魔晶";
                default: return "采集药草";
            }
        }

        public override void Interact(GameObject interactor)
        {
            if (!string.IsNullOrEmpty(flagKey))
            {
                if (GameSession.GetFlag(flagKey)) return;
                GameSession.SetFlag(flagKey);
            }
            if (!string.IsNullOrEmpty(counterKey)) GameSession.AddCounter(counterKey);
            if (gold > 0) GameSession.AddGold(gold);
            if (!string.IsNullOrEmpty(itemId)) GameSession.AddPurchasedItem(itemId);
            GameUi.Instance?.ShowToast("获得：" + (gold > 0 ? gold + " 金币" : InteractionPrompt.Replace("采集", "").Replace("拾取", "")));
            Destroy(gameObject);
        }
    }
}
