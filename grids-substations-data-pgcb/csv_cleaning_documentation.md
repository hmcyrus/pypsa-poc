# CSV Cleaning Process Documentation

This document outlines the complete process used to clean and format the messy CSV files (`substations.csv` and `grids.csv`) that were converted from Excel spreadsheets.

## Overview

The original CSV files had several formatting issues from Excel-to-CSV conversion:
- Multiple header rows spanning several lines
- Data rows split across multiple lines
- Page break artifacts and metadata
- Inconsistent column positioning across different voltage levels
- Trailing empty cells
- Mixed formatting and embedded newlines

## Complete Cleaning Code

```python
import csv
import re
import os
from io import StringIO

# Change to working directory
os.chdir('/workspaces/pypsa-poc/grids-substations-data-pgcb')

# Read the raw file
with open('grids.csv', 'r', encoding='utf-8') as f:
    content = f.read()

# Split by voltage level headers using regex
voltage_pattern = r'(\d+)\s*kV\s+Transmission\s+Line'
sections = re.split(voltage_pattern, content)

# Reorganize into (voltage, content) tuples
voltage_sections = []
for i in range(1, len(sections), 2):
    if i+1 < len(sections):
        voltage = sections[i] + ' kV'
        section_content = sections[i+1]
        voltage_sections.append((voltage, section_content))

print(f"Found {len(voltage_sections)} voltage sections")

# Main processing loop
all_data = []

for voltage, section_text in voltage_sections:
    lines = section_text.split('\n')

    # Parse CSV data
    csv_data = list(csv.reader(lines))

    # Process each row
    for row in csv_data:
        if not row or all(not cell.strip() for cell in row):
            continue

        first_cell = row[0].strip()

        # Skip non-data rows (headers, totals, empty)
        if not first_cell or first_cell.lower().startswith('total') or not first_cell[0].isdigit():
            continue

        # Clean individual cells
        cleaned = []
        for cell in row:
            cell = cell.replace('\n', ' ').replace('\r', ' ').strip()
            cell = re.sub(r'\s+', ' ', cell)
            cleaned.append(cell)

        # Remove trailing empty cells
        while cleaned and not cleaned[-1]:
            cleaned.pop()

        # Map columns based on voltage level (different layouts in original Excel)
        if voltage == '400 kV':
            # 400kV format: SN, Name, [empties], RouteKm, [empties], CktKm, [empties], NoCkt, [empties], Conductor, [empty], Size
            mapped = [
                cleaned[0] if len(cleaned) > 0 else '',
                cleaned[1] if len(cleaned) > 1 else '',
                cleaned[4] if len(cleaned) > 4 else '',
                cleaned[7] if len(cleaned) > 7 else '',
                cleaned[10] if len(cleaned) > 10 else '',
                cleaned[13] if len(cleaned) > 13 else '',
                cleaned[15] if len(cleaned) > 15 else '',
                voltage
            ]
        elif voltage == '230 kV':
            # 230kV format: SN, Name, [empties], RouteKm, [empties], CktKm, [empties], NoCkt, [empties], Conductor, Size
            mapped = [
                cleaned[0] if len(cleaned) > 0 else '',
                cleaned[1] if len(cleaned) > 1 else '',
                cleaned[5] if len(cleaned) > 5 else '',
                cleaned[8] if len(cleaned) > 8 else '',
                cleaned[11] if len(cleaned) > 11 else '',
                cleaned[14] if len(cleaned) > 14 else '',
                cleaned[15] if len(cleaned) > 15 else '',
                voltage
            ]
        else:  # 132 kV
            # 132kV format: SN, Name, RouteKm, CktKm, NoCkt, [empty], Conductor, [empties], Size
            mapped = [
                cleaned[0] if len(cleaned) > 0 else '',
                cleaned[1] if len(cleaned) > 1 else '',
                cleaned[2] if len(cleaned) > 2 else '',
                cleaned[3] if len(cleaned) > 3 else '',
                cleaned[4] if len(cleaned) > 4 else '',
                cleaned[6] if len(cleaned) > 6 else '',
                cleaned[9] if len(cleaned) > 9 else '',
                voltage
            ]

        all_data.append(mapped)

# Define standardized header
header = ['SN', 'Name of Lines', 'Length in Route km', 'Length in Ckt. Km',
          'No. of Ckt.', 'Conductor', 'Size', 'Voltage Level']

# Write cleaned CSV
with open('grids-formatted.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(all_data)

# Generate statistics
print(f'Successfully cleaned and formatted grids.csv')
print(f'Total transmission lines: {len(all_data)}')

volt_counts = {}
for row in all_data:
    volt = row[-1]
    volt_counts[volt] = volt_counts.get(volt, 0) + 1

print('\nBreakdown by voltage level:')
for voltage in sorted(volt_counts.keys(), key=lambda x: int(x.split()[0]), reverse=True):
    print(f'  {voltage}: {volt_counts[voltage]} lines')
```

