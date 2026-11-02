using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 冒险者协会委托板：靠近按 E 打开任务板；接任务/交任务都通过 IQuestBoardHost 走 QuestSystem。
    /// 两种摆法：① 地图里独立立一块板（CreateStand）；② 挂在协会大厅的墙面上（CreateBoardComponent）。
    /// </summary>
    [DisallowMultipleComponent]
    public class QuestBoardInteractable : InteractableBase, IQuestBoardHost
    {
        [SerializeField] private string boardId = "roa_guild";

        public QuestBoardView View => QuestSystem.BuildBoardView(boardId);
        public string BoardId => boardId;

        public static QuestBoardInteractable CreateBoardComponent(GameObject host, string boardId)
        {
            var c = host.AddComponent<QuestBoardInteractable>();
            c.boardId = string.IsNullOrEmpty(boardId) ? "roa_guild" : boardId;
            c.prompt = "查看委托板";
            return c;
        }

        /// <summary>独立委托板：两根木柱 + 板面 + 钉在上面的委托纸。</summary>
        public static QuestBoardInteractable CreateStand(Transform parent, Vector3 pos, string boardId, float yaw = 0f)
        {
            var root = new GameObject("QuestBoard_" + boardId);
            root.transform.SetParent(parent, false);
            root.transform.position = pos;
            root.transform.rotation = Quaternion.Euler(0f, yaw, 0f);

            var wood = MapMaterials.Get("wood_plank");
            var woodDark = MapMaterials.Get("wood_dark");
            var paper = MapMaterials.Unlit("board_paper", MapMaterials.Hex("#F2E6C8"));

            PlaceholderArt.Primitive(PrimitiveType.Cube, root.transform, "PostL", new Vector3(-0.85f, 0.95f, 0f), new Vector3(0.16f, 1.9f, 0.16f), woodDark);
            PlaceholderArt.Primitive(PrimitiveType.Cube, root.transform, "PostR", new Vector3(0.85f, 0.95f, 0f), new Vector3(0.16f, 1.9f, 0.16f), woodDark);
            PlaceholderArt.Primitive(PrimitiveType.Cube, root.transform, "Board", new Vector3(0f, 1.55f, 0f), new Vector3(1.9f, 1.0f, 0.1f), wood);
            PlaceholderArt.Primitive(PrimitiveType.Cube, root.transform, "Top", new Vector3(0f, 2.12f, 0f), new Vector3(2.1f, 0.14f, 0.34f), woodDark);

            // 钉在板上的委托纸（错落贴几张小纸片）
            for (int i = 0; i < 4; i++)
            {
                float x = -0.62f + (i % 2) * 0.85f;
                float y = 1.3f + (i / 2) * 0.42f;
                var p = PlaceholderArt.Primitive(PrimitiveType.Cube, root.transform, "Paper" + i,
                    new Vector3(x, y, 0.06f), new Vector3(0.5f, 0.34f, 0.02f), paper);
                p.transform.localRotation = Quaternion.Euler(0f, 0f, (i % 2 == 0 ? 3f : -4f));
                PlaceholderArt.StripCollider(p);
            }

            WorldText.Create(root.transform, "委托板", new Vector3(0f, 2.32f, 0f), 0.19f, new Color(0.16f, 0.11f, 0.07f));

            var c = root.AddComponent<QuestBoardInteractable>();
            c.boardId = string.IsNullOrEmpty(boardId) ? "roa_guild" : boardId;
            c.prompt = "查看委托板";
            return c;
        }

        public override void Interact(GameObject interactor)
        {
            GameUi.Instance?.ShowQuestBoard(this);
        }

        public bool Accept(string questId)
        {
            bool ok = QuestSystem.Accept(questId);
            if (ok)
            {
                var st = QuestSystem.Get(questId);
                GameUi.Instance?.ShowToast("接受了委托：" + (st != null ? st.def.title : questId));
            }
            return ok;
        }

        public bool Claim(string questId)
        {
            var st = QuestSystem.Get(questId);
            bool ok = QuestSystem.Claim(questId);
            if (ok && st != null)
                GameUi.Instance?.ShowToast("委托完成：" + st.def.title + "（+" + st.def.rewardGold + " 金币）");
            return ok;
        }
    }
}
