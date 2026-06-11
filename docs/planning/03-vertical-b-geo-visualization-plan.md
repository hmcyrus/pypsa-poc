# Vertical B — Geo Visualization & Analytics (Google Maps Stack): Assessment & Plan

> **Scope:** A rich, interactive visualization and analytics tool for power system
> infrastructure — substations, lines, transformers, loads, links — built on Google
> Maps / Google Earth–class mapping.
> **Date:** June 2026 | **Status:** Plan v1.0
> **Companions:** [Status assessment](01-project-status-assessment.md) ·
> [Vertical A plan](02-vertical-a-pypsa-analysis-plan.md)

---

## 1. Current State

### 1.1 Geographic assets (see status doc §2.2 for full match analysis)

- **211 substation points** (Substation.kmz) with voltage class + ownership encoded
  in folder structure.
- **357 routed line paths** (Transmission_Line.kmz) — real vertex-by-vertex corridor
  geometry, organized by voltage (400/230/132 kV) and construction type
  (overhead / UG cable / power-station connection).
- Match vs. dataset: ~70% of 249 substation names auto-match; ~75–80% after a
  romanization synonym table; 332 unique Excel routes vs. 357 KML paths ≈ 1:1.
- Residual: ~20–40 substations need geocoding or manual placement; power-plant buses
  and HVDC border pseudo-buses are placeable from known locations.

### 1.2 Stack decision (corrects the original idea)

The **Google Earth API was deprecated in 2015 and is dead** — do not design around
it. Modern equivalents:

| Layer | Choice | Rationale |
|---|---|---|
| Base map + SDK | **Google Maps JavaScript API** | Required by the Google-stack objective; familiar UX |
| Data rendering | **deck.gl via `GoogleMapsOverlay`** (`@deck.gl/google-maps`) | WebGL; handles thousands of line segments + animated overlays; the approach used by grid-viz tools like OpenInfraMap |
| 3D | **Maps JS `Map3DElement`** (photorealistic 3D tiles) | "Google Earth experience" inside the same API; later phase |
| Google Earth proper | **KML/KMZ export** | Cheap derived artifact for stakeholder show-and-tell in Earth web/desktop; not the main app |
| Frontend | React + TypeScript + Vite | Component model for layer panels/inspectors; static-hostable |
| Phase-1 backend | **None** — static GeoJSON artifacts | Map reads files; no server until analysis-on-demand |
| Phase-3+ backend | FastAPI | Triggering Vertical A runs, scenario storage |

PyPSA's own viz (`n.plot()`, `n.explore()`) is matplotlib/folium-grade — fine for
notebooks, not a product. Nothing in the PyPSA ecosystem does what this vertical
targets; that is the product gap.

---

## 2. Phase B0 — Geo Stitching Pipeline (Week 1, shared with Vertical A)

Produces the geo sidecars of the canonical store. All matching is **provenance-
tracked** — every coordinate records how it was obtained.

### 2.1 Substation matching cascade

```
1. normalize        lowercase, strip non-alphanumerics, strip voltage/owner suffixes
                    ("Bhola 230kV" → "bhola"; "Payra PGCB" → "payra")
2. synonym table    romanization variants: Cumilla↔Comilla, Bogura↔Bogra,
                    Barishal↔Barisal, Chattogram↔Chittagong, (N)↔North, (S)↔South …
3. exact match      normalized equality                         (~141 today)
4. fuzzy match      difflib/rapidfuzz ratio ≥ 0.8, manual-confirm 0.8–0.9 band  (~34)
5. line-endpoint    unmatched buses that terminate KML LineStrings: place at the
   inference        endpoint coordinate (works for power-plant buses)
6. geocode          Google Geocoding/Places ("X substation Bangladesh"), OSM
                    power=substation via Overpass
7. manual           hand-placed from network-geo-map.pdf; HVDC border pseudo-buses
                    at known crossing points
```

