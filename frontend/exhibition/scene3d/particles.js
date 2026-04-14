// Phase 10 — Week 5 GPU particle field.
//
// Four particle systems for the Scene C dive-in:
//   1. bacteria     — warm glowing orbs (Points + additive blending)
//   2. mycorrhizae  — threading golden strands (LineSegments, pulsing alpha)
//   3. carbon       — pulsing amber spheres (small instanced meshes)
//   4. water        — sparkling cool streaks (Points with vertical drift)
//
// All systems live inside a single Group centered on the soil column
// interior so the dive-in camera sees them from the inside. Density /
// brightness / speed all scale with a single "vitality" input in 0..1
// — 1.0 = teeming healthy soil, 0.0 = dead teaspoon. The legibility rule
// is that healthy vs dead must be OBVIOUS without reading.
//
// No Nano Banana sprite sheets required for this system to render —
// we use built-in blended Points so the dive-in works with or without
// the texture library populated.

import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.163.0/build/three.module.js';

const BACTERIA_MAX = 800;
const CARBON_MAX = 120;
const MYCO_SEGMENTS = 80;
const WATER_MAX = 200;

function rand(a, b) { return a + Math.random() * (b - a); }

// ---------------------------------------------------------------------
// Bacteria — golden glowing points, drifting slowly, pulsing in brightness.

