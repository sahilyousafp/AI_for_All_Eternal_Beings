# Beneath the Surface
## A Predictive Observatory for Mediterranean Soil
### Finals Submission — AI for ALL | IAAC MaAI 2026
**Team: Rafik, Seid, Vimal, Sahil**
**Faculty: Areti Markopoulou, Joaquín David Rodríguez Álvarez, Akshay Madapura**
**Exhibition: June 2026 · UIA Barcelona, World Capital of Architecture**

---

## What this is

*Beneath the Surface* is an interactive pavilion in which four transparent acrylic columns make Mediterranean soil futures legible to a non-expert public. A visitor selects a climate scenario and a land-management strategy; an Arduino-driven servo system physically refills the rightmost column as a machine-learning **emulator of peer-reviewed European soil models** computes the predicted state in front of them. The point is not the number on the screen. The point is the eight seconds of visible decision-making, made material.

It sits openly inside the lineage of Bruno Latour and Peter Weibel's exhibition *Critical Zones: Observatories for Earthly Politics* (ZKM Karlsruhe, 2020 — MIT Press) and the *Anthropocene Curriculum* at HKW Berlin. What it adds to that lineage is a working **predictive interface**: prior soil and Critical Zones exhibitions have been archival, testimonial, or remediation-oriented; none, to our knowledge, lets visitors *select* a future and watch a physics-grounded model redraw the stratigraphy in physical material in real time.

The course brief from Areti Markopoulou frames the mandate exactly:

> "AI must be **legible, contestable, debatable, open to participation**."
> "AI as mediator between invisible systems and everyday experience."
> "Prototypes of understanding. AI for new forms of civic architecture."

This submission is our attempt to make a soil-prediction system that is all of those things at once.

---

## The four columns

Four transparent acrylic cylinders stand on a single low white plinth. Each contains the same six soil depth bands filled with coloured material, but each tells a different moment of Mediterranean soil:

1. **The Archive — 1950.** A static reference of pre-intensive-agriculture baseline conditions estimated from the Mediterranean soil-science literature. Built once. Never changes.
2. **The Witness — 2025.** Today, filled at the start of the exhibition with real surface values from the SoilGrids 250 m product (Poggio et al., 2021) for the Barcelona region. This column is the calibration anchor — what it shows is measured, not modelled.
3. **The Business as Usual — 2075.** A pre-computed reference future under SSP3-7.0 with no land-management intervention. The column visitors do not control. It is there to make the question "what's different from doing nothing?" visible.
4. **The Oracle — 2075.** The visitor-conditioned column. Empty when no one is interacting, filled live by a servo system the moment a visitor presses a scenario + management button. Eight seconds of visible computation, every fill different, every choice producing a different future.

Each column carries a fifth narrow strip beside the main stratigraphy — **The Living Layer** — which displays the microbial state of the soil under that scenario (see *The Living Layer* section below). It pulses faster than the carbon layers because microbes respond on yearly, not decadal, timescales — visually reinforcing that microbes are the early-warning system.

---

## The system

A reduced-form **machine-learning emulator** of peer-reviewed European soil-science models, conditioned on visitor input. The honest framing is that the science is established; we are the people who made it walkable.

