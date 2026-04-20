"""
5 land management philosophies mapped to concrete simulation parameters.

Each philosophy defines species choice, management practices, amendments,
and educational content for the exhibition.
"""

PHILOSOPHIES = {
    "let_nature_recover": {
        "display_name": "Let Nature Recover",
        "icon": "🌿",
        "color": "#84CC16",
        "tagline": "Walk away. Let plants come back on their own.",
        "description": (
            "Stop managing the land. Weeds come first, then bushes, then small "
            "trees, then an oak forest — about 20 to 30 years. Free, but slow. "
            "The land decides what grows."
        ),
        "species":            "maquis",
        "planting_density":   0,          # natural colonisation
        "initial_cover":      0.15,
        "amendments":         [],
        "tillage":            False,
        "P_factor":           0.70,       # maquis root system ≈ contour strip farming protection
        "C_factor_mulch":     0.0,
        "managed_fire":       False,
        "grazing":            False,
        "grazing_intensity":  0.0,
        "biochar_t_ha":       0,
        "compost_t_ha_yr":    0,
        # Climate-independent base input from the spontaneous herb + grass
        # layer that establishes under natural succession in Mediterranean
        # abandoned fields. Campos et al. 2013 (Agric Ecosystems & Env) and
        # Bonet 2004 (J Arid Env) measure 2-4 t DM/ha/yr continuous root
        # turnover from opportunistic annuals and perennial grasses in Med
        # abandoned arable — independent of tree canopy. Under rewilding the
        # full herb layer establishes quickly and its stable root carbon
        # input (after 5-10 years of succession) supports a long-term SOC
        # trajectory matching Poeplau & Don 2015 (set-aside meta-analysis,
        # n=62 chronosequences): mild loss in the first decade, stable or
        # small gain thereafter. 0.30 g/kg/yr reflects the high end of
        # measured inputs at maturity.
        "base_vegetation_C_input": 0.30,
        "fertilizer_N_kg_ha_yr": 0,
        "expected_50yr": {
            "soc_change_pct": -7,          # transitional decline under fire regime; recovery by yr 100
            "erosion_change_pct": -45,
            "biodiversity_change_pct": +40,
            "carbon_change_pct": -5,
        },
        "learn": {
            "title": "Rewilding & Natural Succession",
            "body": (
                "Rewilding removes human pressure and allows natural processes to restore "
                "biodiversity and soil function. Mediterranean maquis is a remarkably "
                "resilient pioneer community — holm oak can colonise within 20 years. "
                "Mycorrhizal networks recover within 5-10 years under natural succession."
            ),
            "pros": ["Self-sustaining", "High biodiversity recovery", "Low cost"],
            "cons": ["Slow carbon gain", "Fire risk in early years", "No food production"],
        },
    },

    "traditional_farming": {
        "display_name": "Traditional Farming",
        "icon": "🫛",
        "color": "#A16207",
        "tagline": "A few oak trees. Some sheep. No chemicals.",
        "description": (
            "Plant oak trees spread far apart. Let sheep eat the grass between "
            "them and drop manure back on the ground. No factory fertiliser. "
            "This is how Spain farmed for 2,000 years."
        ),
        "species":            "agroforestry",
        "planting_density":   50,         # trees/ha (dehesa density)
        "initial_cover":      0.20,
        "amendments":         ["compost"],
        "tillage":            False,
        "P_factor":           0.70,       # rotational grazing reduces runoff
        "C_factor_mulch":     0.15,
        "managed_fire":       False,
        "grazing":            True,
        "grazing_intensity":  0.30,       # moderate stocking rate
        "biochar_t_ha":       0,
        "compost_t_ha_yr":    2.0,        # livestock manure return
        "compost_years":      None,       # perpetual — annual manure return
        "compost_hum_fraction": 0.10,    # manure: low direct humification (less stable than mature compost)
        "base_vegetation_C_input": 0.25,  # perennial pasture root turnover + herb layer (g/kg/yr)
        # In real dehesa: grass + herbs between trees provide ~2.5 t DM/ha/yr root input
        "fertilizer_N_kg_ha_yr": 0,
        "expected_50yr": {
            "soc_change_pct": -11,         # transitional — trees establishing; pasture layer maintains soil
            "erosion_change_pct": -30,
            "biodiversity_change_pct": +45,
            "carbon_change_pct": -8,
        },
        "learn": {
            "title": "Dehesa Agroforestry",
            "body": (
                "The dehesa is one of Europe's most biodiverse agricultural systems. "
                "Sparse oak + livestock creates a mosaic of habitats. The trees fix "
                "nutrients, provide shade, and their deep roots access subsoil moisture. "
                "Manure returns close the nutrient cycle without synthetic fertilisers."
            ),
            "pros": ["Food + carbon", "Biodiversity friendly", "Culturally rich"],
            "cons": ["Labour intensive", "Slow tree establishment", "Vulnerable to overgrazing"],
        },
    },

    "industrial_agriculture": {
        "display_name": "Industrial Farming",
        "icon": "🌾",
        "color": "#6B7280",
        "tagline": "Big machines. Same crop every year. Chemical food.",
        "description": (
            "Grow one crop on the whole field. Plow it up twice a year. Spray "
            "factory fertiliser. The ground is bare all winter. You get lots "
            "of food right now — but the soil slowly dies."
        ),
        "species":            None,        # annual crops — no permanent vegetation
        "planting_density":   0,
        "initial_cover":      0.30,        # seasonal crop (bare in winter)
        "amendments":         ["mineral_fertilizer"],
        "tillage":            True,
        "tillage_frequency_yr": 2,
        "P_factor":           1.0,
        "C_factor_mulch":     0.0,
        "managed_fire":       False,
        "grazing":            False,
        "grazing_intensity":  0.0,
        "biochar_t_ha":       0,
        "compost_t_ha_yr":    0,
        "fertilizer_N_kg_ha_yr": 150,
        # Even "perfectly weed-free" industrial monoculture leaves residual
        # stubble + volunteer weeds + uncompensated root mass that doesn't
        # show up in the formal crop litter accounting. Álvaro-Fuentes et al.
        # (2008, STOTEN 398) measure 0.15–0.25 g/kg/yr residual C input even
        # under intensive Catalan dryland cereal rotations. Without this the
        # RothC pools drain to the IOM floor over 50 years, which is more
        # extreme than the literature SOC loss range (-30 to -50%).
        "base_vegetation_C_input": 0.18,
        "expected_50yr": {
            "soc_change_pct": -55,         # severe degradation under continuous tillage + SSP5-8.5
            "erosion_change_pct": +120,
            "biodiversity_change_pct": -98,
            "carbon_change_pct": -45,
        },
        "learn": {
            "title": "Industrial Monoculture",
            "body": (
                "Modern intensive agriculture achieves high short-term yields but "
                "degrades soil structure, reduces biodiversity, and increases erosion. "
                "Repeated tillage breaks up soil aggregates. Synthetic nitrogen suppresses "
                "mycorrhizal networks. Bare winter soil is exposed to Mediterranean storms."
            ),
            "pros": ["Highest food yield", "Predictable output"],
            "cons": ["SOC loss ~0.3%/yr", "Erosion × 3-5×", "Biodiversity collapse", "Fertiliser runoff"],
        },
    },

    "maximum_restoration": {
        "display_name": "Full Repair",
        "icon": "🌳",
        "color": "#059669",
        "tagline": "Plant lots of trees. Feed the soil. Build steps on the slopes.",
        "description": (
            "Plant many oak trees close together. Mix charred wood into the "
            "soil (it stays for a thousand years). Spread compost for the "
            "first five years. Cover bare ground with little plants. Build "
            "small steps on the slopes so rain doesn't wash the soil away. "
            "Expensive up front — best recovery science can offer."
        ),
        "species":            "holm_oak",
        "planting_density":   400,         # trees/ha (dense restoration)
        "initial_cover":      0.10,        # initially low (newly planted)
        "amendments":         ["biochar", "compost", "cover_crops"],
        "tillage":            False,
        "P_factor":           0.15,        # terracing — very effective erosion control
        "C_factor_mulch":     0.40,        # heavy mulching
        "managed_fire":       False,
        "grazing":            False,
        "grazing_intensity":  0.0,
        "biochar_t_ha":       10,          # one-time application at year 0 (→ IOM pool)
        "compost_t_ha_yr":    5.0,         # first 5 years only
        "compost_years":      5,           # only during establishment phase
        "compost_hum_fraction": 0.50,    # mature compost: high direct humification
        "cover_crop_t_ha_yr": 3.0,         # cover crops during tree establishment: 3 t DM/ha/yr
        "cover_crop_years":   10,          # first 10 years while holm oak is establishing
        "fire_probability_multiplier": 0.50,  # terracing + mulching + managed restoration ÷2 fire risk
        "fertilizer_N_kg_ha_yr": 0,
        "expected_50yr": {
            "soc_change_pct": +13,         # biochar + compost + cover crops offset slow oak growth
            "erosion_change_pct": -85,     # terracing very effective
            "biodiversity_change_pct": +50,
            "carbon_change_pct": +10,
        },
        "learn": {
            "title": "Intensive Ecological Restoration",
            "body": (
                "Maximum restoration combines all evidence-based techniques: "
                "biochar improves water retention and provides stable carbon for 1,000+ years; "
                "compost kick-starts the microbial food web; holm oak is the climax species "
                "for this region; terracing intercepts runoff before it erodes. "
                "This is what restoration scientists call 'assisted natural recovery'."
            ),
            "pros": ["Fastest SOC gain", "Lowest erosion", "Highest biodiversity potential"],
            "cons": ["High upfront cost", "Labour intensive", "Initial vulnerability"],
        },
    },

    "fast_fix": {
        "display_name": "The Quick Fix (Eucalyptus)",
        "icon": "⚡",
        "color": "#DC2626",
        "tagline": "Fast-growing trees. Looks green. Ends badly.",
        "description": (
            "Plant lots of eucalyptus trees because they grow super fast. "
            "Looks great for a few years. But these trees drink huge amounts "
            "of water, make the soil sour, kill other plants, and catch fire "
            "like matchsticks. A warning story."
        ),
        "species":            "eucalyptus",
        "planting_density":   1000,        # trees/ha (dense plantation)
        "initial_cover":      0.10,
        "amendments":         ["mineral_fertilizer"],
        "tillage":            False,
        "P_factor":           1.0,
        "C_factor_mulch":     0.0,
        "managed_fire":       False,
        "grazing":            False,
        "grazing_intensity":  0.0,
        "biochar_t_ha":       0,
        "compost_t_ha_yr":    0,
        "fertilizer_N_kg_ha_yr": 200,
        # Eucalyptus drops prolific litter (10-15 t DM/ha/yr) but most of it
        # is allelopathic/tannin-rich and slow to incorporate. Calviño-Cancela
        # (2013, For Ecol Manag 305) measures ~0.10 g/kg/yr of residual stable
        # C input despite suppressed understory. Tuning to the lower end of
        # literature SOC loss range for eucalyptus plantations (-30 to -50%).
        "base_vegetation_C_input": 0.10,
        "expected_50yr": {
            "soc_change_pct": -43,        # acidification + water depletion collapse soil carbon
            "erosion_change_pct": -5,     # cover helps but allelopathic litter limits aggregates
            "biodiversity_change_pct": -90,
            "carbon_change_pct": -35,
        },
        "learn": {
            "title": "Eucalyptus — The False Friend",
            "body": (
                "Eucalyptus grows 3-5× faster than native species and is widely planted "
                "for biomass. But its allelopathic litter inhibits native plant regeneration, "
                "its high water demand (1.2 t water per t biomass per metre of rooting) "
                "lowers water tables, and its high oil content creates explosive fire behaviour. "
                "Several Iberian catastrophic fires have burned through eucalyptus plantations."
            ),
            "pros": ["Fast biomass growth", "Carbon sequestration short-term"],
            "cons": [
                "Water table depletion", "Soil acidification (pH -0.5 to -1.5)",
                "Fire risk ×3", "Near-zero understory biodiversity",
                "Allelopathic litter suppresses natives",
            ],
        },
    },
}


def get_philosophy(name: str) -> dict:
    """Return philosophy parameters by key. Raises ValueError if not found."""
    if name not in PHILOSOPHIES:
        raise ValueError(
            f"Unknown philosophy '{name}'. Available: {list(PHILOSOPHIES.keys())}"
        )
    return PHILOSOPHIES[name]


def list_philosophies() -> list:
    """Return list of philosophy metadata for the exhibition UI."""
    return [
        {
            "id":           key,
            "display_name": p["display_name"],
            "icon":         p["icon"],
            "color":        p["color"],
            "tagline":      p.get("tagline", ""),
            "description":  p["description"],
            "expected_50yr": p.get("expected_50yr", {}),
        }
        for key, p in PHILOSOPHIES.items()
    ]
