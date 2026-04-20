/**
 * Soil Futures — simulation runner + hero-scene renderer.
 * All results flow into ONE unified visual: three soil columns (Archive 1950,
 * Witness 2025, Oracle 2075) with canopy silhouettes, ghost erosion strips,
 * event markers, a year scrubber, and an 8-second animated fill. No charts.
 */

let simResult    = null;
let selectedYears = 50;
let _abortCtrl   = null;
let _animRAF     = null;  // active animation handle

// ═════════════════════════════════════════════════════════════════════════
//  Soil depth structure — matches the engine (SoilGrids 2.0 native bands)
// ═════════════════════════════════════════════════════════════════════════
const SOIL_DEPTHS_CM = [
  { top: 0,   bot: 5 },
  { top: 5,   bot: 15 },
  { top: 15,  bot: 30 },
  { top: 30,  bot: 60 },
  { top: 60,  bot: 100 },
  { top: 100, bot: 200 },
];

// ═════════════════════════════════════════════════════════════════════════
//  Simulation runner
// ═════════════════════════════════════════════════════════════════════════

function cancelSimulation() {
  if (_abortCtrl) { _abortCtrl.abort(); _abortCtrl = null; }
  const overlay = document.getElementById('loading-overlay');
  const btn     = document.getElementById('btn-run');
  if (overlay) overlay.classList.remove('visible');
  if (btn)     btn.disabled = false;
}

async function runSimulation() {
  if (!selectedPhilosophy || !selectedScenario) return;
  selectedYears = parseInt(document.getElementById('years-slider').value, 10);

  const years    = selectedYears;
  const ensSel   = document.getElementById('ensemble-select');
  const ensemble = ensSel ? parseInt(ensSel.value, 10) : 3;
  const btn      = document.getElementById('btn-run');
  const overlay  = document.getElementById('loading-overlay');
  const msg      = document.getElementById('loading-msg');

  btn.disabled = true;
  overlay.classList.add('visible');
  msg.textContent = `Growing ${years} years of soil…`;

  _abortCtrl = new AbortController();
  const timeoutId = setTimeout(() => { if (_abortCtrl) _abortCtrl.abort(); }, 45000);

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
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    simResult = await res.json();
    renderHeroScene(simResult);
    document.getElementById('sim-output').classList.add('visible');
  } catch (e) {
    clearTimeout(timeoutId);
    if (e.name === 'AbortError') {
      msg.textContent = 'Timed out — is the backend running?';
    } else {
      console.error('Simulation error:', e);
      msg.textContent = `Error: ${e.message}`;
    }
    setTimeout(cancelSimulation, 3000);
    return;
  } finally {
    _abortCtrl = null;
    btn.disabled = false;
    overlay.classList.remove('visible');
  }
}

// ═════════════════════════════════════════════════════════════════════════
//  Colour: SOC (g/kg) → Munsell-inspired soil RGB
// ═════════════════════════════════════════════════════════════════════════

function socToSoilColor(soc) {
  if (soc == null || !isFinite(soc)) return 'rgb(102,102,102)';
  const anchors = [
    { s:  0, r: 186, g: 160, b: 120 },
    { s:  3, r: 179, g: 151, b: 112 },
    { s:  8, r: 122, g:  84, b:  50 },
    { s: 15, r:  74, g:  46, b:  24 },
    { s: 25, r:  37, g:  23, b:  11 },
  ];
  const v = Math.max(0, Math.min(25, Number(soc)));
  let lo = anchors[0], hi = anchors[anchors.length - 1];
  for (let i = 0; i < anchors.length - 1; i++) {
    if (v >= anchors[i].s && v <= anchors[i + 1].s) {
      lo = anchors[i]; hi = anchors[i + 1]; break;
    }
  }
  const t = (v - lo.s) / Math.max(1e-6, hi.s - lo.s);
  const r = Math.round(lo.r + (hi.r - lo.r) * t);
  const g = Math.round(lo.g + (hi.g - lo.g) * t);
  const b = Math.round(lo.b + (hi.b - lo.b) * t);
  return `rgb(${r},${g},${b})`;
}

// ═════════════════════════════════════════════════════════════════════════
//  Canopy silhouette SVG by philosophy × era
// ═════════════════════════════════════════════════════════════════════════