| Layer | What it does | Where it comes from |
|---|---|---|
| **Climate scenarios** | ΔT, Δprecipitation, CO₂ for SSP1-2.6 / 2-4.5 / 3-7.0 / 5-8.5 trajectories at any year, interpolated for the Mediterranean region | IPCC AR6 WG1 Atlas; SSP database via IIASA (Riahi et al., 2017) |
| **Carbon physics** | RothC five-pool decomposition (DPM, RPM, BIO, HUM, IOM) coupled to climate forcing | Coleman & Jenkinson (1996); calibration follows Lugato et al. (2014) for European agricultural soils |
| **Spatial pattern** | Random Forest classifier predicting six soil properties × six depth bands across a 20×20 cell grid | Trained on SoilGrids 2.0 (Poggio et al., 2021); architecture is a deployment of standard digital-soil-mapping practice (Padarian, Minasny & McBratney, 2019) |
| **Microbial indicators** | Microbial Biomass Carbon, Fungal:Bacterial ratio, qCO₂ metabolic quotient, AMF colonisation derived from RothC pools and biology state | New module — empirical relationships from Anderson & Domsch (1989, 1990), Bardgett & McAlister (1999), Fierer et al. (2009), Treseder (2004); see *The Living Layer* below |
| **Management scenarios** | Five land-management philosophies (rewild, traditional dehesa, intensive agriculture, maximum restoration, fast-fix eucalyptus) | Each maps to concrete simulation parameters (tillage, fertiliser, planting density, amendments) drawn from the European agroforestry and meta-analysis literature |
| **Hardware** | Arduino Mega + 8× MG996R servos + touch kiosk | IAAC Fab Lab build; servo refill is the visible AI moment |

### Honest positioning

Our soil-science engine is **not novel research**. Lugato et al. (2014, JRC) already published SSP-conditioned RothC projections of European soil organic carbon with the same management-scenario branching we deploy. Bruni et al. (2021) quantified the additional carbon input required to maintain stocks under warming. Poggio et al. (2021) is both our training data and the source of a stronger uncertainty methodology than ours. Helfenstein et al. (2024) is the spatiotemporal soil-mapping work our XGBoost upgrade is chasing.

We stand on this literature. Our contribution is **not** the equations — it is the integration medium and the civic interface. Specifically:

1. **The medium.** A servo-actuated, visitor-conditioned stratigraphic column driven by ML inference in real time. No prior Critical Zones, climate-physicalization, or soil exhibition appears to combine these three properties simultaneously.
2. **The microbial indicator layer** (see below). None of the precedents we surveyed — artistic or scientific — surface microbial indicators in an exhibition format. This is the one piece of the technical stack that is genuinely under-explored.
3. **The civic framing**, in line with Areti's course brief: AI presented not as oracle or optimiser, but as a translation layer between Lugato-scale soil science and visitor-scale experience.

---

## The Living Layer — microbial indicators

The carbon column tells a story on a single axis: g/kg of organic carbon goes up or down over decades. That is one number on one dial. The course brief asks for *legibility*, which means more than one dial.

The Living Layer is the second dial. It shows the soil's living community — the microbes that decide whether carbon stays or leaves. Microbes respond in seasons, not decades, so they are the early-warning system for everything else the columns show. A teaspoon of healthy soil contains more living organisms than there are humans on Earth.

We surface four indicators that soil scientists actually measure in the field and that a non-expert visitor can read at a glance:

| Indicator | What it means | Literature |
|---|---|---|
| **Microbial Biomass Carbon (MBC)** | How much living mass is down there. Typically 1–3% of total SOC, modulated by clay protection and moisture. | Anderson & Domsch (1989); Wardle (1992) |
| **Fungal : Bacterial ratio (F:B)** | Maturity of the soil community. >1 = mature woodland, undisturbed; <0.5 = stressed, disturbed, intensively farmed. | Bardgett & McAlister (1999); Fierer et al. (2009); de Vries et al. (2006) |
| **Metabolic quotient (qCO₂)** | Microbial *stress*. High qCO₂ means microbes are working harder per unit of their own biomass — counter-intuitively, low qCO₂ is what mature, efficient soils show. | Anderson & Domsch (1990) |
| **AMF mycorrhizal colonisation** | The "wood-wide-web". % of root length occupied by symbiotic fungi. Suppressed by tillage and synthetic N. | Treseder (2004) meta-analysis |

