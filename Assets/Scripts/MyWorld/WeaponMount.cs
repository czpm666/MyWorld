using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 把武器模型挂到角色的手上。
    ///
    /// KayKit 的模型层级里有两根专门的挂点骨：`handslot.r` / `handslot.l`，
    /// 内置的法杖/魔法书就是 localPosition 全零地挂在它们下面的。
    /// 所以这里也照做：武器实例挂到挂点下、局部归零，位置微调交给偏移参数。
    /// </summary>
    [DisallowMultipleComponent]
    public class WeaponMount : MonoBehaviour
    {
        [Header("挂点（留空则按名字自动找）")]
        [SerializeField] private Transform mainSlot;
        [SerializeField] private Transform offSlot;

        [Header("主手微调")]
        [SerializeField] private Vector3 mainOffset = Vector3.zero;
        [SerializeField] private Vector3 mainEuler = Vector3.zero;

        [Header("副手微调")]
        [SerializeField] private Vector3 offOffset = Vector3.zero;
        [SerializeField] private Vector3 offEuler = Vector3.zero;

        [Header("模型缩放")]
        [Tooltip("保持 1 即可：handslot 已经带着角色的缩放，武器跟着继承才对")]
        [SerializeField] private float modelScale = 1f;

        private GameObject mainInstance;
        private GameObject offInstance;

        /// <summary>副手挂点。抓钩要从这里（枪口）出绳。</summary>
        public Transform OffHandSlot => offSlot;

        private void Awake()
        {
            ResolveSlots();
        }

        /// <summary>按名字找 handslot.r / handslot.l。找不到就保持为空（空手，不报错）。</summary>
        private void ResolveSlots()
        {
            if (mainSlot != null && offSlot != null) return;

            foreach (var t in GetComponentsInChildren<Transform>(true))
            {
                if (t.name == "handslot.r" && mainSlot == null) mainSlot = t;
                else if (t.name == "handslot.l" && offSlot == null) offSlot = t;
                if (mainSlot != null && offSlot != null) break;
            }
        }

        /// <summary>按当前装备刷新手上的模型。换武器/掉武器后要调一次。</summary>
        public void Refresh(WeaponLoadout loadout)
        {
            ResolveSlots();
            if (loadout == null) return;

            mainInstance = Replace(mainInstance, mainSlot, loadout.MainHand, mainOffset, mainEuler);
            offInstance = Replace(offInstance, offSlot, loadout.OffHand, offOffset, offEuler);
        }

        private GameObject Replace(
            GameObject current, Transform slot, WeaponDefinition weapon,
            Vector3 offset, Vector3 euler)
        {
            if (current != null)
            {
                Destroy(current);
                current = null;
            }

            if (slot == null || weapon == null || weapon.model == null) return null;

            var inst = Instantiate(weapon.model, slot);
            inst.name = "Weapon_" + weapon.displayName;
            inst.transform.localPosition = offset;
            inst.transform.localRotation = Quaternion.Euler(euler);
            inst.transform.localScale = Vector3.one * modelScale;

            // 武器是纯装饰，别让它的碰撞体挡住角色自己的 CharacterController
            foreach (var c in inst.GetComponentsInChildren<Collider>(true))
            {
                c.enabled = false;
                Destroy(c);
            }

            return inst;
        }
    }
}
