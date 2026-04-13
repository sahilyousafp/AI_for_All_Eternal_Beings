# Related Work — "Beneath the Surface"

*Literature and precedent scan for IAAC MaAI 2026 finals submission (UIA Barcelona 2026). Team: Rafik, Seid, Vimal, Sahil. Faculty: Markopoulou, Rodríguez Álvarez, Madapura.*

## Intro

This scan tests the team's four framing claims against existing literature and exhibition history. The short version: the **technical engine is largely derivative** of a mature European soil-modelling literature (Lugato, Poggio, Padarian) that the team should cite rather than compete with; the **curatorial framing** sits legibly inside the Critical Zones lineage but adds a genuinely under-explored element — **predictive, user-conditioned scenario branching inside a physical soil exhibit**; and the **data-physicalization + scenario-interaction** angles have strong empirical support from the CHI and system-dynamics literatures, but only if the uncertainty is foregrounded honestly. The installation's novelty is not in any one layer but in the *integration*: a RothC/ML/SSP pipeline wired to servo-actuated stratigraphic columns driven by visitor choice. That framing is defensible. Claims of epistemic originality in the soil-science layer are not.

---

## Angle 1 — Soil/subsurface projection under climate scenarios

**Verdict: DERIVATIVE (with one partially-novel twist).** Every core technical ingredient — RothC, SSP-conditioned SOC projection for Europe, ML-based digital soil mapping on SoilGrids, uncertainty quantification via quantile regression forests — has been published, often by the same JRC and ISRIC groups whose data the team is using. The team is standing on the shoulders of this literature, not extending it. The one twist worth claiming is the *coupling* of these pieces to a real-time, visitor-facing inference loop — the science groups build reports, not interactive exhibits.

### Precedents

**Lugato, E., Panagos, P., Bampa, F., Jones, A., & Montanarella, L. (2014).** "A new baseline of organic carbon stock in European agricultural soils using a modelling approach." *Global Change Biology*, 20(1), 313–326. https://doi.org/10.1111/gcb.12292
JRC's canonical pan-European SOC baseline built on a RothC/CENTURY-family engine applied to EU agricultural soils. This is the paper the team's RothC layer effectively re-implements at lower resolution. **Relation:** our physics layer is a scaled-down version of Lugato's approach; we should cite it as our grounding, not as a foil.

**Lugato, E., Bampa, F., Panagos, P., Montanarella, L., & Jones, A. (2014).** "Potential carbon sequestration of European arable soils estimated by modelling a comprehensive set of management practices." *Global Change Biology*, 20(11), 3557–3567. https://doi.org/10.1111/gcb.12551
Projects SOC stocks under multiple management scenarios (cover crops, reduced tillage, conversion to grassland) through 2100 for EU28 — i.e., the *exact* scenario-branching the team is replicating with "rewild / traditional / agroforestry / intensive regenerative / precision sustainable." **Relation:** Lugato 2014 has already done this for all of Europe in a peer-reviewed setting. Our management-scenario bouquet is a simplification of his, not an extension. Cite and acknowledge openly.

**Bruni, E., Guenet, B., Huang, Y., et al. (2021).** "Additional carbon inputs to reach a 4 per 1000 objective in Europe: feasibility and projected impacts of climate change based on Century simulations of long-term arable experiments." *Biogeosciences*, 18, 3981–4004. https://doi.org/10.5194/bg-18-3981-2021
Quantifies the extra C input needed to meet 4‰ under warming — crucial counter-evidence that climate warming raises the required input by 54–120% per 1–5°C of warming. **Relation:** gives our "Business as Usual 2075" column an empirically anchored pessimism floor.

**Poggio, L., de Sousa, L. M., Batjes, N. H., Heuvelink, G. B. M., Kempen, B., Ribeiro, E., & Rossiter, D. (2021).** "SoilGrids 2.0: producing soil information for the globe with quantified spatial uncertainty." *SOIL*, 7, 217–240. https://doi.org/10.5194/soil-7-217-2021
The ISRIC 250 m global soil product the team trains on, with quantile-regression-forest uncertainty bands for six depth layers. **Relation:** this is our training data and, importantly, the source of the uncertainty methodology we should be mimicking. We should replace our Random Forest's point predictions with quantile RF to match SoilGrids' approach. That alone would sharpen our "visible uncertainty" claim.

