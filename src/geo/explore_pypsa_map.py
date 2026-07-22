#!/usr/bin/env python3
"""explore_pypsa_map.py — overlay the grid topology on a real OpenStreetMap
basemap using PyPSA's built-in interactive plotter (n.explore(), Folium/Leaflet).

Unlike n.plot(geomap=False), this renders actual OSM tiles with the buses and
lines on top, pan/zoom, and hover tooltips. No cartopy needed.

Usage:
    .venv/bin/python src/geo/explore_pypsa_map.py
    # Windows: .venv\\Scripts\\python.exe src\\geo\\explore_pypsa_map.py
"""

from pathlib import Path

from net_coords import (
    REPO,
    VOLTAGE_COLORS,
    build_network_with_coords,
)

OUT_HTML = REPO / "data" / "pipeline" / "geo" / "pypsa_explore_map.html"


def main() -> int:
    n, unlocated = build_network_with_coords(drop_unlocated=True)
    print(f"buses located: {len(n.buses)} | unlocated dropped: {len(unlocated)}")
    if unlocated:
        print(f"  unplaced: {', '.join(unlocated)}")

    bus_colors = n.buses["v_nom"].map(VOLTAGE_COLORS).fillna("#7f7f7f")

    # geomap=True draws the OSM raster tiles under the topology.
    m = n.plot.explore(
        bus_color=bus_colors,
        line_color="#555555",
        line_width=1.5,
        geomap=True,
        tooltip=True,
    )
    # n.plot.explore returns a pydeck Deck; save via to_html.
    # PyPSA auto-picks a country-scale zoom that is too far out; tighten it so
    # Bangladesh fills the initial view (user can still pan/zoom).
    ivs = getattr(m, "initial_view_state", None)
    if ivs is not None:
        ivs.zoom = 6.4
        print(f"view center: lon={ivs.longitude:.3f} lat={ivs.latitude:.3f} zoom={ivs.zoom}")
    print(f"map_style: {getattr(m, 'map_style', None)}")
    m.to_html(str(OUT_HTML), open_browser=False)
    print(f"wrote {OUT_HTML.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
