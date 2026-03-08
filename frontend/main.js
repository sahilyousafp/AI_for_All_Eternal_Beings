// API_BASE is declared in local-data.js as 'http://127.0.0.1:8000'
// We use it here to build the /api prefix without redeclaring.
const API = API_BASE + '/api';
const DEFAULT_COORDS = { lat: 41.39, lon: 2.17 }; // Barcelona

const yearSlider = document.getElementById('yearSlider');
const yearValue = document.getElementById('yearValue');
const datasetSelect = document.getElementById('datasetSelect');
const regionInfo = document.getElementById('regionInfo');
const datasetDescription = document.getElementById('datasetDescription');
const visualizeBtn = document.getElementById('visualizeBtn');
const predictBtn = document.getElementById('predictBtn');
const startYearInput = document.getElementById('startYear');
const endYearInput = document.getElementById('endYear');
const chartTabs = document.querySelectorAll('#tab-predictions .chart-tab');
const chartContainer = document.getElementById('chartContainer');
const statElements = {
  mean:   document.getElementById('statMean'),
  min:    document.getElementById('statMin'),
  max:    document.getElementById('statMax'),
  stdDev: document.getElementById('statStdDev'),
};

const localBandSelect = document.getElementById('localBandSelect');
const modelTypeSelect = document.getElementById('modelTypeSelect');
const localBandControl = document.getElementById('localBandControl');
const backendStatus = document.getElementById('backendBadge');

let activeChart = 'timeseries';
let datasetMetadata = [];
let localDatasets = {}; // To store local files from /api/local-datasets

document.addEventListener('DOMContentLoaded', () => {
  initDashboard();
});

function initDashboard() {
  yearValue.textContent = yearSlider.value;
  regionInfo.textContent = `Barcelona · ${DEFAULT_COORDS.lat.toFixed(2)}°N, ${DEFAULT_COORDS.lon.toFixed(2)}°E`;
  attachEventListeners();
  displayBackendStatus();
  _checkAndResumeTraining();
  Promise.all([refreshDatasetList(), fetchLocalDatasets(), _fetchDatasetYears()]).then(() => {
    updateStatistics();
    updateLocalBandVisibility();
    updateYearSliderForDataset(datasetSelect.value);
    if (window.visualizeGEEDataset) {
      window.visualizeGEEDataset(datasetSelect.value);
    }
    refreshModelStatus();
  });
}

// Expose for local-data.js tab-switch handler
window.showChartPanel = showChartPanel;
window.loadActiveChart = loadActiveChart;

function showChartPanel(datasetName) {
  const panel = document.getElementById('chartPanel');
  const badge = document.getElementById('chartDatasetBadge');
  if (!panel) return;
  panel.classList.remove('hidden');
  if (badge && datasetName) badge.textContent = datasetName;
}

function hideChartPanel() {
  const panel = document.getElementById('chartPanel');
  if (panel) panel.classList.add('hidden');
}

async function fetchLocalDatasets() {
  try {
    const response = await fetch(`${API}/local-datasets`);
    if (response.ok) {
      localDatasets = await response.json();
    }
  } catch (err) {
    console.error('Failed to fetch local datasets:', err);
  }
}

// ── Year slider: update range & label based on dataset's available years ──────

let _datasetYears = {};   // {internal_name: [years]}  — fetched once

async function _fetchDatasetYears() {
  try {
    const res = await fetch(`${API}/years`);
    if (res.ok) _datasetYears = await res.json();
  } catch { /* offline */ }
}

// Track whether the currently selected dataset has real temporal data.
let _currentDatasetIsTemporal = false;

function updateYearSliderForDataset(displayName) {
  const meta  = datasetMetadata.find(d => d.name === displayName);
  const group = document.getElementById('yearSliderGroup');
  if (!meta) return;

  const name  = meta.internal_name || '';
  const years = _datasetYears[name] || meta.available_years || [];

  if (years.length >= 2) {
    // Temporal dataset — show slider clamped to real data range + 10-year extrapolation
    _currentDatasetIsTemporal = true;
    if (group) group.style.display = '';
    const minY   = Math.min(...years);
    const maxY   = Math.max(...years);
    const extMax = maxY + 10;
    yearSlider.min   = minY;
    yearSlider.max   = extMax;
    yearSlider.value = Math.min(parseInt(yearSlider.value, 10) || maxY, extMax);
    yearValue.textContent = yearSlider.value;
    _updateYearLabel(minY, maxY, extMax);
  } else {
    // Static dataset (soil) — no valid temporal model, hide the year slider entirely
    _currentDatasetIsTemporal = false;
    if (group) group.style.display = 'none';
  }

  _updateModelTypeForDataset(_currentDatasetIsTemporal);
}

function _updateYearLabel(min, max, extMax) {
  const label = document.getElementById('yearSliderLabel');
  if (!label) return;
  label.textContent = `Real data: ${min}–${max}  ·  ML extrapolation: ${max + 1}–${extMax}`;
  label.style.color = 'var(--muted)';
}

/**
 * Show/hide temporal model options based on whether the dataset has temporal data.
 * Ridge/MLP temporal models are only valid for datasets with multi-year downloads.
 */
function _updateModelTypeForDataset(isTemporal) {
  if (!modelTypeSelect) return;
  modelTypeSelect.querySelectorAll('.temporal-only').forEach(opt => {
    opt.disabled = !isTemporal;
    opt.hidden   = !isTemporal;
  });
  // Revert to 'auto' if a now-hidden temporal option is selected
  const cur = modelTypeSelect.value;
  if (!isTemporal && (cur === 'temporal_ridge' || cur === 'temporal_mlp')) {
    modelTypeSelect.value = 'auto';
  }
}

