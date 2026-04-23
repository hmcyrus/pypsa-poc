"""
PyPSA Quickstart — Simple Electricity Market Examples
https://docs.pypsa.org/latest/examples/example-1/

Six scenarios for a Southern African electricity market, followed by
a Single Line Diagram (SLD) of the three-zone network saved to
  pypsa-demo/sld_southern_africa.png
"""

import logging
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pypsa

logging.getLogger("pypsa").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Shared data
# ---------------------------------------------------------------------------

marginal_costs = {"Wind": 0, "Hydro": 0, "Coal": 30, "Gas": 60, "Oil": 80}

power_plant_p_nom = {
    "South Africa": {"Coal": 35000, "Wind": 3000, "Gas": 8000, "Oil": 2000},
    "Mozambique": {"Hydro": 1200},
    "Swaziland": {"Hydro": 600},
}

transmission = {
    "South Africa": {"Mozambique": 500, "Swaziland": 250},
    "Mozambique": {"Swaziland": 100},
}

loads = {"South Africa": 42000, "Mozambique": 650, "Swaziland": 250}

# ---------------------------------------------------------------------------
# Scenario 1 — Single bidding zone (South Africa only)
# ---------------------------------------------------------------------------

country = "South Africa"

network = pypsa.Network()

network.add("Bus", country)

for tech in power_plant_p_nom[country]:
    network.add(
        "Generator",
        "{} {}".format(country, tech),
        bus=country,
        p_nom=power_plant_p_nom[country][tech],
        marginal_cost=marginal_costs[tech],
    )

network.add("Load", "{} load".format(country), bus=country, p_set=loads[country])

network.optimize()

print("=== Scenario 1: Single Bidding Zone (South Africa) ===")
print(network.loads_t.p)
print(network.generators_t.p)
print(network.buses_t.marginal_price)

# ---------------------------------------------------------------------------
# Scenario 2 — Two bidding zones (South Africa + Mozambique)
# ---------------------------------------------------------------------------

network = pypsa.Network()

countries = ["Mozambique", "South Africa"]

for country in countries:
    network.add("Bus", country)

    for tech in power_plant_p_nom[country]:
        network.add(
            "Generator",
            "{} {}".format(country, tech),
            bus=country,
            p_nom=power_plant_p_nom[country][tech],
            marginal_cost=marginal_costs[tech],
        )

    network.add("Load", "{} load".format(country), bus=country, p_set=loads[country])

    if country not in transmission:
        continue

    for other_country in countries:
        if other_country not in transmission[country]:
            continue

        # NB: Link is by default unidirectional, so have to set p_min_pu = -1
        # to allow bidirectional (i.e. also negative) flow
        network.add(
            "Link",
            "{} - {} link".format(country, other_country),
            bus0=country,
            bus1=other_country,
            p_nom=transmission[country][other_country],
            p_min_pu=-1,
        )

network.optimize()

print("\n=== Scenario 2: Two Bidding Zones (SA + Mozambique) ===")
print(network.loads_t.p)
print(network.generators_t.p)
print(network.links_t.p0)
print(network.buses_t.marginal_price)
print(network.links_t.mu_lower)

# ---------------------------------------------------------------------------
# Scenario 3 — Three bidding zones (SA + Mozambique + Swaziland)
# ---------------------------------------------------------------------------

network = pypsa.Network()

countries = ["Swaziland", "Mozambique", "South Africa"]

for country in countries:
    network.add("Bus", country)

    for tech in power_plant_p_nom[country]:
        network.add(
            "Generator",
            "{} {}".format(country, tech),
            bus=country,
            p_nom=power_plant_p_nom[country][tech],
            marginal_cost=marginal_costs[tech],
        )

    network.add("Load", "{} load".format(country), bus=country, p_set=loads[country])

    if country not in transmission:
        continue

    for other_country in countries:
        if other_country not in transmission[country]:
            continue

        # NB: Link is by default unidirectional, so have to set p_min_pu = -1
        # to allow bidirectional (i.e. also negative) flow
        network.add(
            "Link",
            "{} - {} link".format(country, other_country),
            bus0=country,
            bus1=other_country,
            p_nom=transmission[country][other_country],
            p_min_pu=-1,
        )

network.optimize()

print("\n=== Scenario 3: Three Bidding Zones ===")
print(network.loads_t.p)
print(network.generators_t.p)
print(network.links_t.p0)
print(network.buses_t.marginal_price)
print(network.links_t.mu_lower)

# Keep this network for the SLD
network_3zone = network

# ---------------------------------------------------------------------------
# Scenario 4 — Price-sensitive industrial load
# ---------------------------------------------------------------------------

country = "South Africa"

network = pypsa.Network()

network.add("Bus", country)

for tech in power_plant_p_nom[country]:
    network.add(
        "Generator",
        "{} {}".format(country, tech),
        bus=country,
        p_nom=power_plant_p_nom[country][tech],
        marginal_cost=marginal_costs[tech],
    )