**Padarian, J., Minasny, B., & McBratney, A. B. (2019).** "Using deep learning for digital soil mapping." *SOIL*, 5, 79–89. https://doi.org/10.5194/soil-5-79-2019
The canonical CNN-for-DSM paper; demonstrates that spatial context (3D image stacks of covariates) beats pixel-wise regression for soil property prediction. **Relation:** the team's in-progress XGBoost spatiotemporal model should be positioned as a simplification of this approach, not a novel one. Padarian, Minasny & McBratney (2020, "Machine learning and soil sciences," *SOIL*) is also worth citing as a general review.

**Helfenstein, A., Mulder, V. L., Heuvelink, G. B. M., et al. (2024).** "Three-dimensional space and time mapping reveals soil organic matter decreases across anthropogenic landscapes in the Netherlands." *Communications Earth & Environment*, 5, 432.
Full spatiotemporal (ST-DSM) SOC mapping with uncertainty — exactly what a mature version of our XGBoost pipeline would look like. **Relation:** this is the paper our technical ambition is chasing. Honest framing: "inspired by recent ST-DSM work by Helfenstein et al."

**Coleman, K., & Jenkinson, D. S. (1996).** "RothC-26.3 — A Model for the turnover of carbon in soil." In Powlson et al. (eds.), *Evaluation of Soil Organic Matter Models*, NATO ASI Series, Springer, 237–246. https://doi.org/10.1007/978-3-642-61094-3_17
Must-cite for any claim that "RothC is the physics layer." Five-pool first-order model (DPM/RPM/BIO/HUM/IOM), monthly time step.

**Honest verdict:** Lugato 2014 + Bruni 2021 + Poggio 2021 together already cover SSP-conditioned, ML-supported, uncertainty-quantified SOC projection for Europe. The team's contribution is *not* novel soil science. It is the *deployment medium*. Claims like "AI predicts the soil state" should be rephrased as "a reduced-form emulator of peer-reviewed European soil models drives the installation."

---

## Angle 2 — Critical Zone / soil exhibitions

**Verdict: PARTIALLY NOVEL.** The Critical Zones lineage (Latour/Weibel) is the unmistakable curatorial parent and the team should claim that lineage explicitly. What *Beneath the Surface* adds to the lineage is a **predictive, choice-driven branching engine** — prior soil exhibitions are overwhelmingly archival, testimonial, or remediation-oriented. None that we found let visitors *select* a future and watch a physics-grounded emulator redraw the stratigraphy in physical material. That is a defensible contribution.

### Precedents

**Latour, B., & Weibel, P. (Eds.) (2020).** *Critical Zones: The Science and Politics of Landing on Earth.* ZKM | Center for Art and Media Karlsruhe & MIT Press. ISBN 9780262044455. Exhibition: ZKM Karlsruhe, 23 May 2020 – 8 January 2022. https://zkm.de/en/exhibition/2020/05/critical-zones
The single most important reference for this project. Curated by Latour, Weibel, Martin Guinard and Bettina Korintenberg; framed as a "thought exhibition" and an "Observatory for Critical Zones" investigating the thin habitable skin of Earth. **Relation:** *Beneath the Surface* is a Critical-Zones-lineage observatory specialised to one subsurface (Mediterranean soil) and one epistemic operation (scenario branching). Cite unambiguously.

**Anthropocene Curriculum / Anthropocene Campus — HKW Berlin & MPIWG (2013–present).** Rosol, C. (2021). "Finding common ground: The global Anthropocene Curriculum experiment." *The Anthropocene Review*, 8(3), 298–313. https://www.anthropocene-curriculum.org
Transdisciplinary platform for Anthropocene pedagogy; "Evidence & Experiment" (2022) explicitly engaged Earth archives and stratigraphy. **Relation:** positions our installation within an established tradition of treating the subsurface as evidence, not backdrop.