// ── Infer and visualize: check if year has real data, else call ML ─────────────

async function inferAndVisualize(displayName, year) {
  if (!displayName || !_currentDatasetIsTemporal) return;
  const mapStatus = document.getElementById('pred-map-status');

  try {
    const res  = await fetch(`${API}/infer?dataset=${encodeURIComponent(displayName)}&year=${year}`);
    if (!res.ok) throw new Error('infer request failed');
    const data = await res.json();

    if (data.has_data) {
      // Real GeoTIFF exists for this year — visualize it directly
      if (window.visualizeGEEDataset) window.visualizeGEEDataset(displayName, year);
    } else if (data.supported === false) {
      // Backend has no valid model for this dataset — just show base map, no overlay
      if (window.visualizeGEEDataset) window.visualizeGEEDataset(displayName, null);
      if (mapStatus) mapStatus.textContent = '';
    } else {
      // No real data for this year but a trained ML model exists — show overlay
      const fallbackYear = data.available_years?.length
        ? Math.max(...data.available_years)
        : null;
      if (window.visualizeGEEDataset) {
        await window.visualizeGEEDataset(displayName, fallbackYear);
      }
      if (window.showPredictionOverlay) {
        window.showPredictionOverlay(
          displayName,
          year,
          data.predicted_value,
          data.model || 'ML model',
          data.units  || '',
          data.confidence_low,
          data.confidence_high,
          data.test_metrics || null,
        );
      }
      if (mapStatus) mapStatus.textContent = '';
    }
  } catch (err) {
    console.error('inferAndVisualize:', err);
    if (window.visualizeGEEDataset) window.visualizeGEEDataset(displayName, null);
  }
}

function updateLocalBandVisibility() {
  if (!datasetSelect.value) return;
  const currentDs = datasetSelect.value.replace(/ /g, '_').split('(')[0].trim();
  
  // Try to find matching typology group
  let matchingFiles = [];
  for (const typology in localDatasets) {
    const matches = localDatasets[typology].filter(f => f.dataset === currentDs);
    if (matches.length > 0) {
      matchingFiles = matches;
      break;
    }
  }

  if (matchingFiles.length > 0) {
    localBandControl.style.display = 'block';
    localBandSelect.innerHTML = '<option value="live">Local (Default)</option>';
    matchingFiles.forEach(f => {
      const option = document.createElement('option');
      option.value = JSON.stringify(f);
      const depthLabels = { b0:'0–5cm', b10:'10–30cm', b30:'30–60cm', b60:'60–100cm', b100:'100–200cm', b200:'200cm+' };
      option.textContent = `${depthLabels[f.band] || f.band} (Local 250m)`;
      localBandSelect.appendChild(option);
    });
  } else {
    localBandControl.style.display = 'none';
    localBandSelect.value = 'live';
  }
}

function attachEventListeners() {
  yearSlider.addEventListener('input', (event) => {
    yearValue.textContent = event.target.value;
    if (localBandSelect.value === 'live') {
      inferAndVisualize(datasetSelect.value, parseInt(event.target.value, 10));
    }
  });

  datasetSelect.addEventListener('change', () => {
    updateDatasetDescription(datasetSelect.value);
    updateLocalBandVisibility();
    updateStatistics();
    updateYearSliderForDataset(datasetSelect.value);
    showChartPanel(datasetSelect.value);
    loadActiveChart();
    if (window.visualizeGEEDataset) {
      window.visualizeGEEDataset(datasetSelect.value);
    }
  });

  visualizeBtn.addEventListener('click', () => {
    const localVal  = localBandSelect.value;
    const modelType = modelTypeSelect?.value || 'auto';

    if (localVal !== 'live') {
      // Explicit local band selected — show that band
      const fileInfo = JSON.parse(localVal);
      if (window.visualizeLocalBand) window.visualizeLocalBand(fileInfo);
    } else if (modelType !== 'auto') {
      // Explicit ML model type selected → run spatial prediction
      const selected = datasetMetadata.find(d => d.name === datasetSelect.value);
      const internalName = selected?.internal_name || '';
      if (window.visualizePredictedMap) {
        window.visualizePredictedMap(internalName, datasetSelect.value, parseInt(yearSlider.value, 10), modelType);
      }
    } else if (_currentDatasetIsTemporal) {
      // Auto: use real data if available, otherwise ML overlay
      inferAndVisualize(datasetSelect.value, parseInt(yearSlider.value, 10));
    } else {
      // Static dataset (soil) — just show the base raster, no year inference
      if (window.visualizeGEEDataset) window.visualizeGEEDataset(datasetSelect.value);
    }
    updateStatistics();
  });

  predictBtn.addEventListener('click', () => {
    loadPrediction();
  });

  const trainBtn = document.getElementById('trainBtn');
  if (trainBtn) trainBtn.addEventListener('click', () => trainModels());

  chartTabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      chartTabs.forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      activeChart = tab.dataset.tab || 'timeseries';
      loadActiveChart();
    });
  });
}

