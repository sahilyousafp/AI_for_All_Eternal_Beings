// Phase 10 — Exhibition 3D scene3d layer entry point.
// Boots Three.js, creates a placeholder soil column, listens for mode
// changes (attract / focused / dive-in). Does NOT replace the existing
// 2D exhibition UI yet — it loads into a separate canvas that is hidden
// until the visitor enters the 3D experience. Week 1 scaffold only.

import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.163.0/build/three.module.js';
import { OrbitControls } from 'https://cdn.jsdelivr.net/npm/three@0.163.0/examples/jsm/controls/OrbitControls.js';

import { SoilColumn } from './soil_column.js';
import { ParticleField } from './particles.js';
import { CameraDirector } from './camera_director.js';
import { HandoffManager } from './handoff.js';

const CANVAS_ID = 'scene3d-canvas';

// "Neutral pose" — locked constants. Blender attract loop ends on
// exactly these values; Three.js scene enters Scene B at the same pose.
// When you change either, change both.
export const NEUTRAL_POSE = Object.freeze({
  cameraPos: new THREE.Vector3(0, 2.5, 6),
  cameraTarget: new THREE.Vector3(0, 1, 0),
  rimLightColor: new THREE.Color('#f5cd8a'),
  rimLightIntensity: 0.8,
});

export class Scene3d {
  constructor(canvas) {
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(canvas.clientWidth, canvas.clientHeight, false);

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color('#08090b');

    const aspect = canvas.clientWidth / Math.max(canvas.clientHeight, 1);
    this.camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 200);
    this.camera.position.copy(NEUTRAL_POSE.cameraPos);
    this.camera.lookAt(NEUTRAL_POSE.cameraTarget);

    // Dev-only orbit controls. Remove in Week 4 once camera director owns it.
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.target.copy(NEUTRAL_POSE.cameraTarget);
    this.controls.enableDamping = true;

    this.addLights();

    this.soilColumn = new SoilColumn(this.scene);
    this.particles = new ParticleField(this.scene);
    this.director = new CameraDirector(this.camera, this.controls);
    this.handoff = new HandoffManager(this);

    this.mode = 'idle';
    this.clock = new THREE.Clock();

    window.addEventListener('resize', () => this.onResize());
    this.onResize();
  }

  addLights() {
    const ambient = new THREE.AmbientLight('#2a2e38', 0.6);
    this.scene.add(ambient);

    const rim = new THREE.DirectionalLight(
      NEUTRAL_POSE.rimLightColor,
      NEUTRAL_POSE.rimLightIntensity,
    );
    rim.position.set(4, 6, 3);
    this.scene.add(rim);
    this.rimLight = rim;

    const fill = new THREE.DirectionalLight('#7fb3ff', 0.15);
    fill.position.set(-5, 2, -4);
    this.scene.add(fill);
  }

  onResize() {
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / Math.max(h, 1);
    this.camera.updateProjectionMatrix();
  }

  setMode(mode) {
    this.mode = mode;
    this.director.transitionTo(mode);
  }

  start() {
    const tick = () => {
      const dt = this.clock.getDelta();
      this.controls.update();
      this.soilColumn.update(dt);
      this.particles.update(dt);
      this.director.update(dt);
      this.renderer.render(this.scene, this.camera);
      this._raf = requestAnimationFrame(tick);
    };
    tick();
  }

  stop() {
    if (this._raf) cancelAnimationFrame(this._raf);
  }
}

export function mount() {
  const canvas = document.getElementById(CANVAS_ID);
  if (!canvas) {
    console.warn('[scene3d] canvas not found — skipping mount');
    return null;
  }
  const scene3d = new Scene3d(canvas);
  scene3d.start();
  window.__scene3d = scene3d; // debug handle
  return scene3d;
}

// Auto-mount when DOM is ready. Harmless if canvas is absent.
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mount);
} else {
  mount();
}
