// Phase 10 — DOM UI overlay for the 3D scene.
//
// Everything visitors read on top of the Three.js canvas lives here:
//   - the big plain-language title for the current scene
//   - the subtitle / secondary fact (Scene C uses this for the teaspoon line)
//   - the vertical year slider for Scene B
//   - the tap-to-start hint for the attract loop outro
//
// All text comes from assets/labels.json so copy edits never require
// touching JS. Legibility rule: every label must pass the 3-second test.

const LABELS_URL = new URL('../assets/labels.json', import.meta.url);

export class UiOverlay {
  constructor(root, scene3d) {
    this.root = root;
    this.scene3d = scene3d;
    this.labels = null;
    this._yearChangeListeners = new Set();

    this._build();
    this._loadLabels();
  }

  _build() {
    this.root.replaceChildren();
    this.root.classList.add('scene3d-overlay');

    // Title bar — the primary label for whatever scene is active.
    this.titleEl = document.createElement('div');
    this.titleEl.className = 'scene3d-title';
    this.root.appendChild(this.titleEl);

    // Subtitle / secondary fact.
    this.subtitleEl = document.createElement('div');
    this.subtitleEl.className = 'scene3d-subtitle';
    this.root.appendChild(this.subtitleEl);

    // Outro hint (attract loop only).
    this.outroEl = document.createElement('div');
    this.outroEl.className = 'scene3d-outro';
    this.root.appendChild(this.outroEl);

    // Year slider column.
    this.sliderWrap = document.createElement('div');
    this.sliderWrap.className = 'scene3d-slider-wrap';
    this.sliderLabel = document.createElement('div');
    this.sliderLabel.className = 'scene3d-slider-label';
    this.sliderInput = document.createElement('input');
    this.sliderInput.type = 'range';
    this.sliderInput.min = '0';
    this.sliderInput.max = '50';
    this.sliderInput.step = '1';
    this.sliderInput.value = '0';
    this.sliderInput.className = 'scene3d-slider';
    this.sliderInput.setAttribute('orient', 'vertical');
    this.sliderYearEl = document.createElement('div');
    this.sliderYearEl.className = 'scene3d-slider-year';
    this.sliderWrap.append(this.sliderLabel, this.sliderInput, this.sliderYearEl);
    this.root.appendChild(this.sliderWrap);

    this.sliderInput.addEventListener('input', () => {
      const year = Number(this.sliderInput.value);
      this.sliderYearEl.textContent = `+${year} years`;
      for (const fn of this._yearChangeListeners) fn(year);
    });

    // Attract-loop clock (years 2026 → 2076).
    this.clockEl = document.createElement('div');
    this.clockEl.className = 'scene3d-clock';
    this.root.appendChild(this.clockEl);

    this._injectStyles();
  }

