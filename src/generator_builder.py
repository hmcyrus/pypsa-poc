"""
generator_builder.py

Reads data/pipeline/raw/generatordatabaseline.xlsx and produces:
  data/pipeline/canonical/generators.csv        — canonical generator table
  data/pipeline/pypsa-components/generators.csv — PyPSA-ready (name as index)

Note: ppfuel.xlsx is not read — fuel mapping is fully hardcoded in FUEL_LOOKUP below.

Run:
    python src/generator_builder.py
"""

import re

import numpy as np
import pandas as pd
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT          = Path(__file__).parent.parent
PIPELINE_DIR  = ROOT / "data" / "pipeline"
BASELINE_PATH = PIPELINE_DIR / "raw" / "generatordatabaseline.xlsx"
CANONICAL_DIR = PIPELINE_DIR / "canonical"
PYPSA_DIR     = PIPELINE_DIR / "pypsa-components"

# ── Marginal cost reference ────────────────────────────────────────────────
# Reference anchor points from artifact f62ef837:
#   {tech: {fuel_category: [(p_mw, cost_usd_mwh), ...]}}
MC_REF = {
    "CCGT": {
        "gas":    [(200, 24.1), (350, 21.6), (450, 20.5)],
        "liquid": [(200, 37.6), (350, 34.4), (450, 31.8)],
    },
    "OCGT": {
        "gas":    [(50, 40.6), (100, 37.5), (200, 35.1)],
        "liquid": [(50, 72.8), (100, 64.9), (200, 58.4)],
    },
    "ICE": {
        "gas":    [(10, 37.2), (50, 34.0), (100, 31.3)],
        "liquid": [(10, 46.9), (50, 43.0), (100, 40.6)],
    },
    "Steam Turbine": {
        "gas":    [(100, 39.9), (300, 36.6), (600, 33.6)],
        "liquid": [(100, 55.0), (300, 50.1), (600, 46.2)],
        "coal":   [(100, 28.8), (300, 26.1), (600, 23.3)],
    },
    "Hydro":    {"hydro":  [(10, 1.5), (100, 1.5), (500, 1.5)]},
    "Solar PV": {"solar":  [(10, 0.0), (100, 0.0), (500, 0.0)]},
    "Wind":     {"wind":   [(10, 0.0), (100, 0.0), (500, 0.0)]},
}

# Map raw fuel strings to reference fuel categories
FUEL_CATEGORY = {
    "Gas":   "gas",
    "HFO":   "liquid",
    "HSD":   "liquid",
    "Coal":  "coal",
    "Solar": "solar",
    "Wind":  "wind",
    "Hydro": "hydro",
}

HSD_PREMIUM = 1.10   # HSD costs ~10 % more per MWh than HFO (lighter, more refined)

# Map fuel string to PyPSA carrier
CARRIER_MAP = {
    "Gas":   "gas",
    "HFO":   "oil",
    "HSD":   "oil",
    "Coal":  "coal",
    "Solar": "solar",
    "Wind":  "wind",
    "Hydro": "hydro",
    "Import": "AC",
}

FUEL_COLS = ["gas", "hfo", "hsd", "coal", "solar", "wind", "hydro"]
MC_COL    = {f: f"marginal_cost_{f}" for f in FUEL_COLS}

