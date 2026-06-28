#!/usr/bin/env python3
"""
fetch_and_split_sheet.py

Downloads a Google Sheet as a single .xlsx workbook, saving it over the
source workbook (default: data/pipeline/raw/pypsa_dataset.xlsx), then splits
selected tabs from it into individual .xlsx files in the same directory using
a sheet-name -> file-name mapping.

The mapping and source spreadsheet are read from a JSON config file
(default: sheet-mapping.json next to this script):

    {
      "spreadsheet": "<full URL or document ID>",
      "output_dir": "data/pipeline/raw",
      "workbook": "pypsa_dataset.xlsx",
      "sheets": {
        "<tab name in the Google Sheet>": "<output-file.xlsx>",
        ...
      }
    }

The Google Sheet must be shared "anyone with the link" so it can be
exported without credentials.

Usage:
    python src/fetch_and_split_sheet.py
    python src/fetch_and_split_sheet.py --config path/to/mapping.json
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DEFAULT_CONFIG = SCRIPT_DIR / "sheet-mapping.json"


def parse_spreadsheet_id(spreadsheet: str) -> str:
    """Accept either a full Google Sheets URL or a bare document ID."""
    spreadsheet = spreadsheet.strip()
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", spreadsheet)
    if m:
        return m.group(1)
    if "PUT_GOOGLE_SHEET" in spreadsheet or not spreadsheet:
        sys.exit("ERROR: set 'spreadsheet' in the config to the Google Sheet URL or ID.")
    return spreadsheet  # assume it is already a bare ID


def download_workbook(spreadsheet_id: str, dest: Path) -> None:
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=xlsx"
    print(f">>> Downloading workbook: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
    # A non-public / wrong-id sheet returns an HTML sign-in page, not xlsx.
    if data[:2] != b"PK":
        sys.exit(
            "ERROR: download did not return an .xlsx file. "
            "Check that the sheet is shared 'anyone with the link' and the URL/ID is correct."
        )
    dest.write_bytes(data)
    print(f"    saved {len(data):,} bytes -> {dest}")


def split_workbook(workbook: Path, mapping: dict[str, str], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Use a context manager so the file handle is released — otherwise Windows
    # cannot delete the temp directory while the workbook is still open.
    with pd.ExcelFile(workbook) as xls:
        available = xls.sheet_names
        print(f">>> Workbook tabs found: {available}")

        missing = [s for s in mapping if s not in available]
        if missing:
            sys.exit(
                f"ERROR: these mapped tabs are not in the workbook: {missing}\n"
                f"       available tabs: {available}"
            )

        for sheet_name, file_name in mapping.items():
            # header=None preserves the exact cell grid the downstream builders expect.
            df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
            out_path = out_dir / file_name
            df.to_excel(out_path, index=False, header=False)
            print(f"    '{sheet_name}'  ->  {out_path}  ({df.shape[0]} rows x {df.shape[1]} cols)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                    help=f"Path to the JSON mapping config (default: {DEFAULT_CONFIG})")
    args = ap.parse_args()

    if not args.config.exists():
        sys.exit(f"ERROR: config not found: {args.config}")

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    spreadsheet_id = parse_spreadsheet_id(cfg.get("spreadsheet", ""))
    mapping = cfg.get("sheets", {})
    if not mapping:
        sys.exit("ERROR: config 'sheets' mapping is empty.")

    out_dir = Path(cfg.get("output_dir", "data/pipeline/raw"))
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # Download the full workbook over the existing source file, then split it.
    workbook = out_dir / cfg.get("workbook", "pypsa_dataset.xlsx")
    download_workbook(spreadsheet_id, workbook)
    split_workbook(workbook, mapping, out_dir)

    print(">>> Done.")


if __name__ == "__main__":
    main()
