"""First F2 render (milestone M1): plot located places colored by voltage,
draw lines between located endpoints, and highlight length-check violations.

Reads bus_locations.csv + length_flags.csv, writes grid_map.html.

Usage:
    .venv\\Scripts\\python.exe src\\geo\\render_map.py
"""

import re
import sys
from pathlib import Path

import folium
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
CANONICAL = REPO / "data" / "pipeline" / "canonical"
GEO_DIR = REPO / "data" / "pipeline" / "geo"

VOLTAGE_COLORS = {400: "#d62728", 230: "#ff7f0e", 132: "#1f77b4"}


def to_place(bus: str) -> str:
    return re.sub(r"_\d+(?:\.\d+)?kV$", "", bus)


def main() -> int:
    locs = pd.read_csv(GEO_DIR / "bus_locations.csv")
    lines = pd.read_csv(CANONICAL / "lines.csv")
    flags = pd.read_csv(GEO_DIR / "length_flags.csv")

    located = locs.dropna(subset=["lat", "lon"]).set_index("place")
    flagged_pairs = set(map(frozenset, flags[["p0", "p1"]].values))

    m = folium.Map(location=[23.8, 90.4], zoom_start=8, tiles="cartodbpositron")

    # lines first so markers draw on top
    seen_pairs = set()
    for _, ln in lines.iterrows():
        p0, p1 = to_place(ln["bus0"]), to_place(ln["bus1"])
        key = frozenset((p0, p1))
        if p0 == p1 or key in seen_pairs:
            continue
        seen_pairs.add(key)
        if p0 not in located.index or p1 not in located.index:
            continue
        a, b = located.loc[p0], located.loc[p1]
        v = int(re.search(r"_(\d+)kV$", ln["bus0"]).group(1))
        bad = key in flagged_pairs
        folium.PolyLine(
            [(a["lat"], a["lon"]), (b["lat"], b["lon"])],
            color="#e91e63" if bad else VOLTAGE_COLORS.get(v, "#777"),
            weight=3 if bad else 1.5,
            dash_array="6" if bad else None,
            opacity=0.9 if bad else 0.6,
            tooltip=f"{p0} - {p1} ({v} kV, {ln['length']} km)"
            + (" FLAGGED" if bad else ""),
        ).add_to(m)

    for place, row in located.iterrows():
        voltages = [int(v) for v in str(row["voltages"]).split("|")]
        color = VOLTAGE_COLORS.get(max(voltages), "#777")
        solid = row["status"] == "accepted"
        folium.CircleMarker(
            location=(row["lat"], row["lon"]),
            radius=5 if solid else 4,
            color=color,
            weight=2,
            fill=True,
            fill_color=color if solid else "#ffffff",
            fill_opacity=0.9 if solid else 0.3,
            tooltip=(
                f"{place} [{'/'.join(map(str, voltages))} kV] "
                f"{row['status']} ({row['matched_name']}, score {row['score']})"
            ),
        ).add_to(m)

    legend = """
    <div style="position: fixed; bottom: 20px; left: 20px; z-index: 1000;
                background: white; padding: 10px 14px; border: 1px solid #999;
                border-radius: 4px; font: 13px sans-serif;">
      <b>Bangladesh grid geocode - M1</b><br>
      <span style="color:#d62728;">&#9679;</span> 400 kV
      <span style="color:#ff7f0e;">&#9679;</span> 230 kV
      <span style="color:#1f77b4;">&#9679;</span> 132 kV<br>
      solid = accepted, hollow = provisional/reopened<br>
      <span style="color:#e91e63;">- - -</span> line-length check failed
    </div>"""
    m.get_root().html.add_child(folium.Element(legend))

    out = GEO_DIR / "grid_map.html"
    m.save(str(out))
    n_lines = len(seen_pairs)
    print(f"Wrote {out}: {len(located)} located places, "
          f"{len(flagged_pairs)} flagged pairs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
