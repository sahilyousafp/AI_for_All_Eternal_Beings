/**
 * API calls, simulation runner, Chart.js rendering.
 * Requires Chart.js loaded via CDN (added dynamically).
 */

let simResult = null;
let charts    = {};

// ── Load Chart.js dynamically ─────────────────────────────────────────────

(function() {
  const s = document.createElement('script');
  s.src = 'https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js';
  document.head.appendChild(s);
})();

// ── Run simulation ────────────────────────────────────────────────────────

async function runSimulation() {
  if (!selectedPhilosophy || !selectedScenario) return;

  const years    = parseInt(document.getElementById('years-slider').value, 10);
  const ensemble = parseInt(document.getElementById('ensemble-select').value, 10);
  const btn      = document.getElementById('btn-run');
  const overlay  = document.getElementById('loading-overlay');
  const msg      = document.getElementById('loading-msg');

  btn.disabled = true;
  overlay.classList.add('visible');
  msg.textContent = `Running ${years}-year simulation (${ensemble} ensemble members)…`;

  try {
    const _base = window.location.origin.startsWith('http') ? window.location.origin : 'http://localhost:8000';
    const res = await fetch(`${_base}/api/exhibition/simulate`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        philosophy:       selectedPhilosophy,
        climate_scenario: selectedScenario,
        years:            years,
        n_ensemble:       ensemble,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    simResult = await res.json();
    renderResults(simResult);
    document.getElementById('sim-output').classList.add('visible');

  } catch (e) {
    alert(`Simulation failed: ${e.message}`);
    console.error(e);
  } finally {
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
    charts[id] = new Chart(ctx, {
      type: 'line',
      data: { labels: years, datasets: makeDataset(label, means, p10, p90, color) },
      options: baseOpts,
    });
  }

  mkChart('chart-soc',    'Mean SOC',     ts.total_soc_mean,    ts.total_soc_p10,    ts.total_soc_p90,    '#84CC16');
  mkChart('chart-erosion','Erosion',      ts.erosion_mean,      ts.erosion_p10,      ts.erosion_p90,      '#EF4444');
  mkChart('chart-bio',    'Biodiversity', ts.biodiversity_mean, ts.biodiversity_p10, ts.biodiversity_p90, '#06B6D4');
  mkChart('chart-canopy', 'Canopy Cover', ts.canopy_cover_mean, ts.canopy_cover_p10, ts.canopy_cover_p90, '#F59E0B');

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
}
