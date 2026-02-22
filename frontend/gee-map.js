/**
 * gee-map.js (v3 — Clean, standardized integration)
 * Handles predictions map and GEE visualization.
 */

let geeMap = null;
let currentLayer = null;

// ── Scientific colour ramps (dataset name → hex stops) ───────────────────────
const GEE_PALETTES = {
  Organic_Carbon:       ['#fff9c4','#f9a825','#e65100','#8d1b00','#3e0000'],
  Soil_pH:              ['#ce93d8','#8855bb','#5c1199','#37006b','#1a0040'],
  Bulk_Density:         ['#e0f7fa','#26c6da','#00838f','#005662','#001b22'],
  Sand_Content:         ['#fff8e1','#ffe082','#ffb300','#e65100','#bf360c'],
  Clay_Content:         ['#e8f5e9','#81c784','#2e7d32','#1b5e20','#0a2800'],
  Soil_Texture:         ['#ede7f6','#9575cd','#512da8','#311b92','#0d0030'],
  Precipitation_CHIRPS: ['#e3f2fd','#64b5f6','#1565c0','#0d47a1','#000f3c'],
  MODIS_Land_Cover:     null,   // handled by discrete MODIS_COLOURS below
  _soil:                ['#fff9c4','#ffcc02','#e65100','#6d1b00','#1a0000'],
};

// NOTE: MODIS_COLOURS is declared in local-data.js (loaded first) and accessible here.

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
function updatePredLegend(dataset, min, max, year = null, modelType = null) {
  const el = document.getElementById('predLegend');
  if (!el) return;

  const key   = (dataset || '').replace(/ /g, '_');
  const units = (typeof DATASET_UNITS !== 'undefined' ? DATASET_UNITS[key] : '') || '';
  const title = key.replace(/_/g, ' ');
  const yearTag   = year      ? `<span style="opacity:.5;font-size:9px"> · ${year}</span>` : '';
  const modelTag  = modelType ? `<span style="opacity:.5;font-size:9px"> · ${modelType.replace(/_/g,' ')}</span>` : '';

  if (key === 'MODIS_Land_Cover') {
    el.style.display = 'block';
    el.innerHTML = `
      <div style="font-weight:700;font-size:11px;margin-bottom:4px">Land Cover (MODIS)${yearTag}${modelTag}</div>
      <em style="font-size:10px;opacity:.7;display:block">Discrete IGBP land cover classes</em>
      <p style="font-size:9px;opacity:.5;margin-top:4px">Click map to identify class</p>`;
    return;
  }

  const ramp  = GEE_PALETTES[key] ?? GEE_PALETTES._soil;
  const stops = ramp.map((c, i) => `${c} ${(i/(ramp.length-1)*100).toFixed(0)}%`).join(', ');

  el.style.display = 'block';
  el.innerHTML = `
    <div style="font-weight:700;font-size:11px;margin-bottom:6px">${title}${units ? ` <span style="font-weight:400;opacity:.6">(${units})</span>` : ''}${yearTag}${modelTag}</div>
    <div style="height:8px;border-radius:4px;background:linear-gradient(to right,${stops});margin-bottom:6px;box-shadow:0 0 10px rgba(0,0,0,0.3)"></div>
    <div style="display:flex;justify-content:space-between;font-size:10px">
      <div><div style="font-weight:600">${min ?? '—'}</div><div style="opacity:.5;font-size:9px">Low</div></div>
      <div style="text-align:right"><div style="font-weight:600">${max ?? '—'}</div><div style="opacity:.5;font-size:9px">High</div></div>
    </div>
    <p style="font-size:9px;margin-top:5px;opacity:.5;text-align:center">2nd–98th %ile · click map for pixel value</p>`;
}

// ── Prediction overlay for ML-inferred years ──────────────────────────────────
let _predOverlay = null;

function _removePredOverlay() {
  if (_predOverlay) { _predOverlay.remove(); _predOverlay = null; }
}

