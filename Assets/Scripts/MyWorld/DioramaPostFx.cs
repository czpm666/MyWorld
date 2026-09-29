using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace MyWorld
{
    /// <summary>
    /// 织梦岛的"玩具模型感"主要来自后处理，而不是模型本身：
    /// 景深让近处和远处同时发虚（移轴效果）、外加暗角把视线收拢到中间。
    ///
    /// VolumeProfile 在运行时用代码建，所以不需要任何资源文件；
    /// 所有参数都开在 Inspector 上，直接在场景里调，不用改代码。
    /// </summary>
    [DisallowMultipleComponent]
    [RequireComponent(typeof(Volume))]
    public class DioramaPostFx : MonoBehaviour
    {
        [Header("景深(移轴感)")]
        [Tooltip("默认关闭：等美术风格定下来、确定要玩具模型感时再打开。开启后画面会近远发虚")]
        [SerializeField] private bool useDepthOfField = false;
        [Tooltip("Bokeh 光斑更漂亮")]
        [SerializeField] private DepthOfFieldMode dofMode = DepthOfFieldMode.Bokeh;
        [Tooltip("对焦距离，应当等于相机到角色的距离")]
        [SerializeField] private float focusDistance = 34f;
        [SerializeField, Range(1f, 32f)] private float aperture = 2.8f;
        [SerializeField, Range(1f, 300f)] private float focalLength = 90f;
        [SerializeField] private bool highQualitySampling = true;

        [Header("泛光")]
        [SerializeField] private bool useBloom = true;
        [SerializeField, Range(0f, 5f)] private float bloomIntensity = 0.32f;
        [SerializeField, Range(0f, 2f)] private float bloomThreshold = 1.0f;
        [SerializeField, Range(0f, 1f)] private float bloomScatter = 0.62f;
        [SerializeField] private Color bloomTint = new Color(1f, 0.96f, 0.88f);

        [Header("色彩")]
        [SerializeField] private bool useColorAdjustments = true;
        [SerializeField, Range(-5f, 5f)] private float postExposure = 0.15f;
        [SerializeField, Range(-100f, 100f)] private float contrast = 8f;
        [SerializeField, Range(-100f, 100f)] private float saturation = 14f;
        [SerializeField] private Color colorFilter = new Color(1f, 0.99f, 0.96f);

        [Header("暗角")]
        [SerializeField] private bool useVignette = true;
        [SerializeField, Range(0f, 1f)] private float vignetteIntensity = 0.3f;
        [SerializeField, Range(0.01f, 1f)] private float vignetteSmoothness = 0.5f;

        [Header("颗粒")]
        [SerializeField] private bool useFilmGrain = false;
        [SerializeField, Range(0f, 1f)] private float grainIntensity = 0.15f;

        private Volume volume;
        private VolumeProfile profile;   // 实际生效的那份（Volume 内部副本）
        private VolumeProfile shared;    // 挂在 sharedProfile 上的源，供 Inspector 显示名字
        private bool built;

        private void Start()
        {
            // 已经挂好了烘焙出来的 Profile 资源就用它，别在运行时另建一份覆盖掉。
            if (volume == null) volume = GetComponent<Volume>();
            if (volume != null && volume.sharedProfile != null) return;

            // 外部已经 Configure 过就不重复构建（Start 的执行顺序在组件之间是不确定的）。
            if (!built) Build();
        }

        /// <summary>由世界生成器调用：设定对焦距离并立即构建。</summary>
        public void Configure(float newFocusDistance)
        {
            focusDistance = newFocusDistance;
            Build();
        }

        /// <summary>按当前 Inspector 参数重建 Volume Profile。</summary>
        public void Build()
        {
            built = true;
            volume = GetComponent<Volume>();
            volume.isGlobal = true;

            if (profile != null) Destroy(profile);
            if (shared != null) Destroy(shared);

            // 注意 Volume 的一个坑：首次读 volume.profile 时，它会把 sharedProfile
            // **复制一份**成内部实例，而 VolumeManager 实际用的是那份副本。
            // 所以要先把 sharedProfile 挂上，再取 volume.profile 作为唯一改写目标；
            // 之后所有 override 都必须加在它上面，改 sharedProfile 原文是没有任何效果的。
            shared = ScriptableObject.CreateInstance<VolumeProfile>();
            shared.name = "DioramaProfile (Runtime)";
            volume.sharedProfile = shared;

            profile = volume.profile;
            profile.name = shared.name;

            PopulateProfile(profile);
        }

        /// <summary>
        /// 把当前 Inspector 参数写进给定的 Profile。
        /// 运行时是写进临时的 profile，烘焙时是写进要存成资源的 profile —— 两条路共用这一份逻辑，
        /// 免得调好的参数在烘焙后又变回默认值。
        /// </summary>
        public void PopulateProfile(VolumeProfile target)
        {
            if (target == null) return;

            if (useDepthOfField) BuildDepthOfField(target);
            if (useBloom) BuildBloom(target);
            if (useColorAdjustments) BuildColorAdjustments(target);
            if (useVignette) BuildVignette(target);
            if (useFilmGrain) BuildFilmGrain(target);

            var tone = target.Add<Tonemapping>(true);
            tone.mode.overrideState = true;
            // Neutral 比 ACES 更能保住高饱和的色块颜色，配占位图元更合适。
            tone.mode.value = TonemappingMode.Neutral;
        }

        /// <summary>
        /// 运行时微调景深，改完立即生效，用来快速找参数（不必改代码重编译）。
        /// 改的是当前生效的那份 Profile（可能是烘焙出来的资源），停 Play 后改动不保留。
        /// </summary>
        public void SetDepthOfField(float focus, float apertureValue, float focalLengthValue)
        {
            if (volume == null) volume = GetComponent<Volume>();

            // 烘焙过的场景里用的是 Profile 资源，不能再 Build 一份临时的把它顶掉。
            var target = volume != null ? volume.profile : null;
            if (target == null)
            {
                Build();
                target = profile;
            }
            if (target == null) return;

            if (!target.TryGet<DepthOfField>(out var dof))
                dof = target.Add<DepthOfField>(true);

            dof.mode.overrideState = true;
            dof.mode.value = dofMode;
            dof.focusDistance.overrideState = true;
            dof.focusDistance.value = focus;
            dof.aperture.overrideState = true;
            dof.aperture.value = apertureValue;
            dof.focalLength.overrideState = true;
            dof.focalLength.value = focalLengthValue;
        }

        private void BuildDepthOfField(VolumeProfile p)
        {
            var dof = p.Add<DepthOfField>(true);
            dof.mode.overrideState = true;
            dof.mode.value = dofMode;

            dof.focusDistance.overrideState = true;
            dof.focusDistance.value = focusDistance;
            dof.aperture.overrideState = true;
            dof.aperture.value = aperture;
            dof.focalLength.overrideState = true;
            dof.focalLength.value = focalLength;
            dof.highQualitySampling.overrideState = true;
            dof.highQualitySampling.value = highQualitySampling;

            // 光斑形状：六边形，稍微收一点，像真实光圈
            dof.bladeCount.overrideState = true;
            dof.bladeCount.value = 6;
            dof.bladeCurvature.overrideState = true;
            dof.bladeCurvature.value = 1f;
        }

        private void BuildBloom(VolumeProfile p)
        {
            var bloom = p.Add<Bloom>(true);
            bloom.intensity.overrideState = true;
            bloom.intensity.value = bloomIntensity;
            bloom.threshold.overrideState = true;
            bloom.threshold.value = bloomThreshold;
            bloom.scatter.overrideState = true;
            bloom.scatter.value = bloomScatter;
            bloom.tint.overrideState = true;
            bloom.tint.value = bloomTint;
            bloom.highQualityFiltering.overrideState = true;
            bloom.highQualityFiltering.value = true;
        }

        private void BuildColorAdjustments(VolumeProfile p)
        {
            var ca = p.Add<ColorAdjustments>(true);
            ca.postExposure.overrideState = true;
            ca.postExposure.value = postExposure;
            ca.contrast.overrideState = true;
            ca.contrast.value = contrast;
            ca.saturation.overrideState = true;
            ca.saturation.value = saturation;
            ca.colorFilter.overrideState = true;
            ca.colorFilter.value = colorFilter;
        }

        private void BuildVignette(VolumeProfile p)
        {
            var v = p.Add<Vignette>(true);
            v.intensity.overrideState = true;
            v.intensity.value = vignetteIntensity;
            v.smoothness.overrideState = true;
            v.smoothness.value = vignetteSmoothness;
            v.color.overrideState = true;
            v.color.value = new Color(0.1f, 0.12f, 0.16f);
        }

        private void BuildFilmGrain(VolumeProfile p)
        {
            var g = p.Add<FilmGrain>(true);
            g.type.overrideState = true;
            g.type.value = FilmGrainLookup.Medium1;
            g.intensity.overrideState = true;
            g.intensity.value = grainIntensity;
        }

        private void OnDestroy()
        {
            if (shared != null) Destroy(shared);
            if (profile != null) Destroy(profile);
        }
    }
}