async function displayBackendStatus() {
  const backendStatus = document.getElementById('backendBadge');
  try {
    const response = await fetch(`${API}/status`);
    if (!response.ok) throw new Error('backend status request failed');
    const payload = await response.json();
    backendStatus.textContent = `Backend online · ${payload.timestamp || 'ready'}`;
  } catch (error) {
    console.error(error);
    backendStatus.textContent = 'Backend offline. Run `uvicorn backend.app:app --reload`';
  }
}

async function refreshDatasetList() {
  datasetSelect.innerHTML = '<option>Loading datasets...</option>';
  try {
    const response = await fetch(`${API}/datasets`);
    if (!response.ok) throw new Error('Datasets request failed');
    const payload = await response.json();
    datasetMetadata = payload.items || [];
  } catch (error) {
    console.error(error);
    datasetMetadata = [];
  }
  populateDatasetOptions();
}

function populateDatasetOptions() {
  datasetSelect.innerHTML = '';
  if (datasetMetadata.length === 0) {
    const fallback = ['Organic Carbon (g/kg)', 'Soil pH (H₂O)', 'Bulk Density (tonnes/m³)', 'Sand Content (%)', 'Clay Content (%)', 'Soil Texture Class'];
    fallback.forEach((label) => {
      const option = document.createElement('option');
      option.value = label;
      option.textContent = label;
      datasetSelect.appendChild(option);
    });
    datasetDescription.textContent = 'Backend offline. Using fallback dataset list.';
  } else {
    datasetMetadata.forEach((dataset) => {
      const option = document.createElement('option');
      option.value = dataset.name;
      option.textContent = dataset.name;
      datasetSelect.appendChild(option);
    });
    updateDatasetDescription(datasetSelect.value);
  }
}

function updateDatasetDescription(datasetName) {
  const metadata = datasetMetadata.find((item) => item.name === datasetName);
  if (metadata) {
    const bandCount = metadata.local_files ? Object.keys(metadata.local_files).length : 0;
    const bandInfo = bandCount > 0 ? ` · ${bandCount} local band${bandCount > 1 ? 's' : ''}` : '';
    datasetDescription.textContent = `${metadata.description}${bandInfo} (${metadata.typology || 'local'})`;
  } else {
    datasetDescription.textContent = 'Dataset metadata will appear once the backend responds.';
  }
}

async function updateStatistics() {
  const dataset = datasetSelect.value;
  if (!dataset) return;
  const year = parseInt(yearSlider.value, 10);
  setStatValues('Loading...');
  try {
    const response = await fetch(
      `${API}/statistics?dataset=${encodeURIComponent(dataset)}&lat=${DEFAULT_COORDS.lat}&lon=${DEFAULT_COORDS.lon}&year=${year}`
    );
    if (!response.ok) throw new Error('Statistics request failed');
    const payload = await response.json();
    const { mean, min, max, stdDev } = payload.statistics || {};
    statElements.mean.textContent = formatStat(mean);
    statElements.min.textContent = formatStat(min);
    statElements.max.textContent = formatStat(max);
    statElements.stdDev.textContent = formatStat(stdDev);
  } catch (error) {
    console.error(error);
    setStatValues('--');
  }
}

function setStatValues(value) {
  Object.values(statElements).forEach((element) => {
    element.textContent = value;
  });
}

function formatStat(value) {
  if (typeof value !== 'number') return '--';
  return value.toFixed(2);
}

// ── Chart.js instance management ─────────────────────────────────────────────
let _chartInstance = null;

function _destroyChart() {
  if (_chartInstance) { _chartInstance.destroy(); _chartInstance = null; }
}

const CHART_DEFAULTS = {
  color: '#f1f5f9',
  font: { family: 'Inter, sans-serif', size: 11 },
  grid: { color: 'rgba(255,255,255,0.06)' },
  ticks: { color: '#94a3b8' },
};

function _baseOptions(title) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
      title: { display: !!title, text: title, color: '#f1f5f9', font: { size: 13, weight: '600' } },
    },
    scales: {
      x: { grid: CHART_DEFAULTS.grid, ticks: CHART_DEFAULTS.ticks },
      y: { grid: CHART_DEFAULTS.grid, ticks: CHART_DEFAULTS.ticks },
    },
  };
}

function _canvas() {
  _destroyChart();
  chartContainer.innerHTML = '<canvas id="analyticsCanvas" style="max-height:260px"></canvas>';
  return document.getElementById('analyticsCanvas').getContext('2d');
}

// ── Risk coloring helpers ──────────────────────────────────────────────────────
/**
 * Given a dataset display name and a numeric value, returns the hex color
 * that corresponds to the risk zone defined in DATASET_INFO, or null if unknown.
 */
function _getRiskColor(datasetName, value) {
  const key = Object.keys(DATASET_INFO).find(k =>
    datasetName.toLowerCase().includes(k.toLowerCase().split(' ')[0])
    || k.toLowerCase().includes(datasetName.toLowerCase().split('(')[0].trim().toLowerCase())
  ) || Object.keys(DATASET_INFO).find(k => k.toLowerCase().startsWith(datasetName.toLowerCase().slice(0, 8)));
  const info = DATASET_INFO[key];
  if (!info) return null;
  const zone = info.ranges.find(r => value >= r.min && value < r.max)
    || (value >= info.ranges[info.ranges.length - 1].max ? info.ranges[info.ranges.length - 1] : null);
  return zone ? zone.color : null;
}

/**
 * Returns an array of per-point border colors based on dataset risk zones.
 * Falls back to defaultColor where no zone is matched.
 */
function _riskColors(datasetName, values, defaultColor = '#8888ff') {
  return values.map(v => _getRiskColor(datasetName, v) || defaultColor);
}

