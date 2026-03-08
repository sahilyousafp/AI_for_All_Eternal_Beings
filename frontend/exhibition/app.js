/**
 * Phase management and philosophy/scenario selection.
 */

const API_BASE = window.location.origin.startsWith('http')
  ? window.location.origin
  : 'http://localhost:8000';

let selectedPhilosophy  = null;
let selectedScenario    = null;

// ── Phase navigation ───────────────────────────────────────────────────────

function showPhase(n) {
  document.querySelectorAll('.phase').forEach(el => el.classList.remove('active'));
  const el = document.getElementById(`phase-${n}`);
  if (el) el.classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Load philosophies ──────────────────────────────────────────────────────

async function loadPhilosophies() {
  try {
    const res  = await fetch(`${API_BASE}/api/exhibition/philosophies`);
    const data = await res.json();
    const grid = document.getElementById('philosophies-grid');
    grid.innerHTML = '';
    for (const p of data.philosophies) {
      const card = document.createElement('div');
      card.className = 'card';
      card.innerHTML = `
        <div class="icon">${p.icon}</div>
        <h3>${p.display_name}</h3>
        <p>${p.description}</p>
        ${p.expected_50yr ? `<small style="color:var(--accent);font-size:0.75rem;margin-top:0.5rem;display:block;">
          SOC ${p.expected_50yr.soc_change_pct > 0 ? '+' : ''}${p.expected_50yr.soc_change_pct}% ·
          Erosion ${p.expected_50yr.erosion_change_pct}% ·
          Biodiversity ${p.expected_50yr.biodiversity_change_pct > 0 ? '+' : ''}${p.expected_50yr.biodiversity_change_pct}%
        </small>` : ''}
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
      const card = document.createElement('div');
      card.className = 'card';
      card.style.borderLeftColor = s.color;
      card.innerHTML = `
        <h3 style="color:${s.color}">${s.name}</h3>
        <p>${s.description}</p>
        <small style="color:var(--muted);font-size:0.75rem;margin-top:0.5rem;display:block;">
          2100: ΔT +${s.delta_T_2100}°C · Precip ${s.delta_P_2100}%
        </small>
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
  document.getElementById('sim-title').textContent =
    `Simulating: ${selectedPhilosophy.replace(/_/g, ' ')} × ${selectedScenario.toUpperCase()}`;
  showPhase(3);
});

// ── Init ──────────────────────────────────────────────────────────────────

loadPhilosophies();
