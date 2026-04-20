// Phase 10 — Exhibition 3D scene3d entry point.
//
// Boots the full scene3d layer:
//   - WebGL renderer and perspective camera at the locked NEUTRAL_POSE
//   - Lights matching the Blender render contract
//   - AttractScene (three diverging columns) OR single SoilColumn
//     depending on mode
//   - ParticleField for the dive-in
//   - CameraDirector for eased transitions and idle timeout
//   - HandoffManager for video ↔ real-time seam
//   - UiOverlay for all plain-language labels, slider, clock
//
// Visitor flow:
//   1. Canvas boots invisible, handoff plays Blender video on top.
//      If no video → AttractScene renders the same content real-time.
//   2. Visitor touch fires HandoffManager.startHandoff() → cross-dissolve.
//   3. Scene B: single column, year slider morphs it, label updates.
//   4. Tap column → Scene C dive-in, particles light up.
//   5. 30s idle → back to attract loop via CameraDirector.
//
// Everything here is vanilla ES modules. No framework. No bundler.
// Drops into the existing exhibition HTML without touching the 2D flow.

import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.163.0/build/three.module.js';

import { SoilColumn } from './soil_column.js';
import { ParticleField } from './particles.js';
import { CameraDirector, POSES } from './camera_director.js';
import { HandoffManager } from './handoff.js';
import { AttractScene } from './attract_scene.js';
import { UiOverlay } from './ui_overlay.js';

const CANVAS_ID = 'scene3d-canvas';

