// Procedural soil column — Week 1 stub.
// Builds a cylindrical cross-section mesh driven by (philosophy, ssp, year).
// Reads ground textures from the Nano Banana manifest at runtime.
// Week 3-4: will gain the real painterly shader and morph-tween logic.

import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.163.0/build/three.module.js';

export class SoilColumn {
  constructor(scene) {
    this.scene = scene;
    this.state = {
      philosophy: 'regenerative',
      ssp: 'ssp2',
      year: 0,
    };

    const geometry = new THREE.CylinderGeometry(0.8, 0.8, 2.5, 48, 24, true);
    const placeholder = new THREE.MeshStandardMaterial({
      color: '#5a3a22',
      roughness: 0.9,
      metalness: 0.0,
      side: THREE.DoubleSide,
    });
    this.mesh = new THREE.Mesh(geometry, placeholder);
    this.mesh.position.y = 1.0;
    scene.add(this.mesh);

    // Cap the top so it doesn't look hollow from above.
    const capGeo = new THREE.CircleGeometry(0.8, 48);
    const capMat = new THREE.MeshStandardMaterial({
      color: '#3a2614',
      roughness: 0.95,
    });
    this.cap = new THREE.Mesh(capGeo, capMat);
    this.cap.rotation.x = -Math.PI / 2;
    this.cap.position.y = 2.25;
    scene.add(this.cap);
  }

  setState(partial) {
    Object.assign(this.state, partial);
    // Week 3-4: swap textures, update uniforms, tween between adjacent
    // year buckets. For now it's a placeholder so the scaffold runs.
  }

  update(dt) {
    // Slow rotation, attract-loop idle feel.
    this.mesh.rotation.y += dt * 0.15;
    this.cap.rotation.z += dt * 0.15;
  }
}
