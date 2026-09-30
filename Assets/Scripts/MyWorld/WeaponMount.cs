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

        [Header("刀尖拖尾（T-012）")]
        [Tooltip("拖尾残留时间（秒）。比法术弹的 0.22 短 —— 近战扫过更快，长尾会糊")]
        [SerializeField] private float trailTime = 0.18f;
        [Tooltip("拖尾起始宽度（米）。比法术弹的 0.3 细 —— 刀刃不是弹体")]
        [SerializeField] private float trailStartWidth = 0.10f;
        [Tooltip("最小顶点间距（米）。挥砍位移比弹体小，需要更密的采样")]
        [SerializeField] private float trailMinVertexDistance = 0.04f;

        private GameObject mainInstance;
        private GameObject offInstance;

        /// <summary>主手武器上的刀尖拖尾（每次重建武器实例时重建）。</summary>
        private TrailRenderer mainTrail;
        /// <summary>拖尾还要发射多久（秒）。≤0 即关闭发射。</summary>
        private float trailEmitTimer;

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

            // T-012：刀尖拖尾只挂在**主手**（＝剑）。副手（抓钩/盾/护手）不挂。
            mainInstance = Replace(mainInstance, mainSlot, loadout.MainHand, mainOffset, mainEuler, true);
            offInstance = Replace(offInstance, offSlot, loadout.OffHand, offOffset, offEuler, false);
        }

        /// <summary>
        /// 挥砍时让刀尖拖尾发射一段时间。**颜色由调用方给**（= 当段刀光的颜色，规格 §2.3）。
        /// ⚠️ 门控在这里内部计时：0.30s 后自动停 → "平时没有拖尾"（判据 F7）**不依赖调用方每帧调用**。
        /// </summary>
        public void EmitSlashTrail(Color color, float seconds)
        {
            if (mainTrail == null) return;          // 主手不是剑（或没有模型）→ 静默不发射

            var start = color * 0.9f;               // 规格 §2.3：startColor = 该段刀光色 × 0.9
            start.a = 1f;
            var end = color;
            end.a = 0f;                             // 规格 §2.3：endColor = 同色、alpha 0

            mainTrail.startColor = start;
            mainTrail.endColor = end;
            mainTrail.emitting = true;
            if (seconds > trailEmitTimer) trailEmitTimer = seconds;
        }

        private void Update()
        {
            if (trailEmitTimer <= 0f) return;
            trailEmitTimer -= Time.deltaTime;
            if (trailEmitTimer <= 0f && mainTrail != null) mainTrail.emitting = false;
        }

        /// <summary>
        /// T-012：给武器实例挂一个**刀尖锚点 + TrailRenderer**。
        ///
        /// ⚠️ **必须在 `Replace()` 里建**：武器实例每次装备/掉落都会**销毁并重建**
        /// （`Replace` 开头 `Destroy(current)`）→ 挂在别处（角色根/骨骼/prefab）会**随重建消失，
        /// 而且不会有任何报错**（规格 §2.1）。这正是"静默失败"的典型形状。
        /// </summary>
        private void AttachBladeTrail(GameObject inst)
        {
            if (inst == null) return;

            // 刀尖位置**由运行时算**，不猜 Unity 的坐标三元组
            // （规格 §2.2：Blender 侧局部轴 ≠ Unity 侧；所以按"离模型原点最远的那一端"取，**与轴无关**）。
            // 用 `Renderer.localBounds`（**局部空间**）而不是 `bounds`（世界空间）。
            Bounds lb = default(Bounds);
            bool any = false;
            foreach (var mr in inst.GetComponentsInChildren<MeshRenderer>(true))
            {
                if (mr == null) continue;
                if (!any) { lb = mr.localBounds; any = true; }
                else lb.Encapsulate(mr.localBounds);
            }
            if (!any) return;   // 没有网格 → 不挂（不报错）

            Vector3 tip = lb.center;
            float bestLen = -1f;
            for (int i = 0; i < 8; i++)
            {
                var c = new Vector3(
                    lb.center.x + ((i & 1) == 0 ? -lb.extents.x : lb.extents.x),
                    lb.center.y + ((i & 2) == 0 ? -lb.extents.y : lb.extents.y),
                    lb.center.z + ((i & 4) == 0 ? -lb.extents.z : lb.extents.z));
                float len = c.magnitude;
                if (len > bestLen) { bestLen = len; tip = c; }
            }

            var anchor = new GameObject("BladeTip");
            anchor.transform.SetParent(inst.transform, false);
            anchor.transform.localPosition = tip;
            anchor.transform.localRotation = Quaternion.identity;

            var t = anchor.AddComponent<TrailRenderer>();
            // 参数**照抄项目里已验证可用的同类**（`SpellProjectile` 的法术弹拖尾），只改颜色与时间。
            t.time = trailTime;
            t.startWidth = trailStartWidth;
            t.endWidth = 0f;
            t.minVertexDistance = trailMinVertexDistance;
            t.material = PlaceholderArt.GetGlowMaterial();
            t.startColor = Color.white;
            t.endColor = new Color(1f, 1f, 1f, 0f);
            t.sortingOrder = 30;          // 与法术弹一致，避免与刀光穿插
            t.emitting = false;           // F7：**平时不发射**（只在挥砍那 0.30s 内发射）
            t.autodestruct = false;

            mainTrail = t;
            Debug.Log($"[My World] 刀尖锚点 localPos={tip.ToString("F3")}（|pos|={bestLen:F3}）"
                      + " —— 由 renderer.localBounds 取最远端算出");
        }

        private GameObject Replace(
            GameObject current, Transform slot, WeaponDefinition weapon,
            Vector3 offset, Vector3 euler, bool withTrail)
        {
            if (withTrail) { mainTrail = null; trailEmitTimer = 0f; }   // 主手被替换 → 旧拖尾随实例一起销毁

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

            if (withTrail) AttachBladeTrail(inst);

            return inst;
        }
    }
}
