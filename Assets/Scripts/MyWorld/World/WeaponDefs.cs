using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 新地图的武器构造表。数值必须和 MyWorldBootstrap.BuildLoadout 完全一致
    /// （那是训练场烘焙场景里的真值；这里只是让运行时生成的玩家也拿到同一套武器）。
    /// ⚠️ 改数值请两处一起改，或者以后把两边收敛到这里 —— 现在先保持镜像。
    /// </summary>
    public static class WeaponDefs
    {
        /// <summary>models 顺序固定：法杖、剑、弓、抓钩、盾、魔法护手。</summary>
        public static WeaponDefinition[] CreateAll(GameObject[] models)
        {
            GameObject M(int i) => (models != null && i >= 0 && i < models.Length) ? models[i] : null;

            return new[]
            {
                new WeaponDefinition
                {
                    displayName = "法杖", kind = WeaponKind.Staff, slot = HandSlot.MainHand,
                    model = M(0), damage = 26f, cooldown = 0.55f,
                },
                new WeaponDefinition
                {
                    displayName = "剑", kind = WeaponKind.Sword, slot = HandSlot.MainHand,
                    model = M(1), damage = 20f, cooldown = 0.66f,
                    meleeRange = 2.0f, meleeHalfAngle = 65f, stabKnockbackGrids = 2f,
                },
                new WeaponDefinition
                {
                    displayName = "弓", kind = WeaponKind.Bow, slot = HandSlot.MainHand,
                    model = M(2), damage = 18f, cooldown = 0.7f,
                    arrowSpeed = 34f, arrowLifeTime = 1.6f,
                },
                new WeaponDefinition
                {
                    displayName = "抓钩", kind = WeaponKind.Grapple, slot = HandSlot.OffHand,
                    model = M(3), cooldown = 0.3f,
                },
                new WeaponDefinition
                {
                    displayName = "盾", kind = WeaponKind.Shield, slot = HandSlot.OffHand,
                    model = M(4), cooldown = 0.6f,
                    shieldBashDamage = 6f, shieldBashKnockbackGrids = 2f, shieldBashRange = 2.6f,
                    blockDamageMultiplier = 0.25f,
                },
                new WeaponDefinition
                {
                    displayName = "魔法护手", kind = WeaponKind.Gauntlet, slot = HandSlot.OffHand,
                    model = M(5), cooldown = 0.35f, damage = 18f,
                    castSpeedMultiplier = 1.5f, castDamageMultiplier = 0.3f,
                },
            };
        }

        public static WeaponDefinition Find(WeaponDefinition[] defs, WeaponKind kind)
        {
            if (defs == null) return null;
            for (int i = 0; i < defs.Length; i++)
                if (defs[i] != null && defs[i].kind == kind) return defs[i];
            return null;
        }

        /// <summary>空手载体：不登记进 owned，只写进 WeaponLoadout.unarmed（和训练场一致）。</summary>
        public static WeaponDefinition Unarmed()
        {
            return new WeaponDefinition
            {
                displayName = "空手", kind = WeaponKind.Unarmed, slot = HandSlot.MainHand,
                model = null, damage = 8f, cooldown = 0.45f,
            };
        }
    }
}