# ── Technology lookup (for rows where Technology cell is blank) ────────────
TECH_LOOKUP = {
    # --- Dhaka region ---
    "Madanganj-55 MW PP(Summit)":                "ICE",
    "Siddhirgonj 210 MW TPP":                    "Steam Turbine",
    "Siddhirgonj 2*120 MW GTPP":                 "OCGT",
    "Gagnagar 102 MW PP (Digital Power)":        "ICE",
    "Kamalaghat 54 MW PP(Banco Energy)":         "ICE",
    "Kodda 150 MW PP BRPL":                      "ICE",
    "Manikganj 55 MW PP (Northern)":             "ICE",
    "Nababganj 55 MW PP (Southern power )":      "ICE",
    "Summit Power Ashulia":                      "ICE",
    "Summit Power Madhabdi":                     "ICE",
    "Gazipur 52 MW PP":                          "ICE",
    "Tongi 80 MW GTPP":                          "OCGT",
    "Kodda 300 MW PP Unit-2 (Summit)":           "ICE",
    "Kodda 149 MW PP Unit-1 (Summit)":           "ICE",
    "Gazipur 100 MW PP":                         "ICE",
    "Meghnaghat 104 MW PP (OPCL)":               "ICE",
    "Manikgonj 162MW PP(MPGL)":                  "ICE",
    "Spectra Solar Plant Ltd.":                  "Solar PV",
    "Kanchan Purbachal Power Generation Ltd.":   "ICE",
    "Unique Meghnaghat Power Limited (UMPL)":    "CCGT",
    "JERA Meghnaghat Power Limited":             "CCGT",
    "Sreepur 150 MW PP BRPL":                    "ICE",
    # --- Chattogram region ---
    "Chattogram TPP":                            "Steam Turbine",
    "Raozan 25 MW PP":                           "ICE",
    "Teknaf  20MW PP (Solartech)":               "Solar PV",
    "Patenga 50MW PP (Baraka)":                  "ICE",
    "Karnaphuli Hydro PP Unit-1,2,3,4, 5":       "Hydro",
    "Sikalbaha 225MW CCPP":                      "CCGT",
    "Sikalbaha Peaking GT":                      "OCGT",
    "Sikalbaha 105 MW PP (Baraka Sikalbaha)":    "ICE",
    "Hathazari 100 MW peaking PP":               "ICE",
    "Dohazari -Kalaish 100 MW Peaking":          "ICE",
    "Juldah 100 MW PP Unit-3 (Acorn)":           "ICE",
    "Malancha, Ctg. EPZ (United)":               "ICE",
    "Chattogram 108 MW PP (ECPV)":               "ICE",
    "Kaptai 7 MW  Solar PP":                     "Solar PV",
    "Anwara 300 MW PP (United)":                 "ICE",
    "Jodiac Power":                              "ICE",
    "Karnaphuli Power Ltd.":                     "ICE",
    "Juldah unit-2 (Acorn)":                     "ICE",
    "Anlima Energy Ltd.":                        "ICE",
    "Mirsharai 150 MW BRPL":                     "ICE",
    "SS Power":                                  "Steam Turbine",
    "Cox's Bazar Wind":                          "Wind",
    "Matarbari 2*600 MW (CPGCBL)":               "Steam Turbine",
    # --- Cumilla region ---
    "Ashuganj TSK 50 MW PP":                     "ICE",
    "Ashuganj 55 MW PP (Precision)":             "ICE",
    "Ashuganj 195 MW PP (APSCL-United)":         "ICE",
    "Ashuganj 51 MW PP (Midland)":               "ICE",
    "Ashuganj 150MW PP (Midland)":               "ICE",
    "Titas 50 MW Peaking PP":                    "ICE",
    "Chandpur 150 MW CCPP":                      "CCGT",
    "Chandpur 200MW (Desh energy)":              "ICE",
    "Import (Tripura)":                          "Import",
    "Jangalia 52 MW PP (Lakdanavi)":             "ICE",
    "Cumilla 25 MW PP (Summit)":                 "ICE",
    "Feni Lanka Power":                          "ICE",
    "Chowmuhani 113 MW":                         "ICE",
    "Chandpur 115(Doreen)":                      "ICE",
    "Sonagazi 75 MW (AC) Solar Power Plant":     "Solar PV",
    # --- Mymensingh region ---
    "Sarishabari 3 MW Solar Plant":              "Solar PV",
    "Mymensingh 200 MW PP (United)":             "ICE",
    "Jamalpur 115 MW PP (United)":               "ICE",
    "Sutiakhali 50 MW Solar PP":                 "Solar PV",
    "Tangail Palli Power Gen 22 MW":             "ICE",
    "Bhairob 54.5 MW":                           "ICE",
    # --- Sylhet region ---
    "Moulvibazar 10 MW Solar Power Plant":       "Solar PV",
    "Shahjibazar GTPP Unit- 8 & 9":             "OCGT",
    "Shahjibazar 86MW PP (Shahjibazar)":         "ICE",
    "Shahjibazar 100 MW GTPP":                   "OCGT",
    "Sylhet  20 MW GTPP":                        "OCGT",
    "Shahjahanulla 25 MW PP":                    "ICE",
    "Bibiyana South 400 MW":                     "CCGT",
    # --- Khulna region ---
    "Bheramara GTPP Unit-3":                     "OCGT",
    "Bheramara (HVDC )":                         "Import",
    "Faridpur 50 MW Peaking PP":                 "ICE",
    "Gopalganj 100 MW Peaking PP":               "ICE",
    "Rupsha 105 MW PP (Orion rupsha)":           "ICE",
    "Madhumati 100 MW PP":                       "ICE",
    "Mongla Orion 100 MW Solar PP":              "Solar PV",
    "Rampal 1320 MW (BIFPCL)":                   "Steam Turbine",
    "HVDC(Nepal)":                               "Import",
    # --- Barishal region ---
    "Patuakhali 1320 MW (RNPL)":                 "Steam Turbine",
    "Barisal 110 MW PP (Summit )":               "ICE",
    "Bhola  33 MW PP (Venture)":                 "ICE",
    "Bhola 225 MW  CCPP":                        "CCGT",
    "Payra 1320 MW":                             "Steam Turbine",
    "Bhola Nutan Biddut BD LTD":                 "CCGT",
    "United Payra Power Ltd.":                   "ICE",
    "Barisal 307 MW":                            "Steam Turbine",
    "Barisal 1 MW Solar Plant":                  "Solar PV",
    # --- Rajshahi region ---
    "Pabna 64 MW Solar Plant":                   "Solar PV",
    "Baghabari 71 MW GTPP":                      "OCGT",
    "Baghabari  100 MW GTPP":                    "OCGT",
    "Baghabari  50 MW Peaking PP":               "ICE",
    "Bera 70 MW Peaking PP":                     "ICE",
    "Katakhali 50 MW Peaking PP":                "ICE",
    "Santahar  50 MW Peaking PP":                "ICE",
    "Natore 52 MW PP (Rajlanka)":                "ICE",
    "Chapainawabganj 100 MW Peaking PP":         "ICE",
    "Bagura 113 MW PP (Confidence)-2":           "ICE",
    "Bagura 113 MW PP (Confidence)-1":           "ICE",
    "Sirajgonj 6.55 MW Solar":                   "Solar PV",
    "Adani Power Jharkhanda Ltd":                "Import",
    "Sirajganj 68 MW Solar Park":                "Solar PV",
    "Pabna Solar 100 MW":                        "Solar PV",
    "Sirajganj 2 MW Wind Power Plant":           "Wind",
    # --- Rangpur region ---
    "Saidpur 150 MW Simple Cycle Power Plant":   "OCGT",
    "Barapukuria TPP Unit-1 & 2":                "Steam Turbine",
    "Barapukuria 275 MW TPP Unit-3":             "Steam Turbine",
    "Rangpur 20 MW  GTPP":                       "OCGT",
    "Saidpur 20 MW GTPP":                        "OCGT",
    "Rangpur 113 MW PP (Confidence)":            "ICE",
    "Sympa Solar Power 8 MW":                    "Solar PV",
    "Energypac Power Venture Thakurgaon Ltd.":   "ICE",
    "Intraco Solar 30 MW":                       "Solar PV",
    "Teesta Solar Limited":                      "Solar PV",
}

