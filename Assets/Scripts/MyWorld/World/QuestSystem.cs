using System.Collections.Generic;
using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 一条委托的目标：用全局计数器推进（杀敌/采集/对话都由对应交互调用 GameSession.AddCounter）。
    /// 接任务时记录计数器基线，进度 = 当前值 - 基线，所以接任务前杀过的怪不算数。
    /// </summary>
    public class QuestObjectiveDef
    {
        public string counterKey;
        public string text;
        public int required = 1;

        public QuestObjectiveDef() { }

        public QuestObjectiveDef(string counterKey, string text, int required)
        {
            this.counterKey = counterKey;
            this.text = text;
            this.required = required;
        }
    }

    public class QuestDef
    {
        public string id;
        public string boardId;
        public string title;
        public string summary;
        public QuestObjectiveDef[] objectives;
        public int rewardGold;
        public string rewardItemId;
    }

    /// <summary>委托内容表。新增委托往这里加一条即可，不用改系统。</summary>
    public static class QuestContent
    {
        public static readonly QuestDef[] All =
        {
            new QuestDef
            {
                id = "guild_starter", boardId = "roa_guild",
                title = "冒险者协会·试炼", summary = "协会给你的入门委托：清理城郊的魔物，顺手采些药草。",
                objectives = new QuestObjectiveDef[]
                {
                    new QuestObjectiveDef("kill", "击败魔物", 3),
                    new QuestObjectiveDef("collect_herb", "采集药草", 2),
                },
                rewardGold = 100, rewardItemId = "potion_large",
            },
            new QuestDef
            {
                id = "slime_cleanup", boardId = "roa_guild",
                title = "魔物清剿", summary = "城外的魔物越来越多了，协会需要有人去清理。",
                objectives = new QuestObjectiveDef[] { new QuestObjectiveDef("kill", "击败魔物", 5) },
                rewardGold = 80, rewardItemId = "potion_small",
            },
            new QuestDef
            {
                id = "herb_gather", boardId = "roa_guild",
                title = "采集药草", summary = "药剂师需要布耶纳村一带的月光草，越多越好。",
                objectives = new QuestObjectiveDef[] { new QuestObjectiveDef("collect_herb", "采集药草", 3) },
                rewardGold = 60, rewardItemId = "potion_small",
            },
            new QuestDef
            {
                id = "wolf_hunt", boardId = "buena_board",
                title = "布耶纳村·狼群威胁", summary = "村外的狼群开始袭击牲畜了，村长悬赏勇士。",
                objectives = new QuestObjectiveDef[] { new QuestObjectiveDef("kill", "击败魔物", 8) },
                rewardGold = 120, rewardItemId = "potion_large",
            },
            new QuestDef
            {
                id = "crystal_ore", boardId = "ranoa_guild",
                title = "学园委托：采集魔晶", summary = "拉诺亚的研究需要魔晶碎片，学园的公告栏上贴着这张委托。",
                objectives = new QuestObjectiveDef[] { new QuestObjectiveDef("collect_crystal", "采集魔晶", 3) },
                rewardGold = 90, rewardItemId = "potion_elixir",
            },
            new QuestDef
            {
                id = "caravan_watch", boardId = "roa_guild",
                title = "商队护卫", summary = "商队要从罗亚市往布耶纳走一趟，路上不太平，协会在找押车的人。",
                objectives = new QuestObjectiveDef[]
                {
                    new QuestObjectiveDef("kill", "击退袭扰的魔物", 6),
                    new QuestObjectiveDef("collect_herb", "沿途采集药草", 2),
                },
                rewardGold = 150, rewardItemId = "potion_large",
            },
            new QuestDef
            {
                id = "wall_patrol", boardId = "roa_guild",
                title = "城墙夜巡", summary = "夜里城墙外总有动静，卫队人手不够，请冒险者协助巡夜。",
                objectives = new QuestObjectiveDef[] { new QuestObjectiveDef("kill", "清理城墙外的魔物", 4) },
                rewardGold = 70, rewardItemId = "bread",
            },
            new QuestDef
            {
                id = "wolf_pack", boardId = "buena_board",
                title = "布耶纳村·月下狼影", summary = "狼群在满月夜下山，村里需要更多的猎手。",
                objectives = new QuestObjectiveDef[] { new QuestObjectiveDef("kill", "击败魔物", 10) },
                rewardGold = 160, rewardItemId = "potion_large",
            },
            new QuestDef
            {
                id = "academy_fieldwork", boardId = "ranoa_guild",
                title = "学园委托：野外实习护卫", summary = "学生要出城做采集实习，需要一位能打的跟在旁边。",
                objectives = new QuestObjectiveDef[]
                {
                    new QuestObjectiveDef("kill", "保护学生，击败魔物", 5),
                    new QuestObjectiveDef("collect_crystal", "协助采集魔晶", 2),
                },
                rewardGold = 130, rewardItemId = "mana_ink",
            },
        };

        public static QuestDef Find(string id)
        {
            for (int i = 0; i < All.Length; i++)
                if (All[i].id == id) return All[i];
            return null;
        }

        public static string BoardTitle(string boardId)
        {
            switch (boardId)
            {
                case "buena_board": return "布耶纳村 · 公告板";
                case "ranoa_guild": return "拉诺亚学园 · 委托板";
                default: return "冒险者协会 · 委托板";
            }
        }
    }

    public class QuestState
    {
        public QuestDef def;
        public bool accepted;
        public bool claimed;
        public int[] baseline;

        public int ObjectiveProgress(int index)
        {
            if (def == null || index < 0 || index >= def.objectives.Length) return 0;
            int raw = GameSession.GetCounter(def.objectives[index].counterKey) - baseline[index];
            return Mathf.Clamp(raw, 0, def.objectives[index].required);
        }

        public bool AllObjectivesDone()
        {
            for (int i = 0; i < def.objectives.Length; i++)
                if (ObjectiveProgress(i) < def.objectives[i].required) return false;
            return true;
        }

        public bool ReadyToClaim => accepted && !claimed && AllObjectivesDone();

        public string[] ObjectiveLines()
        {
            var lines = new string[def.objectives.Length];
            for (int i = 0; i < lines.Length; i++)
                lines[i] = def.objectives[i].text + "  " + ObjectiveProgress(i) + "/" + def.objectives[i].required;
            return lines;
        }

        public string TrackerLine()
        {
            if (def == null) return null;
            string s = "委托：" + def.title;
            for (int i = 0; i < def.objectives.Length; i++)
                s += "  " + def.objectives[i].text + " " + ObjectiveProgress(i) + "/" + def.objectives[i].required;
            if (ReadyToClaim) s += "  （可领取）";
            return s;
        }
    }

    /// <summary>任务状态机：接受 / 进度 / 领取。状态跨场景保留（static）。</summary>
    public static class QuestSystem
    {
        static readonly List<QuestState> states = new List<QuestState>();
        static readonly Dictionary<string, QuestState> lookup = new Dictionary<string, QuestState>();
        static bool loaded;

        /// <summary>任务状态变化时触发（接任务/进度/领取）。HUD 任务追踪和任务板刷新用它。</summary>
        public static event System.Action Changed;

        static void EnsureLoaded()
        {
            if (loaded) return;
            loaded = true;
            for (int i = 0; i < QuestContent.All.Length; i++)
            {
                var def = QuestContent.All[i];
                var st = new QuestState { def = def, baseline = new int[def.objectives.Length] };
                states.Add(st);
                lookup[def.id] = st;
            }
        }

        public static IReadOnlyList<QuestState> AllStates
        {
            get { EnsureLoaded(); return states; }
        }

        public static QuestState Get(string id)
        {
            EnsureLoaded();
            QuestState s;
            return (id != null && lookup.TryGetValue(id, out s)) ? s : null;
        }

        public static bool Accept(string questId)
        {
            var st = Get(questId);
            if (st == null || st.accepted) return false;
            st.accepted = true;
            for (int i = 0; i < st.def.objectives.Length; i++)
                st.baseline[i] = GameSession.GetCounter(st.def.objectives[i].counterKey);
            Changed?.Invoke();
            return true;
        }

        /// <summary>由 GameSession.AddCounter 转进来：刷新任务追踪/任务板。</summary>
        public static void ReportProgress(string counterKey, int delta)
        {
            EnsureLoaded();
            if (string.IsNullOrEmpty(counterKey)) return;
            bool anyActive = false;
            for (int i = 0; i < states.Count; i++)
            {
                var st = states[i];
                if (!st.accepted || st.claimed) continue;
                for (int j = 0; j < st.def.objectives.Length; j++)
                    if (st.def.objectives[j].counterKey == counterKey) { anyActive = true; break; }
                if (anyActive) break;
            }
            if (anyActive) Changed?.Invoke();
        }

        public static bool Claim(string questId)
        {
            var st = Get(questId);
            if (st == null || !st.ReadyToClaim) return false;
            st.claimed = true;
            GameSession.AddGold(st.def.rewardGold);
            if (!string.IsNullOrEmpty(st.def.rewardItemId)) GameSession.AddPurchasedItem(st.def.rewardItemId);
            GameSession.AddCounter("quest_claimed");
            Changed?.Invoke();
            return true;
        }

        /// <summary>当前应该显示在右上角的任务追踪（第一条已接受未领取的委托）。</summary>
        public static string TrackerLine()
        {
            EnsureLoaded();
            for (int i = 0; i < states.Count; i++)
            {
                var st = states[i];
                if (st.accepted && !st.claimed) return st.TrackerLine();
            }
            return null;
        }

        public static QuestBoardView BuildBoardView(string boardId)
        {
            EnsureLoaded();
            var view = new QuestBoardView { title = QuestContent.BoardTitle(boardId) };
            for (int i = 0; i < states.Count; i++)
            {
                var st = states[i];
                if (st.def.boardId != boardId) continue;
                if (st.claimed) continue;   // 领过的委托不再占板子

                var card = new QuestCard
                {
                    id = st.def.id,
                    title = st.def.title,
                    summary = st.def.summary,
                    objectiveLines = st.ObjectiveLines(),
                    rewardGold = st.def.rewardGold,
                    state = st.ReadyToClaim ? "Ready" : (st.accepted ? "Active" : "Available"),
                    canAccept = !st.accepted,
                    canClaim = st.ReadyToClaim,
                };
                view.cards.Add(card);
            }
            return view;
        }
    }
}
