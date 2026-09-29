using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 抓钩的全部可调参数，**单独一个组件**，挂在 Player 下的 "Grapple" 子物体上。
    ///
    /// 拆出来的原因：抓钩的分支规则参数很多（地面/空中 × 墙/敌人，还有动量交接），
    /// 混在 WeaponLoadout 的武器定义里根本找不到该改哪个。
    /// 现在在 Hierarchy 里点 Player → Grapple，看到的只有抓钩相关的项。
    ///
    /// 规则速查：
    ///   地面 + 固定物 → 只拽一下（groundTug*）
    ///   地面 + 敌人   → 拉到面前（pullTarget*）
    ///   空中 + 固定物 → 飞过去，距离随离地高度增长（airFlight*）
    ///   空中 + 敌人   → 自己飞一半（airFlightEnemyFactor），敌人只挪一点（airPullStopDistance）
    /// </summary>
    [DisallowMultipleComponent]
    public class GrappleSettings : MonoBehaviour
    {
        [Header("钩头飞行")]
        [Tooltip("出手初速度：不要太慢，否则没有打击感")]
        public float hookSpeedStart = 26f;
        [Tooltip("线性加速度：越飞越快")]
        public float hookAccel = 52f;
        public float hookSpeedMax = 80f;
        [Tooltip("钩索最大长度。超了自动收枪")]
        public float hookRange = 19f;

        [Header("拉自己：基础手感")]
        [Tooltip("起拉速度")]
        public float reelSpeedStart = 20f;
        [Tooltip("拉拽加速度：线性加速、越拉越快")]
        public float reelAccel = 38f;
        public float reelSpeedMax = 52f;
        [Tooltip("停止时离锚点保留的距离，别撞进墙里")]
        public float reelStopPadding = 2.2f;

        [Header("地面 + 钩墙：只拽一下")]
        [Tooltip("在地面钩中固定物，只把自己向前拽这么远，不会飞过去")]
        public float groundTugDistance = 4.0f;
        [Tooltip("短拽的速度：低且不加速，拽完几乎不留惯性")]
        public float groundTugSpeed = 9f;

        [Header("空中 + 钩墙：距离随高度增长")]
        [Tooltip("基础飞行距离")]
        public float airFlightBase = 13.5f;
        [Tooltip("离地每高 1 米额外增加的飞行距离")]
        public float airFlightPerHeight = 5.4f;
        [Tooltip("飞行距离上限。实际还会被 hookRange 截住，所以给大一点 = 能飞多远飞多远")]
        public float airFlightMax = 45f;

        [Header("空中 + 钩敌人：当锚点用")]
        [Tooltip("自己飞过去的距离 = 空中钩墙距离 × 这个系数（默认一半）")]
        public float airFlightEnemyFactor = 0.5f;
        [Tooltip("敌人只被挪到离你这么远，不会被拉到面前")]
        public float airPullStopDistance = 4.5f;

        [Header("拉目标（地面钩敌人）")]
        public float pullTargetSpeedStart = 14f;
        public float pullTargetAccel = 26f;
        public float pullTargetMaxSpeed = 34f;
        [Tooltip("目标被拉到离玩家这么近就算到位。调小 = 敌人被拽得越深、行程越长（现在几乎拽到脸上）")]
        public float pullTargetStopDistance = 0.9f;

        [Header("动量交接比例（0~1，越大滑得越远）")]
        [Tooltip("拉拽到距离上限时保留多少速度。别给大：末速 30+ 时系数 0.5 就能滑出近 20 米")]
        public float flightMomentumCarry = 0.16f;
        [Tooltip("地面短拽结束时保留的惯性，要很小否则会滑出去")]
        public float tugMomentumCarry = 0.04f;
        [Tooltip("飞行途中松开右键时保留的惯性")]
        public float releaseMomentumCarry = 0.3f;
    }
}
