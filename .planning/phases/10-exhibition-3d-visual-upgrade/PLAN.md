# Phase 10 — Exhibition 3D Visual Upgrade — PLAN

**Design doc:** `docs/plans/2026-04-15-exhibition-3d-visuals-design.md`
**Goal:** Hybrid Three.js real-time + pre-rendered Blender cinematic exhibition with Nano Banana texture factory. Painterly style. Every visual passes the 3-second legibility test.

## Task breakdown — 9 weeks

### Week 1 — Foundation & anchor style gate

**1.1 Backend asset factory scaffold** (Claude, autonomous)
- Create `backend/assets/` directory
- Create `backend/assets/prompts/` with prompt template files:
  - `ground_texture.txt` — painterly soil cross-section, parameterized by (philosophy, degradation_level, year)
  - `sky_scenario.txt` — painterly sky per SSP climate scenario
  - `root_brushwork.txt` — transparent-bg root system overlays
  - `particle_sprites.txt` — glowing microbe/carbon/water sprite sheets
  - `anchor_style.txt` — the one hero image used as style reference
- Write `backend/assets/nano_banana_factory.py`:
  - Reads `GEMINI_API_KEY` from env (fails loudly if missing)
  - Uses `google-genai` SDK, model `gemini-2.5-flash-image`
  - Two modes: `--mode anchor` (generates N candidate anchors) and `--mode batch` (generates textures using an existing anchor as style reference)
  - Writes outputs to `frontend/exhibition/assets/textures/`
  - Maintains `backend/assets/asset_manifest.json` mapping (philosophy, ssp, year_bucket) → filename
  - Idempotent: skips filenames that already exist unless `--force`
- Add `google-genai` to `requirements.txt`
- Update `.gitignore`: exclude `frontend/exhibition/assets/textures/*.png` (generated) and `.env`
- Create `.env.example` with `GEMINI_API_KEY=` placeholder

**1.2 Frontend Three.js scaffold** (Claude, autonomous)
- Create `frontend/exhibition/scene3d/` directory
- Create `scene3d/main.js` — Three.js bootstrap, placeholder soil column, orbit controls for dev
- Create `scene3d/soil_column.js` — stub procedural mesh class
- Create `scene3d/particles.js` — stub GPU particle system
- Create `scene3d/camera_director.js` — stub GSAP camera choreography
- Create `scene3d/handoff.js` — stub video↔real-time transition manager
- Create `scene3d/shaders/painterly.vert` and `.frag` — minimal pass-through for now
- Update `frontend/exhibition/index.html`: add a `<canvas id="scene3d"></canvas>` hidden by default, import `scene3d/main.js` as ESM module
- Verify the existing 2D exhibition flow still works unchanged (critical: do not break what ships)

**1.3 Anchor style candidate generation** (user-gated)
- Once user provides `GEMINI_API_KEY`, run: `python backend/assets/nano_banana_factory.py --mode anchor --n 4`
- Produces 4 candidate anchor paintings in `backend/assets/anchor_candidates/`
- **User decision gate:** Rafik picks ONE candidate as `anchor_style.png`. Or asks for 4 more. Do NOT proceed to 1.4 without this.

**1.4 Week 1 commit and milestone** (Claude, autonomous after gate)
- Commit anchor_style.png to repo
- Tag the commit as `phase10-week1-anchor-locked`

### Week 2 — Texture library generation

**2.1 Batch texture generation** (user-gated: needs anchor locked + API key)
- Run `python backend/assets/nano_banana_factory.py --mode batch`
- Generates ~120 textures: 5 philosophies × 4 SSP × 6 year buckets for ground; plus sky variants, root overlays, particle sprites
- All use anchor_style.png as style reference in every call
- Populates `asset_manifest.json`

**2.2 QA pass** (Claude)
- Scan every generated texture programmatically for failures (empty files, wrong dimensions)
- Generate an HTML grid viewer `backend/assets/texture_grid.html` showing every texture with its (philosophy, ssp, year) label
- User opens this in browser, flags any that look wrong, regenerate flagged ones

### Weeks 3–4 — Painterly shader + soil column (Scene B)

**3.1 Painterly shader** (Claude)
- Write `painterly.vert` and `.frag` implementing: edge ink lines (fresnel-based), stylized cel-shading, texture stylization mixing generated ground texture with vertex color
- Test shader on a simple cube before applying to the column
- **Performance check:** measure fps on the exhibition GPU laptop. If below 60fps, cut shader complexity.

**3.2 Procedural soil column mesh** (Claude)
- `soil_column.js`: class that builds a cylindrical cross-section mesh parameterized by (philosophy, ssp, year)
- Reads from existing `sim_output.json` format — DO NOT invent new sim fields
- Applies correct ground texture from manifest based on state
- Supports tween interpolation between (year_n, year_n+1) for smooth slider scrubbing

