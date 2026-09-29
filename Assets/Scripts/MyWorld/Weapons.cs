using UnityEngine;

namespace MyWorld
{
    public enum HandSlot { MainHand, OffHand }

    public enum WeaponKind { Staff, Sword, Bow, Grapple, Shield, Gauntlet }

    /// <summary>
    /// 一件武器的全部参数。做成可序列化的普通类而不是 ScriptableObject：
    /// 这样参数直接存在场景里的 WeaponLoadout 上，能在 Inspector 里调、也被烘焙一起保存，
    /// 不用额外管理一堆 .asset 资源。
    ///
    /// 字段是按武器类型分组的，用不到的字段留着不影响（比如剑不读 hookSpeedStart）。
    /// </summary>
    [System.Serializable]
    public class WeaponDefinition
    {
        [Header("身份")]
        public string displayName = "法杖";
        public WeaponKind kind = WeaponKind.Staff;
        public HandSlot slot = HandSlot.MainHand;

        [Tooltip("挂在手上的模型预制体。留空 = 空手")]
        public GameObject model;

        [Header("通用")]
        public float damage = 24f;
        [Tooltip("两次使用之间的冷却(秒)")]
        public float cooldown = 0.5f;

        [Header("剑：挥砍判定")]
        [Tooltip("挥砍能打到的距离")]
        public float meleeRange = 2.0f;
        [Tooltip("挥砍扇形的半角(度)")]
        public float meleeHalfAngle = 65f;
        [Tooltip("连招最后一段（突刺）的击退格数。1 格 = 2 米，和敌人技能的换算一致；0 = 不击退")]
        public float stabKnockbackGrids = 2f;

        [Header("魔法护手：施法增益")]
        [Tooltip("施法速度倍率(冷却除以它)")]
        public float castSpeedMultiplier = 1.5f;
        [Tooltip("伤害倍率")]
        public float castDamageMultiplier = 0.3f;

        [Header("盾：格挡与盾击")]
        [Tooltip("举盾格挡时正面受到的伤害倍率（0.25 = 只吃 25% 伤害）")]
        [Range(0f, 1f)] public float blockDamageMultiplier = 0.25f;
        [Tooltip("盾击的击退格数")]
        public float shieldBashKnockbackGrids = 2f;
        [Tooltip("盾击的伤害")]
        public float shieldBashDamage = 6f;
        [Tooltip("盾击的判定距离")]
        public float shieldBashRange = 2.6f;

        [Header("弓")]
        [Tooltip("箭矢飞行速度")]
        public float arrowSpeed = 34f;
        [Tooltip("箭矢存活时间(秒)，超了就消失")]
        public float arrowLifeTime = 1.6f;
        [Tooltip("箭矢判定半径")]
        public float arrowRadius = 0.28f;

        // 抓钩的行为参数不在这里 —— 全部搬到 GrappleSettings 组件上了
        // （挂在 Player → Grapple 子物体，点它就能看到所有抓钩参数）。
    }
}
