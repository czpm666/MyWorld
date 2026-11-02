using System;
using System.Collections.Generic;
using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// **音效库**：从 `Assets/Resources/Audio/` 批量加载程序化合成的 wav（Resources.LoadAll），
    /// 用固定数量的 2D/3D 声部（AudioSource 池）播放，**零每帧 GC、无 Instantiate**。
    ///
    /// 用法：
    ///   SfxLibrary.Play("hit_light", hitPoint, 0.8f);        // 3D 空间音
    ///   SfxLibrary.Play2D("ui_click", 0.6f);                  // UI 音
    ///   SfxLibrary.PlayOnPlayer("pickup");                    // 跟随玩家位置
    ///
    /// 旧的 GameAudio 五槽（swing/hit/bow/cast/hurt）继续可用：GameAudio 在自身 clip 为空时会回退到本库。
    /// 本类不持有任何场景引用，跨场景安全。
    /// </summary>
    public static class SfxLibrary
    {
        // 常用名字（与 tools/audio/make_sfx.py 的输出文件名一一对应）
        public const string Swing = "swing";
        public const string HitLight = "hit_light";
        public const string HitHeavy = "hit_heavy";
        public const string HitBlock = "hit_block";
        public const string BowRelease = "bow_release";
        public const string ArrowImpact = "arrow_impact";
        public const string SpellImpact = "spell_impact";
        public const string SpellCast = "cast";
        public const string Heal = "heal";
        public const string MagicHum = "magic_hum";
        public const string FireLoop = "fire_loop";
        public const string SwordSwing = "sword_swing";
        public const string Hurt = "hurt";
        public const string Quest = "quest";
        public const string UiClick = "ui_click";
        public const string UiConfirm = "ui_confirm";
        public const string Coin = "coin";
        public const string Pickup = "pickup";
        public const string Death = "death";
        public const string Portal = "portal";
        public const string GrappleFire = "grapple_fire";
        public const string GrappleHit = "grapple_hit";
        public const string GrapplePull = "grapple_pull";
        public const string FootstepGrass = "footstep_grass";
        public const string FootstepStone = "footstep_stone";

        const int VoiceCount = 16;

        static readonly Dictionary<string, AudioClip> clips = new Dictionary<string, AudioClip>(32, StringComparer.Ordinal);
        static AudioSource[] voices;
        static GameObject root;
        static bool loaded;
        static int nextVoice;
        static Transform cachedPlayer;
        static float playerScanTime;

        /// <summary>已加载的 clip 数量（自检用）。</summary>
        public static int ClipCount
        {
            get
            {
                EnsureLoaded();
                return clips.Count;
            }
        }

        /// <summary>预热：加载资源 + 建声部（VfxDirector 在场景加载后调用一次）。</summary>
        public static void Warmup()
        {
            EnsureLoaded();
            EnsureVoices();
        }

        static void EnsureLoaded()
        {
            if (loaded) return;
            loaded = true;

            AudioClip[] all = Resources.LoadAll<AudioClip>("Audio");
            if (all != null)
            {
                for (int i = 0; i < all.Length; i++)
                {
                    AudioClip c = all[i];
                    if (c == null) continue;
                    clips[c.name] = c;
                }
            }

            // 尚未单独合成的名字先用近似音顶上（保证不静默；真文件出现后以真文件为准）
            AddAlias("grapple_fire", "swing");
            AddAlias("grapple_hit", "hit_heavy");
            AddAlias("grapple_pull", "swing");
            AddAlias("spell_cast", "cast");

            if (Application.isPlaying && clips.Count == 0)
            {
                Debug.LogWarning("[SfxLibrary] Resources/Audio 下没有加载到任何 AudioClip；打击音效将静默。");
            }
        }

        static void AddAlias(string name, string source)
        {
            if (clips.ContainsKey(name)) return;
            AudioClip clip;
            if (clips.TryGetValue(source, out clip) && clip != null) clips[name] = clip;
        }

        /// <summary>按名字取 clip（供 VfxAmbient 之类的循环音使用）；找不到返回 null。</summary>
        public static AudioClip LoadClip(string name)
        {
            EnsureLoaded();
            if (string.IsNullOrEmpty(name)) return null;
            AudioClip clip;
            return clips.TryGetValue(name, out clip) ? clip : null;
        }

        static void EnsureVoices()
        {
            if (voices != null && root != null) return;
            if (!Application.isPlaying) return;

            root = new GameObject("[SfxLibrary]");
            UnityEngine.Object.DontDestroyOnLoad(root);

            voices = new AudioSource[VoiceCount];
            for (int i = 0; i < VoiceCount; i++)
            {
                var go = new GameObject("Voice" + i);
                go.transform.SetParent(root.transform, false);

                var src = go.AddComponent<AudioSource>();
                src.playOnAwake = false;
                src.spatialBlend = 1f;
                src.rolloffMode = AudioRolloffMode.Linear;
                src.minDistance = 6f;
                src.maxDistance = 42f;
                src.dopplerLevel = 0f;
                src.volume = 1f;
                voices[i] = src;
            }
        }

        /// <summary>3D 播放（位置）。找不到 clip 时静默返回。</summary>
        public static void Play(string name, Vector3 position, float volume = 1f, float pitch = 1f)
        {
            if (!Application.isPlaying) return;
            EnsureLoaded();
            EnsureVoices();
            if (voices == null || string.IsNullOrEmpty(name)) return;

            AudioClip clip;
            if (!clips.TryGetValue(name, out clip) || clip == null) return;

            AudioSource src = NextVoice();
            if (src == null) return;

            src.transform.position = position;
            src.spatialBlend = 1f;
            src.clip = clip;
            src.volume = Mathf.Clamp01(volume);
            src.pitch = Mathf.Clamp(pitch, 0.5f, 2f);
            src.minDistance = 6f;
            src.maxDistance = 42f;
            src.Play();
        }

        /// <summary>2D 播放（UI / 无位置提示音）。</summary>
        public static void Play2D(string name, float volume = 1f, float pitch = 1f)
        {
            if (!Application.isPlaying) return;
            EnsureLoaded();
            EnsureVoices();
            if (voices == null || string.IsNullOrEmpty(name)) return;

            AudioClip clip;
            if (!clips.TryGetValue(name, out clip) || clip == null) return;

            AudioSource src = NextVoice();
            if (src == null) return;

            src.clip = clip;
            src.spatialBlend = 0f;
            src.volume = Mathf.Clamp01(volume);
            src.pitch = Mathf.Clamp(pitch, 0.5f, 2f);
            src.Play();
        }

        /// <summary>在玩家位置播放；找不到玩家则 2D。适合拾取/治疗这类"跟着角色"的音。</summary>
        public static void PlayOnPlayer(string name, float volume = 1f, float pitch = 1f)
        {
            Transform player = LocalPlayer();
            if (player != null)
            {
                Play(name, player.position + Vector3.up * 1.1f, volume, pitch);
            }
            else
            {
                Play2D(name, volume, pitch);
            }
        }

        /// <summary>当前本地玩家（按 PlayerHealth 找；缓存 2 秒，避免每帧 FindObjects）。</summary>
        public static Transform LocalPlayer()
        {
            if (cachedPlayer != null) return cachedPlayer;
            if (Time.unscaledTime - playerScanTime < 2f) return null;
            playerScanTime = Time.unscaledTime;

            PlayerHealth[] players = UnityEngine.Object.FindObjectsByType<PlayerHealth>(FindObjectsSortMode.None);
            if (players != null && players.Length > 0 && players[0] != null)
            {
                cachedPlayer = players[0].transform;
            }
            return cachedPlayer;
        }

        static AudioSource NextVoice()
        {
            if (voices == null || voices.Length == 0) return null;

            for (int i = 0; i < voices.Length; i++)
            {
                int idx = (nextVoice + i) % voices.Length;
                if (voices[idx] != null && !voices[idx].isPlaying)
                {
                    nextVoice = (idx + 1) % voices.Length;
                    return voices[idx];
                }
            }

            // 全忙：抢当前轮转声部（保证永远不新建 AudioSource）
            AudioSource steal = voices[nextVoice];
            nextVoice = (nextVoice + 1) % voices.Length;
            return steal;
        }
    }
}