**3.3 Year slider + Scene B integration** (Claude)
- Vertical year slider on right side of canvas
- Dragging morphs the column in real time
- Plain-language label updates: "THIS IS WHAT [philosophy name] DOES TO THE GROUND IN [current year-2026] YEARS"
- Labels pulled from `assets/labels.json`, not hardcoded

**3.4 Week 4 demo milestone** (Claude)
- Scene B works end-to-end as a demo page
- Commit `phase10-week4-scene-b-demoable`

### Week 5 — The dive-in (Scene C)

**5.1 GPU particle system** (Claude)
- `particles.js`: instanced particles using Nano Banana sprite sheets
- Three particle types: bacteria (round glowing), mycorrhizae (threading strands via ribbon geometry), carbon pockets (pulsing orbs)
- Water as animated sparkling lines
- Count/density/brightness parameterized by microbial indicator values from sim

**5.2 Fly-in camera** (Claude)
- `camera_director.js`: GSAP timeline for the dive-in choreography
- Smooth transition from Scene B orbit camera to Scene C internal view
- Tap anywhere to exit back to Scene B
- 30s idle timer to return to attract loop

**5.3 Healthy vs degraded contrast** (Claude)
- Test with extreme cases: best regenerative future vs worst degraded
- Verify visual contrast is OBVIOUS without reading labels (the core legibility test)
- Label logic: "INSIDE ONE TEASPOON OF HEALTHY SOIL..." vs "THIS TEASPOON IS ALMOST EMPTY"

**5.4 Week 5 milestone**
- The dive-in feels alive. Commit `phase10-week5-dive-in-alive`.

### Weeks 6–7 — Blender attract loop (Scene A)

**6.1 Blender scene setup** (Claude + user)
- Create `blender/soil_futures.blend` — three soil columns in painterly lighting
- Import Nano Banana textures via the shared asset folder
- Match the shader look of Three.js as closely as Cycles/Eevee allows (goal: tonal match so handoff looks seamless)

**6.2 Automated render script** (Claude)
- `blender/render_attract_loop.py`: drives Blender headless, reads sim output, renders 40s × 60fps = 2400 frames
- Ffmpeg-encode to h264 mp4, seamless loop
- Final output: `frontend/exhibition/assets/videos/attract_loop.mp4`

**6.3 First full render** (user: start the long-running render job)
- Overnight render
- Review next morning. Iterate.

**6.4 Week 7 milestone**
- Full visitor journey showable end-to-end (manually trigger each scene). Commit `phase10-week7-journey-showable`.

### Week 8 — The invisible handoff

**8.1 Lock geometry** (Claude)
- Define the "neutral pose" frame numbers: camera position (0, 2.5, 6), target (0, 1, 0), lighting color (warm #f5cd8a, intensity 0.8)
- Both pipelines MUST exit/enter this exact pose
- Encode these as constants in `handoff.js` AND `blender/render_attract_loop.py`

**8.2 Handoff manager** (Claude)
- `handoff.js`: preload Three.js scene while video plays last 2 seconds
- On touch: freeze video, fade Three.js in over 300ms, start Scene B at the neutral pose
- Test seam visually

**8.3 Hardware test** (user + Claude)
- **Critical:** test on actual exhibition GPU laptop, not dev machine
- If seam is janky: tune dissolve timing, or lock more tightly
- Fallback: skip video, boot straight into Three.js with a simpler attract loop

### Week 9 — Polish + legibility test + buffer

**9.1 Legibility test with non-technical viewer** (user-led)
- Find someone outside the project — ideally a kid or non-technical family member
- Have them watch the full journey once, then ask them to explain what each scene means in their own words
- Any confusion = rewrite the offending label. Do not argue with what they didn't understand.

**9.2 Performance pass** (Claude)
- Profile on exhibition GPU laptop
- Target 60fps in Scene B and Scene C
- If slow: reduce particle count, simplify shader, bake more into textures

**9.3 Idle reset logic** (Claude)
- 30s no-touch in Scene B or C → fade back to attract loop
- Also resets all state so next visitor starts clean

**9.4 Bugfix buffer**
- Whatever broke. Fix it.

**9.5 Final commit**
- Tag `phase10-complete`

## Dependencies & user-gated checkpoints

- **Gate 1 (end of Week 1):** user picks anchor style from 4 candidates — EVERYTHING downstream blocks on this
- **Gate 2 (Week 2):** user reviews generated texture grid, flags any to regenerate
- **Gate 3 (Week 6):** user provides Blender access / runs the overnight render
- **Gate 4 (Week 8):** user provides access to the exhibition hardware for seam testing
- **Gate 5 (Week 9):** user finds a non-technical viewer for the legibility test

## Out of scope (explicit)

- Switching to React/R3F framework
- Photoreal or neon data-viz style
- 3D models from Nano Banana (it's 2D only)
- Replacing or modifying the soil simulation engine
- Shipping .blend files to the exhibition machine
- A fourth hero scene

## Source of truth

`docs/plans/2026-04-15-exhibition-3d-visuals-design.md` — if this PLAN.md conflicts with the design doc, the design doc wins.
