# Hourly demand disaggregation

The experiment is a one-day disaggregation. National hourly demand is already measured. What has to be invented is the hourly demand under it, for the nine areas and then for each grid substation, so the same procedure can be rerun when another day's report arrives.

Demand comes first. The missing object is hourly load served. A later dispatch can turn this demand into generation.

## Sources

The canonical tables in `data/pipeline/canonical/` are one operating point. Buses, lines, transformers, generators, and links describe the network. The 483 load rows are a single `p_set` snapshot, about 15,559 MW, on 187 buses. They are background for a later bus join. They are not a target the hourly series has to pass through.

The workbook `data/grids-substations-data-pgcb/pgcb-substation-Daily-Report- 11-05-2026.xlsx` is the 10 May 2026 daily report. The file name says 11 May. The sheets are the 10 May operating day.

The sheet **MAXIMUM LOAD SERVED BY DIFFERENT GRID SUB-STATIONS** is the substation data:

- 197 substations. 195 have a numeric daily maximum and the clock time it occurred. Those maxima sum to **16,100 MW**. Kaptai and Modern are `N/A`.
- The maxima are not simultaneous. 64 substations peak at 00:00 (4,422 MW of maxima). The other large groups are 13:00, 19:00, 12:00, and 19:30.
- Above that table, nine areas are given at **19:30 only**: Dhaka 5,233, Chattogram 1,525, Cumilla 1,204, Mymensingh 910, Sylhet 475, Khulna 1,646, Barishal 433, Rajshahi 1,358, Rangpur 942. Eastern grid is the first five (9,347 MW). Western grid is the last four (4,379 MW). The nine sum to **13,726 MW**.

The national hourly series is the sheet **Hourly Demand, Generation & Load-Shed**. Demand runs from **11,872 MW at 17:00** to **14,740 MW at 00:00**, and it includes a 19:30 point of **14,211 MW**. Day energy demand is 319.6 GWh, so the daily load factor is about **0.90**. The day is flat.

Plant-level hourly generation is already filled in on the generation log, and east/west generation is already on the generation curve. Those are not the missing series. The east/west generation curve can be tried later as a shape hint.

## Series to produce

The hourly product uses the report's own timestamps, including 19:30, so a substation marked 19:00 and one marked 19:30 stay distinct, and the area snapshot stays on its real clock time.

The hierarchy is national, then the nine areas, then substations. Eastern and Western hourly series are the sums of their areas.

National demand stays the published column. The nine area values at 19:30 stay the published area megawatts. Those two measurements disagree by **484 MW** (14,211 − 13,726), about **3.4%**. That gap is kept as an unallocated residual at every hour, in that same proportion. Area loads at hour `t` therefore sum to **96.6% of national demand**. Filling all of national demand with the nine areas would overwrite the only hour where both numbers were measured.

Each substation's recorded clock time is its highest hour, a little under the printed maximum when the area total cannot fit the printed number exactly. Every other hour is lower, and no hour exceeds the printed maximum.

Which substation belongs to which area is not on this sheet. That mapping is an input. Without it, the national-and-substation problem can still be run. The area layer waits on the map.

The series stay keyed to the substation names in the report until a later join onto canonical buses.

## Limits

The maximum limit is each substation's printed daily maximum.

The minimum limit is the national demand curve, after the 3.4% residual. It applies to the **sum**, not to each substation. A personal floor of 80% of each substation's own maximum, copied from the national valley, would overshoot the valley: 80% of 16,100 MW is about 12,880 MW, and the residual-adjusted valley is about 11,470 MW.

The day is coincident as well as flat. National peak is 14,740 MW against 16,100 MW of maxima, a coincidence of about **0.92**. At midnight, the 64 substations that peak then account for only 4,422 MW. To reach the residual-adjusted national target, the other substations must still be near **84% of their own maxima** at an hour that is not their peak. A typical residential curve that falls to 40% of peak is outside the feasible set. The national total pulls those hours back up. An external shape is allowed, and on this day it can only nudge a profile that is already flat.

No recorded peak group is large enough to break the national total. The biggest locked group is 4,422 MW at midnight, and the smallest national target is about 11,470 MW. Soft peaks and the national curve can be satisfied together. Whether a single area's 19:30 total can absorb the substations that peak inside it has to be checked after the area map exists.

## Approaches

| Approach | What it produces on this file | Where it breaks |
|---|---|---|
| One external shape, scaled so each substation touches its own maximum | Simple hourly series | Every substation peaks at the same hour. The sum at that hour is 16,100 MW, above 14,740 MW. |
| Same shape, shifted so the peak lands on each substation's recorded hour | Peak hours line up with the sheet | The day is too flat for a shift to create a real peak, and the hours still add up above national demand. Area totals are ignored. |
| Split national demand by the 19:30 area shares, then split each area in proportion to substation maxima | National total and the 19:30 area megawatts | Substation peak times are ignored. A substation that peaked at 02:00 is given its high hour at midnight. |
| Iterative proportional fitting (RAS): start from a flat prior and alternately scale hours to the national target and substations to their maxima | Totals and caps, and it reruns cheaply each day | A strict "this clock time is the highest hour" rule is awkward to enforce. Peak labels need a repair step. |
| One quadratic program for the day | All of the rules below, on this day's numbers, and on a later day by swapping the report | Needs the area map for the middle layer. Without the map, the same program runs at national level only. |
| A conditional generator trained in the style of the Kraftringen thesis | Useful once many days of maxima exist | This file is one day. There is no hourly history and no customer mix to train on. |

## Method

Use one quadratic program for the day. One variable per substation per timestamp. The prior is the national shape plus a small bump on the recorded peak timestamp.

Conditions:

- The recorded timestamp is strictly the highest value, and it sits at the printed maximum unless the area total forces it a little under.
- Every other timestamp is lower, and none exceeds the printed maximum.
- Substations in an area add up to that area's hourly target.
- Areas add up to 96.6% of published national demand.
- Neighboring hours stay smooth, so the bump is a peak and not a one-hour spike.

That is a few thousand variables and a few thousand linear conditions. The same program reruns on a later day when that day's demand column, area evening totals, and substation maxima replace this day's.

Solve once for the central series. Then randomize the height of the peak bump inside the same conditions and solve again. The ensemble is the synthetic data: every member respects the printed maxima, the recorded peak times, the 19:30 area totals, and the national curve.

A deep residential prior can be included as a comparison case. On this day the solver has to lift it into the 70–90% band of each substation's own maximum. That lift is the result worth seeing.

When a time range of daily reports exists, those reconciled series become the material a conditional generator can learn from. This single day does not support that training.