# ── Fuel lookup ────────────────────────────────────────────────────────────
FUEL_LOOKUP = {
    "Ghorasal Repowered CCPP Unit-3":            "Gas",
    "Ghorasal Repowered CCPP Unit-4":            "Gas",
    "Ghorasal TPP Unit-5":                       "Gas",
    "Ghorasal 365 MW CCPP Unit-7":               "Gas",
    "Ghorashal 108 MW PP (Regent)":              "Gas",
    "Haripur GTPP":                              "Gas",
    "Haripur 412 MW CCPP":                       "Gas",
    "Meghnaghat 450 MW CCPP (MPL)":              "Gas",
    "Meghnaghat CCPP(Summit)":                   "Gas",
    "Madanganj-55 MW PP(Summit)":                "HFO",
    "Siddhirgonj 210 MW TPP":                    "Gas",
    "Siddhirgonj 2*120 MW GTPP":                 "Gas",
    "Siddhirganj 335 MW CCPP":                   "Gas",
    "Gagnagar 102 MW PP (Digital Power)":        "HFO",
    "Kamalaghat 54 MW PP(Banco Energy)":         "HFO",
    "Kodda 150 MW PP BRPL":                      "HFO",
    "Manikganj 55 MW PP (Northern)":             "HFO",
    "Nababganj 55 MW PP (Southern power )":      "HFO",
    "Summit Power Ashulia":                      "Gas",
    "Summit Power Madhabdi":                     "Gas",
    "Gazipur 52 MW PP":                          "HFO",
    "Tongi 80 MW GTPP":                          "Gas",
    "Kodda 300 MW PP Unit-2 (Summit)":           "HFO",
    "Kodda 149 MW PP Unit-1 (Summit)":           "HFO",
    "Gazipur 100 MW PP":                         "HFO",
    "Meghnaghat 104 MW PP (OPCL)":               "HFO",
    "Manikgonj 162MW PP(MPGL)":                  "HFO",
    "Spectra Solar Plant Ltd.":                  "Solar",
    "Kanchan Purbachal Power Generation Ltd.":   "HFO",
    "Unique Meghnaghat Power Limited (UMPL)":    "Gas",
    "Meghnaghat CCPP(Summit)-2":                 "Gas/HSD",
    "JERA Meghnaghat Power Limited":             "Gas",
    "Sreepur 150 MW PP BRPL":                    "HFO",
    "Chattogram TPP":                            "Gas",
    "Raozan 25 MW PP":                           "HFO",
    "Teknaf  20MW PP (Solartech)":               "Solar",
    "Patenga 50MW PP (Baraka)":                  "HFO",
    "Karnaphuli Hydro PP Unit-1,2,3,4, 5":       "Hydro",
    "Sikalbaha 225MW CCPP":                      "Gas/HSD",
    "Sikalbaha Peaking GT":                      "Gas/HSD",
    "Sikalbaha 105 MW PP (Baraka Sikalbaha)":    "HFO",
    "Hathazari 100 MW peaking PP":               "HFO",
    "Dohazari -Kalaish 100 MW Peaking":          "HFO",
    "Juldah 100 MW PP Unit-3 (Acorn)":           "HFO",
    "Malancha, Ctg. EPZ (United)":               "Gas",
    "Chattogram 108 MW PP (ECPV)":               "HFO",
    "Kaptai 7 MW  Solar PP":                     "Solar",
    "Anwara 300 MW PP (United)":                 "HFO",
    "Jodiac Power":                              "HFO",
    "Karnaphuli Power Ltd.":                     "HFO",
    "Juldah unit-2 (Acorn)":                     "HFO",
    "Anlima Energy Ltd.":                        "HFO",
    "Mirsharai 150 MW BRPL":                     "HFO/Gas",
    "SS Power":                                  "Coal",
    "Cox's Bazar Wind":                          "Wind",
    "Matarbari 2*600 MW (CPGCBL)":               "Coal",
    "Ashuganj CCPP 225 MW":                      "Gas",
    "Ashuganj 450 MW CCPP(North)":               "Gas",
    "Ashuganj 450 MW CCPP(South)":               "Gas",
    "Ashuganj 420 MW CCPP(East)":                "Gas",
    "Ashuganj TSK 50 MW PP":                     "Gas",
    "Ashuganj 55 MW PP (Precision)":             "Gas",
    "Ashuganj 195 MW PP (APSCL-United)":         "Gas",
    "Ashuganj 51 MW PP (Midland)":               "Gas",
    "Ashuganj 150MW PP (Midland)":               "HFO",
    "Titas 50 MW Peaking PP":                    "HFO",
    "Chandpur 150 MW CCPP":                      "Gas",
    "Chandpur 200MW (Desh energy)":              "HFO",
    "Import (Tripura)":                          "Import",
    "Jangalia 52 MW PP (Lakdanavi)":             "HFO",
    "Cumilla 25 MW PP (Summit)":                 "ICE",
    "Feni Lanka Power":                          "HFO",
    "Chowmuhani 113 MW":                         "HFO",
    "Chandpur 115(Doreen)":                      "HFO",
    "Sonagazi 75 MW (AC) Solar Power Plant":     "Solar",
    "RPCL 210MW CCPP":                           "Gas",
    "Sarishabari 3 MW Solar Plant":              "Solar",
    "Mymensingh 200 MW PP (United)":             "HFO",
    "Jamalpur 115 MW PP (United)":               "HFO",
    "Sutiakhali 50 MW Solar PP":                 "Solar",
    "Tangail Palli Power Gen 22 MW":             "HFO",
    "Bhairob 54.5 MW":                           "HFO",
    "Moulvibazar 10 MW Solar Power Plant":       "Solar",
    "Fenchugonj CCPP Phase-1":                   "Gas",
    "Fenchugonj CCPP Phase-2":                   "Gas",
    "Kushiara 163 MW CCPP (KP)":                 "Gas",
    "Shajibazar 330 MW CCPP":                    "Gas",
    "Shahjibazar GTPP Unit- 8 & 9":              "Gas",
    "Shahjibazar 86MW PP (Shahjibazar)":         "Gas",
    "Shahjibazar 100 MW GTPP":                   "Gas",
    "Sylhet 225 MW CCPP":                        "Gas",
    "Sylhet  20 MW GTPP":                        "Gas",
    "Shahjahanulla 25 MW PP":                    "Gas",
    "Bibiana-II 341 MW CCPP (Summit)":           "Gas",
    "Bibiyana-III 400 MW CCPP":                  "Gas",
    "Bibiyana South 400 MW":                     "Gas",
    "Bheramara GTPP Unit-3":                     "HSD",
    "Bheramara (HVDC )":                         "Import",
    "Faridpur 50 MW Peaking PP":                 "HFO",
    "Khulna 225 MW CCPP":                        "HSD/Gas",
    "Gopalganj 100 MW Peaking PP":               "HFO",
    "Bheramara 410 MW CCPP":                     "Gas",
    "Rupsha 105 MW PP (Orion rupsha)":           "HFO",
    "Madhumati 100 MW PP":                       "HFO",
    "Mongla Orion 100 MW Solar PP":              "Solar",
    "Khulna 330 MW CCPP":                        "HSD/Gas",
    "Rampal 1320 MW (BIFPCL)":                   "Coal",
    "HVDC(Nepal)":                               "Import",
    "Patuakhali 1320 MW (RNPL)":                 "Coal",
    "Barisal 110 MW PP (Summit )":               "HFO",
    "Bhola  33 MW PP (Venture)":                 "Gas",
    "Bhola 225 MW  CCPP":                        "Gas",
    "Payra 1320 MW":                             "Coal",
    "Bhola Nutan Biddut BD LTD":                 "Gas/HSD",
    "United Payra Power Ltd.":                   "HFO",
    "Barisal 307 MW":                            "Coal",
    "Barisal 1 MW Solar Plant":                  "Solar",
    "Pabna 64 MW Solar Plant":                   "Solar",
    "Baghabari 71 MW GTPP":                      "Gas",
    "Baghabari  100 MW GTPP":                    "Gas",
    "Baghabari  50 MW Peaking PP":               "HFO",
    "Bera 70 MW Peaking PP":                     "HFO",
    "Katakhali 50 MW Peaking PP":                "HFO",
    "Sirajgonj 225MW CCPP Unit-1":               "Gas/HSD",
    "Sirajgonj 225MW CCPP Unit-2":               "Gas/HSD",
    "Sirajgonj 225MW CCPP Unit-3":               "Gas/HSD",
    "Sirajgonj 400 MW CCPP Unit-4":              "Gas/HSD",
    "Santahar  50 MW Peaking PP":                "HFO",
    "Natore 52 MW PP (Rajlanka)":                "HFO",
    "Chapainawabganj 100 MW Peaking PP":         "HFO",
    "Bagura 113 MW PP (Confidence)-2":           "HFO",
    "Bagura 113 MW PP (Confidence)-1":           "HFO",
    "Sirajgonj 6.55 MW Solar":                   "Solar",
    "Adani Power Jharkhanda Ltd":                "Import",
    "Sirajganj 68 MW Solar Park":                "Solar",
    "Pabna Solar 100 MW":                        "Solar",
    "Sirajganj 2 MW Wind Power Plant":           "Wind",
    "Saidpur 150 MW Simple Cycle Power Plant":   "HSD",
    "Barapukuria TPP Unit-1 & 2":                "Coal",
    "Barapukuria 275 MW TPP Unit-3":             "Coal",
    "Rangpur 20 MW  GTPP":                       "HSD",
    "Saidpur 20 MW GTPP":                        "HSD",
    "Rangpur 113 MW PP (Confidence)":            "HFO",
    "Sympa Solar Power 8 MW":                    "Solar",
    "Energypac Power Venture Thakurgaon Ltd.":   "HFO",
    "Intraco Solar 30 MW":                       "Solar",
    "Teesta Solar Limited":                      "Solar",
    "Cumilla 25 MW PP (Summit)":                 "Gas",
}


