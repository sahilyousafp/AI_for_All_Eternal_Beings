import ee
import os
import requests
import zipfile
import io
import time

# ============================================================================
# 1. CONFIGURATION
# ============================================================================

PROJECT_ID   = 'abm-sim-485823'
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DRY_RUN      = False   # True = print without downloading

# Barcelona metropolitan area bounding box [west, south, east, north]
BARCELONA_BOUNDS = [1.90, 41.25, 2.35, 41.55]

# ─── Static datasets (one file per band, no year loop) ────────────────────────
STATIC_DATASETS = {
    "soil": [
        {"name": "Organic_Carbon", "asset": "OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02"},
        {"name": "Soil_pH",        "asset": "OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02"},
        {"name": "Bulk_Density",   "asset": "OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02"},
        {"name": "Sand_Content",   "asset": "OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02"},
        {"name": "Clay_Content",   "asset": "OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02"},
        {"name": "Soil_Texture",   "asset": "OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02"},
    ],
}

# ─── Temporal datasets (downloaded year by year → year=XXXX/ subfolders) ─────
#
# For each dataset:
#   asset      : GEE ImageCollection ID
#   bands      : which bands to export (keep this small!)
#   reduction  : how to collapse the collection within each year ("mean"|"mode")
#   year_start : first year to download
#   year_end   : last year to download (inclusive)
#   typology   : subfolder name
#
TEMPORAL_DATASETS = [
    {
        "typology":   "climate",
        "name":       "Precipitation_CHIRPS",
        "asset":      "UCSB-CHG/CHIRPS/PENTAD",
        "bands":      ["precipitation"],          # CHIRPS has a single band
        "reduction":  "mean",                     # annual mean
        "year_start": 2000,
        "year_end":   2024,
    },
    {
        "typology":   "land_cover",
        "name":       "MODIS_Land_Cover",
        "asset":      "MODIS/061/MCD12Q1",
        "bands":      ["LC_Type1"],               # IGBP primary classification only
        "reduction":  "mode",                     # annual mode (most common class)
        "year_start": 2001,
        "year_end":   2023,
    },
]

# ============================================================================
# 2. INITIALIZATION
# ============================================================================

def initialize_gee():
    print(f"Initializing Earth Engine (project: {PROJECT_ID})…")
    try:
        ee.Initialize(project=PROJECT_ID)
        print("  GEE ready.")
    except Exception as e:
        print(f"  ERROR: {e}")
        print("  Run:  earthengine authenticate")
        exit(1)

# ============================================================================
# 3. DOWNLOAD HELPERS
# ============================================================================

def _download_band(image, dataset_name, band_name, out_dir, spain_bbox):
    """Download a single band of a GEE image as a GeoTIFF file."""
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{dataset_name}.{band_name}.tif")

    if os.path.isfile(out_path):
        print(f"   [skip] already exists: {os.path.relpath(out_path, BASE_DIR)}")
        return True

    try:
        url = image.select(band_name).clip(spain_bbox).getDownloadURL({
            'scale': 250,
            'format': 'GEO_TIFF',
            'region': spain_bbox,
            'filePerBand': False,
        })
    except Exception as e:
        print(f"   [error] URL for {band_name}: {e}")
        return False

    try:
        resp = requests.get(url, stream=True, timeout=600)
        resp.raise_for_status()
    except Exception as e:
        print(f"   [error] HTTP for {band_name}: {e}")
        return False

    raw = resp.content
    if raw[:2] == b'PK':   # GEE sometimes returns a ZIP
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                tifs = [f for f in z.namelist() if f.lower().endswith('.tif')]
                if tifs:
                    with z.open(tifs[0]) as src, open(out_path, 'wb') as dst:
                        dst.write(src.read())
        except zipfile.BadZipFile:
            print(f"   [error] bad ZIP for {band_name}")
            return False
    else:
        with open(out_path, 'wb') as f:
            f.write(raw)

    print(f"   [ok]   {os.path.relpath(out_path, BASE_DIR)}")
    return True


def _get_image_for_bands(image, bands):
    """Return image filtered to specific bands (if they exist)."""
    try:
        available = image.bandNames().getInfo()
        use = [b for b in bands if b in available]
        return image.select(use), use
    except Exception:
        return image, bands

# ============================================================================
# 4. STATIC DATASET DOWNLOAD (soil — flat folder, all bands)
# ============================================================================

def download_static(spain_bbox):
    for typology, layers in STATIC_DATASETS.items():
        print(f"\n{'='*50}\n{typology.upper()}\n{'='*50}")
        for layer in layers:
            name  = layer['name']
            print(f"\n  {name}…")
            if DRY_RUN:
                print(f"    [dry-run]  {typology}/{name}.*")
                continue
            try:
                image = ee.Image(layer['asset'])
                band_names = image.bandNames().getInfo()
            except Exception as e:
                print(f"    [error] {e}")
                continue
            out_dir = os.path.join(BASE_DIR, typology)
            for band in band_names:
                _download_band(image, name, band, out_dir, spain_bbox)
                time.sleep(1)

# ============================================================================
# 5. TEMPORAL DATASET DOWNLOAD (climate / land_cover — year=XXXX/ subfolders)
# ============================================================================

def download_temporal(spain_bbox):
    for cfg in TEMPORAL_DATASETS:
        typology  = cfg['typology']
        name      = cfg['name']
        asset     = cfg['asset']
        bands     = cfg['bands']
        reduction = cfg['reduction']
        y_start   = cfg['year_start']
        y_end     = cfg['year_end']

        print(f"\n{'='*50}\n{typology.upper()} — {name}  ({y_start}–{y_end})\n{'='*50}")

        for year in range(y_start, y_end + 1):
            start_dt = f"{year}-01-01"
            end_dt   = f"{year}-12-31"
            out_dir  = os.path.join(BASE_DIR, typology, f"year={year}")

            if DRY_RUN:
                print(f"  [dry-run] {typology}/year={year}/{name}.*.tif")
                continue

            print(f"  {year}…", end=" ", flush=True)
            try:
                col = (ee.ImageCollection(asset)
                         .filterBounds(spain_bbox)
                         .filterDate(start_dt, end_dt))
                count = col.size().getInfo()
                if count == 0:
                    print(f"no images for {year}, skipping")
                    continue

                if reduction == 'mean':
                    image = col.mean()
                elif reduction == 'mode':
                    image = col.mode()
                else:
                    image = col.first()

                image, use_bands = _get_image_for_bands(image, bands)

            except Exception as e:
                print(f"collection error: {e}")
                continue

            print()  # newline after year header
            for band in use_bands:
                _download_band(image, name, band, out_dir, spain_bbox)
                time.sleep(1)

            time.sleep(2)

# ============================================================================
# 6. MAIN
# ============================================================================

def main():
    initialize_gee()

    spain_bbox = ee.Geometry.BBox(
        BARCELONA_BOUNDS[0],   # west
        BARCELONA_BOUNDS[1],   # south
        BARCELONA_BOUNDS[2],   # east
        BARCELONA_BOUNDS[3],   # north
    )

    print("\n[1/2] Static datasets (soil depth bands)")
    download_static(spain_bbox)

    print("\n[2/2] Temporal datasets (year-by-year)")
    download_temporal(spain_bbox)

    print("\nAll downloads complete.")

if __name__ == "__main__":
    main()