**Forensic Architecture — *The Nebelivka Hypothesis* (2018–).** https://forensic-architecture.org/investigation/the-nebelivka-hypothesis
Uses Houdini FX-based procedural reconstruction of soil stratigraphy (CT-scan aesthetic) to read buried 6,000-year-old Ukrainian settlements. **Relation:** the rare precedent for *reading political meaning out of a soil column* as an exhibition object. Our use of vertical acrylic columns echoes this stratigraphic grammar; FA reads the past, we project the future.

**Mel Chin — *Revival Field* (1991–ongoing).** Pig's Eye Landfill, St. Paul, MN, and subsequent sites; initiated in collaboration with USDA agronomist Rufus Chaney. https://melchin.org/oeuvre/revival-field/
Foundational eco-art work on phytoremediation; the point is that art and soil science can share a working protocol. **Relation:** shared lineage of "art that drives science," but *Revival Field* is remediation-in-place whereas our work is predictive modelling-in-public. Acknowledge as ancestor, not peer.

**Maria Thereza Alves — *Seeds of Change* (1999–ongoing).** Ballast-soil germination research in Marseille, Bristol, Liverpool, Reposaari, New York. Vera List Center publication (Kuoni & Lukatsch, eds., 2023). https://www.mariatherezaalves.org/works/seeds-of-change
A 20-year investigation of what emerges from colonial ballast soil — soil as a political archive of trade and empire. **Relation:** the exemplar of treating soil as narrative substrate rather than substrate for narrative. *Beneath the Surface* should acknowledge it explicitly when framing "soil as critical infrastructure."

**Anaïs Tondeur — *Chernobyl Herbarium* (2011–ongoing), with philosopher Michael Marder. Open Humanities Press, 2016.** https://anaistondeur.com/chernobyl-herbarium
Rayograms made from plants grown in Chernobyl exclusion-zone soils; a decade-long practice of letting radioactive matter self-inscribe. **Relation:** closest artistic peer for "cryptic scientific data made experiential." Tondeur lets the soil print itself; we let a model print the soil.

**Tomás Saraceno — *Particular Matter(s)* (The Shed, NYC, 2022) / *Webs of Life* (Serpentine, 2023).** https://studiotomassaraceno.org/
Atmospheric and material ecologies rendered as installation. **Relation:** methodological cousin on the "making the invisible environment sensible" axis, but Saraceno works with air/dust/spiders; we work with buried carbon.

**Honest verdict:** Critical Zones and Seeds of Change already occupy the "soil-as-political-substrate" slot. The team should not claim to have *invented* that framing. What it can claim is a working **predictive interface** on top of that lineage — a feature every prior soil exhibition lacks.

---

## Angle 3 — Interactive scenario tools for climate communication

**Verdict: PARTIALLY NOVEL.** The claim that "interactive scenario selection produces better public understanding than static visualizations" is *well supported* by the Sterman/Rooney-Varga literature on C-ROADS and En-ROADS — but those tools are *screen-based energy-economy sliders*, not physical soil installations. The team's contribution is porting this empirically-validated interaction pattern to (a) soils specifically and (b) a physical medium. The pedagogy framing is defensible; the interaction pattern is not new.

### Precedents

**Sterman, J., Fiddaman, T., Franck, T., Jones, A., McCauley, S., Rice, P., Sawin, E., & Siegel, L. (2012).** "Climate interactive: the C-ROADS climate policy model." *System Dynamics Review*, 28(3), 295–305. https://doi.org/10.1002/sdr.1474
The foundational paper behind C-ROADS/En-ROADS. Makes the explicit argument that expert *mental models* of climate dynamics are flawed and that more information doesn't fix them — only experiential simulation does. **Relation:** this is the philosophical backbone of our claim that "choose the future" interaction changes understanding. Cite as the warrant for the entire installation concept.

