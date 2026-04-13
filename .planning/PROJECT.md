# Beneath the Surface — Project Context

**Programme:** AI for ALL | IAAC MaAI 2026 | UIA Barcelona — World Capital of Architecture 2026
**Exhibition:** June 2026
**Team:** Rafik, Seid, Vimal, Sahil
**Faculty:** Areti Markopoulou, Joaquín David Rodríguez Álvarez, Akshay Madapura

## Course mandate (from Areti's intro brief)

> "AI must be **legible, contestable, debatable, open to participation**."
> "AI as mediator between invisible systems and everyday experience."
> "Prototypes of understanding. AI for new forms of civic architecture."

Typology: **Public Awareness Tool** + **Speculative Futures & Storytelling**. The course rejects AI-as-optimiser and asks for AI-as-civic-interface. The measure of success is whether a non-expert visitor walks away understanding something about AI prediction *and* about the subject of the prediction — not whether the model is state-of-the-art.

## What it is

A physical interactive pavilion with **four transparent acrylic columns** on a low plinth. Each column contains the same six soil depth layers filled with coloured material; each tells a different Barcelona-region soil moment:

1. **The Archive (1950)** — historical baseline
2. **The Witness (2025)** — today, filled with real SoilGrids data
3. **The BAU (2075)** — business-as-usual projection
4. **The Oracle (2075)** — visitor-selected future, refilled live by servos when they press a button

The right column is the event. A visitor picks (a) an IPCC AR6 SSP pathway and (b) one of five land-management strategies; Arduino-driven servos drain and refill the Oracle column in ~8 seconds of visible computation while a 60" screen shows the prediction loop. The point of the installation is not the number on the screen — it is the eight seconds of visible decision-making, made material.

## Stack

| Layer | Component | Location |
|---|---|---|
| Climate | IPCC AR6 SSP1-2.6 / 2-4.5 / 3-7.0 / 5-8.5 tables (ΔT, ΔP, CO₂) | `backend/climate_scenarios/ssp_data.py` |
| Physics | RothC 5-pool carbon turnover (Coleman & Jenkinson 1996) | `backend/soil_model/` |
| Management | 5 philosophies: rewild, traditional, agroforestry, intensive regenerative, precision sustainable | `backend/soil_model/philosophies.py` |
| ML | Random Forest on ~215k SoilGrids pixels, 6 depth bands × 6 properties; XGBoost spatiotemporal upgrade in progress | `backend/ml_models/` |
| API | FastAPI | `backend/app.py`, `backend/exhibition_api.py` |
| Frontend | Vanilla JS / HTML / canvas | `frontend/exhibition/` |
| Hardware | Arduino Mega, 8× MG996R servos, touch kiosk, 60" LCD | (built at IAAC Fab Lab) |

## Positioning (post literature scan)

A literature scan (`research/related_work.md`) established that:

- The soil-science engine is **derivative**. Lugato et al. (2014, JRC) already published SSP-conditioned RothC projections of European SOC with the same management-scenario branching we are replicating. Bruni et al. (2021) quantified the warming penalty. Poggio et al. (2021, SoilGrids 2.0) is both our training data and a better uncertainty method (quantile regression forests) than our current RF.
- The "93% test accuracy" claim is almost certainly inflated by non-spatial cross-validation (see Wadoux et al. 2021). Must be re-benchmarked with spatial k-fold CV or dropped.
- The **real novelty** is the *integration medium*: a servo-actuated, visitor-conditioned stratigraphic column driven by ML inference. No prior Critical Zones / climate / soil exhibition has a predictive branching interface in physical material. That is our defensible contribution.
- The **curatorial parent** is Bruno Latour & Peter Weibel, *Critical Zones: Observatories for Earthly Politics* (ZKM Karlsruhe / MIT Press, 2020). Must be cited openly; the installation is the predictive observatory extension of that lineage.
- One genuinely novel technical addition is possible: **microbial indicators** (microbial biomass C, fungal:bacterial ratio, metabolic quotient, AMF colonisation). None of the surveyed precedents — artistic or scientific — touches these in an exhibition context, and they are the perfect "invisible system made experiential" on-brief for Areti's course.

## Key references (from `research/related_work.md`)

1. Latour & Weibel (2020), *Critical Zones*, MIT Press / ZKM.
2. Lugato et al. (2014), "European SOC baseline," *Global Change Biology* 20(1).
3. Lugato et al. (2014), "European management-scenario SOC projections," *Global Change Biology* 20(11).
4. Poggio et al. (2021), "SoilGrids 2.0," *SOIL* 7.
5. Bruni et al. (2021), "4 per 1000 feasibility under warming," *Biogeosciences* 18.
6. Coleman & Jenkinson (1996), "RothC-26.3," Springer.
7. Sterman et al. (2012), "C-ROADS," *System Dynamics Review* 28(3).
8. Rooney-Varga et al. (2020), "Climate Action Simulation," *Simulation & Gaming* 51(2).
9. Jansen et al. (2015), "Data Physicalization," *CHI '15*.
10. van der Bles et al. (2019), "Communicating uncertainty," *Royal Society Open Science* 6(5).
