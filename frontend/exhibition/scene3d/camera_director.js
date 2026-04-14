// Phase 10 — Week 5 camera director.
//
// Owns all camera movement: pose transitions between idle / focused /
// dive modes, subtle idle-time drift so the attract loop feels alive,
// and the 30-second idle timer that automatically resets to attract
// mode when nobody touches the screen.
//
// I'm NOT loading GSAP as an external dep — it's one more thing to cache
// on the exhibition laptop for a tween library that's easy to replace.
// Instead we use a tiny in-house tween that's specialized for Vector3
// lerps with ease-in-out cubic. Good enough, no network dep.

import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.163.0/build/three.module.js';

// Ease curves. Default is cubic in-out.
const EASE = {
  linear: (t) => t,
  cubicInOut: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  cubicOut:   (t) => 1 - Math.pow(1 - t, 3),
};

// Canonical poses for each mode. Idle pose matches NEUTRAL_POSE in
// main.js so the Blender handoff lands on the same frame.
export const POSES = {
  idle: {
    pos: new THREE.Vector3(0, 2.5, 6.0),
    target: new THREE.Vector3(0, 1.0, 0),
    duration: 1.4,
    ease: 'cubicInOut',
  },
  focused: {
    pos: new THREE.Vector3(0, 1.8, 4.2),
    target: new THREE.Vector3(0, 1.0, 0),
    duration: 1.2,
    ease: 'cubicInOut',
  },
  dive: {
    pos: new THREE.Vector3(0.0, 0.9, 0.1),
    target: new THREE.Vector3(0, 0.6, -0.8),
    duration: 1.6,
    ease: 'cubicOut',
  },
};

class Tween {
  constructor(fromPos, toPos, fromTarget, toTarget, duration, ease) {
    this.fromPos = fromPos.clone();
    this.toPos = toPos.clone();
    this.fromTarget = fromTarget.clone();
    this.toTarget = toTarget.clone();
    this.duration = Math.max(0.01, duration);
    this.ease = EASE[ease] ?? EASE.cubicInOut;
    this.elapsed = 0;
    this.onComplete = null;
    this.done = false;
  }

  step(dt, cameraPos, controlsTarget) {
    if (this.done) return;
    this.elapsed += dt;
    const t = Math.min(1, this.elapsed / this.duration);
    const e = this.ease(t);
    cameraPos.lerpVectors(this.fromPos, this.toPos, e);
    controlsTarget.lerpVectors(this.fromTarget, this.toTarget, e);
    if (t >= 1) {
      this.done = true;
      if (this.onComplete) this.onComplete();
    }
  }
}

export class CameraDirector {
  constructor(camera, controls) {
    this.camera = camera;
    this.controls = controls;
    this.currentMode = 'idle';
    this.tween = null;
    this.idleTimer = 0;
    this.idleTimeoutSec = 30; // back to attract loop after 30s inactivity
    this.onIdleReset = null;
    this._transitionListeners = new Set();
  }

  // Snap immediately to the neutral / idle pose without animating.
  // Used at boot and right after a video→real-time handoff so the
  // first frame matches the Blender render exactly.
  snapToIdle() {
    const pose = POSES.idle;
    this.camera.position.copy(pose.pos);
    if (this.controls) this.controls.target.copy(pose.target);
    else this.camera.lookAt(pose.target);
    this.currentMode = 'idle';
    this.tween = null;
    this.idleTimer = 0;
  }

  transitionTo(mode, opts = {}) {
    const pose = POSES[mode] ?? POSES.idle;
    const duration = opts.duration ?? pose.duration;
    const ease = opts.ease ?? pose.ease;
    const fromTarget = this.controls ? this.controls.target : pose.target;
    this.tween = new Tween(
      this.camera.position,
      pose.pos,
      fromTarget,
      pose.target,
      duration,
      ease,
    );
    this.tween.onComplete = () => {
      for (const fn of this._transitionListeners) fn(mode);
    };
    this.currentMode = mode;
    this.idleTimer = 0;
  }

  onTransitionComplete(fn) {
    this._transitionListeners.add(fn);
  }

  // Mark the scene as "not idle" — resets the timeout. Called on every
  // visitor touch / slider drag / click.
  poke() {
    this.idleTimer = 0;
  }

  update(dt) {
    if (this.tween && !this.tween.done) {
      this.tween.step(
        dt,
        this.camera.position,
        this.controls ? this.controls.target : new THREE.Vector3(),
      );
    } else {
      // Subtle idle drift so the attract loop camera feels alive even
      // when the tween has settled.
      if (this.currentMode === 'idle') {
        const t = performance.now() * 0.00015;
        const baseY = POSES.idle.pos.y;
        const baseX = POSES.idle.pos.x;
        this.camera.position.y = baseY + Math.sin(t * 0.8) * 0.08;
        this.camera.position.x = baseX + Math.sin(t * 0.5) * 0.12;
      }
    }

    // Idle timeout — reset to attract mode.
    if (this.currentMode !== 'idle') {
      this.idleTimer += dt;
      if (this.idleTimer >= this.idleTimeoutSec) {
        this.idleTimer = 0;
        this.transitionTo('idle');
        if (this.onIdleReset) this.onIdleReset();
      }
    }
  }
}
