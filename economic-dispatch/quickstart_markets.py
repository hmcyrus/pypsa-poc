"""
PyPSA Quickstart 1 — Markets
https://docs.pypsa.org/latest/examples/example-1

Two-zone electricity market with quadratic generator cost functions.
  Zone 1: demand 500 MW,  C1(g1) = 10·g1 + 0.005·g1²
  Zone 2: demand 1500 MW, C2(g2) = 13·g2 + 0.01·g2²
  Line 1-2: s_nom = 400 MW, x = 0.01 Ω

Outputs a Single Line Diagram saved to sld_markets.png.
"""

import logging
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pypsa

warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.getLogger("pypsa").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Build network
# ---------------------------------------------------------------------------

n = pypsa.Network()

n.add("Bus", "zone_1")
n.add("Bus", "zone_2")

n.add("Load", "load_1", bus="zone_1", p_set=500)
n.add("Load", "load_2", bus="zone_2", p_set=1500)

n.add(
    "Generator",
    "gen_1",
    bus="zone_1",
    p_nom=2000,
    marginal_cost=10,
    marginal_cost_quadratic=0.005,
)
n.add(
    "Generator",
    "gen_2",
    bus="zone_2",
    p_nom=2000,
    marginal_cost=13,
    marginal_cost_quadratic=0.01,
)

n.add("Line", "line_1", bus0="zone_1", bus1="zone_2", x=0.01, s_nom=400)

# ---------------------------------------------------------------------------
# Optimise
# ---------------------------------------------------------------------------

n.optimize()

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

print("Generator dispatch (MW):")
print(n.generators_t.p, "\n")

print("Market clearing prices (€/MWh):")
print(n.buses_t.marginal_price, "\n")

print("Line flow (MW)  [p1: bus1→bus0 positive]:")
print(n.lines_t.p1, "\n")

congestion_rent = (
    n.buses_t.marginal_price.eval("zone_2 - zone_1") * n.lines_t.p0["line_1"]
)
print("Congestion rent (€/h):")
print(congestion_rent, "\n")

# ---------------------------------------------------------------------------
# Single Line Diagram
# ---------------------------------------------------------------------------

snap = n.snapshots[0]

g1   = n.generators_t.p.loc[snap, "gen_1"]
g2   = n.generators_t.p.loc[snap, "gen_2"]
mp1  = n.buses_t.marginal_price.loc[snap, "zone_1"]
mp2  = n.buses_t.marginal_price.loc[snap, "zone_2"]
flow = n.lines_t.p0.loc[snap, "line_1"]   # positive = zone_1 → zone_2
cr   = float(congestion_rent.iloc[0])

fig, ax = plt.subplots(figsize=(13, 7))
ax.set_xlim(0, 13)
ax.set_ylim(0, 9)
ax.axis("off")
fig.patch.set_facecolor("#f5f5f5")
ax.set_facecolor("#f5f5f5")

ax.set_title(
    "Single Line Diagram — Two-Zone Electricity Market\n"
    "PyPSA Quickstart 1 · C₁(g₁) = 10g₁ + 0.005g₁²  ·  C₂(g₂) = 13g₂ + 0.01g₂²",
    fontsize=12, fontweight="bold", pad=12,
)

# ── Bus bars ────────────────────────────────────────────────────────────────
BUS_COLOR  = "#1a237e"
BUS_LW     = 6

# Zone 1: x 0.5–4.5, y 5.5
z1_x, z1_y, z1_hw = 2.5, 5.5, 2.0
ax.plot([z1_x - z1_hw, z1_x + z1_hw], [z1_y, z1_y],
        color=BUS_COLOR, lw=BUS_LW, solid_capstyle="round", zorder=3)
ax.text(z1_x, z1_y + 0.35, "zone_1", ha="center", fontsize=11,
        fontweight="bold", color=BUS_COLOR)

# Zone 2: x 8.5–12.5, y 5.5
z2_x, z2_y, z2_hw = 10.5, 5.5, 2.0
ax.plot([z2_x - z2_hw, z2_x + z2_hw], [z2_y, z2_y],
        color=BUS_COLOR, lw=BUS_LW, solid_capstyle="round", zorder=3)
ax.text(z2_x, z2_y + 0.35, "zone_2", ha="center", fontsize=11,
        fontweight="bold", color=BUS_COLOR)