/**
 * Append a risk zone legend below the chart container.
 * Only shows ranges that have at least one matching value in `values`.
 */
function _appendRiskLegend(datasetName, values) {
  if (!chartContainer) return;
  const key = Object.keys(DATASET_INFO).find(k =>
    datasetName.toLowerCase().includes(k.toLowerCase().split(' ')[0])
    || k.toLowerCase().includes(datasetName.toLowerCase().split('(')[0].trim().toLowerCase())
  ) || Object.keys(DATASET_INFO).find(k => k.toLowerCase().startsWith(datasetName.toLowerCase().slice(0, 8)));
  const info = DATASET_INFO[key];
  if (!info) return;

  const min = Math.min(...values), max = Math.max(...values);
  const relevant = info.ranges.filter(r => r.max > min && r.min < max);
  if (!relevant.length) return;

  const pills = relevant.map(r =>
    `<span style="display:inline-flex;align-items:center;gap:5px;margin:2px 4px;padding:2px 8px;border-radius:12px;font-size:9px;background:${r.color}22;border:1px solid ${r.color}60;color:${r.color}">
      <span style="width:8px;height:8px;border-radius:50%;background:${r.color};display:inline-block"></span>${r.label}
    </span>`
  ).join('');

  const legend = document.createElement('div');
  legend.style.cssText = 'margin-top:6px;padding:6px 10px;border-radius:8px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07)';
  legend.innerHTML = `<div style="font-size:9px;color:#64748b;margin-bottom:4px;font-weight:600">RISK ZONES (colour key)</div><div style="display:flex;flex-wrap:wrap">${pills}</div>`;
  chartContainer.appendChild(legend);
}

function renderLineChart(title, labels, values, units = '', extra = {}) {
  if (!labels.length) return showChartMessage('No data available for this dataset.');
  const ctx = _canvas();

  // Apply per-point risk colours when a dataset name is provided
  const riskColors = extra.dataset ? _riskColors(extra.dataset, values) : null;
  const defaultColor = '#8888ff';

  _chartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: units ? `${title} (${units})` : title,
        data: values,
        borderColor: riskColors || defaultColor,
        backgroundColor: riskColors
          ? riskColors.map(c => c + '28')
          : 'rgba(136,136,255,0.15)',
        fill: !riskColors, // gradient fill only when not risk-coloured per-segment
        tension: 0.4,
        pointBackgroundColor: riskColors || defaultColor,
        pointBorderColor: riskColors ? riskColors.map(c => c + 'cc') : defaultColor,
        pointRadius: 4,
        pointHoverRadius: 6,
        segment: riskColors ? {
          borderColor: ctx2 => riskColors[ctx2.p1DataIndex] || defaultColor,
        } : undefined,
      }],
    },
    options: {
      ..._baseOptions(extra.subtitle || ''),
      plugins: {
        ..._baseOptions('').plugins,
        tooltip: {
          callbacks: {
            label: ctx2 => {
              const v = ctx2.parsed.y.toFixed(2);
              const col = riskColors ? riskColors[ctx2.dataIndex] : null;
              const zone = col ? ` ● ` : '';
              return `${zone}${v} ${units}`;
            },
          },
        },
      },
    },
  });
}

/**
 * Erosion scenario bar chart — horizontal bars coloured by risk zone.
 * Used when /api/analysis/forecast returns erosion_mode:true (soil datasets).
 */
function renderBarChartErosion(title, labels, values, units = '', dataset = '') {
  if (!labels.length) return showChartMessage('No erosion scenario data available.');
  const ctx = _canvas();
  const riskCols = dataset ? _riskColors(dataset, values) : values.map(() => '#8888ff');
  const bgCols   = riskCols.map(c => c + '55');

  _chartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels.map(l => l.length > 30 ? l.slice(0, 28) + '…' : l),
      datasets: [{
        label: units ? `${title} (${units})` : title,
        data: values,
        backgroundColor: bgCols,
        borderColor: riskCols,
        borderWidth: 1.5,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: { display: true, text: title, color: '#f1f5f9', font: { size: 13, weight: '600' } },
        tooltip: {
          callbacks: {
            label: ctx2 => `${ctx2.parsed.x.toFixed(3)} ${units}`,
          },
        },
      },
      scales: {
        x: { grid: CHART_DEFAULTS.grid, ticks: CHART_DEFAULTS.ticks },
        y: { grid: { display: false }, ticks: { ...CHART_DEFAULTS.ticks, font: { size: 9 } } },
      },
    },
  });
}

function renderBarChart(title, labels, values, interpretation = '') {
  if (!labels.length) return showChartMessage('No correlation data available.');
  const ctx = _canvas();
  const colors = values.map(v => v >= 0
    ? 'rgba(74,222,128,0.75)' : 'rgba(248,113,113,0.75)');
  const borders = values.map(v => v >= 0 ? '#4ade80' : '#f87171');

  _chartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels.map(l => l.length > 22 ? l.slice(0, 20) + '…' : l),
      datasets: [{
        label: interpretation || title,
        data: values,
        backgroundColor: colors,
        borderColor: borders,
        borderWidth: 1,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: { display: true, text: title, color: '#f1f5f9', font: { size: 13, weight: '600' } },
        tooltip: {
          callbacks: { label: ctx => `${ctx.parsed.x > 0 ? '+' : ''}${ctx.parsed.x.toFixed(3)}` },
        },
      },
      scales: {
        x: {
          min: -1, max: 1,
          grid: CHART_DEFAULTS.grid,
          ticks: { ...CHART_DEFAULTS.ticks, callback: v => v > 0 ? `+${v}` : v },
        },
        y: { grid: { display: false }, ticks: CHART_DEFAULTS.ticks },
      },
    },
  });

  // Show interpretation hint below chart
  const hint = document.createElement('p');
  hint.style.cssText = 'font-size:10px;color:#64748b;margin-top:6px;text-align:center;padding:0 12px';
  hint.textContent = interpretation;
  chartContainer.appendChild(hint);
}