# standard high marginal utility consumers
network.add("Load", "{} load".format(country), bus=country, p_set=loads[country])

# add an industrial load as a dummy negative-dispatch generator
# with marginal utility of 70 EUR/MWh for 8000 MW
network.add(
    "Generator",
    "{} industrial load".format(country),
    bus=country,
    p_max_pu=0,
    p_min_pu=-1,
    p_nom=8000,
    marginal_cost=70,
)

network.optimize()

print("\n=== Scenario 4: Price-Sensitive Industrial Load ===")
print(network.loads_t.p)
# NB only half of industrial load is served, because this maxes out
# Gas. Oil is too expensive with a marginal cost of 80 EUR/MWh
print(network.generators_t.p)
print(network.buses_t.marginal_price)

# ---------------------------------------------------------------------------
# Scenario 5 — Multi-period with variable wind
# ---------------------------------------------------------------------------

country = "South Africa"

network = pypsa.Network()

# snapshots labelled by [0,1,2,3]
network.set_snapshots(range(4))

network.add("Bus", country)

# p_max_pu is variable for wind
for tech in power_plant_p_nom[country]:
    network.add(
        "Generator",
        "{} {}".format(country, tech),
        bus=country,
        p_nom=power_plant_p_nom[country][tech],
        marginal_cost=marginal_costs[tech],
        p_max_pu=([0.3, 0.6, 0.4, 0.5] if tech == "Wind" else 1),
    )

# load which varies over the snapshots
network.add(
    "Load",
    "{} load".format(country),
    bus=country,
    p_set=loads[country] + np.array([0, 1000, 3000, 4000]),
)

network.optimize()

print("\n=== Scenario 5: Multi-Period with Variable Wind ===")
print(network.loads_t.p)
print(network.generators_t.p)
print(network.buses_t.marginal_price)

# ---------------------------------------------------------------------------
# Scenario 6 — Multi-period with storage
# ---------------------------------------------------------------------------

country = "South Africa"

network = pypsa.Network()

# snapshots labelled by [0,1,2,3]
network.set_snapshots(range(4))

network.add("Bus", country)

# p_max_pu is variable for wind
for tech in power_plant_p_nom[country]:
    network.add(
        "Generator",
        "{} {}".format(country, tech),
        bus=country,
        p_nom=power_plant_p_nom[country][tech],
        marginal_cost=marginal_costs[tech],
        p_max_pu=([0.3, 0.6, 0.4, 0.5] if tech == "Wind" else 1),
    )

# load which varies over the snapshots
network.add(
    "Load",
    "{} load".format(country),
    bus=country,
    p_set=loads[country] + np.array([0, 1000, 3000, 4000]),
)

# storage unit to do price arbitrage
network.add(
    "StorageUnit",
    "{} pumped hydro".format(country),
    bus=country,
    p_nom=1000,
    max_hours=6,  # energy storage in terms of hours at full power
)

network.optimize()

print("\n=== Scenario 6: Multi-Period with Storage ===")
print(network.loads_t.p)
print(network.generators_t.p)
print(network.storage_units_t.p)
print(network.storage_units_t.state_of_charge)
print(network.buses_t.marginal_price)

# ---------------------------------------------------------------------------
# Single Line Diagram — three-zone network (Scenario 3)
# ---------------------------------------------------------------------------

snap = network_3zone.snapshots[0]

GEN_COLORS = {
    "Coal": "#455a64",
    "Wind": "#43a047",
    "Gas":  "#fb8c00",
    "Oil":  "#e53935",
    "Hydro":"#1e88e5",
}

# Bus bar positions: (x_center, y_center, half_width)
BUS_POS = {
    "South Africa": (4.0, 7.5, 3.2),
    "Mozambique":   (7.8, 3.0, 1.2),
    "Swaziland":    (1.2, 3.0, 1.2),
}

fig, ax = plt.subplots(figsize=(13, 9))
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis("off")
ax.set_facecolor("#f8f9fa")
fig.patch.set_facecolor("#f8f9fa")

ax.set_title(
    "Single Line Diagram — Southern Africa Three-Zone Market\n"
    "(Scenario 3: SA · Mozambique · Swaziland)",
    fontsize=13, fontweight="bold", pad=14,
)

def draw_bus(ax, name, cx, cy, hw, label_above=True):
    ax.plot([cx - hw, cx + hw], [cy, cy], color="#1a237e", lw=5, solid_capstyle="round", zorder=3)
    dy = 0.28 if label_above else -0.36
    ax.text(cx, cy + dy, name, ha="center", va="center",
            fontsize=10, fontweight="bold", color="#1a237e")