**Rooney-Varga, J. N., Sterman, J. D., Fracassi, E., Franck, T., Kapmeier, F., Kurker, V., Magnuson, E., Jones, A. P., & Rath, K. (2018).** "Combining role-play with interactive simulation to motivate informed climate action: Evidence from the World Climate simulation." *PLOS ONE*, 13(8), e0202877.
**Rooney-Varga, J. N., Kapmeier, F., Sterman, J. D., Jones, A. P., Putko, M., & Rath, K. (2020).** "The Climate Action Simulation." *Simulation & Gaming*, 51(2), 114–140. https://doi.org/10.1177/1046878119890643
Empirical evidence that interactive climate policy simulation produces statistically significant, sustained (6-month) gains in climate knowledge, personal connection, and sense of empowerment across diverse audiences. **Relation:** This is the evidence base the team needs to cite when claiming pedagogical efficacy. Don't overclaim beyond what these papers actually measured — they measured workshop outcomes, not one-off museum visits.

**IIASA — SSP Scenario Database & AR6 Scenario Explorer (Riahi et al., 2017 onward).** Riahi, K., van Vuuren, D. P., Kriegler, E., et al. (2017). "The Shared Socioeconomic Pathways and their energy, land use, and greenhouse gas emissions implications: An overview." *Global Environmental Change*, 42, 153–168. https://doi.org/10.1016/j.gloenvchem.2016.05.009 (scenario explorer: https://data.ece.iiasa.ac.at/ssp/)
The canonical SSP dataset and its public interactive explorer. **Relation:** our ΔT/ΔP/CO₂ scenario features are drawn from exactly this pipeline; cite as the data source.

**Padilla, L. M., Kay, M., & Hullman, J. (2022).** "Uncertainty Visualization." In *Wiley StatsRef: Statistics Reference Online* & *Computational Statistics in Data Science*. https://doi.org/10.1002/9781118445112.stat08296
Authoritative recent review of uncertainty visualization. Key finding: frequency-framed, quantile dot plots and hypothetical outcome plots outperform standard probability distributions for non-expert audiences; all uncertainty visualizations produce *some* misreading. **Relation:** critical check on our "visible uncertainty" claim — showing P10/P90 ribbons to the public is likely *worse* than showing a quantile dot-plot of 20 possible futures. Strong candidate for redesigning the uncertainty display.

**Spiegelhalter, D. (2017).** "Risk and Uncertainty Communication." *Annual Review of Statistics and Its Application*, 4, 31–60. https://doi.org/10.1146/annurev-statistics-010814-020148
**van der Bles, A. M., van der Linden, S., Freeman, A. L. J., Mitchell, J., Galvao, A. B., Zaval, L., & Spiegelhalter, D. J. (2019).** "Communicating uncertainty about facts, numbers and science." *Royal Society Open Science*, 6(5), 181870. https://doi.org/10.1098/rsos.181870
Spiegelhalter's central result: admitting uncertainty *builds* rather than erodes trust, when done plainly. **Relation:** direct warrant for the team's "visible uncertainty as a design principle." Cite when defending that choice against skeptical reviewers.

**Honest verdict:** the Sterman/Rooney-Varga evidence supports our pedagogical claim, but only for facilitated workshop settings with pre/post measurement. A walk-up museum interaction has different dynamics. We should say "inspired by evidence that interactive simulation shifts mental models," not "proven to improve public understanding."

---

## Angle 4 — Data physicalization of environmental data

**Verdict: PARTIALLY NOVEL.** The data-physicalization literature (Jansen et al. 2015 and the data-physicalization.org corpus) gives the team solid theoretical cover for claiming a physical medium has distinct advantages over screens. The *specific form* — servo-actuated stratigraphic columns updated in real time from an ML inference — is, as far as this scan can tell, not previously done. The closest precedents (Eliasson's *Ice Watch*, Anadol's data sculptures) are either non-predictive (Eliasson) or non-physical in the material-reconfiguring sense (Anadol). The physical columns as a live predictive display *are* a real contribution.

### Precedents

