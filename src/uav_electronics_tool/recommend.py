from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


G = 9.80665  # m/s^2


@dataclass
class Mission:
    n_motors: int = 4
    mass_kg: float = 2.0
    thrust_to_weight: float = 2.0
    battery_cells_s: int = 6
    # If you don't know voltage, we approximate from S count
    voltage_nom_v: Optional[float] = None


def nominal_voltage_from_s(cells_s: int) -> float:
    # LiPo nominal cell voltage ~3.7V
    return float(cells_s) * 3.7


def load_motors_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)


    required = [
        "id",
        "manufacturer",
        "model",
        "kv",
        "max_current_a",
        "max_power_w",
        "voltage_min_v",
        "voltage_max_v",
        "mass_g",
        "price_usd",
        "url",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"motors.csv missing columns: {missing}")

    numeric_cols = [
        "kv",
        "max_current_a",
        "max_power_w",
        "voltage_min_v",
        "voltage_max_v",
        "mass_g",
        "price_usd",
    ]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    bad = df[numeric_cols].isna().any(axis=1)
    if bad.any():
        bad_ids = df.loc[bad, "id"].tolist()
        raise ValueError(f"motors.csv has non-numeric values in rows: {bad_ids}")

    return df


def recommend_motors(motors: pd.DataFrame, mission: Mission) -> pd.DataFrame:
    v_nom = mission.voltage_nom_v or nominal_voltage_from_s(mission.battery_cells_s)

    # Required thrust (N) and per motor thrust
    total_thrust_n = mission.thrust_to_weight * mission.mass_kg * G
    thrust_per_motor_n = total_thrust_n / mission.n_motors

    # Convert thrust (N) to grams-force: 1 N ≈ 101.97 gf
    thrust_per_motor_gf = thrust_per_motor_n * 101.971621

    # Assume hover power per motor ≈ thrust_gf / (g_per_w)
    g_per_w = 7.0
    hover_power_w_est = thrust_per_motor_gf / g_per_w

    # Use a peak factor (maneuvers). For T/W=2, peak maybe ~1.6x hover estimate
    peak_factor = 1.6
    peak_power_w_est = hover_power_w_est * peak_factor

    # Electrical current estimate at nominal voltage
    peak_current_a_est = peak_power_w_est / max(v_nom, 1e-6)

    df = motors.copy()

    # Filters
    df = df[(df["voltage_min_v"] <= v_nom) & (v_nom <= df["voltage_max_v"])]

    # Margin checks
    df["power_margin"] = df["max_power_w"] / peak_power_w_est
    df["current_margin"] = df["max_current_a"] / peak_current_a_est

    # Keep only motors with >=20% margin
    df = df[(df["power_margin"] >= 1.2) & (df["current_margin"] >= 1.2)]

    # Score: prefer lighter + cheaper + higher margins
    # Normalize components to comparable scale
    df["mass_score"] = (df["mass_g"] - df["mass_g"].min()) / max((df["mass_g"].max() - df["mass_g"].min()), 1e-9)
    df["price_score"] = (df["price_usd"] - df["price_usd"].min()) / max((df["price_usd"].max() - df["price_usd"].min()), 1e-9)
    df["margin_score"] = 0.5 * df["power_margin"] + 0.5 * df["current_margin"]

    # Lower is better for mass/price; higher is better for margin
    # Weighted objective: 0.4 mass + 0.3 price - 0.3 margin
    df["score"] = 0.4 * df["mass_score"] + 0.3 * df["price_score"] - 0.3 * df["margin_score"]

    df["v_nom_used"] = v_nom
    df["thrust_per_motor_gf"] = thrust_per_motor_gf
    df["hover_power_w_est"] = hover_power_w_est
    df["peak_power_w_est"] = peak_power_w_est
    df["peak_current_a_est"] = peak_current_a_est

    # Sort best first
    df = df.sort_values("score", ascending=True).reset_index(drop=True)
    return df


def save_recommendations(df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "id",
        "manufacturer",
        "model",
        "kv",
        "mass_g",
        "price_usd",
        "voltage_min_v",
        "voltage_max_v",
        "max_power_w",
        "max_current_a",
        "power_margin",
        "current_margin",
        "score",
        "url",
        "v_nom_used",
        "thrust_per_motor_gf",
        "hover_power_w_est",
        "peak_power_w_est",
        "peak_current_a_est",
    ]
    df.to_csv(out_path, index=False, columns=[c for c in cols if c in df.columns])