const API_BASE = 'http://127.0.0.1:8000/api';
const DEFAULT_COORDS = { lat: 40.4, lon: -3.7 };

const yearSlider = document.getElementById('yearSlider');
const yearValue = document.getElementById('yearValue');
const datasetSelect = document.getElementById('datasetSelect');
const regionInfo = document.getElementById('regionInfo');
const backendStatus = document.getElementById('backendStatus');
const datasetDescription = document.getElementById('datasetDescription');
const visualizeBtn = document.getElementById('visualizeBtn');
const predictBtn = document.getElementById('predictBtn');
const startYearInput = document.getElementById('startYear');
const endYearInput = document.getElementById('endYear');
const chartTabs = document.querySelectorAll('.chart-tab');
const chartContainer = document.querySelector('.chart-container');
const statElements = {
  mean: document.getElementById('statMean'),
  min: document.getElementById('statMin'),
  max: document.getElementById('statMax'),
  stdDev: document.getElementById('statStdDev')
};

let activeChart = 'timeseries';
let datasetMetadata = [];

document.addEventListener('DOMContentLoaded', () => {
  initDashboard();
});

function initDashboard() {
  yearValue.textContent = yearSlider.value;
  regionInfo.textContent = `Lat: ${DEFAULT_COORDS.lat.toFixed(2)}, Lon: ${DEFAULT_COORDS.lon.toFixed(2)} (simulated region)`;
  attachEventListeners();
  displayBackendStatus();
  refreshDatasetList().then(() => {
    updateStatistics();
    // Initially load the map for the default dataset
    if (window.visualizeDataset) {
      window.visualizeDataset(datasetSelect.value);
    }
  });
}

function attachEventListeners() {
  yearSlider.addEventListener('input', (event) => {
    yearValue.textContent = event.target.value;
  });

  datasetSelect.addEventListener('change', () => {
    updateDatasetDescription(datasetSelect.value);
    updateStatistics();
  });

  visualizeBtn.addEventListener('click', () => {
    if (window.visualizeDataset) {
      window.visualizeDataset(datasetSelect.value, yearSlider.value);
    }
    updateStatistics();
  });

  predictBtn.addEventListener('click', () => {
    loadPrediction();
  });

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
  try {
    const response = await fetch(`${API_BASE}/status`);
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
    const response = await fetch(`${API_BASE}/datasets`);
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
    datasetDescription.textContent = `${metadata.description} · Asset: ${metadata.asset}`;
  } else {
    datasetDescription.textContent = 'Dataset metadata will appear once the backend responds.';
  }
}

