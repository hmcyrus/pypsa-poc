"""
Geo map reading script.
Parses grids-formatted.csv → geo-map-lines.csv using:
  - Visual inspection of network-geo-map.pdf for status
  - Naming convention: {bus0}_{v}kVto{bus1}_{v}kV_Line{n}

LILO rules:
  "LILO of A-B at C"  → two connections: C→A (length L) and C→B (length L)
  "LILO of A-B"       → treat as a parallel connection A→B (length L)
"""

import csv
import re
from pathlib import Path

BASE = Path(__file__).parent

# ---------------------------------------------------------------------------
# Status overrides – based on geo-map visual inspection
# Key: lowercase substring of the raw line name  Value: Existing|Ongoing|Planned
# ---------------------------------------------------------------------------
STATUS_OVERRIDES = {
    # 400 kV – dashed/dotted on geo map
    "roopur-gopalganj (overhead)": "Ongoing",
    "roopur-gopalganj (ug)": "Ongoing",
    "rooppur-gopalganj (overhead)": "Ongoing",
    "rooppur-gopalganj (ug)": "Ongoing",
    "barguna pp - payra pp": "Ongoing",
    "monakosa-rahanpur": "Ongoing",
    # 230 kV – partial or dotted on geo map
    "bogura(s)-noagaon (partial)": "Ongoing",
    "lilo of bogura(s)-noagaon": "Ongoing",
    # 132 kV later additions that appear as dashed/dotted on the geo map
    "panchagarh-thakurgaon": "Existing",   # confirmed solid red in zoom
    "thakurgaon-panchagarh": "Existing",
    "naogaon-joypurhat": "Existing",
    "niyamatpur-rahanpur (lilo point)": "Ongoing",
    "us dk - cox's bazar": "Ongoing",
    "barishal (n)-bhandaria": "Ongoing",
    "sirangj 68mw solar-sirajganj": "Existing",
    "lilo of cumilla(n)-daudkandi at muradnagar": "Existing",
    "lilo of ashuganj-kishoreganj at bajitpur": "Existing",
    "rahanpur-chowdala(section onward)": "Ongoing",
    "lilo of ghatial-rpcl at muktagacha": "Ongoing",
    "muradnagar-kosba": "Existing",
    "jhenaidah-chuadanga": "Existing",
    "kurigram-lalmonirht 2nd circuit": "Existing",
    "cumilla(n)-chandina": "Ongoing",
    "rajendrapur-sreepur": "Ongoing",
    "araihazar-bhulta": "Ongoing",
    "dynamics solar plant-ishurdi": "Ongoing",
    "kachua-laksam": "Ongoing",
    "chowmuhani-lakshmipur": "Ongoing",
    "lilo of saidpur-rangpur at taraganj": "Existing",
    "lilo of feni-chowmuhani at dagunbhuyan": "Ongoing",
    "rampura-basundhara": "Existing",
    "sripur-kodda (partial)": "Ongoing",
    "sirajganj solar-sirajganj grid": "Existing",
    "lilo of ishwardi-baghabari line at sathia": "Existing",
    "kaliganj- maheshpur": "Ongoing",
    "lilo of barishal-patuakhali at bakerganj": "Existing",
    "sathia-pabna 64 mw solar": "Ongoing",
}

CIRCUIT_MAP = {
    "single": 1,
    "double": 2,
    "triple": 3,
    "four":   4,
}


def get_status(raw_name: str, sn: int, voltage: str) -> str:
    key = raw_name.strip().lower()
    for k, v in STATUS_OVERRIDES.items():
        if k in key:
            return v
    if voltage == "132 kV" and sn >= 229:
        return "Ongoing"
    return "Existing"


def circuit_count(raw: str) -> int:
    return CIRCUIT_MAP.get(raw.strip().lower(), 1)


def extract_voltage(raw: str) -> int:
    m = re.search(r"(\d+)\s*kV", raw, re.IGNORECASE)
    return int(m.group(1)) if m else 132


# ---------------------------------------------------------------------------
# Node name parsing
# ---------------------------------------------------------------------------

def split_on_dash(text: str):
    """
    Split 'A-B' or 'A - B' into (A, B).
    Prefers ' - ' separator; falls back to first bare '-'.
    """
    if " - " in text:
        a, b = text.split(" - ", 1)
        return a.strip(), b.strip()
    if "-" in text:
        a, b = text.split("-", 1)
        return a.strip(), b.strip()
    return None


