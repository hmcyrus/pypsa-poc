# CSV Cleaning Process Documentation

This document outlines the complete process used to clean and format the messy CSV files (`substations.csv` and `grids.csv`) that were converted from Excel spreadsheets.

## Overview

The original CSV files had several formatting issues from Excel-to-CSV conversion:
- Multiple header rows spanning several lines
- Data rows split across multiple lines
- Page break artifacts and metadata
- Inconsistent column positioning across different voltage levels (grids.csv)
- Trailing empty cells
- Mixed formatting and embedded newlines

## Two Separate Cleaning Processes

This session involved cleaning two different CSV files with different challenges:

### 1. Substations CSV Cleaning (Simpler)
**File:** `substations.csv` → `substations-formatted.csv`
**Issues:** Multi-line headers, page breaks, multi-line data rows
**Result:** 251 data rows, 8 columns

### 2. Grids CSV Cleaning (Complex)
**File:** `grids.csv` → `grids-formatted.csv`
**Issues:** Multiple voltage sections, inconsistent column layouts, complex multi-line content
**Result:** 354 data rows, 8 columns (28×400kV, 63×230kV, 263×132kV)

## Substations CSV Cleaning Code

```python
import csv
import re
import os
from io import StringIO

os.chdir('/workspaces/pypsa-poc/grids-substations-data-pgcb')

# Read the raw CSV
with open('substations.csv', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove all header sections, empty lines, page break info
cleaned_lines = []
skip_next_header = False

for i, line in enumerate(lines):
    line_stripped = line.strip()
    
    # Skip metadata and page headers
    if (not line_stripped or 
        line_stripped.startswith(',,,') or 
        'QF-SPL-01' in line_stripped or
        'Page' in line_stripped or
        line_stripped == ''):
        continue
    
    # Skip header rows (check if line contains "Name of Grid" or is a multi-line header part)
    if 'Name of Grid' in line_stripped or 'Operation' in line_stripped and 'Zone' in line_stripped:
        # Skip the entire multi-line header block
        j = i
        while j < len(lines) and ('Zone' in lines[j] or 'Detail' in lines[j] or 'Total' in lines[j] or 'Transformer' in lines[j] or 'Capacity' in lines[j] or 'Voltage' in lines[j]):
            j += 1
        continue
    
    # Skip lines that are just parts of headers
    if line_stripped.startswith('SN,') and i+1 < len(lines) and ('Zone' in lines[i+1] or 'Detail' in lines[i+1]):
        continue
        
    cleaned_lines.append(line)

# Reconstruct CSV text
csv_text = ''.join(cleaned_lines)

# Parse using CSV reader with proper handling of multi-line quoted fields
reader = csv.reader(StringIO(csv_text), skipinitialspace=True)
all_rows = list(reader)

# Filter out rows that are not data rows or incomplete
data_rows = []
for row in all_rows:
    if not row or all(not cell.strip() for cell in row):
        continue
    
    # Skip if first cell is empty or doesn't start with a number
    if not row[0].strip() or not (row[0].strip()[0].isdigit() or row[0].strip() == '-'):
        continue
    
    # Clean the row
    cleaned_row = []
    for cell in row:
        # Replace newlines with space
        cell = cell.replace('\n', ' ').replace('\r', ' ').strip()
        # Remove page number references
        cell = re.sub(r'Pag\s+e\s+\d+\s+of\s+\d+', '', cell).strip()
        # Normalize multiple spaces
        cell = re.sub(r'\s+', ' ', cell)
        cleaned_row.append(cell)
    
    # Remove trailing empty columns
    while cleaned_row and not cleaned_row[-1]:
        cleaned_row.pop()
    
    if cleaned_row:
        data_rows.append(cleaned_row)

# Define header and normalize columns
target_header = ['SN', 'Name of Grid Substation', 'Operation Zone', 'Transformer Detail (MVA)', 
                 'Total Capacity (MVA)', 'Owership', 'Grid Circle', 'Voltage Level']

# Normalize each row to have 8 columns
formatted_rows = []
for row in data_rows:
    # Pad to 8 columns if needed
    while len(row) < 8:
        row.append('')
    # Trim to 8 columns
    row = row[:8]
    formatted_rows.append(row)

# Write the formatted CSV
with open('substations-formatted.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(target_header)
    writer.writerows(formatted_rows)

print(f"Successfully processed {len(formatted_rows)} data rows")
```

