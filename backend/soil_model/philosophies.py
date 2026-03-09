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
        "description": (
            "Stop all human intervention. Allow natural succession: bare soil → "
            "annual plants → maquis scrub → oak woodland over decades. "
            "Slow but self-sustaining. The land chooses its own path."
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
        "description": (
            "Dehesa-style agroforestry: sparse holm oak + livestock on rotational "
            "grazing. Compost returned to soil. No synthetic inputs. "
            "The Iberian Peninsula's historic land use for 2,000 years."
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
        "display_name": "Industrial Agriculture",
        "icon": "🌾",
        "color": "#6B7280",
        "description": (
            "Intensive monoculture with synthetic fertilisers, biannual tillage, "
            "and no permanent vegetation. Maximum short-term yield, "
            "with known long-term soil degradation."
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
        "display_name": "Maximum Restoration",
        "icon": "🌳",
        "color": "#059669",
        "description": (
            "All-in restoration: holm oak at high density, biochar amendment, "
            "compost for 5 years, cover crops, terracing. "
            "The fastest scientifically-supported route to soil recovery."
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
        "display_name": "Fast Fix (Eucalyptus)",
        "icon": "⚡",
        "color": "#DC2626",
        "description": (
            "Dense eucalyptus plantation with fertiliser. Fast biomass accumulation "
            "looks good on paper but depletes groundwater, acidifies soil, "
            "and creates catastrophic fire risk. A cautionary tale."
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
            "description":  p["description"],
            "expected_50yr": p.get("expected_50yr", {}),
        }
        for key, p in PHILOSOPHIES.items()
    ]