# ── Helpers ────────────────────────────────────────────────────────────────

def log_linear_interp(p: float, points: list) -> float:
    ps = np.array([pt[0] for pt in points], dtype=float)
    cs = np.array([pt[1] for pt in points], dtype=float)

    if np.all(cs == cs[0]):
        return round(float(cs[0]), 2)

    log_ps = np.log(ps)
    log_cs = np.log(np.where(cs == 0, 1e-9, cs))
    log_p  = np.log(max(p, 0.1))

    if log_p <= log_ps[0]:
        slope = (log_cs[1] - log_cs[0]) / (log_ps[1] - log_ps[0])
        log_c = log_cs[0] + slope * (log_p - log_ps[0])
    elif log_p >= log_ps[-1]:
        slope = (log_cs[-1] - log_cs[-2]) / (log_ps[-1] - log_ps[-2])
        log_c = log_cs[-1] + slope * (log_p - log_ps[-1])
    else:
        log_c = np.interp(log_p, log_ps, log_cs)

    result = np.exp(log_c)
    if np.all(cs == 0):
        return 0.0
    return round(float(result), 2)


def _marginal_cost(p_nom: float, tech: str, fuel: str) -> float | None:
    if tech == "Import" or fuel == "Import":
        return None
    if p_nom <= 0 or pd.isna(p_nom):
        return None
    fuel_cat = FUEL_CATEGORY.get(fuel)
    if fuel_cat is None:
        return None
    tech_ref = MC_REF.get(tech)
    if tech_ref is None:
        return None
    points = tech_ref.get(fuel_cat)
    if points is None:
        return None
    cost = log_linear_interp(p_nom, points)
    if fuel == "HSD":
        cost = round(cost * HSD_PREMIUM, 2)
    return cost


