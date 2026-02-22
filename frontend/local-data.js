/**
 * local-data.js  — Local GeoTIFF viewer for Barcelona GEE data
 * Clean, annotated, production-ready.
 */

const API_BASE = 'http://127.0.0.1:8000';

// ── State ────────────────────────────────────────────────────────────────────
let localMap = null;
let activeLayers = [];      // [{ key, layer, fileInfo, opacity, dotId }]
let predMapReady = false;
const tifCache = {};        // key → parsed georaster (avoid re-download)

// ── Scientific colour ramps (dataset name → hex stops) ───────────────────────
const PALETTES = {
  Organic_Carbon:       ['#fff9c4','#f9a825','#e65100','#8d1b00','#3e0000'],
  Soil_pH:              ['#f3e5f5','#ce93d8','#8e24aa','#4a148c','#1a0040'],
  Bulk_Density:         ['#e0f7fa','#26c6da','#00838f','#005662','#001b22'],
  Sand_Content:         ['#fff8e1','#ffe082','#ffb300','#e65100','#bf360c'],
  Clay_Content:         ['#e8f5e9','#81c784','#2e7d32','#1b5e20','#0a2800'],
  Soil_Texture:         ['#ede7f6','#9575cd','#512da8','#311b92','#0d0030'],
  Precipitation_CHIRPS: ['#e3f2fd','#64b5f6','#1565c0','#0d47a1','#000f3c'],
  MODIS_Land_Cover:     null, // handled by discrete map below
  // fallbacks per typology
  _soil:       ['#fff9c4','#ffcc02','#e65100','#6d1b00','#1a0000'],
  _climate:    ['#e3f2fd','#64b5f6','#1565c0','#0d47a1','#000f3c'],
  _land_cover: ['#f1f8e9','#aed581','#558b2f','#1b5e20','#071a00'],
};

// MODIS discrete class colours (classes 0–17)
const MODIS_COLOURS = [
  '#aec6cf','#047835','#0f6e0f','#75a100','#b5d900','#cab700',
  '#e0d060','#c7a020','#d67000','#d2a060','#e8e8c0','#d0e0a0',
  '#94b07c','#5d9c5c','#4c8c4c','#2266aa','#b4dcff','#f5f5f5',
];

const DEPTH_LABELS = {
  b0:'0–5 cm', b10:'10–30 cm', b30:'30–60 cm',
  b60:'60–100 cm', b100:'100–200 cm', b200:'200 cm+',
};

// ── Percentile display range ─────────────────────────────────────────────────
/**
 * Computes the 2nd–98th percentile of actual pixel values in a georaster band.
 * This prevents a single-color display when the local data range (e.g. OC 6–9)
 * is tiny compared to the theoretical uint8 range (1–255).
 */
function computeDisplayRange(gr) {
  const noData = gr.noDataValue;
  const vals = [];
  for (const row of (gr.values?.[0] ?? [])) {
    for (const v of row) {
      if (v != null && !isNaN(v) && v !== noData) vals.push(v);
    }
  }
  if (!vals.length) return { min: gr.mins[0], max: gr.maxs[0] };
  vals.sort((a, b) => a - b);
  return {
    min: vals[Math.floor(vals.length * 0.02)],
    max: vals[Math.floor(vals.length * 0.98)],
  };
}

