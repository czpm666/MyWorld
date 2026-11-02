using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 【Lead 临时验证用，验收后删除】最小地图：验证 MapBootstrap 的运行时生成链
    /// （玩家/相机/UI/SessionBridge/交互/商店/任务板/传送门/拾取）是否端到端可用。
    /// </summary>
    public class SmokeMap : MapBootstrap
    {
        protected override void BuildMapContent(Transform world)
        {
            PlaceSpawn("start", new Vector3(0f, 0f, -8f));

            var props = Prop("Props");

            Box(world, "TestHouse", new Vector3(-10f, 1.6f, 0f), new Vector3(4f, 3.2f, 4f),
                MapMaterials.Get("plaster_warm"), 20f);
            Box(world, "TestRoof", new Vector3(-10f, 3.4f, 0f), new Vector3(4.8f, 0.6f, 4.8f),
                MapMaterials.Get("roof_terracotta"), 20f);
            Box(world, "Cobble", new Vector3(0f, 0.02f, -6f), new Vector3(14f, 0.06f, 10f),
                MapMaterials.Get("cobble"), 0f, false);

            SpawnNpc(NpcRole.Merchant, "杂货商", new Vector3(-5f, 0f, -5f), 90f,
                new[] { "你好，旅人。", "药水和面包都是今早刚到的。" }, "roa_general", null, null);

            QuestBoardInteractable.CreateStand(props.transform, new Vector3(0f, 0f, -3.6f), "roa_guild", 0f);
            ScenePortal.Create(props.transform, new Vector3(5f, 0.1f, -8f), MapId.TrainingGround, "start", "训练场", 200f);
            PickupInteractable.Create(props.transform, new Vector3(2.5f, 0.2f, -6f), PickupKind.Herb, 0, null, "smoke_herb");
            PickupInteractable.Create(props.transform, new Vector3(3.2f, 0.2f, -8.4f), PickupKind.Coin, 35);

            SpawnEnemy(new Vector3(9f, 0f, -16f));
        }
    }
}
