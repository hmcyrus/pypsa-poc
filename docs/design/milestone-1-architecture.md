# PLEXOS-Style Simulation Platform — Architecture & Milestone 1

Source of the target picture: *PLEXOS Overview & Tutorial*, pages 1–7.
This document defines (a) the overall architecture we are steering toward and
(b) a deliberately small **Milestone 1** that is deliverable on its own yet
structurally extendable to the full vision.

---

## 1. The PLEXOS picture we are copying

Pages 1–7 of the tutorial describe five load-bearing ideas, independent of any
particular feature (hydro, emissions, bidding, …):

1. **Input database, separate from the engine.** All system data lives in a
   structured store (objects + properties), created and edited independently
   of simulation runs. In PLEXOS this is an Access database.
2. **Simulation phases.** Four models over the same database:
   - **LT Plan** — long-term capacity expansion (10–30 yr, NPV-minimising
     build/retire decisions for generation and transmission),
   - **PASA/Preschedule** — capacity adequacy, maintenance and forced outages,
   - **MT Schedule** — medium-term, load-duration-curve based scheduling,
   - **ST Schedule** — trading-period chronological dispatch and pricing with
     optional thermal unit commitment.
3. **One-directional phase chaining.** Phases can run in sequence and feed
   each other, but only **long-term → short-term** (LT → PASA → MT → ST).
   Never the reverse.
4. **Engine → LP/MIP → pluggable solver.** The engine reads the database,
   emits an optimization problem, and hands it to an interchangeable
   commercial-grade solver (MOSEK/CPLEX in the tutorial).
5. **Results database + log per run.** The solver's outcome comes back as a
   *database the user explores*, not a console printout.

The client/server split (license check, remote solve) is an operational detail
of the ISU course setup; we note where it would slot in but do not build it.

## 2. Where the repo is today

- A **data pipeline** (`src/*_builder.py`, `src/line-bus-processor.py`,
  `src/bus_supplement.py`) turning spreadsheet exports into PyPSA component
  CSVs under `data/pipeline/pypsa-components/`.
- A **single-snapshot linear economic dispatch** (`src/economic_dispatch.py`)
  with strong infeasibility diagnostics, printing to stdout and saving one PNG.
- No time axis, no scenarios, no run persistence, no phase concept. Scripts
  are hardcoded to one dataset and invoked by hand.

The gap to the PLEXOS picture is therefore *architectural*, not mathematical —
PyPSA/linopy already covers the LP/MIP translation and solver plurality.

## 3. Target architecture

One Python package, `powersim`, with five layers mirroring §1. Arrows show the
only allowed dependency direction (top depends on bottom, never sideways-up):

```
┌─────────────────────────────────────────────────────────────┐
│  CLI / Runner            powersim run cases/<case>.yaml     │
├─────────────────────────────────────────────────────────────┤
│  Phase Engine            PhaseChain: LT → PASA → MT → ST    │
│                          (each phase: prepare → solve →     │
│                           emit; HandoffState flows long→short)│
├──────────────────────────┬──────────────────────────────────┤
│  Project Store (input)   │  Results Store (output)          │
│  base tables + profiles  │  runs/<run_id>/: solved network, │
│  + scenario overlays     │  summary tables, log, manifest   │
├──────────────────────────┴──────────────────────────────────┤
│  Model & Solve           pypsa.Network + linopy             │
│                          solver adapter: HiGHS default,     │
│                          Gurobi/CPLEX by config only        │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 Project Store — the "Access database"

A **project** is a directory, not code:

```
project/
  components/        # today's pypsa-components CSVs (buses, lines, gens, …)
  profiles/          # time series: load shapes, availability, fuel prices
  scenarios/         # named overlays: property patches applied at load time
  cases/             # runnable model definitions (YAML), see §4.2