// ── Colour helpers ───────────────────────────────────────────────────────────
function hexToRgb(hex) {
  const n = parseInt(hex.replace('#',''), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function lerp(ramp, t) {
  t = Math.max(0, Math.min(1, t));
  const idx = t * (ramp.length - 1);
  const lo  = Math.floor(idx), hi = Math.ceil(idx), f = idx - lo;
  const [r1,g1,b1] = hexToRgb(ramp[lo]);
  const [r2,g2,b2] = hexToRgb(ramp[hi]);
  return `rgb(${Math.round(r1+(r2-r1)*f)},${Math.round(g1+(g2-g1)*f)},${Math.round(b1+(b2-b1)*f)})`;
}

/** Normalise a dataset name to a palette key (always underscored) */
function dsKey(name) {
  return (name || '').replace(/ /g, '_');
}

/**
 * Returns the correct pixel-to-colour function for a given georaster.
 * Resolves the ramp fresh each call so cached georasters always get
 * the correct colours for their dataset.
 */
function makePixelFn(dataset, typology, georaster) {
  const noData = georaster.noDataValue;
  const key    = dsKey(dataset);

  if (key === 'MODIS_Land_Cover') {
    return ([v]) => {
      if (v == null || isNaN(v) || v === noData) return null;
      return MODIS_COLOURS[Math.round(v) % MODIS_COLOURS.length] ?? '#555';
    };
  }

  const ramp = PALETTES[key] ?? PALETTES[`_${typology}`] ?? PALETTES._soil;
  // Use percentile stretch so the full color ramp is used across the actual
  // data range in the tile (not the theoretical 1–255 uint8 range).
  const { min, max } = computeDisplayRange(georaster);
  const range = (max - min) || 1;
  return ([v]) => {
    if (v == null || isNaN(v) || v === noData) return null;
    return lerp(ramp, (v - min) / range);
  };
}

// ── Map legend ───────────────────────────────────────────────────────────────
function updateLegend(dataset, typology, georaster, displayMin, displayMax) {
  const el = document.getElementById('mapLegend');
  if (!el) return;

  const key  = dsKey(dataset);
  const ramp = PALETTES[key] ?? PALETTES[`_${typology}`] ?? PALETTES._soil;
  const { min: autoMin, max: autoMax } = computeDisplayRange(georaster);
  const min  = (displayMin ?? autoMin)?.toFixed(1) ?? '?';
  const max  = (displayMax ?? autoMax)?.toFixed(1) ?? '?';
  const title = (dataset || '').replace(/_/g, ' ');

  if (key === 'MODIS_Land_Cover' || !ramp) {
    el.innerHTML = `<strong>${title}</strong><em style="font-size:10px;opacity:.7">Discrete classes</em>`;
    el.style.display = 'block';
    return;
  }

  const stops = ramp.map((c, i) => `${c} ${(i/(ramp.length-1)*100).toFixed(0)}%`).join(', ');
  el.style.display = 'block';
  el.innerHTML = `
    <div style="font-weight:700;font-size:11px;margin-bottom:4px;letter-spacing:.4px">${title}</div>
    <div style="height:10px;border-radius:5px;background:linear-gradient(to right,${stops});margin-bottom:4px"></div>
    <div style="display:flex;justify-content:space-between;font-size:10px;opacity:.8">
      <span>${min}</span><span>${max}</span>
    </div>`;
}

function hideLegend() {
  const el = document.getElementById('mapLegend');
  if (el) el.style.display = 'none';
}

// ── Leaflet map initialisation (Barcelona) ───────────────────────────────────
function initLocalMap() {
  const BCN = [[41.25, 1.90], [41.55, 2.35]];

  localMap = L.map('local-map', { zoomControl: true, preferCanvas: true })
               .setView([41.39, 2.17], 11);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '©OpenStreetMap ©CARTO', maxZoom: 19,
  }).addTo(localMap);

  // Animated Barcelona bounding box
  const bbox = L.rectangle(BCN, {
    color: '#8888ff', weight: 2, fill: false, dashArray: '8 6', opacity: 0.8,
  }).addTo(localMap);

  // Pulse animation via setInterval on dashOffset
  let offset = 0;
  setInterval(() => {
    offset = (offset + 1) % 14;
    bbox.setStyle({ dashOffset: `${offset}` });
  }, 50);

  localMap.fitBounds(BCN);
}

// ── Layer ordering ───────────────────────────────────────────────────────────
function reorderLayers() {
  activeLayers.forEach(({ layer }) => layer.bringToFront());
}