These four feed a composite **Living Soil Index (0–100)** displayed on the fifth strip beside each column, and they appear individually on the wall screen. Under our five management scenarios they move in distinctively different directions: intensive regenerative pumps MBC and the F:B ratio upward and qCO₂ downward; business-as-usual tillage collapses the fungal network; rewilding takes thirty years to shift F:B but moves qCO₂ down immediately. Each scenario produces a distinctive *fingerprint*, not just a number. Under the deck's typology, this is what gives a visitor *something to argue with*.

The module is implemented as a pure derivation layer over the existing RothC and biology state — no new training data, no new calibration parameters. Every coefficient comes from a published empirical relationship. The exact citations live in the docstring of `backend/soil_model/microbial_indicators.py`.

---

## Visitor experience

**Approach (0–10 s).** A visitor enters and sees four glowing columns. The four columns share the same six depth bands but the warm amber organic-carbon stripe at the top shrinks across them: thick in 1950, thinner in 2025, a pale stripe in 2075-BAU, and Column 4 — Oracle — is empty, glowing faintly, waiting. The visitor reads the trajectory before reading a single word. Past, present, possible.

**Engage (10–30 s).** Annotations on Column 2 confirm what the visitor already senses: real measured values of organic carbon, clay, bulk density, sourced from SoilGrids 2.0. The reasoning panel between columns 3 and 4 reads what the model knows about this soil — climate trajectory, the calibration source, and the per-management influences.

**Choose (30–45 s).** Two rings of buttons sit at the base of Column 4: an outer ring for the four SSP climate scenarios, an inner ring for the five land-management philosophies. The visitor picks one of each. No instruction is needed.

**The AI moment (45–55 s).** Column 4 responds. It does not appear filled — it fills, layer by layer, over eight seconds. A progress indicator on the wall screen shows the model running. The Living Layer strip beside the column lights up live as the indicators are computed. Then it stops. The carbon stripe is at the height the model predicted under the chosen scenario; the Living Layer shows whether the resulting soil community is healthy, stressed, or collapsed.

**Compare (55 s – 2 min).** The visitor presses a different combination. Column 4 drains and refills again. They press a third. Multiple visitors take turns. Groups compare scenarios simultaneously. The columns make the conversation happen.

**Step back (2 min +).** They see all four columns at once. The story is complete. Above them on the wall:

> *You are standing above soil that took 10,000 years to form.
> The model computed plausible 2075 states in eight seconds.
> What you do with that information is not the model's decision.*

---

## What visitors learn about AI

By the end of the interaction, without reading a manual, visitors have directly experienced four things about predictive AI:

1. **AI prediction is grounded in real, peer-reviewed science.** The reasoning panel names the inputs (climate scenario, soil measurements, management choice) and names the upstream science (RothC, IPCC AR6, SoilGrids, Lugato et al.). There is no mystery and no claim of novelty — the model is a translation layer over existing soil science.
2. **AI prediction has visible uncertainty.** The columns show P10/P90 envelopes as a translucent halo at each layer boundary, the wall chart shows the same, and the Living Soil Index trajectory plot carries its own envelope. We follow Spiegelhalter's principle (Spiegelhalter, 2017; van der Bles et al., 2019) that admitting uncertainty plainly *builds* rather than erodes trust.
3. **AI prediction depends on the choices we make.** The same present data (Column 2) produces twenty different futures across five managements × four climates. The model is not fate; it is a tool for reasoning about consequences of choices. This is the empirically supported claim from the Climate Interactive / C-ROADS literature (Sterman et al., 2012; Rooney-Varga et al., 2020): interactive scenario simulation shifts mental models in ways static visualization cannot.
4. **AI prediction is a translation, not an oracle.** The course brief asks for AI as "mediator between invisible systems and everyday experience." That is what the four columns are. The model does not replace the soil scientist. It makes their decades of measurement legible to a five-year-old.

---

## Spatial layout

**Total footprint.** 3.0 m (W) × 1.2 m (D) × 2.4 m (H).
**Location.** UIA Barcelona Exhibition Space, Room 103, IAAC — June 2026.

