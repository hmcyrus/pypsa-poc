# MATLAB Syntax & Concepts — Crash Course for Python/Java Developers

This guide is written for someone who knows Python and Java but is reading MATLAB
code for the first time. Every concept is illustrated with real examples taken
directly from the `.m` files in this repository.

---

## Table of Contents

1. [The Basics](#1-the-basics)
2. [Variables and Types](#2-variables-and-types)
3. [Indexing — The #1 Gotcha](#3-indexing--the-1-gotcha)
4. [Matrices and Vectors](#4-matrices-and-vectors)
5. [Arithmetic Operators](#5-arithmetic-operators)
6. [Control Flow](#6-control-flow)
7. [Functions](#7-functions)
8. [Scripts vs Functions vs the Workspace](#8-scripts-vs-functions-vs-the-workspace)
9. [Cell Arrays](#9-cell-arrays)
10. [Complex Numbers](#10-complex-numbers)
11. [Linear Algebra Operations](#11-linear-algebra-operations)
12. [Logical Indexing and `find()`](#12-logical-indexing-and-find)
13. [The `%` Comment and Semicolon Rule](#13-the--comment-and-semicolon-rule)
14. [Common Built-in Functions](#14-common-built-in-functions)
15. [How the Power Flow Scripts Chain Together](#15-how-the-power-flow-scripts-chain-together)
16. [Quick Reference: MATLAB → Python Translation Table](#16-quick-reference-matlab--python-translation-table)

---

## 1. The Basics

### `.m` files are either scripts or functions

A file with no `function` declaration at the top is a **script** — it runs top-to-bottom
and shares the caller's workspace (like a Python file run with `exec()`).

A file that starts with `function` is a **function** — it has its own scope.

```matlab
% script: ieee_4bus_3ph_3_4wire.m — just statements, no function header
clear all;
kVA_base = 2000e3;
```

```matlab
% function: cdparam.m — has a header, inputs, and outputs
function [A_C B_C K_C E0_C A_D B_D K_D E0_D] = cdparam(Efull_C, Eexp_C, ...)
```

### Running one script from another

Calling a script by name (without parentheses) runs it in the **same workspace**
— all variables it creates become available to the caller. This is how the power
flow chain works:

```matlab
% nrci3ph4w.m — calls three scripts by name, inheriting their variables
ieee_4bus_3ph_3_4wire    % defines bus{}, line{}, Y matrices, base values
ymat_3ph3_4w             % reads those variables, builds Y matrix → G, B
for iter = 1:50
    curr_mm_3p3_4w       % reads G, B, busV, busA → updates them in-place
    if (max(abs(dI)) <= 1e-6)
        break;
    end
end
```

**Python equivalent:** Roughly `exec(open('ieee_4bus_3ph_3_4wire.m').read())`,
but in Python you'd use function calls and return values instead.

---

## 2. Variables and Types

### No declarations needed

```matlab
x = 5;          % integer-like (actually double by default)
y = 3.14;       % float
z = 'hello';    % string
flag = true;    % boolean
```

All numeric variables are **double-precision floating point** by default —
there is no `int`, `float`, `double` distinction you need to think about.

### Everything is a matrix

Even a scalar is a 1×1 matrix. A "vector" is a 1×N or N×1 matrix.

```matlab
kVA_base = 2000e3;          % scalar (1×1)
V0 = [1.0; 1.0; 1.0; 0.0]; % column vector (4×1) — semicolons separate rows
ang0 = [0.0, -2*pi/3, 2*pi/3, 0.0];  % row vector (1×4) — commas separate cols
```

**Python analogy:** Think of every variable as a NumPy array. A scalar is
`np.array(5.0)`.

---

## 3. Indexing — The #1 Gotcha

### MATLAB indices start at 1, not 0

This is the single most important difference. Every array, matrix, and cell
access uses base-1 indexing.

```matlab
% From curr_mm_3p3_4w.m
for b = 1:tot_bus           % b goes 1, 2, 3, ... tot_bus (inclusive)
    for p = 1:4
        n0 = 4*(b-1) + p   % convert to flat index: bus b, phase p
    end
end
```

**Python translation of the same index arithmetic:**
```python
for b in range(tot_bus):        # b goes 0, 1, 2, ... tot_bus-1
    for p in range(4):
        n0 = 4*b + p            # same position, no -1 correction needed
```

The MATLAB pattern `4*(b-1)+p` always becomes `4*b + p` in Python when you
switch to 0-based indexing. This is everywhere in this codebase.

### Colon ranges are inclusive on both ends

```matlab
1:8      % [1, 2, 3, 4, 5, 6, 7, 8] — both ends included
1:2:10   % [1, 3, 5, 7, 9]          — step of 2
```

Python equivalent: `range(1, 9)` for the first (note: Python excludes the end).

### Slicing with a range

```matlab
A(2:5)          % elements 2 through 5 of vector A
A(1:3, 1:3)     % top-left 3×3 submatrix of matrix A
A(end)          % last element (keyword 'end' = last index)
A(end-1:end)    % last two elements
```

---

## 4. Matrices and Vectors

### Creating matrices

Spaces or commas separate columns; semicolons separate rows:

```matlab
% From ieee_4bus_3ph_3_4wire.m
z_3w_3ph = [...
    0.4013+1i*1.4133  0.0953+1i*0.8515  0.0953+1i*0.7266;
    0.0953+1i*0.8515  0.4013+1i*1.4133  0.0953+1i*0.7802;
    0.0953+1i*0.7266  0.0953+1i*0.7802  0.4013+1i*1.4133;
];
```

**Python equivalent:**
```python
z_3w_3ph = np.array([
    [0.4013+1j*1.4133, 0.0953+1j*0.8515, 0.0953+1j*0.7266],
    ...
])
```

### Useful matrix constructors

```matlab
zeros(4, 4)      % 4×4 zero matrix       → np.zeros((4,4))
ones(4, 1)       % 4×1 column of ones    → np.ones((4,1))
eye(4)           % 4×4 identity          → np.eye(4)
diag([a b c d])  % diagonal matrix       → np.diag([a,b,c,d])
```

### Transpose

```matlab
A'       % conjugate transpose (Hermitian) for complex matrices
A.'      % plain transpose, no conjugation
```

**Python:** `A.conj().T` vs `A.T`

### Concatenation

```matlab
% horizontal (side by side): same number of rows
C = [A  B]         % or horzcat(A, B)
% vertical (stacked): same number of columns
C = [A; B]         % or vertcat(A, B)
```

**Python:** `np.hstack([A, B])` / `np.vstack([A, B])`

### Deleting rows or columns

```matlab
% From curr_mm_3p3_4w.m — delete rows and cols in-place
IJAC(vanish_ind, :) = [];   % delete rows listed in vanish_ind
IJAC(:, vanish_ind) = [];   % delete those cols
```

**Python:** `np.delete(IJAC, vanish_ind, axis=0)` and `axis=1`.
Note: MATLAB does this destructively in-place; NumPy returns a new array.

---

## 5. Arithmetic Operators

### Element-wise vs matrix operations

This distinction does not exist in Python — NumPy `*` is always element-wise,
and `@` is matrix multiplication. In MATLAB:

| Operator | MATLAB meaning                  | Python equivalent    |
|----------|---------------------------------|----------------------|
| `A * B`  | **Matrix** multiplication       | `A @ B`              |
| `A .* B` | Element-wise multiplication     | `A * B`              |
| `A / B`  | Matrix right-division: `A*inv(B)` | `A @ np.linalg.inv(B)` |
| `A ./ B` | Element-wise division           | `A / B`              |
| `A ^ n`  | Matrix power                    | `np.linalg.matrix_power(A, n)` |
| `A .^ n` | Element-wise power              | `A ** n`             |
| `A \ b`  | **Left-division** (solve `Ax=b`) | `np.linalg.solve(A, b)` |

The dot prefix (`.`) switches any operator to element-wise. This appears
constantly in `cdparam.m`:

```matlab
B_C = 3 ./ Qexp_C;            % element-wise divide (Qexp_C is a vector)
K_C = (...) .* (Q - Qnom_C);  % element-wise multiply
```

### The left-division operator `\`

This is MATLAB's most powerful convenience operator. `A \ b` means "solve the
linear system Ax = b" — it picks the best algorithm (LU, QR, etc.) automatically.

```matlab
% From curr_mm_3p3_4w.m — the Newton-Raphson solve step
dV = IJAC \ dI;     % solve IJAC * dV = dI for dV
```

**Python:** `dV = np.linalg.solve(IJAC, dI)`

---

## 6. Control Flow

### `for` loop

```matlab
for b = 1:tot_bus       % iterate over a range
    ...
end

for ii = 1:length(pv_ind)    % length() = Python len()
    ...
end
```

The loop variable iterates over **the columns** of whatever comes after `=`.
So `for x = [3 7 2]` gives x = 3, then 7, then 2.

### `while` loop

```matlab
while condition
    ...
end
```

### `if / elseif / else`

```matlab
% From SoC_ref_gen.m
if SoC_ref_calc <= CincSoC_ref
    Ibatt_ref_calc = Ibatt_ref_calc + (omega_Chg_PEV / (60*tsc));
elseif SoC_ref_calc >= CdecSoC_ref
    Ibatt_ref_calc = Ibatt_ref_calc - (omega_Chg_PEV / (60*tsc));
end
```

Note: `elseif` is one word (Python uses `elif`; Java uses `else if`).

### `break` and `continue`

Same as Python/Java. `break` exits the innermost loop; `continue` skips to the
next iteration.

```matlab
% From nrci3ph4w.m
for iter = 1:50
    curr_mm_3p3_4w;
    if (max(abs(dI)) <= 1e-6)
        break;
    end
end
```

---

## 7. Functions

### Defining a function

```matlab
function [out1, out2, out3] = myFunc(in1, in2)
    out1 = in1 + in2;
    out2 = in1 .* in2;
    out3 = out1 + out2;
end
```

Key differences from Python/Java:
- **Return values** are listed at the top in `[out1, out2]` — not a `return`
  statement at the end.
- The function body assigns to those output variable names and they are
  automatically returned when the function ends.
- A `return` statement can exit early (like `return` in Java/Python void methods).

### Calling a function

```matlab
[A_C, B_C, K_C, E0_C, A_D, B_D, K_D, E0_D] = cdparam(Efull_C, Eexp_C, ...);
```

You can ignore trailing outputs:
```matlab
[A_C, ~, K_C] = myFunc(x, y);   % ~ discards the second output
```

### Anonymous functions (lambda)

```matlab
f = @(x) x.^2 + 1;     % equivalent to Python: f = lambda x: x**2 + 1
f(3)                    % returns 10
```

---

## 8. Scripts vs Functions vs the Workspace

### The workspace is a global variable store

When running interactively or running scripts, all variables live in the
**base workspace** — a shared namespace. Scripts read from and write to it.

`clear all` wipes everything. `clear x y` removes specific variables.

```matlab
% ieee_4bus_3ph_3_4wire.m begins with:
clear global;
clear all;
```

### How the power flow files share state

Because all four files are **scripts** (not functions), they communicate through
the workspace. Each script reads variables set by previous scripts and adds its
own:

```
ieee_4bus_3ph_3_4wire.m  → creates: bus{}, line{}, kVA_base, Trf_Z, y_line_12, ...
         ↓ (workspace shared)
ymat_3ph3_4w.m           → reads:   bus{}, line{}
                         → creates: Y, G, B, busV, busA, busPL, ...
         ↓
curr_mm_3p3_4w.m         → reads:   Y, G, B, busV, busA, busPL, ...
                         → updates: busV, busA, busPZ, busQZ, ...
                         → creates: dI (convergence metric)
```

This is the MATLAB equivalent of Python's "passing a shared mutable dict to
every function." The Python conversion (`python_conversion_psa/`) replaces this
with an explicit `state` dict passed between functions.

---

## 9. Cell Arrays

### What they are

A cell array `{}` is MATLAB's heterogeneous container — like a Python `list`
where each element can be any type (matrix, string, number, another cell array).

```matlab
% From ieee_4bus_3ph_3_4wire.m — the bus table is a cell array
bus = {
    [1]  [1.00;1.00;1.00;0.00]  [0.00;-(2*pi/3);(2*pi/3);0.00]  0.0*[1.80;...]  ...  [1];
    [2]  [1.00;1.00;1.00;0.00]  [0.00;-(2*pi/3);(2*pi/3);0.00]  0.0*[1.80;...]  ...  [3];
    ...
};
```

Each row is a bus record. Each column is a field (bus number, voltage magnitudes,
voltage angles, P loads, Q loads, ..., bus type).

### Accessing elements

```matlab
% () gives a sub-cell-array (a cell, not its content)
bus(2, 1)        % returns a 1×1 cell containing the value

% {} extracts the actual content
bus{2, 1}        % returns the actual matrix/scalar inside
```

**Python analogy:** `{}` access is like `list[i]`; `()` access is like getting a
sublist.

### `cell2mat`

Converts a cell array of same-type matrices into one concatenated matrix:

```matlab
% From ymat_3ph3_4w.m
busV = cell2mat(bus(:, 2));   % stack all voltage vectors into one column vector
busA = cell2mat(bus(:, 3));   % stack all angle vectors
```

**Python equivalent:** `np.concatenate([b['V'] for b in buses])`

### `:` as "all rows" or "all columns"

```matlab
bus(:, 1)    % all rows, column 1 → bus numbers
bus(2, :)    % row 2, all columns → all fields of bus 2
```

**Python:** `bus[:, 0]` (but with 0-based index).

---

## 10. Complex Numbers

### Imaginary unit

MATLAB uses `1i` or `1j` (either works). The repository uses both:

```matlab
Trf_Z = 0.01 + 0.06i;                  % imaginary unit appended directly
z = 0.4013 + 1i*1.4133;                % explicit multiply form
V = busV .* exp(1i * busA);            % Euler's formula
```

**Python:** Use `1j` — `0.01 + 0.06j`, `np.exp(1j * busA)`.

### Complex operations

```matlab
abs(V)      % magnitude  → np.abs(V)
angle(V)    % phase angle in radians → np.angle(V)
real(V)     % real part  → V.real
imag(V)     % imaginary part → V.imag
conj(V)     % complex conjugate → np.conj(V)  or  V.conj()
```

From `lineflow_3p4w.m`:
```matlab
Vsend = Vsend_mag .* exp(1i * Vsend_ang);    % polar to rectangular
S_from = cell2mat(Vsend) .* conj(I_from);    % complex power S = V * I*
```

---

## 11. Linear Algebra Operations

### Matrix inverse

```matlab
inv(A)         % explicit inverse → np.linalg.inv(A)
```

But prefer `A \ b` over `inv(A) * b` — it is faster and more numerically stable.

### Solving linear systems

```matlab
x = A \ b     % solve Ax = b → np.linalg.solve(A, b)
x = b / A     % solve xA = b → np.linalg.solve(A.T, b.T).T
```

From `curr_mm_3p3_4w.m`:
```matlab
dV = IJAC \ dI;     % the core Newton-Raphson step
```

### Diagonal matrix from a vector

```matlab
diag([Trf_Y  Trf_Y  Trf_Y  Trf_Y])    % 4×4 diagonal matrix
```

**Python:** `np.diag([Trf_Y, Trf_Y, Trf_Y, Trf_Y])`

### Getting diagonal of a matrix

```matlab
d = diag(Y)    % extracts the main diagonal as a column vector
```

**Python:** `d = np.diag(Y)`

The same function does double duty — creation and extraction depending on input.

### The `B / ZB` shorthand (right-division)

From `yprim.m`:
```matlab
Yl = B / ZB * transpose(B);    % equivalent to B * inv(ZB) * B'
```

**Python:** `Yl = B @ np.linalg.inv(ZB) @ B.T`

---

## 12. Logical Indexing and `find()`

### `find()` returns indices of true elements

```matlab
% From ymat_3ph3_4w.m
zyind = find(dY == 0);        % indices where diagonal is zero

pq_ind  = find(bus_typ_ind == 3);   % PQ buses
pv_ind  = find(bus_typ_ind == 2);   % PV buses
swing_ind = find(bus_typ_ind == 1); % slack bus
```

**Python:** `np.where(dY == 0)[0]` — note the `[0]` to get the array from the tuple.

### Logical indexing

```matlab
A(A > 0)         % all elements of A greater than zero
A(logical_mask)  % select elements where mask is true
```

### `isempty()`

```matlab
if isempty(pv_ind) == 0      % if pv_ind is not empty
    ...
end
```

**Python:** `if len(pv_ind) > 0:` or `if pv_ind.size > 0:`

---

## 13. The `%` Comment and Semicolon Rule

### Comments

`%` starts a line comment (like Python's `#` or Java's `//`).
There are no block comments in MATLAB (`%{ ... %}` exists but is rarely used).

### The semicolon suppresses output

Without a semicolon, MATLAB **prints the result** to the console:

```matlab
x = 5          % prints: x = 5
x = 5;         % silent — no output
```

In scripts with large matrices, a missing `;` will flood the console.
All assignment lines in production code should end with `;`.

The main script `nrci3ph4w.m` prints the iteration count deliberately:
```matlab
iter            % no semicolon — intentionally prints iter to console
```

### Line continuation

`...` continues a statement on the next line (Python uses `\` or implicit
continuation inside `[]`):

```matlab
bus = {
    [1]  [1.00;1.00;1.00;0.00]  ...   % continues on next line
         [0.00;-(2*pi/3);(2*pi/3);0.00];
};
```

---

## 14. Common Built-in Functions

| MATLAB | Python (NumPy) | Description |
|--------|---------------|-------------|
| `zeros(m,n)` | `np.zeros((m,n))` | Zero matrix |
| `ones(m,n)` | `np.ones((m,n))` | All-ones matrix |
| `eye(n)` | `np.eye(n)` | Identity matrix |
| `length(x)` | `len(x)` or `x.shape[0]` | Length of longest dimension |
| `size(A)` | `A.shape` | Dimensions tuple |
| `size(A,1)` | `A.shape[0]` | Number of rows |
| `numel(A)` | `A.size` | Total element count |
| `sum(A)` | `np.sum(A, axis=0)` | Column-wise sum |
| `sum(A,2)` | `np.sum(A, axis=1)` | Row-wise sum |
| `max(abs(x))` | `np.max(np.abs(x))` | Max of absolute values |
| `abs(x)` | `np.abs(x)` | Absolute value / magnitude |
| `real(x)` | `x.real` | Real part |
| `imag(x)` | `x.imag` | Imaginary part |
| `angle(x)` | `np.angle(x)` | Phase angle |
| `conj(x)` | `np.conj(x)` | Complex conjugate |
| `exp(x)` | `np.exp(x)` | Exponential |
| `sqrt(x)` | `np.sqrt(x)` | Square root |
| `inv(A)` | `np.linalg.inv(A)` | Matrix inverse |
| `A \ b` | `np.linalg.solve(A,b)` | Solve linear system |
| `diag(v)` | `np.diag(v)` | Make diagonal matrix |
| `diag(A)` | `np.diag(A)` | Extract diagonal |
| `find(cond)` | `np.where(cond)[0]` | Indices of true elements |
| `cell2mat(C)` | `np.concatenate(...)` | Flatten cell array to matrix |
| `horzcat(A,B)` | `np.hstack([A,B])` | Horizontal concatenation |
| `vertcat(A,B)` | `np.vstack([A,B])` | Vertical concatenation |
| `isempty(x)` | `len(x)==0` | True if empty |
| `mod(a,b)` | `a % b` | Modulo |
| `floor(x)` | `np.floor(x)` | Floor |
| `ceil(x)` | `np.ceil(x)` | Ceiling |
| `cumsum(x)` | `np.cumsum(x)` | Cumulative sum |
| `pi` | `np.pi` | π |
| `acos(x)` | `np.arccos(x)` | Inverse cosine |
| `tan(x)` | `np.tan(x)` | Tangent |
| `transpose(A)` | `A.T` | Non-conjugate transpose |

---

## 15. How the Power Flow Scripts Chain Together

This section maps out the data flow across the four main files so you can
navigate the code without getting lost.

```
┌─────────────────────────────────────────────────────────┐
│  ieee_4bus_3ph_3_4wire.m  (data definition script)     │
│                                                         │
│  Defines:                                               │
│   • Base values: kVA_base, Z_baseH, Z_baseL             │
│   • Transformer: Trf_Z, Trf_Y, LTC_Y, trf_Y_4x4        │
│   • bus{} cell array  — rows=buses, cols=fields         │
│     Col 1:  bus number                                  │
│     Col 2:  |V| init (4×1: a,b,c,n)                    │
│     Col 3:  angle init (4×1)                            │
│     Col 4:  PL constant-power load (4×1)                │
│     Col 5:  QL                                          │
│     Col 6:  PG generation (4×1)                         │
│     Col 7:  QG                                          │
│     Col 8:  PZ constant-impedance load                  │
│     Col 9:  QZ                                          │
│     Col 10: PI constant-current load                    │
│     Col 11: QI                                          │
│     Col 12: SR (reserved)                               │
│     Col 13: SI (reserved)                               │
│     Col 14: bus type (1=slack, 2=PV, 3=PQ)             │
│     Col 15: DGP (distributed generation P)             │
│     Col 16: DGQ                                         │
│   • line{} cell array — rows=branches, cols=fields      │
│     Col 1: from bus number                              │
│     Col 2: to bus number                                │
│     Col 3: Y_series (4×4 admittance matrix)             │
│     Col 4: Y_shunt/2 (4×4 charging admittance)         │
│   • y_line_12, y_line_23, y_line_34 (4×4 matrices)     │
│   • ind_3w_bus: bus numbers with floating neutral       │
└─────────────────────────────────────────────────────────┘
                          ↓  (workspace inherited)
┌─────────────────────────────────────────────────────────┐
│  ymat_3ph3_4w.m  (Y-matrix builder script)             │
│                                                         │
│  Reads:  bus{}, line{}, LDM, p_P, q_P, ...             │
│  Creates:                                               │
│   • busV, busA       flat voltage magnitude/angle       │
│                      vectors (4*n_bus × 1)              │
│   • busPL, busQL, busPZ, busQZ, busPI, busQI  load vecs │
│   • busDGP, busDGQ   DG vectors                         │
│   • Y  (4*n_bus × 4*n_bus) nodal admittance matrix      │
│   • G = real(Y),  B = imag(Y)                           │
│   • pq_ind, pv_ind, swing_ind  bus type index vectors   │
│   • aaa,bbb,ccc,ddd  phase index helpers                │
│     aaa = [1, 5, 9, 13, ...]  (phase-a global indices) │
└─────────────────────────────────────────────────────────┘
                          ↓  (workspace inherited)
┌─────────────────────────────────────────────────────────┐
│  curr_mm_3p3_4w.m  (NR iteration script)               │
│                                                         │
│  Reads:  all of the above                               │
│  Each call performs ONE Newton-Raphson iteration:       │
│   1. V = busV .* exp(1i*busA)  (complex voltages)       │
│   2. Compute I_spec from P/Q specs (phase-to-neutral)   │
│   3. Compute current mismatch: dIr, dIm = I - Y*V      │
│   4. Build IJAC (current injection Jacobian, 8*n_bus)   │
│   5. Remove slack and floating-neutral rows/cols        │
│   6. dV = IJAC \ dI  (solve for corrections)           │
│   7. Update busV, busA                                  │
│   8. Update ZIP load vectors (busPZ, busQZ, busPI, ...) │
│  Outputs (in workspace):                                │
│   • dI  — mismatch vector (used for convergence check)  │
└─────────────────────────────────────────────────────────┘
                          ↓  (workspace inherited)
┌─────────────────────────────────────────────────────────┐
│  nrci3ph4w.m  (main loop)                              │
│                                                         │
│  for iter = 1:50                                        │
│      curr_mm_3p3_4w;                                    │
│      if max(abs(dI)) <= 1e-6; break; end                │
│  end                                                    │
└─────────────────────────────────────────────────────────┘
```

### The 4-wire phase indexing convention

Throughout this codebase, each bus has **4 scalar DOFs** (degrees of freedom):
phases a, b, c, and neutral (n). Variables are stored as flat column vectors
of length `4 * n_bus`.

```
Index in flat vector:
  Bus 1, phase a → index  1  (MATLAB) /  0  (Python)
  Bus 1, phase b → index  2           /  1
  Bus 1, phase c → index  3           /  2
  Bus 1, neutral → index  4           /  3
  Bus 2, phase a → index  5           /  4
  ...
  Bus b, phase p → index  4*(b-1)+p   /  4*(b-1)+(p-1)
```

The helper vectors `aaa`, `bbb`, `ccc`, `ddd` give the flat indices of each
phase across all buses at once:

```matlab
aaa = 4*((1:tot_bus)-1) + 1;   % [1, 5,  9, 13, ...] phase-a indices
bbb = 4*((1:tot_bus)-1) + 2;   % [2, 6, 10, 14, ...] phase-b indices
ccc = 4*((1:tot_bus)-1) + 3;   % phase-c
ddd = 4*((1:tot_bus)-1) + 4;   % neutral

% Usage example:
busV(aaa)    % phase-a voltage magnitudes for all buses (as a row vector)
sum(busPL(aaa))  % total phase-a active load across all buses
```

---

## 16. Quick Reference: MATLAB → Python Translation Table

| Concept | MATLAB | Python |
|---------|--------|--------|
| Imaginary unit | `1i` or `1j` | `1j` |
| Indexing | starts at **1** | starts at **0** |
| Range (inclusive) | `a:b` → `[a, a+1, ..., b]` | `range(a, b+1)` |
| Array literal | `[1 2; 3 4]` | `np.array([[1,2],[3,4]])` |
| Matrix multiply | `A * B` | `A @ B` |
| Element-wise multiply | `A .* B` | `A * B` |
| Element-wise divide | `A ./ B` | `A / B` |
| Element-wise power | `A .^ n` | `A ** n` |
| Solve `Ax=b` | `A \ b` | `np.linalg.solve(A, b)` |
| Matrix inverse | `inv(A)` | `np.linalg.inv(A)` |
| Delete rows | `A(idx,:) = []` | `np.delete(A, idx, axis=0)` |
| Find nonzero | `find(cond)` | `np.where(cond)[0]` |
| Cell array | `{...}` | `list` or `dict` |
| Extract cell | `C{i,j}` | `C[i][j]` |
| Flatten cell→matrix | `cell2mat(C)` | `np.concatenate(...)` |
| Script calling script | `scriptname;` | `exec(open(...).read())` — use functions instead |
| Multiple return | `[a,b] = f(x)` | `a, b = f(x)` |
| Discard output | `[~, b] = f(x)` | `_, b = f(x)` |
| Print variable | `x` (no semicolon) | `print(x)` |
| Suppress output | `x = 5;` | (default — no print) |
| Comment | `% comment` | `# comment` |
| Line continuation | `...` | `\` or implicit in `[]` |
| Length of array | `length(A)` | `len(A)` or `A.shape[0]` |
| Size of matrix | `size(A)` | `A.shape` |
| Modulo | `mod(a,b)` | `a % b` |
| Absolute value | `abs(x)` | `np.abs(x)` |
| Phase angle | `angle(x)` | `np.angle(x)` |
| Cumulative sum | `cumsum(x)` | `np.cumsum(x)` |
| `π` | `pi` | `np.pi` |
| `arccos` | `acos(x)` | `np.arccos(x)` |
| Boolean AND | `&&` (scalar), `&` (array) | `and`, `&` |
| Boolean OR | `\|\|` (scalar), `\|` (array) | `or`, `\|` |

---

*This file was generated from the `.m` sources in this repository.
The Python conversion lives in `python_conversion_psa/`.*