// "Neutral pose" — locked constants. Blender attract loop ends on
// exactly these values; Three.js scene enters Scene B at the same pose.
// Changing these means changing blender/render_attract_loop.py too.
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
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color('#08090b');
    this.scene.fog = new THREE.Fog('#08090b', 8, 20);

    const aspect = canvas.clientWidth / Math.max(canvas.clientHeight, 1);
    this.camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 200);
    this.camera.position.copy(NEUTRAL_POSE.cameraPos);
    this.camera.lookAt(NEUTRAL_POSE.cameraTarget);

    // Minimal controls surface for camera director to lerp against.
    this.controlsLike = { target: NEUTRAL_POSE.cameraTarget.clone() };

    this.addLights();

    // Scene graph pieces.
    this.attract = new AttractScene(this.scene);
    this.focused = null; // lazily created from the picked attract column
    this.particles = new ParticleField(this.scene);
    this.director = new CameraDirector(this.camera, this.controlsLike);
    this.handoff = new HandoffManager(this);
    this.ui = null; // set in mount() after canvas is in DOM

    this.state = 'idle'; // 'idle' | 'focused' | 'dive'
    this.currentPhilosophy = null;
    this.currentYear = 0;
    this.clock = new THREE.Clock();

    // Visitor touch / click handler for the whole canvas.
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.canvas.addEventListener('pointerdown', (e) => this.onPointerDown(e));

    window.addEventListener('resize', () => this.onResize());
    this.onResize();
  }

  addLights() {
    const ambient = new THREE.AmbientLight('#2a2e38', 0.6);
    this.scene.add(ambient);

    const rim = new THREE.DirectionalLight(
      NEUTRAL_POSE.rimLightColor,
      NEUTRAL_POSE.rimLightIntensity * 1.5,
    );
    rim.position.set(4, 6, 3);
    this.scene.add(rim);
    this.rimLight = rim;

    const fill = new THREE.DirectionalLight('#7fb3ff', 0.18);
    fill.position.set(-5, 2, -4);
    this.scene.add(fill);
  }

  onResize() {
    const w = this.canvas.clientWidth || window.innerWidth;
    const h = this.canvas.clientHeight || window.innerHeight;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / Math.max(h, 1);
    this.camera.updateProjectionMatrix();
  }

  // Mount the UI overlay. Called once after construction.
  attachOverlay(rootEl) {
    this.ui = new UiOverlay(rootEl, this);
    this.ui.onYearChange((year) => this.onYearChange(year));
  }

  // ----------------------------------------------------------------
  // Visitor input.

  onPointerDown(event) {
    const rect = this.canvas.getBoundingClientRect();
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, this.camera);

    if (this.state === 'idle') {
      // Tap MUST land on a column to advance. Falling through to a
      // default made every accidental tap pick "regenerative" — visitors
      // experienced this as random / sketchy navigation.
      const picked = this.attract.pickColumnFromRay(this.raycaster);
      if (picked) this.enterFocused(picked);
    } else if (this.state === 'focused') {
      // Tap ON the focused column → dive in.
      // Tap on empty space → back to attract loop. Gives visitors a
      // natural "tap subject = forward, tap empty = back" gesture
      // without adding a back button.
      const hits = this.focused
        ? this.raycaster.intersectObject(this.focused.mesh, false)
        : [];
      if (hits.length > 0) {
        this.enterDive();
      } else {
        this.setMode('idle');
      }
    } else if (this.state === 'dive') {
      // Tap anywhere → back out to focused.
      this.enterFocused(this.currentPhilosophy);
    }
    this.director.poke();
  }

  onYearChange(year) {
    this.currentYear = year;
    if (this.focused) this.focused.setState({ year });
    this.director.poke();
  }

  // ----------------------------------------------------------------
  // Mode transitions.

  async enterFocused(philosophy) {
    this.state = 'focused';
    this.currentPhilosophy = philosophy;

    // Start handoff if we're coming from attract video.
    if (this.handoff.state === 'attract-video' || this.handoff.state === 'attract-threejs') {
      await this.handoff.startHandoff(philosophy);
    }

    // Collapse attract to the chosen column, or create a dedicated one.
    if (!this.focused) {
      const chosen = this.attract.collapseTo(philosophy);
      this.focused = chosen ?? new SoilColumn(this.scene, { philosophy });
    } else {
      this.focused.setState({ philosophy });
    }
    this.focused.setState({ year: this.currentYear });

    this.particles.setEnabled(false);
    this.director.transitionTo('focused');
    this.ui?.setMode('focused', {
      philosophy,
      years: this.currentYear,
    });
  }

  enterDive() {
    this.state = 'dive';
    this.director.transitionTo('dive');
    this.particles.setEnabled(true);

    // Vitality from the column's current degradation uniform.
    const degradation = this.focused?.material.uniforms.uDegradation.value ?? 0.5;
    const vitality = 1 - degradation;
    this.particles.setVitality(vitality);

    this.ui?.setMode('dive', { healthy: vitality > 0.45 });
  }

  // Called by HandoffManager or the 30s idle timer.
  setMode(mode, context = {}) {
    if (mode === 'idle') {
      this.state = 'idle';
      this.attract.setActive(true);
      if (this.focused) {
        this.focused.dispose();
        this.focused = null;
      }
      this.attract.reset();
      this.particles.setEnabled(false);
      this.director.snapToIdle();
      this.ui?.setMode('idle');
    } else if (mode === 'focused') {
      this.enterFocused(context.philosophy ?? 'regenerative');
    } else if (mode === 'dive') {
      this.enterDive();
    }
  }

  // ----------------------------------------------------------------
  // Render loop.

  start() {
    this.director.onIdleReset = () => this.handoff.resetToAttract();

    const tick = () => {
      const dt = this.clock.getDelta();

      if (this.state === 'idle') {
        this.attract.update(dt);
        this.ui?.setClock(this.attract.getCurrentYear());
      } else if (this.focused) {
        this.focused.update(dt);
      }

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

// ----------------------------------------------------------------

export function mount() {
  const canvas = document.getElementById(CANVAS_ID);
  if (!canvas) {
    console.warn('[scene3d] canvas not found — skipping mount');
    return null;
  }

  const scene3d = new Scene3d(canvas);

  // Create a dedicated overlay root so our UI doesn't collide with
  // the existing 2D exhibition DOM.
  let overlayRoot = document.getElementById('scene3d-overlay');
  if (!overlayRoot) {
    overlayRoot = document.createElement('div');
    overlayRoot.id = 'scene3d-overlay';
    document.body.appendChild(overlayRoot);
  }
  scene3d.attachOverlay(overlayRoot);

  scene3d.handoff.init().then(() => {
    scene3d.setMode('idle');
  });

  scene3d.start();
  window.__scene3d = scene3d; // debug handle

  return scene3d;
}

// Auto-mount when the body gets the scene3d-active class (or is already
// set). Harmless if canvas is absent.
function tryMount() {
  if (document.body && document.body.classList.contains('scene3d-active')) {
    mount();
    return true;
  }
  return false;
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    if (!tryMount()) {
      // Watch for activation.
      const observer = new MutationObserver(() => {
        if (tryMount()) observer.disconnect();
      });
      observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    }
  });
} else if (!tryMount()) {
  const observer = new MutationObserver(() => {
    if (tryMount()) observer.disconnect();
  });
  observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
}
