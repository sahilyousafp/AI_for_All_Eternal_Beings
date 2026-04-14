// Painterly vertex shader — Week 1 stub.
// Week 3-4 will add view-space normals and fresnel output for the ink
// line pass. For now it's a plain world-space pass-through so the
// scaffold compiles in Three.js ShaderMaterial without errors.

varying vec2 vUv;
varying vec3 vWorldNormal;
varying vec3 vViewDir;

void main() {
  vUv = uv;
  vWorldNormal = normalize(mat3(modelMatrix) * normal);
  vec4 worldPos = modelMatrix * vec4(position, 1.0);
  vViewDir = normalize(cameraPosition - worldPos.xyz);
  gl_Position = projectionMatrix * viewMatrix * worldPos;
}
