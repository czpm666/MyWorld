using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 掉在地上的武器。旋转显示 + 触发球，玩家走过去就捡起来——
    /// 但**只进背包，不会自动装备**（用户的规则）。
    /// </summary>
    [DisallowMultipleComponent]
    public class WeaponPickup : MonoBehaviour
    {
        [SerializeField] private float spinSpeed = 70f;
        [SerializeField] private float bobHeight = 0.12f;
        [SerializeField] private float pickupRadius = 1.6f;
        [Tooltip("掉落后这么久内不可被拾取。没有它的话，武器掉在脚下会当帧被自己吸走，别人根本没机会捡")]
        [SerializeField] private float pickupDelay = 1.0f;

        private float armTimer;

        private WeaponDefinition def;
        private Vector3 basePos;
        private Transform modelRoot;
        private Collider thisTrigger;

        public static WeaponPickup Spawn(WeaponDefinition weapon, Vector3 position)
        {
            if (weapon == null || weapon.model == null) return null;

            var go = new GameObject("Pickup_" + weapon.displayName);
            go.transform.position = position;

            var pickup = go.AddComponent<WeaponPickup>();
            pickup.def = weapon;
            pickup.Build();
            return pickup;
        }

        private void Build()
        {
            basePos = transform.position;

            modelRoot = new GameObject("Model").transform;
            modelRoot.SetParent(transform, false);
            modelRoot.localScale = Vector3.one * 0.62f;

            var inst = Instantiate(def.model, modelRoot);
            inst.transform.localPosition = Vector3.zero;
            // 立起来一点，躺着看不清是什么武器
            inst.transform.localRotation = Quaternion.Euler(-60f, 0f, 0f);

            var trigger = gameObject.AddComponent<SphereCollider>();
            trigger.radius = pickupRadius;
            trigger.isTrigger = true;
            trigger.enabled = false;      // 先关掉，等 armTimer 走完再开
            thisTrigger = trigger;

            armTimer = pickupDelay;

            // 地上的武器要能被抓钩吸过来，所以给它一个运动学刚体当"可移动"标记
            var body = gameObject.AddComponent<Rigidbody>();
            body.isKinematic = true;
            body.useGravity = false;
        }

        private void Update()
        {
            transform.Rotate(Vector3.up, spinSpeed * Time.deltaTime, Space.World);
            float bob = Mathf.Sin(Time.time * 2.5f) * bobHeight;
            transform.position = basePos + Vector3.up * bob;

            if (armTimer > 0f)
            {
                armTimer -= Time.deltaTime;
                if (armTimer <= 0f && thisTrigger != null) thisTrigger.enabled = true;
            }
        }

        private void OnTriggerEnter(Collider other)
        {
            if (armTimer > 0f) return;   // 刚掉的武器有个短暂的无敌期，别被丢的人瞬间捡回

            var combat = other.GetComponentInParent<PlayerCombat>();
            if (combat == null) return;

            combat.PickUp(def);
            Destroy(gameObject);
        }
    }
}
