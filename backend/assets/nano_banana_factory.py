"""Nano Banana texture factory for the Soil Futures exhibition 3D upgrade.

Generates painterly textures via Google's Gemini 2.5 Flash Image model
("Nano Banana") using a single style anchor image as a reference so all
outputs share one coherent painterly look.

Two modes:
    --mode anchor   generates N candidate hero paintings. Rafik picks one.
    --mode batch    generates the full texture library using an existing
                    anchor_style.png as style reference in every call.

Reads GEMINI_API_KEY from environment (loaded from .env if present).
The key is never echoed, logged, or written to any committed file.

Run from project root:
    python backend/assets/nano_banana_factory.py --mode anchor --n 4
    python backend/assets/nano_banana_factory.py --mode batch
    python backend/assets/nano_banana_factory.py --mode batch --force
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
ANCHOR_PATH = Path(__file__).resolve().parent / "anchor_style.png"
ANCHOR_CANDIDATES_DIR = Path(__file__).resolve().parent / "anchor_candidates"
TEXTURES_DIR = PROJECT_ROOT / "frontend" / "exhibition" / "assets" / "textures"
MANIFEST_PATH = Path(__file__).resolve().parent / "asset_manifest.json"

DEFAULT_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")


# --- Soil Futures taxonomy ----------------------------------------------------
# These must match what backend/soil_model/philosophies.py and
# backend/climate_scenarios/ssp_data.py actually produce. Keep in sync.

PHILOSOPHIES = [
    "do_nothing",
    "conventional",
    "regenerative",
    "rewild",
    "over_farm",
]

SSPS = ["ssp1", "ssp2", "ssp3", "ssp5"]

YEAR_BUCKETS = [0, 10, 20, 30, 40, 50]

# Rough degradation level per (philosophy, year). 0.0 = pristine, 1.0 = dead.
# These are HINTS for the prompt, not the sim — the actual sim values drive
# the Three.js scene at runtime. This table only steers texture aesthetics.
DEGRADATION_HINTS = {
    "do_nothing":    [0.3, 0.35, 0.4,  0.45, 0.5,  0.55],
    "conventional":  [0.25, 0.35, 0.45, 0.55, 0.65, 0.75],
    "regenerative":  [0.4, 0.3,  0.2,  0.15, 0.1,  0.05],
    "rewild":        [0.5, 0.4,  0.3,  0.2,  0.15, 0.1],
    "over_farm":     [0.3, 0.5,  0.65, 0.8,  0.9,  0.95],
}

SSP_MOODS = {
    "ssp1": "hopeful cool spring, 1.9°C",
    "ssp2": "uncertain hazy golden, 2.7°C",
    "ssp3": "drought ochre dust, 3.6°C",
    "ssp5": "violent red-orange heat, 4.4°C",
}


# --- Plumbing -----------------------------------------------------------------

@dataclass
class GeminiClient:
    client: "genai.Client"
    model: str

    @classmethod
    def from_env(cls, model: str = DEFAULT_MODEL) -> "GeminiClient":
        if load_dotenv is not None:
            load_dotenv(PROJECT_ROOT / ".env")
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            sys.exit(
                "ERROR: GEMINI_API_KEY not set.\n"
                "Set it in .env or via:  setx GEMINI_API_KEY \"your-key\""
            )
        if genai is None:
            sys.exit(
                "ERROR: google-genai not installed.\n"
                "Run:  pip install google-genai python-dotenv"
            )
        return cls(client=genai.Client(api_key=api_key), model=model)

    def generate(
        self,
        prompt: str,
        reference_image: Path | None = None,
    ) -> bytes:
        """Call Gemini image model. Returns raw PNG bytes of first image."""
        contents: list = [prompt]
        if reference_image is not None and reference_image.exists():
            ref_bytes = reference_image.read_bytes()
            contents.append(
                genai_types.Part.from_bytes(
                    data=ref_bytes,
                    mime_type="image/png",
                )
            )
            contents.append(
                "MATCH THE STYLE OF THE REFERENCE IMAGE EXACTLY. "
                "Same brush texture, same palette, same lighting mood. "
                "Only the subject differs."
            )

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
        )
        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None) is not None:
                return part.inline_data.data
        raise RuntimeError(
            "Gemini returned no image. Full response text:\n"
            f"{getattr(response, 'text', '<no text>')}"
        )


def read_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_png(data: bytes, path: Path) -> None:
    ensure_dir(path.parent)
    path.write_bytes(data)
    print(f"  wrote {path.relative_to(PROJECT_ROOT)}", flush=True)


# --- Modes --------------------------------------------------------------------

def mode_anchor(n: int, force: bool) -> None:
    """Generate N candidate anchor paintings. User picks the winner."""
    client = GeminiClient.from_env()
    prompt = read_prompt("anchor_style")
    ensure_dir(ANCHOR_CANDIDATES_DIR)

    print(f"Generating {n} anchor candidates…")
    for i in range(1, n + 1):
        out = ANCHOR_CANDIDATES_DIR / f"anchor_candidate_{i:02d}.png"
        if out.exists() and not force:
            print(f"  skip (exists): {out.name}")
            continue
        varied_prompt = (
            f"{prompt}\n\nVariation {i}/{n}: keep the style identical "
            f"but offer a slightly different composition / lighting angle "
            f"so the candidates can be compared."
        )
        data = client.generate(varied_prompt)
        save_png(data, out)

    print(
        "\nDone. Open each candidate in:\n"
        f"  {ANCHOR_CANDIDATES_DIR.relative_to(PROJECT_ROOT)}\n"
        "Pick ONE you love. Copy it to:\n"
        f"  {ANCHOR_PATH.relative_to(PROJECT_ROOT)}\n"
        "Then run:  python backend/assets/nano_banana_factory.py --mode batch"
    )


def iter_ground_jobs() -> Iterable[dict]:
    for phi in PHILOSOPHIES:
        for ssp_i, ssp in enumerate(SSPS):
            for y_i, year_offset in enumerate(YEAR_BUCKETS):
                yield {
                    "kind": "ground",
                    "philosophy": phi,
                    "ssp": ssp,
                    "year_offset": year_offset,
                    "degradation_level": DEGRADATION_HINTS[phi][y_i],
                    "filename": f"ground_{phi}_{ssp}_y{year_offset:02d}.png",
                }


def iter_sky_jobs() -> Iterable[dict]:
    for ssp in SSPS:
        yield {
            "kind": "sky",
            "ssp": ssp,
            "mood_description": SSP_MOODS[ssp],
            "filename": f"sky_{ssp}.png",
        }


def iter_root_jobs() -> Iterable[dict]:
    for density in ("low", "medium", "dense"):
        for depth in ("shallow", "medium", "deep"):
            yield {
                "kind": "root",
                "root_density": density,
                "root_depth": depth,
                "filename": f"roots_{density}_{depth}.png",
            }


def iter_particle_jobs() -> Iterable[dict]:
    for ptype in ("bacteria", "mycorrhizae", "carbon", "water"):
        yield {
            "kind": "particle",
            "particle_type": ptype,
            "filename": f"particle_{ptype}.png",
        }


def build_job_list() -> list[dict]:
    return [
        *iter_ground_jobs(),
        *iter_sky_jobs(),
        *iter_root_jobs(),
        *iter_particle_jobs(),
    ]


def render_prompt_for_job(job: dict) -> str:
    kind = job["kind"]
    if kind == "ground":
        tpl = read_prompt("ground_texture")
        return tpl.format(
            philosophy=job["philosophy"],
            ssp=job["ssp"],
            year_offset=job["year_offset"],
            degradation_level=f"{job['degradation_level']:.2f}",
        )
    if kind == "sky":
        tpl = read_prompt("sky_scenario")
        return tpl.format(
            ssp=job["ssp"],
            mood_description=job["mood_description"],
        )
    if kind == "root":
        tpl = read_prompt("root_brushwork")
        return tpl.format(
            root_density=job["root_density"],
            root_depth=job["root_depth"],
        )
    if kind == "particle":
        tpl = read_prompt("particle_sprites")
        return tpl.format(particle_type=job["particle_type"])
    raise ValueError(f"unknown job kind: {kind}")


def mode_batch(force: bool) -> None:
    if not ANCHOR_PATH.exists():
        sys.exit(
            f"ERROR: anchor_style.png not found at {ANCHOR_PATH}.\n"
            "Run --mode anchor first, pick a candidate, copy it there."
        )

    client = GeminiClient.from_env()
    jobs = build_job_list()
    ensure_dir(TEXTURES_DIR)
    manifest: dict = {"anchor": str(ANCHOR_PATH.name), "assets": []}

    print(f"Generating {len(jobs)} textures using anchor style reference…")
    for i, job in enumerate(jobs, 1):
        out = TEXTURES_DIR / job["filename"]
        print(f"[{i:3d}/{len(jobs)}] {job['kind']:<8} {job['filename']}")
        if out.exists() and not force:
            print("           skip (exists)")
            manifest["assets"].append({"job": job, "path": str(out.relative_to(PROJECT_ROOT))})
            continue
        prompt = render_prompt_for_job(job)
        try:
            data = client.generate(prompt, reference_image=ANCHOR_PATH)
            save_png(data, out)
            manifest["assets"].append({"job": job, "path": str(out.relative_to(PROJECT_ROOT))})
        except Exception as exc:
            print(f"           FAILED: {exc}")

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest written to {MANIFEST_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Total textures: {len([a for a in manifest['assets']])}")


# --- CLI ----------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("anchor", "batch"), required=True)
    parser.add_argument("--n", type=int, default=4, help="anchor candidate count")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    args = parser.parse_args()

    if args.mode == "anchor":
        mode_anchor(n=args.n, force=args.force)
    elif args.mode == "batch":
        mode_batch(force=args.force)


if __name__ == "__main__":
    main()