// ── Chart loading functions ────────────────────────────────────────────────────

async function loadActiveChart() {
  if (!chartContainer) return;
  showChartMessage('Loading…');
  const dataset = datasetSelect.value;
  if (!dataset) { showChartMessage('Select a dataset to begin.'); return; }
  switch (activeChart) {
    case 'timeseries':   return loadTimeSeries(dataset);
    case 'correlation':  return loadCorrelation(dataset);
    case 'forecast':     return loadForecast(dataset);
    default: showChartMessage('Select an analysis tab.');
  }
}

function showChartMessage(message) {
  _destroyChart();
  if (!chartContainer) return;
  chartContainer.innerHTML = `<div class="chart-message"><div class="chart-message-icon">📊</div><p>${message}</p></div>`;
}

async function loadTimeSeries(dataset) {
  try {
    const res = await fetch(`${API}/analysis/time-series?dataset=${encodeURIComponent(dataset)}`);
    if (!res.ok) throw new Error('Time series request failed');
    const p = await res.json();
    const vals = p.values || [];
    renderLineChart(
      `${p.dataset} — Depth Profile`,
      p.labels || [],
      vals,
      p.units || '',
      { subtitle: p.description || '', dataset }
    );
    _appendRiskLegend(dataset, vals);
    _appendDatasetInfo(dataset, 'timeseries');
  } catch (e) {
    console.error(e);
    showChartMessage('Depth profile data unavailable.');
  }
}

async function loadCorrelation(dataset) {
  try {
    const res = await fetch(`${API}/analysis/correlation?dataset=${encodeURIComponent(dataset)}`);
    if (!res.ok) throw new Error('Correlation request failed');
    const p = await res.json();
    renderBarChart(
      `What influences "${p.dataset}"?`,
      p.labels || [],
      p.values || [],
      p.interpretation || 'Green = positive · Red = inverse relationship'
    );
    _appendDatasetInfo(dataset, 'correlation');
  } catch (e) {
    console.error(e);
    showChartMessage('Influence data unavailable.');
  }
}

async function loadForecast(dataset, years = 200) {
  try {
    showChartMessage('Loading forecast…');
    // Try pre-computed cache first (fast)
    let p = null;
    try {
      const cached = await fetch(`${API}/forecasts/cached?dataset=${encodeURIComponent(dataset)}`);
      if (cached.ok) {
        p = await cached.json();
        // Trim to requested year range (only for temporal, non-erosion datasets)
        if (!p.erosion_mode && years < (p.labels || []).length) {
          p.labels = p.labels.slice(0, years + 1);
          p.values = p.values.slice(0, years + 1);
        }
      }
    } catch { /* fall through to live */ }

    // Fall back to live computation if cache miss
    if (!p) {
      showChartMessage(p?.erosion_mode ? 'Loading erosion scenario…' : 'Running ML forecast model…');
      const res = await fetch(`${API}/analysis/forecast?dataset=${encodeURIComponent(dataset)}&years=${years}`);
      if (!res.ok) throw new Error('Forecast request failed');
      p = await res.json();
    }

    const labels = p.labels || [];
    const values = p.values || [];

    if (p.erosion_mode) {
      // Erosion scenario: labels are already meaningful strings (no subsampling needed)
      renderBarChartErosion(
        `${p.dataset} — Erosion Scenario`,
        labels, values, p.units || '', dataset
      );
      const badge = document.createElement('p');
      badge.style.cssText = 'font-size:10px;color:#fbbf24;text-align:center;margin-top:4px;line-height:1.5';
      badge.textContent = `Model: ${p.model || '–'}  ·  Current surface: ${p.baseline ?? '–'} ${p.units ?? ''}  ·  ${p.subtitle || ''}`;
      chartContainer.appendChild(badge);
    } else {
      // Temporal forecast: subsample to ~20 points for readability
      const step = Math.max(1, Math.floor(labels.length / 20));
      const dispLabels = labels.filter((_, i) => i % step === 0 || i === labels.length - 1);
      const dispValues = values.filter((_, i) => i % step === 0 || i === values.length - 1);
      renderLineChart(
        `${p.dataset} — ${years}-Year Forecast`,
        dispLabels, dispValues, p.units || '',
        { subtitle: `Model: ${p.model || ''}`, dataset }
      );
      if (p.model) {
        const badge = document.createElement('p');
        badge.style.cssText = 'font-size:10px;color:#8888ff;text-align:center;margin-top:4px';
        badge.textContent = `Model: ${p.model}  ·  Baseline: ${p.baseline ?? '–'} ${p.units ?? ''}`;
        chartContainer.appendChild(badge);
      }
      _appendRiskLegend(dataset, dispValues);
    }
    // Show dataset-specific interpretation below chart
    _appendDatasetInfo(dataset, 'forecast');
  } catch (e) {
    console.error(e);
    showChartMessage('Forecast unavailable.');
  }
}

