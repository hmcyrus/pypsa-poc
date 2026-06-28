#
# Runs the data-building scripts in the required order.
# See src/data-script-execution-order.txt for the canonical ordering.
#
# Order:
#   1. buses + lines        (must run first)
#   2. generators, loads, transformers, links (any order)
#   3. bus supplement       (must run last)

$ErrorActionPreference = "Stop"

# Run from the repo root regardless of where this is invoked from.
Set-Location -Path $PSScriptRoot

$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

function Invoke-Step {
    param([string]$Script)
    Write-Host ">>> $Python $Script"
    & $Python $Script
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed ($LASTEXITCODE): $Script"
    }
}

# 1. buses + lines (must be first)
Invoke-Step "src/line-bus-processor.py"

# 2. generators / loads / transformers / links (any order)
Invoke-Step "src/generator_builder.py"
Invoke-Step "src/load_builder.py"
Invoke-Step "src/transformer_builder.py"
Invoke-Step "src/link_builder.py"

# 3. augment buses.csv (must be last)
Invoke-Step "src/bus_supplement.py"

Write-Host ">>> Pipeline complete."