function canopySVG(mode) {
  // mode: 'archive' (thick forest), 'witness' (sparse shrubs),
  //       'oak_forest', 'dehesa', 'bare_field', 'eucalyptus',
  //       'dense_restoration', 'scrubland'
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 200 180');
  svg.setAttribute('preserveAspectRatio', 'none');

  const addEl = (name, attrs) => {
    const el = document.createElementNS('http://www.w3.org/2000/svg', name);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    svg.appendChild(el);
    return el;
  };

  // Ground line always
  const ground = () => addEl('line', {x1:'0',y1:'175',x2:'200',y2:'175',
    stroke:'rgba(255,255,255,0.08)','stroke-width':'1'});

  const oak = (cx, cy, rx, ry, trunkW, trunkH) => {
    addEl('ellipse', {cx, cy, rx, ry, fill:'#1a3a1a', opacity:'0.9'});
    addEl('ellipse', {cx:cx-5, cy:cy-10, rx:rx*0.78, ry:ry*0.75, fill:'#2d5a2d', opacity:'0.8'});
    addEl('rect', {x:cx-trunkW/2, y:cy+ry-2, width:trunkW, height:trunkH, fill:'#1a1108'});
  };
  const shrub = (cx, cy, rx, ry) => {
    addEl('ellipse', {cx, cy, rx, ry, fill:'#2d4a2d', opacity:'0.7'});
  };
  const stump = (x) => addEl('rect', {x, y:'166', width:'3', height:'12', fill:'#2a1a10'});
  const deadTree = (cx) => {
    addEl('rect', {x:cx-1.5, y:'130', width:'3', height:'50', fill:'#2a1a10'});
    addEl('line', {x1:cx, y1:'130', x2:cx-12, y2:'115', stroke:'#2a1a10','stroke-width':'2'});
    addEl('line', {x1:cx, y1:'130', x2:cx+12, y2:'118', stroke:'#2a1a10','stroke-width':'2'});
  };
  const eucTree = (cx) => {
    addEl('rect', {x:cx-1.5, y:'60', width:'3', height:'120', fill:'#3a2a1a'});
    addEl('ellipse', {cx, cy:'65', rx:'14', ry:'24', fill:'#2d5a4a', opacity:'0.82'});
  };

  if (mode === 'archive' || mode === 'oak_forest') {
    oak(50, 85, 34, 42, 6, 40);
    oak(120, 95, 42, 50, 7, 30);
    oak(175, 88, 28, 38, 5, 40);
  } else if (mode === 'dehesa') {
    oak(40, 105, 22, 28, 4, 32);
    oak(110, 112, 24, 30, 5, 25);
    oak(170, 100, 20, 26, 4, 32);
    // grass tufts between
    shrub(75, 165, 10, 4);
    shrub(140, 168, 8, 3);
  } else if (mode === 'dense_restoration') {
    // Many small oaks growing up
    oak(30, 115, 16, 22, 3, 28);
    oak(70, 110, 18, 24, 3, 28);
    oak(110, 112, 17, 22, 3, 28);
    oak(150, 108, 18, 24, 3, 28);
    oak(185, 112, 16, 22, 3, 28);
  } else if (mode === 'scrubland' || mode === 'witness') {
    shrub(30, 158, 20, 12);
    shrub(80, 162, 16, 9);
    shrub(135, 158, 22, 12);
    shrub(180, 162, 14, 9);
  } else if (mode === 'eucalyptus') {
    eucTree(40); eucTree(75); eucTree(110); eucTree(145); eucTree(180);
  } else if (mode === 'bare_field') {
    // Red sky hint
    addEl('rect', {x:'0', y:'0', width:'200', height:'60', fill:'rgba(239,68,68,0.05)'});
    stump(40); stump(110); stump(165);
  } else if (mode === 'dead_forest') {
    deadTree(50); deadTree(120); deadTree(175);
  }
  ground();
  return svg;
}