async function loadPrediction() {
  const dataset = datasetSelect.value;
  if (!dataset) { showChartMessage('Select a dataset to begin.'); return; }

  const sYear = parseInt(startYearInput.value, 10);
  const eYear = parseInt(endYearInput.value, 10);
  const years = Math.min(Math.max(eYear - sYear, 1), 200);

  // Switch to forecast tab and run it with the selected year range
  activeChart = 'forecast';
  chartTabs.forEach(t => t.classList.toggle('active', t.dataset.tab === 'forecast'));
  await loadForecast(dataset, years);
}

// ── Model training UI ─────────────────────────────────────────────────────────

let _trainPollInterval = null;

/**
 * Shared polling loop — works for fresh training starts and page-reload resumes.
 */
function _startTrainingPoll(btn, statusEl) {
  clearInterval(_trainPollInterval);
  _trainPollInterval = setInterval(async () => {
    try {
      const res  = await fetch(`${API}/train/status`);
      const data = await res.json();

      if (data.status === 'done') {
        clearInterval(_trainPollInterval);
        _trainPollInterval = null;
        const saved = Object.values(data.result || {}).filter(v => v === 'saved').length;
        if (statusEl) statusEl.textContent = `✅ Done — ${saved} models saved.`;
        if (btn) { btn.disabled = false; btn.textContent = '🧠 Retrain Models'; }
        await refreshModelStatus();

      } else if (data.status === 'error') {
        clearInterval(_trainPollInterval);
        _trainPollInterval = null;
        if (statusEl) statusEl.textContent = `❌ Error: ${data.error}`;
        if (btn) { btn.disabled = false; btn.textContent = '🧠 Train Models'; }

      } else if (data.status === 'training') {
        if (statusEl) statusEl.textContent = 'Training in progress…';

      } else {
        // 'idle' — server restarted mid-training; abort poll, re-enable button
        clearInterval(_trainPollInterval);
        _trainPollInterval = null;
        if (statusEl) statusEl.textContent = '⚠️ Training interrupted (server restarted).';
        if (btn) { btn.disabled = false; btn.textContent = '🧠 Train Models'; }
      }
    } catch { /* ignore transient poll errors */ }
  }, 4000);
}

/**
 * Called at page load: resumes polling if training was already running
 * (handles the case where user refreshed mid-train).
 */
async function _checkAndResumeTraining() {
  try {
    const res  = await fetch(`${API}/train/status`);
    if (!res.ok) return;
    const data = await res.json();
    const btn      = document.getElementById('trainBtn');
    const statusEl = document.getElementById('trainStatus');

    if (data.status === 'training') {
      if (btn)      { btn.disabled = true; btn.textContent = '⏳ Training…'; }
      if (statusEl) statusEl.textContent = 'Training in progress…';
      _startTrainingPoll(btn, statusEl);
    } else if (data.status === 'done') {
      const saved = Object.values(data.result || {}).filter(v => v === 'saved').length;
      if (statusEl && saved > 0) statusEl.textContent = `✅ ${saved} models ready.`;
    }
  } catch { /* backend offline at load time — ignore */ }
}

async function trainModels() {
  const btn      = document.getElementById('trainBtn');
  const statusEl = document.getElementById('trainStatus');
  if (!btn || !statusEl) return;

  btn.disabled = true;
  btn.textContent = '⏳ Training…';
  statusEl.textContent = 'Sending training request…';

  try {
    const res  = await fetch(`${API}/train`, { method: 'POST' });
    const data = await res.json();
    statusEl.textContent = data.status === 'already_training'
      ? 'Training already in progress…'
      : 'Training started in background (may take ~1–2 min)…';
  } catch {
    statusEl.textContent = '⚠️ Could not reach backend.';
    btn.disabled = false;
    btn.textContent = '🧠 Train Models';
    return;
  }

  _startTrainingPoll(btn, statusEl);
}

async function refreshModelStatus() {
  try {
    const res = await fetch(`${API}/model-status`);
    if (!res.ok) return;
    const data = await res.json();

    // Aggregate: is any dataset trained for each model type?
    const has = {
      ridge:          Object.values(data).some(d => d.ridge),
      mlp:            Object.values(data).some(d => d.mlp),
      rf:             Object.values(data).some(d => d.rf),
      temporal_ridge: Object.values(data).some(d => d.temporal_ridge),
      temporal_mlp:   Object.values(data).some(d => d.temporal_mlp),
      temporal_rf:    Object.values(data).some(d => d.temporal_rf),
    };

    _setModelDot('ml-ridge',          has.ridge          ? 'trained' : '');
    _setModelDot('ml-mlp',            has.mlp            ? 'trained' : '');
    _setModelDot('ml-rf',             has.rf             ? 'trained' : '');
    _setModelDot('ml-temporal_ridge', has.temporal_ridge ? 'trained' : '');
    _setModelDot('ml-temporal_mlp',   has.temporal_mlp   ? 'trained' : '');
    _setModelDot('ml-temporal_rf',    has.temporal_rf    ? 'trained' : '');

    // Update the model type dropdown: disable options that have no trained model
    if (modelTypeSelect) {
      modelTypeSelect.querySelectorAll('option').forEach(opt => {
        if (opt.value === 'auto') return;
        const key = opt.value;  // e.g. 'rf', 'temporal_ridge'
        opt.disabled = !has[key];
        if (opt.disabled && opt.selected) modelTypeSelect.value = 'auto';
      });
    }
  } catch { /* backend offline */ }
}