// ── Layer Manager UI ─────────────────────────────────────────────────────────
function renderLayerManager() {
  const listEl   = document.getElementById('activeLayersList');
  const section  = document.getElementById('activeLayersSection');

  if (activeLayers.length === 0) {
    section.style.display = 'none';
    listEl.innerHTML = '';
    hideLegend();
    return;
  }
  section.style.display = 'block';

  // Show legend for topmost layer
  const top = activeLayers[activeLayers.length - 1];
  const cachedGr = tifCache[top.key];
  if (cachedGr) {
    const { min, max } = computeDisplayRange(cachedGr);
    updateLegend(top.fileInfo.dataset, top.fileInfo.typology, cachedGr, min, max);
  }

  listEl.innerHTML = '';
  [...activeLayers].reverse().forEach((item, revIdx) => {
    const realIdx = activeLayers.length - 1 - revIdx;
    const depth   = DEPTH_LABELS[item.fileInfo.band] || item.fileInfo.band;
    const name    = `${(item.fileInfo.dataset || '').replace(/_/g,' ')} (${depth})`;
    const ramp    = PALETTES[dsKey(item.fileInfo.dataset)] ?? PALETTES._soil;
    const swatches = ramp ? ramp.map(c =>
      `<span style="display:inline-block;width:8px;height:8px;background:${c};border-radius:2px"></span>`
    ).join('') : '';

    const card = document.createElement('div');
    card.className = 'active-layer-card';
    card.innerHTML = `
      <div class="active-layer-header">
        <span class="active-layer-name" title="${name}">
          <span style="display:inline-flex;gap:2px;margin-right:5px">${swatches}</span>${name}
        </span>
        <div class="layer-controls">
          <button class="layer-control-btn" onclick="moveLayerUp(${realIdx})" title="Move Up">↑</button>
          <button class="layer-control-btn" onclick="moveLayerDown(${realIdx})" title="Move Down">↓</button>
          <button class="layer-control-btn" onclick="removeLayer('${item.key}')" title="Remove" style="color:#ef4444">✕</button>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <input type="range" min="0" max="1" step="0.05" value="${item.opacity}"
               oninput="setLayerOpacity('${item.key}',this.value)"
               style="flex:1;accent-color:#8888ff">
        <span style="font-size:10px;color:#999;width:28px">${Math.round(item.opacity*100)}%</span>
      </div>`;
    listEl.appendChild(card);
  });
}

// Global handlers called from inline onclick
window.setLayerOpacity = (key, val) => {
  const item = activeLayers.find(i => i.key === key);
  if (!item) return;
  item.opacity = parseFloat(val);
  item.layer.setOpacity(item.opacity);
  renderLayerManager();
};

window.removeLayer = (key) => {
  const idx = activeLayers.findIndex(i => i.key === key);
  if (idx === -1) return;
  const { layer, dotId } = activeLayers[idx];
  localMap.removeLayer(layer);
  document.getElementById(dotId)?.setAttribute('class', 'band-status unloaded');
  document.querySelector(`[data-key="${key}"]`)?.classList.remove('active');
  activeLayers.splice(idx, 1);
  renderLayerManager();
  updateInfoBox(activeLayers.at(-1)?.fileInfo ?? null, activeLayers.at(-1) ? 'loaded' : 'idle');
};

window.moveLayerUp = (idx) => {
  if (idx >= activeLayers.length - 1) return;
  [activeLayers[idx], activeLayers[idx+1]] = [activeLayers[idx+1], activeLayers[idx]];
  reorderLayers(); renderLayerManager();
};

window.moveLayerDown = (idx) => {
  if (idx <= 0) return;
  [activeLayers[idx], activeLayers[idx-1]] = [activeLayers[idx-1], activeLayers[idx]];
  reorderLayers(); renderLayerManager();
};

