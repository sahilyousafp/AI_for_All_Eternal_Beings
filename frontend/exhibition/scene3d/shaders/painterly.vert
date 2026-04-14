// Phase 10 — painterly vertex shader.
// Exposes world-space normal, view direction, uv, and a derived "wrap"
// coordinate so the fragment shader can do cel-shade ramps, fresnel
// ink lines, and animated brush-stroke offsets.

uniform float uTime;
uniform float uMorph;       // 0..1 — tween between two soil states
uniform float uDegradation; // 0..1 — visual degradation level

varying vec2 vUv;
varying vec3 vWorldNormal;
varying vec3 vWorldPos;
varying vec3 vViewDir;
varying float vFresnel;

// Cheap hash-based noise to offset vertices slightly for a hand-drawn wobble.
float hash(vec3 p) {
  p = fract(p * vec3(443.897, 441.423, 437.195));
  p += dot(p, p.yzx + 19.19);
  return fract((p.x + p.y) * p.z);
}

void main() {
  vUv = uv;

  // Subtle hand-painted wobble — more on degraded surfaces (cracks feel).
  float wobbleAmount = 0.006 + uDegradation * 0.012;
  float wobble = (hash(position * 7.0) - 0.5) * wobbleAmount;
  vec3 wobbled = position + normal * wobble;

  vec4 worldPos4 = modelMatrix * vec4(wobbled, 1.0);
  vWorldPos = worldPos4.xyz;
  vWorldNormal = normalize(mat3(modelMatrix) * normal);
  vViewDir = normalize(cameraPosition - vWorldPos);

  // Fresnel factor baked at vertex level; fragment refines it.
  vFresnel = 1.0 - max(dot(vWorldNormal, vViewDir), 0.0);

  gl_Position = projectionMatrix * viewMatrix * worldPos4;
}
