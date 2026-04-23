We faced an issue in output with the first iteration of conversion after we replaced the `[zeros(4,4)]` with `trf_ymat` in the initialization of `lines` in position `{2,3}` (1-indexed position) in `ieee_4bus_3ph_3_4wire.m`

# output of nr iteration 

## from python version 
```
  iter   1   max|dI| = 9.9737e-01
  iter   2   max|dI| = 1.1825e+00
  iter   3   max|dI| = 1.2121e+00
  iter   4   max|dI| = 1.2125e+00
  iter   5   max|dI| = 1.2125e+00
```
also, the output wasn't changing from this value and didn't converge after 50 iterations of nr

## from matlab
```
iter: 1
max|dI|: 0.99737
iter: 2
max|dI|: 0.065204
iter: 3
max|dI|: 0.00050969
iter: 4
max|dI|: 1.7967e-07
```
# value of busV

## from matlab
```
busV =

   1.0000
   1.0000
   1.0000
        0
   0.9870
   0.9920
   0.9888
        0
   0.9353
   0.9452
   0.9389
        0
   0.7971
   0.8624
   0.8217
        0
```
## output from python script, the 3rd column is equivalent to busV 
```
--- Bus Voltage Results ---
 Bus   Phase    |V| (pu)   Angle (deg)
   1       a    1.000000        0.0000
   1       b    1.000000     -120.0000
   1       c    1.000000      120.0000
   1       n    0.000000        0.0000

   2       a    0.986960       -0.3524
   2       b    0.992013     -120.3400
   2       c    0.988840      119.6376
   2       n    0.000000        0.0000

   3       a    0.935327       -3.7034
   3       b    0.945151     -123.4599
   3       c    0.938927      116.3868
   3       n    0.000000        0.0000

   4       a    0.797145       -9.2837
   4       b    0.862360     -128.2109
   4       c    0.821750      110.9378
   4       n    0.000000        0.0000  
```

**So, the value of `busV` matched but the output of nr iteration differed, which isn't expected.**

Following was the analysis of claude.

### Root cause

`nr_step()` was returning `dI_full` — the **full** `8×tot_bus` mismatch vector, including slack-bus rows. The MATLAB script (`curr_mm_3p3_4w.m:258`) does `dI(vanish_ind)=[]` to strip those rows **before** the convergence check. Python was skipping that step.

The slack-bus mismatch equals `−Y·V` at the slack node, which is small at the flat start (iteration 1) because all voltages are ≈ 1∠0°. But after iteration 1 updates the PQ-bus voltages to the real solution, the slack bus now sees the actual supply current — making `max|dI_full|` jump from small to large. That's the "very large dI in the second iteration."

### Fix (`nr_iteration.py:337`)

```python
# Before (wrong): included slack-bus rows
return sd, dI_full

# After (correct): same trim MATLAB applies before its convergence check
dI_conv = np.delete(dI_full, vanish_ind)   # removes slack + neutral rows
if len(delV_spec) > 0:
    dI_conv = np.concatenate([dI_conv, delV_spec])  # append PV voltage mismatch
return sd, dI_conv
```

`vanish_ind` already contains the slack bus indices (`0..7`) and the floating-neutral indices for 3-wire buses — identical to what MATLAB removes. After this fix, the convergence check in `main.py` works on the same reduced vector as MATLAB.