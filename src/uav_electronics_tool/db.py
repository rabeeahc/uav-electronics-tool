from __future__ import annotations
from pathlib import Path
import pandas as pd
from rich import print

def load_csv_robust(path: Path) -> pd.DataFrame:
    """Load a CSV file, auto-detecting comma or semicolon delimiters."""
    try:
        df = pd.read_csv(path, sep=';')
        if len(df.columns) <= 1:
            df = pd.read_csv(path, sep=',')
    except Exception:
        df = pd.read_csv(path, sep=',')
        
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    return df

def clean_batteries(df: pd.DataFrame) -> pd.DataFrame:
    has_cap = "Capacity_mAh" in df.columns
    has_cap_lower = "capacity_mah" in df.columns
    if has_cap:
        df = df.rename(columns={
            "Capacity_mAh": "capacity_mah",
            "n_series": "cells_s",
            "Weight_kg": "mass_kg",
            "TYPE": "manufacturer",
            "Model": "model",
            "Discharge_Rate_C": "c_rating",
            "Voltage_V": "voltage_nom_v",
            "Imax_A": "max_discharge_a"
        })
        if "mass_kg" in df.columns:
            df["mass_g"] = df["mass_kg"] * 1000
    if has_cap or has_cap_lower:
        if "price_usd" not in df.columns:
            df["price_usd"] = 50.0
        if "url" not in df.columns:
            df["url"] = ""
        if "id" not in df.columns:
            df["id"] = ["bat_" + str(i) for i in range(len(df))]
    return df

def clean_motors(df: pd.DataFrame) -> pd.DataFrame:
    if "Kv_rpm_v" in df.columns:
        df = df.rename(columns={
            "Kv_rpm_v": "kv",
            "TYPE": "manufacturer",
            "Model": "model",
            "Mass_g": "mass_g",
            "Imax_A" : "max_current_a",
            "Imax (A)": "max_current_a",
        })
        if "Voltage" in df.columns:
            df["max_power_w"] = df["Voltage"] * df["max_current_a"]
            df["voltage_max_v"] = df["Voltage"]
            df["voltage_min_v"] = 7.4
    if "kv" in df.columns:
        if "price_usd" not in df.columns:
            df["price_usd"] = 50.0
        if "url" not in df.columns:
            df["url"] = ""
        if "id" not in df.columns:
            df["id"] = ["mtr_" + str(i) for i in range(len(df))]
    return df

def clean_escs(df: pd.DataFrame) -> pd.DataFrame:
    has_imax = "I_max_A" in df.columns or "Imax_A" in df.columns
    has_imax_lower = "max_current_a" in df.columns
    if has_imax:
        df = df.rename(columns={
            "I_max_A": "max_current_a",
            "Imax_A": "max_current_a",
            "Mass_g": "mass_g",
            "Weight_g": "mass_g",
            "V_max_V": "voltage_max_v",
            "Vmax_V": "voltage_max_v",
            "Power_max_W": "max_power_w",
            "Pmax_W": "max_power_w",
            "TYPE": "manufacturer",
            "Model": "model",
        })
    if has_imax or has_imax_lower:
        if "price_usd" not in df.columns:
            df["price_usd"] = 30.0
        if "url" not in df.columns:
            df["url"] = ""
        if "id" not in df.columns:
            df["id"] = ["esc_" + str(i) for i in range(len(df))]
    return df

def clean_propellers(df: pd.DataFrame) -> pd.DataFrame:
    if "Product Name" in df.columns:
        df = df.rename(columns={
            "Product Name": "model",
            "Diameter (INCHES)": "diameter_in",
            "Pitch (INCHES)": "pitch_in",
            "Weight (grams)": "mass_g",
            "Product Weight (NOT for Shipping Calculations) (grams) ": "mass_g"
        })
        df["manufacturer"] = "APC"
    elif "DIAMETER_IN" in df.columns: # Performances file
        df = df.rename(columns={
            "DIAMETER_IN": "diameter_in",
            "TYPE": "manufacturer",
            "Model": "model", 
            "Ct": "ct",
            "Cp": "cp",
        })
        if "BETA" in df.columns:
            df["pitch_in"] = df["diameter_in"] * df["BETA"]
        if "mass_g" not in df.columns:
            df["mass_g"] = 15.0
    
    if "diameter_in" in df.columns:
        if "price_usd" not in df.columns:
            df["price_usd"] = 10.0
        if "url" not in df.columns:
            df["url"] = ""
        if "id" not in df.columns:
            df["id"] = ["prop_" + str(i) for i in range(len(df))]
    return df

def load_database(data_dir: Path) -> dict[str, pd.DataFrame]:
    db = {"motors": pd.DataFrame(), "batteries": pd.DataFrame(), "escs": pd.DataFrame(), "propellers": pd.DataFrame()}
    if not data_dir.exists():
        return db
        
    for fpath in data_dir.rglob("*.csv"):
        name = fpath.name.lower()
        parts = [p.lower() for p in fpath.parts]
        try:
            df = load_csv_robust(fpath)
            if df.empty:
                continue
                
            if "batteries" in parts or "bat" in name:
                db["batteries"] = pd.concat([db["batteries"], clean_batteries(df)])
            elif "motors" in parts or "mot" in name:
                db["motors"] = pd.concat([db["motors"], clean_motors(df)])
            elif "esc" in parts or "esc" in name:
                db["escs"] = pd.concat([db["escs"], clean_escs(df)])
            elif "propellers" in parts or "prop" in name:
                db["propellers"] = pd.concat([db["propellers"], clean_propellers(df)])
        except Exception as e:
            print(f"[red]Error loading {fpath.name}: {e}[/red]")
            
    for k in db:
        if not db[k].empty:
            db[k] = db[k].dropna(how='all', axis=1)
            # Do NOT use model, since same model string is used for different cells_s in batteries
            db[k] = db[k].drop_duplicates()
            
    return db

def validate_db(data_dir: Path = Path("data")) -> int:
    db = load_database(data_dir)
    ok_all = True
    print(f"[bold blue]Scanning {data_dir.resolve()}...[/bold blue]")
    for k, v in db.items():
        if v.empty:
            print(f"[yellow]Warning: No data loaded for {k}[/yellow]")
            ok_all = False
        else:
            print(f"[green]OK:[/green] {k} -> {len(v)} unique items")
    return 0 if ok_all else 1