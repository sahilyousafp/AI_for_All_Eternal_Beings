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

## Dependency graph

```
Phase 1 (microbial)  ────┐
                         ├──► Phase 2 (docs) — needs microbial story + final accuracy
Phase 3 (spatial CV) ────┘
```

Phase 1 and Phase 3 are independent and can run in parallel. Phase 2 waits on both.

## Out of scope for this milestone

- Switching RothC to MIMICS or MEND (next cycle)
- Arduino firmware (hardware team)
- XGBoost spatiotemporal retrain (separate branch)
- Visitor UAT (post-assembly)