Output `geo/substation_coords.csv`:
`substation, lat, lon, source{kmz_exact|kmz_fuzzy|endpoint|geocode_google|geocode_osm|manual}, confidence, kmz_name, notes`

### 2.2 Line geometry matching

```
1. endpoint snapping   for each KML LineString, find nearest placed substations to
                       its two endpoints (threshold ~500 m) → candidate bus pair
2. name corroboration  parse KML names ("Goalpara-Khulna (C)", "LILO of
                       Hasnabad-Shyampur 132kV") against the candidate pair
3. route → circuits    one KML path serves all circuits of that route
                       (Line1/Line2 share geometry; store route once, reference per circuit)
4. LILO handling       LILO entries split a parent route; model as separate segments
                       to the LILO substation, flag parent route superseded
5. residuals           routes with no KML path → straight geodesic bus0→bus1,
                       flagged geometry_source=straight
```

Output `geo/line_geometries.geojson` — FeatureCollection keyed by route id, with
`circuits[]` (line names referencing it), `voltage`, `construction`
(overhead/ug_cable/ps_connection), `geometry_source`, `kml_name`.

### 2.3 Validation gates

- KML path length vs. Excel `Length(km)`: flag deviations > 15%.
- Geometric endpoint-snap bus pair vs. declared `bus0`/`bus1`: disagreements are
  **data-error flags for either source** — review, don't auto-resolve.
- Coverage report: % buses placed, % routes with real geometry, per-voltage breakdown.
- KMZ-vintage check: list dataset assets (e.g. Adani, Payra) absent from KMZ.

**Exit criterion:** ≥95% of buses placed (any source), ≥85% of routes with real
geometry, `unmatched_review.csv` empty or explicitly accepted.

---

## 3. Phase B1 — The Infrastructure Map (Weeks 2–4)

### 3.1 Artifact build (`viz/build_artifacts.py`)

Canonical store → static artifacts:

```
artifacts/
  substations.geojson    point features: name, v_levels, total MVA, transformer
                         details, ownership, zone, grid circle, provenance
  lines.geojson          route features: voltage, circuits, conductor, length,
                         s_nom, construction type, geometry source
  links.geojson          HVDC interconnects
  generators.geojson     (once Vertical A assigns buses) plant, fuel, p_nom
  network.kmz            styled KML for Google Earth
  manifest.json          build hash, counts, coverage stats
```

### 3.2 Map layers (deck.gl)

| Layer | Geometry | Encoding |
|---|---|---|
| Lines | `PathLayer` | Color by voltage (400 red / 230 orange / 132 blue — match PGCB legend in `legends.png`); width by s_nom; dashed for UG cable; straight-fallback rendered thinner/dotted |
| Substations | `ScatterplotLayer` (+ `IconLayer` at high zoom) | Radius ~ total MVA; fill by ownership or zone (toggle); HVDC stations distinct icon |
| HVDC links | `ArcLayer` | Distinct styling for the 3 interconnects |
| Labels | `TextLayer` | Zoom-gated: 400 kV names always; 132 kV at high zoom |

### 3.3 Interactions

- **Layer panel:** toggle by voltage tier, ownership, construction type, zone.
- **Inspector:** click substation → name, voltage levels, transformer list with MVA,
  ownership, zone, connected lines (each clickable); click line → endpoints,
  circuits, conductor, length (Excel vs. measured), s_nom, construction.
- **Search:** typeahead over substation/line names → fly-to.
- **Data-quality mode:** color by provenance/confidence — turns the map into the
  review tool for Phase B0 residuals (dogfooding).
- **Stats strip:** visible-extent aggregates (substation count, total MVA, km of
  line by voltage).

**Exit criterion:** full network browsable; inspector complete; KMZ export opens
correctly in Google Earth. This is already a stakeholder-demoable product more
complete than any public BD grid map.

---

## 4. Phase B2 — Analysis Overlays (Weeks 4–7, gated on Vertical A Phase A2)