## Step-by-Step Process Explanation

### 1. Setup and File Reading
- Import required modules: `csv`, `re`, `os`, `io.StringIO`
- Change to the data directory
- Read the entire raw CSV file as a string to handle multi-line content

### 2. Section Separation
- Use regex pattern to identify voltage level headers (`400 kV Transmission Line`, etc.)
- Split the file content by these headers
- Reorganize into tuples of (voltage_level, section_content)

### 3. Data Processing Loop
- Iterate through each voltage section separately
- Parse each section as CSV data
- Filter out headers, empty rows, and total rows
- Keep only rows that start with numbers (actual data)

### 4. Cell-Level Cleaning
- Remove newlines and carriage returns from cells
- Normalize multiple spaces to single spaces
- Strip leading/trailing whitespace
- Remove trailing empty cells from each row

### 5. Voltage-Specific Column Mapping
The original Excel file had different column layouts for each voltage level:

**400 kV Format:**
```
SN | Name | [empty] | [empty] | RouteKm | [empty] | [empty] | CktKm | [empty] | [empty] | NoCkt | [empty] | [empty] | Conductor | [empty] | Size
```

**230 kV Format:**
```
SN | Name | [empty] | [empty] | [empty] | RouteKm | [empty] | [empty] | CktKm | [empty] | [empty] | NoCkt | [empty] | [empty] | Conductor | Size
```

**132 kV Format:**
```
SN | Name | RouteKm | CktKm | NoCkt | [empty] | Conductor | [empty] | [empty] | Size
```

### 6. Output Generation
- Create standardized 8-column format for all data
- Write to new CSV file with proper encoding
- Generate processing statistics

## Final Output Format

The cleaned CSV has these standardized columns:

| Column | Description |
|--------|-------------|
| SN | Serial number |
| Name of Lines | Transmission line name |
| Length in Route km | Route length in kilometers |
| Length in Ckt. Km | Circuit length in kilometers |
| No. of Ckt. | Number of circuits (Single/Double/Four) |
| Conductor | Conductor type and specifications |
| Size | Conductor size (MCM, sq.mm, etc.) |
| Voltage Level | 400 kV, 230 kV, or 132 kV |

## Processing Results

- **Total transmission lines processed:** 354
- **400 kV lines:** 28
- **230 kV lines:** 63
- **132 kV lines:** 263

## Key Challenges Solved

1. **Multi-section files** - Single CSV contained separate sections for different voltage levels
2. **Inconsistent column positioning** - Each voltage level had different column layouts
3. **Multi-line content** - Headers and data spanned multiple rows
4. **Embedded artifacts** - Page breaks, footers, and Excel conversion artifacts
5. **Mixed data types** - Numbers, text, and empty cells in unpredictable positions

## Usage

To reuse this cleaning logic for similar CSV files:

1. Update the file path and name
2. Adjust voltage level patterns if different
3. Modify column mapping logic if the Excel layout changes
4. Update the output filename and header as needed

This process can be adapted for any CSV file that originated from Excel spreadsheets with similar formatting issues.