function philosophyCanopyMode(philId, era) {
  // era: 'archive' | 'witness' | 'oracle'
  if (era === 'archive')  return 'archive';         // pre-industrial forest everywhere
  if (era === 'witness')  return 'witness';         // today = sparse scrubland
  // Oracle depends on the chosen philosophy
  switch (philId) {
    case 'maximum_restoration':  return 'dense_restoration';
    case 'traditional_farming':  return 'dehesa';
    case 'let_nature_recover':   return 'scrubland';
    case 'fast_fix':             return 'eucalyptus';
    case 'industrial_agriculture': return 'bare_field';
    default: return 'scrubland';
  }
}

// ═════════════════════════════════════════════════════════════════════════
//  Band rendering
// ═════════════════════════════════════════════════════════════════════════

// Depth-proportional band heights with an 8% floor so shallow layers stay legible
const BAND_HEIGHT_PCT = (() => {
  const TOTAL = 200, MIN = 8;
  const raw = SOIL_DEPTHS_CM.map(d => (d.bot - d.top) * 100 / TOTAL);
  const boosted = raw.map(p => Math.max(p, MIN));
  const sum = boosted.reduce((a, b) => a + b, 0);
  return boosted.map(p => (p / sum) * 100);
})();

function _microbeDots(count) {
  const wrap = document.createElement('span');
  wrap.className = 'microbes';
  for (let i = 0; i < count; i++) {
    const dot = document.createElement('span');
    dot.className = 'dot';
    dot.style.top  = (10 + Math.random() * 80) + '%';
    dot.style.left = (8 + Math.random() * 82) + '%';
    wrap.appendChild(dot);
  }
  return wrap;
}

/**
 * Build one soil column DOM: 6 bands, coloured + layered with visual cues.
 *
 * @param {string} containerId - id of the .soil-column element
 * @param {number[]} values     - array of 6 SOC g/kg values
 * @param {object} opts
 *   bd       : optional array of 6 bulk densities (stipple trigger)
 *   moist    : optional boolean flags for moist sheen
 *   lsi      : surface LSI (0-100) — drives glow intensity on band 0
 *   mbc      : surface microbial biomass (g/kg) — drives dot count on bands 0-1
 *   events   : array of {year, type, severity} — for Oracle column event track
 *   showRoots: boolean, AMF fringe visibility (Oracle only)
 */
function buildColumn(containerId, values, opts = {}) {
  const col = document.getElementById(containerId);
  if (!col) return;
  col.textContent = '';

  const bdArr   = opts.bd || [];
  const moist   = opts.moist || false;
  const lsi     = opts.lsi != null ? Number(opts.lsi) : null;
  const mbc     = opts.mbc != null ? Number(opts.mbc) : null;

  for (let i = 0; i < Math.min(values.length, SOIL_DEPTHS_CM.length); i++) {
    const depth = SOIL_DEPTHS_CM[i];
    const band  = document.createElement('div');
    band.className = 'band';
    band.dataset.layer = String(i);
    band.style.background = socToSoilColor(values[i]);
    band.style.flexBasis  = `${BAND_HEIGHT_PCT[i]}%`;
    band.style.flexGrow   = '0';

    // Bulk density → stipple if BD > 1.5
    if (bdArr[i] != null && bdArr[i] > 1.5) band.classList.add('bd-dense');

    // Moist sheen on high-moisture layers
    if (moist) band.classList.add('moist');

    // LSI glow on surface band (only meaningful for layer 0–1)
    if (lsi != null && i <= 1) {
      if (lsi >= 55) band.classList.add('thriving');
      else if (lsi >= 35) band.classList.add('alive');
    }

    // Microbe particle dots on layers 0–1 if MBC is meaningful
    if (mbc != null && mbc > 0.05 && i <= 1) {
      const count = Math.max(2, Math.min(10, Math.round(mbc * 6)));
      band.appendChild(_microbeDots(count));
    }

    const depthLabel = document.createElement('span');
    depthLabel.className = 'band-depth';
    depthLabel.textContent = `${depth.top}–${depth.bot} cm`;
    band.appendChild(depthLabel);

    const valueLabel = document.createElement('span');
    valueLabel.className = 'band-value';
    const v = (values[i] == null || !isFinite(values[i])) ? '—' : Number(values[i]).toFixed(1);
    valueLabel.textContent = v + ' ';
    const unit = document.createElement('span');
    unit.className = 'unit';
    unit.textContent = 'g/kg';
    valueLabel.appendChild(unit);
    band.appendChild(valueLabel);

    // Interactivity
    band.addEventListener('mouseenter', () => _highlightLayer(i));
    band.addEventListener('mouseleave', () => _clearHighlight());
    band.addEventListener('click',      () => _showBandDetail(i, containerId));

    col.appendChild(band);
  }
}