Consumes the name-keyed result artifacts defined in Vertical A plan §7.2. Join is
`result.name → feature.name` — no PyPSA dependency in the frontend.

| Overlay | Source table | Rendering |
|---|---|---|
| **Line loading** | `line_loading.csv` | Path color ramp green→amber→red by % of s_nom; binding lines (≥98%) pulse |
| **Flow direction** | `lines_t.p0` sign | deck.gl `TripsLayer` animated dashes along the real routed geometry; speed ~ magnitude |
| **Nodal LMP heatmap** | `lmp.csv` | `HeatmapLayer`/contour over buses + per-bus price labels; the proposal's flagship Experiment E view |
| **Dispatch** | `dispatch.csv` | Generator symbols sized by output, colored by fuel; zonal stack popups |
| **Congestion rents** | `mu_lower/mu_upper` | Ranked corridor list ↔ map highlight |
| **N-1 contingency** | A3 screening runs | Select a line → show post-contingency loading of all others |

**Time controls:** snapshot scrubber + playback for 24-h runs; **scenario A/B**: load
two run artifacts, render difference (ΔLMP, Δloading).

**Exit criterion:** the LMP-map demo — the commercially significant artifact for the
proposal's Tier 1–3 audiences (IPP siting, lender studies, policy dashboards).

---

## 5. Phase B3 — Fidelity & Product Features (Months 2–4+)

Ordered by value:

1. **3D corridor views** — `Map3DElement` photorealistic tiles; fly-through of
   corridors (e.g. Aminbazar–Gopalganj Padma crossing, already in KMZ geometry).
2. **Residual geometry fill** — OSM `power=line` ways for straight-fallback routes;
   then the satellite-image tower-detection idea (`locating-transmission-towers.md`)
   as a decoupled research track — refinement, never a blocker.
3. **Interconnection screening tool** — click an empty location → nearest buses,
   distance, indicative LMP/curtailment from Vertical A scenario runs (the proposal's
   Tier-1 IPP product feature).
4. **Tower-level detail** — when/if tower detection produces data.
5. **Reports** — map-view + result-table → PDF for the lender/consulting use case.
6. **Auth + scenario storage** — multi-user; precedes any SaaS pilot (FastAPI backend
   arrives here).

---

## 6. Architecture & Operational Notes

```
canonical store ──build_artifacts.py──▶ artifacts/ (GeoJSON + KMZ, static)
                                            │
results/<run_id>/ (Vertical A) ─────────────┤  fetch + name-join in frontend
                                            ▼
                              React + Maps JS API + deck.gl overlay
                              (static hosting; no backend until B3)
```

- **Performance:** 357 routes / ~10k vertices / 305 points is small for deck.gl; no
  tiling needed. Pre-simplify geometries (Douglas-Peucker ~10 m) for initial load;
  full resolution on inspect.
- **API cost:** Maps JS dynamic-map pricing only (deck.gl renders data client-side —
  no per-feature cost); Geocoding usage is a one-time pipeline run, ~150 calls.
- **Key management:** Maps key referrer-restricted; geocoding key server-side only.
- **CRS:** everything WGS84 (KML native, GeoJSON native, Maps native) — no
  reprojection anywhere.

### Risks

| Risk | Mitigation |
|---|---|
| KMZ vintage misses recent assets | Vintage check in B0 surfaces exactly which; straight-fallback + geocode |
| Endpoint snapping ambiguous in dense Dhaka cluster | Lower threshold + name corroboration; manual review queue |
| LILO topology mismatch between KMZ and Excel | Explicit LILO handling rule (B0 §2.2); review flags |
| Maps API cost at public scale | Cost alarm; fallback abstraction — deck.gl also runs on MapLibre/free tiles with the same layers |
| Scope creep into GIS-editor territory | Map is a *viewer* over the canonical store; edits happen in the store pipeline, surfaced via data-quality mode |