def draw_generator(ax, bx, by, offset_x, tech, p_nom, p_dispatch):
    x = bx + offset_x
    stem_top = by
    circle_y = by - 1.1
    ax.plot([x, x], [stem_top, circle_y + 0.22], color="#333", lw=1.2, zorder=2)
    circle = plt.Circle((x, circle_y), 0.22, color=GEN_COLORS.get(tech, "#888"),
                         ec="#333", lw=1.0, zorder=4)
    ax.add_patch(circle)
    ax.text(x, circle_y, tech[0], ha="center", va="center",
            fontsize=6.5, fontweight="bold", color="white", zorder=5)
    ax.text(x, circle_y - 0.33, f"{p_nom/1000:.0f} GW", ha="center", va="top",
            fontsize=6, color="#444")
    if p_dispatch is not None:
        ax.text(x, circle_y - 0.60, f"▶{p_dispatch/1000:.1f}GW", ha="center",
                va="top", fontsize=5.5, color="#c62828")

def draw_load(ax, bx, by, offset_x, p_mw):
    x = bx + offset_x
    ax.plot([x, x], [by, by - 0.55], color="#333", lw=1.2, zorder=2)
    tri = plt.Polygon(
        [[x - 0.20, by - 0.55], [x + 0.20, by - 0.55], [x, by - 0.95]],
        closed=True, color="#b71c1c", ec="#333", lw=0.8, zorder=4,
    )
    ax.add_patch(tri)
    ax.text(x, by - 1.10, f"{p_mw/1000:.2f} GW", ha="center", va="top",
            fontsize=6.5, color="#b71c1c")

def draw_link(ax, pos, b0, b1, p_nom, p_flow):
    cx0, cy0, _ = pos[b0]
    cx1, cy1, _ = pos[b1]
    ax.plot([cx0, cx1], [cy0, cy1], color="#5c6bc0", lw=2.2,
            linestyle="--", zorder=1)
    mx, my = (cx0 + cx1) / 2, (cy0 + cy1) / 2
    direction = "→" if p_flow >= 0 else "←"
    ax.text(mx + 0.15, my + 0.15,
            f"{p_nom} MW\n{direction}{abs(p_flow):.0f} MW",
            ha="center", va="center", fontsize=7,
            color="#283593",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#9fa8da", lw=0.8))

# ── Draw buses ───────────────────────────────────────────────────────────────
for name, (cx, cy, hw) in BUS_POS.items():
    draw_bus(ax, name, cx, cy, hw, label_above=(cy > 5))

# ── Draw generators ──────────────────────────────────────────────────────────
sa_cx, sa_cy, _ = BUS_POS["South Africa"]
sa_gens = list(power_plant_p_nom["South Africa"].items())
sa_offsets = [-2.8, -1.4, 0.0, 1.4]
for (tech, p_nom), ox in zip(sa_gens, sa_offsets):
    gen_name = f"South Africa {tech}"
    p_disp = None
    if gen_name in network_3zone.generators_t.p.columns:
        p_disp = network_3zone.generators_t.p.loc[snap, gen_name]
    draw_generator(ax, sa_cx, sa_cy, ox, tech, p_nom, p_disp)

for country, (cx, cy, _) in [("Mozambique", BUS_POS["Mozambique"]),
                               ("Swaziland",  BUS_POS["Swaziland"])]:
    tech, p_nom = list(power_plant_p_nom[country].items())[0]
    gen_name = f"{country} {tech}"
    p_disp = None
    if gen_name in network_3zone.generators_t.p.columns:
        p_disp = network_3zone.generators_t.p.loc[snap, gen_name]
    draw_generator(ax, cx, cy, 0.0, tech, p_nom, p_disp)

# ── Draw loads ───────────────────────────────────────────────────────────────
draw_load(ax, sa_cx, sa_cy,  2.8, loads["South Africa"])
draw_load(ax, *BUS_POS["Mozambique"][:2], 0.8, loads["Mozambique"])
draw_load(ax, *BUS_POS["Swaziland"][:2], -0.8, loads["Swaziland"])

# ── Draw links ───────────────────────────────────────────────────────────────
link_pairs = [
    ("South Africa", "Mozambique", 500,
     "South Africa - Mozambique link"),
    ("South Africa", "Swaziland", 250,
     "South Africa - Swaziland link"),
    ("Mozambique", "Swaziland", 100,
     "Mozambique - Swaziland link"),
]
for b0, b1, cap, link_name in link_pairs:
    p_flow = 0.0
    if link_name in network_3zone.links_t.p0.columns:
        p_flow = network_3zone.links_t.p0.loc[snap, link_name]
    draw_link(ax, BUS_POS, b0, b1, cap, p_flow)

# ── Legend ───────────────────────────────────────────────────────────────────
legend_elements = [
    mpatches.Patch(color=c, label=t) for t, c in GEN_COLORS.items()
] + [
    mpatches.Patch(color="#b71c1c", label="Load"),
    plt.Line2D([0], [0], color="#5c6bc0", lw=2, linestyle="--", label="Link"),
]
ax.legend(handles=legend_elements, loc="lower center", ncol=7,
          fontsize=8, framealpha=0.9,
          bbox_to_anchor=(0.5, -0.02))

plt.tight_layout()
out_path = "sld_southern_africa.png"
plt.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"\nSLD saved to {out_path}")
