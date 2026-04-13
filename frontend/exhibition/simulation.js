/**
 * API calls, simulation runner, Chart.js rendering.
 * Requires Chart.js loaded via CDN (added dynamically).
 */

let simResult    = null;
let charts       = {};
let selectedYears = 50;  // default: 2075
let _abortCtrl   = null;

// ── Cancel / dismiss loading overlay from anywhere ────────────────────────

function cancelSimulation() {
  if (_abortCtrl) { _abortCtrl.abort(); _abortCtrl = null; }
  const overlay = document.getElementById('loading-overlay');
  const btn     = document.getElementById('btn-run');
  if (overlay) overlay.classList.remove('visible');
  if (btn)     btn.disabled = false;
}

// ── Historical 1950 reference (Mediterranean soil literature baseline) ─────
const HISTORICAL_1950 = {
  total_soc:       18.2,   // g/kg — pre-intensive agriculture (EXHIBITION_SUBMISSION.md)
  erosion:         0.8,    // t/ha/yr — pre-deforestation estimate
  water_retention: 28.5,   // % volumetric — higher SOC → better water holding
  bulk_density:    1.12,   // t/m³ — less compaction before mechanised tillage
};

// ── Run simulation ────────────────────────────────────────────────────────

async function runSimulation() {
  if (!selectedPhilosophy || !selectedScenario) return;
  selectedYears = parseInt(document.getElementById('years-slider').value, 10);

  // 1950 — show static historical reference, no API call needed
  if (selectedYears === 'historical') {
    showHistoricalReference();
    return;
  }

  const years    = selectedYears;
  const ensemble = parseInt(document.getElementById('ensemble-select').value, 10);
  const btn      = document.getElementById('btn-run');
  const overlay  = document.getElementById('loading-overlay');
  const msg      = document.getElementById('loading-msg');
  const label    = years === 1 ? '2025 (current state)' : `2075 (${years}-year prediction)`;

  btn.disabled = true;
  overlay.classList.add('visible');
  msg.textContent = `Running simulation for ${label}…`;

  // Hard 30-second timeout — prevents overlay getting stuck forever
  _abortCtrl = new AbortController();
  const timeoutId = setTimeout(() => {
    if (_abortCtrl) _abortCtrl.abort();
  }, 30000);

  try {
    const res = await fetch(`${API_BASE}/api/exhibition/simulate`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      signal:  _abortCtrl.signal,
      body:    JSON.stringify({
        philosophy:       selectedPhilosophy,
        climate_scenario: selectedScenario,
        years:            years,
        n_ensemble:       ensemble,
      }),
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    simResult = await res.json();
    renderResults(simResult);
    document.getElementById('sim-output').classList.add('visible');

  } catch (e) {
    clearTimeout(timeoutId);
    if (e.name === 'AbortError') {
      msg.textContent = 'Timed out — is the backend running?';
    } else {
      console.error('Simulation error:', e);
      msg.textContent = `Error: ${e.message}`;
    }
    // Auto-dismiss after 3 seconds so user is never stuck
    setTimeout(cancelSimulation, 3000);
    return;
  } finally {
    _abortCtrl = null;
    btn.disabled = false;
    overlay.classList.remove('visible');
  }
}

// ── Render results ────────────────────────────────────────────────────────

function renderResults(data) {
  const ts    = data.timeseries;
  const years = data.years;

  // Chart defaults
  const baseOpts = {
    responsive: true,
    plugins:    { legend: { labels: { color: '#e8e8e8', font: { size: 11 } } } },
    scales: {
      x: { ticks: { color: '#888', maxTicksLimit: 8 }, grid: { color: '#2a2a2a' } },
      y: { ticks: { color: '#888' }, grid: { color: '#2a2a2a' } },
    },
  };

  function makeDataset(label, means, p10, p90, color) {
    return [
      {
        label,
        data:        means,
        borderColor: color,
        backgroundColor: color + '22',
        borderWidth: 2,
        fill: false,
        tension: 0.3,
        pointRadius: 0,
      },
      {
        label: '90th percentile',
        data:  p90,
        borderColor: color + '55',
        borderWidth: 1,
        borderDash: [4, 4],
        fill: '+1',
        backgroundColor: color + '11',
        pointRadius: 0,
      },
      {
        label: '10th percentile',
        data:  p10,
        borderColor: color + '55',
        borderWidth: 1,
        borderDash: [4, 4],
        fill: false,
        backgroundColor: color + '11',
        pointRadius: 0,
      },
    ];
  }

  // Destroy previous charts
  for (const c of Object.values(charts)) c.destroy();
  charts = {};

  function mkChart(id, label, means, p10, p90, color) {
    const ctx = document.getElementById(id)?.getContext('2d');
    if (!ctx) return;
    // Compute tight y-axis bounds from mean line only, with 20% padding
    const meanVals = means.filter(v => v != null && isFinite(v));
    const dataMin  = Math.min(...meanVals);
    const dataMax  = Math.max(...meanVals);
    const range    = dataMax - dataMin;
    const pad      = range > 0 ? range * 0.5 : dataMax * 0.05 || 0.1;
    const opts = JSON.parse(JSON.stringify(baseOpts));
    opts.scales.y.min = parseFloat((dataMin - pad).toFixed(3));
    opts.scales.y.max = parseFloat((dataMax  + pad).toFixed(3));
    charts[id] = new Chart(ctx, {
      type: 'line',
      data: { labels: years, datasets: makeDataset(label, means, p10, p90, color) },
      options: opts,
    });
  }

  mkChart('chart-soc',    'Organic Carbon (g/kg)',     ts.total_soc_mean,       ts.total_soc_p10,       ts.total_soc_p90,       '#84CC16');
  mkChart('chart-erosion','Erosion Rate (t/ha/yr)',    ts.erosion_mean,         ts.erosion_p10,         ts.erosion_p90,         '#EF4444');
  mkChart('chart-bio',    'Water Retention (%)',       ts.water_retention_mean, ts.water_retention_p10, ts.water_retention_p90, '#06B6D4');
  mkChart('chart-canopy', 'Bulk Density (t/m³)',       ts.bulk_density_mean,    ts.bulk_density_p10,    ts.bulk_density_p90,    '#F59E0B');

  // Confidence bar
  const conf  = data.confidence || {};
  const s     = conf.supported_years   || 30;
  const m     = conf.modeled_years     || 50;
  const sp    = conf.speculative_years || 0;
  const bar   = document.getElementById('conf-bar');
  bar.innerHTML = `
    <div class="conf-green"  style="flex:${s}"></div>
    <div class="conf-amber"  style="flex:${m}"></div>
    <div class="conf-red"    style="flex:${sp}"></div>
  `;
  document.getElementById('conf-label').textContent =
    `Green: calibrated data (${s}yr) · Amber: physics model (${m}yr) · Red: speculative (${sp}yr)`;

  // Events
  const evList = document.getElementById('events-list');
  evList.innerHTML = '';
  if (!data.events || data.events.length === 0) {
    evList.innerHTML = '<p style="color:var(--muted);font-size:0.8rem;">No major disturbance events.</p>';
  } else {
    for (const ev of data.events.slice(0, 30)) {
      const div = document.createElement('div');
      div.className = 'event-item';
      div.innerHTML = `
        <span class="yr">${ev.year}</span>
        <span class="severity-${ev.severity || 'low'}">${ev.type} (${ev.severity || 'n/a'})</span>
        <span style="color:var(--muted)">${ev.cells_affected || 0} cells</span>
      `;
      evList.appendChild(div);
    }
  }

  // Spatial SOC map
  renderSpatialMap('spatial-soc', data.spatial_final?.soc, '#84CC16');

  // Living Layer — microbial indicators panel
  renderLivingLayer(ts, years);
}

// ── Living Layer (microbial indicators) ───────────────────────────────────
//
// Renders the four microbial indicators + the composite Living Soil Index.
// Uses the LAST year of each timeseries as the "current state" tile values
// (the predicted endpoint), and draws an LSI trajectory chart with P10/P90
// envelope.
//
// References for the displayed indicators are documented in
// backend/soil_model/microbial_indicators.py.

function renderLivingLayer(ts, years) {
  const panel = document.getElementById('living-layer');
  if (!panel) return;
  if (!ts || !ts.living_soil_index_mean) {
    panel.style.display = 'none';
    return;
  }
  panel.style.display = 'block';

  const last = (arr) => arr[arr.length - 1];
  const fmt  = (v, d = 2) => (v == null || !isFinite(v)) ? '—' : Number(v).toFixed(d);

  const lsi  = last(ts.living_soil_index_mean);
  const mbc  = last(ts.mbc_mean);
  const fb   = last(ts.fb_ratio_mean);
  const qco2 = last(ts.qco2_mean);
  const amf  = last(ts.amf_pct_mean);

  document.getElementById('ll-lsi-val').textContent  = fmt(lsi, 0);
  document.getElementById('ll-mbc-val').textContent  = fmt(mbc, 2);
  document.getElementById('ll-fb-val').textContent   = fmt(fb,  2);
  document.getElementById('ll-qco2-val').textContent = fmt(qco2, 2);
  document.getElementById('ll-amf-val').textContent  = fmt(amf, 1);

  // Position the marker on the LSI strip
  const strip = document.getElementById('ll-lsi-strip');
  if (strip && lsi != null) {
    strip.style.setProperty('--ll-pos', `${Math.min(100, Math.max(0, lsi))}%`);
  }

  // LSI trajectory chart
  if (charts['chart-lsi']) charts['chart-lsi'].destroy();
  const ctx = document.getElementById('chart-lsi')?.getContext('2d');
  if (!ctx) return;
  charts['chart-lsi'] = new Chart(ctx, {
    type: 'line',
    data: {
      labels: years,
      datasets: [
        {
          label: 'Living Soil Index',
          data: ts.living_soil_index_mean,
          borderColor: '#a3e635',
          backgroundColor: '#a3e63522',
          borderWidth: 2.5,
          fill: false,
          tension: 0.3,
          pointRadius: 0,
        },
        {
          label: 'P90',
          data: ts.living_soil_index_p90,
          borderColor: '#a3e63555',
          borderWidth: 1,
          borderDash: [4, 4],
          fill: '+1',
          backgroundColor: '#a3e63511',
          pointRadius: 0,
        },
        {
          label: 'P10',
          data: ts.living_soil_index_p10,
          borderColor: '#a3e63555',
          borderWidth: 1,
          borderDash: [4, 4],
          fill: false,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#e8e8e8', font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: '#888', maxTicksLimit: 8 }, grid: { color: '#1f2f1f' } },
        y: {
          min: 0, max: 100,
          ticks: { color: '#888' }, grid: { color: '#1f2f1f' },
          title: { display: true, text: '0 = sterile · 100 = mature', color: '#6b7280', font: { size: 10 } },
        },
      },
    },
  });
}

// ── Historical 1950 reference display ────────────────────────────────────

function showHistoricalReference() {
  for (const c of Object.values(charts)) c.destroy();
  charts = {};

  document.getElementById('sim-output').classList.add('visible');

  const metrics = [
    { id: 'chart-soc',    label: 'Organic Carbon (g/kg)',  value: HISTORICAL_1950.total_soc,       color: '#84CC16' },
    { id: 'chart-erosion',label: 'Erosion Rate (t/ha/yr)', value: HISTORICAL_1950.erosion,         color: '#EF4444' },
    { id: 'chart-bio',    label: 'Water Retention (%)',     value: HISTORICAL_1950.water_retention, color: '#06B6D4' },
    { id: 'chart-canopy', label: 'Bulk Density (t/m³)',     value: HISTORICAL_1950.bulk_density,    color: '#F59E0B' },
  ];

  const baseOpts = {
    responsive: true,
    plugins: {
      legend: { labels: { color: '#e8e8e8', font: { size: 11 } } },
      tooltip: { enabled: false },
    },
    scales: {
      x: { ticks: { color: '#888' }, grid: { color: '#2a2a2a' } },
      y: { ticks: { color: '#888' }, grid: { color: '#2a2a2a' } },
    },
  };

  // Show a flat reference line across a 75-year window (1950 baseline)
  const refYears = Array.from({ length: 76 }, (_, i) => 1950 + i);

  for (const m of metrics) {
    const ctx = document.getElementById(m.id)?.getContext('2d');
    if (!ctx) continue;
    charts[m.id] = new Chart(ctx, {
      type: 'line',
      data: {
        labels: refYears,
        datasets: [{
          label: `${m.label} — 1950 baseline (estimated)`,
          data: refYears.map(() => m.value),
          borderColor: m.color,
          backgroundColor: m.color + '22',
          borderWidth: 2,
          borderDash: [6, 4],
          fill: false,
          pointRadius: 0,
        }],
      },
      options: baseOpts,
    });
  }
}
