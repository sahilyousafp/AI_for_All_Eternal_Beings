# Barcelona UI Polish & Bug Fix: Dynamic Legend & Animations

This phase addresses the user's reported bug (layers not updating colors) and enhances the UI with a dynamic legend, animations, and "live" map elements.

## User Review Required

> [!IMPORTANT]
> **Bug Fix**: I've identified that inconsistent dataset names (spaces vs underscores) caused the palette to fallback to the same "amber" ramp for most bands. I will normalize these names to ensure each dataset gets its unique scientific color scheme.

## Proposed Changes

### 1. Fix "Stuck Color" Bug
- **[local-data.js]** & **[gee-map.js]**: Standardize dataset-to-palette mapping logic. Ensure "Organic Carbon" and "Organic_Carbon" both resolve to the correct ramp.

### 2. Dynamic Legend
- **[index.html]**: Add a `#mapLegend` container overlaid on the map.
- **[local-data.js]** & **[gee-map.js]**: Implement `updateLegend(ramp, min, max, title)` to display a color scale for the active layer.

### 3. Aesthetics & Animations
- **[index.html]**:
  - Add `@keyframes` for fade-ins and scale-ups.
  - Implement a "Live Scan" effect on the Barcelona bounding box (moving dash line).
  - Add glassmorphism (backdrop-filter) to sidebar sections and overlays for a premium feel.
- **[main.js]**: Add subtle transitions when switching tabs or updating values.

### 4. "Live" Map Elements
- **[local-data.js]**: Add a subtle animation to the Barcelona bounding box to indicate active data coverage.

## Verification Plan

### Manual Verification
1.  Select "Organic Carbon". Verify the legend shows an **Amber** ramp.
2.  Select "Soil pH". Verify the legend updates to a **Violet** ramp and the map colors change accordingly.
3.  Observe the Barcelona bounding box for the "Live" scanning effect.
4.  Check for smooth tab transitions and sidebar item highlights.
