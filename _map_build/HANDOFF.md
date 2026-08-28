# Knuckles Basin Atlas — build handoff

Continue the interactive 3D map from here. Everything needed is in this folder
(`Desktop/Knuckles/_map_build/`). Read this file first, then follow **Rebuild pipeline**.

**Do not work out of the Claude scratchpad.** It was wiped mid-session once already.
Work here, in the project folder.

---

## Where things stand

| Thing | State |
|---|---|
| `Desktop/Knuckles/Knuckles_3D_Map.html` | **Last published build (6.51 MB). Still the OLD version** — 7 basins, narrow window. None of the in-progress work below is in it. |
| Artifact URL | https://claude.ai/code/artifact/1c5f0677-38ed-4d79-8a7f-7f21324b3a24 — republish to this exact URL (pass it as `url`) so the link stays stable. |
| `_map_build/knuckles_data.json` | **New** payload: 6 merged basins, widened grid, translated points. Rivers/rings need rebuilding — see TODO. |
| `_map_build/satellite.jpg` | **New**, matches the widened grid. 2400×2945, 18.4 m/px, 1.17 MB. |
| `_map_build/basins.png` | **New**, matches the widened grid. Basin id × 32. |
| `_map_build/overlay_OLD_EXTENT.png` | **STALE** — built for the old narrow window. Must be regenerated. |
| `_map_build/template.html` | Still the 7-basin viewer. Needs the changes under TODO. |

## What the user asked for

1. Merge Hulu Ganga + Hunnasgiriye Tika into one basin, "Hulu Ganga". **Done.**
2. Find names for small flow branches — Kalu Ganga, Sudu Ganga, Naranaththa Oya,
   Waddahena Oya, Puwakpitiya Oya, etc. **Partly done — see Open question.**
3. Easier navigation. **Not started.**
4. Clearly show Mahaweli Ganga and Amban Ganga. **Data ready, rendering not started.**
5. Show where each stream from the Knuckles meets the Mahaweli or Amban Ganga.
   **Computed; rendering not started.**

## Done so far

### Basins merged, renumbered 1–6 (was 7). Total unchanged at 762.33 km²

| # | Name | km² | Source folder(s) under `Watersheds/` |
|---|---|---|---|
| 1 | Hasalaka Oya | 85.69 | `watershed(2)` |
| 2 | Hulu Ganga | 240.00 | `watershed(4)` + `watershed(3)` |
| 3 | Amban Ganga Side Eka | 99.70 | `watershed(5)` |
| 4 | Thelgamu Oya | 102.54 | `watershed(6)` |
| 5 | Kalu Ganga | 116.25 | `watershed` |
| 6 | Heen Ganga | 118.15 | `watershed(1)` |

The union of `watershed(4)` and `watershed(3)` leaves 8 sliver holes (largest 3.4 ha)
along the shared edge. `basins2.py` → `drop_slivers()` discards interior rings under
0.10 km². Do **not** fix this with a buffer-out/in — that shifts the true outer
boundary by up to 60 m.

Old basin id → new id remap, already applied to every stored point:
`{1:1, 2:2, 3:2, 4:3, 5:4, 6:5, 7:6}`

### Map window widened

The old window cropped out most confluences. It is now the full COP30 tile:

```
EPSG:5235   x 480810 .. 524970     y 522030 .. 576210
grid 736 x 903 at 60 m             44.2 x 54.2 km
```

Stored point coordinates are metres from the NW corner, so widening was a pure
translation: `dx = +3300`, `dy = +3480`, already applied by `regrid.py`.

### Confluences computed

`confl.py` walks every named OSM watercourse and finds its closest approach to a
trunk. The basin-relevant results:

| River | Joins | Gap | Elev |
|---|---|---|---|
| Hulu Ganga | Mahaweli Ganga | 0 m | 427 m |
| Hasalaka Oya | Mahaweli Ganga | 0 m | 74 m |
| Heen Ganga | Mahaweli Ganga | 0 m | 64 m |
| Thelgamu Oya | Amban Ganga | 0 m | 146 m |
| Dankanda Oya | Amban Ganga | 0 m | 358 m |
| Amban Ganga Side Eka | Amban Ganga | 55 m (basin outlet) | 295 m |