function _highlightLayer(layerIdx) {
  document.querySelectorAll('.band').forEach(b => {
    if (Number(b.dataset.layer) === layerIdx) b.classList.add('hl');
  });
}
function _clearHighlight() {
  document.querySelectorAll('.band.hl').forEach(b => b.classList.remove('hl'));
}

function _showBandDetail(layerIdx, colId) {
  const panel = document.getElementById('band-detail');
  if (!panel || !simResult) return;
  const depth = SOIL_DEPTHS_CM[layerIdx];
  const profile = simResult.initial_profile || {};
  const lastLayers = simResult.timeseries?.soc_layers_mean?.slice(-1)[0] || [];
  const archiveOC = simResult.archive_profile?.organic_carbon_g_kg || [];

  panel.classList.add('visible');
  panel.textContent = '';

  const h = document.createElement('h4');
  h.textContent = `Depth ${depth.top}–${depth.bot} cm · everything we know about this layer`;
  panel.appendChild(h);

  const grid = document.createElement('div');
  grid.className = 'bd-grid';
  const rows = [
    ['Carbon · 1950',    archiveOC[layerIdx],   'g/kg'],
    ['Carbon · 2025',    profile.organic_carbon_g_kg?.[layerIdx], 'g/kg'],
    ['Carbon · 2075',    lastLayers[layerIdx],  'g/kg'],
    ['Clay',             profile.clay_pct?.[layerIdx],            '%'],
    ['Sand',             profile.sand_pct?.[layerIdx],            '%'],
    ['Silt',             profile.silt_pct?.[layerIdx],            '%'],
    ['Bulk density',     profile.bulk_density_t_m3?.[layerIdx],  't/m³'],
    ['Soil pH',          profile.soil_ph?.[layerIdx],            ''],
  ];
  rows.forEach(([label, val, unit]) => {
    const cell = document.createElement('div');
    cell.className = 'bd-stat';
    const strong = document.createElement('strong');
    const v = (val == null || !isFinite(val)) ? '—' : Number(val).toFixed(2) + (unit ? ' ' + unit : '');
    strong.textContent = v;
    cell.appendChild(strong);
    cell.appendChild(document.createTextNode(label));
    grid.appendChild(cell);
  });
  panel.appendChild(grid);
}

// ═════════════════════════════════════════════════════════════════════════
//  Erosion ghost strip
// ═════════════════════════════════════════════════════════════════════════

function renderErosionGhost(elId, mmLost, captionText) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.className = 'erosion-ghost';
  el.textContent = '';
  if (!mmLost || mmLost <= 0) return;
  if (mmLost >= 80)      el.classList.add('catastrophic');
  else if (mmLost >= 30) el.classList.add('medium');
  else                   el.classList.add('has-loss');
  const span = document.createElement('span');
  span.textContent = captionText || `${mmLost.toFixed(0)} mm topsoil lost →`;
  el.appendChild(span);
}

// ═════════════════════════════════════════════════════════════════════════
//  Event track (Oracle column)
// ═════════════════════════════════════════════════════════════════════════

function renderEventTrack(events) {
  const oracleCol = document.getElementById('col-oracle');
  if (!oracleCol) return;
  // Clear existing
  oracleCol.querySelectorAll('.event-track').forEach(el => el.remove());
  if (!events || events.length === 0) return;

  const track = document.createElement('div');
  track.className = 'event-track';
  // Show at most 6 most significant events
  const shown = events.slice(0, 6);
  for (const ev of shown) {
    const dot = document.createElement('span');
    dot.className = 'ev';
    dot.title = `${ev.type} · ${ev.year} · ${ev.severity || 'n/a'}`;
    if (ev.type === 'fire')      dot.textContent = '🔥';
    else if (ev.type === 'drought') dot.textContent = '💧';
    else                            dot.textContent = '⚡';
    track.appendChild(dot);
  }
  oracleCol.appendChild(track);
}

