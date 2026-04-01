from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import math

import pandas as pd


G = 9.80665  # m/s^2


@dataclass
class Mission:
    n_motors: int = 4
    mass_kg: float = 2.0
    thrust_to_weight: float = 2.0
    battery_cells_s: int = 6
    voltage_nom_v: Optional[float] = None


@dataclass
class SystemRecommendations:
    motors: pd.DataFrame
    escs: pd.DataFrame
    batteries: pd.DataFrame
    propellers: pd.DataFrame
    
    @property
    def is_empty(self) -> bool:
        return self.motors.empty and self.escs.empty and self.batteries.empty and self.propellers.empty


def nominal_voltage_from_s(cells_s: int) -> float:
    return float(cells_s) * 3.7


def recommend_motors(motors: pd.DataFrame, mission: Mission) -> tuple[pd.DataFrame, float]:
    """Returns (recommended_motors_df, peak_current_target)."""
    if motors.empty or "max_current_a" not in motors.columns:
        return pd.DataFrame(), 0.0
        
    v_nom = mission.voltage_nom_v or nominal_voltage_from_s(mission.battery_cells_s)
    total_thrust_n = mission.thrust_to_weight * mission.mass_kg * G
    thrust_per_motor_n = total_thrust_n / mission.n_motors
    thrust_per_motor_gf = thrust_per_motor_n * 101.971621

    hover_power_w_est = thrust_per_motor_gf / 7.0
    peak_power_w_est = hover_power_w_est * 1.6
    peak_current_a_est = peak_power_w_est / max(v_nom, 1e-6)

    df = motors.copy()
    if "voltage_min_v" in df.columns and "voltage_max_v" in df.columns:
        df = df[(df["voltage_min_v"] <= v_nom) & (v_nom <= df["voltage_max_v"])]

    if "max_power_w" in df.columns:
        df["power_margin"] = df["max_power_w"] / peak_power_w_est
    else:
        df["power_margin"] = 1.5

    if "max_current_a" in df.columns:
        df["current_margin"] = df["max_current_a"] / peak_current_a_est
    else:
        df["current_margin"] = 1.5

    df = df[(df["power_margin"] >= 1.2) & (df["current_margin"] >= 1.2)]

    df["mass_score"] = (df["mass_g"] - df["mass_g"].min()) / max((df["mass_g"].max() - df["mass_g"].min()), 1e-9) if "mass_g" in df.columns else 0.5
    df["price_score"] = (df["price_usd"] - df["price_usd"].min()) / max((df["price_usd"].max() - df["price_usd"].min()), 1e-9) if "price_usd" in df.columns else 0.5
    df["margin_score"] = 0.5 * df["power_margin"] + 0.5 * df["current_margin"]

    df["score"] = 0.4 * df["mass_score"] + 0.3 * df["price_score"] - 0.3 * df["margin_score"]
    
    df["v_nom_used"] = v_nom
    df["thrust_per_motor_gf"] = thrust_per_motor_gf
    df["hover_power_w_est"] = hover_power_w_est
    df["peak_power_w_est"] = peak_power_w_est
    df["peak_current_a_est"] = peak_current_a_est

    return df.sort_values("score", ascending=True).reset_index(drop=True), peak_current_a_est


def recommend_escs(escs: pd.DataFrame, mission: Mission, peak_current: float) -> pd.DataFrame:
    if escs.empty or "max_current_a" not in escs.columns:
        return pd.DataFrame()
        
    v_nom = mission.voltage_nom_v or nominal_voltage_from_s(mission.battery_cells_s)
    df = escs.copy()
    
    if "voltage_max_v" in df.columns:
        df = df[df["voltage_max_v"] >= v_nom]
        
    df["current_margin"] = df["max_current_a"] / max(peak_current, 1e-6)
    df = df[df["current_margin"] >= 1.2]
    
    # Prefer lightweight and cheap ESCs that still cover the current needed
    df["mass_score"] = (df["mass_g"] - df["mass_g"].min()) / max((df["mass_g"].max() - df["mass_g"].min()), 1e-9) if "mass_g" in df.columns else 0.5
    df["price_score"] = (df["price_usd"] - df["price_usd"].min()) / max((df["price_usd"].max() - df["price_usd"].min()), 1e-9) if "price_usd" in df.columns else 0.5
    df["score"] = 0.5 * df["mass_score"] + 0.5 * df["price_score"] - 0.1 * df["current_margin"]
    
    return df.sort_values("score", ascending=True).reset_index(drop=True)