All of these fall inside the widened window. Kalu Ganga has no OSM geometry; its
basin outlet sits 318 m from the Mahaweli.

Do **not** use the basin outlet as the confluence in general — the river often runs
several km past the basin boundary before joining (Heen Ganga: 5.7 km). Follow the
named river. The outlet is only the fallback when the river is unnamed in OSM.

## Open question — needs the user before item 2 can finish

Of the names the user listed, **only these exist in OpenStreetMap**: Hulu Ganga,
Heen Ganga, Hasalaka Oya (tagged "Hassalaka Oya"), Thelgamu Oya, Kota Ganga,
Kukul Oya, Meemure Oya, Dankanda Oya, Delivala Oya, Amban Ganga, Mahaweli Ganga.

**Not in OSM, and not placeable from any data on this machine:**

- **Kalu Ganga** — recoverable: it is basin 5's own name, so `confl.py` derives a
  label on that basin's highest-order channel. Marked `"osm": false` in `data.stems`.
- **Puwakpitiya Oya** — recoverable but **not yet done**. The QGIS project names
  `Watersheds/watershed(16)` as "5 - I Puwakpitiya Oya". Same derivation trick as
  Kalu Ganga. (`watershed(15)` is "5 - II Thelgamu Oya until 5I meets".) Those are
  the only two named sub-basin layers in `Knuckles Watersheds.qgz`.
- **Sudu Ganga, Naranaththa Oya, Waddahena Oya** — no geometry anywhere. Ask the user
  to place them. Suggested mechanism: a `local_river_names.csv` in the project root
  with `name,lon,lat` that the build reads and renders as labels. **Do not invent
  positions.**

## TODO

1. **Regenerate `overlay.png` at the new extent.** The script was lost in the wipe;
   rewrite it. Output RGB PNG, 2400×2945, aligned exactly to the grid above:
   - **R = roads** from `OSM/Knuckles_Roads.shp` by `road_class`: major 255 @ width 5,
     minor 150 @ 3, trail 80 @ 2 (widths at 2× supersample; draw trail → minor →
     major so majors win, then LANCZOS down to 1×).
   - **G = stream network** from `Streams/*.shp` — the project's own layers. The user
     explicitly asked for these rather than a DEM-derived network. They are
     polygonised stream masks, all at the same ~60 m footprint, so the hierarchy is
     made morphologically: L1 eroded 2×2 → 95, L3 as-is → 180, L4 dilated 3×3 → 255,
     then GaussianBlur(0.6). `min_upa_km` is the real hierarchy: L1 ≥ 1 km²,
     L3 ≥ 100 km², L4 ≥ 1000 km² upstream area.
   - **B = water bodies** from `osm_named.json` polys, filled.
2. **Re-run `rivers2.py` then `confl.py`.** Both ran against the *old* grid and
   `regrid.py` cleared their outputs. They read the grid from the payload, so they
   only need re-running. Set `TW = 2400` in any texture-sized script.
3. **Update `template.html`:**
   - 6 basins, not 7 — `BCOL` currently has 7 entries plus index 0.
   - Draw trunk rivers (`data.trunks`) and tributaries (`data.tribs`) as vector lines,
     same technique as the basin divides: a second GL program, positions
     `(x, elev, z)`, depth bias `q.z -= uBias * q.w`, elevation per vertex from
     `elevAtInit()`. Trunks heavy in Deep Ocean Blue, tributaries lighter in Water Blue.
   - Confluence markers from `data.confluences`, plus a "Confluences" section in the
     register listing e.g. "Hulu Ganga → Mahaweli Ganga, 427 m".
   - River name labels from `data.trunkLabels`, `data.tribLabels`, `data.stems`.
   - Navigation: a row of 6 basin chips at the top of the rail for one-click
     isolate + fly; keyboard 1–6 to select, 0 to clear.
