// Camera director — Week 1 stub.
// Owns scene transitions (attract → focused → dive-in). Week 5 wires in
// real GSAP timelines. For now it just snaps to mode-appropriate poses.

import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.163.0/build/three.module.js';

const POSES = {
  idle: {
    pos: new THREE.Vector3(0, 2.5, 6),
    target: new THREE.Vector3(0, 1, 0),
  },
  focused: {
    pos: new THREE.Vector3(0, 2.0, 4.5),
    target: new THREE.Vector3(0, 1, 0),
  },
  dive: {
    pos: new THREE.Vector3(0, 0.8, 0.4),
    target: new THREE.Vector3(0, 0.4, -0.5),
  },
};

export class CameraDirector {
  constructor(camera, controls) {
    this.camera = camera;
    this.controls = controls;
    this.currentMode = 'idle';
  }

  transitionTo(mode) {
    const pose = POSES[mode] ?? POSES.idle;
    this.camera.position.copy(pose.pos);
    if (this.controls) {
      this.controls.target.copy(pose.target);
    } else {
      this.camera.lookAt(pose.target);
    }
    this.currentMode = mode;
    // Week 5: replace snap with GSAP tween.
  }

  update(dt) {
    // Stub — Week 5 drives ongoing camera choreography.
  }
}
