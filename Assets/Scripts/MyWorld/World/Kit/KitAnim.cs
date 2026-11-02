using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 世界文字自动适配：量 TextMesh 的实际包围盒，把它等比缩放到 maxWidth × maxHeight 内。
    /// 招牌/路牌在 2.5D 相机（距离约 22m、fov 30）下必须够大才看得清，所以统一走这个组件，
    /// 避免每处手调 characterSize。生成后一帧生效，然后自己关掉。
    /// </summary>
    [DisallowMultipleComponent]
    public class KitAutoFitText : MonoBehaviour
    {
        MeshRenderer _mr;
        float _maxW = 1f;
        float _maxH = 0.4f;
        bool _done;
        int _tries;
        Vector3 _baseScale = Vector3.one;

        public void Configure(MeshRenderer mr, float maxWidth, float maxHeight)
        {
            _mr = mr != null ? mr : GetComponent<MeshRenderer>();
            _maxW = maxWidth;
            _maxH = maxHeight;
            _done = false;
            _tries = 0;
            _baseScale = transform.localScale;
        }

        void LateUpdate()
        {
            if (_done) return;
            if (_mr == null)
            {
                _done = true;
                enabled = false;
                return;
            }
            if (_maxW <= 0.001f && _maxH <= 0.001f)
            {
                _done = true;
                enabled = false;
                return;
            }

            // TextMesh 在自己的 Update 里重建网格，这里到 LateUpdate 才量得到正确 bounds。
            Bounds b = _mr.bounds;
            Vector3 s = b.size;
            if (s.x < 0.0005f || s.y < 0.0005f)
            {
                if (++_tries > 10) _done = true;   // 字体/文本没生成出来，放弃适配，保持原尺寸
                return;
            }

            float f = float.MaxValue;
            if (_maxW > 0.001f) f = Mathf.Min(f, _maxW / s.x);
            if (_maxH > 0.001f) f = Mathf.Min(f, _maxH / s.y);
            f = Mathf.Clamp(f, 0.01f, 100f);
            transform.localScale = _baseScale * f;
            _done = true;
            enabled = false;
        }
    }

    /// <summary>缓慢自转（风车、旗帜、浮空法阵）。静态场景不需要就别挂。</summary>
    [DisallowMultipleComponent]
    public class KitSpin : MonoBehaviour
    {
        public float DegreesPerSecond = 20f;
        public Vector3 Axis = Vector3.up;

        void Update()
        {
            transform.Rotate(Axis, DegreesPerSecond * Time.deltaTime, Space.Self);
        }
    }

    /// <summary>轻微上下浮动（悬挂招牌、灯笼、浮空水晶）。</summary>
    [DisallowMultipleComponent]
    public class KitBob : MonoBehaviour
    {
        public float Amplitude = 0.06f;
        public float Speed = 1.4f;
        float _t;
        Vector3 _base;

        void OnEnable()
        {
            _base = transform.localPosition;
            _t = 0f;
        }

        void Update()
        {
            _t += Time.deltaTime * Speed;
            transform.localPosition = _base + Vector3.up * (Mathf.Sin(_t) * Amplitude);
        }
    }
}