def parse_nodes(raw_name: str):
    """
    Return list of (from_node, to_node) pairs.
    Most entries yield one pair; LILOs with an "at" clause yield two pairs.
    """
    name = raw_name.strip()

    # T-connection pattern
    m = re.match(r"T-connection\s+from\s+(.+?)\s+to\s*(.+)$", name, re.IGNORECASE)
    if m:
        return [(m.group(1).strip(), m.group(2).strip())]

    # LILO / LILI (handle both spellings, and "atNode" without space)
    # Pattern: "LIL[IO] of A-B [line [qualifier]] at C"  (space before "at" optional)
    m = re.match(
        r"LIL[IO]\s+of\s+(.+?)\s+(?:(?:line(?:\s+\w+)?)\s+)?at\s*(.+)$",
        name, re.IGNORECASE
    )
    if m:
        main_part = m.group(1).strip()
        # Remove trailing qualifiers like "single circuit", "d/c"
        main_part = re.sub(
            r"\s+(single|double|triple|four|d/c|s/c)\s*(circuit)?$",
            "", main_part, flags=re.IGNORECASE
        ).strip()
        lilo_pt = m.group(2).strip()
        pair = split_on_dash(main_part)
        if pair:
            node_a, node_b = pair
            # Return two connections: lilo_pt → A, and lilo_pt → B
            return [(lilo_pt, node_a), (lilo_pt, node_b)]
        return [(lilo_pt, main_part)]

    # LILO / LILI without "at" clause → treat as parallel A-B
    m2 = re.match(r"LIL[IO]\s+of\s+(.+)$", name, re.IGNORECASE)
    if m2:
        inner = m2.group(1).strip()
        # Strip trailing " line" artefact
        inner = re.sub(r"\s+line\s*$", "", inner, flags=re.IGNORECASE)
        pair = split_on_dash(inner)
        if pair:
            return [pair]
        return [(inner, inner)]

    # Strip HVDC prefix
    name = re.sub(r"^HVDC\s+", "", name, flags=re.IGNORECASE).strip()

    pair = split_on_dash(name)
    if pair:
        return [pair]

    # Fallback: self-loop (won't be useful but won't crash)
    return [(name, name)]


# ---------------------------------------------------------------------------
# Naming convention
# ---------------------------------------------------------------------------

def bus_label(node: str, v_nom: int) -> str:
    node = re.sub(r"\s+", " ", node).strip()
    return f"{node}_{v_nom}kV"


def make_line_name(from_node: str, to_node: str, v_nom: int, circuit: int) -> str:
    return f"{bus_label(from_node, v_nom)}to{bus_label(to_node, v_nom)}_Line{circuit}"


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

def generate():
    input_path  = BASE / "grids-formatted.csv"
    output_path = BASE / "geo-map-lines.csv"

    rows_out = []
    current_voltage = None
    current_sn = 0

    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header

        for raw_row in reader:
            while len(raw_row) < 8:
                raw_row.append("")

            sn_raw     = raw_row[0].strip()
            name_raw   = raw_row[1].strip()
            length_raw = raw_row[2].strip()
            ckt_raw    = raw_row[4].strip()
            volt_raw   = raw_row[7].strip()

            if not name_raw:
                continue

            if volt_raw:
                v_nom = extract_voltage(volt_raw)
                if v_nom != current_voltage:
                    current_voltage = v_nom
                    current_sn = 0

            if current_voltage is None:
                continue

            try:
                current_sn = int(sn_raw)
            except ValueError:
                current_sn += 1

            try:
                length_km = float(length_raw)
            except ValueError:
                length_km = 0.0

            n_circuits = circuit_count(ckt_raw)
            status     = get_status(name_raw, current_sn, f"{current_voltage} kV")
            pairs      = parse_nodes(name_raw)

            for (from_node, to_node) in pairs:
                # Track circuit numbering per unique (from, to, v) pair
                for c in range(1, n_circuits + 1):
                    rows_out.append({
                        "start_node":       from_node,
                        "end_node":         to_node,
                        "voltage_level":    f"{current_voltage} kV",
                        "approx_length_km": length_km,
                        "status":           status,
                        "line_name":        make_line_name(from_node, to_node, current_voltage, c),
                    })

    fieldnames = [
        "start_node", "end_node", "voltage_level",
        "approx_length_km", "status", "line_name",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"Written {len(rows_out)} rows → {output_path}")

    from collections import Counter
    print("Voltage:", dict(Counter(r["voltage_level"] for r in rows_out)))
    print("Status: ", dict(Counter(r["status"] for r in rows_out)))


if __name__ == "__main__":
    generate()
