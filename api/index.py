import os
import json
import math
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, root_validator
from typing import Optional

from src.uav_electronics_tool.recommend import Mission, recommend_system
from src.uav_electronics_tool.db import load_database

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Database into memory globally (since Vercel keeps instances warm temporarily)
DATA_DIR = Path(__file__).parent.parent / "data"
db = load_database(DATA_DIR)

class MissionRequest(BaseModel):
    n_motors: int = 4
    mass_kg: float = 2.0
    tw: float = 2.0
    cells: int = 6
    v_nom: Optional[float] = None
    top_n: int = 10

@app.post("/api/recommend")
def recommend_endpoint(req: MissionRequest):
    global db
    if all(v.empty for v in db.values()):
        # Retry load just in case (Vercel warm booting weirdness)
        db = load_database(DATA_DIR)
        
    mission = Mission(
        n_motors=req.n_motors,
        mass_kg=req.mass_kg,
        thrust_to_weight=req.tw,
        battery_cells_s=req.cells,
        voltage_nom_v=req.v_nom
    )
    
    sys_recs = recommend_system(db, mission)
    
    # We need to replace NaN and Infinity for JSON compliance since pandas might output NaNs
    def clean_df(df, cols):
        if df is None or df.empty:
            return []
        
        selected = df[[c for c in cols if c in df.columns]].copy()
        selected = selected.replace([math.inf, -math.inf], None)
        selected = selected.fillna("N/A")
        return selected.head(req.top_n).to_dict(orient="records")

    return {
        "motors": clean_df(sys_recs.motors, ["manufacturer", "model", "kv", "mass_g", "price_usd", "score"]),
        "escs": clean_df(sys_recs.escs, ["manufacturer", "model", "max_current_a", "voltage_max_v", "mass_g", "score"]),
        "batteries": clean_df(sys_recs.batteries, ["manufacturer", "model", "cells_s", "capacity_mah", "c_rating", "mass_g", "score"]),
        "propellers": clean_df(sys_recs.propellers, ["manufacturer", "model", "diameter_in", "pitch_in", "mass_g", "score"])
    }

@app.get("/api/health")
def health():
    return {"status": "ok", "db_loaded": not all(v.empty for v in db.values())}

if os.path.isdir(os.path.join(os.getcwd(), "public")):
    app.mount("/", StaticFiles(directory="public", html=True), name="static")
