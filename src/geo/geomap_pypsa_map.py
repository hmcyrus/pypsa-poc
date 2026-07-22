#!/usr/bin/env python3
"""geomap_pypsa_map.py — static geographic map: overlay the grid topology on a
cartopy basemap (coastline/borders/land) using PyPSA's built-in n.plot(geomap=True).

This is the report-quality complement to the interactive n.explore() map. Unlike
the interactive HTML, it renders a self-contained PNG with no browser/CDN needed.

Requires cartopy (see requirements.txt). On first run cartopy downloads the
Natural Earth 50m shapefiles.

Usage:
    .venv/bin/python src/geo/geomap_pypsa_map.py
    # Windows: .venv\\Scripts\\python.exe src\\geo\\geomap_pypsa_map.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless render
import cartopy.crs as ccrs
import matplotlib.pyplot as plt

from net_coords import (
    BD_BOUNDARIES,
    REPO,
    VOLTAGE_COLORS,
    build_network_with_coords,
)

OUT_PNG = REPO / "data" / "pipeline" / "geo" / "pypsa_geomap.png"


def main() -> int:
    n, unlocated = build_network_with_coords(drop_unlocated=True)
    print(f"buses located: {len(n.buses)} | unlocated dropped: {len(unlocated)}")

    bus_colors = n.buses["v_nom"].map(VOLTAGE_COLORS).fillna("#7f7f7f")

    fig = plt.figure(figsize=(9, 12))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    n.plot(
        ax=ax,
        geomap=True,
        geomap_resolution="50m",
        boundaries=BD_BOUNDARIES,  # [lon_min, lon_max, lat_min, lat_max]
        bus_color=bus_colors,
        bus_size=0.006,
        line_color="#333333",
        line_width=0.8,
        line_alpha=0.7,
    )
    handles = [
        plt.Line2D([], [], marker="o", ls="", color=c, label=f"{int(v)} kV")
        for v, c in VOLTAGE_COLORS.items()
    ]
    ax.legend(handles=handles, title="Nominal voltage", loc="upper left")
    ax.set_title(
        f"Bangladesh grid on cartopy basemap — PyPSA n.plot(geomap=True)\n"
        f"{len(n.buses)} buses located via OSM geocoding"
    )
    fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
    print(f"wrote {OUT_PNG.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