function makeBacteria() {
  const geo = new THREE.BufferGeometry();
  const positions = new Float32Array(BACTERIA_MAX * 3);
  const phases = new Float32Array(BACTERIA_MAX);
  const speeds = new Float32Array(BACTERIA_MAX * 3);

  for (let i = 0; i < BACTERIA_MAX; i++) {
    positions[i * 3 + 0] = rand(-1.1, 1.1);
    positions[i * 3 + 1] = rand(-1.1, 1.1);
    positions[i * 3 + 2] = rand(-1.1, 1.1);
    phases[i] = Math.random() * Math.PI * 2;
    speeds[i * 3 + 0] = rand(-0.04, 0.04);
    speeds[i * 3 + 1] = rand(-0.02, 0.02);
    speeds[i * 3 + 2] = rand(-0.04, 0.04);
  }

  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
  geo.setAttribute('aSpeed', new THREE.BufferAttribute(speeds, 3));

  const material = new THREE.ShaderMaterial({
    uniforms: {
      uTime:     { value: 0 },
      uVitality: { value: 1.0 },
    },
    vertexShader: /* glsl */ `
      uniform float uTime;
      uniform float uVitality;
      attribute float aPhase;
      varying float vPulse;
      void main() {
        vPulse = 0.5 + 0.5 * sin(uTime * 1.4 + aPhase);
        vec3 p = position;
        gl_Position = projectionMatrix * viewMatrix * modelMatrix * vec4(p, 1.0);
        float baseSize = 14.0;
        gl_PointSize = baseSize * mix(0.3, 1.0, uVitality) * (0.7 + vPulse * 0.6)
          * (300.0 / -(viewMatrix * modelMatrix * vec4(p, 1.0)).z);
      }
    `,
    fragmentShader: /* glsl */ `
      uniform float uVitality;
      varying float vPulse;
      void main() {
        vec2 uv = gl_PointCoord - 0.5;
        float d = length(uv);
        float core = smoothstep(0.5, 0.0, d);
        float halo = smoothstep(0.5, 0.15, d) * 0.5;
        float alpha = (core + halo) * mix(0.2, 1.0, uVitality) * (0.5 + vPulse * 0.5);
        vec3 warm = vec3(1.0, 0.78, 0.32);
        gl_FragColor = vec4(warm, alpha);
        if (alpha < 0.02) discard;
      }
    `,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const points = new THREE.Points(geo, material);
  points.userData.update = (dt, vitality) => {
    material.uniforms.uTime.value += dt;
    material.uniforms.uVitality.value = vitality;
    const pos = geo.attributes.position.array;
    const spd = geo.attributes.aSpeed.array;
    for (let i = 0; i < BACTERIA_MAX; i++) {
      pos[i * 3 + 0] += spd[i * 3 + 0] * dt * vitality;
      pos[i * 3 + 1] += spd[i * 3 + 1] * dt * vitality;
      pos[i * 3 + 2] += spd[i * 3 + 2] * dt * vitality;
      // Wrap inside the column volume.
      for (let k = 0; k < 3; k++) {
        const idx = i * 3 + k;
        if (pos[idx] > 1.15) pos[idx] = -1.15;
        if (pos[idx] < -1.15) pos[idx] = 1.15;
      }
    }
    geo.attributes.position.needsUpdate = true;
  };
  return points;
}

// ---------------------------------------------------------------------
// Mycorrhizae — fine golden line segments branching through space, with a
// pulse of light traveling along each one.

function makeMycorrhizae() {
  const positions = [];
  const colors = [];
  const phases = [];

  for (let i = 0; i < MYCO_SEGMENTS; i++) {
    const origin = new THREE.Vector3(rand(-1, 1), rand(-1, 1), rand(-1, 1));
    let prev = origin.clone();
    const hops = 5 + Math.floor(Math.random() * 4);
    for (let h = 0; h < hops; h++) {
      const dir = new THREE.Vector3(rand(-0.3, 0.3), rand(-0.3, 0.3), rand(-0.3, 0.3));
      const next = prev.clone().add(dir);
      positions.push(prev.x, prev.y, prev.z, next.x, next.y, next.z);
      colors.push(1.0, 0.72, 0.3, 1.0, 0.72, 0.3);
      const ph = Math.random() * Math.PI * 2;
      phases.push(ph, ph);
      prev = next;
    }
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  geo.setAttribute('aPhase', new THREE.Float32BufferAttribute(phases, 1));

  const material = new THREE.ShaderMaterial({
    uniforms: {
      uTime:     { value: 0 },
      uVitality: { value: 1.0 },
    },
    vertexShader: /* glsl */ `
      uniform float uTime;
      attribute float aPhase;
      attribute vec3 color;
      varying float vPulse;
      varying vec3 vColor;
      void main() {
        vColor = color;
        vPulse = 0.5 + 0.5 * sin(uTime * 1.8 + aPhase);
        gl_Position = projectionMatrix * viewMatrix * modelMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: /* glsl */ `
      uniform float uVitality;
      varying float vPulse;
      varying vec3 vColor;
      void main() {
        float alpha = mix(0.0, 0.9, uVitality) * (0.4 + vPulse * 0.6);
        gl_FragColor = vec4(vColor * (0.6 + vPulse * 0.6), alpha);
      }
    `,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const lines = new THREE.LineSegments(geo, material);
  lines.userData.update = (dt, vitality) => {
    material.uniforms.uTime.value += dt;
    material.uniforms.uVitality.value = vitality;
  };
  return lines;
}

// ---------------------------------------------------------------------
// Carbon — slow pulsing amber spheres, instanced for perf.

function makeCarbon() {
  const geo = new THREE.SphereGeometry(0.04, 12, 10);
  const material = new THREE.MeshBasicMaterial({
    color: new THREE.Color('#d89a3a'),
    transparent: true,
    opacity: 0.75,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const mesh = new THREE.InstancedMesh(geo, material, CARBON_MAX);
  const dummy = new THREE.Object3D();
  const positions = [];
  const phases = [];

  for (let i = 0; i < CARBON_MAX; i++) {
    const p = new THREE.Vector3(rand(-0.9, 0.9), rand(-0.9, 0.9), rand(-0.9, 0.9));
    positions.push(p);
    phases.push(Math.random() * Math.PI * 2);
    dummy.position.copy(p);
    dummy.scale.setScalar(1);
    dummy.updateMatrix();
    mesh.setMatrixAt(i, dummy.matrix);
  }
  mesh.instanceMatrix.needsUpdate = true;

  let t = 0;
  mesh.userData.update = (dt, vitality) => {
    t += dt;
    material.opacity = 0.15 + vitality * 0.65;
    for (let i = 0; i < CARBON_MAX; i++) {
      const pulse = 0.7 + 0.3 * Math.sin(t * 1.1 + phases[i]);
      dummy.position.copy(positions[i]);
      dummy.scale.setScalar(pulse * (0.4 + vitality * 0.6));
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
  };
  return mesh;
}

// ---------------------------------------------------------------------
// Water — cool silver-blue vertical streaks drifting downward.

function makeWater() {
  const geo = new THREE.BufferGeometry();
  const positions = new Float32Array(WATER_MAX * 3);
  const speeds = new Float32Array(WATER_MAX);
  for (let i = 0; i < WATER_MAX; i++) {
    positions[i * 3 + 0] = rand(-1, 1);
    positions[i * 3 + 1] = rand(-1, 1);
    positions[i * 3 + 2] = rand(-1, 1);
    speeds[i] = rand(0.1, 0.35);
  }
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('aSpeed', new THREE.BufferAttribute(speeds, 1));

  const material = new THREE.ShaderMaterial({
    uniforms: {
      uVitality: { value: 1.0 },
    },
    vertexShader: /* glsl */ `
      uniform float uVitality;
      void main() {
        vec3 p = position;
        gl_Position = projectionMatrix * viewMatrix * modelMatrix * vec4(p, 1.0);
        gl_PointSize = 6.0 * (0.3 + uVitality * 0.7)
          * (300.0 / -(viewMatrix * modelMatrix * vec4(p, 1.0)).z);
      }
    `,
    fragmentShader: /* glsl */ `
      uniform float uVitality;
      void main() {
        vec2 uv = gl_PointCoord - 0.5;
        float d = length(uv);
        float core = smoothstep(0.5, 0.0, d);
        vec3 cool = vec3(0.7, 0.85, 1.0);
        float alpha = core * mix(0.05, 0.7, uVitality);
        gl_FragColor = vec4(cool, alpha);
        if (alpha < 0.02) discard;
      }
    `,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const points = new THREE.Points(geo, material);
  points.userData.update = (dt, vitality) => {
    material.uniforms.uVitality.value = vitality;
    const pos = geo.attributes.position.array;
    const spd = geo.attributes.aSpeed.array;
    for (let i = 0; i < WATER_MAX; i++) {
      pos[i * 3 + 1] -= spd[i] * dt * vitality;
      if (pos[i * 3 + 1] < -1.2) pos[i * 3 + 1] = 1.2;
    }
    geo.attributes.position.needsUpdate = true;
  };
  return points;
}

// ---------------------------------------------------------------------

export class ParticleField {
  constructor(scene) {
    this.scene = scene;
    this.enabled = false;
    this.vitality = 1.0; // 0=dead, 1=teeming

    this.group = new THREE.Group();
    this.group.visible = false;
    this.bacteria = makeBacteria();
    this.myco = makeMycorrhizae();
    this.carbon = makeCarbon();
    this.water = makeWater();
    this.group.add(this.bacteria, this.myco, this.carbon, this.water);
    scene.add(this.group);
  }

  setEnabled(enabled) {
    this.enabled = enabled;
    this.group.visible = enabled;
  }

  // vitality: 0..1 — drives density, opacity, motion. Typically read from
  // the microbial living_soil_index from the Python sim output.
  setVitality(vitality) {
    this.vitality = Math.max(0, Math.min(1, vitality));
  }

  // Compatibility with Week 1 API.
  setDensity(d) {
    this.setVitality(d);
  }

  update(dt) {
    if (!this.enabled) return;
    this.bacteria.userData.update(dt, this.vitality);
    this.myco.userData.update(dt, this.vitality);
    this.carbon.userData.update(dt, this.vitality);
    this.water.userData.update(dt, this.vitality);
  }

  dispose() {
    this.scene.remove(this.group);
    this.bacteria.geometry.dispose();
    this.bacteria.material.dispose();
    this.myco.geometry.dispose();
    this.myco.material.dispose();
    this.carbon.geometry.dispose();
    this.carbon.material.dispose();
    this.water.geometry.dispose();
    this.water.material.dispose();
  }
}