function _setModelDot(elId, cls) {
  const dot = document.querySelector(`#${elId} .ml-dot`);
  if (!dot) return;
  dot.className = 'ml-dot' + (cls ? ` ${cls}` : '');
}

// ── Dataset knowledge base ────────────────────────────────────────────────────
// Soil science explanations, good/bad ranges, and contextual interpretation
// shown below charts and map visualizations.

const DATASET_INFO = {
  'Bulk Density (tonnes/m³)': {
    what: 'Bulk density measures how tightly soil particles are packed. It reflects compaction, pore space, and overall soil structure.',
    ranges: [
      { label: 'Ideal (loose, fertile)', min: 0.8, max: 1.2, color: '#4ade80' },
      { label: 'Acceptable', min: 1.2, max: 1.5, color: '#fbbf24' },
      { label: 'Compacted (limits roots)', min: 1.5, max: 1.8, color: '#f87171' },
      { label: 'Severely compacted', min: 1.8, max: 2.0, color: '#dc2626' },
    ],
    unit: 'tonnes/m³',
    forecast: 'Bulk density tends to increase under intensive agriculture and urbanisation due to compaction. Climate-driven drought cycles can further compact soils over decades.',
    influence: 'High clay content, low organic matter, and intensive tillage are the main drivers of high bulk density. Vegetation cover and earthworm activity reduce it.',
  },
  'Clay Content (%)': {
    what: 'Clay is the finest soil particle fraction (<0.002 mm). It governs water retention, nutrient holding capacity, and structural stability.',
    ranges: [
      { label: 'Sandy loam (low clay)', min: 0, max: 15, color: '#fbbf24' },
      { label: 'Loam / Silty loam', min: 15, max: 27, color: '#4ade80' },
      { label: 'Clay loam', min: 27, max: 40, color: '#60a5fa' },
      { label: 'Heavy clay (shrink-swell risk)', min: 40, max: 100, color: '#f87171' },
    ],
    unit: '%',
    forecast: 'Clay content is geologically stable over human timescales. Changes are driven by erosion, sedimentation, and long-term weathering rather than climate change directly.',
    influence: 'Clay is primarily a function of parent material (bedrock geology) and landform. Topographic position and drainage strongly control clay accumulation.',
  },
  'Organic Carbon (g/kg)': {
    what: 'Soil organic carbon (SOC) is the carbon stored in organic matter — decomposed plant/animal material. It is a key indicator of soil health, fertility, and the global carbon cycle.',
    ranges: [
      { label: 'Very low (degraded)', min: 0, max: 6, color: '#f87171' },
      { label: 'Low', min: 6, max: 12, color: '#fbbf24' },
      { label: 'Moderate (agricultural target)', min: 12, max: 20, color: '#4ade80' },
      { label: 'High (healthy)', min: 20, max: 40, color: '#22d3ee' },
      { label: 'Very high (peat-like)', min: 40, max: 200, color: '#818cf8' },
    ],
    unit: 'g/kg',
    forecast: 'SOC is declining globally due to warming temperatures (faster decomposition) and land-use change. Under business-as-usual, Barcelona-region soils may lose 10–25% SOC by 2100.',
    influence: 'Land use is the dominant driver — forests and grasslands store more SOC than croplands. Precipitation and temperature control decomposition rates.',
  },
  'Sand Content (%)': {
    what: 'Sand (0.05–2 mm) is the coarsest soil fraction. It determines drainage speed, aeration, and workability. Sandy soils drain quickly but hold fewer nutrients.',
    ranges: [
      { label: 'Clay/silty (low sand)', min: 0, max: 25, color: '#60a5fa' },
      { label: 'Loam', min: 25, max: 50, color: '#4ade80' },
      { label: 'Sandy loam (well-drained)', min: 50, max: 70, color: '#fbbf24' },
      { label: 'Sand (droughty)', min: 70, max: 100, color: '#f87171' },
    ],
    unit: '%',
    forecast: 'Sand content is geologically stable. However, erosion and aeolian (wind) deposition can shift texture at exposed surfaces, especially under land-cover change.',
    influence: 'Parent material and geomorphology are the primary controls. Coastal proximity and wind exposure increase sand fractions in surface layers.',
  },
  'Soil Texture Class': {
    what: 'Soil texture class (USDA system) is a categorical classification combining sand, silt, and clay fractions into named groups: Sandy, Loam, Clay, Silty Clay, etc.',
    ranges: [
      { label: 'Class 1–3: Coarse (Sandy)', min: 1, max: 3, color: '#fbbf24' },
      { label: 'Class 4–6: Medium (Loamy)', min: 4, max: 6, color: '#4ade80' },
      { label: 'Class 7–9: Fine (Clayey)', min: 7, max: 9, color: '#60a5fa' },
      { label: 'Class 10–12: Very Fine', min: 10, max: 12, color: '#818cf8' },
    ],
    unit: 'class (1–12)',
    forecast: 'Texture class is stable over human timescales unless major erosion or deposition events occur. Changes in surface texture are driven by topsoil loss.',
    influence: 'Defined by parent material and weathering stage. Climate (rainfall intensity, freeze-thaw) drives long-term weathering that shifts texture class.',
  },
  'Soil pH (H₂O)': {
    what: 'Soil pH measures acidity/alkalinity on a 0–14 scale. It controls nutrient availability, microbial activity, and plant growth. Most crops prefer slightly acidic to neutral soils.',
    ranges: [
      { label: 'Strongly acidic (<5.5) — Al/Mn toxicity risk', min: 4, max: 5.5, color: '#f87171' },
      { label: 'Moderately acidic', min: 5.5, max: 6.5, color: '#fbbf24' },
      { label: 'Optimal (6.0–7.0)', min: 6.0, max: 7.0, color: '#4ade80' },
      { label: 'Neutral to slightly alkaline', min: 7.0, max: 7.5, color: '#4ade80' },
      { label: 'Alkaline — P deficiency risk', min: 7.5, max: 8.5, color: '#fbbf24' },
      { label: 'Strongly alkaline (>8.5)', min: 8.5, max: 10, color: '#f87171' },
    ],
    unit: 'pH units',
    forecast: 'Soil acidification is driven by nitrogen deposition, acid rain, and intensive cropping. Climate change may shift pH through altered precipitation chemistry and weathering rates.',
    influence: 'Parent material (limestone raises pH, granite lowers it), rainfall (leaching acidifies), fertiliser type, and vegetation type are key drivers.',
  },
  'Precipitation (CHIRPS)': {
    what: 'CHIRPS (Climate Hazards Group InfraRed Precipitation with Station data) annual precipitation represents total rainfall in mm/year for the Barcelona region.',
    ranges: [
      { label: 'Arid (<250 mm/yr)', min: 0, max: 250, color: '#f87171' },
      { label: 'Semi-arid (250–500)', min: 250, max: 500, color: '#fbbf24' },
      { label: 'Sub-humid (500–800)', min: 500, max: 800, color: '#4ade80' },
      { label: 'Humid (800–1200)', min: 800, max: 1200, color: '#22d3ee' },
      { label: 'Very humid (>1200)', min: 1200, max: 3000, color: '#818cf8' },
    ],
    unit: 'mm/year',
    forecast: 'Mediterranean climates like Barcelona face projected drying under most IPCC scenarios. Annual precipitation may decrease 10–20% by 2100, with more extreme single events.',
    influence: 'Large-scale atmospheric circulation (NAO, Azores High) dominates inter-annual variability. ENSO teleconnections affect drought years. Local topography amplifies orographic rainfall.',
  },
  'MODIS Land Cover': {
    what: 'MODIS MCD12Q1 Land Cover product classifies land surface into 17 IGBP classes (forests, croplands, urban, water, etc.) at 500m resolution using satellite imagery.',
    ranges: [
      { label: 'Forests (classes 1–5): high carbon, biodiversity', min: 1, max: 5, color: '#166534' },
      { label: 'Shrublands (6–7): transition zones', min: 6, max: 7, color: '#86efac' },
      { label: 'Savannas (8–9)', min: 8, max: 9, color: '#a3e635' },
      { label: 'Grasslands (10)', min: 10, max: 10, color: '#4ade80' },
      { label: 'Wetlands (11)', min: 11, max: 11, color: '#38bdf8' },
      { label: 'Croplands (12)', min: 12, max: 12, color: '#fbbf24' },
      { label: 'Urban/Built-up (13)', min: 13, max: 13, color: '#f87171' },
      { label: 'Barren (16)', min: 16, max: 16, color: '#d1d5db' },
    ],
    unit: 'IGBP class (1–17)',
    forecast: 'Barcelona\u2019s peri-urban fringe continues to urbanise. Cropland and natural shrubland are projected to decrease as built-up area expands. Climate may push tree line upward.',
    influence: 'Land use policies, urbanisation pressure, agricultural economics, and climate-driven vegetation shifts are key drivers. Fire frequency shapes shrubland/forest balance.',
  },
};

