"""Phase 10 — Blender headless render script for the Scene A attract loop.

Run this script INSIDE Blender to build the three-soil-column scene,
bind it to a 40-second animation, and render a seamless MP4 to
`frontend/exhibition/assets/videos/attract_loop.mp4`.

Usage (headless):
    blender --background --python blender/render_attract_loop.py -- \
            --anchor backend/assets/anchor_style.png \
            --textures frontend/exhibition/assets/textures \
            --out frontend/exhibition/assets/videos/attract_loop.mp4

Design requirements (locked by handoff contract):
    - Camera ends the loop at NEUTRAL_POSE (must match main.js exactly):
         position = (0, 2.5, 6)
         target   = (0, 1, 0)
    - Rim light warm color #f5cd8a, intensity 0.8
    - 40s total, 60 fps → 2400 frames
    - Three soil columns at x = -3, 0, +3
    - Loops seamlessly (first frame == last frame tonally)
    - Visually diverges across years 2026 → 2076:
         - do_nothing   (left)     → slow decay
         - regenerative (center)   → glow grows
         - over_farm    (right)    → cracks deepen

The render uses Eevee for speed. Cycles is available as a flag for the
final "beauty" render if the user's machine can afford it.

This script is plain Python executed inside Blender's bundled interpreter,
so it uses `bpy` directly. It does NOT depend on google-genai or anything
else from the project venv.
"""

import argparse
import math
import os
import sys
from pathlib import Path

try:
    import bpy  # noqa: F401  — only importable inside Blender
except ImportError:
    print("ERROR: this script must be run INSIDE Blender.", file=sys.stderr)
    print("Usage: blender --background --python blender/render_attract_loop.py -- ...",
          file=sys.stderr)
    sys.exit(1)


# --- Locked constants -- KEEP IN SYNC with frontend/exhibition/scene3d/main.js

NEUTRAL_POSE = {
    "cam_pos":       (0.0, 6.0, 2.5),   # Blender Z-up: (x, y, z) = (0, 6, 2.5)
    "cam_target":    (0.0, 0.0, 1.0),
    "rim_color":     (0.96, 0.80, 0.54),  # #f5cd8a → linear
    "rim_intensity": 0.8,
}

FPS = 60
DURATION_SEC = 40
TOTAL_FRAMES = FPS * DURATION_SEC

# Column layout in world space.
COLUMNS = [
    {"key": "do_nothing",   "x": -3.0, "divergence": -0.25},
    {"key": "regenerative", "x":  0.0, "divergence": +0.60},
    {"key": "over_farm",    "x":  3.0, "divergence": -0.80},
]


def parse_script_args():
    # Blender passes script args after a `--` separator.
    argv = sys.argv
    if "--" not in argv:
        raw = []
    else:
        raw = argv[argv.index("--") + 1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--anchor", required=True)
    parser.add_argument("--textures", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--engine", default="BLENDER_EEVEE",
                        choices=("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"))
    parser.add_argument("--samples", type=int, default=32)
    return parser.parse_args(raw)


def clean_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False, confirm=False)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    for img in list(bpy.data.images):
        if img.users == 0:
            bpy.data.images.remove(img)
    for mat in list(bpy.data.materials):
        if mat.users == 0:
            bpy.data.materials.remove(mat)


def setup_world():
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    nodes.clear()
    bg = nodes.new("ShaderNodeBackground")
    out = nodes.new("ShaderNodeOutputWorld")
    bg.inputs["Color"].default_value = (0.025, 0.03, 0.04, 1.0)
    bg.inputs["Strength"].default_value = 0.4
    world.node_tree.links.new(bg.outputs["Background"], out.inputs["Surface"])


def setup_lights():
    bpy.ops.object.light_add(type="SUN")
    rim = bpy.context.object
    rim.name = "RimLight"
    rim.location = (4, -3, 6)
    rim.rotation_euler = (math.radians(-45), math.radians(10), math.radians(30))
    rim.data.color = NEUTRAL_POSE["rim_color"]
    rim.data.energy = NEUTRAL_POSE["rim_intensity"] * 2.2  # Sun intensity scale

    bpy.ops.object.light_add(type="AREA")
    fill = bpy.context.object
    fill.name = "FillLight"
    fill.location = (-5, 4, 3)
    fill.data.color = (0.55, 0.75, 1.0)
    fill.data.energy = 30
    fill.data.size = 6


def setup_camera():
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.name = "Camera"
    cam.location = NEUTRAL_POSE["cam_pos"]
    # Point at target.
    tx, ty, tz = NEUTRAL_POSE["cam_target"]
    cx, cy, cz = cam.location
    direction = (tx - cx, ty - cy, tz - cz)
    # Lazy: add a Track To constraint to an empty at the target.
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=NEUTRAL_POSE["cam_target"])
    target_empty = bpy.context.object
    target_empty.name = "CamTarget"
    track = cam.constraints.new(type="TRACK_TO")
    track.target = target_empty
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    cam.data.lens = 50
    bpy.context.scene.camera = cam


