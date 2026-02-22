import ee
import os
import requests
import zipfile
import io
import time

# ============================================================================
# 1. CONFIGURATION & DATASETS
# ============================================================================

PROJECT_ID = 'abm-sim-485823'
COUNTRY_NAME = 'Spain'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DRY_RUN = False  # Set to True to test without downloading

# Spain bounding box coordinates (created after ee.Initialize inside main())
# W=-18.2, S=27.5, E=4.6, N=43.9 — covers mainland + Canary + Balearic Islands
SPAIN_BOUNDS = [-18.2, 27.5, 4.6, 43.9]  # [west, south, east, north]

DATASETS = {
    "soil": [
        {"name": "Organic_Carbon", "asset": "OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02"},
        {"name": "Soil_pH",        "asset": "OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02"},
        {"name": "Bulk_Density",   "asset": "OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02"},
        {"name": "Sand_Content",   "asset": "OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02"},
        {"name": "Clay_Content",   "asset": "OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02"},
        {"name": "Soil_Texture",   "asset": "OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02"},
    ],
    "climate": [
        {
            "name": "Precipitation_CHIRPS",
            "asset": "UCSB-CHG/CHIRPS/PENTAD",
            "is_collection": True,
            "reduction": "mean",
            "start": "2020-01-01",
            "end":   "2020-12-31",
        },
    ],
    "land_cover": [
        {
            "name": "MODIS_Land_Cover",
            "asset": "MODIS/061/MCD12Q1",
            "is_collection": True,
            "reduction": "mode",
            "start": "2020-01-01",
            "end":   "2020-12-31",
        },
    ],
}

# ============================================================================
# 2. INITIALIZATION
# ============================================================================

def initialize_gee():
    print(f"Initializing Earth Engine with project: {PROJECT_ID}...")
    try:
        ee.Initialize(project=PROJECT_ID)
        print("✅ Initialization successful.")
    except Exception as e:
        print(f"❌ Failed to initialize Earth Engine: {e}")
        print("Run: earthengine authenticate")
        exit(1)

# ============================================================================
# 3. DOWNLOAD LOGIC
# ============================================================================

def download_band(image, dataset_name, band_name, typology, spain_bbox):
    """Downloads a single band of a GEE image as an individual GeoTIFF."""
    out_dir = os.path.join(BASE_DIR, typology)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{dataset_name}.{band_name}.tif")

    try:
        band_image = image.select(band_name).clip(spain_bbox)
        url = band_image.getDownloadURL({
            'scale': 2500,         # 2.5 km — keeps each band well under GEE's 50MB limit
            'format': 'GEO_TIFF',
            'region': spain_bbox,
            'filePerBand': False,  # single band → single .tif
        })
    except Exception as e:
        print(f"   ❌ URL error [{band_name}]: {e}")
        return

    try:
        response = requests.get(url, stream=True, timeout=600)
        response.raise_for_status()
    except Exception as e:
        print(f"   ❌ HTTP error [{band_name}]: {e}")
        return

    raw = response.content
    # GEE sometimes still returns a ZIP even for single bands
    if raw[:2] == b'PK':
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                tif_files = [f for f in z.namelist() if f.lower().endswith('.tif')]
                if tif_files:
                    with z.open(tif_files[0]) as src, open(out_path, 'wb') as dst:
                        dst.write(src.read())
        except zipfile.BadZipFile:
            print(f"   ❌ Bad ZIP for [{band_name}]")
            return
    else:
        with open(out_path, 'wb') as f:
            f.write(raw)

    print(f"   ✅ {out_path}")


def download_image(image, name, typology, spain_bbox):
    """Fetches band list, then downloads each band as a separate GeoTIFF."""
    print(f"\nDownloading {name}...")
    try:
        band_names = image.bandNames().getInfo()
    except Exception as e:
        print(f"❌ Could not retrieve band names for {name}: {e}")
        return

    print(f"   Bands ({len(band_names)}): {band_names}")
    for band in band_names:
        download_band(image, name, band, typology, spain_bbox)
        time.sleep(1)  # small pause between band requests

# ============================================================================
# 4. MAIN EXECUTION
# ============================================================================

def main():
    initialize_gee()  # must come before any ee.Geometry creation

    # Create Spain bbox AFTER initialization
    spain_bbox = ee.Geometry.BBox(
        SPAIN_BOUNDS[0],  # west
        SPAIN_BOUNDS[1],  # south
        SPAIN_BOUNDS[2],  # east
        SPAIN_BOUNDS[3],  # north
    )

    for typology, layers in DATASETS.items():
        print(f"\n{'='*50}")
        print(f"Typology: {typology.upper()}")
        print(f"{'='*50}")

        for layer in layers:
            name  = layer['name']
            asset = layer['asset']

            if layer.get('is_collection'):
                collection = (
                    ee.ImageCollection(asset)
                      .filterBounds(spain_bbox)
                      .filterDate(layer['start'], layer['end'])
                )
                reduction = layer.get('reduction', 'mean')
                if reduction == 'mean':
                    image = collection.mean()
                elif reduction == 'mode':
                    image = collection.mode()
                else:
                    image = collection.first()
            else:
                image = ee.Image(asset)

            if DRY_RUN:
                print(f"[DRY RUN] Would download: {name}  →  {typology}/")
            else:
                download_image(image, name, typology, spain_bbox)
                time.sleep(2)  # brief pause between requests

    print("\n✅ All downloads complete.")

if __name__ == "__main__":
    main()
