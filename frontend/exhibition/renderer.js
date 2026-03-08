/**
 * Canvas-based spatial grid renderer.
 * Renders the 20×20 soil state grid as a colour map.
 */

function lerp(t, fromColor, toColor) {
  const c1 = parseHex(fromColor);
  const c2 = parseHex(toColor);
  return `rgb(${Math.round(c1[0]+(c2[0]-c1[0])*t)},${Math.round(c1[1]+(c2[1]-c1[1])*t)},${Math.round(c1[2]+(c2[2]-c1[2])*t)})`;
}

function parseHex(hex) {
  const h = hex.replace('#','');
  return [parseInt(h.slice(0,2),16), parseInt(h.slice(2,4),16), parseInt(h.slice(4,6),16)];
}

function renderSpatialMap(containerId, grid2d, highColor) {
  const container = document.getElementById(containerId);
  if (!container || !grid2d) return;
  container.innerHTML = '';

  const flat  = grid2d.flat();
  const min   = Math.min(...flat.filter(isFinite));
  const max   = Math.max(...flat.filter(isFinite));
  const range = max - min || 1;

  for (const row of grid2d) {
    for (const val of row) {
      const cell = document.createElement('div');
      cell.className = 'spatial-cell';
      const t = Math.max(0, Math.min(1, (val - min) / range));
      cell.style.backgroundColor = lerp(t, '#1a1a1a', highColor);
      cell.title = `${(val || 0).toFixed(2)}`;
      container.appendChild(cell);
    }
  }
}
