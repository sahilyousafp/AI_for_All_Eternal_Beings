// Phase 10 — Nano Banana texture library.
//
// Loads textures lazily from frontend/exhibition/assets/textures/ using
// the filenames the Python factory generates. Keeps one shared instance
// so multiple soil columns (the three-column attract scene) share a
// single texture cache.
//
// If a texture is missing (e.g. the user hasn't run --mode batch yet)
// the library falls back to a procedurally-generated painterly dirt
// texture so the scene renders with a reasonable look even before any
// Nano Banana asset exists.

import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.163.0/build/three.module.js';

const TEXTURE_BASE = new URL('../assets/textures/', import.meta.url);
const YEAR_BUCKETS = [0, 10, 20, 30, 40, 50];

// Default inline shaders used by SoilColumn until the real painterly
// shader files finish loading. Keeps the pipeline valid on first frame.
const DEFAULT_VERT = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * viewMatrix * modelMatrix * vec4(position, 1.0);
  }
`;

const DEFAULT_FRAG = /* glsl */ `
  uniform sampler2D uGroundTex;
  varying vec2 vUv;
  void main() {
    gl_FragColor = texture2D(uGroundTex, vUv);
  }
`;

function makeFallbackGroundTexture() {
  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');

  // Warm gradient base — honey browns.
  const grad = ctx.createLinearGradient(0, 0, 0, size);
  grad.addColorStop(0, '#4a2c16');
  grad.addColorStop(0.5, '#6b3e1c');
  grad.addColorStop(1, '#2a1a0a');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);

  // Brush-stroke noise layer — warm and cool flecks.
  const warmColors = ['#a85c28', '#d8893f', '#704018', '#8a4a1c'];
  for (let i = 0; i < 800; i++) {
    ctx.fillStyle = warmColors[Math.floor(Math.random() * warmColors.length)];
    const x = Math.random() * size;
    const y = Math.random() * size;
    const r = 0.5 + Math.random() * 1.8;
    ctx.globalAlpha = 0.5 + Math.random() * 0.3;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1.0;

  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

export class TextureLibrary {
  static _shared = null;
  static DEFAULT_VERT = DEFAULT_VERT;
  static DEFAULT_FRAG = DEFAULT_FRAG;

  static shared() {
    if (!TextureLibrary._shared) TextureLibrary._shared = new TextureLibrary();
    return TextureLibrary._shared;
  }

  constructor() {
    this._loader = new THREE.TextureLoader();
    this._cache = new Map();
    this._fallback = makeFallbackGroundTexture();
  }

  getFallback() {
    return this._fallback;
  }

  _filenameFor(kind, params) {
    if (kind === 'ground') {
      const { philosophy, ssp, year } = params;
      const yearStr = String(year).padStart(2, '0');
      return `ground_${philosophy}_${ssp}_y${yearStr}.png`;
    }
    if (kind === 'sky') return `sky_${params.ssp}.png`;
    if (kind === 'root') return `roots_${params.density}_${params.depth}.png`;
    if (kind === 'particle') return `particle_${params.type}.png`;
    return null;
  }

  _load(filename) {
    if (this._cache.has(filename)) return this._cache.get(filename);
    const url = new URL(filename, TEXTURE_BASE);
    const tex = this._loader.load(
      url.toString(),
      (loaded) => {
        loaded.colorSpace = THREE.SRGBColorSpace;
        loaded.anisotropy = 8;
      },
      undefined,
      () => {
        // Missing file — caller will use fallback via the pre-seeded entry.
      },
    );
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    this._cache.set(filename, tex);
    return tex;
  }

  getGround(philosophy, ssp, year) {
    const yearBucket = YEAR_BUCKETS.reduce((best, y) =>
      Math.abs(y - year) < Math.abs(best - year) ? y : best,
    YEAR_BUCKETS[0]);
    const filename = this._filenameFor('ground', {
      philosophy, ssp, year: yearBucket,
    });
    if (!filename) return this._fallback;
    return this._load(filename);
  }

  getSky(ssp) {
    const filename = this._filenameFor('sky', { ssp });
    return this._load(filename);
  }

  getRoots(density = 'medium', depth = 'medium') {
    const filename = this._filenameFor('root', { density, depth });
    return this._load(filename);
  }

  getParticle(type) {
    const filename = this._filenameFor('particle', { type });
    return this._load(filename);
  }
}
