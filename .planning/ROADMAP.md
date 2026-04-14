# Beneath the Surface — Roadmap

## Milestone: Finals Submission (June 2026)

Three phases derived from the literature scan (`research/related_work.md`) and the three gaps in `.planning/REQUIREMENTS.md`.

---

## Phase 1 — Microbial Indicators Module (the novel contribution)

**Goal.** Give the installation a second, independent axis of soil state that a non-expert visitor can read at a glance, and that is genuinely under-explored in both the soil-science literature and the Critical Zones exhibition lineage.

**Deliverables.**
- `backend/soil_model/microbial_indicators.py` — pure derivation layer on top of existing RothC + RF outputs. No new training data.
  - `microbial_biomass_c(soc, clay, moisture, temperature)` → g C / kg soil
  - `fungal_bacterial_ratio(ph, c_n_ratio, tillage_intensity, tree_cover_frac)` → dimensionless
  - `metabolic_quotient(mbc, temperature, moisture_stress)` → mg CO₂-C / g MBC / hour
  - `amf_colonisation_pct(tillage_intensity, p_availability, tree_cover_frac)` → %
  - `living_soil_index(mbc, fb, qco2, amf)` → 0–100 composite used for the visual strip
- Integration in `backend/soil_model/philosophies.py`: each of the 5 management philosophies adjusts the four indicators per published meta-analyses.
- Exposure in `backend/exhibition_api.py`: four new fields + the composite index on the scenario response.
- Frontend "Living Layer" strip rendered beside each acrylic column in `frontend/exhibition/`.
- Citation block at the top of `microbial_indicators.py` listing every empirical relationship used.

**Literature.** Anderson & Domsch (1989, 1990) on MBC and qCO₂; Wardle (1992) on MBC scaling; Bardgett & McAlister (1999) and Fierer et al. (2009) on F:B; Treseder (2004) meta-analysis on AMF and tillage; Liu et al. (2018) on cover crops and MBC.

**Acceptance.**
1. The four indicators differ visibly across the five management philosophies (not just a 1% swing).
2. Indicator direction matches the literature consensus (tillage ↓ F:B, cover crops ↑ MBC, rewild ↑ AMF, etc.).
3. The API returns them for every `/scenario` call without breaking existing consumers.
4. The frontend strip renders next to each column and updates live during the Oracle refill.

---

## Phase 2 — Honest Framing Rewrite

**Goal.** Make the submission defensible to a soil scientist on the jury. Claim what is ours, cite what is not.

**Deliverables.**
- Rewritten `EXHIBITION_SUBMISSION.md` positioning the stack as a reduced-form emulator of peer-reviewed European soil science, claiming the Critical Zones lineage, tying the "AI as mediator" framing to Areti's course brief and Sterman/Rooney-Varga evidence, and citing the 10 recommended references from the scan.
- Updated `PROJECT_REPORT.md` with the same framing corrections.
- A references section with every DOI verified.

**Rules.**
- No language that implies the RF/XGBoost model is a novel contribution to soil science.
- The "93% accuracy" line is dropped until Phase 3 produces a spatial-CV replacement.
- "AI predicts the soil" → "an ML emulator conditioned on IPCC AR6 SSP trajectories interpolates plausible future soil states, constrained to within validated European soil-science envelopes."
- Latour & Weibel (2020) is cited on the first page, not buried in a footnote.

**Acceptance.** Both documents read as honest positioning of an on-brief civic AI pavilion, not as a claim to have invented soil modelling. A reader should come away knowing: (a) what the team built, (b) what existing science it sits on top of, and (c) what the novelty actually is (the medium + the microbial layer + the civic interface).

---

## Phase 3 — Spatial k-Fold Benchmark

**Goal.** Replace the inflated random-split accuracy with an honest spatial-CV number, following Wadoux et al. (2021).

**Deliverables.**
- A benchmark script (`backend/ml_models/spatial_cv_benchmark.py`) that re-evaluates the RF classifier with geographic-tile-blocked k-fold CV.
- A short `backend/ml_models/BENCHMARK.md` recording the honest accuracy number with the methodology used and the Wadoux et al. reference.
- Updated accuracy line in both markdown documents rewritten in Phase 2.

**Acceptance.** The benchmark uses at least 5-fold spatial CV with non-adjacent fold assignment. The number in the deck matches the number in the benchmark report. If it drops below a level the team wants to publish, we drop the claim instead of spinning it.

---

## Phase 10 — Exhibition 3D Visual Upgrade

**Goal.** Replace the flat 2D exhibition result panel with a cinematic hybrid 3D experience: pre-rendered painterly Blender attract loop → seamless handoff → interactive Three.js soil column with morphing year-slider → microbial dive-in. Every visual must pass the "random visitor understands it in 3 seconds" test.

