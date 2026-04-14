// Phase 10 — painterly fragment shader.
// Produces a Studio-Ghibli-meets-Björk-Biophilia look by combining:
//   - a Nano Banana ground texture sampler as the base color
//   - cel-shade band ramp (3 bands) driven by world light
//   - warm fresnel rim ink line that darkens degraded surfaces
//   - subtle hue shift toward cool grey as uDegradation rises
//   - tiny brush-stroke noise on the base color
//
// Every parameter is tunable via uniforms so the JS side can morph
// between healthy and degraded states in real time with the year slider.

uniform sampler2D uGroundTex;
uniform sampler2D uGroundTexNext;  // next year bucket, mix via uMorph
uniform float uMorph;              // 0..1 — blend factor
uniform float uDegradation;        // 0..1 — visual degradation
uniform float uTime;
uniform vec3 uRimColor;
uniform float uRimIntensity;
uniform vec3 uLightDir;

varying vec2 vUv;
varying vec3 vWorldNormal;
varying vec3 vWorldPos;
varying vec3 vViewDir;
varying float vFresnel;

// Cheap 2D hash noise for brush-stroke texture.
float hash2(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise2(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  float a = hash2(i);
  float b = hash2(i + vec2(1.0, 0.0));
  float c = hash2(i + vec2(0.0, 1.0));
  float d = hash2(i + vec2(1.0, 1.0));
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

// 3-step cel shade ramp — maps continuous NdotL to 3 discrete lighting bands.
float celBands(float ndotl) {
  if (ndotl < 0.28) return 0.35;
  if (ndotl < 0.62) return 0.65;
  return 1.0;
}

void main() {
  // Blend the two ground textures for smooth year-slider morphing.
  vec3 baseA = texture2D(uGroundTex, vUv).rgb;
  vec3 baseB = texture2D(uGroundTexNext, vUv).rgb;
  vec3 base = mix(baseA, baseB, clamp(uMorph, 0.0, 1.0));

  // Brush stroke noise layered over the base color.
  float brush = noise2(vUv * 48.0 + vec2(uTime * 0.03, 0.0));
  base *= mix(0.92, 1.08, brush);

  // Cool-grey desaturation as degradation increases.
  vec3 grey = vec3(dot(base, vec3(0.299, 0.587, 0.114)));
  vec3 deadColor = mix(grey, vec3(0.55, 0.58, 0.62), 0.35);
  base = mix(base, deadColor, clamp(uDegradation * 0.8, 0.0, 1.0));

  // Cel-shaded key light.
  float ndotl = max(dot(normalize(vWorldNormal), normalize(uLightDir)), 0.0);
  float bands = celBands(ndotl);

  // Fresnel ink line — sharpens on degraded surfaces for crack feel.
  float fresnel = pow(clamp(vFresnel, 0.0, 1.0), mix(3.0, 1.6, uDegradation));
  vec3 rim = uRimColor * fresnel * uRimIntensity;

  // Ink line darkening at the very edge.
  float inkLine = smoothstep(0.72, 0.98, fresnel) * (0.4 + uDegradation * 0.3);
  vec3 inked = base * (1.0 - inkLine);

  vec3 lit = inked * bands + rim;

  // Subtle inner glow for healthy soil, suppressed when degraded.
  float glow = (1.0 - uDegradation) * 0.12;
  lit += vec3(0.85, 0.55, 0.2) * glow;

  gl_FragColor = vec4(lit, 1.0);
}
