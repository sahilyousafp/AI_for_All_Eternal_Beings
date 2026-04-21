# Soil Futures — SketchUp Model Dimensions (extracted from Model_2.dae)

**Source file:** `Model_2.dae`
**Exported:** 2026-04-20T15:41:49Z from SketchUp 20.0.363
**Native units:** inch (converted to meters below)
**Up axis:** Z

All dimensions in metres unless noted.

## 4 Cylinders — NEW DIMENSIONS (corrected from Term 2 spec)

The cylinders modelled in this SketchUp export are **smaller and flatter** than the Term 2 "Beneath the Surface" spec assumed. They are half-cylinders mounted against the back wall (front face only, 12.5 cm depth from the wall).

| Cylinder | Width (along arc) | Depth (from wall) | Height | Centre X | Z range |
|----------|-------------------|-------------------|--------|----------|---------|
| I        | 25.0 cm           | 12.5 cm           | 100 cm | 14.815 m | 0.75 – 1.75 m |
| II       | 25.0 cm           | 12.5 cm           | 100 cm | 15.862 m | 0.75 – 1.75 m |
| III      | 25.0 cm           | 12.5 cm           | 100 cm | 16.915 m | 0.75 – 1.75 m |
| IV       | 25.0 cm           | 12.5 cm           | 100 cm | 17.962 m | 0.75 – 1.75 m |

- All four cylinders sit at **Y = 8.384 m** (flush against the back wall in this model's coordinate system).
- All four mount at **Z = 0.75 m to 1.75 m** — so they rise 75 cm above the base shelf and reach 1.75 m total from the floor.
- **Centre-to-centre spacing:** ~1.05 m (Cyl1→2 = 1.047, Cyl2→3 = 1.053, Cyl3→4 = 1.047).
- **Gap between cylinders (edge-to-edge):** ~80 cm.
- **Total span of 4 cylinders along the back wall:** 4.636 m (from 13.749 m to 18.385 m).

### Implication for the design spec

The previous spec (`2026-04-20-soil-futures-posters-design.md`) assumed 40 cm ⌀ × 160 cm cylinders from the Term 2 "Beneath the Surface" document. The current SketchUp model supersedes that: **25 cm wide × 12.5 cm deep half-cylinders × 100 cm tall, mounted at 75 cm above the floor.**

The poster-wrap surface per cylinder is therefore:
- Front-facing: the visible arc (~π × 25 cm / 2 ≈ **39 cm wide**) × 100 cm tall — the printed graphic must fit this.
- Each wrap is a ~39 cm × 100 cm printed panel curved around the half-cylinder.

## Booth shell

| Element | Size (W × D × H) | Notes |
|---------|------------------|-------|
| Overall booth volume (`group_2`) | 5.000 × 1.924 × 2.650 m | Outer footprint, arc included |
| Back wall (`group_36`) | 4.000 × 0.100 × 2.750 m | 4 m wide vertical panel, 10 cm thick, 2.75 m tall |
| Ceiling / top (`group_4`) | 4.272 × 1.449 × 0.100 m | At Z 2.55–2.65 m |
| Main floor platform (`group_6`) | 4.000 × 2.000 × 0.150 m | 15 cm thick raised floor |
| Front standing platform (`group_0`) | 3.000 × 1.250 × 0.152 m | Smaller front area |
| Mid-height band (`group_38`) | 4.000 × 0.500 × 0.150 m | Where cylinders mount, at Z 0.60–0.75 m |
| Upper band / sign area (`group_37`) | 4.000 × 0.500 × 0.150 m | Top, at Z 2.60–2.75 m |
| Tablet kiosk (`group_1`) | 1.400 × 0.170 × 0.771 m | At Z 1.40–2.17 m (mounted high on stand) |

## Derived exhibit geometry

- Back wall is **4 m wide** and **2.75 m tall** — larger than the 5 m × 1.75 m given in the Model_Plan.pdf top view. The 5 m figure covers the outer arc chord (including the curved side panels); the flat mountable back-wall is 4 m wide.
- Cylinders mount on the **4 m flat back wall**, centred, with 18 cm margin from each end.
- Two visible bands on the back wall (`group_37` top, `group_38` mid) could carry the deep-time ribbon (top band) and a baseline shelf (mid band) the cylinders sit on.
- The **tablet kiosk is modelled at 1.4 m × 0.17 m × 0.77 m, centred ~1.79 m above floor** — that height only makes sense if the kiosk is on a standing-height stand. The tablet surface itself is therefore at roughly 1.4 m off the floor, which is correct visitor eye level.

## Observation about coordinate separation

The SketchUp model places the 4 cylinders' group (near X ≈ 16 m, Y ≈ 8 m) **geographically separate** from the booth shell group (near X ≈ 62 m, Y ≈ 3 m). They are components of the same design, not yet merged into one assembly. When building the real stand, the cylinders get mounted inside the booth shell as the current spec describes — the X/Y offsets in the .dae are a modelling-workflow artefact, not a design decision.

A large (`group_35`, 123.75 × 18.49 × 29.04 m) mesh is site/landscape context — ignore for the booth build.

## Saved camera views in the .dae

- `skp_camera_Last_Saved_SketchUp_View`
- `skp_camera_Scene_1`, `Scene_2`, `Scene_3`
- `skp_camera_Closeup`
- `skp_camera_front`, `skp_camera_left`, `skp_camera_Isometric`

Use the Isometric, front, and left views for presentation renders.
