# IEEE 4-Bus System — Topology Variations

This document explores five network topologies of similar complexity to the
canonical IEEE 4-Bus System, each illustrating a different structural approach
to power distribution. All examples preserve the four-bus scale and include a
mix of generation, transformation, transmission, and load elements.

These variations are intended as a learning reference for understanding how
network topology shapes power flow, reliability, fault behavior, and the
integration of distributed energy resources.

---

## Topology 1: Radial (Classic IEEE 4-Bus)

A straight radial feed from generation through a step-down transformer to load.
This is the canonical reference topology — simple, economical, but offering no
redundancy.

```
   [G]          Line 1-2        Trf         Line 3-4         [Load]
   (~)─────[1]══════════════[2]──(Trf)──[3]══════════════[4]──▶
    │       │    12.47 kV    │          │    4.16 kV     │
   ═╧═                                                    ═╧═
               P+jQ                          P+jQ
```

**Characteristics**
- Single source, single path to load
- Lowest cost, simplest protection
- A fault anywhere on the feeder de-energizes everything downstream
- Typical of rural distribution feeders

---

## Topology 2: Ring / Loop Network

A closed-loop configuration providing redundancy — if one segment fails, power
reroutes around the ring.

```
                      Line 1-2
        [G]     ┌════════════════┐
        (~)────[1]              [2]
         │      ║                ║
        ═╧═     ║ Line           ║ Line
                ║ 1-4            ║ 2-3
                ║                ║
               [4]══════════════[3]──(Trf)
                │     Line 4-3   │
                ▼                ▼
              Load A           Load B
              4.16 kV         12.47 kV
```

**Characteristics**
- Two independent paths to every load
- Requires directional/differential protection
- Common in urban distribution and industrial plants
- Higher reliability than radial at modest extra cost

---

## Topology 3: Mesh / Interconnected

Multiple paths between every bus — the highest reliability topology, used in
critical transmission grids and data-center-grade infrastructure.

```
       [G1]                            [G2]
       (~)                             (~)
        │                               │
       [1]═══════════ Line 1-2 ════════[2]
        ║ ╲                          ╱ ║
        ║   ╲ Line 1-3      Line 2-4 ╱ ║
        ║     ╲                    ╱   ║
        ║       ╲                ╱     ║
     Line 1-4     ╲            ╱    Line 2-3
        ║           ╲        ╱         ║
        ║             ╲    ╱           ║
        ║          (Trf)  (Trf)        ║
        ║             ╱    ╲           ║
       [4]═══════════════════════════[3]
        │         Line 4-3             │
        ▼                               ▼
      Load                            Load
      4.16 kV                        4.16 kV
```

**Characteristics**
- Dual generation sources with full interconnection
- Power flows redistribute automatically on contingency
- Complex protection coordination (distance / line differential)
- Typical of transmission backbones and N-1 secure networks

---

## Topology 4: Star / Radial Hub

A central bus distributes to multiple spokes — common for substation-fed
distribution where one primary bus serves several independent feeders.

```
                      [G]
                      (~)
                       │
                      ═╧═
                       │
                      [1]  ◀── Central Hub (12.47 kV)
                     ╱ │ ╲
                    ╱  │  ╲
             Line  ╱   │   ╲ Line
             1-2  ╱    │    ╲ 1-4
                 ╱  Line    ╲
                ╱    1-3     ╲
               ╱      │       ╲
           (Trf)    (Trf)   (Trf)
             │        │        │
            [2]      [3]      [4]
             ▼        ▼        ▼
           Load A   Load B   Load C
          4.16 kV  4.16 kV  480 V
```

**Characteristics**
- Single point of generation, multiple independent LV outlets
- Fault on one spoke does not affect the others
- Common in campus / industrial / refugee-camp microgrids
- The hub becomes a single point of failure if unprotected

---

## Topology 5: Dual-Source Tie (Hybrid Grid + Solar)

Two independent sources feeding a common tie bus — the typical structure for
grid-tied renewable integration, where a utility feed (e.g., PDB) runs in
parallel with an on-site PV array.

```
   [Grid/PDB]                              [PV Array]
      (~)                                     (☀)
       │                                       │
      ═╧═                                     ═╧═
       │                                       │
      [1]                                     [4]
       ║                                       ║
    Line 1-2                                Line 4-3
       ║                                       ║
      [2]──(Trf Step-Down)──[3]◀══ Tie Bus ═══[3]
       │       12.47→4.16kV   │
       ▼                      ▼
     Load                   Load
    (Critical)            (Non-critical)
```

**Characteristics**
- Two uncorrelated sources increase availability
- Solar PV may export to grid at low-load hours (reverse power flow)
- Requires anti-islanding protection on the PV inverter
- Voltage regulation must account for variable PV output
- Representative of humanitarian microgrid projects where a weak national
  utility is augmented by on-site renewables

---

## Summary Table

| # | Topology          | Redundancy | Cost    | Typical Use                          |
|---|-------------------|------------|---------|--------------------------------------|
| 1 | Radial            | None       | Lowest  | Rural feeders                        |
| 2 | Ring / Loop       | Single     | Medium  | Urban distribution, industrial       |
| 3 | Mesh              | Full N-1   | High    | Transmission, critical infrastructure|
| 4 | Star / Hub        | Per-spoke  | Medium  | Campus / substation distribution     |
| 5 | Dual-Source Tie   | Dual infeed| Medium  | Grid + renewable hybrid microgrids   |
