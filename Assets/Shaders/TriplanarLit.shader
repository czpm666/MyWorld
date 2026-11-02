// 三角平面（triplanar）URP 前向材质。
//
// 为什么需要它：王国套件是从 Blender 导进来的 FBX，mesh.uv.Length == 0 —— 一个顶点
// UV 都没有。URP/Lit 采样 _BaseMap 时所有顶点都落在 (0,0)，整块表面等于取同一个纹素，
// 于是无论贴什么图，画面都是纯色（16x16 亮度标准差 0.00）。
// 这里改成在世界空间按法线权重采样三次（X/Y/Z 三个投影），就完全不依赖 UV。
//
// 关键约定：
//   _BaseMap_ST.z = 一个贴图块对应多少"世界米"（不是 offset！offset 固定为 0）。
//   赋值脚本写 _BaseMap_ST = (1, 1, 米数, 0)，于是 1.6 = 1.6 m 一块石，0.45 = 一块木板。
//   ST.z 为 0 时退回 2.0 m（shader 默认值），避免除零。
//
// 亮度守恒：albedo = _BaseColor * _DetailGain * clamp(1 + _DetailStrength * (rel - 1), 0.15, 3)，
//   rel = 贴图亮度 / 贴图平均亮度，均值恒为 1，所以乘子的均值恒等于 _DetailGain。
//   _DetailGain 由编辑器脚本写成"贴图 (0,0) 纹素的亮度" —— 也就是换 shader 之前
//   （所有顶点 UV 都是 (0,0)）URP/Lit 恒定采到的那一个值。于是换 shader 前后平均亮度
//   几乎不变（实测每通道 ±1/255），只是平色上多出石缝、瓦缝、木纹，_DetailStrength 默认 0.7。
//
// 光照：完全走 URP 自己的 UniversalFragmentPBR，前向 pass 的 keyword / 结构照抄
//   SimpleLit.shader，所以阴影、附加光、Forward+、雾、SH 环境光和 URP/Lit 一致。
//   另外补了 ShadowCaster / DepthOnly / DepthNormals 三个 pass：投影、深度、
//   以及 SSAO（PC_Renderer 的 SSAO Source = Depth Normals）需要的法线缓冲。

