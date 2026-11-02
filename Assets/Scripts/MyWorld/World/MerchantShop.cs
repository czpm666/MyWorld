using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 商人：靠近按 E 打开商店面板。购买逻辑在这里（UI 只调 Buy），
    /// 买下后立即生效并记进 GameSession 背包（目前药水是"买完即饮"，没有独立的使用界面）。
    /// </summary>
    [DisallowMultipleComponent]
    public class MerchantShop : InteractableBase, IShopHost
    {
        [SerializeField] private string shopId = "roa_general";
        [SerializeField] private string merchantName = "商人";

        public ShopView View => ShopCatalog.GetShop(shopId);
        public string MerchantName => merchantName;

        public void Configure(string id, string name)
        {
            shopId = id;
            merchantName = name;
            prompt = "与 " + name + " 交易";
        }

        public override void Interact(GameObject interactor)
        {
            GameUi.Instance?.ShowShop(this);
        }

        public bool Buy(string itemId)
        {
            var def = ShopCatalog.Get(itemId);
            if (def == null) return false;

            var health = Object.FindFirstObjectByType<PlayerHealth>();
            bool needsHeal = def.effect == ShopEffect.Heal || def.effect == ShopEffect.FullHeal;
            if (needsHeal && health != null && health.HealthFraction >= 0.999f)
            {
                GameUi.Instance?.ShowToast("生命已满，不需要药水");
                return false;
            }

            if (!GameSession.SpendGold(def.price))
            {
                GameUi.Instance?.ShowToast("金币不足（需要 " + def.price + "）");
                return false;
            }

            GameSession.AddPurchasedItem(itemId);

            if (health != null && def.effect == ShopEffect.Heal)
                health.Heal(def.amount);
            else if (health != null && def.effect == ShopEffect.FullHeal)
                health.Heal(health.MaxHealth);

            GameUi.Instance?.ShowToast("购买了 " + def.displayName + "（-" + def.price + " 金币）");
            return true;
        }
    }
}
