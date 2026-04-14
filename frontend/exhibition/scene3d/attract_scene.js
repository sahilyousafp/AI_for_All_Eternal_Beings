// Phase 10 — Scene A attract loop as a Three.js real-time fallback.
//
// Purpose: if the Blender pre-rendered attract_loop.mp4 isn't present
// (because the user chose to ship without Blender, or because the render
// job hasn't finished), this module renders the same "three futures
// diverging over 50 years" scene entirely in real-time. It uses three
// SoilColumn instances — one per chosen philosophy — and drives their
// year state from an internal clock so the columns visibly diverge.
//
// This is ALSO useful as the cheap path for any venue without a GPU
// laptop: it's the same codebase as Scene B, just laid out differently.
//
// The attract loop cycles through a 40-second timeline:
//   0.0 – 3.0s    Scene fades in, all three columns at year 0
//   3.0 – 33.0s   Year ticks from 0 to 50 across all three
//   33.0 – 38.0s  Held pose at year 50 — divergence at maximum
//   38.0 – 40.0s  Outro fade, label flips to "TOUCH A COLUMN TO SEE WHY"
//   loop.

import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.163.0/build/three.module.js';
import { SoilColumn } from './soil_column.js';

const LOOP_DURATION = 40.0;
const YEAR_START_T = 3.0;
const YEAR_END_T = 33.0;
const HOLD_END_T = 38.0;

// The three philosophies the attract loop compares. Order = left/center/right.
export const ATTRACT_PHILOSOPHIES = [
  { key: 'do_nothing',    offset: new THREE.Vector3(-3.0, 0, 0) },
  { key: 'regenerative',  offset: new THREE.Vector3( 0.0, 0, 0) },
  { key: 'over_farm',     offset: new THREE.Vector3( 3.0, 0, 0) },
];

export class AttractScene {
  constructor(scene, options = {}) {
    this.scene = scene;
    this.ssp = options.ssp ?? 'ssp2';
    this.group = new THREE.Group();
    scene.add(this.group);
    this.time = 0;
    this.active = false;

    this.columns = ATTRACT_PHILOSOPHIES.map(({ key, offset }) => {
      const col = new SoilColumn(this.group, {
        philosophy: key,
        ssp: this.ssp,
        position: new THREE.Vector3(0, 1, 0).add(offset),
        radius: 0.7,
        height: 2.3,
        rotate: false, // attract loop controls rotation uniformly
      });
      return { key, column: col, offset };
    });

    // Per-column label sprites would live here, but we use DOM labels
    // in the UI overlay for accessibility. Nothing to build in 3D.
  }

  setActive(active) {
    this.active = active;
    this.group.visible = active;
    if (active) this.time = 0;
  }

  // Returns current normalized year for the visitor-facing clock.
  getCurrentYear() {
    const t = this.time;
    if (t < YEAR_START_T) return 0;
    if (t < YEAR_END_T) {
      const p = (t - YEAR_START_T) / (YEAR_END_T - YEAR_START_T);
      return Math.round(p * 50);
    }
    return 50;
  }

  // Returns 'intro' | 'morphing' | 'held' | 'outro' for UI label sync.
  getPhase() {
    const t = this.time;
    if (t < YEAR_START_T) return 'intro';
    if (t < YEAR_END_T) return 'morphing';
    if (t < HOLD_END_T) return 'held';
    return 'outro';
  }

  update(dt) {
    if (!this.active) return;
    this.time = (this.time + dt) % LOOP_DURATION;
    const year = this.getCurrentYear();
    for (const { column } of this.columns) {
      column.setState({ year });
      // Each column still rotates individually, but synchronized.
      column.mesh.rotation.y += dt * 0.1;
      column.cap.rotation.z += dt * 0.1;
      column.bottomCap.rotation.z += dt * 0.1;
    }
  }

  // Which philosophy is the visitor pointing at? Used when a touch lands.
  // cameraRay is a THREE.Raycaster. Returns philosophy key or null.
  pickColumnFromRay(raycaster) {
    const meshes = this.columns.map((c) => c.column.mesh);
    const hits = raycaster.intersectObjects(meshes, false);
    if (hits.length === 0) return null;
    const hit = hits[0].object;
    const picked = this.columns.find((c) => c.column.mesh === hit);
    return picked ? picked.key : null;
  }

  // Collapse the attract loop — dissolve the two unpicked columns and
  // float the chosen one to center. Returns the chosen SoilColumn so
  // the caller can wire it into Scene B / Scene C.
  collapseTo(philosophyKey) {
    const chosen = this.columns.find((c) => c.key === philosophyKey);
    if (!chosen) return null;
    // Fade other columns by dropping their material opacity — but our
    // ShaderMaterial doesn't have a uniform for that yet, so simplest
    // reliable path is visibility toggle. Week 8 can add a proper
    // particle dissolve animation.
    for (const c of this.columns) {
      if (c.key !== philosophyKey) {
        c.column.mesh.visible = false;
        c.column.cap.visible = false;
        c.column.bottomCap.visible = false;
      }
    }
    // Move chosen to world origin smoothly — in Week 8 this becomes a
    // tween. For now snap the parent group.
    this.group.position.sub(chosen.offset);
    return chosen.column;
  }

  // Restore all three columns for next attract cycle.
  reset() {
    for (const c of this.columns) {
      c.column.mesh.visible = true;
      c.column.cap.visible = true;
      c.column.bottomCap.visible = true;
    }
    this.group.position.set(0, 0, 0);
    this.time = 0;
  }

  dispose() {
    for (const c of this.columns) c.column.dispose();
    this.scene.remove(this.group);
  }
}