function showPredictionOverlay(dataset, year, predValue, modelName, units, confLow, confHigh, testMetrics) {
  _removePredOverlay();
  const el = document.createElement('div');
  el.id = 'mlPredOverlay';
  el.style.cssText = [
    'position:absolute', 'top:16px', 'left:50%', 'transform:translateX(-50%)',
    'z-index:800', 'padding:12px 20px', 'border-radius:14px',
    'background:rgba(8,12,28,0.85)',
    'backdrop-filter:blur(20px) saturate(160%)',
    '-webkit-backdrop-filter:blur(20px) saturate(160%)',
    'border:1px solid rgba(251,191,36,0.35)',
    'box-shadow:0 4px 24px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.06)',
    'font-family:Inter,system-ui,sans-serif',
    'pointer-events:none', 'text-align:center', 'min-width:280px',
  ].join(';');

  const formatted = typeof predValue === 'number' ? predValue.toFixed(2) : '—';
  const ci = (confLow != null && confHigh != null)
    ? `<div style="font-size:10px;color:#94a3b8;margin-top:4px;">`
      + `90% CI: ${confLow.toFixed(2)} – ${confHigh.toFixed(2)} ${units}`
      + `</div>`
    : '';
  const metricsHtml = testMetrics
    ? `<div style="font-size:10px;color:#64748b;margin-top:5px;border-top:1px solid rgba(255,255,255,0.08);padding-top:5px;">`
      + `Test RMSE: <span style="color:#a78bfa">${testMetrics.test_rmse ?? '—'}</span>`
      + ` &nbsp;|&nbsp; R²: <span style="color:#a78bfa">${testMetrics.test_r2 != null ? testMetrics.test_r2.toFixed(3) : '—'}</span>`
      + ` &nbsp;|&nbsp; MAE: <span style="color:#a78bfa">${testMetrics.test_mae ?? '—'}</span>`
      + `</div>`
    : '';

  el.innerHTML = `
    <div style="font-size:11px;color:#fbbf24;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">
      🤖 ML Prediction — No real data for ${year}
    </div>
    <div style="font-size:20px;font-weight:700;color:#f1f5f9;">
      ${formatted} <span style="font-size:13px;color:#94a3b8;">${units}</span>
    </div>
    <div style="font-size:10px;color:#8b5cf6;margin-top:4px;">Model: ${modelName}</div>
    ${ci}
    ${metricsHtml}
    <div style="font-size:10px;color:#64748b;margin-top:6px;">${dataset} · Predicted for ${year}</div>
  `;

  const mapEl = document.getElementById('pred-map');
  if (mapEl) {
    mapEl.style.position = 'relative';
    mapEl.appendChild(el);
    _predOverlay = el;
  }
}

// ── Map initialisation ───────────────────────────────────────────────────────
let _currentGr = null;  // current georaster for pixel sampling

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

  // ── Pixel value popup on map click ──────────────────────────────────────────
  geeMap.on('click', function(e) {
    if (!_currentGr) return;
    const v = sampleGeoRaster(_currentGr, e.latlng.lat, e.latlng.lng);
    if (v === null) return;
    const key   = _currentGr._datasetKey || '';
    const units = (typeof DATASET_UNITS !== 'undefined' ? DATASET_UNITS[key] : '') || '';
    let valStr;
    if (key === 'MODIS_Land_Cover') {
      const cls = Math.round(v);
      valStr = `Class ${cls}: <strong>${(typeof MODIS_CLASS_NAMES !== 'undefined' ? MODIS_CLASS_NAMES[cls] : null) ?? 'Unknown'}</strong>`;
    } else {
      valStr = `<strong>${v.toFixed(3)}</strong> ${units}`;
    }
    const title = key.replace(/_/g, ' ') || 'Value';
    L.popup({ maxWidth: 220 })
      .setLatLng(e.latlng)
      .setContent(`<div style="font-size:12px"><em>${title}</em><br>${valStr}</div>`)
      .openOn(geeMap);
  });

  const datasetSelect = document.getElementById('datasetSelect');
  const firstDs = datasetSelect?.value || 'Organic Carbon (g/kg)';
  visualizeGEEDataset(firstDs);
}

