// Phase 10 — procedural soil column.
//
// Builds a cylindrical cross-section mesh with the painterly shader and
// loads Nano Banana ground textures from the asset manifest. Supports
// smooth morphing between adjacent year buckets via a uMorph uniform,
// which the year-slider UI drives directly. Also supports setting a
// degradation level that's used for shader desaturation + fresnel ink
// sharpening, so healthy vs dying soil is visually obvious.

import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.163.0/build/three.module.js';

import { TextureLibrary } from './texture_library.js';

const PAINTERLY_VERT_URL = new URL('./shaders/painterly.vert', import.meta.url);
const PAINTERLY_FRAG_URL = new URL('./shaders/painterly.frag', import.meta.url);

const YEAR_BUCKETS = [0, 10, 20, 30, 40, 50];

// Rough runtime hint for the shader's degradation uniform. The real sim
// output drives this via setFromSimState(). This fallback keeps the
// column looking right even if no sim data has been loaded yet.
const DEGRADATION_HINTS = {
  do_nothing:   [0.30, 0.35, 0.40, 0.45, 0.50, 0.55],
  conventional: [0.25, 0.35, 0.45, 0.55, 0.65, 0.75],
  regenerative: [0.40, 0.30, 0.20, 0.15, 0.10, 0.05],
  rewild:       [0.50, 0.40, 0.30, 0.20, 0.15, 0.10],
  over_farm:    [0.30, 0.50, 0.65, 0.80, 0.90, 0.95],
};

export class SoilColumn {
  constructor(scene, options = {}) {
    this.scene = scene;
    this.position = options.position ?? new THREE.Vector3(0, 1, 0);
    this.radius = options.radius ?? 0.8;
    this.height = options.height ?? 2.5;
    this.rotate = options.rotate ?? true;

    this.state = {
      philosophy: options.philosophy ?? 'regenerative',
      ssp: options.ssp ?? 'ssp2',
      year: 0, // 0..50, continuous
    };

    this._textures = TextureLibrary.shared();
    this._shaderReady = false;
    this._time = 0;

    this._buildPlaceholderMesh();
    this._loadShadersAndUpgrade();
  }

  _buildPlaceholderMesh() {
    // Column body — open cylinder so the inside is visible during dive-in.
    const bodyGeo = new THREE.CylinderGeometry(
      this.radius, this.radius, this.height,
      64, 32, false,
    );

    const fallbackTex = this._textures.getFallback();
    this.material = new THREE.ShaderMaterial({
      uniforms: {
        uGroundTex:     { value: fallbackTex },
        uGroundTexNext: { value: fallbackTex },
        uMorph:         { value: 0.0 },
        uDegradation:   { value: 0.2 },
        uTime:          { value: 0.0 },
        uRimColor:      { value: new THREE.Color('#f5cd8a') },
        uRimIntensity:  { value: 0.8 },
        uLightDir:      { value: new THREE.Vector3(0.6, 0.8, 0.4).normalize() },
      },
      vertexShader: TextureLibrary.DEFAULT_VERT,
      fragmentShader: TextureLibrary.DEFAULT_FRAG,
      side: THREE.DoubleSide,
      transparent: false,
    });

    this.mesh = new THREE.Mesh(bodyGeo, this.material);
    this.mesh.position.copy(this.position);
    this.scene.add(this.mesh);

    // Cap disc for the ground surface — same shader, just a disc.
    const capGeo = new THREE.CircleGeometry(this.radius, 64);
    this.cap = new THREE.Mesh(capGeo, this.material);
    this.cap.rotation.x = -Math.PI / 2;
    this.cap.position.copy(this.position);
    this.cap.position.y += this.height / 2;
    this.scene.add(this.cap);

    // Bottom cap (dark — the "deep" end of the column).
    const bottomMat = new THREE.MeshBasicMaterial({ color: '#0a0806' });
    this.bottomCap = new THREE.Mesh(capGeo, bottomMat);
    this.bottomCap.rotation.x = Math.PI / 2;
    this.bottomCap.position.copy(this.position);
    this.bottomCap.position.y -= this.height / 2;
    this.scene.add(this.bottomCap);
  }

  async _loadShadersAndUpgrade() {
    try {
      const [vertSrc, fragSrc] = await Promise.all([
        fetch(PAINTERLY_VERT_URL).then((r) => r.text()),
        fetch(PAINTERLY_FRAG_URL).then((r) => r.text()),
      ]);
      this.material.vertexShader = vertSrc;
      this.material.fragmentShader = fragSrc;
      this.material.needsUpdate = true;
      this._shaderReady = true;
      this._refreshTextures();
    } catch (err) {
      console.warn('[SoilColumn] painterly shader load failed, using default', err);
    }
  }

  _refreshTextures() {
    const { philosophy, ssp, year } = this.state;
    const { idxA, idxB, morph } = this._yearToBucketIndices(year);
    const yearA = YEAR_BUCKETS[idxA];
    const yearB = YEAR_BUCKETS[idxB];

    const texA = this._textures.getGround(philosophy, ssp, yearA);
    const texB = this._textures.getGround(philosophy, ssp, yearB);

    if (texA) this.material.uniforms.uGroundTex.value = texA;
    if (texB) this.material.uniforms.uGroundTexNext.value = texB;
    this.material.uniforms.uMorph.value = morph;

    const hintRow = DEGRADATION_HINTS[philosophy] ?? DEGRADATION_HINTS.regenerative;
    const degA = hintRow[idxA];
    const degB = hintRow[idxB];
    this.material.uniforms.uDegradation.value = degA * (1 - morph) + degB * morph;
  }

  _yearToBucketIndices(year) {
    const clamped = Math.max(0, Math.min(50, year));
    const bucketSize = 10;
    const idxA = Math.min(
      YEAR_BUCKETS.length - 2,
      Math.floor(clamped / bucketSize),
    );
    const idxB = idxA + 1;
    const morph = (clamped - YEAR_BUCKETS[idxA]) / bucketSize;
    return { idxA, idxB, morph };
  }

  setState(partial) {
    Object.assign(this.state, partial);
    if (this._shaderReady) this._refreshTextures();
  }

  // Set degradation from real sim output (overrides the hint table).
  setFromSimState(simState) {
    // Expected shape from backend/exhibition_api.py scenario response:
    // { living_soil_index: 0..100, philosophy, ssp, year }
    if (!simState) return;
    if (typeof simState.living_soil_index === 'number') {
      // Map 0..100 (0=dead, 100=lush) to 1..0 degradation.
      const normalized = simState.living_soil_index / 100;
      this.material.uniforms.uDegradation.value = 1 - Math.max(0, Math.min(1, normalized));
    }
    if (simState.philosophy || simState.ssp || typeof simState.year === 'number') {
      this.setState({
        philosophy: simState.philosophy ?? this.state.philosophy,
        ssp: simState.ssp ?? this.state.ssp,
        year: simState.year ?? this.state.year,
      });
    }
  }

  update(dt) {
    this._time += dt;
    if (this.material && this.material.uniforms) {
      this.material.uniforms.uTime.value = this._time;
    }
    if (this.rotate) {
      this.mesh.rotation.y += dt * 0.12;
      this.cap.rotation.z += dt * 0.12;
      this.bottomCap.rotation.z += dt * 0.12;
    }
  }

  dispose() {
    this.scene.remove(this.mesh);
    this.scene.remove(this.cap);
    this.scene.remove(this.bottomCap);
    this.mesh.geometry.dispose();
    this.cap.geometry.dispose();
    this.bottomCap.geometry.dispose();
    this.material.dispose();
  }
}
