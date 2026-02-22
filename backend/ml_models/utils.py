import os
import re

# Depth-band labels and ordering for soil datasets
DEPTH_ORDER = ['b0', 'b10', 'b30', 'b60', 'b100', 'b200']
DEPTH_LABELS = {
    'b0': '0–5 cm', 'b10': '10–30 cm', 'b30': '30–60 cm',
    'b60': '60–100 cm', 'b100': '100–200 cm', 'b200': '200 cm+',
}

# Display metadata per dataset name (as stored in filenames)
_DATASET_META = {
    'Organic_Carbon':       {'display': 'Organic Carbon (g/kg)',     'units': 'g/kg',   'description': 'Organic carbon concentration (OpenLandMap/SoilGrids)'},
    'Soil_pH':              {'display': 'Soil pH (H₂O)',             'units': 'pH',     'description': 'Water-extracted soil pH (USDA calibration)'},
    'Bulk_Density':         {'display': 'Bulk Density (tonnes/m³)',  'units': 't/m³',   'description': 'Fine-earth bulk density (USDA-4A1H)'},
    'Sand_Content':         {'display': 'Sand Content (%)',          'units': '%',      'description': 'Sand fraction (USDA-3A1A1A)'},
    'Clay_Content':         {'display': 'Clay Content (%)',          'units': '%',      'description': 'Clay fraction (USDA-3A1A1A)'},
    'Soil_Texture':         {'display': 'Soil Texture Class',        'units': 'class',  'description': 'USDA soil texture classification (1–12)'},
    'Precipitation_CHIRPS': {'display': 'Precipitation (mm/yr)',     'units': 'mm/yr',  'description': 'Annual precipitation — CHIRPS (2000–2024)'},
    'MODIS_Land_Cover':     {'display': 'Land Cover (MODIS)',        'units': 'class',  'description': 'MODIS MCD12Q1 IGBP land cover (2001–2023)'},
}

# Preferred primary bands for temporal (non-soil) datasets
_TEMPORAL_PRIMARY = {
    'Precipitation_CHIRPS': 'precipitation',
    'MODIS_Land_Cover':     'LC_Type1',
}

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data_downloader')
_YEAR_RE  = re.compile(r'^year=(\d{4})$')


# ── Static registry (flat files — soil depth bands) ───────────────────────────

def _scan_local_files():
    """Scan flat tif files (soil depth bands) from typology subfolders."""
    registry = {}
    for typology in ['soil', 'climate', 'land_cover']:
        folder = os.path.join(DATA_DIR, typology)
        if not os.path.isdir(folder):
            continue
        for fname in sorted(os.listdir(folder)):
            if not fname.endswith('.tif'):
                continue
            parts = fname.rsplit('.', 2)
            ds_name = parts[0]
            band    = parts[1] if len(parts) >= 3 else 'default'
            path    = os.path.join(folder, fname)
            if ds_name not in registry:
                meta = _DATASET_META.get(ds_name, {})
                registry[ds_name] = {
                    'name':        ds_name,
                    'typology':    typology,
                    'local_files': {},
                    'display':     meta.get('display', ds_name.replace('_', ' ')),
                    'units':       meta.get('units', ''),
                    'description': meta.get('description', ''),
                }
            registry[ds_name]['local_files'][band] = path
    return registry


# ── Temporal registry (year=XXXX/ subfolders — climate / land_cover) ─────────

def _scan_temporal_files():
    """
    Scan year=XXXX/ subdirectories within typology folders.

    Returns:
        {dataset_name: {year: {band: path}}}
    """
    temporal: dict[str, dict[int, dict[str, str]]] = {}
    for typology in ['climate', 'land_cover']:
        folder = os.path.join(DATA_DIR, typology)
        if not os.path.isdir(folder):
            continue
        for entry in sorted(os.listdir(folder)):
            m = _YEAR_RE.match(entry)
            if not m:
                continue
            year      = int(m.group(1))
            year_path = os.path.join(folder, entry)
            for fname in sorted(os.listdir(year_path)):
                if not fname.endswith('.tif'):
                    continue
                parts   = fname.rsplit('.', 2)
                ds_name = parts[0]
                band    = parts[1] if len(parts) >= 3 else 'default'
                path    = os.path.join(year_path, fname)
                temporal.setdefault(ds_name, {}).setdefault(year, {})[band] = path
    return temporal


LOCAL_REGISTRY    = _scan_local_files()
TEMPORAL_REGISTRY = _scan_temporal_files()  # {name: {year: {band: path}}}


# ── Ordered dataset list for /api/datasets ────────────────────────────────────

DATASETS = []
for _name, _entry in LOCAL_REGISTRY.items():
    _years = sorted(TEMPORAL_REGISTRY.get(_name, {}).keys())
    DATASETS.append({
        'name':           _entry['display'],
        'internal_name':  _name,
        'typology':       _entry['typology'],
        'units':          _entry['units'],
        'description':    _entry['description'],
        'local_files':    _entry['local_files'],
        'available_years': _years,           # [] for static soil datasets
        'is_temporal':    len(_years) >= 2,  # True if we have multi-year data
    })


# ── Lookup helpers ────────────────────────────────────────────────────────────

def find_dataset(display_name: str) -> dict:
    """Return a dataset entry by its display name (falls back to first)."""
    for ds in DATASETS:
        if ds['name'] == display_name:
            return ds
    return DATASETS[0] if DATASETS else {}