// ═════════════════════════════════════════════════════════════════════════
//  Canopy render
// ═════════════════════════════════════════════════════════════════════════

function renderCanopy(elId, mode) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.textContent = '';
  el.appendChild(canopySVG(mode));
}

// ═════════════════════════════════════════════════════════════════════════
//  Summary strip + AI caption
// ═════════════════════════════════════════════════════════════════════════

const AI_CAPTIONS = {
  maximum_restoration:
    "Took today's real soil data for Barcelona (6 depth layers, measured by satellite). " +
    "Ran <strong>50 years</strong> of physics: how carbon moves through soil, how rain and heat change it. " +
    "Added your choice: <strong>plant oaks at high density, mix biochar into the soil, spread compost for 5 years, grow cover crops between trees, build erosion steps.</strong> " +
    "Projected the result to 2075.",
  traditional_farming:
    "Took today's real soil data. Ran 50 years of physics. " +
    "Added your choice: <strong>sparse oak trees, sheep grazing between them, manure returned to the land, no chemicals.</strong> " +
    "Projected the result to 2075.",
  let_nature_recover:
    "Took today's real soil data. Ran 50 years of physics. " +
    "Added your choice: <strong>stop all management, let plants come back on their own.</strong> " +
    "Projected the result to 2075.",
  industrial_agriculture:
    "Took today's real soil data. Ran 50 years of physics. " +
    "Added your choice: <strong>one crop everywhere, plough twice a year, chemical fertiliser, bare ground in winter.</strong> " +
    "Projected the result to 2075.",
  fast_fix:
    "Took today's real soil data. Ran 50 years of physics. " +
    "Added your choice: <strong>dense eucalyptus plantation with fertiliser — fast-growing but thirsty, acidifying, fire-prone.</strong> " +
    "Projected the result to 2075.",
};

function setAICaption(philId) {
  const el = document.getElementById('ai-caption-text');
  if (!el) return;
  const html = AI_CAPTIONS[philId] || 'Ran the soil model for you.';
  // Safe: the caption strings are hardcoded constants, not user input.
  el.innerHTML = html;
}

function renderSummary(data) {
  const strip = document.getElementById('summary-strip');
  if (!strip) return;
  const ts = data.timeseries || {};
  const last = (arr) => (arr && arr.length) ? arr[arr.length - 1] : null;
  const first = (arr) => (arr && arr.length) ? arr[0] : null;

  const soc0   = first(ts.total_soc_mean);
  const socN   = last(ts.total_soc_mean);
  const waterN = last(ts.water_retention_mean);
  const water0 = first(ts.water_retention_mean);
  const lsiN   = last(ts.living_soil_index_mean);
  const mmLost = data.erosion_summary?.topsoil_mm_lost || 0;
  const fireCount    = (data.events || []).filter(e => e.type === 'fire').length;
  const droughtCount = (data.events || []).filter(e => e.type === 'drought').length;

  const delta = (a, b) => (a == null || b == null) ? '' :
    `${b > a ? '+' : ''}${Math.round((b - a) / Math.max(0.01, a) * 100)}%`;
  const goodBadSoc = (socN != null && soc0 != null && socN >= soc0) ? 'good' : 'bad';
  const goodBadWater = (waterN != null && water0 != null && waterN >= water0) ? 'good' : 'bad';
  const goodBadLsi = (lsiN != null && lsiN >= 45) ? 'good' : 'bad';

  const stats = [
    {label: 'Carbon in the soil', value: socN != null ? `${socN.toFixed(1)} g/kg` : '—',
     sub: soc0 != null ? `was ${soc0.toFixed(1)} · ${delta(soc0, socN)}` : '',
     klass: goodBadSoc},
    {label: 'Topsoil lost', value: `${mmLost.toFixed(0)} mm`,
     sub: mmLost >= 30 ? 'catastrophic loss' : 'washed away',
     klass: mmLost >= 30 ? 'bad' : ''},
    {label: 'Water held', value: waterN != null ? `${waterN.toFixed(0)} %` : '—',
     sub: water0 != null ? `was ${water0.toFixed(0)} · ${delta(water0, waterN)}` : '',
     klass: goodBadWater},
    {label: 'Living Soil Score', value: lsiN != null ? `${Math.round(lsiN)} / 100` : '—',
     sub: lsiN >= 55 ? 'thriving' : lsiN >= 35 ? 'alive' : 'barely alive',
     klass: goodBadLsi},
    {label: 'Events', value: `🔥 ${fireCount} · 💧 ${droughtCount}`,
     sub: fireCount + droughtCount > 0 ? 'disturbances' : 'none',
     klass: fireCount + droughtCount > 0 ? 'bad' : ''},
  ];

  strip.textContent = '';
  for (const s of stats) {
    const wrap = document.createElement('div');
    wrap.className = 'stat';
    const labelEl = document.createElement('div');
    labelEl.className = 'stat-label';
    labelEl.textContent = s.label;
    const valueEl = document.createElement('div');
    valueEl.className = 'stat-value' + (s.klass ? ' ' + s.klass : '');
    valueEl.textContent = s.value;
    const subEl = document.createElement('div');
    subEl.className = 'stat-sub';
    subEl.textContent = s.sub;
    wrap.appendChild(labelEl);
    wrap.appendChild(valueEl);
    wrap.appendChild(subEl);
    strip.appendChild(wrap);
  }
}

