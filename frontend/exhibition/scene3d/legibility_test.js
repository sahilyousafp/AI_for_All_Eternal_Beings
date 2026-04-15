// Phase 10 — Week 9 legibility test harness.
//
// Tool for testing the exhibition on a non-technical viewer. Runs a
// scripted sequence through the 3 scenes while capturing timestamped
// notes you type as the viewer watches. The goal: catch any label or
// visual that doesn't pass the "random visitor understands it in 3
// seconds" test.
//
// Load from the browser console:
//   import('/frontend/exhibition/scene3d/legibility_test.js')
//     .then(m => m.startLegibilityTest(window.__scene3d))
//
// Or wire a hidden dev button in index.html.

const STEPS = [
  {
    mode: 'idle',
    duration: 42,
    question: 'What do you think the three columns mean?',
  },
  {
    mode: 'focused',
    context: { philosophy: 'regenerative', years: 50 },
    duration: 12,
    question: 'What is this showing you about the ground?',
  },
  {
    mode: 'dive',
    context: { healthy: true },
    duration: 10,
    question: 'What is this place? What is the glowing stuff?',
  },
  {
    mode: 'focused',
    context: { philosophy: 'over_farm', years: 50 },
    duration: 12,
    question: 'What is different from the healthy one?',
  },
  {
    mode: 'dive',
    context: { healthy: false },
    duration: 10,
    question: 'What do you feel now compared to the glowing one?',
  },
];

export async function startLegibilityTest(scene3d) {
  if (!scene3d) {
    console.error('[legibility] scene3d not provided');
    return;
  }

  const notes = [];
  const ui = scene3d.ui;
  if (!ui) {
    console.error('[legibility] UI overlay not attached yet');
    return;
  }

  console.group('%c Legibility Test Started', 'background: #a3e635; color: black; padding: 4px 8px;');
  console.info('For each step:');
  console.info('  1. Ask the viewer the question shown.');
  console.info('  2. Call window.__noteLegibility("their answer") while they speak.');
  console.info('  3. Press any key in this tab to move to the next step.');
  console.groupEnd();

  window.__noteLegibility = (text) => {
    const entry = { step: currentStepIdx, text, t: Date.now() };
    notes.push(entry);
    console.log(`  noted [step ${currentStepIdx}]: ${text}`);
  };

  let currentStepIdx = 0;
  for (const step of STEPS) {
    console.group(`%c Step ${currentStepIdx + 1}/${STEPS.length} — ${step.mode}`,
                  'color: #f5cd8a; font-weight: bold;');
    console.info(`Question: ${step.question}`);
    ui.setMode(step.mode, step.context ?? {});
    if (step.mode === 'idle') {
      ui.setClock(0);
      setTimeout(() => ui.setClock(50), step.duration * 500);
    }
    await waitOrKey(step.duration * 1000);
    console.groupEnd();
    currentStepIdx++;
  }

  console.group('%c Legibility Test Complete', 'background: #22d3ee; color: black; padding: 4px 8px;');
  console.log('Collected notes:');
  console.table(notes);
  console.log('\nNotes JSON (copy to save):');
  console.log(JSON.stringify(notes, null, 2));
  console.groupEnd();

  return notes;
}

function waitOrKey(ms) {
  return new Promise((resolve) => {
    let done = false;
    const timer = setTimeout(() => {
      if (done) return;
      done = true;
      document.removeEventListener('keydown', onKey);
      resolve();
    }, ms);
    const onKey = () => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      document.removeEventListener('keydown', onKey);
      resolve();
    };
    document.addEventListener('keydown', onKey, { once: true });
  });
}