// ── Load / toggle a GeoTIFF layer ────────────────────────────────────────────
async function toggleLayer(typology, fileInfo, itemEl) {
  const key   = `${typology}/${fileInfo.filename}`;
  const dotId = `dot-${fileInfo.filename.replace(/\W/g,'_')}`;

  // Already active → remove
  if (activeLayers.find(i => i.key === key)) {
    window.removeLayer(key);
    return;
  }

  itemEl.classList.add('active');
  document.getElementById(dotId)?.setAttribute('class', 'band-status loading');
  updateInfoBox(fileInfo, 'loading');

  try {
    // Use cache if available
    let gr = tifCache[key];
    if (!gr) {
      const res = await fetch(`${API_BASE}${fileInfo.url}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      gr = await parseGeoraster(await res.arrayBuffer());
      tifCache[key] = gr;
    }

    // Create layer — pixelFn is always computed fresh so each dataset gets
    // its own palette and its actual min/max from the georaster.
    const layer = new GeoRasterLayer({
      georaster: gr,
      opacity: 0.8,
      pixelValuesToColorFn: makePixelFn(fileInfo.dataset, typology, gr),
      resolution: 128,
    });

    layer.addTo(localMap);
    activeLayers.push({ key, layer, fileInfo: { ...fileInfo, typology }, opacity: 0.8, dotId });

    document.getElementById(dotId)?.setAttribute('class', 'band-status loaded');
    updateInfoBox(fileInfo, 'loaded', gr);
    renderLayerManager();
    reorderLayers();

  } catch (err) {
    console.error('GeoRaster load error:', err);
    document.getElementById(dotId)?.setAttribute('class', 'band-status unloaded');
    itemEl.classList.remove('active');
    updateInfoBox(fileInfo, 'error');
  }
}

// ── Info box ─────────────────────────────────────────────────────────────────
function updateInfoBox(fileInfo, state = 'idle', gr = null) {
  const box = document.getElementById('selectedBandInfo');
  if (!fileInfo) {
    box.innerHTML = activeLayers.length
      ? '<strong>Layers active</strong>Manage layers in the panel above.'
      : '<strong>Select a layer</strong>Click any band to toggle it on the map.';
    return;
  }
  const depth = DEPTH_LABELS[fileInfo.band] || fileInfo.band;
  const ds    = (fileInfo.dataset || '').replace(/_/g, ' ');
  if (state === 'loading') {
    box.innerHTML = `<strong>${ds} — ${depth}</strong>⏳ Fetching GeoTIFF…`;
  } else if (state === 'loaded' && gr) {
    const { min, max } = computeDisplayRange(gr);
    box.innerHTML = `<strong>${ds} — ${depth}</strong>`
      + `Display range: ${min.toFixed(2)} – ${max.toFixed(2)} (2nd–98th %ile)<br>`
      + `CRS: EPSG:${gr.projection ?? 4326} · NoData: ${gr.noDataValue ?? '—'}`;
  } else if (state === 'error') {
    box.innerHTML = `<strong style="color:#f87171">⚠️ Load failed</strong>Check the backend logs.`;
  }
}

// ── File tree builder ─────────────────────────────────────────────────────────
async function buildFileTree() {
  const treeEl = document.getElementById('localFileTree');
  treeEl.innerHTML = '<div style="padding:12px;font-size:12px;color:#aaa">Loading datasets…</div>';

  try {
    const res  = await fetch(`${API_BASE}/api/local-datasets`);
    if (!res.ok) throw new Error('API unreachable');
    const data = await res.json();

    const ICONS   = { soil:'🌱', climate:'🌧️', land_cover:'🗺️' };
    const COLOURS = { soil:'#c8902a', climate:'#2a82c8', land_cover:'#2ac862' };

    treeEl.innerHTML = '';
    for (const [typology, files] of Object.entries(data)) {
      if (!files.length) continue;

      const colour  = COLOURS[typology] || '#8888ff';
      const label   = typology.replace(/_/g,' ').replace(/\b\w/g, c => c.toUpperCase());

      const header  = document.createElement('div');
      header.className = 'typology-header';
      header.style.cssText = `border-left:3px solid ${colour};padding-left:10px`;
      header.innerHTML = `<span>${ICONS[typology]||'📄'} ${label}</span>`
                        + `<span style="font-size:10px;color:#999">${files.length} bands</span>`
                        + `<span class="arrow">▶</span>`;

      const bandList = document.createElement('div');
      bandList.className = 'band-list';

      // Group by dataset name
      const groups = {};
      files.forEach(f => (groups[f.dataset] = groups[f.dataset] || []).push(f));

      for (const [dsName, bands] of Object.entries(groups)) {
        const ramp  = PALETTES[dsKey(dsName)] ?? PALETTES[`_${typology}`] ?? [];
        const swatches = ramp.length
          ? `<span style="display:flex;gap:2px">${ramp.map(c =>
              `<span style="width:9px;height:9px;background:${c};border-radius:2px;display:inline-block"></span>`
            ).join('')}</span>`
          : '';

        const dsLabel = document.createElement('div');
        dsLabel.style.cssText
          = 'font-size:11px;font-weight:700;color:#666;padding:6px 8px 2px;display:flex;align-items:center;gap:6px';
        dsLabel.innerHTML = `${dsName.replace(/_/g,' ')} ${swatches}`;
        bandList.appendChild(dsLabel);

        bands.forEach(f => {
          const dotId = `dot-${f.filename.replace(/\W/g,'_')}`;
          const item  = document.createElement('div');
          item.className  = 'band-item';
          item.dataset.key = `${typology}/${f.filename}`;
          item.innerHTML  = `<span class="band-status unloaded" id="${dotId}"></span>`
                           + `${DEPTH_LABELS[f.band] || f.band}`;
          item.addEventListener('click', () => toggleLayer(typology, f, item));
          bandList.appendChild(item);
        });
      }

      header.addEventListener('click', () => {
        header.classList.toggle('open');
        bandList.classList.toggle('open');
      });

      const group = document.createElement('div');
      group.className = 'typology-group';
      group.appendChild(header);
      group.appendChild(bandList);
      treeEl.appendChild(group);
    }

    // Auto-open first group
    treeEl.querySelector('.typology-header')?.classList.add('open');
    treeEl.querySelector('.band-list')?.classList.add('open');

  } catch (err) {
    console.error(err);
    treeEl.innerHTML = '<div style="padding:8px;font-size:12px;color:#f87171">⚠️ Backend unreachable</div>';
  }
}

// ── Clear all layers ──────────────────────────────────────────────────────────
document.getElementById('clearLayersBtn').addEventListener('click', () => {
  activeLayers.forEach(({ layer }) => localMap.removeLayer(layer));
  document.querySelectorAll('.band-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.band-status').forEach(el => el.className = 'band-status unloaded');
  activeLayers = [];
  renderLayerManager();
  updateInfoBox(null);
});

// ── Tab switching ─────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');

    if (btn.dataset.tab === 'local' && localMap) {
      requestAnimationFrame(() => localMap.invalidateSize());
    }
    if (btn.dataset.tab === 'predictions') {
      if (!predMapReady) {
        predMapReady = true;
        window.initGEEMap?.();
      } else {
        requestAnimationFrame(() => window.geeMap?.invalidateSize());
      }
    }
  });
});

// ── Backend status badge ──────────────────────────────────────────────────────
async function checkBackend() {
  const badge = document.getElementById('backendBadge');
  try {
    const res = await fetch(`${API_BASE}/api/status`);
    if (!res.ok) throw new Error();
    badge.textContent = '● Backend online';
    badge.className   = 'backend-badge ok';
  } catch {
    badge.textContent = '● Backend offline';
    badge.className   = 'backend-badge err';
  }
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initLocalMap();
  buildFileTree();
  checkBackend();
});
