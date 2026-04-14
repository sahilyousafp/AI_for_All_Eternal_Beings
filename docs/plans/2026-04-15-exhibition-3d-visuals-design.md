# Exhibition 3D Visual Upgrade — Design

**Date:** 2026-04-15
**Author:** brainstorming session (Rafik + Claude, via Telegram)
**Status:** Approved — ready for GSD phase planning
**Branch:** v6.7

## Context

The Soil Futures exhibition frontend (`frontend/exhibition/`) currently
presents the soil-simulation results as a 2D layout: philosophy picker →
SSP climate picker → simulation output panel with a "Living Layer" strip.
The simulation engine and data pipeline are production quality, but the
visual layer is flat and does not carry the emotional weight the
installation is aiming for.

This design describes a full 3D visual upgrade that replaces the current
2D result panel with a cinematic hybrid experience: a pre-rendered
painterly attract loop that hands off seamlessly into an interactive
Three.js scene of the visitor's chosen future, with a microbial dive-in
as the emotional payoff.

Core constraint: **every visual must pass the "random visitor understands
it in 3 seconds" test.** Beauty is not enough. Clarity is the higher bar.

## Decisions locked during brainstorm

| Question | Answer |
|----------|--------|
| Target hardware | One big screen, decent modern laptop / mini PC with a real GPU |
| Interaction model | Hybrid: cinematic attract loop when idle → interactive on touch |
| Hero scenes | (a) rotating soil column, (c) three futures side-by-side, (d) microbial dive-in — collapsed into ONE shared asset with three camera modes |
| Visual style | Painterly (Ghibli × Björk Biophilia), not photoreal, not neon data-viz |
| Timeline | 9 weeks (fits user's "2+ months" comfortably with buffer) |
| Technical approach | Approach 3: Three.js real-time interactive + pre-rendered Blender attract loop + Nano Banana painterly texture factory |
| Nano Banana's role | Generates painterly 2D textures (ground, sky, root brushwork, particles) used by BOTH Blender and Three.js pipelines. NOT 3D assets, NOT animations. |
| Frontend framework | None. Stays vanilla JS. Three.js loaded as ESM. No React/R3F rewrite. |
| Source of truth | Existing Python soil simulation — visuals read `sim_output.json`, never second-guess it |

## Legibility rules (non-negotiable)

1. Every hero scene has a plain-language label on-screen. No jargon.
2. Healthy vs degraded is visible without reading — color does 80% of the work.
3. Movement = life. Healthy pulses, flows, glows. Degraded is still.
4. One idea per scene, max. Three scenes, three ideas, zero overlap.
5. Kill anything that needs a caption to be understood.

## Architecture

```
 ┌─────────────────────────────┐
 │  Nano Banana asset factory  │  Python script calls Gemini 2.5
 │  (painterly textures, skies,│  Flash Image API, generates PNGs
 │   root paintings, particles)│  in batches with a style anchor
 └──────────┬──────────────────┘
            │ shared PNG library
    ┌───────┴───────┐
    ▼               ▼
 ┌────────┐    ┌─────────────┐
 │Blender │    │ Three.js    │
 │(attract│    │ (interactive│
 │ loop)  │    │  scenes B+C)│
 └───┬────┘    └──────┬──────┘
     │                │
     │   .mp4 loop    │  live WebGL
     └───────┬────────┘
             ▼
    ┌────────────────────┐
    │  Exhibition HTML   │
    │  (vanilla JS shell)│
    │  + handoff manager │
    └────────────────────┘
```

### Data flow

```
backend/soil_model/engine.py
    ↓ runs for every (philosophy, ssp, year)
backend/soil_model/sim_output.json  (single source of truth)
    ↓ consumed by:
    ├── nano_banana_factory.py   (selects prompt variants per state)
    ├── render_attract_loop.py   (bakes state into the 40s video)
    └── frontend scene3d/*       (real-time morphing per slider value)
```

The sim is still the brain. This design never recomputes soil state —
it just visualizes whatever `engine.py` already decided. Changing the
model tomorrow automatically updates the visuals.

## The three scenes

### Scene A — Attract loop: "Three Futures" (pre-rendered Blender video)

Three soil columns floating in a soft painterly dark space, slowly
rotating. Above each one, a plain-language label:
- "IF WE KEEP DOING NOTHING"
- "IF WE REGENERATE THE LAND"
- "IF WE OVER-FARM"

A year counter ticks 2026 → 2076 over 40 seconds. The three columns
visibly diverge. Regenerative grows roots deeper, glows warmer,
mycelium threads appear. "Nothing" cracks. "Over-farm" collapses
inward. Loop ends on a held frame: "TOUCH A COLUMN TO SEE WHY."

**Legibility:** three futures side by side — viewer compares without
thinking. Labels are verbs a 10-year-old understands.

### Scene B — Focused column: "Your chosen future" (Three.js real-time)

Visitor touches a column. The other two dissolve into particles and
drift offscreen. The chosen column floats to center. Label updates:
"THIS IS WHAT [REGENERATION] DOES TO THE GROUND IN 50 YEARS." A
vertical year-slider lets them scrub 2026 ↔ 2076 — as they drag, the
column morphs in real time. Healthy = dark rich brown, visible root
hairs, warm glow. Degraded = cracked, pale, still.

One tap on the column itself triggers Scene C.

**Legibility:** one column, one label, one slider. Nothing else on
screen. The morph is physical — they see it change under their finger.

### Scene C — The dive-in: "The ground is alive" (Three.js real-time)

Camera flies INTO the surface. The world gets quiet. We're inside the
soil at microbial scale. Painterly glowing particles = bacteria.
Threading golden strands = mycorrhizae. Pulsing orbs = carbon pockets.
Water trickles as sparkling lines. Everything moves and pulses softly.

Label: "INSIDE ONE TEASPOON OF HEALTHY SOIL LIVES MORE LIFE THAN
PEOPLE ON EARTH."

If the chosen future is "over-farm" or "do nothing," the dive-in is
visibly emptier. Fewer particles, slower movement, dimmer light.
Label: "THIS TEASPOON IS ALMOST EMPTY." Zero jargon. The visitor
feels the loss.

Tap anywhere to fly back to Scene B. After 30s idle → back to Scene A.

**Legibility:** dense + moving + glowing = alive. Empty + still + dim
= dead. The one fact in the label is a real, memorable number.

## Tech stack additions

- `three` (Three.js core) via ESM CDN — no build step
- `gsap` for camera animations and scene transitions
- `blender` 4.x (local, offline) for pre-rendering the attract loop
- `google-genai` Python SDK for the Nano Banana factory script

No framework rewrite. No bundler. Drops straight into
`frontend/exhibition/`.

## File layout

```
backend/assets/
  nano_banana_factory.py      # Generates textures via Gemini API
  asset_manifest.json         # Maps (philosophy, ssp, year) → filenames
  prompts/                    # Prompt templates per asset kind
  anchor_style.png            # Hero painting; style reference for all calls

frontend/exhibition/
  scene3d/
    main.js                   # Three.js bootstrap + scene manager
    soil_column.js            # Procedural mesh + shader
    particles.js              # GPU particle system
    camera_director.js        # GSAP camera choreography
    handoff.js                # Video ↔ real-time transition
    shaders/
      painterly.vert/frag     # Custom painterly shader
  assets/
    textures/                 # Nano Banana output
    videos/
      attract_loop.mp4        # Blender render, seamless loop
    labels.json               # All on-screen text, plain language

blender/
  soil_futures.blend          # Shared scene file
  render_attract_loop.py      # Automated render script
```

## The invisible handoff (the hard part of Approach 3)

1. Blender renders the attract loop ending on a "neutral pose" frame
   (three columns, 45° camera, warm rim light) — numbers locked.
2. The Three.js scene boots in the background BEFORE the video ends,
   pre-warming shaders and loading textures.
3. When a visitor touches the screen: video freezes on its last frame,
   Three.js canvas fades in over 300ms with camera already at the
   matched neutral pose.
4. Both pipelines use the SAME Nano Banana textures → tonal match
   automatic. Locked camera/lighting → geometric match automatic.
5. 300ms cross-dissolve hides any remaining seam.

## 9-week timeline

| Week | Work | Milestone |
|------|------|-----------|
| 1 | Scene3d scaffold, Three.js loading, Nano Banana factory script, 4 anchor style candidates | **User decision gate: pick the anchor style** |
| 2 | Generate 120+ painterly textures in batches using anchor as style reference. Build asset manifest. | Texture library complete |
| 3-4 | Painterly shader, procedural soil column, real-time morph slider, Scene B labels | **Scene B demo-able as real interactive thing** |
| 5 | GPU particle system, dive-in camera choreography, healthy/dying visual contrast | **The dive-in feels alive** |
| 6-7 | Blender attract loop: scene setup, render script, first full 40s render | **Full visitor journey showable end to end** |
| 8 | Handoff: lock end-frame geometry, implement handoff.js, test on exhibition hardware | Seamless video → real-time |
| 9 | Copy review, legibility test on non-technical viewer, performance pass (60fps), idle reset, buffer | **Exhibition ready** |

## Risks and mitigations

1. **Anchor style isn't good enough.** Week 1 decision gate. Iterate
   until it sings BEFORE generating 120 textures. Painful to redo later.
2. **Handoff visibly janky on exhibition hardware.** Test on real
   hardware at week 8, not week 9. Fallback: skip video entirely, boot
   straight into Three.js attract loop.
3. **Painterly shader eats frame rate.** Measure on GPU laptop in week 3
   as soon as the shader exists. If slow, bake the painterly effect
   into the textures (Nano Banana already does this) instead of
   running per-frame.
4. **"Super understandable" test fails on real visitor.** Week 9 test
   with a non-technical family member or kid. Iterate labels based on
   what confuses them.
5. **Scope creep — someone asks for a fourth scene.** Say no. Three
   scenes done well beats five done badly.

## Explicit non-goals

- Not switching to React/R3F. Vanilla JS stays.
- Not photoreal. Painterly is deliberate.
- Not 3D from Nano Banana. Nano Banana is a 2D texture factory.
- Not replacing the simulation engine — the visuals read its output.
- Not shipping the Blender source to the exhibition machine — only
  the rendered mp4.
- Not adding a fourth hero scene. Three scenes, three ideas.

## Next step

Invoke `/gsd-add-phase` to register this as a phase on the roadmap,
then `/gsd-plan-phase` to produce a week-by-week task breakdown
(PLAN.md), then begin Week 1 execution.
