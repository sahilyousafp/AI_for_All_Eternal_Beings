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
    this._lastFactIdx = -1;

    this._build();
    this._loadLabels();
  }

  // Pick a fresh educational fact, avoiding immediate repeats so the
  // visitor doesn't see the same line twice in a row.
  _pickFact() {
    const facts = this.labels?.facts;
    if (!facts || facts.length === 0) return '';
    if (facts.length === 1) return facts[0];
    let idx;
    do {
      idx = Math.floor(Math.random() * facts.length);
    } while (idx === this._lastFactIdx);
    this._lastFactIdx = idx;
    return facts[idx];
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

    // Year slider — only thumb + tiny year readout, no caps label.
    this.sliderWrap = document.createElement('div');
    this.sliderWrap.className = 'scene3d-slider-wrap';
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
    this.sliderWrap.append(this.sliderInput, this.sliderYearEl);
    this.root.appendChild(this.sliderWrap);

    this.sliderInput.addEventListener('input', () => {
      const year = Number(this.sliderInput.value);
      this.sliderYearEl.textContent = `+${year}`;
      for (const fn of this._yearChangeListeners) fn(year);
    });

    // Attract-loop clock (years 2026 → 2076).
    this.clockEl = document.createElement('div');
    this.clockEl.className = 'scene3d-clock';
    this.root.appendChild(this.clockEl);

    // Back capsule — only visible in focused/dive. Always-on lifeline
    // for visitors who don't discover the tap-empty-space gesture.
    this.backEl = document.createElement('button');
    this.backEl.className = 'scene3d-back';
    this.backEl.type = 'button';
    const backArrow = document.createElement('span');
    backArrow.className = 'arrow';
    backArrow.textContent = '\u2190';
    const backWord = document.createElement('span');
    backWord.className = 'word';
    backWord.textContent = 'back';
    this.backEl.append(backArrow, backWord);
    this.backEl.setAttribute('aria-label', 'Back to attract loop');
    this.backEl.addEventListener('click', (e) => {
      e.stopPropagation();
      this.scene3d?.setMode('idle');
    });
    this.root.appendChild(this.backEl);

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
      /* Museum-caption style: title sits as a calm wall-label in the
         lower-left corner so the columns own the center of the frame.
         Max ~28ch keeps it as a single block of legible body text, not
         a billboard. */
      .scene3d-title {
        position: absolute; left: 4vw; bottom: 12vh;
        max-width: 30ch; text-align: left;
        font-family: 'Fraunces', serif;
        font-weight: 600; font-size: clamp(0.98rem, 1.25vw, 1.3rem);
        line-height: 1.35; letter-spacing: -0.005em;
        color: #f5f1e8;
        text-shadow: 0 2px 14px rgba(0,0,0,0.75);
        opacity: 0; transition: opacity 420ms ease;
      }
      .scene3d-title.visible { opacity: 1; }
      .scene3d-subtitle {
        position: absolute; left: 4vw; bottom: 7vh;
        max-width: 32ch; text-align: left;
        font-weight: 400; font-size: clamp(0.78rem, 0.9vw, 0.95rem);
        line-height: 1.45; color: #c8bfa6;
        text-shadow: 0 1px 10px rgba(0,0,0,0.7);
        opacity: 0; transition: opacity 420ms ease;
      }
      .scene3d-subtitle.visible { opacity: 1; }
      /* Tap-hint: small, off to the bottom-right, no scale-pulse. A gentle
         opacity breath is enough to draw the eye without shouting. */
      .scene3d-outro {
        position: absolute; right: 4vw; bottom: 5vh;
        font-weight: 600; font-size: clamp(0.7rem, 0.78vw, 0.85rem);
        letter-spacing: 0.14em; text-transform: uppercase;
        color: rgba(245, 205, 138, 0.78);
        text-shadow: 0 0 18px rgba(0,0,0,0.6);
        opacity: 0; transition: opacity 420ms ease;
      }
      .scene3d-outro.visible {
        animation: scene3d-breath 3.2s ease-in-out infinite;
      }
      @keyframes scene3d-breath {
        0%, 100% { opacity: 0.55; }
        50%      { opacity: 0.95; }
      }
      .scene3d-slider-wrap {
        position: absolute; right: 5vw; top: 50%; transform: translateY(-50%);
        display: flex; flex-direction: column; align-items: center; gap: 0.6rem;
        pointer-events: auto;
        opacity: 0; transition: opacity 420ms ease;
      }
      .scene3d-slider-wrap.visible { opacity: 1; }
      .scene3d-slider {
        writing-mode: vertical-lr;
        direction: rtl;
        -webkit-appearance: slider-vertical;
        appearance: slider-vertical;
        width: 2rem; height: 36vh;
        accent-color: #f5cd8a;
      }
      .scene3d-slider-year {
        font-family: 'Fraunces', serif;
        font-size: 0.95rem; font-weight: 500;
        font-variant-numeric: tabular-nums;
        color: rgba(245, 205, 138, 0.85);
        letter-spacing: 0.02em;
        text-shadow: 0 1px 8px rgba(0,0,0,0.7);
      }
      .scene3d-clock {
        position: absolute; top: 4vh; right: 4vw;
        font-family: 'Fraunces', serif;
        font-size: clamp(0.78rem, 0.95vw, 1rem);
        font-variant-numeric: tabular-nums;
        letter-spacing: 0.04em;
        color: rgba(230, 217, 184, 0.7);
        text-shadow: 0 1px 8px rgba(0,0,0,0.7);
        opacity: 0; transition: opacity 420ms ease;
      }
      .scene3d-clock.visible { opacity: 1; }
      /* Back capsule — ghost glyph at top-center. Materializes only in
         focused / dive modes. Backdrop blur lifts it off the soil
         columns without a hard background. */
      .scene3d-back {
        position: absolute; top: 4vh; left: 50%;
        transform: translateX(-50%) translateY(-4px);
        display: inline-flex; align-items: center; gap: 0.55rem;
        padding: 0.55rem 1.05rem 0.6rem;
        border-radius: 999px;
        background: rgba(12, 14, 18, 0.42);
        border: 1px solid rgba(245, 241, 232, 0.16);
        backdrop-filter: blur(10px) saturate(120%);
        -webkit-backdrop-filter: blur(10px) saturate(120%);
        color: rgba(245, 241, 232, 0.88);
        font-family: 'Fraunces', serif;
        font-size: 0.86rem;
        font-style: italic;
        letter-spacing: 0.01em;
        cursor: pointer;
        pointer-events: auto;
        opacity: 0; visibility: hidden;
        transition:
          opacity 420ms ease,
          transform 420ms cubic-bezier(0.2, 0.9, 0.3, 1),
          background 220ms ease,
          border-color 220ms ease;
      }
      .scene3d-back .arrow {
        font-family: 'Inter', system-ui, sans-serif;
        font-style: normal;
        font-size: 1rem;
        line-height: 1;
        transform: translateY(-1px);
        transition: transform 220ms cubic-bezier(0.2, 0.9, 0.3, 1);
      }
      .scene3d-back .word { line-height: 1; }
      .scene3d-back.visible {
        opacity: 1; visibility: visible;
        transform: translateX(-50%) translateY(0);
      }
      .scene3d-back:hover {
        background: rgba(20, 22, 28, 0.62);
        border-color: rgba(245, 205, 138, 0.55);
        color: #f5cd8a;
      }
      .scene3d-back:hover .arrow { transform: translate(-3px, -1px); }
      .scene3d-back:focus-visible {
        outline: 1px solid rgba(245, 205, 138, 0.7);
        outline-offset: 3px;
      }
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
      this.subtitleEl.textContent = this._pickFact();
      this.outroEl.textContent = attract_loop?.outro ?? '';
      this._show(this.titleEl, this.subtitleEl, this.outroEl, this.clockEl);
    } else if (mode === 'focused') {
      // Contemplative scene: ONE caption, a slider, and a back affordance.
      // No clock, no fact, no slider label — the column is the subject.
      const verb = philosophy_verbs?.[context.philosophy] ?? context.philosophy ?? '';
      const years = context.years ?? 0;
      const template = scene_b?.title_template ?? '{years} years of {philosophy_verb}';
      this.titleEl.textContent = template
        .replace('{philosophy_verb}', verb)
        .replace('{years}', String(years));
      this.sliderInput.value = String(years);
      this.sliderYearEl.textContent = `+${years}`;
      this._show(this.titleEl, this.sliderWrap, this.backEl);
    } else if (mode === 'dive') {
      const healthy = context.healthy !== false;
      const block = healthy ? scene_c_healthy : scene_c_dying;
      this.titleEl.textContent = block?.title ?? '';
      this.subtitleEl.textContent = block?.fact ?? '';
      this._show(this.titleEl, this.subtitleEl, this.backEl);
    }
  }

  setClock(year) {
    const base = 2026;
    this.clockEl.textContent = `${base} → ${base + year}`;
  }

  _hideAll() {
    for (const el of [this.titleEl, this.subtitleEl, this.outroEl, this.sliderWrap, this.clockEl, this.backEl]) {
      if (el) el.classList.remove('visible');
    }
  }

  _show(...els) {
    for (const el of els) el.classList.add('visible');
  }
}
