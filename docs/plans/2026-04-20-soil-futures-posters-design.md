# Soil Futures Exhibition — 4 Cylinder Design + Interaction + Seed-paper Wristband

**Date:** 2026-04-20
**Author:** brainstorming session (Rafik + Claude, via Telegram)
**Status:** Approved — ready for GSD phase planning
**Branch:** v6.7
**Budget:** €500 total (hard cap)
**Depends on:** `2026-04-15-exhibition-3d-visuals-design.md` (Cylinder IV's interactive Three.js scene)

## Context

Physical Soil Futures stand for IAAC Barcelona 2026 ("AI for All" exhibition). Four cylinders on a curved wall (confirmed dimensions: 5.00m arc × 1.75m deep, cylinders 40cm ⌀ × 160cm tall), plus a tablet kiosk at the front. Cylinders I–III are static story cylinders; Cylinder IV is the interactive AI station that runs the Three.js simulation. Every visitor leaves with a **seed-paper wristband** — a universal, plantable token they wear during the visit and plant after.

This spec covers: narrative arc, per-cylinder imagery/copy, visual system, visitor interaction, seed-paper wristband take-away, and the €500 budget allocation.

The non-negotiable constraint, inherited from the exhibition's rule: **every visual must pass the "random visitor understands it in 3 seconds" test.** Beauty is not enough — legibility is the higher bar.

## Decisions locked during brainstorm

| Question | Answer |
|----------|--------|
| Hero | A single mycorrhizal fungus network, three life stages across cylinders I–III |
| POV | Single-organism — the fungus is the protagonist, soil biology is the story |
| Visual style | Ghibli-painterly × macro-photographic fusion — real Mediterranean soil/landscape photography with hand-painted luminous fungal threads overlaid |
| Narrative | Grief arc: "ground was still working" → "ground is tired" → "ground is forgetting how to be alive" |
| Honesty calibration | No Eden. Soil has been thinning since the Industrial Revolution — 1950 is the last moment biology still mostly worked |
| Cylinder physical form | **Opaque cylinders with printed wraps** (not transparent acrylic) — budget reality |
| Cylinder dimensions | 40cm ⌀ × 160cm tall, 4 cylinders on the arc |
| Booth footprint | 5.00m wide × 1.75m deep, curved wall |
| Sound | **Silent.** No music, no narration, no ambient audio |
| Reading | Visitors read cylinders I–III silently. Brief copy, nothing wordy |
| Interactivity | **Only Cylinder IV is interactive.** Cylinders I–III are static |
| Interaction mode | **Two-step pick.** Step 1: 5 philosophies (rewild / regenerate / conventional / over-farm / do-nothing). Step 2: 4 climate SSPs. Two taps total |
| Cylinder IV payoff | **A + cheap LED glow ring.** Tablet animates the chosen future, thin LED ring at top of cylinder shifts color to match |
| Take-away | **Universal seed-paper wristband.** Plantable Mediterranean-wildflower-seed paper, single design for all visitors. They wear it during the exhibit, plant it after. **No card, no thermal printer, no QR code.** |
| Continuity anchor | Same fungal network visible in I–III wraps with the same hyphal shape. Only density/color change |
| Deep-time ribbon | Thin printed strip across the top of cylinders I–III: 2000y ago (Roman forests) → 1800 (Industrial Rev.) → 1950 → 2026 → 2076 |
| Text budget | One serif display headline + one subhead + 2-3 brief fact lines per cylinder. Zero paragraphs |

## Legibility rules (non-negotiable)

1. The image alone tells the story in 3 seconds. Text deepens it.
2. Healthy vs degraded is visible without reading — density and color do 80% of the work.
3. No jargon. Plain English. "The ground is tired" not "Soil organic carbon declined 42%."
4. Every factual claim is defensible.
5. One emotion per cylinder. Three cylinders, three emotions, zero overlap.

## The four cylinders

### Cylinder I — PAST (Barcelona, 1950)

**Emotional beat:** Quiet abundance. The last moment biology was still mostly working.

**Image concept (printed wrap):**
Cross-section of a square meter of Barcelona-edge farmland, 1950. Above ground: warm afternoon Mediterranean sun, wild thyme, a donkey path, a child's bare foot at the frame edge. Below ground (the meat of the image): a dense gold-white mycorrhizal network glowing through dark loam, entwined around plant roots, dense like lace. Earthworms, beetles, seeds, life everywhere underground. Ghibli-painterly overlay on macro-photographic soil base, warm gold palette.

**Copy (tight):**
- **Headline:** *The ground was still working.*
- **Subhead:** *Barcelona, 1950. Small farms. Alive soil.*
- **Facts:** 2× denser fungi than today. The Llobregat was still farmland.

### Cylinder II — PRESENT (Barcelona, 2026)

**Emotional beat:** Fragile. Quiet. Not-yet-lost.

**Image concept (printed wrap):**
Same cross-section, same square meter. Above: industrial farm edge or warehouse lot, asphalt in the distance, one dry weed. Below: the fungal network is thinner, grey-silver, patches have gone dark. Some threads still glow. Fewer roots. One earthworm.

**Copy (tight):**
- **Headline:** *The ground is tired.*
- **Subhead:** *Same patch. 76 years later. Barely here.*
- **Facts:** Half the soil carbon lost. Still refusing to die.

### Cylinder III — FUTURE (Barcelona, 2076, SSP2 business-as-usual)

**Emotional beat:** Grief without melodrama. The end of a two-century curve.

**Image concept (printed wrap):**
Same square meter, 50 years on. Above: cracked dry earth, no plants, hot dust, distant city silhouette. Below: most of the network is dark. A single small cluster still glows — a last ember. No worms. Bleached palette, dim ember tones.

**Copy (tight):**
- **Headline:** *The ground is forgetting how to be alive.*
- **Subhead:** *Barcelona, 2076. If we change nothing.*
- **Facts:** Predicted by AI. Not the worst case — the expected one.

### Cylinder IV — AI STATION (interactive)

**Emotional beat:** Agency. Hope earned, not given.

**Physical form:** Opaque cylinder with printed wrap + tablet mounted on or beside it + a thin frosted acrylic LED glow ring at the top. When the visitor picks a future, the ring shifts color to match (green-gold for regenerate, ember for over-farm, pale for collapse, bright gold for thriving).

**Image concept (printed wrap):**
Split composition around the cylinder.
- Left half: the same fungus network from I–III, shown as a decision tree — branching paths glowing different colors (green-gold regenerate, warm ember business-as-usual, pale collapse, bright gold thriving).
- Right half: the AI shown abstractly — constellation-like nodes in the same painterly Ghibli glow, as if the fungus has become a neural network.

**Tablet UX — two-step pick + results screen:**

*Screen 1 — "What do we do with the land?"* (5 buttons, big, icon + plain words):
- 🌱 Let nature come back
- 🌾 Regenerate the land
- 🚜 Keep farming the way we do now
- 🌵 Over-farm it
- 🪨 Do nothing

*Screen 2 — "And what about the climate?"* (4 buttons):
- 🌤 Cool future
- ☀️ Middle of the road
- 🌵 Drought future
- 🔥 Hottest future

*Screen 3 — Animation + results.* ~15-20 seconds of soil transformation based on the simulation engine output for that combination. Overlay the three key numbers on the animation (e.g. *+40% biodiversity · +25% carbon · -30% erosion · by 2076*) and one short honest interpretation line. LED glow ring shifts to the matching color.

*Screen 4 — Take-away prompt.* A simple final screen: *"Take a wristband as you leave. Plant it when you get home."* A basket of universal seed-paper wristbands sits on the plinth next to the tablet — self-serve.

**Copy on the wrap (short blocks around the cylinder):**
1. *How we predict.* We teach an AI what happens when you do X vs Y, using 50 years of real soil measurements. Then we let it run the next 50 years thousands of times.
2. *What AI is here.* A time machine for soil. Classical science tells us what soil *was*. AI rolls possible futures forward.
3. *What you can do.* Touch the tablet. Pick a future. See it.

## Visual system

**Shared across cylinders I–III:**
- Same framing and composition (cross-section of one square meter), same camera angle. Only the content inside the frame changes across time.
- Same hyphal shape and curve for the fungus network. Only density and color shift.
- Serif display font for headlines. Handwritten-feel font for subheads. Clean sans for fact lines.
- 1 headline + 1 subhead + 2-3 fact lines per cylinder. No paragraphs.

**Color arc:**

| Cylinder | Above-ground palette | Fungal-thread color | Feel |
|----------|---------------------|---------------------|------|
| I — Past | Warm gold, olive, ochre | Gold-white, dense | Abundant |
| II — Present | Muted silver, dusty green, grey | Silver, patchy | Tired |
| III — Future | Bleached, hot dust, no green | Dim ember, fragmented | Quiet |
| IV — AI | Deep blue-black, painterly glow | Electric gold + blue constellation | Agency |

**Deep-time ribbon:**
Thin printed strip running across the top of cylinders I, II, III. Markers: 2000y ago (Roman forests) | 1800 (Industrial Rev.) | 1950 | 2026 | 2076. A faint descending line traces soil carbon across the ribbon. Each cylinder highlights its own date.

## Visitor interaction flow

| Time | What happens | Sound | Visual |
|------|-------------|-------|--------|
| 0:00 | Visitor approaches booth, sees 4 cylinders on curved wall | Silent | 4 cylinders visible |
| 0:05–0:40 | Reads cylinders I → II → III left to right | Silent | Static imagery + brief copy |
| 0:40–0:50 | Arrives at Cylinder IV. Tablet shows attract loop ("Touch a column. Pick a future.") | Silent | Tablet gently pulses |
| 0:50–1:05 | Screen 1 — picks a philosophy | Silent | Big tap, screen transitions |
| 1:05–1:20 | Screen 2 — picks a climate | Silent | Big tap |
| 1:20–1:45 | Simulation animation plays on tablet with numbers overlay. LED glow ring shifts color. | Silent | Tablet animates the future; ring glows; three numbers appear |
| 1:45–2:00 | Final screen prompts them to take a wristband from the basket on the plinth. | Silent | Static prompt |
| 2:00 | Visitor walks away with seed-paper wristband. Kiosk resets after 15s idle. | Silent | Attract loop resumes |

## Take-away — seed-paper wristband

**Format:** universal seed-paper wristband. One design for every visitor (no per-combo variants). Mediterranean-wildflower seeds embedded in recycled paper, cut into wristband strips, closed with a small adhesive tab.

**Design (single universal):**
- Exhibit name — *Soil Futures · Barcelona 2026*
- A small painterly motif of the fungal network (same as the cylinders, so the wristband reads as part of the family)
- Plain-language instruction: *"Plant me when you get home — Mediterranean wildflowers"*
- Small care line: *"Soil, water, sunlight. A few weeks."*

**Dimensions:** ~20-25 cm long × 1.5-2 cm wide, strip form. Fits most adult wrists.

**Seed mix:** Mediterranean natives only (lavender, thyme, chamomile, poppy, cornflower). NEVER a generic wildflower mix — some commercial mixes contain non-native or invasive species. The supplier must confirm the seed list.

**Rationale for universality (not per-combo variants):**
The tablet carries the personalization — the chosen future, the numbers, the interpretation. The wristband carries the *shared* act: everyone who leaves the exhibit plants a future. This splits the memento into two channels (data-memento on the tablet, earth-memento on the wrist) and is cheaper than 4+ pre-printed variants.

**Distribution:**
Basket on the plinth next to the tablet, self-serve. Final tablet screen prompts: *"Take a wristband as you leave."* No staff required.

**Where the combo-specific data lives:**
On the tablet during the animation (numbers + interpretation overlay). If visitors want to remember the specifics they'll photograph the screen — which is fine; phones are already pointed at exhibits anyway.

## Budget allocation (€500 hard cap)

| Item | Estimate |
|---|---|
| 4 opaque cylinders (Sonotube cardboard or PVC, 40cm ⌀ × 160cm, painted or wrapped) | €80-120 |
| Printed wraps for I, II, III, IV (high-res matte vinyl, local print shop) | €90-140 |
| Cylinder IV glow ring (frosted acrylic + WS2812 LED + ESP32 controller) | €30-50 |
| Tablet for Cylinder IV (reuse existing iPad/Android) | €0 |
| Plinth / tablet stand (plywood + paint) | €20-30 |
| **Seed-paper wristbands** (universal design, ~100-200 units, Mediterranean wildflower mix) | **€100-150** |
| Deep-time ribbon printed strip | €10-15 |
| Base platform / floor mat to define booth | €40-60 |
| Contingency | €30-50 |
| **Total** | **~€400-615** (target ~€500 ceiling; tightest ~€400) |

**Out-of-scope at this budget:**
- ❌ Transparent acrylic cylinders with real soil inside (Term 2 "Beneath the Surface" concept) — €400-800 just for the tubes
- ❌ Wall projection option C (€600-1500)
- ❌ Full-length LED strips inside each cylinder (€200+ across 4 cylinders) — only the top ring on Cylinder IV gets LEDs
- ❌ Thermal photo printer + ZINK card stock (dropped with the card concept) — saved ~€130-180
- ❌ Per-combo wristband variants (minimum-order math doesn't fit €500) — single universal design only

## Image-generation workflow

AI image generation produces: the four cylinder wraps (I, II, III, IV), the attract-loop visuals on the tablet, the 20 painterly animation frames shown during Screen 3 of the interaction (one painterly end-state image per combo, used during the simulation animation overlay), and the small fungal-network motif printed on the seed-paper wristband.

**Pipeline:**
1. Claude drafts a detailed prompt file per asset (subject, composition, style refs, color palette, continuity constraints, negative prompts).
2. Rafik runs each through the chosen image-gen API.
3. Iterate 3-5 generations per asset. Pick winners, refine, regenerate until the cylinder wraps read as one family and the 20 animation end-states look like variations of the same universe.
4. Compositing in Figma or Photoshop — text overlay, ribbon, final grading.
5. Rafik approves. Print-ready files exported.

**Budget estimate:** ~80-120 API generations total (4 cylinder wraps × 5 iterations + 20 animation end-states × 3 iterations + wristband motif + attract-loop assets).

**API options (final pick pending Rafik's account access):**

| API | Strengths | Cost/image |
|-----|-----------|------------|
| Flux Pro 1.1 (fal.ai / Replicate) | Photographic, controllable | ~€0.04 |
| Midjourney v6 (unofficial API) | Painterly, "Ghibli" signal | ~€0.10 |
| Google Imagen 3 / Nano Banana (Gemini Flash Image) | Already scaffolded in `scene3d/` | ~€0.03 |
| DALL·E 3 | Prompt adherence | ~€0.08 |

**Recommendation:** Flux Pro for the macro-photographic base, Midjourney for the painterly finish. If unavailable, fall back to Nano Banana since plumbing exists. Image-gen total at most €15 at current rates — negligible next to hardware.

## Dependencies

- **2026-04-15 exhibition 3D visuals design** — Cylinder IV's tablet animation comes from the Three.js scene being built there.
- **Python simulation engine** — the three numbers overlaid on the tablet animation come from `backend/soil_model/engine.py` output for the chosen philosophy × SSP combination. This already works for 20 combinations (5 philosophies × 4 SSPs).
- **Seed-paper wristband supplier** — lead time is 2-3 weeks for bulk orders. This is the longest-lead-time item in the build and should be ordered first.
- **Citation sweep** — fact-line claims ("2× denser fungi," "Half the soil carbon lost," etc.) need traceable citations (Calvo de Anta, Álvaro-Fuentes, Rubio groups) before print to avoid fact-check risk.

## Open items to confirm before print

- Which tablet we're using — Rafik's existing iPad/Android is the default (budget assumes €0 here)
- Which image-gen API (Flux Pro / Midjourney / Nano Banana / DALL·E) — depends on account access
- Final copy wording after citation sweep (some fact-line numbers may need to move)
- Supplier for the cardboard/PVC cylinders (local Barcelona source once on-site)
- Supplier for the printed vinyl wraps (local Barcelona print shop, ~3-5 day turnaround)
- **Seed-paper wristband supplier** (Growing Paper NL, Botanical Paperworks, Seedpaper.es, or Pappier FR — request Mediterranean native seed mix, ask about minimum order, 2-3 week lead time)

## What this spec does not cover

- The interactive simulation inside Cylinder IV's tablet (covered by the 2026-04-15 spec — this spec just calls it)
- The scientific evaluation/critique of the simulation's accuracy from a data-science / AI-prediction lens (deferred — separate thread)
- Taqasim-AI and unrelated projects in the same Telegram session (separate specs)

## Success criteria

- A random visitor walking up to Cylinder I understands in 3 seconds that it shows Barcelona's soil in 1950, full of life.
- Walking past all three soil cylinders, without stopping to read, they feel the arc: abundance → tired → forgetting.
- Reading only headlines they come away with: "Soil has been thinning for 200 years. Still here, barely. Could go either way from here. And I can see the futures I didn't choose."
- Cylinder IV explicitly answers "what is AI actually doing here" on the printed wrap — no hand-waving.
- Every visitor who interacts walks away with a plantable seed-paper wristband — a living souvenir of Barcelona 2026 that becomes wildflowers where they live.
- A measurable share (>30%) of wristbands actually get planted (self-reported, optional post-exhibit follow-up).
- Total build cost ≤ €500.

## Next steps after this spec approves

1. Invoke `writing-plans` to create the implementation plan covering:
   - Drafting prompt files for AI image generation (4 cylinder wraps + 20 animation end-states + wristband motif + attract loop)
   - Citation sweep for fact lines
   - Choosing and provisioning the image-gen API
   - Iteration rounds for each asset
   - Figma/Photoshop compositing
   - Hardware sourcing (cylinders, tablet reuse, LED ring + ESP32, plinth, seed-paper wristband supplier)
   - Tablet UX implementation (two-step pick + simulation animation with numbers overlay + wristband prompt)
   - Print prep and physical assembly
2. Seed-paper wristband supplier selection + order (min 100 units, Mediterranean natives only, lead time ~2-3 weeks — order early).
3. Fabrication: can begin in parallel with image generation once dimensions are locked.
4. Begin prompt drafting and first-round generation.