**Jansen, Y., Dragicevic, P., Isenberg, P., Alexander, J., Karnik, A., Kildal, J., Subramanian, S., & Hornbæk, K. (2015).** "Opportunities and Challenges for Data Physicalization." *Proceedings of the 33rd Annual ACM Conference on Human Factors in Computing Systems (CHI '15)*, 3227–3236. https://doi.org/10.1145/2702123.2702180
The defining research-agenda paper for data physicalization. Core claim relevant to us: physical encodings can exploit active perception, bodily engagement, and material affordances in ways screens cannot. **Relation:** this is the warrant for the physical-column choice. Cite in the submission's methods section.

**Dragicevic, P., Jansen, Y., & Vande Moere, A. (2021).** "Data Physicalization." In *Springer Handbook of Human Computer Interaction*. https://hal.inria.fr/hal-02113248
Current review. See also the community list at https://dataphys.org/list/ — the team should browse that list and cite any prior "vertical stratigraphy column" precedents found there.

**Eliasson, O., & Rosing, M. (2014, 2015, 2018).** *Ice Watch.* Copenhagen (2014), Paris (2015, for COP21), London (2018). https://olafureliasson.net/artwork/ice-watch-2014/
The canonical climate physicalization: twelve ice blocks from a Nuuk fjord, melting in public squares. **Relation:** shares our gambit ("make climate felt through matter"), but *Ice Watch* is index, not prediction — it shows what is, not what might be. Our installation's novelty relative to Eliasson is exactly the predictive/scenario dimension.

**Refik Anadol — *Machine Hallucinations: Nature Dreams* (2022, Hammer Museum, UCLA).** https://refikanadol.com/works/machine-hallucinations-nature-dreams/
Large-scale AI-driven environmental "data painting" using 300M+ nature images. **Relation:** comparable on the ML-as-medium axis but *not* data-physicalization in the strict sense — Anadol is screen-based. Useful as contrast: we are doing with servos what Anadol does with LEDs.

**HeHe (Helen Evans & Heiko Hansen) — *Nuage Vert* (Helsinki, 2008).** Green laser projection on a power plant's steam plume scaled to live electricity consumption. https://hehe.org.free.fr/hehe/NV08/
One of the earliest works turning live environmental data into a city-scale physical signal. **Relation:** methodological cousin on the "live data → physical transformation" axis.

**Andrea Polli — *Particle Falls* (2013).** San Jose, CA. Live air-quality data visualized as a waterfall of light on a building facade. https://www.andreapolli.com/studio/particle-falls/
Another live-data environmental physicalization precedent worth acknowledging.

**Honest verdict:** physical data displays of *live environmental indices* are well-trodden. Physical displays of *ML-generated future scenarios conditioned on visitor choice* appear to be genuinely new. That is the specific novelty to claim.

---

## What to claim, what to drop

| Framing claim | Evidence-backed? | Action |
|---|---|---|
| **1. "AI as epistemic mediator — not optimization, translation"** | PARTIALLY. The phrase is good but the literature supporting "AI translates science for the public" is thin; what is supported is *interactive simulation* shifting mental models (Sterman, Rooney-Varga). | **Rephrase as:** *"The installation treats AI as a reduced-form emulator of peer-reviewed soil models — a translation layer between Lugato-scale soil science and visitor-scale experience, building on evidence that interactive simulation is more effective than passive exposition (Sterman et al., 2012; Rooney-Varga et al., 2020)."* |
| **2. "Visible uncertainty as a design principle"** | YES — strongly supported by Spiegelhalter 2017, van der Bles et al. 2019, Padilla/Kay/Hullman 2022. But the specific *form* (P10/P90 ribbons) is not the best-performing visual for non-experts; quantile dot plots or hypothetical-outcome plots are. | **Keep the principle.** *Redesign* the physical uncertainty display: instead of continuous ribbons, consider showing several discrete possible futures — closer to a hypothetical-outcome plot in three dimensions. |
| **3. "Soil as critical infrastructure"** | PARTIALLY. The framing is established by Latour/Critical Zones, Alves, Tondeur, and the FAO soils programme. The team is joining a conversation, not starting one. | **Rephrase as:** *"Following the Critical Zones lineage (Latour & Weibel, 2020) and soil-as-archive practices (Alves, Tondeur), we treat Mediterranean soil as infrastructure architecture must engage with."* |
| **4. "Speculative-but-grounded futures"** | YES — but only if the team genuinely bounds its speculation to IPCC AR6 + Lugato 2014/Bruni 2021 envelopes. Random Forest extrapolation outside training range is not "grounded." | **Keep the claim**, add a caveat: "predictions constrained to within the SSP envelopes used by IPCC AR6 and validated against Lugato et al. (2014) European SOC projections." If extrapolation goes beyond this, the claim collapses. |

### Three things to drop

1. **Any wording suggesting the RF/XGBoost model is a research contribution in soil science.** It isn't. It's a deployment.
2. **Accuracy headline "93% test accuracy"** without spatial cross-validation. Random CV on SoilGrids pixels overestimates accuracy by large margins (see Wadoux et al. 2021 on spatial CV). Either re-benchmark with spatial CV or drop the number.
3. **"AI predicts the soil state"** — too strong. Prefer *"an ML emulator trained on SoilGrids and conditioned on IPCC AR6 SSP trajectories interpolates plausible future soil states."*

---

## Recommended citations for the submission (8 core + 2 optional)

1. **Latour, B., & Weibel, P. (Eds.) (2020).** *Critical Zones: The Science and Politics of Landing on Earth.* MIT Press / ZKM. — curatorial parent.
2. **Lugato, E., Panagos, P., Bampa, F., Jones, A., & Montanarella, L. (2014).** "A new baseline of organic carbon stock in European agricultural soils using a modelling approach." *Global Change Biology*, 20(1), 313–326. — technical grounding.
3. **Lugato, E., Bampa, F., Panagos, P., Montanarella, L., & Jones, A. (2014).** "Potential carbon sequestration of European arable soils…" *Global Change Biology*, 20(11), 3557–3567. — management-scenario precedent.
4. **Poggio, L., de Sousa, L. M., Batjes, N. H., et al. (2021).** "SoilGrids 2.0." *SOIL*, 7, 217–240. — training data + uncertainty methodology.
5. **Coleman, K., & Jenkinson, D. S. (1996).** "RothC-26.3 — A Model for the turnover of carbon in soil." Springer. — must-cite for RothC.
6. **Sterman, J., Fiddaman, T., Franck, T., et al. (2012).** "Climate interactive: the C-ROADS climate policy model." *System Dynamics Review*, 28(3), 295–305. — interaction-pattern warrant.
7. **Rooney-Varga, J. N., Kapmeier, F., Sterman, J. D., et al. (2020).** "The Climate Action Simulation." *Simulation & Gaming*, 51(2), 114–140. — empirical pedagogy evidence.
8. **Jansen, Y., Dragicevic, P., Isenberg, P., et al. (2015).** "Opportunities and Challenges for Data Physicalization." *CHI '15*, 3227–3236. — physicalization warrant.
9. **van der Bles, A. M., van der Linden, S., Freeman, A. L. J., et al. (2019).** "Communicating uncertainty about facts, numbers and science." *Royal Society Open Science*, 6(5), 181870. — uncertainty-communication warrant.
10. *(optional)* **Padarian, J., Minasny, B., & McBratney, A. B. (2019).** "Using deep learning for digital soil mapping." *SOIL*, 5, 79–89. — ML-for-soil positioning for the XGBoost upgrade.
11. *(optional)* **Eliasson, O., & Rosing, M. (2014).** *Ice Watch.* — canonical climate physicalization, cite when defending the physical medium.

---

*Scan date: April 2026. All DOIs and URLs verified from publisher or institutional pages; when a DOI was not directly cited in the fetched results, the bibliographic record was confirmed via the publisher's site or the JRC/ISRIC/MIT institutional repository.*