async function visualizeGEEDataset(datasetName, year = null) {
  if (!geeMap) return;
  _removePredOverlay();
  const mapStatus = document.getElementById('pred-map-status');
  if (mapStatus) mapStatus.textContent = `Loading ${datasetName}${year ? ' · ' + year : ''}…`;

  if (currentLayer) { geeMap.removeLayer(currentLayer); currentLayer = null; }

  try {
    let url = `${API_BASE}/api/map?dataset=${encodeURIComponent(datasetName)}`;
    if (year) url += `&year=${year}`;

    const res  = await fetch(url);
    const data = await res.json();

    if (data.error) throw new Error(data.error);

    if (data.localUrl) {
      const tifRes = await fetch(`${API_BASE}${data.localUrl}`);
      if (!tifRes.ok) throw new Error(`HTTP ${tifRes.status}`);
      const gr  = await parseGeoraster(await tifRes.arrayBuffer());

      const { min, max } = computeDisplayRange(gr);
      const range = (max - min) || 1;
      const key   = data.internal_name || (datasetName || '').replace(/ /g, '_');
      gr._datasetKey = key;   // tag for pixel popup
      _currentGr = gr;

      if (key === 'MODIS_Land_Cover') {
        currentLayer = new GeoRasterLayer({
          georaster: gr, opacity: 0.85, resolution: 128,
          pixelValuesToColorFn: ([v]) => {
            if (v == null || isNaN(v) || v === gr.noDataValue) return null;
            return MODIS_COLOURS[Math.round(v) % MODIS_COLOURS.length] ?? '#555';
          }
        });
      } else {
        const ramp = GEE_PALETTES[key] ?? GEE_PALETTES._soil;
        currentLayer = new GeoRasterLayer({
          georaster: gr, opacity: 0.85, resolution: 128,
          pixelValuesToColorFn: ([v]) => {
            if (v == null || isNaN(v) || v === gr.noDataValue) return null;
            return lerp(ramp, (v - min) / range);
          }
        });
      }
      geeMap.addLayer(currentLayer);
      if (mapStatus) mapStatus.textContent = '';
      updatePredLegend(key, min.toFixed(1), max.toFixed(1));

    } else if (data.urlFormat) {
      currentLayer = L.tileLayer(data.urlFormat, { attribution: 'Google Earth Engine', maxZoom: 18 });
      geeMap.addLayer(currentLayer);
      if (mapStatus) mapStatus.textContent = '';
      updatePredLegend(data.internal_name || datasetName, data.min, data.max);
    }
  } catch (err) {
    if (mapStatus) mapStatus.textContent = `Error: ${err.message}`;
    console.error('Map Error:', err);
  }
}