// ═════════════════════════════════════════════════════════════════════════
//  Year scrubber + 8-second animated fill
// ═════════════════════════════════════════════════════════════════════════

function _setupScrubber(data) {
  const scrub = document.getElementById('year-scrubber');
  const label = document.getElementById('year-label');
  const ticks = document.getElementById('year-ticks');
  if (!scrub || !label || !ticks) return;
  const years = data.years || [];
  if (years.length === 0) return;
  const yearsCount = years.length - 1;  // 0..N
  scrub.max = String(yearsCount);
  scrub.value = String(yearsCount);
  label.textContent = String(years[yearsCount]);

  // Rebuild ticks: start / mid / end
  ticks.textContent = '';
  const samples = [0, Math.floor(yearsCount * 0.2), Math.floor(yearsCount * 0.4),
                   Math.floor(yearsCount * 0.6), Math.floor(yearsCount * 0.8), yearsCount];
  samples.forEach(i => {
    const s = document.createElement('span');
    s.textContent = String(years[i]);
    ticks.appendChild(s);
  });

  scrub.oninput = () => {
    const idx = parseInt(scrub.value, 10);
    label.textContent = String(years[idx]);
    _renderOracleAtYear(data, idx);
  };
}

function _renderOracleAtYear(data, yearIdx) {
  const layers = data.timeseries?.soc_layers_mean?.[yearIdx];
  if (!layers) return;
  const profile = data.initial_profile || {};
  const lsi = data.timeseries?.living_soil_index_mean?.[yearIdx];
  const mbc = data.timeseries?.mbc_mean?.[yearIdx];
  const water = data.timeseries?.water_retention_mean?.[yearIdx];
  buildColumn('col-oracle', layers, {
    bd: profile.bulk_density_t_m3,
    moist: water != null && water > 25,
    lsi,
    mbc,
  });
  // Update title year
  const title = document.getElementById('col-oracle-title');
  if (title && data.years) title.textContent = String(data.years[yearIdx]);
  // Ghost erosion grows with cumulative years
  if (data.erosion_summary?.topsoil_mm_lost != null && data.timeseries?.erosion_mean) {
    const fractionOfTime = yearIdx / Math.max(1, data.timeseries.erosion_mean.length - 1);
    const erosionAt = data.erosion_summary.topsoil_mm_lost * fractionOfTime;
    renderErosionGhost('erosion-oracle', erosionAt, `${erosionAt.toFixed(0)} mm topsoil lost →`);
  }
  // Root fringe appears when SOC is trending up at depth (restoration signal)
  const oracleCol = document.getElementById('col-oracle');
  const roots = oracleCol && layers[1] > 6.5;
  const colEl = oracleCol?.querySelector('.soil-column');
  if (colEl) colEl.classList.toggle('has-roots', !!roots);
}