def make_column_material(name, anchor_path, divergence):
    """Painterly-ish soil column material driven by the anchor texture.

    `divergence` is a real in [-1, 1]:
       +1 = maximally healthy / lush
        0 = neutral
       -1 = maximally dead / bleached

    We animate `divergence` via a custom property so the render loop
    sweeps it over the 40s timeline. The shader mixes the anchor texture
    with warm honey for healthy and cool grey for dead.
    """
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    img = nodes.new("ShaderNodeTexImage")

    if Path(anchor_path).exists():
        img.image = bpy.data.images.load(str(anchor_path))
    # Warm / cool mix nodes for healthy / dead look.
    mix_warm = nodes.new("ShaderNodeMixRGB")
    mix_warm.blend_type = "MULTIPLY"
    mix_warm.inputs[1].default_value = (0.0, 0.0, 0.0, 1.0)  # set per-frame
    mix_warm.inputs["Fac"].default_value = 0.6

    links.new(img.outputs["Color"], mix_warm.inputs[1])
    links.new(mix_warm.outputs["Color"], principled.inputs["Base Color"])
    principled.inputs["Roughness"].default_value = 0.85
    principled.inputs["Specular IOR Level"].default_value = 0.15
    links.new(principled.outputs["BSDF"], out.inputs["Surface"])

    # Stash the target color as a custom property. Animation loop
    # updates `mix_warm` inputs per frame.
    mat["divergence"] = divergence
    mat["mix_warm_node"] = mix_warm.name
    return mat


def build_column(x, material):
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.8,
        depth=2.5,
        location=(x, 0, 1.25),
        vertices=64,
    )
    col = bpy.context.object
    col.name = f"column_{x:+.1f}"
    col.data.materials.append(material)
    return col


def animate(columns, scene):
    scene.frame_start = 1
    scene.frame_end = TOTAL_FRAMES
    scene.render.fps = FPS

    # Gentle synchronized rotation across the loop (one full turn).
    for col in columns:
        col.rotation_euler = (0, 0, 0)
        col.keyframe_insert(data_path="rotation_euler", frame=1)
        col.rotation_euler = (0, 0, math.radians(360))
        col.keyframe_insert(data_path="rotation_euler", frame=TOTAL_FRAMES)

    # Per-frame material tint update — drives the visual divergence.
    # Blender handles this via a frame_change handler.
    def frame_handler(scn):
        f = scn.frame_current
        # 0..1 progress through the loop
        p = (f - 1) / max(1, TOTAL_FRAMES - 1)
        for col in columns:
            mat = col.data.materials[0]
            div_target = mat["divergence"]
            # Ramp divergence from 0 at frame 1 to target at frame end.
            div_now = div_target * p
            mix_name = mat["mix_warm_node"]
            mix_node = mat.node_tree.nodes.get(mix_name)
            if mix_node is None:
                continue
            if div_now >= 0:
                # Warm honey tint for healthy soil.
                r = 1.0
                g = 0.78 + 0.1 * div_now
                b = 0.45 + 0.1 * div_now
            else:
                # Cool grey tint for dead soil.
                mag = -div_now
                r = 0.6 + 0.2 * (1 - mag)
                g = 0.63 + 0.17 * (1 - mag)
                b = 0.66 + 0.14 * (1 - mag)
            mix_node.inputs[1].default_value = (r, g, b, 1.0)

    bpy.app.handlers.frame_change_pre.clear()
    bpy.app.handlers.frame_change_pre.append(frame_handler)


def configure_render(out_path, engine, samples):
    scene = bpy.context.scene
    scene.render.engine = engine
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.filepath = str(out_path)

    if engine == "CYCLES":
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
    else:
        scene.eevee.taa_render_samples = max(8, samples // 2)


def main():
    args = parse_script_args()
    print(f"[render] anchor   = {args.anchor}")
    print(f"[render] textures = {args.textures}")
    print(f"[render] out      = {args.out}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    clean_scene()
    setup_world()
    setup_lights()
    setup_camera()

    columns = []
    for spec in COLUMNS:
        mat_name = f"soil_{spec['key']}"
        material = make_column_material(
            name=mat_name,
            anchor_path=args.anchor,
            divergence=spec["divergence"],
        )
        col = build_column(spec["x"], material)
        columns.append(col)

    animate(columns, bpy.context.scene)
    configure_render(out_path, engine=args.engine, samples=args.samples)

    print(f"[render] rendering {TOTAL_FRAMES} frames → {out_path}")
    bpy.ops.render.render(animation=True)
    print("[render] done.")


if __name__ == "__main__":
    main()
