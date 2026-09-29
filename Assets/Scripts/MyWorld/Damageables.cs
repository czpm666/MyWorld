using System.Collections.Generic;
using UnityEngine;

namespace MyWorld
{
    /// <summary>可被法术命中的目标。</summary>
    public interface IDamageable
    {
        void TakeDamage(float amount, Vector3 hitPoint, Vector3 hitNormal);
        bool IsAlive { get; }

        /// <summary>目标的世界位置（锁定、瞄准、放标记都要用）。</summary>
        Transform Transform { get; }
    }

    /// <summary>
    /// 可伤害目标的登记表。锁定功能需要"找到最近的敌人"，
    /// 用登记表比每帧 FindObjectsOfType 遍历整个场景便宜得多，也更好扩展到敌人系统。
    /// </summary>
    public static class DamageableRegistry
    {
        private static readonly List<IDamageable> All = new List<IDamageable>();

        /// <summary>当前登记的目标（只读，遍历时不要改集合）。</summary>
        public static IReadOnlyList<IDamageable> Targets => All;

        public static void Register(IDamageable target)
        {
            if (target == null || All.Contains(target)) return;
            All.Add(target);
        }

        public static void Unregister(IDamageable target)
        {
            if (target == null) return;
            All.Remove(target);
        }
    }
}
