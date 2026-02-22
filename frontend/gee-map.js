/**
 * gee-map.js (v3 — Clean, standardized integration)
 * Handles predictions map and GEE visualization.
 */

let geeMap = null;
let currentLayer = null;

// ── Scientific colour ramps (dataset name → hex stops) ───────────────────────
const GEE_PALETTES = {
  Organic_Carbon:  ['#fff9c4','#f9a825','#e65100','#8d1b00','#3e0000'],
  Soil_pH:         ['#ce93d8','#8855bb','#5c1199','#37006b','#1a0040'],
  Bulk_Density:    ['#e0f7fa','#26c6da','#00838f','#005662','#001b22'],
  Sand_Content:    ['#fff8e1','#ffe082','#ffb300','#e65100','#bf360c'],
  Clay_Content:    ['#e8f5e9','#81c784','#2e7d32','#1b5e20','#0a2800'],
  _soil:           ['#fff9c4','#ffcc02','#e65100','#6d1b00','#1a0000'],
};

// ── Percentile display range ─────────────────────────────────────────────────
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

// ── Legend management ────────────────────────────────────────────────────────
function updatePredLegend(dataset, min, max) {
  const el = document.getElementById('predLegend');
  if (!el) return;
  
  const key  = (dataset || '').replace(/ /g, '_');
  const ramp = GEE_PALETTES[key] ?? GEE_PALETTES._soil;
  const stops = ramp.map((c, i) => `${c} ${(i/(ramp.length-1)*100).toFixed(0)}%`).join(', ');

  el.style.display = 'block';
  el.innerHTML = `
    <div style="font-weight:700;font-size:11px;margin-bottom:8px;color:var(--accent-primary);text-transform:uppercase;letter-spacing:1px">${dataset.replace(/_/g,' ')}</div>
    <div style="height:8px;border-radius:4px;background:linear-gradient(to right,${stops});margin-bottom:8px;box-shadow: 0 0 10px rgba(0,0,0,0.3)"></div>
    <div style="display:flex;justify-content:space-between;font-size:10px;font-weight:600;color:var(--text-muted)">
      <span>${min ?? '—'}</span><span>${max ?? '—'}</span>
    </div>`;
}

// ── Map initialisation ───────────────────────────────────────────────────────
function initGEEMap() {
  if (geeMap) return;

  geeMap = L.map('pred-map', { preferCanvas: true }).setView([41.39, 2.15], 11);
  window.geeMap = geeMap;

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '©OpenStreetMap contributors ©CARTO', maxZoom: 19,
  }).addTo(geeMap);

  // Reference bounding box
  L.rectangle([[41.25, 1.90], [41.55, 2.35]], {
    color: '#8888ff', weight: 1, fill: false, dashArray: '5 5', opacity: 0.5
  }).addTo(geeMap);

  const datasetSelect = document.getElementById('datasetSelect');
  const firstDs = datasetSelect?.value || 'Organic Carbon (g/kg)';
  visualizeGEEDataset(firstDs);
}

// ── Visualization logic ──────────────────────────────────────────────────────
async function visualizeGEEDataset(datasetName, year = null) {
  if (!geeMap) return;
  const mapStatus = document.getElementById('pred-map-status');
  if (mapStatus) mapStatus.textContent = `⏳ Loading live ${datasetName}…`;

  if (currentLayer) { geeMap.removeLayer(currentLayer); currentLayer = null; }

  try {
    let url = `http://localhost:8000/api/map?dataset=${encodeURIComponent(datasetName)}`;
    if (year) url += `&year=${year}`;

    const res  = await fetch(url);
    const data = await res.json();

    if (data.error) throw new Error(data.error);

    if (data.urlFormat) {
      currentLayer = L.tileLayer(data.urlFormat, { attribution: 'Google Earth Engine', maxZoom: 18 });
      geeMap.addLayer(currentLayer);
      if (mapStatus) mapStatus.textContent = `✅ ${datasetName}`;
      // Note: Live GEE legend uses metadata from backend if available
      updatePredLegend(datasetName, data.min, data.max);
    }
  } catch (err) {
    if (mapStatus) mapStatus.textContent = `❌ ${err.message}`;
    console.error('GEE Error:', err);
  }
}

/** Renders individual bands from local GeoTIFF in the Predictions tab */
async function visualizeLocalBand(fileInfo) {
  if (!geeMap) return;
  const mapStatus = document.getElementById('pred-map-status');
  if (mapStatus) mapStatus.textContent = `⏳ Loading ${fileInfo.dataset} high-res…`;

  if (currentLayer) { geeMap.removeLayer(currentLayer); currentLayer = null; }

  try {
    const res = await fetch(`http://127.0.0.1:8000${fileInfo.url}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const gr = await parseGeoraster(await res.arrayBuffer());

    const { min, max } = computeDisplayRange(gr);
    const range = (max - min) || 1;
    const key = (fileInfo.dataset || '').replace(/ /g, '_');
    const ramp = GEE_PALETTES[key] ?? GEE_PALETTES._soil;

    const layer = new GeoRasterLayer({
      georaster: gr, opacity: 0.85, resolution: 128,
      pixelValuesToColorFn: ([v]) => {
        if (v == null || isNaN(v) || v === gr.noDataValue) return null;
        return lerp(ramp, (v - min) / range);
      }
    });

    currentLayer = layer;
    geeMap.addLayer(currentLayer);
    if (mapStatus) mapStatus.textContent = `✅ Local: ${fileInfo.dataset} (${fileInfo.band})`;
    updatePredLegend(fileInfo.dataset, min.toFixed(1), max.toFixed(1));

  } catch (err) {
    if (mapStatus) mapStatus.textContent = '❌ Failed to load local TIF.';
    console.error('Local TIF Error:', err);
  }
}

// Global Exports
window.initGEEMap = initGEEMap;
window.visualizeGEEDataset = visualizeGEEDataset;
window.visualizeLocalBand = visualizeLocalBand;
window.getMapBounds = () => geeMap?.getBounds();
