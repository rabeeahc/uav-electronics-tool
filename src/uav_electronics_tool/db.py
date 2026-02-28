from __future__ import annotations
from pathlib import Path
import pandas as pd
from rich import print

REQUIRED_COLUMNS = {
    "motors.csv": [
        "id","manufacturer","model","kv","max_current_a","max_power_w",
        "voltage_min_v","voltage_max_v","mass_g","price_usd","url"
    ],
    "batteries.csv": [
        "id","manufacturer","model","cells_s","capacity_mah","c_rating",
        "voltage_nom_v","max_discharge_a","mass_g","price_usd","url"
    ]
}

def validate_csv(path: Path, required: list[str]) -> tuple[bool, list[str]]:
    df = pd.read_csv(path)
    missing = [c for c in required if c not in df.columns]
    return (len(missing) == 0), missing

def validate_db(data_dir: Path = Path("data")) -> int:
    ok_all = True
    csv_files = list(data_dir.glob("*.csv"))
    
    if not csv_files:
        print(f"[yellow]No CSV files found in {data_dir}[/yellow]")
        return 0

    for fpath in csv_files:
        filename = fpath.name
        if filename not in REQUIRED_COLUMNS:
            print(f"[yellow]Skipping unknown schema:[/yellow] {filename}")
            continue
            
        required = REQUIRED_COLUMNS[filename]
        ok, missing = validate_csv(fpath, required)
        if ok:
            print(f"[green]OK:[/green] {filename}")
        else:
            print(f"[red]Bad columns in {filename}[/red] → missing: {missing}")
            ok_all = False
            
    # Optionally also check if any REQUIRED_COLUMNS are missing
    for filename in REQUIRED_COLUMNS:
        if not (data_dir / filename).exists():
            print(f"[red]Missing required file:[/red] {filename}")
            ok_all = False

    return 0 if ok_all else 1