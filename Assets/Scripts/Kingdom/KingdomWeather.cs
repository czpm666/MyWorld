using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace MyWorld.Kingdom
{
    /// <summary>Weather states the capital and the overworld can be in.</summary>
    public enum SkyWeather { Clear, Fair, Cloudy, Overcast, Rain, Storm, Snow, Fog }

    /// <summary>
    /// Full weather + time-of-day + atmosphere driver for the Asura kingdom maps.
    ///
    /// What it owns
    ///  - the sun/moon directional light (angle, colour, intensity, shadows)
    ///  - skybox tint/thickness/exposure and its rotation
    ///  - linear fog (start/end/colour) blended between weather presets and the hour
    ///  - ambient trilight colours and intensity
    ///  - rain / snow / dust particle systems that follow the active camera
    ///  - lightning flashes during storms, wind vectors published to shaders
    ///
    /// What it deliberately does NOT own
    ///  - camera far clip and shadow distance (KingdomAtmosphere owns those; it runs in Start
    ///    and re-asserts the far plane for a few frames)
    ///  - the minimap (it reads nothing from here)
    ///
    /// Usage
    ///    var w = KingdomWeather.Instance;              // auto-creates on first use
    ///    w.SetHour(7.4f, 0f);                          // instant sunrise
    ///    w.SetWeather(SkyWeather.Rain, 12f);           // blend over 12 s
    ///    w.wind = new Vector3(1, 0, 0.3f) * 0.7f;      // shader wind, if anyone listens
    /// </summary>
    [DisallowMultipleComponent]
    public class KingdomWeather : MonoBehaviour
    {
        // ------------------------------------------------------------------
        // tuning
        // ------------------------------------------------------------------
        [Header("Time of day")]
        [Tooltip("Hours per real second when autoCycle is on (0.02 = a 20 minute day).")]
        public float hoursPerSecond = 0.02f;
        public bool autoCycle = true;
        [Range(0f, 24f)] public float hourOfDay = 9.2f;
        [Tooltip("Tilt of the sun path away from the equator, degrees.")]
        public float sunTilt = 22f;

        [Header("Weather")]
        public SkyWeather weather = SkyWeather.Fair;
        public SkyWeather pendingWeather = SkyWeather.Fair;
        public float transitionSeconds = 15f;
        [Range(0f, 1f)] public float rainStrength = 1f;
        public Vector3 wind = new Vector3(0.8f, 0f, 0.35f);

        [Header("Particles")]
        public int maxRainParticles = 2600;
        public int maxSnowParticles = 1800;
        public int maxDustParticles = 420;
        public float rainBox = 34f;
        public float rainHeight = 22f;

        // ------------------------------------------------------------------
        // runtime
        // ------------------------------------------------------------------
        private Light _sun;
        private Light _flash;
        private Light _moon;
        private Camera _cam;
        private Material _sky;
        private ParticleSystem _rain;
        private ParticleSystem _snow;
        private ParticleSystem _dust;
        private Material _rainMat;
        private Material _snowMat;
        private Material _dustMat;

        private SkyWeather _from;
        private float _blend = 1f;
        private float _blendSpeed = 0.1f;
        private float _lightningTimer;
        private float _windGust;

        // weather presets: sunMult, ambient, fog colour, fog start, fog end, sky tint, thickness, exposure
        private struct Preset
        {
            public float sun, ambient, fogStart, fogEnd, thickness, exposure, rain, snow, dust, wind;
            public Color fog, sky, ground;
        }

        private static Preset PresetFor(SkyWeather w)
        {
            switch (w)
            {
                case SkyWeather.Clear:
                    return new Preset
                    {
                        sun = 1.28f, ambient = 1.06f, fogStart = 1600f, fogEnd = 5200f,
                        thickness = 0.55f, exposure = 1.25f, rain = 0f, snow = 0f, dust = 0f, wind = 0.45f,
                        fog = new Color(0.62f, 0.74f, 0.90f), sky = new Color(0.55f, 0.66f, 0.88f),
                        ground = new Color(0.32f, 0.30f, 0.26f)
                    };
                case SkyWeather.Fair:
                    return new Preset
                    {
                        sun = 1.05f, ambient = 0.96f, fogStart = 1100f, fogEnd = 4200f,
                        thickness = 0.72f, exposure = 1.18f, rain = 0f, snow = 0f, dust = 0.10f, wind = 0.62f,
                        fog = new Color(0.68f, 0.755f, 0.855f), sky = new Color(0.53f, 0.64f, 0.86f),
                        ground = new Color(0.30f, 0.285f, 0.245f)
                    };
                case SkyWeather.Cloudy:
                    return new Preset
                    {
                        sun = 0.62f, ambient = 0.86f, fogStart = 780f, fogEnd = 3200f,
                        thickness = 1.15f, exposure = 1.05f, rain = 0f, snow = 0f, dust = 0.20f, wind = 0.85f,
                        fog = new Color(0.66f, 0.70f, 0.76f), sky = new Color(0.62f, 0.66f, 0.72f),
                        ground = new Color(0.28f, 0.28f, 0.27f)
                    };
                case SkyWeather.Overcast:
                    return new Preset
                    {
                        sun = 0.34f, ambient = 0.80f, fogStart = 520f, fogEnd = 2300f,
                        thickness = 1.75f, exposure = 0.95f, rain = 0.18f, snow = 0f, dust = 0f, wind = 1.05f,
                        fog = new Color(0.60f, 0.635f, 0.68f), sky = new Color(0.60f, 0.63f, 0.68f),
                        ground = new Color(0.25f, 0.25f, 0.25f)
                    };
                case SkyWeather.Rain:
                    return new Preset
                    {
                        sun = 0.22f, ambient = 0.72f, fogStart = 380f, fogEnd = 1750f,
                        thickness = 2.10f, exposure = 0.88f, rain = 1f, snow = 0f, dust = 0f, wind = 1.25f,
                        fog = new Color(0.52f, 0.565f, 0.61f), sky = new Color(0.52f, 0.56f, 0.60f),
                        ground = new Color(0.21f, 0.22f, 0.23f)
                    };
                case SkyWeather.Storm:
                    return new Preset
                    {
                        sun = 0.16f, ambient = 0.66f, fogStart = 280f, fogEnd = 1400f,
                        thickness = 2.55f, exposure = 0.82f, rain = 1.35f, snow = 0f, dust = 0f, wind = 1.8f,
                        fog = new Color(0.44f, 0.48f, 0.53f), sky = new Color(0.44f, 0.48f, 0.53f),
                        ground = new Color(0.18f, 0.19f, 0.20f)
                    };
                case SkyWeather.Snow:
                    return new Preset
                    {
                        sun = 0.38f, ambient = 0.95f, fogStart = 520f, fogEnd = 2200f,
                        thickness = 1.55f, exposure = 1.02f, rain = 0f, snow = 1f, dust = 0f, wind = 0.75f,
                        fog = new Color(0.78f, 0.81f, 0.86f), sky = new Color(0.74f, 0.78f, 0.85f),
                        ground = new Color(0.40f, 0.42f, 0.46f)
                    };
                default: // Fog
                    return new Preset
                    {
                        sun = 0.40f, ambient = 0.85f, fogStart = 120f, fogEnd = 900f,
                        thickness = 1.9f, exposure = 1.0f, rain = 0f, snow = 0f, dust = 0f, wind = 0.30f,
                        fog = new Color(0.76f, 0.78f, 0.80f), sky = new Color(0.70f, 0.74f, 0.79f),
                        ground = new Color(0.36f, 0.37f, 0.38f)
                    };
            }
        }

        // ------------------------------------------------------------------
        // lifecycle
        // ------------------------------------------------------------------
        private static KingdomWeather _instance;

        public static KingdomWeather Instance
        {
            get
            {
                if (_instance != null) return _instance;
                _instance = FindFirstObjectByType<KingdomWeather>();
                if (_instance == null)
                {
                    var go = new GameObject("KingdomWeather");
                    _instance = go.AddComponent<KingdomWeather>();
                }
                return _instance;
            }
        }

        private void Awake()
        {
            if (_instance != null && _instance != this)
            {
                Destroy(this);
                return;
            }
            _instance = this;
            _from = weather;
            pendingWeather = weather;
            _blend = 1f;
        }

        private void Start()
        {
            Acquire();
            ApplyImmediate();
        }

        private void OnDestroy()
        {
            if (_instance == this) _instance = null;
            if (_rainMat != null) Destroy(_rainMat);
            if (_snowMat != null) Destroy(_snowMat);
            if (_dustMat != null) Destroy(_dustMat);
        }

        private void Acquire()
        {
            foreach (var l in FindObjectsByType<Light>(FindObjectsSortMode.None))
            {
                if (l.type != LightType.Directional) continue;
                if (_sun == null) _sun = l;
                else if (_moon == null) _moon = l;
            }
            if (_sun == null)
            {
                var go = new GameObject("Sun (KingdomWeather)");
                _sun = go.AddComponent<Light>();
                _sun.type = LightType.Directional;
                go.transform.rotation = Quaternion.Euler(52f, -34f, 0f);
            }
            _sun.shadows = LightShadows.Soft;
            _sun.shadowStrength = 0.92f;

            _sky = RenderSettings.skybox;
            if (_sky == null)
            {
                var sh = Shader.Find("Skybox/Procedural");
                if (sh != null)
                {
                    _sky = new Material(sh) { name = "KingdomSky (weather)" };
                    RenderSettings.skybox = _sky;
                }
            }

            if (_flash == null)
            {
                var go = new GameObject("WeatherFlash");
                go.transform.SetParent(transform, false);
                _flash = go.AddComponent<Light>();
                _flash.type = LightType.Directional;
                _flash.intensity = 0f;
                _flash.color = new Color(0.82f, 0.86f, 1f);
                _flash.shadows = LightShadows.None;
                go.transform.rotation = Quaternion.Euler(64f, 20f, 0f);
            }

            BuildParticles();
        }

        // ------------------------------------------------------------------
        // public API
        // ------------------------------------------------------------------
        public void SetWeather(SkyWeather next, float seconds = -1f)
        {
            if (seconds < 0f) seconds = transitionSeconds;
            if (next == pendingWeather && Mathf.Approximately(_blend, 1f)) return;
            _from = BlendSource();
            pendingWeather = next;
            _blend = seconds <= 0.01f ? 1f : 0f;
            _blendSpeed = seconds <= 0.01f ? 999f : 1f / seconds;
            if (seconds <= 0.01f) weather = next;
        }

        public void SetHour(float hour, float seconds = 0f)
        {
            hourOfDay = Mathf.Repeat(hour, 24f);
            if (seconds <= 0f) ApplyImmediate();
        }

        public bool IsWet => (weather == SkyWeather.Rain || weather == SkyWeather.Storm) && _blend > 0.35f;

        public float Daylight01
        {
            get
            {
                float h = hourOfDay;
                // 0 at night, 1 at noon, smooth through dawn/dusk
                float day = Mathf.Clamp01(Mathf.Sin((h - 6f) / 12f * Mathf.PI));
                return day;
            }
        }

        public string Describe()
        {
            return string.Format("{0} {1:00}:{2:00}", weather, Mathf.FloorToInt(hourOfDay),
                Mathf.FloorToInt((hourOfDay - Mathf.Floor(hourOfDay)) * 60f));
        }

        // ------------------------------------------------------------------
        // update
        // ------------------------------------------------------------------
        private void Update()
        {
            if (_sun == null) Acquire();

            if (autoCycle && !Mathf.Approximately(hoursPerSecond, 0f))
                hourOfDay = Mathf.Repeat(hourOfDay + Time.deltaTime * hoursPerSecond, 24f);

            if (_blend < 1f)
            {
                _blend = Mathf.Min(1f, _blend + Time.deltaTime * _blendSpeed);
                if (_blend >= 1f) weather = pendingWeather;
            }

            Apply();
            DriveParticles();
            DriveLightning();
        }

        private SkyWeather BlendSource()
        {
            // if a blend is in flight, blend from whatever is currently on screen
            return _blend < 0.98f ? _from : weather;
        }

        private void ApplyImmediate()
        {
            if (_sun == null) Acquire();
            _blend = 1f;
            weather = pendingWeather;
            Apply();
        }

        private Preset CurrentPreset()
        {
            var a = PresetFor(_from);
            var b = PresetFor(pendingWeather);
            float t = Mathf.SmoothStep(0f, 1f, _blend);
            return new Preset
            {
                sun = Mathf.Lerp(a.sun, b.sun, t),
                ambient = Mathf.Lerp(a.ambient, b.ambient, t),
                fogStart = Mathf.Lerp(a.fogStart, b.fogStart, t),
                fogEnd = Mathf.Lerp(a.fogEnd, b.fogEnd, t),
                thickness = Mathf.Lerp(a.thickness, b.thickness, t),
                exposure = Mathf.Lerp(a.exposure, b.exposure, t),
                rain = Mathf.Lerp(a.rain, b.rain, t),
                snow = Mathf.Lerp(a.snow, b.snow, t),
                dust = Mathf.Lerp(a.dust, b.dust, t),
                wind = Mathf.Lerp(a.wind, b.wind, t),
                fog = Color.Lerp(a.fog, b.fog, t),
                sky = Color.Lerp(a.sky, b.sky, t),
                ground = Color.Lerp(a.ground, b.ground, t)
            };
        }

        private void Apply()
        {
            var p = CurrentPreset();
            // KingdomAtmosphere (or the scene) may swap the skybox after our Start; adopt it.
            if (RenderSettings.skybox != null && RenderSettings.skybox != _sky) _sky = RenderSettings.skybox;
            float day = Daylight01;                       // 0 night .. 1 noon
            float dusk = 1f - Mathf.Abs(day - 0.24f) * 5f; // golden band near sunrise/sunset
            dusk = Mathf.Clamp01(dusk);

            // ---- sun angle and colour
            float sunAngle = (hourOfDay / 24f) * 360f - 90f;
            _sun.transform.rotation = Quaternion.Euler(sunAngle + 6f, -28f + sunTilt, 0f);
            Color noon = new Color(1f, 0.965f, 0.905f);
            Color dawn = new Color(1f, 0.62f, 0.38f);
            Color night = new Color(0.42f, 0.50f, 0.72f);
            Color sunCol = day > 0.28f ? Color.Lerp(dawn, noon, Mathf.InverseLerp(0.28f, 0.75f, day))
                                       : Color.Lerp(night, dawn, Mathf.InverseLerp(0f, 0.28f, day));
            _sun.color = sunCol;
            _sun.intensity = p.sun * Mathf.Lerp(0.045f, 1f, Mathf.SmoothStep(0f, 1f, day)) * (1f - dusk * 0.12f);

            // ---- sky
            if (_sky != null)
            {
                if (_sky.HasProperty("_SkyTint")) _sky.SetColor("_SkyTint", Color.Lerp(p.sky, new Color(1f, 0.55f, 0.34f), dusk * 0.45f));
                if (_sky.HasProperty("_GroundColor")) _sky.SetColor("_GroundColor", p.ground);
                if (_sky.HasProperty("_AtmosphereThickness")) _sky.SetFloat("_AtmosphereThickness", p.thickness);
                if (_sky.HasProperty("_Exposure")) _sky.SetFloat("_Exposure", p.exposure * Mathf.Lerp(0.55f, 1f, day));
                if (_sky.HasProperty("_SunSize")) _sky.SetFloat("_SunSize", Mathf.Lerp(0.06f, 0.035f, dusk));
                if (_sky.HasProperty("_SunSizeConvergence")) _sky.SetFloat("_SunSizeConvergence", 3.2f);
                if (_sky.HasProperty("_Rotation")) _sky.SetFloat("_Rotation", (hourOfDay / 24f) * 360f);
            }

            // ---- fog: stronger at dawn/dusk, thinner at noon
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            float dawnBoost = 1f - Mathf.Clamp01(day);
            float fogStart = Mathf.Min(p.fogStart, 1000f) * Mathf.Lerp(1f, 0.55f, dawnBoost * 0.6f);
            float fogEnd = Mathf.Min(p.fogEnd, 4200f) * Mathf.Lerp(1f, 0.70f, dawnBoost * 0.5f);
            RenderSettings.fogStartDistance = fogStart;
            RenderSettings.fogEndDistance = fogEnd;
            Color fogCol = Color.Lerp(p.fog, new Color(0.78f, 0.60f, 0.48f), dusk * 0.35f);
            fogCol = Color.Lerp(fogCol, new Color(0.10f, 0.13f, 0.20f), (1f - day) * 0.55f);
            RenderSettings.fogColor = fogCol;

            // ---- ambient
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = Color.Lerp(new Color(0.12f, 0.15f, 0.24f), new Color(0.58f, 0.65f, 0.80f), day) * p.ambient;
            RenderSettings.ambientEquatorColor = Color.Lerp(new Color(0.09f, 0.10f, 0.13f), new Color(0.50f, 0.48f, 0.44f), day) * p.ambient;
            RenderSettings.ambientGroundColor = Color.Lerp(new Color(0.05f, 0.05f, 0.06f), new Color(0.30f, 0.28f, 0.24f), day) * p.ambient;
            RenderSettings.ambientIntensity = Mathf.Lerp(0.55f, 1f, day);

            // ---- wind (published for any shader that wants it)
            _windGust = Mathf.PerlinNoise(Time.time * 0.23f, 3.7f);
            Vector3 wv = wind * p.wind * (0.65f + _windGust * 0.7f);
            Shader.SetGlobalVector("_KingdomWind", new Vector4(wv.x, wv.y, wv.z, p.wind));
            Shader.SetGlobalFloat("_KingdomWetness", IsWet ? Mathf.Clamp01(1f - Mathf.Abs(day - 0.4f)) : 0f);
            Shader.SetGlobalFloat("_KingdomDaylight", day);

            // ---- rain / snow strength
            SetEmission(_rain, p.rain * rainStrength);
            SetEmission(_snow, p.snow);
            SetEmission(_dust, p.dust * Mathf.Clamp01(day + 0.15f));
        }

        private static void SetEmission(ParticleSystem ps, float amount)
        {
            if (ps == null) return;
            var em = ps.emission;
            em.rateOverTimeMultiplier = amount;
            var main = ps.main;
            main.simulationSpeed = Mathf.Lerp(0.75f, 1.25f, Mathf.Clamp01(amount));
            if (amount > 0.01f && !ps.isPlaying) ps.Play();
            else if (amount <= 0.01f && ps.isPlaying) ps.Stop(false, ParticleSystemStopBehavior.StopEmitting);
        }

        // ------------------------------------------------------------------
        // particles
        // ------------------------------------------------------------------
        private void BuildParticles()
        {
            if (_rain == null) _rain = MakeRain();
            if (_snow == null) _snow = MakeSnow();
            if (_dust == null) _dust = MakeDust();
        }

        private Camera Cam
        {
            get
            {
                if (_cam != null) return _cam;
                _cam = Camera.main;
                if (_cam == null)
                {
                    foreach (var c in FindObjectsByType<Camera>(FindObjectsSortMode.None))
                    {
                        if (c.isActiveAndEnabled) { _cam = c; break; }
                    }
                }
                return _cam;
            }
        }

        private ParticleSystem NewSystem(string name)
        {
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            var ps = go.AddComponent<ParticleSystem>();
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.renderMode = ParticleSystemRenderMode.Billboard;
            r.shadowCastingMode = ShadowCastingMode.Off;
            r.receiveShadows = false;
            r.maxParticleSize = 0.5f;
            var main = ps.main;
            main.loop = true;
            main.playOnAwake = false;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            return ps;
        }

        private ParticleSystem MakeRain()
        {
            var ps = NewSystem("WeatherRain");
            var main = ps.main;
            main.startLifetime = 1.15f;
            main.startSpeed = 0f;
            main.startSize = new ParticleSystem.MinMaxCurve(0.035f, 0.055f);
            main.maxParticles = maxRainParticles;
            main.startRotation3D = true;
            main.startRotationX = 0f;
            main.startRotationY = 0f;

            var shape = ps.shape;
            shape.enabled = true;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(rainBox, rainHeight, rainBox);
            shape.position = new Vector3(0f, rainHeight * 0.35f, 0f);

            var vel = ps.velocityOverLifetime;
            vel.enabled = true;
            vel.space = ParticleSystemSimulationSpace.World;
            vel.x = new ParticleSystem.MinMaxCurve(-1.4f, -1.4f);
            vel.y = new ParticleSystem.MinMaxCurve(-16f, -13f);
            vel.z = new ParticleSystem.MinMaxCurve(-0.5f, -0.5f);

            var col = ps.colorOverLifetime;
            col.enabled = true;
            var grad = new Gradient();
            grad.SetKeys(new[]
            {
                new GradientColorKey(new Color(0.72f, 0.78f, 0.86f), 0f),
                new GradientColorKey(new Color(0.80f, 0.86f, 0.94f), 1f)
            }, new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(0.75f, 0.15f), new GradientAlphaKey(0.5f, 1f) });
            col.color = grad;

            _rainMat = MakeStreakMaterial("WeatherRainMat", new Color(0.80f, 0.86f, 0.94f, 0.55f), 9f);
            var r = ps.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = _rainMat;
            r.renderMode = ParticleSystemRenderMode.Stretch;
            r.lengthScale = 9f;
            r.velocityScale = 0.10f;

            var em = ps.emission;
            em.rateOverTime = 0f;
            em.rateOverTimeMultiplier = 0f;
            ps.Play();
            em.rateOverTimeMultiplier = 0f;
            return ps;
        }

        private ParticleSystem MakeSnow()
        {
            var ps = NewSystem("WeatherSnow");
            var main = ps.main;
            main.startLifetime = 6.5f;
            main.startSpeed = 0f;
            main.startSize = new ParticleSystem.MinMaxCurve(0.09f, 0.20f);
            main.maxParticles = maxSnowParticles;

            var shape = ps.shape;
            shape.enabled = true;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(rainBox, rainHeight, rainBox);
            shape.position = new Vector3(0f, rainHeight * 0.35f, 0f);

            var vel = ps.velocityOverLifetime;
            vel.enabled = true;
            vel.space = ParticleSystemSimulationSpace.World;
            vel.x = new ParticleSystem.MinMaxCurve(-1.6f, -0.7f);
            vel.y = new ParticleSystem.MinMaxCurve(-1.7f, -1.1f);
            vel.z = new ParticleSystem.MinMaxCurve(-0.6f, -0.2f);

            var noise = ps.noise;
            noise.enabled = true;
            noise.strength = new ParticleSystem.MinMaxCurve(0.55f);
            noise.frequency = 0.28f;
            noise.scrollSpeed = 0.22f;
            noise.damping = true;

            _snowMat = MakeFlakeMaterial("WeatherSnowMat", new Color(0.98f, 0.99f, 1f, 0.9f));
            var r = ps.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = _snowMat;
            r.renderMode = ParticleSystemRenderMode.Billboard;

            var em = ps.emission;
            em.rateOverTime = 0f;
            em.rateOverTimeMultiplier = 0f;
            ps.Play();
            em.rateOverTimeMultiplier = 0f;
            return ps;
        }

        private ParticleSystem MakeDust()
        {
            var ps = NewSystem("WeatherDust");
            var main = ps.main;
            main.startLifetime = 5.5f;
            main.startSpeed = new ParticleSystem.MinMaxCurve(0.35f, 1.1f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.04f, 0.10f);
            main.maxParticles = maxDustParticles;

            var shape = ps.shape;
            shape.enabled = true;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(rainBox * 0.8f, 8f, rainBox * 0.8f);

            var vel = ps.velocityOverLifetime;
            vel.enabled = true;
            vel.space = ParticleSystemSimulationSpace.World;
            vel.x = new ParticleSystem.MinMaxCurve(-2.1f, -1.2f);
            vel.y = new ParticleSystem.MinMaxCurve(-0.10f, 0.25f);
            vel.z = new ParticleSystem.MinMaxCurve(-0.9f, -0.3f);

            var col = ps.colorOverLifetime;
            col.enabled = true;
            var grad = new Gradient();
            grad.SetKeys(new[] { new GradientColorKey(new Color(0.92f, 0.84f, 0.66f), 0f) },
                         new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(0.55f, 0.3f), new GradientAlphaKey(0f, 1f) });
            col.color = grad;

            _dustMat = MakeFlakeMaterial("WeatherDustMat", new Color(0.92f, 0.86f, 0.70f, 0.5f));
            var r = ps.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = _dustMat;
            r.renderMode = ParticleSystemRenderMode.Billboard;

            var em = ps.emission;
            em.rateOverTime = 0f;
            em.rateOverTimeMultiplier = 0f;
            ps.Play();
            em.rateOverTimeMultiplier = 0f;
            return ps;
        }

        private void DriveParticles()
        {
            var cam = Cam;
            if (cam != null)
            {
                Vector3 p = cam.transform.position;
                Vector3 fwd = cam.transform.forward;
                Vector3 centre = p + fwd * rainBox * 0.35f;
                Follow(_rain, centre);
                Follow(_snow, centre);
                Follow(_dust, new Vector3(p.x, p.y + 2f, p.z));
            }
            if (_rain != null && _rain.isPlaying)
            {
                var vel = _rain.velocityOverLifetime;
                float gust = _windGust * 3f;
                vel.x = new ParticleSystem.MinMaxCurve(-1.4f - gust, -1.0f - gust);
                vel.z = new ParticleSystem.MinMaxCurve(-0.6f - gust * 0.5f, -0.2f);
            }
        }

        private static void Follow(ParticleSystem ps, Vector3 p)
        {
            if (ps == null) return;
            var t = ps.transform;
            t.position = new Vector3(p.x, p.y, p.z);
        }

        // ------------------------------------------------------------------
        // lightning
        // ------------------------------------------------------------------
        private void DriveLightning()
        {
            bool storm = weather == SkyWeather.Storm || (pendingWeather == SkyWeather.Storm && _blend > 0.5f);
            if (!storm || _flash == null)
            {
                if (_flash != null) _flash.intensity = Mathf.Lerp(_flash.intensity, 0f, Time.deltaTime * 6f);
                return;
            }
            _lightningTimer -= Time.deltaTime;
            if (_lightningTimer <= 0f)
            {
                _lightningTimer = UnityEngine.Random.Range(4.5f, 13f);
                StartCoroutine(Flash());
            }
            _flash.intensity = Mathf.Max(0f, _flash.intensity - Time.deltaTime * 90f);
        }

        private IEnumerator Flash()
        {
            float strength = UnityEngine.Random.Range(1.8f, 3.4f);
            for (int i = 0; i < 3; i++)
            {
                _flash.intensity = strength * (i == 0 ? 1f : 0.55f);
                yield return new WaitForSeconds(0.045f);
                _flash.intensity = 0f;
                yield return new WaitForSeconds(0.06f + i * 0.03f);
            }
        }

        // ------------------------------------------------------------------
        // procedural particle materials (no texture assets to import)
        // ------------------------------------------------------------------
        private static Material MakeStreakMaterial(string name, Color col, float stretch)
        {
            Shader sh = Shader.Find("Universal Render Pipeline/Particles/Unlit");
            if (sh == null) sh = Shader.Find("Particles/Standard Unlit");
            if (sh == null) sh = Shader.Find("Sprites/Default");
            var m = new Material(sh) { name = name };
            var tex = StreakTexture();
            if (m.HasProperty("_BaseMap")) m.SetTexture("_BaseMap", tex);
            if (m.HasProperty("_MainTex")) m.SetTexture("_MainTex", tex);
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", col);
            if (m.HasProperty("_Color")) m.SetColor("_Color", col);
            m.renderQueue = 3000;
            return m;
        }

        private static Material MakeFlakeMaterial(string name, Color col)
        {
            Shader sh = Shader.Find("Universal Render Pipeline/Particles/Unlit");
            if (sh == null) sh = Shader.Find("Particles/Standard Unlit");
            if (sh == null) sh = Shader.Find("Sprites/Default");
            var m = new Material(sh) { name = name };
            var tex = FlakeTexture();
            if (m.HasProperty("_BaseMap")) m.SetTexture("_BaseMap", tex);
            if (m.HasProperty("_MainTex")) m.SetTexture("_MainTex", tex);
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", col);
            if (m.HasProperty("_Color")) m.SetColor("_Color", col);
            m.renderQueue = 3000;
            return m;
        }

        private static Texture2D StreakTexture()
        {
            const int w = 4, h = 48;
            var t = new Texture2D(w, h, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
            for (int y = 0; y < h; y++)
            {
                float ty = y / (float)(h - 1);
                float a = Mathf.Sin(ty * Mathf.PI);           // fade both ends
                a = Mathf.Pow(a, 0.7f);
                for (int x = 0; x < w; x++)
                {
                    float tx = Mathf.Abs(x - (w - 1) * 0.5f) / ((w - 1) * 0.5f);
                    float edge = Mathf.Clamp01(1f - tx * tx);
                    t.SetPixel(x, y, new Color(1f, 1f, 1f, a * edge));
                }
            }
            t.Apply();
            return t;
        }

        private static Texture2D FlakeTexture()
        {
            const int s = 16;
            var t = new Texture2D(s, s, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
            for (int y = 0; y < s; y++)
            {
                for (int x = 0; x < s; x++)
                {
                    float dx = (x - (s - 1) * 0.5f) / (s * 0.5f);
                    float dy = (y - (s - 1) * 0.5f) / (s * 0.5f);
                    float d = Mathf.Sqrt(dx * dx + dy * dy);
                    float a = Mathf.Clamp01(1f - d);
                    t.SetPixel(x, y, new Color(1f, 1f, 1f, a * a));
                }
            }
            t.Apply();
            return t;
        }
    }
}
