/**
 * Phase management and philosophy/scenario selection.
 * Kiosk app: data comes from our own local backend (trusted), but we still
 * HTML-escape every injected string as defense-in-depth.
 */

const API_BASE = 'http://127.0.0.1:8001';

let selectedPhilosophy  = null;
let selectedScenario    = null;
let _philosophyData     = {};
let _scenarioData       = {};

// ── Escape helper ─────────────────────────────────────────────────────────
function esc(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ── Phase navigation ───────────────────────────────────────────────────────

function showPhase(n) {
  document.querySelectorAll('.phase').forEach(el => el.classList.remove('active'));
  const el = document.getElementById(`phase-${n}`);
  if (el) el.classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Helpers ────────────────────────────────────────────────────────────────

function plainPct(label, v, invert) {
  if (v == null) return '';
  const sign = v > 0 ? '+' : '';
  const isGood = invert ? v < 0 : v > 0;
  const cls = v === 0 ? '' : (isGood ? ' good' : ' bad');
  return `<span class="chip${cls}">${esc(label)} ${sign}${Number(v)}%</span>`;
}

// ── Load philosophies ──────────────────────────────────────────────────────

async function loadPhilosophies() {
  const grid = document.getElementById('philosophies-grid');
  grid.innerHTML = '<p style="grid-column:1/-1;color:var(--muted);font-size:0.9rem;text-align:center;padding:2rem;">Waking up the soil model…</p>';
  try {
    const res  = await fetch(`${API_BASE}/api/exhibition/philosophies`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    grid.innerHTML = '';
    for (const p of data.philosophies) {
      _philosophyData[p.id] = p;
      const e = p.expected_50yr || {};
      const card = document.createElement('div');
      card.className = 'card philosophy';
      card.innerHTML = `
        <div class="icon">${esc(p.icon)}</div>
        <h3>${esc(p.display_name)}</h3>
        ${p.tagline ? `<div class="tagline">${esc(p.tagline)}</div>` : ''}
        <p class="description">${esc(p.description)}</p>
        <div class="stat-chips">
          ${plainPct('Carbon', e.soc_change_pct, false)}
          ${plainPct('Erosion', e.erosion_change_pct, true)}
          ${plainPct('Life', e.biodiversity_change_pct, false)}
        </div>
      `;
      card.addEventListener('click', () => {
        document.querySelectorAll('#philosophies-grid .card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        selectedPhilosophy = p.id;
        document.getElementById('btn-to-climate').disabled = false;
      });
      grid.appendChild(card);
    }
  } catch (e) {
    console.error('Failed to load philosophies:', e);
    grid.innerHTML = `
      <div style="grid-column:1/-1;padding:1.5rem;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.3);border-radius:12px;color:#fca5a5;">
        <strong>The soil model isn't running yet.</strong><br>
        <span style="font-size:0.82rem;color:var(--muted);">
          Start the server first:<br>
          <code style="color:#e8e8e8;">ai4all/Scripts/python.exe -m uvicorn backend.app:app --port 8001</code>
        </span>
      </div>`;
  }
}

// ── Load climate scenarios ─────────────────────────────────────────────────

async function loadScenarios() {
  try {
    const res  = await fetch(`${API_BASE}/api/exhibition/climate-scenarios`);
    const data = await res.json();
    const grid = document.getElementById('scenarios-grid');
    grid.innerHTML = '';
    for (const s of data.scenarios) {
      _scenarioData[s.id] = s;
      const card = document.createElement('div');
      card.className = 'card scenario';
      card.style.setProperty('--card-stripe', s.color);
      card.innerHTML = `
        ${s.subtitle ? `<div class="subtitle-small">${esc(s.subtitle)}</div>` : ''}
        <h3>${esc(s.name)}</h3>
        ${s.tagline ? `<div class="tagline" style="color:${esc(s.color)}">${esc(s.tagline)}</div>` : ''}
        <p class="description">${esc(s.description)}</p>
        ${s.tech_label ? `<span class="tech-label">${esc(s.tech_label)}</span>` : ''}
      `;
      card.addEventListener('click', () => {
        document.querySelectorAll('#scenarios-grid .card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        selectedScenario = s.id;
        document.getElementById('btn-to-sim').disabled = false;
      });
      grid.appendChild(card);
    }
  } catch (e) {
    console.error('Failed to load scenarios:', e);
  }
}

// ── Navigation buttons ─────────────────────────────────────────────────────

document.getElementById('btn-to-climate').addEventListener('click', () => {
  loadScenarios();
  showPhase(2);
});

document.getElementById('btn-to-sim').addEventListener('click', () => {
  if (!selectedPhilosophy || !selectedScenario) return;
  const p = _philosophyData[selectedPhilosophy];
  const s = _scenarioData[selectedScenario];
  const comboP = document.getElementById('combo-philosophy');
  const comboS = document.getElementById('combo-scenario');
  if (comboP) comboP.textContent = p ? `${p.icon} ${p.display_name}` : selectedPhilosophy;
  if (comboS) comboS.textContent = s ? s.name : selectedScenario;
  showPhase(3);
});

// ── Init ──────────────────────────────────────────────────────────────────

loadPhilosophies();
