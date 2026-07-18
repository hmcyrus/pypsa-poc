# Putting the Power Grid on the Map — Progress Summary

*Last updated: 18 July 2026*

## The goal

We are building a map of Bangladesh's electricity transmission network: every
substation shown as a dot (colored by voltage level), with the transmission
lines drawn between them. To do that, every substation needs a real-world
location (latitude/longitude). This document explains how far we've gotten,
where the results live, and what still needs a human touch.

## Where things stand

The network has **302 buses** (connection points in the electrical model).
Many of them are the same physical site at different voltage levels, so they
boil down to **251 real-world places** to locate.

| | Places | Share |
|---|---|---|
| **Located and verified** | 173 | 69% |
| Located but not yet trusted | 44 | 18% |
| No location found yet | 34 | 13% |

The 173 verified places were found automatically using OpenStreetMap (a free,
community-built world map) and then double-checked with a simple physical
test: we know the length of every transmission line, so if two "located"
substations sit farther apart than the line connecting them could possibly
reach, one of the locations must be wrong. Every verified place passed that
test. This mattered — the check caught mix-ups like a substation near Dhaka
being confused with a same-named town 300 km away.

## How to look at the results

Everything lives in the folder `data/pipeline/geo/`:

- **`grid_map.html`** — *start here.* Open it in any web browser. Dots are
  substations (red = 400 kV, orange = 230 kV, blue = 132 kV; solid = verified,
  hollow = not yet trusted). Lines connect them. Anything drawn as a **dashed
  pink line** is a location the distance test rejected — a visual "something
  is wrong here."
- **`bus_locations.csv`** — the master spreadsheet, one row per place: its
  coordinates, what it matched on the map, a match score, and a status
  (`accepted` = verified, `provisional`/`reopened` = found but doubtful,
  `unresolved` = not found).
- **`leftovers.csv`** — just the doubtful and missing rows: the to-do list.
- **`length_flags.csv`** — the distance-test failures, with the line length
  versus the actual distance, so you can see how bad each mismatch is.

## Why the remaining 78 places need manual help

The free map data simply doesn't have everything. What's left is the hard
tail: small or brand-new substations that nobody has drawn on OpenStreetMap
yet, industrial sites known by company acronyms, places whose names are
spelled several different ways, and a handful of cross-border connection
points in India. No amount of re-running the automatic search will conjure
data that isn't there.

Two ways to finish the job:

1. **Google Places search (faster, small cost).** Google's map database is
   richer than OpenStreetMap's. This needs a Google Cloud account with
   billing enabled and an API key — something only the project owner can set
   up. The code is ready to use it the moment a key exists, and we've already
   computed a "must be within this circle" constraint for each missing place
   (from the line lengths of its neighbors), which keeps the search honest.
2. **Manual lookup (free, slower).** A person looks up each of the 78 places
   in Google Maps and pastes the coordinates into an overrides file. We can
   generate a helper page that lists each missing place with ready-made
   search links and hints about which verified neighbors it should be near,
   so each lookup takes a minute or two.

Either way, whatever survives both routes goes through the same manual
overrides file, and a few special cases (the India-side endpoints of
cross-border links) will be typed in by hand regardless.

## What happens after that

Once every place has a trusted coordinate, the final steps are already
planned: place the 146 power plants (they sit at or near their substations),
write the coordinates into the electrical model, and re-render the map. The
finish line test is simple: no dashed pink lines left — every line on the map
looks like a plausible piece of the real grid.