```
TOP VIEW (floor plan)
─────────────────────────────────────────────────────────
                     1.2 m
    ┌──────────────────────────────────────────────┐
    │                  WALL                        │
    │    ┌──────────────────────────────────┐     │  0.15 m
    │    │        60" WALL SCREEN           │     │
    │    └──────────────────────────────────┘     │
    │                                              │
    │  ┌──┐  ┌──┐  ┌──────────┐  ┌──┐  ┌──┐     │  0.3 m plinth
    │  │C1│  │C2│  │ REASONING│  │C3│  │C4│     │
    │  └──┘  └──┘  │  PANEL   │  └──┘  └──┘     │
    │              └──────────┘  ↑               │
    │                  ↑ visitor selects ↑        │
    │◄────────────────── 3.0 m ──────────────────►│
    └──────────────────────────────────────────────┘

 Visitor circulation: 1.5 m clearance in front
```

| Component | Position | Dimensions | Height |
|---|---|---|---|
| C1 — Archive 1950 | 0.30 m from left | Ø 0.15 m cylinder | 2.0 m |
| C2 — Witness 2025 | 0.75 m | Ø 0.15 m | 2.0 m |
| Reasoning panel | 1.20 m | 0.12 m W × 1.5 m H | eye level |
| C3 — BAU 2075 | 1.80 m | Ø 0.15 m | 2.0 m |
| C4 — Oracle 2075 | 2.40 m | Ø 0.15 m servo-actuated | 2.0 m |
| Scenario buttons | below C4 | 9 buttons (4 SSP + 5 management) | plinth top |
| Plinth | full width | 3.0 m × 0.4 m | 0.3 m |
| Wall screen | rear, centred | 1.33 m × 0.75 m | bottom @ 1.5 m |

---

## Material strategy

No real soil is used. Each column layer uses a clean, dry, locally sourced material that visually reads as the soil type it represents.

| Layer | Depth | Material | Colour |
|---|---|---|---|
| Surface | 0–5 cm | Light craft sand | `#C4A882` |
| Subsoil 1 | 10–30 cm | Dried coffee grounds | `#7A5C40` |
| Subsoil 2 | 30–60 cm | Fine dark gravel | `#5C4033` |
| Subsoil 3 | 60–100 cm | Grey sand | `#3D2B1F` |
| Deep | 100–200 cm | White quartz sand | `#1A1209` |
| Inert | 200 cm+ | Red clay powder | `#0D0906` |

Column 4 (Oracle) uses the same materials, but the surface-band fill height is dynamically controlled by an Arduino servo that physically raises/lowers a divider inside the tube based on the prediction. Under SSP1-2.6 + intensive regenerative the divider sits high; under SSP5-8.5 + industrial agriculture it drops. The physical column changes. The model's output is embodied in matter.

The Living Layer strip is a separate narrow channel on the side of each column, lit from within by an addressable LED strip whose colour and pulse rate are driven by the Living Soil Index for that scenario.

---

## Budget

Under the IAAC €500 base budget. See `PROJECT_REPORT.md` for the full component-by-component breakdown.

| Category | Amount |
|---|---|
| Acrylic columns + materials | €265 |
| Arduino + servos + electronics | €148 |
| LEDs + Living Layer strips | €40 |
| Printed labels, panels, hardware | €45 |
| **Subtotal** | **€498** |
| IAAC Fab Lab discount | −€100 |
| **Net** | **€398** |
| Buffer (replacement / contingencies) | €102 |

---

## Where the technical claims are honest

We keep the deck readable for non-experts but every claim above is grounded in a citeable source. Specifically:

- "ML emulator of peer-reviewed European soil models" — Lugato et al. (2014a, 2014b) on European RothC + SOC management projections; Poggio et al. (2021) on SoilGrids 2.0; Coleman & Jenkinson (1996) on RothC itself.
- "Conditioned on IPCC AR6 SSP trajectories" — Riahi et al. (2017) and the IIASA SSP database; AR6 WG1 Atlas regional values.
- "The integration medium is the contribution" — Jansen et al. (2015) on data physicalization as a research agenda; the absence of a predictive scenario-branching physical soil exhibit in the literature we surveyed.
- "AI as translation, not oracle" — directly from Areti's course brief and supported by Sterman et al. (2012) and Rooney-Varga et al. (2020) on interactive scenario simulation as a tool for shifting mental models.
- "Visible uncertainty as a design principle" — Spiegelhalter (2017); van der Bles et al. (2019); Padilla, Kay & Hullman (2022) on uncertainty visualization.
- "Microbial indicators as a second axis" — Anderson & Domsch (1989, 1990); Bardgett & McAlister (1999); Fierer et al. (2009); Treseder (2004); de Vries et al. (2006); Tiemann et al. (2015).
- "Critical Zones lineage" — Latour & Weibel (2020); Anthropocene Curriculum (HKW Berlin / MPIWG).

The Random Forest accuracy figure has been re-benchmarked under blocked spatial k-fold cross-validation following Wadoux et al. (2021); the result is documented in `backend/ml_models/BENCHMARK.md`. The honest finding is that the texture classifier is essentially saturated on this dataset (only four dominant USDA texture classes for Spain at 2.5 km resolution), so neither the previously circulated "93%" nor any other single accuracy headline carries the meaning it appears to carry. The deck has been updated to remove the misleading number; the predictive-uncertainty story is now told by the P10–P90 envelopes drawn on the SOC and Living Soil Index trajectories — not by a single accuracy percentage on a coarse classification task. See `backend/ml_models/BENCHMARK.md` for the full methodology, both numbers side by side, and the recommended reframings.

---

## References

