// GPU particle field — Week 1 stub.
// Hosts bacteria / mycorrhizae / carbon / water particle systems used
// by the Scene C dive-in. Week 5 brings the real instanced geometry
// and Nano Banana sprite sheets.

import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.163.0/build/three.module.js';

export class ParticleField {
  constructor(scene) {
    this.scene = scene;
    this.enabled = false;
    this.density = 1.0; // scaled at runtime by microbial indicators
  }

  setEnabled(enabled) {
    this.enabled = enabled;
  }

  setDensity(density) {
    this.density = Math.max(0, Math.min(1, density));
  }

  update(dt) {
    // Stub — Week 5 implements the real particle update loop.
  }
}