  _injectStyles() {
    if (document.getElementById('scene3d-overlay-styles')) return;
    const style = document.createElement('style');
    style.id = 'scene3d-overlay-styles';
    style.textContent = `
      .scene3d-overlay {
        position: fixed; inset: 0; z-index: 110;
        pointer-events: none;
        font-family: 'Inter', system-ui, sans-serif;
        color: #f5f1e8;
        user-select: none;
      }
      .scene3d-title {
        position: absolute; top: 8vh; left: 50%; transform: translateX(-50%);
        max-width: 80vw; text-align: center;
        font-family: 'Fraunces', serif;
        font-weight: 700; font-size: clamp(1.8rem, 4vw, 3.4rem);
        line-height: 1.05; letter-spacing: -0.02em;
        text-shadow: 0 2px 20px rgba(0,0,0,0.9);
        opacity: 0; transition: opacity 420ms ease;
      }
      .scene3d-title.visible { opacity: 1; }
      .scene3d-subtitle {
        position: absolute; bottom: 14vh; left: 50%; transform: translateX(-50%);
        max-width: 70vw; text-align: center;
        font-weight: 500; font-size: clamp(1.1rem, 1.8vw, 1.6rem);
        line-height: 1.3; color: #e6d9b8;
        text-shadow: 0 2px 16px rgba(0,0,0,0.85);
        opacity: 0; transition: opacity 420ms ease;
      }
      .scene3d-subtitle.visible { opacity: 1; }
      .scene3d-outro {
        position: absolute; bottom: 8vh; left: 50%; transform: translateX(-50%);
        font-weight: 800; font-size: clamp(1rem, 1.5vw, 1.4rem);
        letter-spacing: 0.12em; text-transform: uppercase;
        color: #f5cd8a;
        text-shadow: 0 0 24px rgba(245, 205, 138, 0.4);
        opacity: 0; transition: opacity 420ms ease;
        animation: scene3d-pulse 2s ease-in-out infinite;
      }
      .scene3d-outro.visible { opacity: 1; }
      @keyframes scene3d-pulse {
        0%, 100% { transform: translateX(-50%) scale(1); }
        50% { transform: translateX(-50%) scale(1.04); }
      }
      .scene3d-slider-wrap {
        position: absolute; right: 5vw; top: 50%; transform: translateY(-50%);
        display: flex; flex-direction: column; align-items: center; gap: 0.8rem;
        pointer-events: auto;
        opacity: 0; transition: opacity 420ms ease;
      }
      .scene3d-slider-wrap.visible { opacity: 1; }
      .scene3d-slider-label {
        font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.1em;
        color: #b8ad95;
      }
      .scene3d-slider {
        -webkit-appearance: slider-vertical; appearance: slider-vertical;
        width: 2.5rem; height: 40vh;
      }
      .scene3d-slider-year {
        font-family: 'Fraunces', serif;
        font-size: 1.6rem; color: #f5cd8a;
        font-weight: 600;
      }
      .scene3d-clock {
        position: absolute; top: 8vh; right: 5vw;
        font-family: 'Fraunces', serif;
        font-size: clamp(1.2rem, 2vw, 1.8rem);
        color: #e6d9b8;
        opacity: 0; transition: opacity 420ms ease;
      }
      .scene3d-clock.visible { opacity: 1; }
    `;
    document.head.appendChild(style);
  }

  async _loadLabels() {
    try {
      const resp = await fetch(LABELS_URL);
      this.labels = await resp.json();
    } catch (err) {
      console.warn('[UiOverlay] failed to load labels.json', err);
      this.labels = {};
    }
  }

  // --- public API ------------------------------------------------------

  onYearChange(fn) {
    this._yearChangeListeners.add(fn);
  }

  setMode(mode, context = {}) {
    // Always start clean.
    this._hideAll();

    if (!this.labels) return;
    const { philosophy_verbs, attract_loop, scene_b, scene_c_healthy, scene_c_dying } = this.labels;

    if (mode === 'idle') {
      this.titleEl.textContent = attract_loop?.intro ?? '';
      this.outroEl.textContent = attract_loop?.outro ?? '';
      this._show(this.titleEl, this.outroEl, this.clockEl);
    } else if (mode === 'focused') {
      const verb = philosophy_verbs?.[context.philosophy] ?? context.philosophy ?? '';
      const years = context.years ?? 0;
      const template = scene_b?.title_template ?? 'THIS IS WHAT {philosophy_verb} DOES TO THE GROUND IN {years} YEARS';
      this.titleEl.textContent = template
        .replace('{philosophy_verb}', verb)
        .replace('{years}', String(years));
      this.subtitleEl.textContent = '';
      this.sliderLabel.textContent = scene_b?.slider_label ?? 'Drag to move through time';
      this.sliderInput.value = String(years);
      this.sliderYearEl.textContent = `+${years} years`;
      this._show(this.titleEl, this.sliderWrap);
    } else if (mode === 'dive') {
      const healthy = context.healthy !== false;
      const block = healthy ? scene_c_healthy : scene_c_dying;
      this.titleEl.textContent = block?.title ?? '';
      this.subtitleEl.textContent = block?.fact ?? '';
      this._show(this.titleEl, this.subtitleEl);
    }
  }

  setClock(year) {
    const base = 2026;
    this.clockEl.textContent = `${base} → ${base + year}`;
  }

  _hideAll() {
    for (const el of [this.titleEl, this.subtitleEl, this.outroEl, this.sliderWrap, this.clockEl]) {
      el.classList.remove('visible');
    }
  }

  _show(...els) {
    for (const el of els) el.classList.add('visible');
  }
}