1. Anderson, T.-H., & Domsch, K. H. (1989). Ratios of microbial biomass carbon to total organic carbon in arable soils. *Soil Biology & Biochemistry*, 21(4), 471–479.
2. Anderson, T.-H., & Domsch, K. H. (1990). Application of eco-physiological quotients (qCO₂ and qD) on microbial biomasses from soils of different cropping histories. *Soil Biology & Biochemistry*, 22(2), 251–255.
3. Bardgett, R. D., & McAlister, E. (1999). The measurement of soil fungal:bacterial biomass ratios as an indicator of ecosystem self-regulation in temperate meadow grasslands. *Biology and Fertility of Soils*, 29, 282–290.
4. Bruni, E., Guenet, B., Huang, Y., et al. (2021). Additional carbon inputs to reach a 4‰ objective in Europe: feasibility and projected impacts of climate change. *Biogeosciences*, 18, 3981–4004. https://doi.org/10.5194/bg-18-3981-2021
5. Coleman, K., & Jenkinson, D. S. (1996). RothC-26.3 — A model for the turnover of carbon in soil. In Powlson et al. (eds.), *Evaluation of Soil Organic Matter Models*, NATO ASI Series, Springer, 237–246.
6. de Vries, F. T., Hoffland, E., van Eekeren, N., Brussaard, L., & Bloem, J. (2006). Fungal/bacterial ratios in grasslands with contrasting nitrogen management. *Soil Biology & Biochemistry*, 38(8), 2092–2103.
7. Fierer, N., Strickland, M. S., Liptzin, D., Bradford, M. A., & Cleveland, C. C. (2009). Global patterns in belowground communities. *Ecology Letters*, 12(11), 1238–1249.
8. Helfenstein, A., Mulder, V. L., Heuvelink, G. B. M., et al. (2024). Three-dimensional space and time mapping reveals soil organic matter decreases across anthropogenic landscapes in the Netherlands. *Communications Earth & Environment*, 5, 432.
9. Jansen, Y., Dragicevic, P., Isenberg, P., et al. (2015). Opportunities and Challenges for Data Physicalization. *Proceedings of CHI '15*, 3227–3236. https://doi.org/10.1145/2702123.2702180
10. Latour, B., & Weibel, P. (Eds.) (2020). *Critical Zones: The Science and Politics of Landing on Earth.* ZKM | Center for Art and Media Karlsruhe & MIT Press. ISBN 9780262044455.
11. Lugato, E., Panagos, P., Bampa, F., Jones, A., & Montanarella, L. (2014a). A new baseline of organic carbon stock in European agricultural soils using a modelling approach. *Global Change Biology*, 20(1), 313–326. https://doi.org/10.1111/gcb.12292
12. Lugato, E., Bampa, F., Panagos, P., Montanarella, L., & Jones, A. (2014b). Potential carbon sequestration of European arable soils estimated by modelling a comprehensive set of management practices. *Global Change Biology*, 20(11), 3557–3567. https://doi.org/10.1111/gcb.12551
13. Padarian, J., Minasny, B., & McBratney, A. B. (2019). Using deep learning for digital soil mapping. *SOIL*, 5, 79–89. https://doi.org/10.5194/soil-5-79-2019
14. Padilla, L. M., Kay, M., & Hullman, J. (2022). Uncertainty Visualization. In *Wiley StatsRef* / *Computational Statistics in Data Science*. https://doi.org/10.1002/9781118445112.stat08296
15. Poggio, L., de Sousa, L. M., Batjes, N. H., Heuvelink, G. B. M., Kempen, B., Ribeiro, E., & Rossiter, D. (2021). SoilGrids 2.0: producing soil information for the globe with quantified spatial uncertainty. *SOIL*, 7, 217–240. https://doi.org/10.5194/soil-7-217-2021
16. Riahi, K., van Vuuren, D. P., Kriegler, E., et al. (2017). The Shared Socioeconomic Pathways and their energy, land use, and greenhouse gas emissions implications. *Global Environmental Change*, 42, 153–168.
17. Rooney-Varga, J. N., Kapmeier, F., Sterman, J. D., et al. (2020). The Climate Action Simulation. *Simulation & Gaming*, 51(2), 114–140. https://doi.org/10.1177/1046878119890643
18. Spiegelhalter, D. (2017). Risk and Uncertainty Communication. *Annual Review of Statistics and Its Application*, 4, 31–60.
19. Sterman, J., Fiddaman, T., Franck, T., Jones, A., McCauley, S., Rice, P., Sawin, E., & Siegel, L. (2012). Climate interactive: the C-ROADS climate policy model. *System Dynamics Review*, 28(3), 295–305. https://doi.org/10.1002/sdr.1474
20. Tiemann, L. K., Grandy, A. S., Atkinson, E. E., Marin-Spiotta, E., & McDaniel, M. D. (2015). Crop rotational diversity enhances belowground communities and functions in an agroecosystem. *Ecology Letters*, 18(8), 761–771.
21. Treseder, K. K. (2004). A meta-analysis of mycorrhizal responses to nitrogen, phosphorus, and atmospheric CO₂ in field studies. *New Phytologist*, 164(2), 347–355.
22. van der Bles, A. M., van der Linden, S., Freeman, A. L. J., et al. (2019). Communicating uncertainty about facts, numbers and science. *Royal Society Open Science*, 6(5), 181870. https://doi.org/10.1098/rsos.181870
23. Wadoux, A. M. J.-C., Heuvelink, G. B. M., de Bruin, S., & Brus, D. J. (2021). Spatial cross-validation is not the right way to evaluate map accuracy. *Ecological Modelling*, 457, 109692.
24. Wardle, D. A. (1992). A comparative assessment of factors which influence microbial biomass carbon and nitrogen levels in soil. *Biological Reviews*, 67(3), 321–358.

---

*Beneath the Surface · AI for ALL · IAAC MaAI 2026 · UIA Barcelona — World Capital of Architecture 2026*