/** Renders individual bands from local GeoTIFF in the Predictions tab */
async function visualizeLocalBand(fileInfo) {
  if (!geeMap) return;
  _removePredOverlay();
  const mapStatus = document.getElementById('pred-map-status');
  if (mapStatus) mapStatus.textContent = `Loading ${fileInfo.dataset}…`;

  if (currentLayer) { geeMap.removeLayer(currentLayer); currentLayer = null; }

  try {
    const res = await fetch(`${API_BASE}${fileInfo.url}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const gr  = await parseGeoraster(await res.arrayBuffer());

    const { min, max } = computeDisplayRange(gr);
    const range = (max - min) || 1;
    const key   = (fileInfo.dataset || '').replace(/ /g, '_');
    gr._datasetKey = key;   // tag for pixel popup
    _currentGr = gr;

    let layer;
    if (key === 'MODIS_Land_Cover') {
      layer = new GeoRasterLayer({
        georaster: gr, opacity: 0.85, resolution: 128,
        pixelValuesToColorFn: ([v]) => {
          if (v == null || isNaN(v) || v === gr.noDataValue) return null;
          return MODIS_COLOURS[Math.round(v) % MODIS_COLOURS.length] ?? '#555';
        }
      });
    } else {
      const ramp = GEE_PALETTES[key] ?? GEE_PALETTES._soil;
      layer = new GeoRasterLayer({
        georaster: gr, opacity: 0.85, resolution: 128,
        pixelValuesToColorFn: ([v]) => {
          if (v == null || isNaN(v) || v === gr.noDataValue) return null;
          return lerp(ramp, (v - min) / range);
        }
      });
    }

    currentLayer = layer;
    geeMap.addLayer(currentLayer);
    if (mapStatus) mapStatus.textContent = '';
    updatePredLegend(fileInfo.dataset, min.toFixed(1), max.toFixed(1));

  } catch (err) {
    if (mapStatus) mapStatus.textContent = 'Failed to load local TIF.';
    console.error('Local TIF Error:', err);
  }
}

// Global Exports
window.initGEEMap            = initGEEMap;
window.visualizeGEEDataset   = visualizeGEEDataset;
window.visualizeLocalBand    = visualizeLocalBand;
window.showPredictionOverlay = showPredictionOverlay;
window.visualizePredictedMap = visualizePredictedMap;
window.getMapBounds = () => geeMap?.getBounds();

// ── ML Spatial Prediction Map ────────────────────────────────────────────────
async function visualizePredictedMap(internalName, displayName, year, modelType) {
  if (!geeMap) return;
  _removePredOverlay();
  const mapStatus = document.getElementById('pred-map-status');
  if (mapStatus) mapStatus.textContent = `⏳ Generating ${modelType.replace(/_/g,' ')} prediction for ${year}…`;

  if (currentLayer) { geeMap.removeLayer(currentLayer); currentLayer = null; }

  try {
    const url = `${API_BASE}/api/predict-map?dataset=${encodeURIComponent(displayName)}&year=${year}&model_type=${encodeURIComponent(modelType)}`;
    const res = await fetch(url);
    if (!res.ok) {
      const body = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
      throw new Error(body.error || `HTTP ${res.status}`);
    }

    const gr = await parseGeoraster(await res.arrayBuffer());
    const key = internalName || (displayName || '').replace(/ /g, '_');
    gr._datasetKey = key;
    _currentGr = gr;

    const { min, max } = computeDisplayRange(gr);
    const range = (max - min) || 1;

    if (key === 'MODIS_Land_Cover') {
      currentLayer = new GeoRasterLayer({
        georaster: gr, opacity: 0.85, resolution: 128,
        pixelValuesToColorFn: ([v]) => {
          if (v == null || isNaN(v) || v === gr.noDataValue) return null;
          return MODIS_COLOURS[Math.round(v) % MODIS_COLOURS.length] ?? '#555';
        }
      });
    } else {
      const ramp = GEE_PALETTES[key] ?? GEE_PALETTES._soil;
      currentLayer = new GeoRasterLayer({
        georaster: gr, opacity: 0.85, resolution: 128,
        pixelValuesToColorFn: ([v]) => {
          if (v == null || isNaN(v) || v === gr.noDataValue) return null;
          return lerp(ramp, (v - min) / range);
        }
      });
    }

    geeMap.addLayer(currentLayer);
    if (mapStatus) mapStatus.textContent = `📡 ${modelType.replace(/_/g,' ')} prediction · ${year}`;
    updatePredLegend(key, min.toFixed(1), max.toFixed(1), year, modelType);

  } catch (err) {
    if (mapStatus) mapStatus.textContent = `⚠️ Prediction failed: ${err.message}`;
    console.error('Prediction map error:', err);
  }
}