```

PLEXOS concepts map directly: *objects/properties* → component CSVs,
*scenarios* → overlay patch files, *models* → case YAMLs, *horizon* → the
snapshot spec inside a case. Milestone 1 keeps files; a later move to SQLite
changes only this layer's loader, nothing above it.

### 3.2 Phase Engine

```python
class Phase(Protocol):
    name: str                                   # "st_schedule", "lt_plan", …
    def prepare(self, project: Project, case: Case,
                handoff: HandoffState) -> pypsa.Network: ...
    def solve(self, n: pypsa.Network, case: Case) -> SolveInfo: ...
    def emit(self, n: pypsa.Network, run: RunContext) -> PhaseResult: ...
```

- Phases register in a registry keyed by name; a case lists an ordered
  sequence of phases.
- `PhaseChain` validates the order against the PLEXOS rule (LT before PASA
  before MT before ST; illegal orders rejected up front) and threads a
  `HandoffState` forward — e.g. LT Plan's chosen capacities become the
  installed capacities ST dispatches; PASA's outage draws become `p_max_pu`
  time series for ST.
- **Milestone 1 implements only `st_schedule`.** The other three are empty
  registry slots — the chain, handoff object, and ordering rule exist from
  day one so adding LT/MT/PASA never reshapes the core.

### 3.3 Model & Solve

PyPSA is the LP/MIP generator (PLEXOS step 3), linopy the solver interface
(step 4). The solver adapter is pure configuration:

```yaml
solver:
  name: highs          # gurobi / cplex are a config change, not a code change
  options: {}
```

### 3.4 Results Store — the "outcome database"

Every run writes an immutable directory; nothing is only printed:

```
runs/<case>-<timestamp>/
  manifest.json        # case snapshot, git rev, phase sequence, solver, status
  network.nc           # solved pypsa.Network (export_to_netcdf)
  summary/             # tidy CSVs: dispatch, lmp, line_loading, costs, …
  report/              # charts + a small static HTML index
  run.log
```

`summary/` tables are the API for comparison tooling later ("diff two runs")
— the netCDF is the full-fidelity record.

### 3.5 CLI / Runner

```
powersim run cases/base-day.yaml        # execute a case end-to-end
powersim validate                       # structural checks, no solve
powersim report runs/<run_id>           # (re)build report from a stored run
```

The runner is deliberately thin: load project → build chain → execute → point
user at the run directory. A future server/API (PLEXOS's remote-solve split)
wraps this same entry point; it is out of scope for every near milestone.

## 4. Milestone 1 — "ST Schedule, end to end"

**Definition of done:** `powersim run cases/base-day.yaml` runs a 24-hour
chronological economic dispatch of the existing Bangladesh network and
produces a complete run directory with report. Nothing more.

### 4.1 Scope

In:
- `powersim/` package skeleton with all five layers present (§3), even where
  minimal.
- Phase registry + `PhaseChain` + ordering rule, with **one** registered
  phase: `st_schedule` — multi-snapshot **linear** dispatch (unit-commitment
  flag accepted in the schema but rejected as "not yet implemented";
  reserving the config surface now avoids a breaking schema change later).
- Time axis: hourly snapshots from the case spec; per-load hourly profiles
  from `profiles/load-shape.csv` (a normalized daily curve scaling each
  load's `p_set`; a single national shape is acceptable for M1).
- Project loader that reads today's `data/pipeline/pypsa-components/` as the
  `components/` table set — the existing builder pipeline is untouched and
  becomes the "data import" stage feeding the Project Store.
- Scenario overlays: a minimal patch format (`component, name, property,
  value`) applied at network build; one worked example scenario in the repo.
- Results Store exactly as §3.4, with report charts: dispatch stack over the
  day, LMP range, top line loadings, cost summary.
- Validation: port the structural pre-checks from `economic_dispatch.py` into
  `powersim validate`; the slack-relaxed infeasibility diagnosis is retained
  as the automatic on-failure path of `st_schedule`.

Out (explicitly deferred, with their landing slot):
- Unit commitment → M2, inside `st_schedule.solve` (committable generators).
- LT Plan / MT Schedule / PASA → M3+, new registry entries; PASA's outage
  draws use the same profiles mechanism (`p_max_pu` overlays) built in M1.
- Hydro/storage, ancillary services, emissions, bidding (tutorial pp. 5–6
  feature matrix) → component-level additions inside `prepare`; none touch
  the chain, stores, or CLI.
- SQLite project store, run-comparison tooling, server/API, GUI.

### 4.2 Case file (the M1 contract)

```yaml
name: base-day
description: 24h chronological dispatch, base scenario
phases: [st_schedule]                 # ordered; validated against LT→…→ST rule
horizon:
  start: 2026-01-15
  periods: 24
  freq: 1h