4. **Rebuild, verify, republish** to the existing artifact URL.

## Rebuild pipeline

Run from this folder. `build.py` and `recover.py` still have hardcoded paths pointing
at the old scratchpad — repoint them here first.

```bash
"/c/Program Files/QGIS 3.40.8/bin/python-qgis-ltr.bat" basins2.py
```

Then `overlay.py` (rewrite first), `rivers2.py`, `confl.py`, and finally `build.py`,
each invoked the same way.

`regrid.py` and `satellite2.py` are already done — only re-run them if the window
changes again. `satellite2.py` makes ~500 tile requests.

`recover.py` rebuilds the entire working set (assets, fonts, payload, template) out of
a published `Knuckles_3D_Map.html`. That is the disaster-recovery path if this folder
is ever lost — every asset is embedded in the HTML.

## Environment gotchas

- **Python** is `C:\Program Files\QGIS 3.40.8\bin\python-qgis-ltr.bat`. It has
  GDAL/OGR, numpy, PIL, requests, scipy. Bare `python` is a broken Windows Store
  alias. The `-c` flag fails through Bash because of the space in the path — write a
  `.py` file instead.
- **This machine ran out of RAM** during the session: 0.2 GB free of 7.7 GB, and GDAL
  failed to allocate 10 MB. Scripts therefore use `gdal.SetCacheMax(48*1024*1024)`,
  disk-backed `GTiff` rather than `MEM`, and `del` + `gc.collect()`. Keep that
  discipline. If allocations fail, it is the machine, not the code.
- **OGR lifetime trap:** keep a reference to the `DataSource` *and* the `Feature`, or
  `GetGeometryRef().Clone()` throws a TypeError.
- **Non-ASCII in the JS block** must be `\uXXXX`-escaped — `build.py` does this. The
  final file is written as ASCII with `xmlcharrefreplace`, so a bare `×` in a JS
  string becomes a literal `&#215;` when assigned via `textContent`.
- **Preview:** `node serve.js` on port 8731, then point the browser pane at
  `http://localhost:8731`. The pane does **not** composite, so screenshots time out.
  Render instead through the built-in debug hook: `window.__kmap.shot(w, h)` returns a
  PNG data URL; POST it to `/shot?n=name` and `serve.js` writes it next to the script,
  then read the PNG. Also available: `.state()`, `.set({...})`, `.markers(w,h)`,
  `.texState()`.
- Publishing without `url` creates a *new* artifact. Always pass the URL above.

## Design constraints already settled — keep these

- Brand: `Desktop/Branding/01_Brand_Guide.md`. Deep Ocean Blue `#14416B` leads, Water
  Blue `#1E78B0`, Natural Green `#2E6B4F`, Off-White `#F6F7F4`, Slate Ink `#1C2A33`,
  Contour Grey `#C9CEC7`. Poppins headings, Inter body, both embedded as woff2 data
  URIs — no CDN, the artifact CSP blocks font hosts.
- **Brown and teal are banned by the brand guide.** Blue fills over green terrain land
  on teal automatically. The shader avoids it by pulling the base toward its own
  luminance before tinting, and the elevation ramp is neutral grey rather than green.
  Do not reintroduce a green ramp.
- Seven fills exceeded the brand's "three colours" rule; that rule governs marketing
  layouts, not a categorical map key. Fills are brand hues plus sanctioned tints,
  separated by lightness. Only six are needed now.
- Basin divides are vector lines, not a raster mask — the source rings are already
  smooth (83–172 vertices) and raster edges stair-step when zoomed in.
- Imagery is **Esri World Imagery**, not Google. Google's tile endpoints are not
  licensed for this. Attribution sits in the `#credits` block.
- `#credits` needs `position:fixed` — it was missing once and overlapped the rail.
- A viewport meta is injected by script at the top of the page. Without it, phones lay
  out at 980 px and the responsive rules never fire.
- Mobile panels are mutually exclusive and use non-animated `visibility`, so a hidden
  panel cannot stay clickable if transitions stall.