Shader "MyWorld/TriplanarLit"
{
    Properties
    {
        [MainTexture] _BaseMap("Base Map (RGB)", 2D) = "white" {}
        [MainColor]   _BaseColor("Base Color", Color) = (1, 1, 1, 1)

        // 法线贴图：kit 这套 mesh 没有 UV、没有切线，所以这里同样按世界空间三投影采样，
        // 强度由编辑器脚本按材质类别写（石/瓦强、灰泥弱）。见 TriplanarNormalOffset。
        [Normal]      _BumpMap("Normal Map (triplanar)", 2D) = "bump" {}
        _BumpScale("Normal Strength", Range(0.0, 2.0)) = 0.8

        // 贴图亮度统计（由 Tools/My World/王国⑦三角平面着色 自动写入）
        _DetailMean("Detail Mean Luminance", Float) = 0.2
        _DetailGain("Detail Gain", Float) = 1.0
        _DetailStrength("Detail Strength", Range(0.0, 1.0)) = 0.7

        _Smoothness("Smoothness", Range(0.0, 1.0)) = 0.1
        _Metallic("Metallic", Range(0.0, 1.0)) = 0.0
        [HDR] _EmissionColor("Emission Color", Color) = (0, 0, 0, 1)

        [HideInInspector] _Cutoff("Alpha Cutoff", Range(0.0, 1.0)) = 0.5
        [HideInInspector] _Surface("__surface", Float) = 0.0
        [HideInInspector] _Blend("__blend", Float) = 0.0
        [HideInInspector] _Cull("__cull", Float) = 2.0
        [HideInInspector] _ZWrite("__zw", Float) = 1.0
        [HideInInspector] _SrcBlend("__src", Float) = 1.0
        [HideInInspector] _DstBlend("__dst", Float) = 0.0
    }

    SubShader
    {
        Tags
        {
            "RenderType" = "Opaque"
            "RenderPipeline" = "UniversalPipeline"
            "UniversalMaterialType" = "Lit"
            "IgnoreProjector" = "True"
            "Queue" = "Geometry"
        }
        LOD 300

        // ------------------------------------------------------------------
        // 前向：唯一真正出颜色的 pass
        // ------------------------------------------------------------------
        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }

            Blend One Zero
            ZWrite On
            ZTest LEqual
            Cull Back

            HLSLPROGRAM
            #pragma target 3.0

            #pragma vertex TriplanarVert
            #pragma fragment TriplanarFrag

            // ---- 材质关键字 ----
            #pragma shader_feature_local_fragment _EMISSION
            #pragma shader_feature_local_fragment _NORMALMAP
            // 顶点色染色（只给地形用：镇子周围晕出一圈土色空地）。默认关，其它材质不受影响。
            #pragma shader_feature_local _VERTEXCOLOR

            // ---- URP 管线关键字（与 SimpleLit 前向 pass 一致） ----
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile _ EVALUATE_SH_MIXED EVALUATE_SH_VERTEX
            #pragma multi_compile _ LIGHTMAP_SHADOW_MIXING
            #pragma multi_compile _ SHADOWS_SHADOWMASK
            #pragma multi_compile _ _LIGHT_LAYERS
            #pragma multi_compile _ _CLUSTER_LIGHT_LOOP
            #pragma multi_compile_fragment _ _ADDITIONAL_LIGHT_SHADOWS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT
            #pragma multi_compile_fragment _ _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fragment _ _SCREEN_SPACE_OCCLUSION
            #pragma multi_compile_fragment _ _DBUFFER_MRT1 _DBUFFER_MRT2 _DBUFFER_MRT3
            #pragma multi_compile_fragment _ _LIGHT_COOKIES
            #include_with_pragmas "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Fog.hlsl"

            #pragma multi_compile_instancing

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/SurfaceData.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            TEXTURE2D(_BaseMap);
            SAMPLER(sampler_BaseMap);
            TEXTURE2D(_BumpMap);
            SAMPLER(sampler_BumpMap);

            CBUFFER_START(UnityPerMaterial)
                float4 _BaseMap_ST;
                half4  _BaseColor;
                half4  _EmissionColor;
                half   _DetailMean;
                half   _DetailGain;
                half   _DetailStrength;
                half   _Smoothness;
                half   _Metallic;
                half   _BumpScale;
                half   _Cutoff;
            CBUFFER_END

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS   : NORMAL;
                half4  color      : COLOR;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                half3  normalWS   : TEXCOORD1;
                half   fogFactor  : TEXCOORD2;
                half4  color      : TEXCOORD3;
                UNITY_VERTEX_INPUT_INSTANCE_ID
                UNITY_VERTEX_OUTPUT_STEREO
            };

            Varyings TriplanarVert(Attributes input)
            {
                Varyings output = (Varyings)0;
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_TRANSFER_INSTANCE_ID(input, output);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

                VertexPositionInputs posInput = GetVertexPositionInputs(input.positionOS.xyz);
                VertexNormalInputs   nrmInput = GetVertexNormalInputs(input.normalOS);

                output.positionCS = posInput.positionCS;
                output.positionWS = posInput.positionWS;
                output.normalWS   = half3(nrmInput.normalWS);
                output.fogFactor  = ComputeFogFactor(posInput.positionCS.z);
                output.color      = input.color;
                return output;
            }

            // 世界空间三角平面采样：|normal|^4 权重，三次投影
            half3 TriplanarAlbedo(float3 positionWS, float3 normalWS)
            {
                float3 w = pow(abs(normalWS), 4.0);
                w /= max(w.x + w.y + w.z, 1e-4);

                // ST.z = 每块贴图多少世界米（ST.zw 另作他用，这里不当 offset 使）
                float tile = _BaseMap_ST.z > 0.001 ? _BaseMap_ST.z : 2.0;
                float3 p = positionWS / tile;
                float2 tiling = _BaseMap_ST.xy;

                half3 cX = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, p.zy * tiling).rgb;
                half3 cY = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, p.xz * tiling).rgb;
                half3 cZ = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, p.xy * tiling).rgb;

                return cX * w.x + cY * w.y + cZ * w.z;
            }

            // 三角平面法线：没有切线，就把每张贴图的切线空间偏移 (x,y) 按该投影的
            // (u,v) 轴序还原成世界轴方向，再按同一套 |n|^6 权重混合后叠加到几何法线上。
            // 严格说这不是切线空间变换（u 方向的叉乘符号会随朝向翻转），但石缝/瓦垄这种
            // 各向同性的凹凸，观感上足够；换来的是零切线数据、零 UV。
            float3 TriplanarNormalOffset(float3 positionWS, float3 normalWS)
            {
                float tile = _BaseMap_ST.z > 0.001 ? _BaseMap_ST.z : 2.0;
                float3 p = positionWS / tile;
                float2 tiling = _BaseMap_ST.xy;

                half3 nx = UnpackNormalScale(SAMPLE_TEXTURE2D(_BumpMap, sampler_BumpMap, p.zy * tiling), _BumpScale);
                half3 ny = UnpackNormalScale(SAMPLE_TEXTURE2D(_BumpMap, sampler_BumpMap, p.xz * tiling), _BumpScale);
                half3 nz = UnpackNormalScale(SAMPLE_TEXTURE2D(_BumpMap, sampler_BumpMap, p.xy * tiling), _BumpScale);

                // 投影轴序：X 投影采样 (z,y)，Y 投影采样 (x,z)，Z 投影采样 (x,y)
                float3 ox = nx.x * float3(0.0, 0.0, 1.0) + nx.y * float3(0.0, 1.0, 0.0);
                float3 oy = ny.x * float3(1.0, 0.0, 0.0) + ny.y * float3(0.0, 0.0, 1.0);
                float3 oz = nz.x * float3(1.0, 0.0, 0.0) + nz.y * float3(0.0, 1.0, 0.0);

                float3 w = pow(abs(normalWS), 6.0);
                w /= max(w.x + w.y + w.z, 1e-4);
                return ox * w.x + oy * w.y + oz * w.z;
            }

            half4 TriplanarFrag(Varyings input) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);

                float3 normalWS = normalize((float3)input.normalWS);

                half3 detail = TriplanarAlbedo(input.positionWS, normalWS);

            #if defined(_NORMALMAP)
                // 石缝/瓦垄/木板纹的起伏。灰度地形（灰泥、茅草）_BumpScale 给得很小，
                // 只有石材/瓦/木头才明显 —— 强度表在 KingdomTriplanarAssign.BumpScaleFor。
                normalWS = normalize(normalWS + TriplanarNormalOffset(input.positionWS, normalWS));
            #endif

                // rel 的均值恒为 1，所以乘子的均值恒等于 _DetailGain —— 也就是换 shader 之前
                // URP/Lit 在 UV(0,0) 上恒定采到的那一个常量，于是平均亮度、平均色调一动不动
                half lum  = dot(detail, half3(0.2126, 0.7152, 0.0722));
                half rel  = lum / max(_DetailMean, 1e-4);
                // 摆幅上下限必须夹住：DetailStrength 给到 3.0 时 1+3*(rel-1) 在 rel<0.67 就一路砸到
                // 0.15，瓦缝/石缝这些暗纹把整座城压成深灰（实测航拍均值 134 -> 87）。现在无论
                // strength 多大，乘子都停在 0.55..1.75，只是"纹路变深/变浅"，不会整体变暗。
                half mult = _DetailGain * clamp(1.0 + _DetailStrength * (rel - 1.0), 0.55, 1.75);

                SurfaceData surfaceData = (SurfaceData)0;
                half3 tint = half3(1.0, 1.0, 1.0);
            #if defined(_VERTEXCOLOR)
                tint = input.color.rgb;
            #endif
                // 大尺度脏化：三角平面每 TileMeters 米重复一次，广场/码头这种大块面上
                // 石纹的"扇形/回纹"会读成图案。这里按 ~23 m 与 ~7 m 两个尺度做平滑噪声乘子，
                // 把重复打断，同时给墙根、大面一点自然的明暗层次（均值仍约 1.0，不改整体亮度）。
                float3 mq  = input.positionWS * 0.043;
                float3 mq2 = input.positionWS * 0.147;
                float macro = 1.0
                    + 0.085 * sin(mq.x * 1.7 + 0.9) * sin(mq.z * 1.3 + 2.1)
                    + 0.060 * sin((mq.x + mq.z) * 0.8 + 1.7)
                    + 0.035 * sin(mq2.x * 1.1 - 0.4) * sin(mq2.z * 1.9 + 3.3);
                surfaceData.albedo      = _BaseColor.rgb * mult * tint * macro;
                surfaceData.metallic    = _Metallic;
                surfaceData.specular    = half3(0.0, 0.0, 0.0);
                surfaceData.smoothness  = _Smoothness;
                surfaceData.normalTS    = half3(0.0, 0.0, 1.0);
                surfaceData.occlusion   = 1.0;
                surfaceData.alpha       = 1.0;
                surfaceData.emission    = half3(0.0, 0.0, 0.0);
            #if defined(_EMISSION)
                surfaceData.emission = _EmissionColor.rgb;
            #endif
                surfaceData.clearCoatMask       = 0.0;
                surfaceData.clearCoatSmoothness = 0.0;

                InputData inputData = (InputData)0;
                inputData.positionWS           = input.positionWS;
                inputData.positionCS           = input.positionCS;
                inputData.normalWS             = normalWS;
                inputData.viewDirectionWS      = GetWorldSpaceNormalizeViewDir(input.positionWS);
                inputData.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(input.positionCS);
                inputData.shadowMask           = half4(1.0, 1.0, 1.0, 1.0);
                inputData.bakedGI              = SampleSH(normalWS);
                inputData.vertexLighting       = VertexLighting(input.positionWS, half3(normalWS));
                inputData.fogCoord             = InitializeInputDataFog(float4(input.positionWS, 1.0), input.fogFactor);
            #if defined(MAIN_LIGHT_CALCULATE_SHADOWS)
                inputData.shadowCoord          = TransformWorldToShadowCoord(input.positionWS);
            #else
                inputData.shadowCoord          = float4(0.0, 0.0, 0.0, 0.0);
            #endif

                half4 color = UniversalFragmentPBR(inputData, surfaceData);
                color.rgb = MixFog(color.rgb, inputData.fogCoord);
                return color;
            }
            ENDHLSL
        }

        // ------------------------------------------------------------------
        // 投影：往 shadow map 里写深度，不然整座城不投影
        // ------------------------------------------------------------------
        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode" = "ShadowCaster" }

            ZWrite On
            ZTest LEqual
            ColorMask 0
            Cull Back

            HLSLPROGRAM
            #pragma target 3.0

            #pragma vertex ShadowPassVertex
            #pragma fragment ShadowPassFragment

            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            #pragma multi_compile_instancing

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            CBUFFER_START(UnityPerMaterial)
                float4 _BaseMap_ST;
                half4  _BaseColor;
                half4  _EmissionColor;
                half   _DetailMean;
                half   _DetailGain;
                half   _DetailStrength;
                half   _Smoothness;
                half   _Metallic;
                half   _BumpScale;
                half   _Cutoff;
            CBUFFER_END

            #include "Packages/com.unity.render-pipelines.universal/Shaders/ShadowCasterPass.hlsl"
            ENDHLSL
        }

        // ------------------------------------------------------------------
        // 深度：深度图 / 深度预通道
        // ------------------------------------------------------------------
        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode" = "DepthOnly" }

            ZWrite On
            ColorMask R
            Cull Back

            HLSLPROGRAM
            #pragma target 3.0

            #pragma vertex DepthOnlyVertex
            #pragma fragment DepthOnlyFragment

            #pragma multi_compile_instancing

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            CBUFFER_START(UnityPerMaterial)
                float4 _BaseMap_ST;
                half4  _BaseColor;
                half4  _EmissionColor;
                half   _DetailMean;
                half   _DetailGain;
                half   _DetailStrength;
                half   _Smoothness;
                half   _Metallic;
                half   _BumpScale;
                half   _Cutoff;
            CBUFFER_END

            #include "Packages/com.unity.render-pipelines.universal/Shaders/DepthOnlyPass.hlsl"
            ENDHLSL
        }

        // ------------------------------------------------------------------
        // 法线：PC_Renderer 的 SSAO 用 Depth Normals 作来源，没有这个 pass
        // 整座城会从 AO 的法线缓冲里消失（AO 反差全变），所以这里补上
        // ------------------------------------------------------------------
        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode" = "DepthNormals" }

            ZWrite On
            Cull Back

            HLSLPROGRAM
            #pragma target 3.0

            #pragma vertex DepthNormalsVertex
            #pragma fragment DepthNormalsFragment

            #pragma multi_compile_fragment _ _GBUFFER_NORMALS_OCT
            #pragma multi_compile_instancing

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            CBUFFER_START(UnityPerMaterial)
                float4 _BaseMap_ST;
                half4  _BaseColor;
                half4  _EmissionColor;
                half   _DetailMean;
                half   _DetailGain;
                half   _DetailStrength;
                half   _Smoothness;
                half   _Metallic;
                half   _BumpScale;
                half   _Cutoff;
            CBUFFER_END

            #include "Packages/com.unity.render-pipelines.universal/Shaders/DepthNormalsPass.hlsl"
            ENDHLSL
        }
    }

    FallBack "Hidden/Universal Render Pipeline/FallbackError"
}