scenarios: []                         # e.g. [gas-price-high]
st_schedule:
  unit_commitment: false              # schema-present, M1 rejects true
load_profile: profiles/load-shape.csv
solver:
  name: highs
  options: {}
```

### 4.3 Package layout

```
src/powersim/
  __init__.py
  cli.py                 # run / validate / report
  project.py             # Project Store loader (+ scenario overlay engine)
  case.py                # case YAML schema + validation
  chain.py               # Phase protocol, registry, PhaseChain, HandoffState
  phases/
    st_schedule.py       # M1: chronological linear dispatch + diagnostics
  results.py             # run directory writer, manifest, summary tables
  report.py              # charts + static HTML index
  validate.py            # structural checks (ported from economic_dispatch)
```

### 4.4 Milestone sequence beyond M1 (orientation only)

| Milestone | Adds | PLEXOS analogue |
|---|---|---|
| M1 | ST Schedule linear, phases/stores/CLI skeleton | ST Schedule (no UC) |
| M2 | Unit commitment; richer profiles (per-zone loads, RE availability) | ST Schedule (full) |
| M3 | Outage/maintenance draws feeding ST via handoff | PASA/Preschedule |
| M4 | Load-duration-curve scheduling; LT expansion via `p_nom_extendable` | MT Schedule, LT Plan |
| M5 | Run comparison, SQLite store, server API | Outcome DB tooling, remote solve |

## 5. Design rules that keep M1 extendable

1. **Phases only talk through `HandoffState`** — never read each other's
   internals; long→short order enforced centrally in `chain.py`.
2. **All inputs come from the Project Store, all outputs go to the Results
   Store.** No phase reads ad-hoc paths or prints results as its output.
3. **The case YAML is the only run contract.** New capabilities appear as new
   optional keys with defaults; existing cases must keep running unchanged.
4. **Solver choice is configuration.** No phase may import a solver directly.
5. **The existing builder pipeline stays as-is** and feeds the Project Store;
   data cleaning improvements and simulation development stay decoupled.

## 6. Engine choice: is PyPSA sufficient for the MILP backbone?

The mathematical backbone of PLEXOS-style planning is MILP. The question is
whether PyPSA suffices for M1 and the overall vision, or whether a different
engine is needed. Short answer: **yes for M1 without qualification, yes for
~80% of the overall vision, and we should not swap PyPSA out.**

The deciding fact: PyPSA is not itself the MILP engine — it is a power-system
data model plus a formulation layer that *builds* an LP/MILP in
[linopy](https://github.com/PyPSA/linopy) and hands it to any solver. We are
pinned to `pypsa>=1.1.2` (the modern 1.x line), which everything below
assumes.

### 6.1 Milestone 1

M1 is chronological linear dispatch — a pure LP, no integer variables. PyPSA
does this natively and it is the workload PyPSA is most used for. Even M2's
unit commitment (the first genuinely MILP feature) is native:
`committable=True` gives min up/down times, start-up/shut-down costs, and
ramp limits including start/stop ramps — the standard UC formulation.

### 6.2 Overall vision, feature by feature

Mapping the tutorial's pp. 2–6 feature list against PyPSA 1.x:

**Native — no extra library needed:**
- DC-OPF co-optimized with dispatch; LMPs from LP duals
- Unit commitment MILP; committable *and* extendable together
- Multi-investment-period LT expansion with discounting (the LT Plan core)
- Discrete builds via modular capacity (`p_nom_mod` — integer unit counts,
  PLEXOS's "integer builds")
- Security-constrained (contingency) optimization
- Rolling-horizon solving (`optimize_with_rolling_horizon` — how PLEXOS's ST
  Schedule chops a year into daily MIP steps)
- Storage and pumped hydro; emissions caps and prices via global constraints
- Stochastic/scenario optimization (added in the 1.x line — covers LT Plan's
  "deterministic or stochastic" bullet)

**Buildable on PyPSA's escape hatch:** `n.optimize.create_model()` returns
the raw linopy model *before* solving; arbitrary variables and constraints
can be added to it. This is how the PLEXOS features PyPSA does not ship get
implemented — ancillary-service/reserve co-optimization (reserve variables +
requirement constraints), PLEXOS "generic constraints" and interface limits
(linear expressions over any variables; near one-to-one with linopy),
water-value curves (piecewise-linear terms on storage state of charge), and
heat-rate curves (piecewise-linear cost segments). None require leaving
PyPSA; they are constraints written in a phase's `prepare`/`solve` step —
exactly where the architecture puts them (design rule 1).

**Not realistically any engine's job off the shelf:**
- Monte Carlo outage draws (PASA) — sampling logic *around* the
  optimization; we write it in the PASA phase regardless of engine
- LMP decomposition into congestion + marginal-loss parts — linear DC has no
  losses; research-grade feature, deferred
- Game-theoretic bidding (Nash-Cournot/Bertrand) — an equilibrium/MPEC
  problem, a different mathematical class from MILP; no candidate engine
  provides it. Explicitly out of scope.

### 6.3 Alternatives assessed

| Alternative | Verdict |
|---|---|
| **Pyomo** | Maximum flexibility, but we would hand-write the network model, DC power flow, UC, and expansion formulations PyPSA already ships and has battle-tested; slower model construction at scale than linopy. Right tool for building a modeling language, not a planning tool. |
| **linopy directly** | Already underneath PyPSA; using it standalone means rewriting PyPSA's formulation layer for zero gain. Use it *through* the escape hatch. |
| **Sienna / PowerSimulations.jl** (NREL, Julia) | The only alternative to take seriously — architecturally the closest open-source thing to PLEXOS, with simulation sequencing and feed-forwards (our `PhaseChain`/`HandoffState`) built in. But it means moving the project to Julia and abandoning a working pandas/PyPSA-shaped pipeline. Cost is a rewrite; benefit is something §3 designs in ~200 lines. |
| **GridPath, Calliope, oemof, Antares** | Each covers a slice (production cost, expansion, adequacy); none is stronger than PyPSA across our whole phase list, and all inherit the same custom-constraint work for AS/hydro anyway. |

### 6.4 Where the real risk lives: the solver, not the library

National-scale 8760-hour UC MILPs are hard for *any* formulation layer; the
difference between tractable and not is HiGHS vs. Gurobi/CPLEX plus horizon
decomposition. The tutorial itself makes this point: PLEXOS emits the MIP
and ships it to MOSEK/CPLEX (p. 7). Both mitigations are already in this
design — the solver adapter (§3.3) makes commercial solvers a config change,
and rolling-horizon in the ST phase bounds MIP size the same way PLEXOS does.

### 6.5 Decision

Keep PyPSA as the engine core; add no new modeling library for M1 (linopy
and highspy are already in the stack). Two guardrails make this a low-regret
bet:

1. All custom-constraint work goes through the linopy escape hatch inside
   phase code — we never fork or fight PyPSA.
2. PyPSA is quarantined inside the Model & Solve layer (§3): the Project
   Store, PhaseChain, Results Store, and CLI do not depend on it
   conceptually. If a genuine wall is hit (e.g. AS co-optimization proves
   unmaintainable as custom constraints), swapping the bottom layer for
   Sienna or raw linopy is bounded surgery, not a restart.

That optionality is worth more than picking the theoretically maximal engine
today.
