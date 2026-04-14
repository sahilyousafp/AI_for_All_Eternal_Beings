// Painterly fragment shader — Week 1 stub.
// Week 3-4: cel-shade band ramp, fresnel ink-line edges, texture
// stylization against the Nano Banana ground sampler. For now this is
// a plain textured surface so the scaffold compiles and renders.

uniform sampler2D uGroundTex;
uniform vec3 uRimColor;

varying vec2 vUv;
varying vec3 vWorldNormal;
varying vec3 vViewDir;

void main() {
  vec3 base = texture2D(uGroundTex, vUv).rgb;
  float fresnel = pow(1.0 - max(dot(vWorldNormal, vViewDir), 0.0), 2.5);
  vec3 rim = uRimColor * fresnel * 0.4;
  gl_FragColor = vec4(base + rim, 1.0);
}
