# Beneath the Surface — Requirements

## Success criteria (derived from course brief + submission deadline)

The installation succeeds if, by June 2026:

1. **Legibility.** A non-expert visitor understands within 10 seconds what the columns show, and within 2 minutes understands that their scenario choice produced a specific predicted outcome different from the alternatives.
2. **Contestability.** Uncertainty is visibly part of the prediction, not hidden. The visitor sees "what the AI doesn't know" as clearly as what it claims to know.
3. **Debatability.** The five management scenarios differ visibly on multiple axes (carbon, water, microbial life), so the visitor has *something to argue with*.
4. **Participation.** The interaction is a real choice — the servos actually refill the column differently based on visitor input, not a pre-rendered video.
5. **Academic defensibility.** The submission survives a soil scientist reading it. The technical stack is positioned as a reduced-form emulator of peer-reviewed European soil science, not as novel research. Accuracy claims are backed by spatial CV, not random-split CV.

## Outstanding gaps (the three workstreams)

### Gap A — Single-axis story
The columns currently only tell a carbon story. That is one number on one axis. The course brief asks for legibility, which means **more than one dial**. The microbial indicators workstream adds a second axis (living vs. stressed soil) that a 10-year-old can read and that no precedent exhibition or paper covers in this way. This is also the most defensible originality claim the team can make.

### Gap B — Framing language overreaches
The current deck says "AI predicts the soil" and claims the model is novel. The literature scan disagrees — Lugato 2014 already did the scenario branching, Poggio 2021 is our training data, and the RF layer is a deployment of existing science. The deck must be rewritten to claim what is actually ours (the medium, the microbial layer, the civic interface) and cite what is not (Lugato, Bruni, Poggio, Critical Zones).

### Gap C — Inflated accuracy headline
"93% test accuracy" is almost certainly the result of random-split CV on spatially autocorrelated SoilGrids pixels. Under spatial k-fold CV the number will drop — possibly significantly. Wadoux et al. (2021) is explicit about this failure mode. Either re-benchmark honestly or remove the number from the submission.

## Scope (what is in / out)

**In:**
- Microbial indicators module (MBC, F:B, qCO2, AMF colonisation) derived from existing RothC + RF outputs
- Integration into the 5 management philosophies
- API surface for the four indicators
- "Living Layer" visualisation strip in the frontend
- Honest rewrites of EXHIBITION_SUBMISSION.md and PROJECT_REPORT.md
- Spatial k-fold CV benchmark for the RF classifier
- Updated accuracy claim (or a deletion)

**Out of scope (for this cycle):**
- Switching RothC to MIMICS or MEND (a 2–3 week rewrite; too risky before the deadline)
- Arduino firmware / physical servo testing (handled by the hardware team)
- Re-training the XGBoost spatiotemporal model (in progress on another branch)
- UAT / usability testing with real visitors (separate phase after assembly)

## Constraints

- Deadline: June 2026 exhibition assembly. Everything must be defensible by mid-May for rehearsal.
- Budget: €638 (deck page 28). No software spend.
- The hardware team is building columns + servos in parallel; API contracts should not break mid-assembly.
- All citations added must be real (no fabricated DOIs).