## Grids CSV Cleaning Code (Complex Version)

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

### Substations CSV Cleaning Process

1. **File Reading**: Read all lines from the raw CSV file
2. **Header Removal**: Skip metadata lines, page headers, and multi-line header blocks
3. **Line Filtering**: Remove empty lines and non-data content
4. **CSV Parsing**: Use Python's csv.reader to properly handle quoted fields
5. **Data Filtering**: Keep only rows starting with numbers (actual substation data)
6. **Cell Cleaning**: Remove newlines, normalize spaces, remove page artifacts
7. **Column Standardization**: Ensure all rows have exactly 8 columns
8. **Output**: Write clean CSV with standardized header

### Grids CSV Cleaning Process

1. **Setup and File Reading**: Import modules and read entire raw CSV as string
2. **Section Separation**: Use regex to split file by voltage level headers
3. **Voltage Section Processing**: Handle each voltage level (400kV, 230kV, 132kV) separately
4. **Data Processing Loop**: Parse CSV data for each section
5. **Row Filtering**: Skip headers, empty rows, and total rows
6. **Cell-Level Cleaning**: Remove newlines, extra whitespace, trailing empties
7. **Voltage-Specific Column Mapping**: Handle different column layouts for each voltage level
8. **Output Generation**: Write standardized 8-column format
9. **Statistics**: Generate processing summary by voltage level

## Voltage-Specific Column Mapping (Grids CSV)

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

## Final Output Formats

### Substations CSV Output
| Column | Description |
|--------|-------------|
| SN | Serial number |
| Name of Grid Substation | Substation name |
| Operation Zone | Operational zone |
| Transformer Detail (MVA) | Transformer specifications |
| Total Capacity (MVA) | Total capacity |
| Ownership | Owner organization |
| Grid Circle | Grid circle |
| Voltage Level | Voltage level |

### Grids CSV Output
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

## Processing Results Summary

### Substations CSV
- **Input:** Raw Excel-converted CSV with multi-line headers and page breaks
- **Output:** 251 clean data rows
- **Columns:** 8 standardized columns
- **Issues Fixed:** Multi-line headers, page artifacts, inconsistent formatting

### Grids CSV
- **Input:** Complex multi-section CSV with voltage level divisions
- **Output:** 354 clean data rows
- **Breakdown:** 28×400kV, 63×230kV, 263×132kV lines
- **Columns:** 8 standardized columns
- **Issues Fixed:** Multiple voltage sections, inconsistent column layouts, complex multi-line content

## Key Challenges Solved

### Both Files
- Multi-line headers spanning several rows
- Data rows split across multiple lines
- Page break artifacts and Excel conversion metadata
- Trailing empty cells and inconsistent formatting

### Grids CSV (Additional)
- Single file containing separate sections for different voltage levels
- Different column positioning for each voltage level
- Complex parsing required due to varying Excel layouts

## Usage Instructions

### For Similar Substation CSV Files:
1. Update file paths (`substations.csv` → `your_file.csv`)
2. Adjust header detection patterns if different
3. Modify target header columns as needed
4. Update output filename

### For Similar Grids CSV Files:
1. Update file path and voltage level regex patterns
2. Adjust column mapping logic for different voltage layouts
3. Modify output header and filename
4. Update voltage level detection patterns if needed

This documentation covers all cleaning operations performed in the current session for both CSV files.