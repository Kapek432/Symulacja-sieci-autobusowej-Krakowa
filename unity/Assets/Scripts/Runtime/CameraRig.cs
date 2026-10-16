using UnityEngine;
using UnityEngine.InputSystem;

namespace BusReplay
{
    /// <summary>Kamera znad mapy: przesuwanie, zoom kolkiem, obrot prawym przyciskiem.</summary>
    public class CameraRig : MonoBehaviour
    {
        public const float MinHeight = 150f;
        public const float MaxHeight = 25000f;

        public Vector2 focus = Vector2.zero;
        public float height = 12000f;
        public float pitch = 55f;
        public float yaw = 0f;

        /// <summary>Jedno "oczko" kolka = +-10% wysokosci, niezaleznie od skali scrolla (Input System daje +-1 lub +-120).</summary>
        public static float ZoomHeight(float height, float scroll)
        {
            if (Mathf.Abs(scroll) < 0.01f) return height;
            return Mathf.Clamp(height * Mathf.Pow(0.9f, Mathf.Sign(scroll)), MinHeight, MaxHeight);
        }

        void Start()
        {
            var cam = GetComponent<Camera>();
            if (cam != null) cam.farClipPlane = 60000f;
            Apply();
        }

        void Update()
        {
            var mouse = Mouse.current;
            var kb = Keyboard.current;
            Vector2 move = Vector2.zero;

            if (mouse != null)
            {
                if (mouse.leftButton.isPressed)
                    move -= mouse.delta.ReadValue() * (height * 0.0012f);
                if (mouse.rightButton.isPressed)
                    yaw += mouse.delta.ReadValue().x * 0.2f;
                float scroll = mouse.scroll.ReadValue().y;
                height = ZoomHeight(height, scroll);
            }
            if (kb != null)
            {
                Vector2 k = Vector2.zero;
                if (kb.wKey.isPressed) k.y += 1;
                if (kb.sKey.isPressed) k.y -= 1;
                if (kb.dKey.isPressed) k.x += 1;
                if (kb.aKey.isPressed) k.x -= 1;
                move += k * (height * 0.8f * Time.unscaledDeltaTime);
            }

            if (move != Vector2.zero)
            {
                float r = yaw * Mathf.Deg2Rad;
                Vector2 right = new Vector2(Mathf.Cos(r), -Mathf.Sin(r));
                Vector2 fwd = new Vector2(Mathf.Sin(r), Mathf.Cos(r));
                focus += right * move.x + fwd * move.y;
            }
            Apply();
        }

        void Apply()
        {
            var rot = Quaternion.Euler(pitch, yaw, 0f);
            var target = new Vector3(focus.x, 0f, focus.y);
            float dist = height / Mathf.Sin(pitch * Mathf.Deg2Rad);
            transform.rotation = rot;
            transform.position = target - rot * Vector3.forward * dist;
        }
    }
}