/**
 * Append a "ℹ️ About this data" panel below the active chart.
 * @param {string} datasetName - full display name matching DATASET_INFO keys
 * @param {'timeseries'|'correlation'|'forecast'} chartType
 */
function _appendDatasetInfo(datasetName, chartType) {
  // find the closest matching key
  const key = Object.keys(DATASET_INFO).find(k =>
    datasetName.toLowerCase().includes(k.toLowerCase().split(' ')[0])
    || k.toLowerCase().includes(datasetName.toLowerCase().split('(')[0].trim().toLowerCase())
  ) || Object.keys(DATASET_INFO).find(k => k.toLowerCase().startsWith(datasetName.toLowerCase().slice(0, 8)));
  const info = DATASET_INFO[key];
  if (!info || !chartContainer) return;

  const contextText = chartType === 'forecast' ? info.forecast
    : chartType === 'correlation' ? info.influence
    : info.what;

  // Build range pills
  const rangePills = info.ranges.map(r =>
    `<span style="display:inline-block;margin:2px 3px;padding:1px 7px;border-radius:10px;font-size:9px;background:${r.color}22;border:1px solid ${r.color};color:${r.color}">${r.label}</span>`
  ).join('');

  const panel = document.createElement('div');
  panel.style.cssText = 'margin-top:10px;padding:10px 12px;border-radius:10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);font-size:10px;color:#94a3b8;line-height:1.5';
  panel.innerHTML = `
    <div style="font-size:10px;font-weight:600;color:#c7d2fe;margin-bottom:5px">ℹ️ About this data</div>
    <p style="margin-bottom:6px">${contextText}</p>
    <div style="margin-top:4px">${rangePills}</div>
    <div style="margin-top:5px;color:#64748b;font-size:9px">Unit: ${info.unit}</div>
  `;
  chartContainer.appendChild(panel);
}


