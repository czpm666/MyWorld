using System.Collections.Generic;
using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 挂在玩家身上：每帧（节流）找最近的 IInteractable，显示提示并处理 E 键。
    /// 用遍历而不是物理层，是因为可交互物数量少（&lt;60），省下改 Layer/Physics 设置的麻烦。
    /// </summary>
    /// <remarks>
    /// ⚠️ 必须独占同名文件（PlayerInteractor.cs）—— 理由见 <see cref="SpawnMarker"/>：
    /// 挤在 Interactables.cs 里时烘焙场景会丢组件（实测 PlayerInteractor 剩 0 个，
    /// 效果就是按 E 完全没反应）。
    /// </remarks>
    [DisallowMultipleComponent]
    public class PlayerInteractor : MonoBehaviour
    {
        [SerializeField] private float radius = 2.6f;

        private MyWorldInput input;
        private readonly List<InteractableBase> candidates = new List<InteractableBase>(64);
        private float refreshTimer;
        private string lastPrompt;

        private void Awake()
        {
            input = GetComponent<MyWorldInput>();
        }

        private void Update()
        {
            if (input == null) input = GetComponent<MyWorldInput>();

            // 菜单/对话框打开时：隐藏提示、不响应 E（输入归 UI）
            if (GameUi.IsOpen || input == null)
            {
                SetPrompt(null);
                return;
            }

            refreshTimer -= Time.deltaTime;
            if (refreshTimer <= 0f)
            {
                refreshTimer = 0.2f;
                RefreshCandidates();
            }

            InteractableBase best = FindNearest();
            SetPrompt(best != null ? best.InteractionPrompt : null);

            if (best != null && input.InteractPressed)
                best.Interact(gameObject);
        }

        private void RefreshCandidates()
        {
            candidates.Clear();
            var all = Object.FindObjectsByType<InteractableBase>(FindObjectsSortMode.None);
            for (int i = 0; i < all.Length; i++)
                if (all[i] != null && all[i].CanInteract) candidates.Add(all[i]);
        }

        private InteractableBase FindNearest()
        {
            InteractableBase best = null;
            float bestSqr = radius * radius;
            Vector3 me = transform.position;
            for (int i = 0; i < candidates.Count; i++)
            {
                var c = candidates[i];
                if (c == null || !c.CanInteract) continue;
                Vector3 d = c.transform.position - me;
                d.y = 0f;
                float sqr = d.sqrMagnitude;
                if (sqr <= bestSqr)
                {
                    bestSqr = sqr;
                    best = c;
                }
            }
            return best;
        }

        private void SetPrompt(string text)
        {
            if (text == lastPrompt) return;
            lastPrompt = text;
            if (GameUi.Instance != null) GameUi.Instance.SetInteractPrompt(text);
        }
    }
}
