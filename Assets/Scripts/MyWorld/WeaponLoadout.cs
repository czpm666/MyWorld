using System.Collections.Generic;
using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 当前装备。主手、副手各只能装一件（用户的规则）。
    ///
    /// ⚠️ **T-076（分支 B）改了拾取的归宿**：捡到的武器**不再进 `backpack`** ——
    /// 武器的归属**只由 `owned` 决定**（它只增不减，被打掉的也一直在里面）。
    /// `backpack` 现在表示**"武器以外的物品"**（材料/道具等），**当前结构上必然为空**
    /// （全工程只有 `WeaponDefinition` 一种可持有物）。
    /// 理由：原先"打掉的武器仍在 `owned`、捡回又 `Add` 进 `backpack`"会**让同一件武器同时出现在两页**。
    /// `AddToBackpack` / `EquipFromBackpack` **保留**（给旧入口与"过渡态"用），但**正常游玩不再走它们**。
    ///
    /// ⚠️ **T-051 订正**：本文原先写"C 键只切换'当前操作的手'，不换装备" —— **全工程没有 C 键绑定**。
    /// `SwitchHand()` 是**预留的扩展点、当前零调用者**（**保留不删**，但别当成已有功能）。
    ///
    /// 注意：这个类必须单独一个文件 —— Unity 要求 MonoBehaviour 的类名和文件名一致，
    /// 否则 AddComponent 出来的组件在场景里会变成 MISSING(null)。
    /// </summary>
    [DisallowMultipleComponent]
    public class WeaponLoadout : MonoBehaviour
    {
        [SerializeField] private WeaponDefinition mainHand;
        [SerializeField] private WeaponDefinition offHand;
        [SerializeField] private HandSlot activeHand = HandSlot.MainHand;

        // 这两个列表必须序列化：烘焙场景重载时要从场景文件恢复。
        // 非序列化的 List 字段重载后就是空的（武器池会变成 0 把）。
        [SerializeField] private List<WeaponDefinition> backpack = new List<WeaponDefinition>();
        [SerializeField] private List<WeaponDefinition> owned = new List<WeaponDefinition>();

        public WeaponDefinition MainHand => mainHand;
        public WeaponDefinition OffHand => offHand;
        public HandSlot ActiveHand => activeHand;

        /// <summary>
        /// 已拥有的全部武器（含当前装备的两把）。
        /// 换武器是从这个池子里挑，而不是从背包 ——
        /// 背包只装"捡到但还没装备"的额外武器。
        /// </summary>
        public IReadOnlyList<WeaponDefinition> Owned => owned;

        /// <summary>把一把武器登记进"已拥有"。世界生成器在搭玩家时把六把都登记进来。</summary>
        public void RegisterOwned(WeaponDefinition weapon)
        {
            if (weapon != null && !owned.Contains(weapon)) owned.Add(weapon);
        }

        /// <summary>装备一把已拥有的武器到它对应的槽位，并处理武器间的互斥规则。</summary>
        public void Equip(WeaponDefinition weapon)
        {
            if (weapon == null) return;

            if (weapon.slot == HandSlot.MainHand) mainHand = weapon;
            else offHand = weapon;

            EnforceCompatibility();
        }

        /// <summary>
        /// 弓要腾出一只手来拉弓搭箭，所以**用弓时副手不能拿盾**。
        /// 违反时把副手退回抓钩（抓钩总有）。
        /// </summary>
        private void EnforceCompatibility()
        {
            if (mainHand == null || mainHand.kind != WeaponKind.Bow) return;
            if (offHand == null || offHand.kind != WeaponKind.Shield) return;

            for (int i = 0; i < owned.Count; i++)
            {
                if (owned[i] != null && owned[i].kind == WeaponKind.Grapple)
                {
                    offHand = owned[i];
                    Debug.Log("[My World] 用弓时副手不能装盾，已自动换回抓钩");
                    return;
                }
            }
            offHand = null;
        }

        /// <summary>
        /// 当前操作的那只手上的武器（由 `activeHand` 决定）。
        /// ⚠️ 原写"（**C 切换的**那个）"—— **没有 C 键**。切手是 `SwitchHand()`，
        /// 那是**预留的扩展点、当前零调用者**，所以 `activeHand` 目前恒为 `MainHand`（T-051 订正）。
        /// </summary>
        public WeaponDefinition Active => activeHand == HandSlot.MainHand ? mainHand : offHand;

        /// <summary>
        /// 背包：**武器以外的物品**（T-076 分支 B）。**当前结构上必然为空** ——
        /// 全工程只有 `WeaponDefinition` 一种可持有物，所以还没有东西可放。
        /// ⚠️ **它不再承载武器**：武器的归属只看 `owned`。
        /// </summary>
        public IReadOnlyList<WeaponDefinition> Backpack => backpack;

        // ---- T-076：拾取事件的"通知游标" ----
        // 为什么需要它：原先"拾取"是靠**背包数量变多**做边沿检测的（`GameUi.WatchWeaponEvents`），
        // 而 T-076 之后武器**不再进背包** → 数量不变 → **拾取会变成无声发生**（玩家不知道捡到了）。
        // 所以改成由拾取处显式通知。**这不是数值**（没有引入任何时长/阈值/上限常量），只是一个计数器 + 名字。
        [System.NonSerialized] private int pickupCount;
        [System.NonSerialized] private WeaponDefinition lastPickedUp;

        /// <summary>拾取次数（单调递增）。UI 用它做"有没有新拾取"的边沿检测。</summary>
        public int PickupCount => pickupCount;

        /// <summary>最近拾取的那件武器（没有则为 null）。</summary>
        public WeaponDefinition LastPickedUp => lastPickedUp;

        /// <summary>拾取一件武器时由拾取处调用：登记归属 + 通知 UI。</summary>
        public void NotifyPickedUp(WeaponDefinition weapon)
        {
            if (weapon == null) return;
            RegisterOwned(weapon);        // 幂等（内部有 Contains 去重）
            lastPickedUp = weapon;
            pickupCount++;
        }

        /// <summary>副手是不是魔法护手（决定施法增益）。</summary>
        public bool HasGauntlet => offHand != null && offHand.kind == WeaponKind.Gauntlet;

        /// <summary>当前操作的手是不是空手。</summary>
        public bool ActiveIsEmpty => Active == null;

        public void SwitchHand()
        {
            activeHand = activeHand == HandSlot.MainHand ? HandSlot.OffHand : HandSlot.MainHand;
        }

        /// <summary>设置两个槽的装备（世界生成器在搭玩家时调用）。</summary>
        public void SetEquipped(WeaponDefinition main, WeaponDefinition off)
        {
            mainHand = main;
            offHand = off;
        }

        /// <summary>
        /// 拾取：把一件武器放进背包。
        /// ⚠️ **T-076 之后正常游玩不再走这条路** —— 武器归属只看 `owned`（见 `NotifyPickedUp`）。
        /// **保留**它是为了：(a) 旧入口仍可达时不至于编译不过/丢失数据；(b) F8 判据要构造"背包里有武器"的过渡态。
        /// </summary>
        public void AddToBackpack(WeaponDefinition weapon)
        {
            if (weapon != null) backpack.Add(weapon);
        }

        /// <summary>主手武器被打掉（被抓钩命中/被盾击时调用），返回掉的那件。</summary>
        public WeaponDefinition DropMainHand()
        {
            var dropped = mainHand;
            mainHand = null;
            return dropped;
        }

        /// <summary>把背包里的一件装备到对应槽位（给以后的背包界面用）。</summary>
        public void EquipFromBackpack(int index)
        {
            if (index < 0 || index >= backpack.Count) return;

            var w = backpack[index];
            backpack.RemoveAt(index);
            if (w.slot == HandSlot.MainHand) mainHand = w;
            else offHand = w;

            // ⚠️ T-024：这里原先**漏调** EnforceCompatibility()，于是"从背包页装盾"可绕过弓副手互斥
            // —— 主手拿弓 + 副手装盾会同时成立，而 Equip() 走的是另一条会校验的路径（见上方 :50），
            // 两条等价操作行为不一致。现在两条路径过同一道校验。
            // 已知副作用（未擅自改）：若这次装备被互斥规则退回，退回的那件**不会回到背包** ——
            // 与 Equip() 现有行为一致；是否该退回背包属于设计问题，待界面部/总控定。
            EnforceCompatibility();
        }
    }
}
