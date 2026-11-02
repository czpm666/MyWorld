using UnityEditor;
using UnityEngine;
using MyWorld.Kingdom;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// Weather test hooks.  Every item works in Play mode on the loaded scene; they find (or
    /// create) the KingdomWeather instance through its static accessor, so no scene wiring is
    /// needed to try a state out.
    /// </summary>
    public static class KingdomWeatherMenu
    {
        private static KingdomWeather W => KingdomWeather.Instance;

        [MenuItem("Tools/My World/天气/晴 Clear", priority = 520)]
        private static void Clear() { Set(SkyWeather.Clear); }
        [MenuItem("Tools/My World/天气/多云 Cloudy", priority = 521)]
        private static void Cloudy() { Set(SkyWeather.Cloudy); }
        [MenuItem("Tools/My World/天气/阴 Overcast", priority = 522)]
        private static void Overcast() { Set(SkyWeather.Overcast); }
        [MenuItem("Tools/My World/天气/雨 Rain", priority = 523)]
        private static void Rain() { Set(SkyWeather.Rain); }
        [MenuItem("Tools/My World/天气/暴风雨 Storm", priority = 524)]
        private static void Storm() { Set(SkyWeather.Storm); }
        [MenuItem("Tools/My World/天气/雪 Snow", priority = 525)]
        private static void Snow() { Set(SkyWeather.Snow); }
        [MenuItem("Tools/My World/天气/雾 Fog", priority = 526)]
        private static void FogW() { Set(SkyWeather.Fog); }

        [MenuItem("Tools/My World/天气/时刻/清晨 06:20", priority = 540)]
        private static void Dawn() { Hour(6.33f); }
        [MenuItem("Tools/My World/天气/时刻/正午 12:00", priority = 541)]
        private static void Noon() { Hour(12f); }
        [MenuItem("Tools/My World/天气/时刻/黄昏 18:40", priority = 542)]
        private static void Dusk() { Hour(18.66f); }
        [MenuItem("Tools/My World/天气/时刻/夜晚 22:30", priority = 543)]
        private static void Night() { Hour(22.5f); }

        [MenuItem("Tools/My World/天气/自动昼夜 开", priority = 560)]
        private static void AutoOn() { W.autoCycle = true; Debug.Log("[Weather] auto cycle ON, " + W.Describe()); }
        [MenuItem("Tools/My World/天气/自动昼夜 关", priority = 561)]
        private static void AutoOff() { W.autoCycle = false; Debug.Log("[Weather] auto cycle OFF"); }

        [MenuItem("Tools/My World/天气/打印状态", priority = 580)]
        private static void Status()
        {
            var w = W;
            Debug.Log(string.Format(
                "[Weather] {0} | sun={1:0.00} fog={2:0}..{3:0} colour={4} | wind={5} | wet={6}",
                w.Describe(),
                RenderSettings.sun != null ? RenderSettings.sun.intensity : -1f,
                RenderSettings.fogStartDistance, RenderSettings.fogEndDistance,
                RenderSettings.fogColor, w.wind, w.IsWet));
        }

        private static void Set(SkyWeather s)
        {
            if (!Application.isPlaying)
            {
                // Still useful on a stopped editor: writes the intent so Play starts in that state.
                var w = W;
                w.weather = s;
                w.pendingWeather = s;
                Debug.Log("[Weather] preset set to " + s + " (applies on Play)");
                return;
            }
            W.SetWeather(s, 6f);
            Debug.Log("[Weather] → " + s + " over 6 s");
        }

        private static void Hour(float h)
        {
            W.SetHour(h, 0f);
            Debug.Log("[Weather] hour = " + h.ToString("0.00"));
        }
    }
}