def recommend_batteries(batteries: pd.DataFrame, mission: Mission, peak_current: float) -> pd.DataFrame:
    if batteries.empty or "capacity_mah" not in batteries.columns or "c_rating" not in batteries.columns:
        return pd.DataFrame()
        
    total_peak = peak_current * mission.n_motors
    df = batteries.copy()
    
    if "cells_s" in df.columns:
        # allow ±1S matching if some DBs are weird, ideally exact match
        df = df[df["cells_s"] == mission.battery_cells_s]
        
    # Calculate max possible continuous Ampere output
    df["max_amps_continuous"] = (df["capacity_mah"] / 1000.0) * df["c_rating"]
    df["amp_margin"] = df["max_amps_continuous"] / max(total_peak, 1e-6)
    
    df = df[df["amp_margin"] >= 1.1]  # needs to at least support 110% peak
    
    df["cap_score"] = 1.0 - ((df["capacity_mah"] - df["capacity_mah"].min()) / max((df["capacity_mah"].max() - df["capacity_mah"].min()), 1e-9))
    df["mass_score"] = (df["mass_g"] - df["mass_g"].min()) / max((df["mass_g"].max() - df["mass_g"].min()), 1e-9) if "mass_g" in df.columns else 0.5
    df["price_score"] = (df["price_usd"] - df["price_usd"].min()) / max((df["price_usd"].max() - df["price_usd"].min()), 1e-9) if "price_usd" in df.columns else 0.5
    
    df["score"] = 0.4 * df["cap_score"] + 0.4 * df["mass_score"] + 0.2 * df["price_score"]
    return df.sort_values("score", ascending=True).reset_index(drop=True)


def recommend_propellers(propellers: pd.DataFrame, mission: Mission) -> pd.DataFrame:
    if propellers.empty or "diameter_in" not in propellers.columns:
        return pd.DataFrame()
        
    # Generic rule of thumb sizing
    total_thrust_n = mission.thrust_to_weight * mission.mass_kg * G
    thrust_per_motor_gf = (total_thrust_n / mission.n_motors) * 101.971621
    
    # target diameter inches loosely correlated to thrust
    target_diam = 2.5 * math.sqrt(thrust_per_motor_gf / 100.0)
    
    df = propellers.copy()
    df["diam_diff"] = abs(df["diameter_in"] - target_diam)
    
    # keep propellers within +/- 1.5 inches of optimal geometric size
    df = df[df["diam_diff"] <= 1.5]
    
    df["mass_score"] = (df["mass_g"] - df["mass_g"].min()) / max((df["mass_g"].max() - df["mass_g"].min()), 1e-9) if "mass_g" in df.columns else 0.5
    df["score"] = 0.7 * (df["diam_diff"] / max(df["diam_diff"].max(), 1e-9)) + 0.3 * df["mass_score"]
    
    return df.sort_values("score", ascending=True).reset_index(drop=True)


def recommend_system(db: dict[str, pd.DataFrame], mission: Mission) -> SystemRecommendations:
    motors_req, peak_a = recommend_motors(db.get("motors", pd.DataFrame()), mission)
    
    escs_req = recommend_escs(db.get("escs", pd.DataFrame()), mission, peak_a)
    bats_req = recommend_batteries(db.get("batteries", pd.DataFrame()), mission, peak_a)
    props_req = recommend_propellers(db.get("propellers", pd.DataFrame()), mission)
    
    return SystemRecommendations(motors_req, escs_req, bats_req, props_req)


def save_system_recommendations(sys: SystemRecommendations, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    
    def save(df: pd.DataFrame, name: str):
        if not df.empty:
            df.to_csv(out_dir / f"recommendations_{name}.csv", index=False)
            
    save(sys.motors, "motors")
    save(sys.escs, "escs")
    save(sys.batteries, "batteries")
    save(sys.propellers, "propellers")