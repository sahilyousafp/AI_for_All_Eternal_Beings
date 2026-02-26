// Google Earth Engine Map Integration
// Initialize GEE and display map with dataset visualization

let geeMap = null;
let currentLayer = null;

function initGEEMap() {
  const mapStatus = document.getElementById('mapStatus');
  mapStatus.textContent = '✅ Connected to Backend Map Service';
  createGEEMap();
}

function createGEEMap() {
  const mapDiv = document.getElementById('map');
  
  // Create map using Leaflet
  geeMap = L.map('map').setView([40.0, -3.5], 6);
  
  // Add base layer
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
    maxZoom: 19
  }).addTo(geeMap);

  // Initialize with the currently selected dataset if available, otherwise default
  const datasetSelect = document.getElementById('datasetSelect');
  const firstDataset = (datasetSelect && datasetSelect.value) ? datasetSelect.value : "Organic Carbon (g/kg)";
  visualizeDataset(firstDataset);

  // Add click handler for region selection
  geeMap.on('click', function(e) {
    const { lat, lng } = e.latlng;
    document.getElementById('regionInfo').textContent = 
      `Lat: ${lat.toFixed(2)}, Lon: ${lng.toFixed(2)}`;
  });
}

async function visualizeDataset(datasetName, year = null) {
  if (!geeMap) return;

  const mapStatus = document.getElementById('mapStatus');
  const yearText = year ? ` for year ${year}` : '';
  mapStatus.textContent = `Loading ${datasetName}${yearText} layer...`;

  // Remove previous layer
  if (currentLayer) {
    geeMap.removeLayer(currentLayer);
  }

  try {
    let url = `http://localhost:8000/api/map?dataset=${encodeURIComponent(datasetName)}`;
    if (year) {
      url += `&year=${year}`;
    }
    
    const response = await fetch(url);
    const data = await response.json();
    
    if (data.error) {
       mapStatus.textContent = '❌ Error: ' + data.error;
       console.error('Map endpoint error:', data.error);
       return;
    }

    if (data.urlFormat) {
       const eeLayer = L.tileLayer(data.urlFormat, {
         attribution: 'Google Earth Engine',
         maxZoom: 18 
       });
       
       currentLayer = eeLayer;
       geeMap.addLayer(currentLayer);
       
       mapStatus.textContent = '✅ Displaying ' + datasetName;
    } else {
       mapStatus.textContent = '❌ Failed to receive map URL from backend.';
    }
  } catch (err) {
    mapStatus.textContent = '❌ Failed to fetch map layer from backend.';
    console.error('Fetch error:', err);
  }
}


// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
  initGEEMap();
});

// Export for use in main.js
window.visualizeDataset = visualizeDataset;
window.getMapBounds = () => {
    if (geeMap) {
        return geeMap.getBounds();
    }
    return null;
};