# ── Transmission line ────────────────────────────────────────────────────────
ax.annotate(
    "", xy=(z2_x - z2_hw, z2_y), xytext=(z1_x + z1_hw, z1_y),
    arrowprops=dict(arrowstyle="-|>", color="#3949ab", lw=2.0,
                    mutation_scale=18),
    zorder=2,
)
line_mx = (z1_x + z1_hw + z2_x - z2_hw) / 2
ax.text(line_mx, z1_y + 0.25,
        f"line_1  |  s_nom = 400 MW  ·  x = 0.01 Ω",
        ha="center", va="bottom", fontsize=9, color="#283593")
ax.text(line_mx, z1_y - 0.28,
        f"Flow: {flow:+.1f} MW  (zone_1 → zone_2)",
        ha="center", va="top", fontsize=9, color="#c62828",
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#ef9a9a", lw=0.8))

# ── Helper: draw a generator symbol (circle + stem) ─────────────────────────
def draw_gen(ax, bx, by, ox, label, p_nom, dispatch, color):
    x = bx + ox
    ax.plot([x, x], [by, by - 1.0], color="#333", lw=1.3, zorder=2)
    circ = plt.Circle((x, by - 1.35), 0.30, color=color, ec="#222",
                       lw=1.0, zorder=4)
    ax.add_patch(circ)
    ax.text(x, by - 1.35, "G", ha="center", va="center",
            fontsize=9, fontweight="bold", color="white", zorder=5)
    ax.text(x, by - 1.80, label, ha="center", va="top", fontsize=8,
            color="#333", fontweight="bold")
    ax.text(x, by - 2.10, f"p_nom = {p_nom} MW", ha="center", va="top",
            fontsize=7.5, color="#555")
    ax.text(x, by - 2.38, f"Dispatch: {dispatch:.1f} MW", ha="center",
            va="top", fontsize=7.5, color="#b71c1c", fontweight="bold")

# ── Helper: draw a load symbol (downward triangle) ───────────────────────────
def draw_load(ax, bx, by, ox, label, p_mw):
    x = bx + ox
    ax.plot([x, x], [by, by - 0.6], color="#333", lw=1.3, zorder=2)
    tri = plt.Polygon(
        [[x - 0.28, by - 0.60], [x + 0.28, by - 0.60], [x, by - 1.10]],
        closed=True, color="#b71c1c", ec="#333", lw=0.8, zorder=4,
    )
    ax.add_patch(tri)
    ax.text(x, by - 1.22, label, ha="center", va="top",
            fontsize=8, color="#333", fontweight="bold")
    ax.text(x, by - 1.52, f"{p_mw} MW", ha="center", va="top",
            fontsize=7.5, color="#b71c1c")

# ── Draw generators ──────────────────────────────────────────────────────────
draw_gen(ax, z1_x, z1_y, -0.7, "gen_1", 2000, g1, "#1565c0")
draw_load(ax, z1_x, z1_y,  0.7, "load_1", 500)

draw_gen(ax, z2_x, z2_y, -0.7, "gen_2", 2000, g2, "#2e7d32")
draw_load(ax, z2_x, z2_y,  0.7, "load_2", 1500)

# ── Price boxes ──────────────────────────────────────────────────────────────
for bx, by, price, label in [
    (z1_x, z1_y, mp1, "zone_1"),
    (z2_x, z2_y, mp2, "zone_2"),
]:
    ax.text(bx, by + 0.85, f"λ = {price:.2f} €/MWh",
            ha="center", va="center", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.35", fc="#e8eaf6", ec=BUS_COLOR, lw=1.2))

# ── Congestion rent box ──────────────────────────────────────────────────────
ax.text(line_mx, 1.5,
        f"Congestion rent = (λ₂ − λ₁) × flow\n"
        f"= ({mp2:.2f} − {mp1:.2f}) × {abs(flow):.1f} = {cr:,.1f} €/h",
        ha="center", va="center", fontsize=9.5,
        bbox=dict(boxstyle="round,pad=0.5", fc="#fff8e1", ec="#f9a825", lw=1.3))

# ── Legend ───────────────────────────────────────────────────────────────────
handles = [
    mpatches.Patch(color="#1565c0", label="Generator (zone 1)"),
    mpatches.Patch(color="#2e7d32", label="Generator (zone 2)"),
    mpatches.Patch(color="#b71c1c", label="Load"),
    plt.Line2D([0], [0], color="#3949ab", lw=2, label="Transmission line"),
]
ax.legend(handles=handles, loc="lower left", fontsize=8.5, framealpha=0.9)

plt.tight_layout()
out = "sld_markets.png"
plt.savefig(out, dpi=150, bbox_inches="tight")
print(f"SLD saved to {out}")