**Design doc.** `docs/plans/2026-04-15-exhibition-3d-visuals-design.md` — approved via brainstorm 2026-04-15. Read this first; it is the source of truth for every decision below.

**Deliverables.**
- `backend/assets/nano_banana_factory.py` — Python script that calls Gemini 2.5 Flash Image API to generate painterly textures in batches using one style anchor for consistency. Reads `GEMINI_API_KEY` from env; key never committed.
- `backend/assets/asset_manifest.json` — maps `(philosophy, ssp, year_bucket)` tuples to texture filenames.
- `backend/assets/prompts/` — prompt templates per asset kind (ground, sky, root brushwork, particles).
- `backend/assets/anchor_style.png` — the one hero painting, used as style reference in every Nano Banana call.
- `frontend/exhibition/scene3d/` — vanilla-JS Three.js layer: `main.js`, `soil_column.js`, `particles.js`, `camera_director.js`, `handoff.js`, plus painterly vert/frag shaders.
- `frontend/exhibition/assets/textures/` — generated Nano Banana textures (gitignored after anchor is locked).
- `frontend/exhibition/assets/videos/attract_loop.mp4` — Blender-rendered 40s seamless cinematic of the three futures diverging.
- `frontend/exhibition/assets/labels.json` — all on-screen text in plain language, no jargon.
- `blender/soil_futures.blend` + `blender/render_attract_loop.py` — shared scene and automated render script.
- Updated `frontend/exhibition/index.html` wiring the new scene3d layer next to the existing 2D flow.

**Three scenes (one shared soil-column asset, three camera modes).**
- **Scene A — Attract loop.** Pre-rendered Blender. Three columns diverging over 50 years. Plain-language labels: "IF WE KEEP DOING NOTHING" / "IF WE REGENERATE THE LAND" / "IF WE OVER-FARM".
- **Scene B — Focused column.** Three.js real-time. Visitor touches, other two dissolve, year-slider morphs the chosen column in real time.
- **Scene C — Microbial dive-in.** Three.js real-time. Camera flies into the surface. Healthy = dense, glowing, moving. Degraded = empty, still, dim.

**Legibility rules (non-negotiable).**
1. Every hero scene has a plain-language label on-screen. No jargon.
2. Healthy vs degraded is visible without reading — color does 80% of the work.
3. Movement = life. Healthy pulses and flows. Degraded is still.
4. One idea per scene, max.
5. Kill anything that needs a caption to be understood.

**Source of truth.** The visuals read `backend/soil_model/engine.py` output via the existing simulation JSON. This phase never recomputes soil state.

**Timeline.** 9 weeks. Week 1 has a user decision gate on the Nano Banana anchor style.

**Risks.** Anchor style not good enough (mitigation: Week 1 gate); handoff janky on hardware (mitigation: test Week 8 not Week 9); shader eats frame rate (mitigation: bake effect into textures); legibility test fails on real visitor (mitigation: Week 9 non-technical viewer test); scope creep (mitigation: say no).

**Depends on.** Phase 1 (Microbial Indicators) — the dive-in scene visualizes those indicators directly. Also depends on a Gemini API key being provided by the user at the end of Week 1.

**Acceptance.**
1. A visitor walks up to the screen, watches the attract loop for 40 seconds, and can name which of the three futures is healthy and which are dying — without reading any explanation beyond the three plain-language labels.
2. Touching a column on the screen transitions into the interactive Three.js scene with no visible seam (no black flash, no geometric jump).
3. Dragging the year slider morphs the soil column's appearance in real time at 60fps on the exhibition GPU laptop.
4. Tapping the column flies the camera into the microbial dive-in; the visual density of the dive-in differs obviously between healthy and degraded futures.
5. The painterly visual style is consistent across all textures (anchor style enforced across every Nano Banana call).
6. A non-technical viewer (tested Week 9) can explain what each scene means in their own words after watching the full journey once.
7. The full 9-week timeline completes with at least 1 week of buffer preserved for polish and bugfixes.

---

## Dependency graph

```
Phase 1 (microbial)  ────┬──► Phase 2 (docs) — needs microbial story + final accuracy
                         │
Phase 3 (spatial CV) ────┘

Phase 1 (microbial)  ────► Phase 10 (3D visual upgrade) — dive-in scene visualizes microbial indicators
```

Phase 1 and Phase 3 are independent and can run in parallel. Phase 2 waits on both. Phase 10 is the new exhibition visual overhaul and depends only on Phase 1.

## Out of scope for this milestone

- Switching RothC to MIMICS or MEND (next cycle)
- Arduino firmware (hardware team)
- XGBoost spatiotemporal retrain (separate branch)
- Visitor UAT (post-assembly)