async function updateStatistics() {
  const dataset = datasetSelect.value;
  if (!dataset) return;
  setStatValues('Loading...');
  try {
    const response = await fetch(
      `${API_BASE}/statistics?dataset=${encodeURIComponent(dataset)}&lat=${DEFAULT_COORDS.lat}&lon=${DEFAULT_COORDS.lon}`
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

async function loadActiveChart() {
  if (!chartContainer) return;
  showChartMessage('Loading chart data…');
  const dataset = datasetSelect.value;
  if (!dataset) {
    showChartMessage('Select a dataset to begin.');
    return;
  }
  switch (activeChart) {
    case 'timeseries':
      return loadTimeSeries(dataset);
    case 'change':
      return loadChangeDetection(dataset);
    case 'correlation':
      return loadCorrelation(dataset);
    case 'forecast':
      return loadForecast(dataset);
    default:
      showChartMessage('Select an analysis tab to visualize data.');
  }
}

function renderChart(title, rows) {
  if (!chartContainer) return;
  if (!rows.length) {
    showChartMessage('No data available yet.');
    return;
  }
  chartContainer.innerHTML = `
    <div class="chart-output">
      <strong>${title}</strong>
      ${rows
        .map(
          (row) => `
            <div class="chart-output-row">
              <span>${row.label}</span>
              <span>${row.value}</span>
            </div>
          `
        )
        .join('')}
    </div>
  `;
}

function showChartMessage(message) {
  if (!chartContainer) return;
  chartContainer.innerHTML = `
    <div class="placeholder">
      <p>${message}</p>
    </div>
  `;
}

async function loadTimeSeries(dataset) {
  const endYear = parseInt(yearSlider.value, 10);
  const startYear = 2000;
  try {
    const response = await fetch(
      `${API_BASE}/analysis/time-series?dataset=${encodeURIComponent(dataset)}&start_year=${startYear}&end_year=${endYear}`
    );
    if (!response.ok) throw new Error('Time series request failed');
    const payload = await response.json();
    const rows = (payload.points || [])
      .slice(-6)
      .map((point) => ({ label: `${point.year}`, value: formatStat(point.value) }));
    renderChart('Time Series', rows);
  } catch (error) {
    console.error(error);
    showChartMessage('Time series data unavailable.');
  }
}

async function loadChangeDetection(dataset) {
  const endYear = parseInt(yearSlider.value, 10);
  const startYear = Math.max(2000, endYear - 5);
  try {
    const response = await fetch(
      `${API_BASE}/analysis/change-detection?dataset=${encodeURIComponent(dataset)}&year_a=${startYear}&year_b=${endYear}`
    );
    if (!response.ok) throw new Error('Change detection request failed');
    const payload = await response.json();
    const rows = [
      { label: `${payload.earlier_year}`, value: formatStat(payload.earlier_value) },
      { label: `${payload.later_year}`, value: formatStat(payload.later_value) },
      { label: 'Delta', value: formatStat(payload.delta) }
    ];
    renderChart('Change Detection', rows);
  } catch (error) {
    console.error(error);
    showChartMessage('Change detection data unavailable.');
  }
}

async function loadCorrelation(dataset) {
  try {
    const response = await fetch(`${API_BASE}/analysis/correlation?dataset=${encodeURIComponent(dataset)}`);
    if (!response.ok) throw new Error('Correlation request failed');
    const payload = await response.json();
    const entries = Object.entries(payload.correlation || {}).slice(0, 4);
    const rows = entries.map(([label, value]) => ({
      label,
      value: typeof value === 'number' ? value.toFixed(2) : '--'
    }));
    renderChart('Correlation', rows);
  } catch (error) {
    console.error(error);
    showChartMessage('Correlation data unavailable.');
  }
}

async function loadForecast(dataset) {
  try {
    const response = await fetch(`${API_BASE}/analysis/forecast?dataset=${encodeURIComponent(dataset)}&years=5`);
    if (!response.ok) throw new Error('Forecast request failed');
    const payload = await response.json();
    const rows = (payload.forecast || []).map((item) => ({
      label: `${item.year}`,
      value: formatStat(item.value)
    }));
    renderChart('ML Forecast', rows);
  } catch (error) {
    console.error(error);
    showChartMessage('Forecast data unavailable.');
  }
}

async function loadPrediction() {
    const dataset = datasetSelect.value;
    if (!dataset) {
        showChartMessage('Select a dataset to begin.');
        return;
    }

    const sYear = parseInt(startYearInput.value, 10);
    const eYear = parseInt(endYearInput.value, 10);

    const bounds = window.getMapBounds();
    if (bounds) {
        const { _northEast, _southWest } = bounds;
        const url = `${API_BASE}/analysis/prediction?dataset=${encodeURIComponent(dataset)}&start_year=${sYear}&end_year=${eYear}&lat_min=${_southWest.lat}&lon_min=${_southWest.lng}&lat_max=${_northEast.lat}&lon_max=${_northEast.lng}`;
        
        try {
            showChartMessage('Running ML prediction model...');
            const response = await fetch(url);
            if (!response.ok) throw new Error('Prediction request failed');
            const payload = await response.json();
            const rows = (payload.points || []).map((point) => ({ label: `${point.year}`, value: formatStat(point.value) }));
            renderChart('Prediction Output', rows);
        } catch (error) {
            console.error(error);
            showChartMessage('Prediction data unavailable.');
        }
    } else {
        alert("Could not get map bounds. Please try again.");
    }
}