def primary_band(ds: dict) -> str | None:
    """Return the best single-band path for a dataset (b0 for soil, else first)."""
    files = ds.get('local_files', {})
    for band in DEPTH_ORDER:
        if band in files:
            return files[band]
    return next(iter(files.values()), None)


def ordered_bands(ds: dict) -> list[tuple[str, str]]:
    """Return (label, path) pairs in depth order (soil) or alphabetical."""
    files = ds.get('local_files', {})
    ordered = [(b, files[b]) for b in DEPTH_ORDER if b in files]
    if ordered:
        return [(DEPTH_LABELS.get(b, b), p) for b, p in ordered]
    return [(b, p) for b, p in sorted(files.items())]


def available_years(dataset_name: str) -> list[int]:
    """Return sorted years that have real downloaded data for a temporal dataset."""
    return sorted(TEMPORAL_REGISTRY.get(dataset_name, {}).keys())


def temporal_primary_band(dataset_name: str, year: int) -> str | None:
    """Return the preferred band path for a given dataset + year."""
    yr_data = TEMPORAL_REGISTRY.get(dataset_name, {}).get(year, {})
    if not yr_data:
        return None
    preferred = _TEMPORAL_PRIMARY.get(dataset_name)
    if preferred and preferred in yr_data:
        return yr_data[preferred]
    return next(iter(yr_data.values()), None)


# Display metadata per dataset name (as stored in filenames)
_DATASET_META = {
    'Organic_Carbon':       {'display': 'Organic Carbon (g/kg)',      'units': 'g/kg',   'description': 'Organic carbon concentration (OpenLandMap/SoilGrids)', 'year': 'composite'},
    'Soil_pH':              {'display': 'Soil pH (H₂O)',              'units': 'pH',     'description': 'Water-extracted soil pH (USDA calibration)',            'year': 'composite'},
    'Bulk_Density':         {'display': 'Bulk Density (tonnes/m³)',   'units': 't/m³',   'description': 'Fine-earth bulk density (USDA-4A1H)',                   'year': 'composite'},
    'Sand_Content':         {'display': 'Sand Content (%)',           'units': '%',      'description': 'Sand fraction (USDA-3A1A1A)',                           'year': 'composite'},
    'Clay_Content':         {'display': 'Clay Content (%)',           'units': '%',      'description': 'Clay fraction (USDA-3A1A1A)',                           'year': 'composite'},
    'Soil_Texture':         {'display': 'Soil Texture Class',         'units': 'class',  'description': 'USDA soil texture classification (1–12)',               'year': 'composite'},
    'Precipitation_CHIRPS': {'display': 'Precipitation (mm/yr)',      'units': 'mm/yr',  'description': 'Annual precipitation — CHIRPS 2020 mean',              'year': '2020'},
    'MODIS_Land_Cover':     {'display': 'Land Cover (MODIS)',         'units': 'class',  'description': 'MODIS MCD12Q1 land cover type (LC_Type1)',              'year': '2020'},
}

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data_downloader')

def _scan_local_files():
    """Scan data_downloader subfolders and return a registry keyed by dataset name."""
    registry = {}
    typologies = ['soil', 'climate', 'land_cover']
    for typology in typologies:
        folder = os.path.join(DATA_DIR, typology)
        if not os.path.isdir(folder):
            continue
        for fname in sorted(os.listdir(folder)):
            if not fname.endswith('.tif'):
                continue
            parts = fname.rsplit('.', 2)
            ds_name = parts[0]
            band = parts[1] if len(parts) >= 3 else 'default'
            path = os.path.join(folder, fname)
            if ds_name not in registry:
                registry[ds_name] = {
                    'name': ds_name,
                    'typology': typology,
                    'local_files': {},
                }
                meta = _DATASET_META.get(ds_name, {})
                registry[ds_name]['display'] = meta.get('display', ds_name.replace('_', ' '))
                registry[ds_name]['units'] = meta.get('units', '')
                registry[ds_name]['description'] = meta.get('description', '')
                registry[ds_name]['year'] = meta.get('year', '')
            registry[ds_name]['local_files'][band] = path
    return registry

LOCAL_REGISTRY = _scan_local_files()

# Ordered list for the /api/datasets endpoint
DATASETS = []
for _name, _entry in LOCAL_REGISTRY.items():
    DATASETS.append({
        'name': _entry['display'],
        'internal_name': _name,
        'typology': _entry['typology'],
        'units': _entry['units'],
        'description': _entry['description'],
        'local_files': _entry['local_files'],
        'year': _entry.get('year', ''),
    })

def find_dataset(display_name: str):
    """Return a dataset entry by its display name (falls back to first)."""
    for ds in DATASETS:
        if ds['name'] == display_name:
            return ds
    return DATASETS[0] if DATASETS else {}

def primary_band(ds: dict) -> str:
    """Return the best single band path for a dataset (b0 for soil, else first band)."""
    files = ds.get('local_files', {})
    for band in DEPTH_ORDER:
        if band in files:
            return files[band]
    # For non-soil datasets pick the first available file
    return next(iter(files.values()), None)

def ordered_bands(ds: dict) -> list[tuple[str, str]]:
    """Return (band_label, path) pairs in depth order (soil) or file order."""
    files = ds.get('local_files', {})
    # Try soil depth order first
    ordered = [(b, files[b]) for b in DEPTH_ORDER if b in files]
    if ordered:
        return [(DEPTH_LABELS.get(b, b), p) for b, p in ordered]
    # Fall back to alphabetical
    return [(b, p) for b, p in sorted(files.items())]

