import csv
import re

# Read the raw CSV
with open("substations.csv", "r", encoding="utf-8") as f:
    content = f.read()

# Split into lines
lines = content.split("\n")

# Define target header columns
target_header = [
    "SN",
    "Name of Grid Substation",
    "Operation Zone",
    "Transformer Detail (MVA)",
    "Total Capacity (MVA)",
    "Owership",
    "Grid Circle",
    "Voltage Level",
]

# Process the data
processed_rows = []
i = 0

while i < len(lines):
    line = lines[i].strip()

    # Skip empty lines and metadata
    if not line or line.startswith(",,,") or "QF-SPL-01" in line or "Page" in line:
        i += 1
        continue

    # Skip header rows (lines that have "Name of Grid" or start with "SN,")
    if "Name of Grid" in line or (
        line.startswith("SN,") and "Operation" in lines[i + 1]
        if i + 1 < len(lines)
        else False
    ):
        # Skip multi-line header
        i += 1
        while i < len(lines) and (
            "Zone" in lines[i] or "Detail" in lines[i] or "Total" in lines[i]
        ):
            i += 1
        continue

    # Check if this is a data row (starts with a digit)
    if line and line[0].isdigit():
        row_data = [line]
        i += 1

        # Collect continuation lines (lines that don't start with a digit)
        while (
            i < len(lines)
            and lines[i].strip()
            and not lines[i].strip()[0].isdigit()
            and "Name of Grid" not in lines[i]
            and "Page" not in lines[i]
            and ",,," not in lines[i]
        ):
            row_data.append(lines[i].strip())
            i += 1

        # Join the multi-line row
        full_row = " ".join(row_data)
        processed_rows.append(full_row)
    else:
        i += 1

# Parse the rows using CSV reader to handle quoted fields properly
parsed_data = []
for row_line in processed_rows:
    try:
        # Use CSV reader to properly parse the line
        reader = csv.reader([row_line])
        for row in reader:
            parsed_data.append(row)
    except:
        pass

# Clean up the data
cleaned_data = []
for row in parsed_data:
    if not row or all(not cell.strip() for cell in row):
        continue

    # Clean each cell: remove newlines, trim whitespace, handle page break remnants
    cleaned_row = []
    for i, cell in enumerate(row):
        # Remove newlines and excess whitespace
        cell = cell.replace("\n", " ").strip()
        # Remove page break references
        cell = re.sub(r"Pag\s+e\s+\d+\s+of\s+\d+", "", cell).strip()
        cell = re.sub(r"\s+", " ", cell)  # Normalize spaces
        cleaned_row.append(cell)

    # Remove trailing empty cells
    while cleaned_row and not cleaned_row[-1]:
        cleaned_row.pop()

    if cleaned_row:
        cleaned_data.append(cleaned_row)

# Ensure we have the correct number of columns (8 columns)
formatted_data = []
for row in cleaned_data:
    # Pad or trim to 8 columns
    while len(row) < 8:
        row.append("")
    row = row[:8]
    formatted_data.append(row)

# Write to formatted CSV
with open("substations-formatted.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    # Write header
    writer.writerow(target_header)
    # Write data rows
    writer.writerows(formatted_data)

print(f"Processed {len(formatted_data)} data rows")
print("Created substations-formatted.csv")