def _carrier(fuel_raw: str) -> str:
    # For dual-fuel use the first listed fuel to determine carrier
    primary = fuel_raw.split("/")[0].strip()
    return CARRIER_MAP.get(primary, "unknown")


def _primary_mc(row) -> float | None:
    """Single marginal_cost value for PyPSA: use the first listed fuel."""
    fuel_raw = str(row["fuel"]).strip()
    primary  = fuel_raw.split("/")[0].strip()
    col_key  = primary.lower().replace(" ", "")
    if col_key not in FUEL_COLS:
        return None
    return row.get(MC_COL[col_key])


# ── Processing pipeline ────────────────────────────────────────────────────

def process_raw_data(path: Path) -> tuple[pd.DataFrame, dict]:
    """
    Returns (canonical_df, warnings).

    Detects the PyPSA attribute header row by scanning for the row that
    contains 'name', 'bus', and 'p_nom'. Column names come from that row
    where available; blank positions fall back to the human-readable label
    in the row above (normalized to snake_case). Trailing empty columns
    are dropped. This makes parsing robust to column insertions/reorderings.
    """
    warnings: dict[str, list[str]] = {
        "unknown_technology": [],
        "unknown_fuel":       [],
        "missing_bus":        [],
        "dual_fuel_mc":       [],
    }

    raw = pd.read_excel(path, sheet_name=0, header=None, dtype=str)

    # Find the PyPSA attribute header row
    pypsa_row_idx = None
    for i, row in raw.iterrows():
        cells = row.fillna("").astype(str).str.strip().tolist()
        if "name" in cells and "bus" in cells and "p_nom" in cells:
            pypsa_row_idx = i
            break
    if pypsa_row_idx is None:
        raise ValueError(f"Could not find PyPSA attribute header row in {path}")

    pypsa_names  = raw.iloc[pypsa_row_idx].fillna("").astype(str).str.strip().tolist()
    human_labels = raw.iloc[pypsa_row_idx - 1].fillna("").astype(str).str.strip().tolist()

    def _make_col(pypsa: str, human: str) -> str | None:
        if pypsa:
            return pypsa                                         # e.g. name, bus, p_nom
        if human:
            return re.sub(r'\W+', '_', human.lower()).strip('_') # e.g. area, technology, fuel
        return None                                              # trailing empty column

    cols = [_make_col(p, h) for p, h in zip(pypsa_names, human_labels)]

    data = raw.iloc[pypsa_row_idx + 1:].reset_index(drop=True)
    data.columns = cols
    data = data.loc[:, [c for c in cols if c is not None]].copy()

    # The source marginal cost column collides with our computed one; rename it
    if "marginal_cost" in data.columns:
        data = data.rename(columns={"marginal_cost": "marginal_cost_src"})

    # Forward-fill area
    data["area"] = data["area"].ffill()

    # Drop rows without a name or that are header echoes
    data = data[data["name"].notna()].copy()
    data = data[data["name"].str.strip() != "name"].copy()

    data["p_nom"] = pd.to_numeric(data["p_nom"], errors="coerce")

    # Resolve technology
    def _get_technology(row) -> str:
        existing = str(row["technology"]).strip() if pd.notna(row["technology"]) else ""
        if existing and existing.lower() not in ("nan", "none", ""):
            return existing
        return TECH_LOOKUP.get(row["name"].strip(), "Unknown")

    # Resolve fuel
    def _get_fuel(row) -> str:
        return FUEL_LOOKUP.get(row["name"].strip(), "Unknown")

    data["technology"] = data.apply(_get_technology, axis=1)
    data["fuel"]       = data.apply(_get_fuel, axis=1)

    # Warn on unknowns and missing bus
    for _, row in data.iterrows():
        name = row["name"].strip()
        if row["technology"] == "Unknown":
            warnings["unknown_technology"].append(name)
        if row["fuel"] == "Unknown":
            warnings["unknown_fuel"].append(name)
        bus = str(row["bus"]).strip() if pd.notna(row["bus"]) else ""
        if not bus or bus.lower() in ("nan", "none", ""):
            warnings["missing_bus"].append(name)

    # Compute per-fuel marginal costs
    for col in MC_COL.values():
        data[col] = None

    def _assign_mc(row):
        fuel_raw = str(row["fuel"]).strip()
        tech     = str(row["technology"]).strip()
        p        = row["p_nom"]
        fuels    = [f.strip() for f in fuel_raw.replace("/", "|").split("|") if f.strip()]

        if len(fuels) > 1:
            warnings["dual_fuel_mc"].append(
                f"{row['name'].strip()} ({fuel_raw}) -> primary MC from '{fuels[0]}'"
            )

        for fuel in fuels:
            if fuel in ("Import", "Unknown"):
                continue
            col_key = fuel.lower().replace(" ", "")
            if col_key not in FUEL_COLS:
                continue
            mc = _marginal_cost(p, tech, fuel)
            if mc is not None:
                row[MC_COL[col_key]] = mc
        return row

    data = data.apply(_assign_mc, axis=1)

    # Carrier column
    data["carrier"] = data["fuel"].apply(_carrier)

    # Clean bus column
    data["bus"] = data["bus"].apply(
        lambda v: str(v).strip() if pd.notna(v) and str(v).strip().lower() not in ("nan", "none", "") else ""
    )

    # Build canonical frame — drop internal columns
    canonical_cols = (
        ["name", "bus", "technology", "fuel", "carrier", "p_nom"]
        + list(MC_COL.values())
    )
    canonical = data[canonical_cols].copy()
    canonical = canonical.reset_index(drop=True)

    return canonical, warnings


