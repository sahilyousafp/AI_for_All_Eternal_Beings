# Blender pipeline for Phase 10 attract loop

This folder holds the Blender-side of the exhibition 3D visual upgrade.
The rest of Phase 10 (interactive Three.js scenes, Nano Banana texture
factory, handoff manager) lives in `frontend/exhibition/scene3d/` and
`backend/assets/`. See `docs/plans/2026-04-15-exhibition-3d-visuals-design.md`
for the full design.

## What this folder produces

A single file: `frontend/exhibition/assets/videos/attract_loop.mp4`.

It's a 40-second seamless-loop cinematic of three soil columns diverging
from year 2026 to 2076 under three management philosophies (do nothing /
regenerate / over-farm). It plays when nobody is touching the screen.
When a visitor touches, the handoff manager freezes the final frame
and seamlessly cross-dissolves into the real-time Three.js scene.

## Requirements

- Blender 4.0 or newer (4.2 LTS recommended)
- The Nano Banana anchor style image committed to
  `backend/assets/anchor_style.png`
- Optional: the full texture library in
  `frontend/exhibition/assets/textures/` — the render uses the anchor
  only, but textures are mentioned in the README for future upgrades

## How to run (from project root)

**Eevee (fast, few minutes):**

    blender --background --python blender/render_attract_loop.py -- \
      --anchor backend/assets/anchor_style.png \
      --textures frontend/exhibition/assets/textures \
      --out frontend/exhibition/assets/videos/attract_loop.mp4 \
      --engine BLENDER_EEVEE_NEXT \
      --samples 32

**Cycles (beautiful, overnight):**

    blender --background --python blender/render_attract_loop.py -- \
      --anchor backend/assets/anchor_style.png \
      --textures frontend/exhibition/assets/textures \
      --out frontend/exhibition/assets/videos/attract_loop.mp4 \
      --engine CYCLES \
      --samples 128

## Locked handoff contract

Three constants MUST match exactly between this script and
`frontend/exhibition/scene3d/main.js`:

| Name              | Value                 |
| ----------------- | --------------------- |
| Camera position   | (0, 2.5, 6) in THREE  |
| Camera target     | (0, 1, 0) in THREE    |
| Rim light color   | #f5cd8a               |
| Rim intensity     | 0.8                   |
| Duration          | 40 seconds            |
| FPS               | 60                    |

Blender Z-up means the camera position in `render_attract_loop.py` is
`(0, 6, 2.5)` — that's the same world point, just with Y/Z swapped.

If you change any of these, change BOTH files. The seamless handoff
depends on the final rendered frame matching the first Three.js frame
byte-for-tonal-byte.

## What to do if Blender isn't available

Ship without the video. The `HandoffManager` detects the missing
`attract_loop.mp4` and automatically falls back to `AttractScene`,
which renders the same three-column diverging scene in real-time
Three.js. The visual quality is lower (real-time shaders vs. Cycles)
but the visitor journey works end-to-end.