function _playAnimation(data) {
  const btn = document.getElementById('btn-play');
  const scrub = document.getElementById('year-scrubber');
  const label = document.getElementById('year-label');
  if (!btn || !scrub || !data.timeseries?.soc_layers_mean) return;
  if (_animRAF) cancelAnimationFrame(_animRAF);

  const years = data.years || [];
  const yearsCount = years.length - 1;
  const durationMs = 8000;
  const start = performance.now();
  btn.disabled = true;

  function tick(now) {
    const elapsed = now - start;
    const t = Math.min(1, elapsed / durationMs);
    const idx = Math.round(t * yearsCount);
    scrub.value = String(idx);
    if (label) label.textContent = String(years[idx]);
    _renderOracleAtYear(data, idx);
    if (t < 1) {
      _animRAF = requestAnimationFrame(tick);
    } else {
      _animRAF = null;
      btn.disabled = false;
    }
  }
  _animRAF = requestAnimationFrame(tick);
}

// ═════════════════════════════════════════════════════════════════════════
//  Main entry point — renderHeroScene
// ═════════════════════════════════════════════════════════════════════════

function renderHeroScene(data) {
  if (!data) return;
  const archive = data.archive_profile;
  const profile = data.initial_profile;
  const ts = data.timeseries || {};
  const layersTs = ts.soc_layers_mean || [];
  const oracleValues = layersTs[layersTs.length - 1];

  // ── Archive (1950) ──────────────────────────────────────────────
  if (archive && archive.organic_carbon_g_kg) {
    buildColumn('col-archive', archive.organic_carbon_g_kg, {
      moist: true,
      lsi: 75,            // 1950 soil was thriving
      mbc: 0.5,
    });
  }
  renderCanopy('canopy-archive', philosophyCanopyMode(selectedPhilosophy, 'archive'));
  renderErosionGhost('erosion-archive', 0);

  // ── Witness (2025) ───────────────────────────────────────────────
  if (profile && profile.organic_carbon_g_kg) {
    buildColumn('col-witness', profile.organic_carbon_g_kg, {
      bd: profile.bulk_density_t_m3,
      moist: false,
      lsi: 40,            // today ≈ tired
      mbc: 0.15,
    });
  }
  renderCanopy('canopy-witness', philosophyCanopyMode(selectedPhilosophy, 'witness'));
  // Tiny "~1cm lost since 1950" ghost on Witness
  renderErosionGhost('erosion-witness', 10, '≈1 cm lost since 1950 →');

  // Titles
  const witnessTitle = document.getElementById('col-witness-title');
  if (witnessTitle && data.years && data.years[0]) {
    witnessTitle.textContent = `${data.years[0]} · today`;
  }
  const oracleTitle = document.getElementById('col-oracle-title');
  if (oracleTitle && data.years) {
    oracleTitle.textContent = `${data.years[data.years.length - 1]} · your future`;
  }

  // ── Oracle (final year) ─────────────────────────────────────────
  if (oracleValues) {
    buildColumn('col-oracle', oracleValues, {
      bd: profile?.bulk_density_t_m3,
      moist: (last(ts.water_retention_mean) || 0) > 25,
      lsi: last(ts.living_soil_index_mean),
      mbc: last(ts.mbc_mean),
    });
  }
  renderCanopy('canopy-oracle', philosophyCanopyMode(selectedPhilosophy, 'oracle'));
  renderErosionGhost('erosion-oracle',
    data.erosion_summary?.topsoil_mm_lost || 0,
    `${(data.erosion_summary?.topsoil_mm_lost || 0).toFixed(0)} mm topsoil lost →`);

  // Root fringe on Oracle if layer-1 SOC is healthy
  const oracleCol = document.getElementById('col-oracle');
  const colEl = oracleCol?.querySelector('.soil-column');
  if (colEl && oracleValues) {
    colEl.classList.toggle('has-roots', oracleValues[1] > 6.5);
  }

  // Events beside Oracle
  renderEventTrack(data.events || []);

  // AI caption + summary
  setAICaption(selectedPhilosophy);
  renderSummary(data);

  // Scrubber + play button
  _setupScrubber(data);
  const playBtn = document.getElementById('btn-play');
  if (playBtn) {
    playBtn.onclick = () => _playAnimation(data);
  }
}

function last(arr) { return (arr && arr.length) ? arr[arr.length - 1] : null; }