# ── Output ─────────────────────────────────────────────────────────────────

def _print_warnings(warnings: dict) -> None:
    sections = [
        ("unknown_technology", "generators with unknown technology"),
        ("unknown_fuel",       "generators with unknown fuel"),
        ("missing_bus",        "generators with no bus assigned"),
        ("dual_fuel_mc",       "dual-fuel plants (primary fuel MC used)"),
    ]
    any_warnings = False
    for key, label in sections:
        items = warnings[key]
        if not items:
            continue
        any_warnings = True
        print(f"\n  !!  {len(items)} {label}:")
        for item in items:
            print(f"       {item}")
    if not any_warnings:
        print("\n  OK  No warnings.")


def main() -> None:
    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    PYPSA_DIR.mkdir(parents=True, exist_ok=True)

    canonical, warnings = process_raw_data(BASELINE_PATH)

    # ── Canonical output ──────────────────────────────────────────────────
    canonical.to_csv(CANONICAL_DIR / "generators.csv", index=False)

    # ── PyPSA-ready output ────────────────────────────────────────────────
    # Exclude Import rows (they are Links in PyPSA, not Generators)
    pypsa = canonical[canonical["technology"] != "Import"].copy()
    n_import = len(canonical) - len(pypsa)

    pypsa["marginal_cost"] = pypsa.apply(_primary_mc, axis=1)
    pypsa["p_max_pu"]      = 1.0

    pypsa_cols = ["bus", "p_nom", "carrier", "marginal_cost", "p_max_pu"]
    pypsa_out  = pypsa.set_index("name")[pypsa_cols]
    pypsa_out.to_csv(PYPSA_DIR / "generators.csv")

    # ── Summary ───────────────────────────────────────────────────────────
    print("=" * 60)
    print("Processing summary")
    print("=" * 60)
    print(f"\n  Total generators : {len(canonical)}")
    print(f"  Import rows      : {n_import} (excluded from PyPSA output)")
    print(f"  PyPSA generators : {len(pypsa_out)}")

    print("\n  Generators by technology:")
    for tech, grp in canonical.groupby("technology"):
        print(f"    {tech:<20}   {len(grp):>3}")

    print("\n  Generators by carrier:")
    for carrier, grp in canonical.groupby("carrier"):
        print(f"    {carrier:<10}   {len(grp):>3}")

    _print_warnings(warnings)

    print(f"\n  Written -> data/pipeline/canonical/generators.csv")
    print(f"  Written -> data/pipeline/pypsa-components/generators.csv")
    print("\nDone.")


if __name__ == "__main__":
    main()
